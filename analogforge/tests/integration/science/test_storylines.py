# ruff: noqa: E501, S603, S607, S101
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
    assert ids == {"verify-route", "route-telemetry"}
    assert a2.results["verify"].artifacts[1].role.value == "TELEMETRY"
