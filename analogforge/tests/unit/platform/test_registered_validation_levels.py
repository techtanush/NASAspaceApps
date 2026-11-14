"""Executed scientific receipts, scoped to each claim's DAG, establish real-source validation levels."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.application.assurance import audit, audit_registered_claim
from analogforge.application.passports import publish_passport
from analogforge.application.qualification import evaluate_candidate
from analogforge.application.registrar import Registrar
from analogforge.ports.domain_models import MeasuredMetric, MissionTestContract
from analogforge.ports.hashing import MISSION_CONTENT_EXCLUDE, model_sha256
from analogforge.ports.science import (
    EvidenceHandle,
    LocalScienceContext,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import CandidateRef, CompareRequirementInput
from analogforge.science.facade import create_science_service
from tests.integration.platform.test_assurance import audit_case
from tests.integration.platform.test_passport_assembly import passport_case
from tests.unit.platform.test_scientific_invocations import WorkerStoreDouble
from tests.unit.science.test_comparison import REQ


class AuditStore(WorkerStoreDouble):
    def create(self, kind, value):
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        return super().create(kind, {"id": str(uuid4()), **value})

    def enqueue(self, kind, payload, **kwargs):
        return self.create("jobs", {"kind": kind, "payload": payload, **kwargs})


@pytest.fixture(params=[(0.01, "FAIL"), (0.08, "PASS")], ids=["supported-negative", "nominal-positive"])
def comparison_publication(tmp_path, request):
    """Run the actual facade and Registrar in live mode against explicit offline measurement test inputs."""
    case = passport_case()
    workspace, run_id = str(case.audit.workspace_id), str(case.audit.run_id)
    store = AuditStore(workspace, run_id)
    blob_store = ContentAddressedStore(tmp_path / "cas")
    mission = case.mission.model_dump(mode="json")
    mission["requirements"] = [REQ["R-SLOPE-AVAILABILITY"].model_dump(mode="json")]
    mission["target"]["vertical_datum"] = "MOLA areoid"
    mission["content_sha256"] = model_sha256(MissionTestContract.model_validate(mission), MISSION_CONTENT_EXCLUDE)
    store.create("mission_revisions", mission)
    store.create("mission_acceptances", {"mission_revision_id": mission["id"], "accepted_at": mission["accepted_at"]})
    run = store.require("runs", run_id)
    run.update(mode="live", state="QUALIFYING", mission_revision_id=mission["id"], rover_revision_id=None,
               config_sha256="1" * 64, runtime={
                   "mission_content_sha256": mission["content_sha256"], "rover_content_sha256": None,
                   "dataset_policy_sha256": "2" * 64, "acquired_manifest_sha256": "3" * 64,
                   "algorithm_lock_sha256": "4" * 64,
               })
    # These explicitly constructed test measurements are not represented as NASA observations. The actual
    # comparison engine decides the S3 verdict, and its real registered result is the object under audit.
    blob = blob_store.put_bytes(b"offline test measurement", "application/json")
    measured = case.evidence[0].model_copy(update={
        "mode": "live", "kind": "DERIVED", "dataset_product_id": "OFFLINE_MEASUREMENT_TEST",
        "algorithm_id": "offline-test-measurement", "artifact_sha256": blob.sha256,
        "artifact_media_type": "application/json", "metrics": [MeasuredMetric(
            metric_id="slope_area_fraction:12-18", value=request.param[0], unit="fraction", support_scale_m=60,
            quantity_kind="DERIVED", method_id="offline-test-measurement", valid_fraction=1,
            uncertainty_note="Test input; no NASA scientific claim",
        )],
    })
    store.create("evidence", measured)
    store.create("artifacts", {"sha256": blob.sha256, "relative_path": blob.relative_path})
    candidate = case.candidates[0].model_copy(update={
        "mode": "live", "name": "Offline measurement boundary test", "origin": "USER_SUPPLIED",
        "evidence_ids": [], "discovery_method": "Explicit offline test nomination",
    })
    store.create("candidates", candidate)
    handle = EvidenceHandle.model_validate({k: v for k, v in measured.model_dump(mode="json").items()
                                            if k in EvidenceHandle.model_fields} | {"evidence_id": measured.id})
    expected_status = request.param[1]
    science_request = ScienceRequest(
        request_id=uuid4(), operation=ScienceOperation.COMPARE_REQUIREMENT, mode="live",
        inputs=CompareRequirementInput(
            requirement=mission["requirements"][0],
            candidate=CandidateRef(window_id="offline-window", candidate_id=candidate.id, name=candidate.name,
                                   aoi=candidate.aoi, origin=candidate.origin,
                                   novelty_status=candidate.novelty_status,
                                   discovery_method=candidate.discovery_method),
            target_evidence_ids=[], candidate_evidence_ids=[measured.id],
            observable_policy_id="slope-band-area-fraction-v1",
        ),
        input_evidence=[handle], source_policy=SourcePolicy(policy_id="offline-test", policy_sha256="5" * 64),
    )
    context = LocalScienceContext(scratch=tmp_path / "scratch", workspace_id=UUID(workspace), job_id=uuid4(),
                                  mode="live")
    result = create_science_service().execute(science_request, context)
    assert result.status == "SUCCEEDED", result.issues
    assert result.payload.adequacy.validation_level == "S3" and result.payload.proposed_status == expected_status
    kwargs = dict(scratch_dir=context.scratch, workspace_id=workspace, run_id=run_id,
                  invocation_id=str(uuid4()), tool_name="compare_requirement")
    return store, blob_store, mission, science_request, result, kwargs, candidate


def test_actual_registered_s3_comparison_and_final_passport_need_no_runtime_validation_map(comparison_publication):
    store, blobs, mission, request, result, kwargs, candidate = comparison_publication
    records = []
    expected_status = result.payload.proposed_status
    expected_publication = "LIMITED" if expected_status == "PASS" else "ALLOWED"

    def publish(unit, registered):
        record = evaluate_candidate(kwargs["workspace_id"], kwargs["run_id"], "live", str(candidate.id),
                                    registered.required_payload, list(registered.evidence_ids))
        report = audit_registered_claim(unit, unit.require("runs", kwargs["run_id"]), mission, None,
                                        record, registered.required_payload, blobs)
        assert report.publication == expected_publication
        assert report.claims[0].qualification_status == expected_status and report.claims[0].validation_level == "S3"
        assert next(g for g in report.claims[0].gates if g.gate_id == "SC-14").outcome == "SATISFIED"
        unit.create("qualifications", record)
        records.append(record)

    Registrar(store, blobs).register(request, result, apply_payload=publish, **kwargs)
    assert len(records) == 1
    assert "validation_receipts" not in store.require("runs", kwargs["run_id"])["runtime"]
    bundle = publish_passport(store, kwargs["workspace_id"], kwargs["run_id"], blobs)
    assert bundle.assurance.publication == expected_publication
    assert bundle.assurance.claims[0].validation_level == "S3"
    assert bundle.assurance.claims[0].qualification_status == expected_status
    assert bundle.passport.qualified_uses == []


@pytest.mark.parametrize("level,kind,algorithm,tool", [
    ("S2", "SOURCE", "ingest-local-dataset", "fetch_dataset"),
    ("S3", "COMPARISON", "compare-requirement", "compare_requirement"),
    ("S4", "VERIFICATION", "verify-route", "verify_route"),
])
@pytest.mark.parametrize("defect", [None, "unrelated", "failed", "wrong_tool", "wrong_kind", "wrong_algorithm",
                                   "foreign_workspace", "foreign_run", "foreign_mode", "manual_map",
                                   "foreign_evidence_workspace", "foreign_evidence_run", "foreign_evidence_mode"])
def test_validation_requires_exact_executed_receipt_within_this_claim_lineage(level, kind, algorithm, tool, defect):
    snapshot, claim, receipts = audit_case("FAIL")
    root = next(iter(snapshot.evidence.values())).model_copy(update={
        "mode": "live", "dataset_product_id": "OFFLINE_TEST_INPUT", "kind": "DERIVED",
    })
    executed = root.model_copy(update={"id": uuid4(), "kind": kind, "algorithm_id": algorithm})
    root = root.model_copy(update={"input_evidence_ids": [] if defect == "unrelated" else [executed.id]})
    validation = receipts[0].model_copy(update={"id": uuid4(), "mode": "live", "tool_name": tool,
                                               "evidence_ids": [executed.id]})
    if defect == "failed":
        validation = validation.model_copy(update={"status": "FAILED"})
    elif defect == "wrong_tool":
        validation = validation.model_copy(update={"tool_name": "inspect_contract"})
    elif defect in {"wrong_kind", "wrong_algorithm"}:
        executed = executed.model_copy(update={"kind": "ASSUMPTION"} if defect == "wrong_kind"
                                       else {"algorithm_id": "unrelated-algorithm"})
    elif defect in {"foreign_workspace", "foreign_run", "foreign_mode"}:
        field = {"foreign_workspace": "workspace_id", "foreign_run": "run_id", "foreign_mode": "mode"}[defect]
        validation = validation.model_copy(update={field: "replay" if field == "mode" else uuid4()})
    elif defect in {"foreign_evidence_workspace", "foreign_evidence_run", "foreign_evidence_mode"}:
        field = {"foreign_evidence_workspace": "workspace_id", "foreign_evidence_run": "run_id",
                 "foreign_evidence_mode": "mode"}[defect]
        executed = executed.model_copy(update={field: "replay" if field == "mode" else uuid4()})
    snapshot = replace(snapshot, mode="live", evidence={root.id: root, executed.id: executed},
                       validation_receipts={key: (executed.id,) for key in
                                            ("decoded_source", "common_scale_comparison", "independent_verification")})
    claim = replace(claim, validation_level=level)
    receipts = [receipts[0].model_copy(update={"mode": "live"})] + ([] if defect == "manual_map" else [validation])
    report = audit(snapshot, [claim], receipts)
    gate = next(g for g in report.claims[0].gates if g.gate_id == "SC-14")
    assert gate.outcome == ("SATISFIED" if defect is None else "UNSATISFIED")
    assert report.publication == ("ALLOWED" if defect is None else "BLOCKED")
