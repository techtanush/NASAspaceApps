"""DIAGNOSE_RESULT policy table, graph-scenario design details and the ANALYSIS_GRID reader wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import (  # noqa: E402
    graph_design,
    graph_design_with,
    make_grid,
    make_route,
    rebuild,
    rover,
)

from analogforge.ports import catalog  # noqa: E402
from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.ports.science_payloads import (  # noqa: E402
    AttemptSummary,
    DiagnoseResultInput,
    RouteViolation,
    VerificationSummary,
)
from analogforge.science.geometry import AnalysisGridSpec  # noqa: E402
from analogforge.science.raster.store import build_analysis_grid, encode_analysis_grid  # noqa: E402
from analogforge.science.routing import RouteInputError, load_grid_arrays  # noqa: E402
from analogforge.science.routing.diagnose import diagnose_result  # noqa: E402
from analogforge.science.routing.fixture_graph import canonical_graph_spec  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402


def attempt(n: int, strategy: str, outcome: str = "FAIL", window: str = catalog.GRAPH_WINDOW_ID) -> AttemptSummary:
    return AttemptSummary(
        attempt_number=n,
        test_revision=n,
        candidate_window_id=window,
        strategy=strategy,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        failure_category="ROUTE" if outcome == "FAIL" else None,
        search_status="FOUND",
    )


def violation(code: str = "EXPOSURE_SHORTFALL", cid: str = "C-EXPOSURE-R-EXPOSURE") -> RouteViolation:
    return RouteViolation(
        code=code, requirement_id="R-EXPOSURE", constraint_id=cid, observed=0.0, threshold=100.0, unit="m", message="x"
    )  # type: ignore[arg-type]


def diag(
    strategy: str,
    *,
    status="FOUND",
    outcome="FAIL",
    category="ROUTE",
    codes=("EXPOSURE_SHORTFALL",),
    history=(),
    repairs=2,
    switches=1,
    constraints=None,
):  # noqa: ANN001, ANN002, ANN003, ANN202
    design = graph_design(strategy)  # type: ignore[arg-type]
    return diagnose_result(
        DiagnoseResultInput(
            constraints=constraints or design.constraints,
            search_status=status,  # type: ignore[arg-type]
            verification=VerificationSummary(outcome=outcome, failure_category=category),  # type: ignore[arg-type]
            violations=[violation(c) for c in codes],
            attempt_history=list(history),
            remaining_route_repairs=repairs,
            remaining_candidate_switches=switches,
        ),
        mode="synthetic",
    ).payload


def test_route_failure_recommends_untried_exposure_coverage() -> None:
    d = diag("WAYPOINT_RETURN", history=[attempt(1, "WAYPOINT_RETURN")])
    assert (d.primary_category, d.permitted_repairs, d.recommended_repair, d.recommended_strategy) == (
        "ROUTE",
        ["NEW_ROUTE"],
        "NEW_ROUTE",
        "EXPOSURE_COVERAGE",
    )
    assert d.violated_constraint_ids == ["C-EXPOSURE-R-EXPOSURE"] and d.proof_scope == "evaluated route only"


def test_route_failure_with_no_untried_strategy_switches_candidate_or_stops() -> None:
    history = [attempt(1, "WAYPOINT_RETURN"), attempt(2, "EXPOSURE_COVERAGE")]
    # a *different candidate's* history does not count as tried on this one
    other = diag("WAYPOINT_RETURN", history=[attempt(1, "EXPOSURE_COVERAGE", window="grid-other")])
    assert other.recommended_strategy == "EXPOSURE_COVERAGE"
    switch = diag("EXPOSURE_COVERAGE", history=history)
    assert (switch.permitted_repairs, switch.recommended_repair, switch.recommended_strategy) == (
        ["NEW_CANDIDATE"],
        "NEW_CANDIDATE",
        None,
    )
    stop = diag("EXPOSURE_COVERAGE", history=history, switches=0)
    assert stop.permitted_repairs == [] and stop.recommended_repair is None
    no_route_budget = diag("WAYPOINT_RETURN", history=[attempt(1, "WAYPOINT_RETURN")], repairs=0)
    assert no_route_budget.permitted_repairs == ["NEW_CANDIDATE"]  # route repairs exhausted, candidate switch left
    nothing = diag("WAYPOINT_RETURN", repairs=0, switches=0)
    assert nothing.permitted_repairs == []


def test_energy_failures_recommend_min_energy_strategy_and_hard_violations_recovery() -> None:
    energy = diag("EXPOSURE_COVERAGE", codes=("ENERGY_RESERVE_SHORTFALL",), history=[attempt(1, "EXPOSURE_COVERAGE")])
    assert energy.recommended_strategy == "MINIMUM_FEASIBLE_ROUTE"
    hard = diag("EXPOSURE_COVERAGE", codes=("FORBIDDEN_INTERSECTION",), history=[attempt(1, "EXPOSURE_COVERAGE")])
    assert hard.recommended_strategy == "RECOVERY_ALTERNATIVE"
    tried = diag(
        "EXPOSURE_COVERAGE", codes=("ENERGY_RESERVE_SHORTFALL",), history=[attempt(1, "MINIMUM_FEASIBLE_ROUTE")]
    )
    assert tried.recommended_strategy is None and tried.permitted_repairs == ["NEW_CANDIDATE"]


def test_budget_exhausted_is_search_limit_never_analog() -> None:
    d = diag("EXPOSURE_COVERAGE", status="BUDGET_EXHAUSTED", outcome="INCONCLUSIVE", category="SEARCH_LIMIT", codes=())
    assert d.primary_category == "SEARCH_LIMIT" and d.recommended_repair == "NEW_ROUTE"
    assert d.recommended_strategy in {"MINIMUM_FEASIBLE_ROUTE", "WAYPOINT_RETURN"} and d.violated_constraint_ids == []
    spent = diag(
        "EXPOSURE_COVERAGE",
        status="BUDGET_EXHAUSTED",
        outcome="INCONCLUSIVE",
        category="SEARCH_LIMIT",
        codes=(),
        history=[attempt(1, "WAYPOINT_RETURN"), attempt(2, "MINIMUM_FEASIBLE_ROUTE")],
    )
    assert spent.permitted_repairs == [] and spent.primary_category == "SEARCH_LIMIT"
    no_repairs = diag(
        "EXPOSURE_COVERAGE",
        status="BUDGET_EXHAUSTED",
        outcome="INCONCLUSIVE",
        category="SEARCH_LIMIT",
        codes=(),
        repairs=0,
    )
    assert no_repairs.permitted_repairs == []


def test_data_system_requirement_and_pass_branches() -> None:
    data = diag("EXPOSURE_COVERAGE", outcome="INCONCLUSIVE", category="DATA", codes=())
    assert (data.primary_category, data.permitted_repairs, data.recommended_repair) == (
        "DATA",
        ["DATA_REPAIR"],
        "DATA_REPAIR",
    )
    system = diag("EXPOSURE_COVERAGE", outcome="INCONCLUSIVE", category="SYSTEM", codes=("STALE_INPUT_HASH",))
    assert system.primary_category == "SYSTEM" and system.permitted_repairs == []
    req = diag("EXPOSURE_COVERAGE", outcome="INCONCLUSIVE", category="REQUIREMENT", codes=())
    assert req.primary_category == "REQUIREMENT" and req.permitted_repairs == []
    ok = diag("EXPOSURE_COVERAGE", outcome="PASS", category=None, codes=())
    assert ok.primary_category is None and ok.permitted_repairs == [] and ok.recommended_repair is None
    err = diag("EXPOSURE_COVERAGE", status="ERROR", outcome="INCONCLUSIVE", category="SYSTEM", codes=())
    assert err.primary_category == "SYSTEM"


def test_exhaustive_infeasible_analog_vs_rover_on_the_graph() -> None:
    # all 15 degree edges removed: still infeasible when the cap is lifted -> ANALOG
    analog_design = graph_design_with(canonical_graph_spec(drop_edges=[("S", "B"), ("B", "C"), ("C", "W1")]))
    d = diagnose_result(
        DiagnoseResultInput(
            constraints=analog_design.constraints,
            search_status="EXHAUSTIVE_INFEASIBLE",
            verification=VerificationSummary(outcome="FAIL", failure_category=None),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        ),
        mode="synthetic",
    ).payload
    assert d.primary_category == "ANALOG" and d.permitted_repairs == ["NEW_CANDIDATE"]
    # same graph, but the 15 degree edges exist and the rover cap (12) forbids them -> ROVER
    capped = graph_design("EXPOSURE_COVERAGE", rover_obj=rover("practice-lite"))
    out = search_route(capped.constraints, capped.constraints_sha256, mode="synthetic")
    assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    r = diagnose_result(
        DiagnoseResultInput(
            constraints=capped.constraints,
            search_status="EXHAUSTIVE_INFEASIBLE",
            verification=VerificationSummary(outcome="FAIL", failure_category=None),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        ),
        mode="synthetic",
    ).payload
    assert (
        r.primary_category == "ROVER"
        and r.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
        and r.recommended_repair is None
    )


def test_enumeration_infeasibility_is_classified_by_a_relaxed_search() -> None:
    """max_distance 229: the certificate cannot prove it; rover relaxation does not help -> ANALOG (by search)."""
    design = graph_design("EXPOSURE_COVERAGE")
    tight, _ = rebuild(design.constraints, max_distance_m=229.0)
    d = diagnose_result(
        DiagnoseResultInput(
            constraints=tight,
            search_status="EXHAUSTIVE_INFEASIBLE",
            verification=VerificationSummary(outcome="FAIL", failure_category=None),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=0,
        ),
        mode="synthetic",
    ).payload
    assert d.primary_category == "ANALOG" and d.permitted_repairs == ["COMPOSITE_PORTFOLIO"]


def test_diagnosis_never_relaxes_a_requirement() -> None:
    """Every payload only offers repairs from the allowed set and none changes thresholds (they are not even fields)."""
    allowed = {"NEW_ROUTE", "NEW_CANDIDATE", "COMPOSITE_PORTFOLIO", "DATA_REPAIR", "NEW_CONTRACT_REQUIRED"}
    for strategy in ("WAYPOINT_RETURN", "EXPOSURE_COVERAGE"):
        for status, outcome, category in (
            ("FOUND", "FAIL", "ROUTE"),
            ("BUDGET_EXHAUSTED", "INCONCLUSIVE", "SEARCH_LIMIT"),
        ):
            d = diag(strategy, status=status, outcome=outcome, category=category)
            assert set(d.permitted_repairs) <= allowed and "NEW_ZONE" not in d.permitted_repairs


# ------------------------------------------------------------------------------------------------ graph design details
def test_graph_design_respects_rover_and_blocked_edges() -> None:
    d = graph_design("RECOVERY_ALTERNATIVE", blocked=["B--C"])
    assert d.constraints.blocked_edge_ids == ["B--C"] and d.constraints.strategy == "RECOVERY_ALTERNATIVE"
    out = search_route(d.constraints, d.constraints_sha256, mode="synthetic")
    assert out.route is not None and "B" not in zip(out.route.node_sequence, out.route.node_sequence[1:], strict=False)
    pairs = {frozenset(p) for p in zip(out.route.node_sequence, out.route.node_sequence[1:], strict=False)}
    assert frozenset(("B", "C")) not in pairs
    route = make_route(d.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS, strategy="RECOVERY_ALTERNATIVE")
    ver = verify_route(d.constraints, d.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
    assert ver.payload.outcome == "FAIL" and "FORBIDDEN_INTERSECTION" in {v.code for v in ver.payload.violations}


def test_graph_scenario_stays_evaluable_without_a_rover_energy_model() -> None:
    """The mock provider is accounting-only: it does not need (or read) the rover's energy model."""
    d = graph_design("EXPOSURE_COVERAGE", rover_obj=rover("practice-no-energy-model"))
    assert d.constraints.energy.model is None
    assert {m.requirement_id: m.treatment for m in d.requirement_mapping}["R-RESERVE"] == "VERIFIED_BY_TOOL"
    route = make_route(d.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    ver = verify_route(d.constraints, d.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
    assert ver.payload.outcome == "PASS"


# ------------------------------------------------------------------------------------------------ ANALYSIS_GRID reader
def _container(tmp_path: Path) -> tuple[Path, str]:
    shape = (6, 7)
    spec = AnalysisGridSpec("EARTH", "TEST", 1000.0, 2000.0, 60.0, 7, 6)
    grid = build_analysis_grid(
        spec,
        elevation_m=np.arange(42, dtype=float).reshape(shape),
        valid=np.ones(shape, bool),
        land=np.ones(shape, bool),
        slope_deg=np.full(shape, 4.0),
        aspect_deg=np.zeros(shape),
        quality=np.zeros(shape, np.uint8),
        source_evidence_ids=("a",),
        algorithm_id="analyze-candidate",
        algorithm_version="1",
        parameters_sha256="0" * 64,
    )
    data = encode_analysis_grid(grid)
    path = tmp_path / "grid.npz"
    path.write_bytes(data)
    from analogforge.ports.hashing import bytes_sha256

    return path, bytes_sha256(data)


def test_grid_reader_round_trip_and_stale_hash(tmp_path: Path) -> None:
    path, digest = _container(tmp_path)
    arrays = load_grid_arrays(path, digest)
    assert (arrays.height, arrays.width, arrays.cell_size_m, arrays.origin_x_m, arrays.origin_y_m) == (
        6,
        7,
        60.0,
        1000.0,
        2000.0,
    )
    assert arrays.center_xy(0, 0) == (1030.0, 1970.0) and arrays.cell_of(1030.0, 1970.0) == (0, 0)
    assert float(arrays.elevation_m[2, 3]) == 17.0
    with pytest.raises(RouteInputError) as err:
        load_grid_arrays(path, "f" * 64)
    assert err.value.code == "STALE_INPUT_HASH"


def test_search_rejects_grid_that_does_not_match_the_constraints() -> None:
    grid = make_grid(np.full((8, 8), 3.0))
    from test_routing_support import raster_constraints

    art, digest = raster_constraints(grid, start=(4, 1), tasks=[("W1", (4, 5))], strategy="WAYPOINT_RETURN")
    other = make_grid(np.full((9, 9), 3.0))
    with pytest.raises(RouteInputError) as err:
        search_route(art, digest, grid=other, mode="synthetic")
    assert err.value.detail_code == "GRID_SPEC_MISMATCH"
    with pytest.raises(RouteInputError) as err2:
        search_route(art, digest, grid=None, mode="synthetic")
    assert err2.value.detail_code == "ANALYSIS_GRID_MISSING"
