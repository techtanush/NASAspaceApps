"""Private verifier authority requires current persisted scope and registered request identity."""

from copy import deepcopy
from uuid import uuid4

import pytest

from analogforge.application.verification_scope import MAX_BINDING_ROWS, current_verification_requests
from analogforge.db.store import NotFound
from analogforge.ports.science import ScienceRequest
from analogforge.ports.science_payloads import CompareRequirementInput
from tests.integration.science.test_exposure_identity import case


class Records:
    def __init__(self, rows):
        self.rows = rows

    def require(self, kind, identifier):
        if identifier not in self.rows.get(kind, {}):
            raise NotFound()
        return self.rows[kind][identifier]

    def list(self, kind, filters, *, limit):
        assert limit == MAX_BINDING_ROWS + 1
        return [row for row in self.rows.get(kind, {}).values()
                if all(row.get(key) == value for key, value in filters.items())][:limit]


def data(tmp_path):
    _, context, _, report, summary, original, _ = case(tmp_path)
    binding = next(iter(context.verification_requests.values()))
    source = ScienceRequest.model_validate(binding["request"]).inputs
    scope = {key: binding[key] for key in ["workspace_id", "run_id", "mode"]}
    candidate_id, test_id, invocation_id, receipt_id, operation_id = [str(uuid4()) for _ in range(5)]
    reference = context.test_candidate.model_copy(update={"candidate_id": candidate_id})
    run = {"id": scope["run_id"], "workspace_id": scope["workspace_id"], "mode": scope["mode"],
           "candidate_ids": [candidate_id]}
    mission = {"id": str(source.constraints.mission_revision_id),
               "content_sha256": source.constraints.mission_content_sha256}
    rover = {"id": str(source.constraints.rover_revision_id), "content_sha256": source.constraints.rover_content_sha256}
    evidence_id = binding["evidence_id"]
    rows = {
        "candidates": {candidate_id: {**scope, "id": candidate_id, "window_id": reference.window_id,
                                     "aoi": reference.aoi.model_dump(mode="json")}},
        "tests": {test_id: {**scope, "id": test_id, "candidate_id": candidate_id, "attempt_number": 1,
            "mission_revision_id": mission["id"], "rover_revision_id": rover["id"], "test_revision": 1,
            "constraints": source.constraints.model_dump(mode="json"), "constraints_sha256": source.constraints_sha256,
            "route_artifact_sha256": source.route_sha256}},
        "test_results": {str(summary.test_result_id): {**scope, "id": str(summary.test_result_id), "test_id": test_id,
            "outcome": report.outcome, "failure_category": report.failure_category,
            "violations": [v.model_dump(mode="json") for v in report.violations],
            "metrics": [metric.model_dump(mode="json") for metric in report.metrics], "evidence_ids": [evidence_id]}},
        "scientific_operations": {operation_id: {**scope, "id": operation_id, "operation": "VERIFY_ROUTE",
            "status": "SUCCEEDED", "request": binding["request"], "receipt_id": receipt_id,
            "evidence_ids": [evidence_id]}},
        "tool_receipts": {receipt_id: {**scope, "id": receipt_id, "invocation_id": invocation_id,
            "status": "SUCCEEDED", "input_sha256": binding["receipt_input_sha256"], "evidence_ids": [evidence_id]}},
        "invocations": {invocation_id: {**scope, "id": invocation_id, "status": "SUCCEEDED",
            "task_kind": "VERIFY_ROUTE", "candidate_id": candidate_id, "input_hash": binding["receipt_input_sha256"]}},
        "evidence": {evidence_id: {**scope, "id": evidence_id, "kind": "VERIFICATION", "algorithm_id": "verify-route",
                                   "artifact_sha256": binding["artifact_sha256"]}},
    }
    inputs = CompareRequirementInput(requirement=original, candidate=reference, target_evidence_ids=[],
        candidate_evidence_ids=[evidence_id], verification=summary, observable_policy_id="route-exposure-v1")
    return Records(rows), inputs, run, mission, rover


def test_current_registered_request_binds_persisted_run_id_without_a_redundant_run_id(tmp_path):
    records, inputs, run, mission, rover = data(tmp_path)
    assert "run_id" not in run
    assert current_verification_requests(records, inputs, run, mission, rover)


@pytest.mark.parametrize("defect", ["result_mode", "test_mission", "test_rover", "constraint_hash", "route_hash",
    "receipt_hash", "invocation_candidate", "evidence_mode", "operation_mode", "membership", "newer_incomplete",
    "duplicate_operation", "operation_cap", "source_candidate"])
def test_foreign_stale_ambiguous_and_unbounded_records_never_supply_private_authority(tmp_path, defect):
    records, inputs, run, mission, rover = data(tmp_path)
    def first(kind):
        return next(iter(records.rows[kind].values()))
    if defect == "result_mode":
        first("test_results")["mode"] = "live"
    elif defect in {"test_mission", "test_rover"}:
        first("tests")["mission_revision_id" if defect == "test_mission" else "rover_revision_id"] = str(uuid4())
    elif defect in {"constraint_hash", "route_hash"}:
        first("tests")["constraints_sha256" if defect == "constraint_hash" else "route_artifact_sha256"] = "0" * 64
    elif defect == "receipt_hash":
        first("tool_receipts")["input_sha256"] = "0" * 64
    elif defect == "invocation_candidate":
        first("invocations")["candidate_id"] = str(uuid4())
    elif defect in {"evidence_mode", "operation_mode"}:
        first("evidence" if defect == "evidence_mode" else "scientific_operations")["mode"] = "live"
    elif defect == "membership":
        run["candidate_ids"] = []
    elif defect == "newer_incomplete":
        identifier = str(uuid4())
        records.rows["tests"][identifier] = {**first("tests"), "id": identifier, "attempt_number": 2}
    elif defect in {"duplicate_operation", "operation_cap"}:
        original = deepcopy(first("scientific_operations"))
        for _ in range(1 if defect == "duplicate_operation" else MAX_BINDING_ROWS):
            identifier = str(uuid4())
            records.rows["scientific_operations"][identifier] = {**original, "id": identifier}
    else:
        first("scientific_operations")["request"]["inputs"]["constraints"]["candidate_window_id"] = "other-candidate"
    assert current_verification_requests(records, inputs, run, mission, rover) == {}
