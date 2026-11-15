"""Compact output references preserve exact facts and the full independent policy gate."""

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _task_receipt_ids, submission_schema
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.wire_context import WireCodec
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_provider_policy_correction import scout_task


def compact_proposal(task, **updates):
    proposal = {**deepcopy(task.payload["authoritative_submission"]), **updates,
                "payload": {"_task_payload_ref": "authoritative_submission.payload"}}
    return WireCodec(task, _task_receipt_ids(task)).encode(proposal)


@pytest.mark.parametrize("disposition,next_action", [("COMPLETE", "continue"), ("NEEDS_USER_REVIEW", "request_review")])
def test_reference_round_trip_preserves_facts_and_independent_review(disposition, next_action):
    task, context, registry, counts = scout_task()
    original = deepcopy(task.payload)
    arguments = compact_proposal(task, disposition=disposition, next_action=next_action,
                                 summary="Review of the exact committed candidate set.")
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(kwargs)
            schema = next(tool["parameters"] for tool in kwargs["tools"] if tool["name"] == "submit_role_result")
            Draft202012Validator(schema).validate(arguments)
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "compact", "arguments": json.dumps(arguments)}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert len(calls) == counts.count("model_requests_per_run") == 1
    assert result.disposition == disposition and result.next_action == next_action
    assert result.payload == original["authoritative_submission"]["payload"]
    assert task.payload == original
    result.payload["shortlist"].clear()
    assert task.payload == original  # No mutable alias to canonical task facts.


@pytest.mark.parametrize("reference", [
    {"_task_payload_ref": "another_task.payload"},
    {"_task_payload_ref": "authoritative_submission.payload", "shortlist": []},
])
def test_forged_or_amended_reference_fails_before_any_tool_execution(reference):
    task, context, registry, counts = scout_task()
    arguments = compact_proposal(task)
    arguments["payload"] = reference

    class Client:
        def create(self, **kwargs):
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "forged", "arguments": json.dumps(arguments)}]}

    with pytest.raises(ProviderError) as error:
        OpenAIProvider(Client()).run(task, registry, context)
    assert error.value.reason == "REPEATED_INVALID_ARGUMENTS"
    assert counts.count("model_requests_per_run") == 2


def test_reference_does_not_authorize_foreign_evidence_or_missing_canonical_payload():
    task, context, registry, _ = scout_task()
    arguments = compact_proposal(task, evidence_ids=["11111111-1111-4111-8111-111111111111"])

    class Client:
        def create(self, **kwargs):
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "foreign", "arguments": json.dumps(arguments)}]}

    with pytest.raises(ProviderError) as error:
        OpenAIProvider(Client()).run(task, registry, context)
    assert error.value.reason == "REPEATED_INVALID_ARGUMENTS"
    no_authority = task.model_copy(update={"payload": {}})
    codec = WireCodec(no_authority, [])
    schema = codec.submission_schema(submission_schema(task.role_key))
    assert "anyOf" not in schema["properties"]["payload"]
    with pytest.raises(ValueError, match="Invalid task payload reference"):
        codec.submission({"payload": {"_task_payload_ref": "authoritative_submission.payload"}})


def test_large_shortlist_output_is_small_without_losing_any_input_fact():
    task, *_ = scout_task()
    proposal = deepcopy(task.payload["authoritative_submission"])
    proposal["payload"]["shortlist"] *= 25
    enlarged = task.model_copy(update={"payload": {**task.payload, "authoritative_submission": proposal}})
    codec = WireCodec(enlarged, _task_receipt_ids(enlarged))
    wire = compact_proposal(enlarged)
    assert len(json.dumps(wire)) < 1024
    assert codec.submission(wire)["payload"] == proposal["payload"]
    assert len(codec.submission(wire)["payload"]["shortlist"]) == 25


def test_final_dispatch_reserves_a_terminal_assessment_without_forcing_a_positive_outcome():
    task, context, registry, counts, _ = task_and_context()
    requests = []

    class Client:
        def create(self, **kwargs):
            requests.append(kwargs)
            terminal = len(requests) == 6
            if terminal:
                assert [tool["name"] for tool in kwargs["tools"]] == ["submit_role_result"]
                proposal = {**task.payload["prepared_submission"], "disposition": "NEEDS_EVIDENCE"}
                name, arguments = "submit_role_result", proposal
            else:
                name, arguments = "get_run_snapshot", {"sections": ["contract"]}
            return {"status": "completed", "output": [{"type": "function_call", "name": name,
                    "call_id": f"call-{len(requests)}", "arguments": json.dumps(arguments)}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert result.disposition == "NEEDS_EVIDENCE"
    assert counts.count("model_requests_per_run") == len(requests) == 6


@pytest.mark.parametrize("aliased", [False, True])
def test_oversized_summary_gets_exact_bound_without_accepting_or_echoing_invalid_text(aliased):
    task, context, registry, counts = scout_task()
    requests = []
    private_text = ((str(task.input_evidence_ids[0]) + " ") * 25 if aliased else "operator-private-" * 60)

    class Client:
        def create(self, **kwargs):
            requests.append(deepcopy(kwargs))
            if len(requests) == 1:
                arguments = compact_proposal(task, summary=private_text)
                if aliased:
                    assert len(arguments["summary"]) < 800 < len(private_text)
            else:
                feedback = json.loads(kwargs["input"][-1]["output"])
                assert feedback["error"]["details"] == [
                    {"field": "summary", "code": "string_too_long", "constraints": {"max_length": 800},
                     "remediation": "Use one short outcome sentence without identifiers; cite evidence_ids instead. "
                                    "The character limit applies after restoring wire aliases."}
                ]
                assert private_text not in json.dumps(feedback)
                arguments = compact_proposal(task, summary="Reviewed the committed candidate evidence.")
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": f"bounded-{len(requests)}", "arguments": json.dumps(arguments)}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert result.summary == "Reviewed the committed candidate evidence."
    assert len(requests) == counts.count("model_requests_per_run") == 2
