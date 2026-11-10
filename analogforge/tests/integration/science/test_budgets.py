# ruff: noqa: E501
"""Performance budgets of guide 05 section 4 (offline), plus facade coverage of ingest/portfolio/display/audit."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml
from support.builders import load_mission, load_rover, requirement
from support.practice import (
    ALL,
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
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.science_payloads import (
    AuditEvidenceInput,
    AuditEvidencePayload,
    BuildDisplayLayersInput,
    BuildDisplayLayersPayload,
    ClaimScope,
    IngestLocalDatasetInput,
    IngestLocalDatasetPayload,
    OptimizePortfolioInput,
    OptimizePortfolioPayload,
    QualificationRowInput,
)

B = catalog.WINDOW_B_CORRIDOR


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    ctx = make_practice_context(tmp_path_factory.mktemp("budget"))
    return Flow(service(), ctx), tmp_path_factory


def test_ingest_each_practice_dataset_within_budget(world) -> None:  # type: ignore[no-untyped-def]
    flow, _ = world
    for ds in ALL:
        root = flow.ctx.dataset_roots[ds]
        manifest = DatasetManifest.model_validate(yaml.safe_load((root / "manifest.yaml").read_text()))
        res, reg = flow.call(IngestLocalDatasetInput(manifest=manifest), name=f"ingest:{ds}", datasets=[ds])
        assert isinstance(res.payload, IngestLocalDatasetPayload) and res.payload.usable_for_quantitative_claims, ds
        assert reg is not None and flow.elapsed[f"ingest:{ds}"] <= 5.0
        assert res.evidence_drafts[0].kind == "SOURCE" and res.artifacts == []


def test_ingest_failed_checks_are_a_successful_computation(world, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    flow, _ = world
    root = flow.ctx.dataset_roots["practice-earth-grid-v1"]
    manifest = DatasetManifest.model_validate(yaml.safe_load((root / "manifest.yaml").read_text()))
    bad = manifest.model_copy(update={"units": "km"})  # wrong units for a metre raster
    res, _ = flow.call(IngestLocalDatasetInput(manifest=bad), datasets=["practice-earth-grid-v1"], check_registrar=False)
    assert res.status.value == "SUCCEEDED" and isinstance(res.payload, IngestLocalDatasetPayload)
    assert any(c.status == "FAIL" for c in res.payload.checks)
    missing = IngestLocalDatasetInput(manifest=manifest.model_copy(update={"dataset_id": "no-such-dataset"}))
    blocked, _ = flow.call(missing, check_registrar=False)
    assert blocked.status.value == "BLOCKED" and blocked.payload is None


def test_core_operations_within_budget(world) -> None:  # type: ignore[no-untyped-def]
    flow, _ = world
    target, th = characterize_mars(flow)
    sc = screen(flow, target)
    cand = candidate_ref(sc, B)
    _, handles = analyze(flow, cand)
    mission = load_mission("mission-mars-mobility")
    compare(flow, requirement(mission, "R-TARGET-SLOPE-CONTEXT"), cand, [th], handles)
    att, _ = prove(flow, sc, B, load_rover("ares-1"), "EXPOSURE_COVERAGE", 1)
    assert att.verify.outcome == "PASS"
    e = flow.elapsed
    assert e["CHARACTERIZE_TARGET"] <= 5.0
    assert e["SCREEN_CANDIDATES"] <= 20.0
    assert e[f"analyze:{B}"] <= 5.0
    assert e["COMPARE_REQUIREMENT"] <= 1.0
    assert att.elapsed["design"] <= 2.0
    assert att.elapsed["search"] <= 10.0
    assert att.elapsed["verify"] <= 3.0


def test_portfolio_display_and_audit_through_the_facade(world) -> None:  # type: ignore[no-untyped-def]
    flow, _ = world
    target, th = characterize_mars(flow)
    sc = screen(flow, target)
    mission = load_mission("mission-mars-mobility")
    cand = candidate_ref(sc, B)
    _, handles = analyze(flow, cand)

    rows = [QualificationRowInput(candidate_window_id=B, requirement_id=r.id, status="PASS" if r.id == "R-SLOPE-AVAILABILITY" else "UNKNOWN", evaluation_stage="FINAL", critic_blocking_open=False) for r in mission.requirements]
    t0 = time.monotonic()
    res, reg = flow.call(OptimizePortfolioInput(requirements=mission.requirements, candidates=[cand], qualification_rows=rows, max_sites=3))
    assert time.monotonic() - t0 <= 1.0
    assert isinstance(res.payload, OptimizePortfolioPayload) and res.payload.selected_window_ids == [B]
    assert reg is not None and res.evidence_drafts[0].algorithm_id == "optimize-portfolio"

    t0 = time.monotonic()
    res, reg = flow.call(BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[handles[0].evidence_id], layer_kinds=["ELEVATION", "SLOPE", "ROUGHNESS"]), evidence=[handles[0]])
    assert time.monotonic() - t0 <= 5.0
    assert isinstance(res.payload, BuildDisplayLayersPayload) and len(res.payload.layers) == 3
    assert all(a.media_type == "image/png" and a.role.value == "DISPLAY_IMAGE" for a in res.artifacts[:3])
    assert all(len(layer.earth_corners or []) == 4 for layer in res.payload.layers)
    assert res.status.value == "SUCCEEDED"

    res2, _ = flow.call(BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[handles[0].evidence_id], layer_kinds=["SLOPE", "THERMAL"]), evidence=[handles[0]])
    assert res2.status.value == "LIMITED" and any(i.scope == "THERMAL" for i in res2.issues)
    res3, _ = flow.call(BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[handles[0].evidence_id], layer_kinds=["MINERAL"]), evidence=[handles[0]], check_registrar=False)
    assert res3.status.value == "BLOCKED"

    comparison = compare(flow, requirement(mission, "R-SLOPE-AVAILABILITY"), cand, [th], handles)
    req_h = flow.handles["COMPARE_REQUIREMENT:requirement"]
    cmp_h = flow.handles["COMPARE_REQUIREMENT:comparison"]
    assert comparison.status.value == "SUCCEEDED"
    claim = ClaimScope(claim_id="c1", claim_type="QUALIFICATION", requirement_id="R-SLOPE-AVAILABILITY", candidate_window_ids=[B], evidence_ids=[cmp_h.evidence_id, handles[0].evidence_id])
    res4, reg4 = flow.call(AuditEvidenceInput(claims=[claim], check_set=["provenance", "units", "scale", "coverage", "uncertainty", "proxies", "independence"]), evidence=[cmp_h, handles[0], req_h])
    assert isinstance(res4.payload, AuditEvidencePayload) and reg4 is not None
    gates = {g.gate_id: g.outcome for g in res4.payload.claim_gates[0].gates}
    assert gates["SC-04"] == "SATISFIED"  # requirement window resolved from the carried requirement record
    assert gates["SC-02"] == "SATISFIED"
