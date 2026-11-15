"""Bound private comparison context to the current persisted verifier request.

The frozen scientific input still carries its existing summary. This metadata
travels only in the picklable worker context and cannot grant artifact access.
"""

from typing import Any

from analogforge.db.store import NotFound
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import ScienceRequest
from analogforge.ports.science_payloads import CompareRequirementInput, VerifyRouteInput

MAX_BINDING_ROWS = 64


def current_verification_requests(
    tx: Any, inputs: Any, run: dict[str, Any], mission: dict[str, Any], rover: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Missing, foreign, stale or ambiguous records provide no authority."""
    if (not isinstance(inputs, CompareRequirementInput) or inputs.verification is None
            or inputs.requirement.observable != "unique_slope_exposure_m"
            or "EXPOSURE_SHORTFALL" not in inputs.verification.violation_codes
            or inputs.verification.test_result_id is None or inputs.candidate.candidate_id is None or rover is None):
        return {}
    try:
        summary, candidate_id = inputs.verification, str(inputs.candidate.candidate_id)
        scope = {"workspace_id": run["workspace_id"], "run_id": run["id"], "mode": run["mode"]}
        candidate = tx.require("candidates", candidate_id)
        if (candidate_id not in run.get("candidate_ids", [])
                or any(candidate.get(key) != value for key, value in scope.items())
                or candidate["window_id"] != inputs.candidate.window_id
                or canonical_sha256(candidate["aoi"]) != canonical_sha256(inputs.candidate.aoi)):
            return {}
        tests = tx.list("tests", {"run_id": run["id"], "candidate_id": candidate_id}, limit=MAX_BINDING_ROWS + 1)
        operations = tx.list("scientific_operations", {"run_id": run["id"], "operation": "VERIFY_ROUTE"},
                             limit=MAX_BINDING_ROWS + 1)
        if not tests or len(tests) > MAX_BINDING_ROWS or len(operations) > MAX_BINDING_ROWS:
            return {}
        test = max(tests, key=lambda row: (row.get("attempt_number", row.get("test_revision", 1)),
                                          row.get("created_at", ""), row["id"]))
        result = tx.require("test_results", str(summary.test_result_id))
        if (result["test_id"] != test["id"] or test["candidate_id"] != candidate_id
                or any(record.get(key) != value for record in (test, result) for key, value in scope.items())
                or result["outcome"] != summary.outcome or result.get("failure_category") != summary.failure_category
                or [v["code"] for v in result.get("violations", [])] != summary.violation_codes
                or canonical_sha256(result.get("metrics", [])) != canonical_sha256(
                    [metric.model_dump(mode="json") for metric in summary.metrics])):
            return {}
        constraints, route_sha = test["constraints"], test.get("route_artifact_sha256")
        expected = {"mode": run["mode"], "mission_revision_id": mission["id"],
                    "mission_content_sha256": mission["content_sha256"], "rover_revision_id": rover["id"],
                    "rover_content_sha256": rover["content_sha256"], "candidate_window_id": candidate["window_id"],
                    "test_revision": test["test_revision"]}
        if (not route_sha or test.get("mission_revision_id") != mission["id"]
                or test.get("rover_revision_id") != rover["id"]
                or any(constraints.get(key) != value for key, value in expected.items())
                or canonical_sha256(constraints) != test["constraints_sha256"]):
            return {}
        matches: dict[str, list[dict[str, Any]]] = {}
        for operation in operations:
            if (operation.get("status") not in {"SUCCEEDED", "LIMITED"}
                    or any(operation.get(key) != value for key, value in scope.items())):
                continue
            request = ScienceRequest.model_validate(operation["request"])
            source = request.inputs
            if (not isinstance(source, VerifyRouteInput) or request.operation.value != "VERIFY_ROUTE"
                    or request.mode != run["mode"] or source.constraints.model_dump(mode="json") != constraints
                    or source.constraints_sha256 != test["constraints_sha256"] or source.route_sha256 != route_sha
                    or canonical_sha256(source.constraints) != source.constraints_sha256
                    or canonical_sha256(source.route) != route_sha):
                continue
            receipt = tx.require("tool_receipts", operation["receipt_id"])
            invocation = tx.require("invocations", receipt["invocation_id"])
            request_sha = canonical_sha256(request)
            if (receipt["status"] != "SUCCEEDED" or receipt["input_sha256"] != request_sha
                    or invocation.get("status") != "SUCCEEDED" or invocation.get("task_kind") != "VERIFY_ROUTE"
                    or invocation.get("candidate_id") != candidate_id or invocation.get("input_hash") != request_sha
                    or any(record.get(key) != value
                           for record in (receipt, invocation) for key, value in scope.items())):
                continue
            for identifier in sorted(set(result.get("evidence_ids", [])) & set(operation.get("evidence_ids", []))):
                evidence = tx.require("evidence", identifier)
                if (identifier not in receipt.get("evidence_ids", []) or evidence.get("kind") != "VERIFICATION"
                        or evidence.get("algorithm_id") != "verify-route" or not evidence.get("artifact_sha256")
                        or any(evidence.get(key) != value for key, value in scope.items())):
                    continue
                matches.setdefault(identifier, []).append({
                    **scope, "candidate_id": candidate_id, "candidate_window_id": candidate["window_id"],
                    "test_id": test["id"], "test_result_id": result["id"],
                    "constraints_sha256": source.constraints_sha256, "route_sha256": route_sha,
                    "evidence_id": identifier, "artifact_sha256": evidence["artifact_sha256"],
                    "receipt_input_sha256": request_sha, "request": request.model_dump(mode="json"),
                })
        return {identifier: values[0] for identifier, values in matches.items() if len(values) == 1}
    except (KeyError, TypeError, ValueError, NotFound):
        return {}
