"""Provider switches preserve budgets, policy boundaries, and credential isolation."""

import json
from copy import deepcopy
from dataclasses import replace

import httpx
import pytest
from openai import APIStatusError, OpenAI
from pydantic import ValidationError

from analogforge.adapters.openai.client import RateLimitCooldown, ResponsesClient, portable_input
from analogforge.adapters.openai.probe import probe
from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.sanitize import sanitize
from analogforge.domain.budgets import BudgetExceeded
from analogforge.settings import Settings
from tests.integration.platform.test_live_rehearsal import task_and_context

# All credential markers in this file are deliberately fake.
# ruff: noqa: S106


def response(body, output=None):
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1700000000,
        "status": "completed",
        "model": body["model"],
        "output": output or [],
    }


def tool(name, args, call_id="call_1"):
    return {
        "type": "function_call",
        "id": "opaque_vendor_id",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(args),
        "status": "completed",
    }


def configured(primary_status=429, groq_handler=None, cooldown=None):
    seen = []

    def handle(request):
        body = json.loads(request.content)
        provider = "groq" if request.url.host == "api.groq.com" else "openai"
        seen.append((provider, body, request.headers["authorization"]))
        if provider == "openai" and primary_status != 200:
            return httpx.Response(
                primary_status,
                json={"error": {"message": "rejected", "type": "rate_limit_error"}},
                headers={"retry-after": "60"},
            )
        if provider == "groq" and groq_handler:
            return groq_handler(body)
        return httpx.Response(200, json=response(body))

    client = ResponsesClient(
        "primary-marker",
        "primary-model",
        groq_api_key="secondary-marker",
        groq_model="secondary-model",
        groq_fallback_enabled=True,
        cooldown=cooldown,
    )
    for name, key, url in (
        ("client", "primary-marker", "https://api.openai.com/v1"),
        ("groq", "secondary-marker", "https://api.groq.com/openai/v1"),
    ):
        setattr(
            client,
            name,
            OpenAI(
                api_key=key,
                base_url=url,
                max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            ),
        )
    return client, seen


def test_primary_healthy_never_calls_groq():
    client, seen = configured(200)
    client.create(input="bounded test", max_output_tokens=16)
    assert [s[0] for s in seen] == ["openai"]
    assert client.model == "primary-model"


def test_429_switch_is_sticky_and_uses_separate_credentials():
    client, seen = configured()
    charged = []
    client.create_budgeted(lambda: charged.append(True), input="first")
    client.create_budgeted(lambda: charged.append(True), input="next")
    assert [s[0] for s in seen] == ["openai", "groq", "groq"]
    assert [s[2] for s in seen] == ["Bearer primary-marker", "Bearer secondary-marker", "Bearer secondary-marker"]
    assert charged == [True]
    assert all(body["store"] is False and body["parallel_tool_calls"] is False for _, body, _ in seen)
    assert client.model == "secondary-model"
    assert client.attempts[0] == {
        "provider": "openai",
        "model": "primary-model",
        "status": "FAILED",
        "http_status": 429,
    }
    assert client.attempts[-1] == {"provider": "groq", "model": "secondary-model", "status": "SUCCEEDED"}


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500, 502, 503, 504])
def test_other_http_failures_do_not_switch(status):
    client, seen = configured(status)
    with pytest.raises(APIStatusError):
        client.create(input="test")
    assert [s[0] for s in seen] == ["openai"]


def test_budget_exhaustion_blocks_fallback_before_network():
    client, seen = configured()

    def exhausted():
        raise BudgetExceeded("model_requests_per_run")

    with pytest.raises(BudgetExceeded):
        client.create_budgeted(exhausted, input="test")
    assert [s[0] for s in seen] == ["openai"]


def test_shared_cooldown_carries_no_conversation_and_expires():
    now = [100.0]
    cooldown = RateLimitCooldown(lambda: now[0])
    first, _ = configured(cooldown=cooldown)
    first.create(input="workspace A")
    second, seen = configured(cooldown=cooldown)
    second.create(input="workspace B")
    assert [s[0] for s in seen] == ["groq"]
    assert "workspace A" not in json.dumps(seen)
    now[0] += 61
    third, seen = configured(200, cooldown=cooldown)
    third.create(input="workspace C")
    assert [s[0] for s in seen] == ["openai"]
    # Existing conversation stays on its selected model even after the cooldown ends.
    second.create(input="continue B")
    assert second.provider == "groq"


@pytest.mark.parametrize(
    "header,seconds", [(None, 60), ("bad", 60), ("nan", 60), ("inf", 60), ("-1", 1), ("9999", 300)]
)
def test_cooldown_is_bounded(header, seconds):
    state = RateLimitCooldown(lambda: 10)
    state.limited(header)
    assert state.until == 10 + seconds


def test_cross_provider_continuation_drops_hidden_reasoning_and_opaque_ids():
    items = [
        {"role": "user", "content": "explicit task"},
        {"type": "reasoning", "id": "secret_reasoning", "encrypted_content": "private"},
        tool("inspect_contract", {"id": "known"}),
        {"type": "function_call_output", "call_id": "call_1", "output": "verified result"},
    ]
    original = deepcopy(items)
    client, seen = configured()
    client.create(input=items)
    forwarded = seen[-1][1]["input"]
    assert forwarded == [items[0], {k: v for k, v in items[2].items() if k not in {"id", "status"}}, items[3]]
    assert items == original
    assert "private" not in json.dumps(forwarded) and "secret_reasoning" not in json.dumps(forwarded)


@pytest.mark.parametrize(
    "item",
    [
        {"type": "item_reference", "id": "opaque"},
        {"role": "user", "content": [{"type": "input_image", "image_url": "private"}]},
    ],
)
def test_nonportable_input_fails_closed(item):
    with pytest.raises(ProviderError):
        portable_input([item])


def submission_response(body, invalid=False):
    task = _expand_wire_task(json.loads(body["input"][0]["content"])["task"])
    submission = deepcopy(task["payload"]["prepared_submission"])
    if invalid:
        submission["evidence_ids"] = ["11111111-1111-4111-8111-111111111111"]
    return httpx.Response(200, json=response(body, [tool("submit_role_result", submission)]))


def test_actual_provider_requests_are_all_charged():
    task, context, registry, counts, _ = task_and_context()
    client, seen = configured(groq_handler=submission_response)
    result = OpenAIProvider(client, sleep=lambda _: None).run(task, registry, context)
    assert result.disposition == "COMPLETE"
    assert [s[0] for s in seen] == ["openai", "groq"]
    assert counts.count("model_requests_per_invocation") == counts.count("model_requests_per_run") == 2


def test_both_providers_limited_remain_bounded_and_typed():
    task, context, registry, counts, _ = task_and_context()
    client, seen = configured(groq_handler=lambda _: httpx.Response(429, json={"error": {"message": "limited"}}))
    sleeps = []
    with pytest.raises(ProviderError) as error:
        OpenAIProvider(client, sleep=sleeps.append).run(task, registry, context)
    assert error.value.code == "PROVIDER_RATE_LIMITED"
    assert [s[0] for s in seen] == ["openai", "groq", "groq", "groq"]
    assert counts.count("model_requests_per_run") == len(seen)
    assert len(sleeps) == 2


def test_groq_invalid_evidence_still_rejected_after_one_correction():
    task, context, registry, counts, calls = task_and_context()
    client, seen = configured(groq_handler=lambda body: submission_response(body, invalid=True))
    with pytest.raises(ProviderError) as error:
        OpenAIProvider(client, sleep=lambda _: None).run(task, registry, context)
    assert error.value.code == "MODEL_OUTPUT_INVALID"
    assert counts.count("model_requests_per_run") == len(seen) == 3
    assert calls == []


def test_correction_after_fallback_respects_request_cap_even_without_charge(monkeypatch):
    task, context, registry, _, _ = task_and_context()
    client, seen = configured(groq_handler=lambda body: submission_response(body, invalid=True))
    monkeypatch.setitem(
        __import__("analogforge.agents.runtime.openai_provider", fromlist=["BUDGETS"]).BUDGETS,
        "model_requests_per_invocation",
        2,
    )
    with pytest.raises(ProviderError) as error:
        OpenAIProvider(client, sleep=lambda _: None).run(task, registry, replace(context, charge=None))
    assert error.value.code == "MODEL_OUTPUT_INVALID"
    assert len(seen) == 2


def test_disabled_fallback_preserves_default_config_hash_and_ignores_unused_secret(tmp_path):
    baseline = Settings(_env_file=None, data_root=tmp_path)
    unused = Settings(_env_file=None, data_root=tmp_path, groq_api_key="gsk_fake-unused", groq_model="unused")
    assert baseline.public_config() == unused.public_config()
    assert not any(k.startswith("groq") for k in baseline.public_config())
    assert baseline.effective_config_sha256() == unused.effective_config_sha256()
    enabled = Settings(
        _env_file=None,
        data_root=tmp_path,
        groq_api_key="gsk_fake-key",
        groq_model="explicit",
        groq_fallback_enabled=True,
    )
    rotated = Settings(
        _env_file=None,
        data_root=tmp_path,
        groq_api_key="gsk_rotated",
        groq_model="explicit",
        groq_fallback_enabled=True,
    )
    assert enabled.effective_config_sha256() == rotated.effective_config_sha256()
    assert enabled.effective_config_sha256() != baseline.effective_config_sha256()
    assert "gsk_fake-key" not in repr(enabled) + json.dumps(enabled.public_config())
    assert sanitize({"groq_api_key": "gsk_fake-key", "message": "failure gsk_fake-key"}) == {
        "message": "failure [REDACTED]"
    }


@pytest.mark.parametrize("kwargs", [{"groq_api_key": "marker"}, {"groq_model": "model"}, {}])
def test_enabled_fallback_requires_both_explicit_settings(kwargs):
    with pytest.raises(ValidationError, match="Groq fallback requires"):
        Settings(_env_file=None, groq_fallback_enabled=True, **kwargs)


def test_probe_runs_both_capabilities_on_selected_fallback():
    def capabilities(body):
        output = (
            [tool("capability_probe", {"ok": True})]
            if body.get("tools")
            else [
                {
                    "type": "message",
                    "role": "assistant",
                    "id": "msg_test",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": '{"ok":true}', "annotations": []}],
                }
            ]
        )
        return httpx.Response(200, json=response(body, output))

    client, seen = configured(groq_handler=capabilities)
    assert probe(client) == {"status": "PASSED", "model": "secondary-model"}
    assert [s[0] for s in seen] == ["openai", "groq", "groq"]
    assert all(body["max_output_tokens"] == 1024 for _, body, _ in seen)


def test_workflow_factory_shares_only_cooldown_and_passes_private_fallback(tmp_path):
    from analogforge.application.scheduler import WorkflowEngine

    settings = Settings(_env_file=None, data_root=tmp_path,
                        openai_api_key="primary-marker", openai_model="primary-model",
                        groq_api_key="secondary-marker", groq_model="secondary-model", groq_fallback_enabled=True)
    engine = WorkflowEngine(object(), settings)
    first, second = engine._provider_client(), engine._provider_client()
    assert first is not second and first.cooldown is second.cooldown
    assert first.groq.api_key == "secondary-marker" and first.client.api_key == "primary-marker"
    assert str(first.groq.base_url) == "https://api.groq.com/openai/v1/"
    assert first.attempts == [] and second.attempts == []


def test_mid_conversation_limit_replays_verified_tool_output_without_reasoning():
    task, context, registry, counts, calls = task_and_context()
    client, seen = configured(groq_handler=submission_response)
    primary_requests = []

    def primary(request):
        body = json.loads(request.content)
        primary_requests.append(body)
        if len(primary_requests) == 1:
            return httpx.Response(200, json=response(body, [
                {"type":"reasoning", "id":"rs_private", "summary":[], "encrypted_content":"private-reasoning"},
                tool("get_run_snapshot", {"sections":["contract"]}),
            ]))
        return httpx.Response(429, json={"error":{"message":"limited"}})

    client.client = OpenAI(api_key="primary-marker", max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(primary)))
    result = OpenAIProvider(client, sleep=lambda _: None).run(task, registry, context)
    assert result.disposition == "COMPLETE"
    assert counts.count("model_requests_per_run") == len(primary_requests) + len(seen) == 3
    assert calls == [{"sections":["contract"]}]
    forwarded = seen[0][1]["input"]
    assert "private-reasoning" not in json.dumps(forwarded)
    assert "rs_private" not in json.dumps(forwarded)
    outputs = [i for i in forwarded if i.get("type") == "function_call_output"]
    assert len(outputs) == 1 and outputs[0]["call_id"] == "call_1"


def test_disabled_fallback_keeps_existing_429_behavior():
    def limited(request):
        return httpx.Response(429, json={"error":{"message":"limited"}})

    client = ResponsesClient("primary-marker", "primary-model", groq_api_key="unused-marker",
                             groq_model="unused-model", groq_fallback_enabled=False)
    client.client = OpenAI(api_key="primary-marker", max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(limited)))
    with pytest.raises(APIStatusError):
        client.create(input="test")
    assert client.groq is None and len(client.attempts) == 1


def test_transport_failure_does_not_change_provider():
    from openai import APIConnectionError

    def disconnected(request):
        raise httpx.ConnectError("disconnected", request=request)

    client, seen = configured()
    client.client = OpenAI(api_key="primary-marker", max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(disconnected)))
    with pytest.raises(APIConnectionError):
        client.create(input="test")
    assert client.provider == "openai" and seen == []


@pytest.mark.parametrize("repeat", [False, True])
def test_groq_rejected_tool_generation_shares_single_safe_correction(repeat):
    task, context, registry, counts, calls = task_and_context()
    attempts = []

    def generated(body):
        attempts.append(body)
        if repeat or len(attempts) == 1:
            return httpx.Response(400, json={"error": {
                "message": "Rejected tool generation", "code": "tool_use_failed",
                "failed_generation": "PRIVATE INVALID GENERATION; NEVER EXECUTE OR REPLAY",
            }})
        return submission_response(body)

    client, seen = configured(groq_handler=generated)
    provider = OpenAIProvider(client, sleep=lambda _: None)
    if repeat:
        with pytest.raises(ProviderError) as error:
            provider.run(task, registry, context)
        assert error.value.code == "MODEL_OUTPUT_INVALID"
    else:
        assert provider.run(task, registry, context).disposition == "COMPLETE"
    assert counts.count("model_requests_per_run") == len(seen) == 3
    assert len(attempts) == 2 and calls == []
    assert "PRIVATE INVALID GENERATION" not in json.dumps(attempts)
    assert json.loads(attempts[1]["input"][-1]["content"])["error"]["code"] == "MODEL_OUTPUT_INVALID"


def test_tool_generation_correction_does_not_add_another_schema_correction():
    task, context, registry, counts, _ = task_and_context()
    attempts = []

    def generated(body):
        attempts.append(body)
        if len(attempts) == 1:
            return httpx.Response(400, json={"error":{"code":"tool_use_failed", "message":"invalid"}})
        return submission_response(body, invalid=True)

    client, seen = configured(groq_handler=generated)
    with pytest.raises(ProviderError) as error:
        OpenAIProvider(client, sleep=lambda _: None).run(task, registry, context)
    assert error.value.code == "MODEL_OUTPUT_INVALID"
    assert counts.count("model_requests_per_run") == len(seen) == 3


@pytest.mark.parametrize("repeat", [False, True])
def test_structured_generation_rejection_gets_one_charged_safe_correction(repeat):
    seen_json = []

    def generated(body):
        seen_json.append(body)
        if repeat or len(seen_json) == 1:
            return httpx.Response(400, json={"error": {
                "message": "Invalid generated JSON", "code": "json_validate_failed",
                "failed_generation": "PRIVATE GENERATED JSON",
            }})
        return httpx.Response(200, json=response(body))

    client, seen = configured(groq_handler=generated)
    charges = []
    arguments = {"input": "explicit original input", "text": {"format": {"type":"json_schema"}}}
    if repeat:
        with pytest.raises(ProviderError) as error:
            client.create_budgeted(lambda: charges.append(True), **arguments)
        assert error.value.code == "MODEL_OUTPUT_INVALID"
    else:
        assert client.create_budgeted(lambda: charges.append(True), **arguments)["status"] == "completed"
    assert len(seen) == 3 and len(charges) == 2  # caller separately reserves the primary request
    assert len(seen_json) == 2 and "PRIVATE GENERATED JSON" not in json.dumps(seen_json)
    assert seen_json[1]["input"][0] == {"role":"user", "content":"explicit original input"}


def test_exhausted_structured_correction_budget_sends_no_additional_request():
    client, seen = configured(primary_status=200, groq_handler=lambda _: httpx.Response(
        400, json={"error":{"code":"json_validate_failed", "message":"rejected"}}))
    client.provider, client.model, client.started = "groq", "secondary-model", True

    def exhausted():
        raise BudgetExceeded("preparation_model_requests")

    with pytest.raises(BudgetExceeded):
        client.create_budgeted(exhausted, input="test", text={"format":{"type":"json_schema"}})
    assert len(seen) == 1
