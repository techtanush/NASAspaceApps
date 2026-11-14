"""Shape-valid policy violations receive the same single bounded correction as schema errors."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task, _validation_details
from analogforge.agents.runtime.provider import ProviderError
from analogforge.domain.policy import PolicyViolation
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_role_invocations import active_invocation, role_attempt

__all__ = ["role_attempt"]
PRIVATE = "private-model-text-must-not-appear-in-diagnostics"


def scout_task():
    task, context, registry, counts, _ = task_and_context()
    evidence_id, receipt_id = uuid4(), uuid4()
    proposal = {**task.payload["prepared_submission"], "role_key": "earth_scout", "task_kind": "screen_candidates",
                "evidence_ids": [str(evidence_id)], "payload": {
                    "search_region_set_id": "bounded-catalog", "screening_receipt_id": str(receipt_id),
                    "screened_region_count": 4, "shortlist": [{
                        "candidate_revision_id": str(uuid4()), "analysis_revision_id": None, "screen_rank": 1,
                        "evidence_ids": [str(evidence_id)], "supported_requirement_ids": [],
                        "unknown_requirement_ids": ["req-1"], "known_analog_reference": False,
                        "selection_reason_code": "FEATURE_MATCH",
                    }], "excluded_candidate_refs": [], "search_limitations": ["Bounded offline test"],
                    "portfolio_revision_id": None, "discovery_exhausted": False,
                }}
    task = task.model_copy(update={
        "role_key": "earth_scout", "task_kind": "screen_candidates", "input_evidence_ids": [evidence_id],
        "allowed_actions": ["continue", "request_review"], "payload": {
            "prepared_submission": proposal, "authoritative_submission": deepcopy(proposal),
            "receipt_summaries": [{"id": str(receipt_id), "status": "SUCCEEDED"}],
        },
    })
    context.role = task.role_key
    return task, context, registry, counts


@pytest.mark.parametrize("violation,code,field", [
    ("nested_evidence", "NESTED_REFERENCE_NOT_AUTHORIZED", "payload.shortlist.0.evidence_ids.0"),
    ("nested_receipt", "NESTED_REFERENCE_NOT_AUTHORIZED", "payload.screening_receipt_id"),
    ("authoritative_fact", "AUTHORITATIVE_ROLE_FACT_CHANGED", "payload"),
    ("common_evidence", "EVIDENCE_NOT_ESTABLISHED", "evidence_ids"),
])
def test_shape_valid_policy_violation_is_corrected_once_without_forcing_completion(violation, code, field, caplog):
    task, context, registry, counts = scout_task()
    invalid = deepcopy(task.payload["prepared_submission"])
    invalid["summary"] = PRIVATE
    if violation == "nested_evidence":
        invalid["payload"]["shortlist"][0]["evidence_ids"] = [str(uuid4())]
    elif violation == "nested_receipt":
        invalid["payload"]["screening_receipt_id"] = str(uuid4())
    elif violation == "authoritative_fact":
        invalid["payload"]["screened_region_count"] = 400
    else:
        invalid["evidence_ids"] = [str(uuid4())]
    corrected = {**deepcopy(task.payload["prepared_submission"]), "disposition": "NEEDS_USER_REVIEW",
                 "next_action": "request_review", "summary": "Evidence requires operator review."}
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            return {"status": "completed", "output": [{
                "type": "function_call", "name": "submit_role_result", "call_id": f"proposal-{len(calls)}",
                "arguments": json.dumps(invalid if len(calls) == 1 else corrected),
            }]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert len(calls) == counts.count("model_requests_per_run") == 2
    feedback = next(item for item in calls[1]["input"] if item.get("type") == "function_call_output")
    details = json.loads(feedback["output"])["error"]["details"]
    assert len(details) == 1 and details[0]["field"] == field and details[0]["code"] == code
    assert details[0]["remediation"]
    if violation in {"nested_evidence", "nested_receipt"}:
        assert "supplied committed evidence and receipt references" in details[0]["remediation"]
    assert PRIVATE not in feedback["output"] and PRIVATE not in caplog.text
    assert result.disposition == "NEEDS_USER_REVIEW" and result.next_action == "request_review"
    assert result.payload == corrected["payload"]
    rejected = [record for record in caplog.records if record.getMessage() == f"provider.proposal_rejected.{code}"]
    assert len(rejected) == 1 and rejected[0].policy_detail_code == code
    assert rejected[0].exc_info is None


def test_repeated_shape_valid_policy_violation_fails_without_publication(role_attempt, monkeypatch, caplog):
    engine, store, workspace, run_id, _ = role_attempt
    calls = []

    class Client:
        def create(self, **kwargs):
            task = _expand_wire_task(json.loads(kwargs["input"][0]["content"])["task"])
            proposal = deepcopy(task["payload"]["prepared_submission"])
            proposal["summary"] = PRIVATE
            proposal["payload"]["portfolio_revision_id"] = str(uuid4())
            calls.append(True)
            return {"status": "completed", "output": [{
                "type": "function_call", "name": "submit_role_result", "call_id": f"proposal-{len(calls)}",
                "arguments": json.dumps(proposal),
            }]}

    monkeypatch.setattr(engine, "_provider_client", lambda: Client())
    with pytest.raises(ProviderError) as caught:
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert caught.value.reason == "REPEATED_INVALID_ARGUMENTS" and len(calls) == 2
    assert active_invocation(store)["status"] == "FAILED"
    assert store.list("role_results") == [] and store.list("agent_actions") == []
    assert PRIVATE not in caplog.text


def test_unrecognized_policy_error_text_is_not_echoed():
    task, *_ = scout_task()
    details = _validation_details(PolicyViolation(PRIVATE), task)
    assert PRIVATE not in str(details)
    assert details == [{"field": "arguments", "code": "schema_or_policy_validation_failed"}]
