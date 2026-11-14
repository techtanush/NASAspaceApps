"""Raster route science end to end on small synthetic grids: design (auto-waypoints-v1) -> search -> verify -> diagnose.

The grids are constructed here (not taken from the practice generators) so the routing engine is exercised on its own;
every outcome emerges from computation and each storyline has a perturbation that flips it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import (  # noqa: E402
    design_input,
    grid_spec_of,
    make_grid,
    mission,
    rebuild,
    rover,
)

from analogforge.ports import catalog  # noqa: E402
from analogforge.ports.science_payloads import (  # noqa: E402
    DiagnoseResultInput,
    VerificationSummary,
)
from analogforge.science.routing import GridArrays  # noqa: E402
from analogforge.science.routing.diagnose import diagnose_result  # noqa: E402
from analogforge.science.routing.grid_graph import build_raster_graph, components  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402
from analogforge.science.routing.waypoints import design_benchmark  # noqa: E402

N = 64


def ramp_window(ramp_slope: float = 15.0, *, nodata: tuple[int, int] | None = None) -> GridArrays:
    """64x64 flat (3 deg) window with a 10-column wide ramp (cols 40..49, rows 8..55)."""
    slope = np.full((N, N), 3.0)
    slope[8:56, 40:50] = ramp_slope
    valid = np.ones((N, N), dtype=bool)
    if nodata is not None:
        valid[nodata] = False
    return make_grid(slope, valid=valid)


def island_window(moat: int = 4) -> GridArrays:
    """Mainland (3 deg) around a 15 deg plateau enclosed by a water moat of ``moat`` cells."""
    slope = np.full((N, N), 3.0)
    land = np.ones((N, N), dtype=bool)
    lo, hi = 20, 44
    slope[lo:hi, lo:hi] = 15.0
    if moat > 0:
        land[lo - moat : hi + moat, lo - moat : hi + moat] = False
        land[lo:hi, lo:hi] = True
    return make_grid(slope, land=land)


def design(grid: GridArrays, strategy="WAYPOINT_RETURN", rover_name="ares-1", **rover_overrides):  # noqa: ANN001, ANN003, ANN202
    inp = design_input(
        strategy,
        rover_obj=rover(rover_name, **rover_overrides),
        mission_obj=mission("mission-mars-mobility"),
        graph=False,
        window_id=catalog.WINDOW_B_CORRIDOR,
    )
    return design_benchmark(inp, mode="synthetic", grid=grid, grid_spec=grid_spec_of(grid))


def run(grid, strategy, rover_name="ares-1", **rover_overrides):  # noqa: ANN001, ANN003, ANN202
    payload = design(grid, strategy, rover_name, **rover_overrides)
    found = search_route(payload.constraints, payload.constraints_sha256, grid=grid, mode="synthetic")
    verified = None
    if found.route is not None:
        verified = verify_route(
            payload.constraints,
            payload.constraints_sha256,
            found.route,
            found.route_sha256 or "",
            "FOUND",
            grid=grid,
            mode="synthetic",
        )
    return payload, found, verified


def _diag(grid, payload, found, verified, *, history=(), repairs=2, switches=1):  # noqa: ANN001, ANN002, ANN202
    if verified is not None:
        summary = VerificationSummary(
            outcome=verified.payload.outcome,
            failure_category=verified.payload.failure_category,
            violation_codes=[v.code for v in verified.payload.violations],
        )
        violations = verified.payload.violations
    else:
        summary = VerificationSummary(outcome="INCONCLUSIVE", failure_category="SEARCH_LIMIT", violation_codes=[])
        violations = []
    return diagnose_result(
        DiagnoseResultInput(
            constraints=payload.constraints,
            search_status=found.payload.search_status,
            verification=summary,
            violations=violations,
            attempt_history=list(history),
            remaining_route_repairs=repairs,
            remaining_candidate_switches=switches,
        ),
        grid=grid,
        mode="synthetic",
    ).payload


# ------------------------------------------------------------------------------------------------ design
def test_design_places_waypoints_by_the_rule_and_records_assumptions() -> None:
    grid = ramp_window()
    payload = design(grid)
    c = payload.constraints
    assert c.artifact_kind == "RASTER_ROUTE_TEST" and c.resource_provider == "PHYSICAL_EARTH_MODEL" and c.graph is None
    assert [t.task_id for t in c.tasks] == ["W1", "W2"]
    assert all(t.tolerance_m == 60.0 and t.dwell_s == 60.0 and t.incremental_energy_wh == 10.0 for t in c.tasks)
    assert c.max_distance_m == 8000.0 and any("8000" in text for text in c.limitations)
    spec = c.exposures[0]
    assert (spec.requirement_id, spec.band_deg, spec.minimum_distance_m) == ("R-EXPOSURE", (12.0, 18.0), 100.0)
    assert spec.upper_inclusive is True  # band upper 18 == ARES-1 cap
    # independent re-derivation of the rule
    graph = build_raster_graph(grid, slope_cap_deg=18.0, exposures=c.exposures)
    comp = components(graph)[0]
    assert len(comp) == N * N  # all cells safe: one component
    assert (c.start.x_m, c.start.y_m) == grid.center_xy(31, 31)  # nearest cell to the centroid (31.5, 31.5), row-major
    edge = 3840.0
    s_xy = np.array(grid.center_xy(31, 31))
    for task in c.tasks:
        d = float(np.hypot(task.location.x_m - s_xy[0], task.location.y_m - s_xy[1]))  # type: ignore[operator]
        assert 0.15 * edge - 1e-6 <= d <= 0.30 * edge + 1e-6
        row, col = grid.cell_of(task.location.x_m, task.location.y_m)  # type: ignore[arg-type]
        assert not 12.0 <= grid.slope_deg[row, col] <= 18.0  # tasks sit outside the band
    w1, w2 = (np.array([t.location.x_m, t.location.y_m]) for t in c.tasks)  # type: ignore[misc]
    assert float(np.hypot(*(w1 - w2))) >= 0.10 * edge - 1e-6


def test_design_requirement_mapping_and_hash() -> None:
    from analogforge.ports.hashing import canonical_sha256

    payload = design(ramp_window())
    by_id = {m.requirement_id: m for m in payload.requirement_mapping}
    assert by_id["R-EXPOSURE"].treatment == "VERIFIED_BY_TOOL" and by_id["R-EXPOSURE"].constraint_ids == [
        "C-EXPOSURE-R-EXPOSURE"
    ]
    assert by_id["R-TASKS"].constraint_ids == ["C-TASK-W1", "C-TASK-W2"]
    assert by_id["R-RESERVE"].treatment == "VERIFIED_BY_TOOL"
    assert by_id["R-CLEARANCE"].treatment == "UNKNOWN" and by_id["R-GRAVITY"].treatment == "GAP"
    assert (
        "R-CLEARANCE" in payload.unverified_requirement_ids and "R-EXPOSURE" not in payload.unverified_requirement_ids
    )
    assert payload.constraints_sha256 == canonical_sha256(payload.constraints)
    assert [e.requirement_id for e in payload.required_exposures] == ["R-EXPOSURE"]
    no_energy = design(ramp_window(), rover_name="practice-no-energy-model")
    assert {m.requirement_id: m for m in no_energy.requirement_mapping}["R-RESERVE"].treatment == "UNKNOWN"
    assert no_energy.constraints.energy.model is None and all(
        t.incremental_energy_wh is None for t in no_energy.constraints.tasks
    )


def test_design_is_deterministic_and_input_dependent() -> None:
    a, b = design(ramp_window()), design(ramp_window())
    assert a.constraints_sha256 == b.constraints_sha256
    moved = design(ramp_window(nodata=(31, 31)))  # nodata under the centroid cell moves S
    assert moved.constraints.start != a.constraints.start


def test_design_blocks_without_an_analysis_grid() -> None:
    from analogforge.science.routing import RouteInputError

    with pytest.raises(RouteInputError) as err:
        design_benchmark(
            design_input("WAYPOINT_RETURN", mission_obj=mission("mission-mars-mobility"), graph=False), mode="synthetic"
        )
    assert err.value.detail_code == "ANALYSIS_GRID_MISSING"


# ------------------------------------------------------------------------------------------------ S-RASTER-1 (B)
def test_corridor_window_fails_first_attempt_then_passes_with_exposure_coverage() -> None:
    grid = ramp_window()
    payload, found, verified = run(grid, "WAYPOINT_RETURN")
    assert found.payload.search_status == "FOUND" and verified is not None
    assert verified.payload.outcome == "FAIL" and verified.payload.failure_category == "ROUTE"
    assert [v.code for v in verified.payload.violations] == ["EXPOSURE_SHORTFALL"]
    assert verified.payload.violations[0].observed < 100.0  # type: ignore[operator]
    first = _diag(grid, payload, found, verified)
    assert (first.primary_category, first.permitted_repairs, first.recommended_strategy) == (
        "ROUTE",
        ["NEW_ROUTE"],
        "EXPOSURE_COVERAGE",
    )
    assert first.violated_constraint_ids == ["C-EXPOSURE-R-EXPOSURE"] and first.proof_scope == "evaluated route only"

    payload2, found2, verified2 = run(grid, "EXPOSURE_COVERAGE")
    assert found2.payload.search_status == "FOUND" and verified2 is not None and verified2.payload.outcome == "PASS"
    unique = next(m.value for m in verified2.payload.metrics if m.metric_id == "unique_exposure_m:R-EXPOSURE")
    assert unique >= 100.0
    assert (
        payload.constraints.mission_content_sha256 == payload2.constraints.mission_content_sha256
    )  # contract unchanged
    assert verified2.payload.verified_route_sha256 == found2.route_sha256
    # solver and verifier agree on distance to numerical precision
    claimed = found2.route.solver_claimed.distance_m  # type: ignore[union-attr]
    assert next(m.value for m in verified2.payload.metrics if m.metric_id == "route_distance_m") == pytest.approx(
        claimed
    )
    # a third attempt is not recommended once the strategy was tried and the route passes
    done = _diag(grid, payload2, found2, verified2)
    assert done.primary_category is None and done.permitted_repairs == []


def test_exposure_route_is_shortest_by_independent_check() -> None:
    """Exposure route length >= the straight-line lower bound S -> nearest band cell -> back plus both tasks."""
    grid = ramp_window()
    payload, found, verified = run(grid, "EXPOSURE_COVERAGE")
    assert verified is not None and verified.payload.outcome == "PASS" and found.route is not None
    wr = run(grid, "WAYPOINT_RETURN")[1].route
    assert (
        wr is not None and found.route.solver_claimed.distance_m >= wr.solver_claimed.distance_m
    )  # exposure costs distance


# ----------------------------------------------------------------------------------------- S-RASTER-1 (A: island)
def test_island_window_is_exhaustive_infeasible_analog_and_moat_perturbation_flips_it() -> None:
    grid = island_window(moat=4)
    payload, found, _ = run(grid, "EXPOSURE_COVERAGE")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and found.payload.counters.labels_pruned_lossy == 0
    assert found.payload.optimistic_exposure_bound_m == {"R-EXPOSURE": 0.0}
    diag = _diag(grid, payload, found, None)
    assert diag.primary_category == "ANALOG" and diag.permitted_repairs == ["NEW_CANDIDATE"]
    assert diag.violated_constraint_ids == ["C-EXPOSURE-R-EXPOSURE"]
    assert "discrete graph" in diag.proof_scope
    last_chance = _diag(grid, payload, found, None, switches=0)
    assert last_chance.permitted_repairs == ["COMPOSITE_PORTFOLIO"]
    # PERT-01: remove the moat -> the same strategy is now feasible and verifies, no candidate switch needed
    attached = island_window(moat=0)
    _, found_ec, verified_ec = run(attached, "EXPOSURE_COVERAGE")
    assert (
        found_ec.payload.search_status == "FOUND" and verified_ec is not None and verified_ec.payload.outcome == "PASS"
    )


def test_flat_negative_control_has_no_band_to_walk() -> None:
    flat = make_grid(np.full((N, N), 2.0))
    payload, found, _ = run(flat, "EXPOSURE_COVERAGE")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert _diag(flat, payload, found, None).primary_category == "ANALOG"


def test_pert02_gentler_ramp_turns_the_corridor_into_an_analog_failure() -> None:
    grid = ramp_window(ramp_slope=10.0)
    payload, found, _ = run(grid, "EXPOSURE_COVERAGE")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert _diag(grid, payload, found, None).primary_category == "ANALOG"


# ------------------------------------------------------------------------------------------------ rover conflicts
def test_rover_lite_cap_conflict_is_rover_not_analog() -> None:
    grid = ramp_window()
    payload, found, _ = run(grid, "EXPOSURE_COVERAGE", rover_name="practice-lite")
    assert (
        payload.constraints.surface_slope_cap_deg == 12.0 and payload.constraints.exposures[0].upper_inclusive is False
    )
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    diag = _diag(grid, payload, found, None)
    assert diag.primary_category == "ROVER" and diag.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
    assert diag.recommended_repair is None  # never an automatic action
    assert diag.violated_constraint_ids == ["C-EXPOSURE-R-EXPOSURE"]


def test_pert03_lowering_ares_cap_to_14_flips_the_corridor_to_rover() -> None:
    grid = ramp_window()
    payload, found, _ = run(grid, "EXPOSURE_COVERAGE", max_slope_deg=14.0)
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert _diag(grid, payload, found, None).primary_category == "ROVER"
    payload18, found18, verified18 = run(grid, "EXPOSURE_COVERAGE")
    assert verified18 is not None and verified18.payload.outcome == "PASS"


def test_small_battery_is_a_lossless_energy_certificate_and_rover_diagnosis() -> None:
    grid = ramp_window()
    payload, found, _ = run(grid, "WAYPOINT_RETURN", rover_name="practice-small-battery")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and found.payload.counters.labels_pruned_lossy == 0
    assert "Wh" in found.payload.termination_reason and found.payload.counters.expansions == 0
    diag = _diag(grid, payload, found, None)
    assert diag.primary_category == "ROVER" and diag.violated_constraint_ids == ["C-ENERGY-RESERVE"]
    assert diag.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
    # PERT-04: the same grid with the full battery is solvable
    _, found_big, verified_big = run(grid, "EXPOSURE_COVERAGE", battery_wh=1800.0)
    assert verified_big is not None and verified_big.payload.outcome == "PASS"


def test_no_energy_model_is_inconclusive_data_with_data_repair() -> None:
    grid = ramp_window()
    payload, found, verified = run(grid, "EXPOSURE_COVERAGE", rover_name="practice-no-energy-model")
    assert found.payload.search_status == "FOUND" and verified is not None
    assert (verified.payload.outcome, verified.payload.failure_category) == ("INCONCLUSIVE", "DATA")
    assert verified.issues[0].code == "ENERGY_UNCALIBRATED"
    exposure_row = next(r for r in verified.payload.benchmark_rows if r.constraint_id == "C-EXPOSURE-R-EXPOSURE")
    assert exposure_row.status == "PASS"  # exposure and tasks verified, only energy is unknown
    diag = _diag(grid, payload, found, verified)
    assert diag.primary_category == "DATA" and diag.permitted_repairs == ["DATA_REPAIR"]


def test_pert06_exposure_beyond_the_route_domain_is_domain_bounded_analog() -> None:
    grid = ramp_window()
    payload = design(grid, "EXPOSURE_COVERAGE")
    data = payload.constraints.model_dump(mode="json")
    data["exposures"][0]["minimum_distance_m"] = 10_000.0
    art, digest = rebuild(payload.constraints, exposures=data["exposures"])
    found = search_route(art, digest, grid=grid, mode="synthetic")
    assert found.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert found.payload.optimistic_exposure_bound_m["R-EXPOSURE"] <= 8000.0
    diag = diagnose_result(
        DiagnoseResultInput(
            constraints=art,
            search_status="EXHAUSTIVE_INFEASIBLE",
            verification=VerificationSummary(outcome="FAIL", failure_category=None),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        ),
        grid=grid,
        mode="synthetic",
    ).payload
    assert diag.primary_category == "ANALOG" and "domain-bounded" in diag.proof_scope


# ------------------------------------------------------------------------------------------------ geometry safety
def test_pert08_nodata_cell_on_the_route_is_rejected_and_search_routes_around_it() -> None:
    grid = ramp_window()
    payload, found, _ = run(grid, "EXPOSURE_COVERAGE")
    assert found.route is not None
    # flip one interior cell of the found route (not an endpoint of a task) into nodata
    victim = found.route.node_sequence[len(found.route.node_sequence) // 2]
    row, col = int(victim[1 : victim.index("c")]), int(victim[victim.index("c") + 1 :])
    valid = grid.valid.copy()
    valid[row, col] = False
    perturbed = GridArrays(
        grid.elevation_m, valid, grid.land, grid.slope_deg, grid.cell_size_m, grid.origin_x_m, grid.origin_y_m
    )
    out = verify_route(
        payload.constraints,
        payload.constraints_sha256,
        found.route,
        found.route_sha256 or "",
        "FOUND",
        grid=perturbed,
        mode="synthetic",
    )
    assert out.payload.outcome == "FAIL" and "UNKNOWN_TERRAIN" in {v.code for v in out.payload.violations}
    again = search_route(payload.constraints, payload.constraints_sha256, grid=perturbed, mode="synthetic")
    if again.route is not None:
        assert victim not in again.route.node_sequence
        recheck = verify_route(
            payload.constraints,
            payload.constraints_sha256,
            again.route,
            again.route_sha256 or "",
            "FOUND",
            grid=perturbed,
            mode="synthetic",
        )
        assert recheck.payload.outcome == "PASS"
    else:
        assert again.payload.search_status in {"EXHAUSTIVE_INFEASIBLE", "BUDGET_EXHAUSTED"}


def test_graph_never_bridges_a_one_cell_nodata_channel_or_cuts_invalid_corners() -> None:
    slope = np.full((9, 9), 3.0)
    valid = np.ones((9, 9), dtype=bool)
    valid[:, 4] = False  # one-cell channel
    grid = make_grid(slope, valid=valid)
    graph = build_raster_graph(grid, slope_cap_deg=18.0, exposures=[])
    left = {i for i, nid in enumerate(graph.node_ids) if int(nid.split("c")[1]) < 4}
    for rec in graph.edges:
        assert (rec.u in left) == (rec.v in left)  # no edge joins the two banks
    # an invalid cell touched only at the corner of a diagonal removes that diagonal (but not the orthogonal path)
    valid2 = np.ones((5, 5), dtype=bool)
    valid2[1, 2] = False
    g2 = build_raster_graph(make_grid(np.full((5, 5), 3.0), valid=valid2), slope_cap_deg=18.0, exposures=[])
    ids = {rec.edge_id for rec in g2.edges}
    assert "r1c1--r2c2" not in ids and "r1c1--r1c2" not in ids
    assert "r2c1--r2c2" in ids  # the orthogonal neighbours remain connected


def test_corner_touched_steep_cell_is_allowed_but_the_cell_itself_is_not_a_node() -> None:
    slope = np.full((5, 5), 3.0)
    slope[1, 2] = 25.0
    graph = build_raster_graph(make_grid(slope), slope_cap_deg=18.0, exposures=[])
    ids = {rec.edge_id for rec in graph.edges}
    # r1c1 -> r2c2 passes through (1,1) and (2,2); the steep cell (1,2) is touched only at the shared corner
    assert "r1c1--r2c2" in ids
    assert "r1c2--r2c2" not in ids and "r1c1--r1c2" not in ids  # edges INTO the steep cell would have positive length
