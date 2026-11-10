# ruff: noqa: E501, S603, S607, S101
"""Port conformance: every operation returns a kit-valid result the registrar stub accepts; bad results are rejected."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from support.builders import load_mission, load_rover, make_context, make_request, run
from support.registrar_stub import RegistrarRejection, register

from analogforge.ports import catalog
from analogforge.ports.science import (
    ArtifactDraft,
    ComputationStatus,
    ScienceComputationResult,
    ScienceOperation,
)
from analogforge.ports.science_payloads import DesignBenchmarkInput
from analogforge.science.facade import create_science_service


@pytest.fixture
def service():  # type: ignore[no-untyped-def]
    return create_science_service()


def _graph_design(strategy: str = "WAYPOINT_RETURN") -> DesignBenchmarkInput:
    mission = load_mission("mission-graph-regression")
    return DesignBenchmarkInput(
        mission=mission,
        rover=load_rover("ares-1"),
        candidate={  # type: ignore[arg-type]
            "window_id": catalog.GRAPH_WINDOW_ID,
            "name": "graph zone",
            "aoi": mission.target.model_copy(update={"body": "EARTH"}).model_dump(),
            "origin": "SYNTHETIC_CONTROL",
            "novelty_status": "NOT_ASSESSED",
            "discovery_method": "fixture",
        },
        analysis_evidence_id=None,
        graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH,
        strategy=strategy,  # type: ignore[arg-type]
        test_revision=1,
    )


def test_supported_operations_are_all_fifteen(service) -> None:  # type: ignore[no-untyped-def]
    assert service.supported_operations() == frozenset(ScienceOperation)


def test_design_result_is_registrable_and_hashes_match(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ctx = make_context(tmp_path)
    result, reg = run(service, _graph_design(), ctx)
    assert result.status == ComputationStatus.SUCCEEDED
    assert reg is not None and "design" in reg.evidence_ids
    assert result.algorithm_id == catalog.ALGORITHM_IDS["DESIGN_BENCHMARK"]
    assert result.payload is not None and result.payload.operation == "DESIGN_BENCHMARK"
    assert result.evidence_drafts[0].algorithm_id == "design-benchmark"
    assert result.artifacts[0].role.value == "CONSTRAINTS"


def _bad(service, tmp_path: Path):  # type: ignore[no-untyped-def]
    ctx = make_context(tmp_path)
    req = make_request(_graph_design())
    return req, ctx, service.execute(req, ctx)


def test_registrar_rejects_hash_mismatch(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    (ctx.scratch / res.artifacts[0].scratch_relpath).write_bytes(b"tampered")
    with pytest.raises(RegistrarRejection, match="sha256|size"):
        register(req, res, ctx)


def test_registrar_rejects_path_escape(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    art = res.artifacts[0]
    outside = tmp_path.parent / "outside.json"
    shutil.copy(ctx.scratch / art.scratch_relpath, outside)
    # a symlink inside scratch pointing out of scratch must be refused
    link = ctx.scratch / "escape.json"
    link.symlink_to(outside)
    forged = art.model_copy(update={"scratch_relpath": "escape.json"})
    res2 = ScienceComputationResult.model_validate(
        res.model_dump(mode="json") | {"artifacts": [forged.model_dump(mode="json")]}
    )
    with pytest.raises(RegistrarRejection, match="symlink|outside"):
        register(req, res2, ctx)
    with pytest.raises(ValueError, match="relative"):
        ArtifactDraft(local_key="x", scratch_relpath="../x", sha256="0" * 64, size_bytes=0, media_type="application/json", role="REPORT")  # type: ignore[arg-type]


def test_registrar_rejects_dangling_local_key(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    ev = res.evidence_drafts[0].model_copy(update={"parent_local_keys": ["nope"]})
    dumped = res.model_dump(mode="json")
    dumped["evidence_drafts"] = [ev.model_dump(mode="json")]
    with pytest.raises(ValueError):
        ScienceComputationResult.model_validate(dumped)  # the kit validator already refuses it


def test_registrar_rejects_payload_with_unknown_evidence_ref(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ctx = make_context(tmp_path)
    from analogforge.ports.science_payloads import SearchRouteInput

    r1, reg = run(service, _graph_design(), ctx)
    assert reg is not None and r1.payload is not None
    constraints = r1.payload.constraints  # type: ignore[union-attr]
    req = make_request(SearchRouteInput(constraints=constraints, constraints_sha256=r1.payload.constraints_sha256))  # type: ignore[union-attr]
    res = service.execute(req, ctx)
    assert res.status == ComputationStatus.SUCCEEDED
    forged_ev = res.evidence_drafts[0].model_copy(update={"local_key": "renamed"})
    dumped = res.model_dump(mode="json")
    dumped["evidence_drafts"] = [forged_ev.model_dump(mode="json")]
    dumped["payload"]["route_artifact_key"] = "missing-key"
    forged = ScienceComputationResult.model_validate(dumped)
    with pytest.raises(RegistrarRejection, match="unknown artifact key"):
        register(req, forged, ctx)


def test_registrar_rejects_non_synthetic_product_id(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    ev = res.evidence_drafts[0].model_copy(update={"dataset_product_id": "NASADEM_HGT"})
    forged = ScienceComputationResult.model_validate(res.model_dump(mode="json") | {"evidence_drafts": [ev.model_dump(mode="json")]})
    with pytest.raises(RegistrarRejection, match="SYNTHETIC_"):
        register(req, forged, ctx)


def test_registrar_rejects_wrong_input_hash(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    forged = ScienceComputationResult.model_validate(res.model_dump(mode="json") | {"input_sha256": "f" * 64})
    with pytest.raises(RegistrarRejection, match="input_sha256"):
        register(req, forged, ctx)


def test_unknown_artifact_parent_uuid_rejected(service, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    req, ctx, res = _bad(service, tmp_path)
    ev = res.evidence_drafts[0].model_copy(update={"parent_evidence_ids": [uuid.uuid4()]})
    forged = ScienceComputationResult.model_validate(res.model_dump(mode="json") | {"evidence_drafts": [ev.model_dump(mode="json")]})
    with pytest.raises(RegistrarRejection, match="not authorized"):
        register(req, forged, ctx)


# --------------------------------------------------------------------------- all fifteen operations
def test_every_operation_returns_a_registrable_result(tmp_path: Path) -> None:
    import yaml
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

    from analogforge.ports.datasets import DatasetManifest
    from analogforge.ports.science_payloads import (
        AssessCompatibilityInput,
        AuditEvidenceInput,
        BuildDisplayLayersInput,
        ClaimScope,
        CoverageSelection,
        FetchSourceInput,
        IngestLocalDatasetInput,
        OptimizePortfolioInput,
        QualificationRowInput,
        ResolveCoverageInput,
    )

    ctx = make_practice_context(tmp_path)
    flow = Flow(service(), ctx)
    mission = load_mission("mission-mars-mobility")
    ares = load_rover("ares-1")
    seen: set[str] = set()

    def note() -> None:
        seen.update(r.operation.value for r in flow.results)

    root = ctx.dataset_roots["practice-earth-grid-v1"]
    flow.call(IngestLocalDatasetInput(manifest=DatasetManifest.model_validate(yaml.safe_load((root / "manifest.yaml").read_text()))), datasets=["practice-earth-grid-v1"])
    target, th = characterize_mars(flow)
    sc = screen(flow, target)
    cand = candidate_ref(sc, "grid-r0c0")
    res, handles = analyze(flow, cand)
    compare(flow, mission.requirements[0], cand, [th], handles)
    compat, _ = flow.call(AssessCompatibilityInput(rover=ares, requirements=mission.requirements, candidate=cand, candidate_evidence_ids=[handles[0].evidence_id]), evidence=[handles[0]])
    assert compat.payload is not None and compat.payload.preliminary  # type: ignore[union-attr]
    dims = {d.metric_id: d.status for d in compat.payload.dimensions}  # type: ignore[union-attr]
    assert dims["max_surface_slope_deg"] == "PASS" and dims["energy_reserve_pct"] == "UNKNOWN"
    assert dims["ground_clearance_m"] == "UNKNOWN" and dims["max_obstacle_height_m"] == "UNKNOWN"
    att, _ = prove(flow, sc, "grid-r0c0", ares, "WAYPOINT_RETURN", 1)
    flow.results.extend(att.results.values())
    rows = [QualificationRowInput(candidate_window_id="grid-r0c0", requirement_id="R-SLOPE-AVAILABILITY", status="PASS", evaluation_stage="FINAL", critic_blocking_open=False)]
    flow.call(OptimizePortfolioInput(requirements=mission.requirements[:1], candidates=[cand], qualification_rows=rows, max_sites=2))
    flow.call(BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[handles[0].evidence_id], layer_kinds=["SLOPE"]), evidence=[handles[0]])
    cmp_h = flow.handles["COMPARE_REQUIREMENT:comparison"]
    flow.call(AuditEvidenceInput(claims=[ClaimScope(claim_id="c", claim_type="QUALIFICATION", requirement_id="R-SLOPE-AVAILABILITY", candidate_window_ids=["grid-r0c0"], evidence_ids=[cmp_h.evidence_id])], check_set=["provenance"]), evidence=[cmp_h])
    cov, _ = flow.call(ResolveCoverageInput(subject_kind="TARGET", aoi=mission.target, adapter_id="synthetic_practice", measurement_kinds=["TERRAIN"]))
    assert [s.selection_key for s in cov.payload.selections if s.access_state == "AVAILABLE"] == ["synthetic_practice:practice-mars-target-v1"]  # type: ignore[union-attr]
    net, _ = flow.call(ResolveCoverageInput(subject_kind="CANDIDATE", aoi=cand.aoi, adapter_id="earth_nasadem_hgt_v001", measurement_kinds=["TERRAIN"]), check_registrar=False)
    assert net.status.value == "BLOCKED" and net.issues[0].code == "UNSUPPORTED_PRODUCT"
    fetch, _ = flow.call(FetchSourceInput(selection=CoverageSelection(selection_key="x", adapter_id="earth_nasadem_hgt_v001", product_id=None, version=None, access_state="AVAILABLE"), aoi=cand.aoi), check_registrar=False)
    assert fetch.status.value == "BLOCKED" and fetch.payload is None
    note()
    assert seen == {op.value for op in ScienceOperation}
    for r in flow.results:  # every result is kit-valid and carries the catalog algorithm id when one exists
        ScienceComputationResult.model_validate(r.model_dump(mode="json"))
        if r.operation.value in catalog.ALGORITHM_IDS:
            assert r.algorithm_id == catalog.ALGORITHM_IDS[r.operation.value]
        assert r.input_sha256 and r.status in set(ComputationStatus)
