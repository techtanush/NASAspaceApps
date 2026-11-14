"""Live provider rehearsed through real local HTTP with no external credentials."""

import json
from uuid import uuid4

import pytest

from analogforge.adapters.openai.client import ResponsesClient
from analogforge.adapters.openai.probe import probe
from analogforge.agents.runtime.openai_provider import OpenAIProvider, submission_schema
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.schemas.task import AgentTask
from analogforge.ports.catalog import ROLE_KEYS
from analogforge.tools.registry import ToolContext, ToolRegistry
from tests.support.fake_openai_server import fake_responses_server


def task_and_context():
    ws, run, invocation, contract = [uuid4() for _ in range(4)]
    submission = {
        "schema_version": "1.0",
        "role_key": "mission_director",
        "task_kind": "advance_workflow",
        "disposition": "COMPLETE",
        "summary": "Only registered tools were used.",
        "evidence_ids": [],
        "assumption_ids": [],
        "issues": [],
        "next_action": None,
        "payload": {
            "dispatch_role": None,
            "dispatch_task_kind": None,
            "dispatch_input_ids": [],
            "requirement_ids": [],
            "expected_evidence_kinds": [],
            "priority": "REQUIRED",
            "stop_reason": None,
            "portfolio_revision_id": None,
        },
    }
    task = AgentTask(
        workspace_id=ws,
        run_id=run,
        invocation_id=invocation,
        role_key="mission_director",
        task_kind="advance_workflow",
        runtime_mode="live",
        expected_run_revision=1,
        contract_revision_id=contract,
        rover_revision_id=None,
        contract_hash="a" * 64,
        rover_hash=None,
        input_evidence_ids=[],
        accepted_assumption_ids=[],
        allowed_actions=[],
        budget={},
        payload={"prepared_submission": submission},
    )
    counts = []
    context = ToolContext(
        "mission_director", str(ws), str(run), "live", 1, "a" * 64, charge=lambda key: counts.append(key)
    )
    calls = []
    registry = ToolRegistry({"get_run_snapshot": lambda args: calls.append(args) or {"state": "CHARACTERIZING"}})
    return task, context, registry, counts, calls


def test_live_responses_loop_serial_tools_and_call_id_correlation():
    task, context, registry, counts, calls = task_and_context()
    with fake_responses_server() as (url, requests):
        result = OpenAIProvider(
            ResponsesClient("local-test-credential", "configured-test-model", base_url=url), sleep=lambda _: None
        ).run(task, registry, context)
    assert result.role_key == "mission_director"
    assert calls == [{"sections": ["contract"]}]
    assert len(requests) == 2
    assert all(r["store"] is False and r["parallel_tool_calls"] is False for r in requests)
    assert all({tool["name"] for tool in request["tools"]} == {"get_run_snapshot", "submit_role_result"}
               for request in requests)
    outputs = [i for i in requests[1]["input"] if i.get("type") == "function_call_output"]
    assert outputs[0]["call_id"] == "opaque-call-1"
    assert counts.count("model_requests_per_run") == 2
    assert "local-test-credential" not in str(requests)


@pytest.mark.parametrize("mode", ["refusal", "malformed", "timeout"])
def test_live_failures_never_fall_back_to_scripted(mode):
    task, context, registry, counts, calls = task_and_context()
    with fake_responses_server(mode) as (url, requests):
        provider = OpenAIProvider(
            ResponsesClient(
                "local-test-credential", "configured-test-model", base_url=url, timeout=0.04 if mode == "timeout" else 2
            ),
            sleep=lambda _: None,
        )
        with pytest.raises(ProviderError) as error:
            provider.run(task, registry, context)
    assert error.value.code in {"TOOL_TIMEOUT", "MODEL_OUTPUT_INVALID"}
    assert len(requests) <= 3
    assert counts.count("model_requests_per_run") == len(requests)


def test_live_one_schema_correction_is_counted():
    task, context, registry, counts, calls = task_and_context()
    with fake_responses_server("malformed_once") as (url, requests):
        result = OpenAIProvider(
            ResponsesClient("local-test-credential", "configured-test-model", base_url=url), sleep=lambda _: None
        ).run(task, registry, context)
    assert result.disposition == "COMPLETE"
    assert counts.count("model_requests_per_run") == 2


def test_live_next_action_schema_and_correction_use_exact_task_actions():
    task, context, registry, counts, _ = task_and_context()
    task = task.model_copy(update={"allowed_actions": ["continue", "request_review"]})
    attempts = []

    def submission(arguments, _task):
        attempts.append(True)
        return {**arguments, "disposition": "NEEDS_USER_REVIEW", "next_action": (
            "Request review of req-1 threshold and support-scale assumptions." if len(attempts) == 1
            else "request_review"
        )}

    with fake_responses_server(transform_submission=submission) as (url, requests):
        result = OpenAIProvider(
            ResponsesClient("local-test-credential", "configured-test-model", base_url=url), sleep=lambda _: None
        ).run(task, registry, context)
    terminal = next(tool for tool in requests[0]["tools"] if tool["name"] == "submit_role_result")
    action_schema = terminal["parameters"]["properties"]["next_action"]
    assert set(action_schema["enum"]) == {"continue", "request_review", None}
    feedback = [item for item in requests[-1]["input"] if item.get("type") == "function_call_output"][-1]
    details = json.loads(feedback["output"])["error"]["details"]
    assert details == [{"field": "next_action", "code": "unlisted_action",
                        "allowed_values": ["continue", "request_review", None]}]
    assert result.next_action == "request_review" and result.disposition == "NEEDS_USER_REVIEW"
    assert counts.count("model_requests_per_run") == 3


def test_live_repeated_free_text_next_action_remains_rejected():
    task, context, registry, _, _ = task_and_context()
    with fake_responses_server(transform_submission=lambda args, _task: {**args, "next_action": "Ask a reviewer"}) as (
        url, requests,
    ):
        with pytest.raises(ProviderError, match="Repeated invalid") as caught:
            OpenAIProvider(
                ResponsesClient("local-test-credential", "configured-test-model", base_url=url), sleep=lambda _: None
            ).run(task, registry, context)
    assert caught.value.code == "MODEL_OUTPUT_INVALID"
    assert len(requests) == 3


def test_model_capability_probe_uses_strict_tool_and_structured_result():
    with fake_responses_server() as (url, requests):
        assert (
            probe(ResponsesClient("local-test-credential", "configured-test-model", base_url=url))["status"] == "PASSED"
        )
    assert len(requests) == 2


def test_model_capability_probe_preserves_response_wire_aliases():
    with fake_responses_server("strict_wire_aliases") as (url, requests):
        assert (
            probe(ResponsesClient("local-test-credential", "configured-test-model", base_url=url))["status"] == "PASSED"
        )
    assert len(requests) == 2
    call = next(item for item in requests[1]["input"] if item.get("type") == "function_call")
    assert call["async"] is False
    assert "async_" not in call


@pytest.mark.parametrize("role", ROLE_KEYS)
def test_role_schemas_have_no_unconstrained_object(role):
    schema = submission_schema(role)

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
                assert set(node.get("required", [])) == set(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
