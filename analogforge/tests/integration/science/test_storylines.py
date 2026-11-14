# ruff: noqa: E501, E402, S603, S607, S101
"""SCN-09: PROVE IT storylines at science level, driven only through ``facade.execute``."""

from __future__ import annotations

from pathlib import Path

from support.builders import load_mission, load_rover, make_context
from support.graph_flow import attempt, attempt_summary

from analogforge.ports import catalog
from analogforge.ports.science_payloads import CandidateRef, DesignBenchmarkInput
from analogforge.science.facade import create_science_service


def _graph_candidate() -> CandidateRef:
    mission = load_mission("mission-graph-regression")
    return CandidateRef(
        window_id=catalog.GRAPH_WINDOW_ID, name="Graph zone 1",
        aoi=mission.target.model_copy(update={"body": "EARTH"}),
        origin="SYNTHETIC_CONTROL", novelty_status="NOT_ASSESSED", discovery_method="canonical graph",
    )  # fmt: skip


def _graph_design(strategy: str, rev: int, **kw: object) -> DesignBenchmarkInput:
    return DesignBenchmarkInput(
        mission=load_mission("mission-graph-regression"), rover=load_rover("ares-1"),
        candidate=_graph_candidate(), analysis_evidence_id=None,
        graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH, strategy=strategy, test_revision=rev, **kw,
    )  # type: ignore[arg-type]  # fmt: skip


def test_s_graph_1(tmp_path: Path) -> None:
    svc = create_science_service()
    ctx = make_context(tmp_path)
    a1 = attempt(svc, ctx, _graph_design("WAYPOINT_RETURN", 1))
    exp1 = catalog.GRAPH_EXPECTED["search_waypoint_return"]
    assert a1.search.search_status == "FOUND"
    assert tuple(a1.search.route.node_sequence) == catalog.GRAPH_SEARCH_WAYPOINT_RETURN  # type: ignore[union-attr]
    assert a1.verify is not None and a1.verify.outcome == "FAIL" and a1.verify.failure_category == "ROUTE"
    assert {v.code for v in a1.verify.violations} == {"EXPOSURE_SHORTFALL"}
    metrics = {m.metric_id: m.value for m in a1.verify.metrics}
    assert metrics["route_distance_m"] == exp1["distance_m"]
    assert a1.diagnosis is not None
    assert a1.diagnosis.recommended_repair == "NEW_ROUTE" and a1.diagnosis.recommended_strategy == "EXPOSURE_COVERAGE"

    a2 = attempt(svc, ctx, _graph_design("EXPOSURE_COVERAGE", 2), history=[attempt_summary(1, _graph_candidate(), a1)])
    exp2 = catalog.GRAPH_EXPECTED["search_exposure_coverage"]
    assert tuple(a2.search.route.node_sequence) == catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE  # type: ignore[union-attr]
    assert a2.verify is not None and a2.verify.outcome == "PASS" and a2.verify.violations == []
    m2 = {m.metric_id: m.value for m in a2.verify.metrics}
    assert m2["route_distance_m"] == exp2["distance_m"]
    assert abs(m2["reserve_pct"] - exp2["reserve_pct"]) < 1e-9  # type: ignore[operator]
    # evidence ids per 08 section 4 / architecture 35 5b
    ids = {d.algorithm_id for d in a2.results["verify"].evidence_drafts}
    # ASSUMED mock graph energies are cited through the accepted-assumption record (its own sub-algorithm id).
    assert ids == {"verify-route", "route-telemetry", "accepted-energy-assumption"}
    assert a2.results["verify"].artifacts[1].role.value == "TELEMETRY"


# --------------------------------------------------------------------------- raster storylines (practice windows)
import pytest  # noqa: E402
from support.builders import load_rover as _rover  # noqa: E402
from support.practice import Flow, characterize_mars, make_practice_context, prove, screen, service  # noqa: E402

A_, B_ = catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR


@pytest.fixture(scope="module")
def practice(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    ctx = make_practice_context(tmp_path_factory.mktemp("story"))
    flow = Flow(service(), ctx)
    target, _ = characterize_mars(flow)
    return flow, screen(flow, target)


def test_s_raster_1_three_attempts(practice) -> None:  # type: ignore[no-untyped-def]
    flow, sc = practice
    ares = _rover("ares-1")
    a1, cand_a = prove(flow, sc, A_, ares, "WAYPOINT_RETURN", 1)
    assert a1.search.search_status == "FOUND"
    assert a1.verify.outcome == "FAIL" and a1.verify.failure_category == "ROUTE"
    v = [x for x in a1.verify.violations if x.code == "EXPOSURE_SHORTFALL"]
    assert (
        len(v) == 1
        and v[0].constraint_id == "C-EXPOSURE-R-EXPOSURE"
        and v[0].observed == 0.0
        and v[0].threshold == 100.0
    )
    assert (a1.diagnosis.recommended_repair, a1.diagnosis.recommended_strategy) == ("NEW_ROUTE", "EXPOSURE_COVERAGE")

    a2, _ = prove(flow, sc, A_, ares, "EXPOSURE_COVERAGE", 2, history=[attempt_summary(1, cand_a, a1)])
    assert a2.search.search_status == "EXHAUSTIVE_INFEASIBLE" and a2.search.counters.labels_pruned_lossy == 0
    assert a2.search.termination_reason.startswith("CERTIFICATE")
    assert a2.search.route is None and a2.verify is None
    assert a2.diagnosis.primary_category == "ANALOG" and a2.diagnosis.recommended_repair == "NEW_CANDIDATE"

    a3, _ = prove(flow, sc, B_, ares, "EXPOSURE_COVERAGE", 3)
    assert a3.search.search_status == "FOUND"
    assert a3.verify.outcome == "PASS" and a3.verify.violations == [] and a3.verify.verified_route_sha256
    unique = next(m.value for m in a3.verify.metrics if m.metric_id.startswith("unique_exposure_m"))
    assert unique >= 100.0
    reserve = next(m.value for m in a3.verify.metrics if m.metric_id == "reserve_pct")
    assert reserve >= 20.0
    assert next(m.value for m in a3.verify.metrics if m.metric_id == "tasks_completed") == 2
    # contract and rover hashes are identical in all three attempts
    assert {a.constraints.mission_content_sha256 for a in (a1, a2, a3)} == {a1.constraints.mission_content_sha256}
    assert {a.constraints.rover_content_sha256 for a in (a1, a2, a3)} == {a1.constraints.rover_content_sha256}


def test_s_rover_lite(practice) -> None:  # type: ignore[no-untyped-def]
    flow, sc = practice
    lite = _rover("practice-lite")
    a1, cand = prove(flow, sc, B_, lite, "WAYPOINT_RETURN", 1)
    assert a1.search.search_status == "FOUND" and a1.verify.outcome == "FAIL"
    assert [v.code for v in a1.verify.violations] == ["EXPOSURE_SHORTFALL"] and a1.verify.failure_category == "ROUTE"
    a2, _ = prove(flow, sc, B_, lite, "EXPOSURE_COVERAGE", 2, history=[attempt_summary(1, cand, a1)])
    assert a2.search.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert a2.diagnosis.primary_category == "ROVER" and a2.diagnosis.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
    assert a2.diagnosis.recommended_repair is None
    assert a2.constraints.surface_slope_cap_deg == 12.0  # the contract is not relaxed


def test_s_no_energy(practice) -> None:  # type: ignore[no-untyped-def]
    flow, sc = practice
    r = _rover("practice-no-energy-model")
    a1, cand = prove(flow, sc, B_, r, "WAYPOINT_RETURN", 1)
    assert a1.verify.outcome == "FAIL"
    a2, _ = prove(flow, sc, B_, r, "EXPOSURE_COVERAGE", 2, history=[attempt_summary(1, cand, a1)])
    assert a2.search.search_status == "FOUND"
    assert (a2.verify.outcome, a2.verify.failure_category) == ("INCONCLUSIVE", "DATA")
    assert any(i.code == "ENERGY_UNCALIBRATED" for i in a2.results["verify"].issues)
    assert a2.results["verify"].status.value == "LIMITED"
    assert next(m for m in a2.verify.metrics if m.metric_id == "reserve_pct").value is None  # unknown, never 0
    assert a2.diagnosis.permitted_repairs == ["DATA_REPAIR"] and a2.diagnosis.primary_category == "DATA"
    exposure = next(m.value for m in a2.verify.metrics if m.metric_id.startswith("unique_exposure_m"))
    assert exposure >= 100.0


def test_s_small_battery(practice) -> None:  # type: ignore[no-untyped-def]
    flow, sc = practice
    r = _rover("practice-small-battery")
    a1, _ = prove(flow, sc, B_, r, "WAYPOINT_RETURN", 1)
    assert a1.search.search_status == "EXHAUSTIVE_INFEASIBLE" and a1.search.counters.labels_pruned_lossy == 0
    assert "Wh" in a1.search.termination_reason
    assert a1.diagnosis.primary_category == "ROVER" and a1.diagnosis.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
    assert "C-ENERGY-RESERVE" in a1.diagnosis.violated_constraint_ids
    assert a1.constraints.energy.battery_wh == 30.0


def test_equal_cost_routes_break_ties_lexicographically(tmp_path: Path) -> None:
    """Two symmetric alternatives (via A or via Z) cost the same: the smallest node_sequence wins (architecture 35 s9)."""
    from support.graph_flow import summary_of  # noqa: F401

    from analogforge.ports.science_payloads import GraphEdge, SearchRoutePayload

    svc = create_science_service()
    ctx = make_context(tmp_path)
    base = attempt(svc, ctx, _graph_design("WAYPOINT_RETURN", 1))
    graph = base.constraints.graph
    assert graph is not None
    twins = [e for e in graph.edges if {e.a, e.b} in ({"S", "A"}, {"A", "W1"})]
    z_edges = [
        GraphEdge(
            a=("Z" if e.a == "A" else e.a),
            b=("Z" if e.b == "A" else e.b),
            length_m=e.length_m,
            surface_slope_deg=e.surface_slope_deg,
            mock_energy_wh=e.mock_energy_wh,
        )
        for e in twins
    ]
    widened = base.constraints.model_copy(
        update={"graph": graph.model_copy(update={"nodes": [*graph.nodes, "Z"], "edges": [*graph.edges, *z_edges]})}
    )
    res, _ = run_search(svc, ctx, widened)
    assert isinstance(res.payload, SearchRoutePayload) and res.payload.route is not None
    assert tuple(res.payload.route.node_sequence) == catalog.GRAPH_SEARCH_WAYPOINT_RETURN  # via A, never Z
    assert res.payload.route.solver_claimed.distance_m == 120.0


def run_search(svc, ctx, constraints):  # type: ignore[no-untyped-def]
    from support.builders import run

    from analogforge.ports.hashing import canonical_sha256
    from analogforge.ports.science_payloads import SearchRouteInput

    return run(svc, SearchRouteInput(constraints=constraints, constraints_sha256=canonical_sha256(constraints)), ctx)


def _verification_handle(analysis):  # type: ignore[no-untyped-def]
    """The platform registers the verifier's evidence as a VERIFICATION-kind handle next to the analysis evidence."""
    return analysis.model_copy(
        update={"evidence_id": __import__("uuid").uuid4(), "kind": "VERIFICATION", "algorithm_id": "verify-route"}
    )


def test_s_no_energy_rows_exposure_tasks_credited_reserve_unknown(practice) -> None:  # type: ignore[no-untyped-def]
    """Arch 40 section 6 S-NO-ENERGY: only the energy is unevaluable, so the verified rows keep their verdict."""
    from support.builders import load_mission, requirement
    from support.graph_flow import summary_of
    from support.practice import analyze, candidate_ref, compare

    from analogforge.ports.science_payloads import CompareRequirementPayload, VerificationSummary

    flow, sc = practice
    r = _rover("practice-no-energy-model")
    a1, cand = prove(flow, sc, B_, r, "WAYPOINT_RETURN", 1)
    a2, _ = prove(flow, sc, B_, r, "EXPOSURE_COVERAGE", 2, history=[attempt_summary(1, cand, a1)])
    assert (a2.verify.outcome, a2.verify.failure_category) == ("INCONCLUSIVE", "DATA")
    cand = candidate_ref(sc, B_)
    _, handles = analyze(flow, cand)
    evidence = [handles[0], _verification_handle(handles[0])]
    mission = load_mission("mission-mars-mobility")
    _, target_handle = None, flow.handles["CHARACTERIZE_TARGET:profile"]

    def row(rid: str, verification: VerificationSummary):  # type: ignore[no-untyped-def]
        res = compare(flow, requirement(mission, rid), cand, [target_handle], evidence, verification)
        assert isinstance(res.payload, CompareRequirementPayload), res.issues
        return res.payload

    energy_only = summary_of(a2.verify)
    assert [m.value for m in energy_only.metrics if m.metric_id == "reserve_pct"] == [None]
    for rid in ("R-EXPOSURE", "R-TASKS"):
        p = row(rid, energy_only)
        assert (p.proposed_status, p.reason_code, p.evaluation_stage) == ("PASS", "ROUTE_VERIFIED", "FINAL"), rid
    p = row("R-RESERVE", energy_only)
    assert (p.proposed_status, p.reason_code, p.measured_value) == ("UNKNOWN", "ENERGY_MODEL_MISSING", None)

    # a DATA-inconclusive with another cause (a violation, or no energy finding at all) earns no credit
    for other in (
        energy_only.model_copy(update={"violation_codes": ["UNKNOWN_TERRAIN"]}),
        energy_only.model_copy(update={"metrics": [m for m in energy_only.metrics if m.metric_id != "reserve_pct"]}),
        energy_only.model_copy(update={"failure_category": "SYSTEM"}),
        energy_only.model_copy(update={"failure_category": "SEARCH_LIMIT"}),
    ):
        for rid in ("R-EXPOSURE", "R-TASKS"):
            p = row(rid, other)
            assert (p.proposed_status, p.reason_code) == ("UNKNOWN", "ROUTE_NOT_VERIFIED"), (
                rid,
                other.failure_category,
            )
