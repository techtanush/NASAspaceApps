"""Terminal provider failures identify a controlled branch without exposing model content."""

import json

import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider
from analogforge.agents.runtime.provider import ProviderError
from analogforge.ports.catalog import BUDGETS
from tests.integration.platform.test_live_rehearsal import task_and_context

PRIVATE = "private-model-output-or-credential-that-must-not-be-logged"


@pytest.mark.parametrize(
    "reason,response,expected_requests",
    [
        ("INCOMPLETE_RESPONSE", {"status": "incomplete", "output": [{"text": PRIVATE}]}, 1),
        ("REFUSAL", {"status": "completed", "output": [
            {"type": "message", "content": [{"type": "refusal", "refusal": PRIVATE}]},
        ]}, 1),
        ("SERIAL_CALL_COUNT", {"status": "completed", "output": [
            {"type": "function_call", "name": PRIVATE}, {"type": "function_call", "name": PRIVATE},
        ]}, 1),
        ("REPEATED_INVALID_ARGUMENTS", {"status": "completed", "output": [
            {"type": "function_call", "name": "submit_role_result", "call_id": "invalid",
             "arguments": json.dumps({"private": PRIVATE})},
        ]}, 2),
        ("REQUEST_BUDGET_EXHAUSTED", {"status": "completed", "output": [
            {"type": "function_call", "name": "get_run_snapshot", "call_id": "read",
             "arguments": json.dumps({"sections": [PRIVATE]})},
        ]}, BUDGETS["model_requests_per_invocation"]),
    ],
)
def test_provider_failure_diagnostics_are_branch_specific_and_private(
    reason, response, expected_requests, caplog
):
    task, context, registry, counts, _ = task_and_context()

    class Client:
        def create(self, **kwargs):
            return response

    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(Client(), sleep=lambda _: None).run(task, registry, context)
    assert caught.value.code == "MODEL_OUTPUT_INVALID"
    assert caught.value.reason == reason
    assert counts.count("model_requests_per_run") == expected_requests
    records = [r for r in caplog.records if r.getMessage().startswith("provider.output_rejected.")]
    assert len(records) == 1
    assert records[0].provider_failure_reason == reason
    assert records[0].invocation_id == str(task.invocation_id)
    assert records[0].role == task.role_key and records[0].task_kind == task.task_kind
    assert records[0].exc_info is None
    assert PRIVATE not in caplog.text
    assert PRIVATE not in str(vars(records[0]))


def test_corrected_submission_does_not_emit_terminal_failure_diagnostics(caplog):
    task, context, registry, _, _ = task_and_context()
    responses = iter([
        {"status": "completed", "output": [{
            "type": "function_call", "name": "submit_role_result", "call_id": "invalid",
            "arguments": json.dumps({"private": PRIVATE}),
        }]},
        {"status": "completed", "output": [{
            "type": "function_call", "name": "submit_role_result", "call_id": "corrected",
            "arguments": json.dumps(task.payload["prepared_submission"]),
        }]},
    ])

    class Client:
        def create(self, **kwargs):
            return next(responses)

    assert OpenAIProvider(Client()).run(task, registry, context).disposition == "COMPLETE"
    assert not any(r.getMessage().startswith("provider.output_rejected.") for r in caplog.records)
