"""Provider schemas and independent validation keep common citations in the evidence namespace."""

import json
from copy import deepcopy
from uuid import uuid4

import jsonschema
import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _task_receipt_ids
from analogforge.agents.runtime.wire_context import WireCodec
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_provider_policy_correction import scout_task


def issue(evidence_ids):
    return {"code": "EVIDENCE_REVIEW", "severity": "BLOCKING", "requirement_id": None,
            "evidence_ids": evidence_ids, "message": "Review the supplied evidence.", "recommended_action": None}


@pytest.mark.parametrize("empty", [False, True])
def test_actual_provider_submission_schema_rejects_other_uuid_namespaces_without_reducing_eligible_evidence(empty):
    if empty:
        task, context, registry, _, _ = task_and_context()
    else:
        task, context, registry, _ = scout_task()
        task = task.model_copy(update={"input_evidence_ids": [*task.input_evidence_ids, uuid4()]})
    proposal = deepcopy(task.payload["prepared_submission"])
    codec = WireCodec(task, _task_receipt_ids(task))
    allowed = [str(identifier) for identifier in task.input_evidence_ids]
    wrong_namespace = [str(task.contract_revision_id), str(uuid4())]
    if not empty:
        wrong_namespace += [proposal["payload"]["shortlist"][0]["candidate_revision_id"],
                            proposal["payload"]["screening_receipt_id"]]
    checked = []

    class Client:
        def create(self, **kwargs):
            schema = next(tool["parameters"] for tool in kwargs["tools"] if tool["name"] == "submit_role_result")
            jsonschema.Draft202012Validator.check_schema(schema)
            if empty:
                assert schema["properties"]["evidence_ids"]["maxItems"] == 0
                assert schema["properties"]["evidence_ids"]["items"]["anyOf"][0] == {"type": "string", "format": "uuid"}
            validator = jsonschema.Draft202012Validator(schema)
            valid = {**proposal, "evidence_ids": allowed, "issues": [issue(allowed)]}
            validator.validate(codec.encode(valid))
            # Missing evidence can be reported with an empty citation list, including in an empty-evidence task.
            validator.validate(codec.encode({**proposal, "evidence_ids": [], "issues": [issue([])],
                                             "disposition": "NEEDS_EVIDENCE"}))
            for identifier in wrong_namespace:
                with pytest.raises(jsonschema.ValidationError):
                    validator.validate(codec.encode({**valid, "evidence_ids": [identifier]}))
                with pytest.raises(jsonschema.ValidationError):
                    validator.validate(codec.encode({**valid, "issues": [issue([identifier])]}))
            checked.append(True)
            return {"status": "completed", "output": [{
                "type": "function_call", "name": "submit_role_result", "call_id": "final",
                "arguments": json.dumps(codec.encode(proposal)),
            }]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert checked == [True] and result.payload == proposal["payload"]


def test_common_issue_citations_are_independently_validated_with_one_correction():
    task, context, registry, counts = scout_task()
    proposal = deepcopy(task.payload["prepared_submission"])
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            invalid = {**proposal, "issues": [issue([str(uuid4())])]}
            corrected = {**proposal, "issues": [issue([str(task.input_evidence_ids[0])])],
                         "disposition": "NEEDS_USER_REVIEW", "next_action": "request_review"}
            return {"status": "completed", "output": [{
                "type": "function_call", "name": "submit_role_result", "call_id": f"final-{len(calls)}",
                "arguments": json.dumps(invalid if len(calls) == 1 else corrected),
            }]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert len(calls) == counts.count("model_requests_per_run") == 2
    feedback = next(item for item in calls[1]["input"] if item.get("type") == "function_call_output")
    detail = json.loads(feedback["output"])["error"]["details"][0]
    assert detail["code"] == "ISSUE_EVIDENCE_NOT_ESTABLISHED" and detail["field"] == "issues.evidence_ids"
    assert result.disposition == "NEEDS_USER_REVIEW" and result.next_action == "request_review"
