# ruff: noqa: E501
"""SCN-10: PERT-01..PERT-09. Each perturbation regenerates the data / changes an input and the computed outcome flips."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import yaml
from support.builders import load_mission, load_rover, make_context, requirement
from support.graph_flow import attempt, attempt_summary
from support.practice import (
    Flow,
    analyze,
    candidate_ref,
    characterize_mars,
    compare,
    make_practice_context,
    prove,
    screen,
    service,
)

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    CandidateRef,
    CompareRequirementPayload,
    DesignBenchmarkInput,
    SearchRouteInput,
    SearchRoutePayload,
    VerifyRouteInput,
    VerifyRoutePayload,
)

A, B = catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR


def setup(tmp: Path, **gen: Any) -> tuple[Flow, Any, Any, Any]:
    ctx = make_practice_context(tmp, **gen)
    flow = Flow(service(), ctx)
    target, th = characterize_mars(flow)
    return flow, target, th, screen(flow, target)


def test_pert_01_no_moat_makes_window_a_testable(tmp_path: Path) -> None:
    flow, _, _, sc = setup(tmp_path, moat_cells=0)
    ares = load_rover("ares-1")
    a1, cand = prove(flow, sc, A, ares, "WAYPOINT_RETURN", 1)
    assert a1.verify.outcome == "FAIL" and [v.code for v in a1.verify.violations] == ["EXPOSURE_SHORTFALL"]
    a2, _ = prove(flow, sc, A, ares, "EXPOSURE_COVERAGE", 2, history=[attempt_summary(1, cand, a1)])
    assert a2.search.search_status == "FOUND" and a2.verify.outcome == "PASS"  # no candidate switch needed
    assert a2.diagnosis is None


def test_pert_02_gentler_ramp_fails_availability_and_is_analog(tmp_path: Path) -> None:
    flow, target, th, sc = setup(tmp_path, ramp_slope_deg=10.0)
    cand = candidate_ref(sc, B)
    _, handles = analyze(flow, cand)
    mission = load_mission("mission-mars-mobility")
    row = compare(flow, requirement(mission, "R-SLOPE-AVAILABILITY"), cand, [th], handles).payload
    assert isinstance(row, CompareRequirementPayload)
    assert (row.proposed_status, row.reason_code) == ("FAIL", "INSUFFICIENT_EXPOSURE")
    att, _ = prove(flow, sc, B, load_rover("ares-1"), "EXPOSURE_COVERAGE", 1)
    assert att.search.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert att.diagnosis.primary_category == "ANALOG"


def test_pert_03_lower_rover_slope_limit_makes_it_a_rover_problem(tmp_path: Path) -> None:
    flow, _, _, sc = setup(tmp_path)
    att, _ = prove(flow, sc, B, load_rover("ares-1", max_slope_deg=14.0), "EXPOSURE_COVERAGE", 1)
    assert att.search.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert att.diagnosis.primary_category == "ROVER" and att.diagnosis.permitted_repairs == ["NEW_CONTRACT_REQUIRED"]
    base, _ = prove(flow, sc, B, load_rover("ares-1"), "EXPOSURE_COVERAGE", 2)
    assert base.verify.outcome == "PASS"


def test_pert_04_battery_30_vs_1800(tmp_path: Path) -> None:
    flow, _, _, sc = setup(tmp_path)
    small, _ = prove(flow, sc, B, load_rover("ares-1", battery_wh=30.0), "EXPOSURE_COVERAGE", 1)
    assert small.search.search_status == "EXHAUSTIVE_INFEASIBLE" and small.diagnosis.primary_category == "ROVER"
    full, _ = prove(flow, sc, B, load_rover("ares-1", battery_wh=1800.0), "EXPOSURE_COVERAGE", 2)
    assert full.verify.outcome == "PASS"


def test_pert_05_shifted_target_histogram_flips_the_context_row(tmp_path: Path) -> None:
    mission = load_mission("mission-mars-mobility")
    req = requirement(mission, "R-TARGET-SLOPE-CONTEXT")
    rows: dict[str, dict[str, str]] = {}
    for label, gen in (("base", {}), ("shifted", {"target_fractions": ((22.0, 1.0),)})):
        flow, _, th, sc = setup(tmp_path / label, **gen)
        for w in (A, B):
            cand = candidate_ref(sc, w)
            _, handles = analyze(flow, cand)
            payload = compare(flow, req, cand, [th], handles).payload
            assert isinstance(payload, CompareRequirementPayload)
            rows.setdefault(label, {})[w] = payload.proposed_status
    assert rows["base"] == {A: "PASS", B: "PASS"}
    assert rows["shifted"] == {A: "FAIL", B: "FAIL"}


def test_pert_06_exposure_requirement_beyond_route_domain(tmp_path: Path) -> None:
    flow, _, _, sc = setup(tmp_path)
    mission = load_mission("mission-mars-mobility", {"R-EXPOSURE": {"lower": 10000}})
    att, _ = prove(flow, sc, B, load_rover("ares-1"), "EXPOSURE_COVERAGE", 1, mission=mission)
    assert att.search.search_status == "EXHAUSTIVE_INFEASIBLE" and att.verify is None
    assert att.diagnosis.primary_category == "ANALOG" and "domain-bounded" in att.diagnosis.proof_scope
    assert att.search.counters.labels_pruned_lossy == 0


def test_pert_07_removing_the_mineral_binding_changes_the_reason(tmp_path: Path) -> None:
    flow, _, th, sc = setup(tmp_path)
    mission = load_mission("mission-mars-mobility")
    req = requirement(mission, "R-MINERAL")
    cand = candidate_ref(sc, B)
    reasons = {}
    for label, datasets in (("bound", ["practice-earth-grid-v1", "practice-earth-minerals-v1"]), ("unbound", None)):
        _, handles = analyze(flow, cand, datasets)
        payload = compare(flow, req, cand, [th], handles).payload
        assert isinstance(payload, CompareRequirementPayload)
        reasons[label] = (payload.proposed_status, payload.reason_code)
    assert reasons == {
        "bound": ("UNKNOWN", "TARGET_EVIDENCE_MISSING"),
        "unbound": ("UNKNOWN", "EARTH_EVIDENCE_MISSING"),
    }


def test_pert_08_one_nodata_cell_on_the_route(tmp_path: Path) -> None:
    flow, _, _, sc = setup(tmp_path)
    ares = load_rover("ares-1")
    base, cand = prove(flow, sc, B, ares, "EXPOSURE_COVERAGE", 1)
    route = base.search.route
    assert route is not None and base.verify.outcome == "PASS"
    interior = [n for n in route.node_sequence[2:-2] if n not in {t.location.node_id for t in base.constraints.tasks}]
    victim = interior[len(interior) // 2]
    r, c = int(victim[1 : victim.index("c")]), int(victim[victim.index("c") + 1 :])
    # corrupt that single cell in a regenerated copy of the dataset
    root = tmp_path / "data" / "practice-earth-grid-v1"
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    tif = root / manifest["primary_file"]
    with rasterio.open(tif, "r+") as ds:
        arr = ds.read(1)
        arr[r, c] = ds.nodata
        ds.write(arr, 1)
    for f in manifest["files"]:
        f.pop("sha256", None)
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    flow2 = Flow(service(), flow.ctx)
    sc2 = sc
    # (a) the OLD route replayed against constraints built on the corrupted grid is rejected by the verifier
    cand2 = candidate_ref(sc2, B)
    _, handles = analyze(flow2, cand2)
    design = DesignBenchmarkInput(mission=load_mission("mission-mars-mobility"), rover=ares, candidate=cand2, analysis_evidence_id=handles[0].evidence_id, strategy="EXPOSURE_COVERAGE", test_revision=2)
    att2 = attempt(flow2.svc, flow2.ctx, design, evidence=[handles[0]], datasets=["practice-earth-grid-v1"])
    forged_route = route.model_copy(update={"constraints_sha256": att2.constraints_sha})
    res, _ = flow2.call(
        VerifyRouteInput(constraints=att2.constraints, constraints_sha256=att2.constraints_sha, route=forged_route, route_sha256=canonical_sha256(forged_route), search_status="NOT_RUN"),
        evidence=[handles[0]], datasets=["practice-earth-grid-v1"],
    )  # fmt: skip
    assert isinstance(res.payload, VerifyRoutePayload)
    assert res.payload.outcome == "FAIL"
    assert {v.code for v in res.payload.violations} & {"UNKNOWN_TERRAIN", "FORBIDDEN_INTERSECTION"}
    # (b) a fresh search never uses the corrupted cell and returns a different legal route (or none)
    if att2.search.route is not None:
        assert victim not in att2.search.route.node_sequence
        assert att2.search.route.node_sequence != route.node_sequence
        assert att2.verify is not None and att2.verify.outcome in ("PASS", "FAIL")
    else:
        assert att2.search.search_status in ("EXHAUSTIVE_INFEASIBLE", "BUDGET_EXHAUSTED")


def test_pert_09_longer_graph_edge_changes_the_search_result(tmp_path: Path) -> None:
    svc = service()
    ctx = make_context(tmp_path)
    mission = load_mission("mission-graph-regression")
    cand = CandidateRef(window_id=catalog.GRAPH_WINDOW_ID, name="g", aoi=mission.target.model_copy(update={"body": "EARTH"}), origin="SYNTHETIC_CONTROL", novelty_status="NOT_ASSESSED", discovery_method="canonical graph")
    inp = DesignBenchmarkInput(mission=mission, rover=load_rover("ares-1"), candidate=cand, analysis_evidence_id=None, graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH, strategy="EXPOSURE_COVERAGE", test_revision=1)
    base = attempt(svc, ctx, inp)
    assert tuple(base.search.route.node_sequence) == catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE  # type: ignore[union-attr]
    graph = base.constraints.graph
    assert graph is not None
    edges = [e.model_copy(update={"length_m": 500.0}) if {e.a, e.b} == {"S", "B"} else e for e in graph.edges]
    changed = base.constraints.model_copy(update={"graph": graph.model_copy(update={"edges": edges})})
    sha = canonical_sha256(changed)
    res, _ = Flow(svc, ctx).call(SearchRouteInput(constraints=changed, constraints_sha256=sha))
    out = res.payload
    assert isinstance(out, SearchRoutePayload)
    same = out.search_status == "FOUND" and out.route is not None and out.route.node_sequence == base.search.route.node_sequence  # type: ignore[union-attr]
    assert not same
    if out.route is not None:
        assert out.route.solver_claimed.distance_m != 230.0
    else:
        assert out.search_status in ("EXHAUSTIVE_INFEASIBLE", "BUDGET_EXHAUSTED")
    assert np.isfinite(out.counters.expansions)
