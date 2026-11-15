"""Every transport preserves canonical validation, identity, budgets and credential boundaries."""

import json
from copy import deepcopy

import httpx
import pytest
from openai import APIStatusError, OpenAI
from pydantic import SecretStr, ValidationError

from analogforge.adapters.openai.client import RateLimitCooldown, ResponsesClient, fallback_options
from analogforge.adapters.openai.fallback import FallbackConfig
from analogforge.adapters.openai.schema_transport import tool_envelope, validate_original, wire_schema
from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.sanitize import sanitize
from analogforge.domain.budgets import BudgetExceeded
from analogforge.settings import Settings
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_groq_fallback import response

# Deliberately fake credentials only.
# ruff: noqa: S106

PROVIDERS = ("groq", "openrouter", "anthropic", "sambanova", "nvidia", "gemini")


def chain(order=PROVIDERS, *, handler=None, cooldown=None):
    configs = tuple(FallbackConfig(name, name + "-model", SecretStr(name + "-marker"),
                                   "openai" if name == "openrouter" else None) for name in order)
    client = ResponsesClient("primary-marker", "primary-model", fallbacks=configs, cooldown=cooldown)
    seen = []

    def handle(request):
        body = json.loads(request.content)
        provider = body["model"].removesuffix("-model")
        provider = "openai" if provider == "primary" else provider
        seen.append((provider, body, dict(request.headers)))
        if handler:
            return handler(provider, body)
        return httpx.Response(429, json={"error": {"message": "PRIVATE_BODY"}}, headers={"retry-after": "60"})

    client.client = OpenAI(api_key="primary-marker", max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    for name in order:
        adapter = client.fallback_clients[name]
        if name in {"groq", "openrouter"}:
            adapter = OpenAI(api_key=name + "-marker", max_retries=0,
                             http_client=httpx.Client(transport=httpx.MockTransport(handle)))
            client.fallback_clients[name] = adapter
            if name == "groq":
                client.groq = adapter
        else:
            adapter.http = httpx.Client(transport=httpx.MockTransport(handle))
    return client, seen


def output(provider, body, name="bounded", arguments=None):
    arguments = {"value": 2} if arguments is None else arguments
    if provider == "anthropic":
        data = {"stop_reason": "tool_use", "content": [
            {"type": "tool_use", "id": "native-call", "name": name, "input": arguments},
        ]}
    elif provider in {"sambanova", "nvidia", "gemini"}:
        text = json.dumps({"call": {"name": name, "arguments": arguments}})
        data = {"status": "completed", "steps": [{"type": "model_output", "content": [
            {"type": "text", "text": text},
        ]}]} if provider == "gemini" else {
            "choices": [{"finish_reason": "stop", "message": {"content": text}}],
        }
    else:
        data = response(body, [{"type": "function_call", "call_id": "native-call", "name": name,
                                "arguments": json.dumps(arguments)}])
    return httpx.Response(200, json=data)


def bounded_tools():
    return [{"type": "function", "name": "bounded", "strict": True, "parameters": {
        "type": "object", "properties": {"value": {"type": "integer", "minimum": 1, "maximum": 3}},
        "required": ["value"], "additionalProperties": False,
    }}]


def test_ordered_429_chain_charges_every_dispatch_and_pins_openrouter():
    def handler(provider, body):
        return output(provider, body) if provider == "anthropic" else httpx.Response(429)

    client, seen = chain(handler=handler)
    charges = []
    value = client.create_budgeted(lambda: charges.append(True), input="untrusted user", instructions="trusted",
                                   tools=bounded_tools(), tool_choice="required", max_output_tokens=4096)
    assert value["status"] == "completed"
    assert [row[0] for row in seen] == ["openai", "groq", "openrouter", "anthropic"]
    assert len(charges) == 3
    assert seen[0][1]["max_output_tokens"] == 4096
    assert all(body["max_output_tokens"] == 1024 for _, body, _ in seen[1:3])
    assert seen[3][1]["max_tokens"] == 1024
    assert seen[2][1]["provider"] == {"only": ["openai"], "require_parameters": True, "allow_fallbacks": False}
    assert "parallel_tool_calls" not in seen[2][1]
    assert seen[2][1]["tools"] == bounded_tools()
    assert seen[3][1]["tool_choice"] == {"type": "any", "disable_parallel_tool_use": True}
    assert [headers.get("authorization", headers.get("x-api-key")) for _, _, headers in seen] == [
        "Bearer primary-marker", "Bearer groq-marker", "Bearer openrouter-marker", "anthropic-marker",
    ]
    assert all("marker" not in json.dumps(attempt) for attempt in client.attempts)


@pytest.mark.parametrize("call_count", [0, 2])
def test_openrouter_rejects_nonserial_tool_output_before_dispatch_without_changing_provider(call_count):
    def handler(provider, body):
        if provider == "openai":
            return httpx.Response(429)
        return httpx.Response(200, json=response(body, [
            {"type": "function_call", "call_id": f"call-{index}", "name": "bounded",
             "arguments": '{"value":2}'} for index in range(call_count)
        ]))

    client, seen = chain(("openrouter", "nvidia"), handler=handler)
    with pytest.raises(ProviderError) as invalid:
        client.create(input="test", tools=bounded_tools(), tool_choice="required")
    assert invalid.value.code == "MODEL_OUTPUT_INVALID"
    assert [row[0] for row in seen] == ["openai", "openrouter"]


def test_shared_per_provider_cooldowns_skip_exhausted_stages_across_fresh_invocations():
    cooldown = RateLimitCooldown(lambda: 100)
    def handler(provider, body):
        return output(provider, body) if provider == "openrouter" else httpx.Response(429)
    first, _ = chain(handler=handler, cooldown=cooldown)
    first.create(input="workspace A")
    second, seen = chain(handler=handler, cooldown=cooldown)
    second.create(input="workspace B")
    assert [row[0] for row in seen] == ["openrouter"]
    assert "workspace A" not in json.dumps(seen)


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 500, 503])
@pytest.mark.parametrize("provider", ["openrouter", "anthropic", "sambanova", "nvidia", "gemini"])
def test_non429_never_switches_to_another_provider(status, provider):
    client, seen = chain((provider, "groq"), handler=lambda name, body: httpx.Response(
        429 if name == "openai" else status, json={"error": {"message": "PRIVATE_BODY"}},
    ))
    with pytest.raises(APIStatusError):
        client.create(input="input", tools=bounded_tools(), tool_choice="required")
    assert [row[0] for row in seen] == ["openai", provider]


def test_cancellation_or_budget_fence_stops_before_next_provider_network():
    client, seen = chain()

    def canceled():
        raise BudgetExceeded("canceled_or_lease_lost")

    with pytest.raises(BudgetExceeded):
        client.create_budgeted(canceled, input="never replay")
    assert [row[0] for row in seen] == ["openai"]


def test_all_provider_cooldowns_do_not_cause_hidden_retries():
    client, seen = chain(("groq",))
    with pytest.raises(APIStatusError):
        client.create(input="first")
    next_client, next_seen = chain(("groq",), cooldown=client.cooldown)
    with pytest.raises(ProviderError) as caught:
        next_client.create(input="next")
    assert caught.value.code == "PROVIDER_RATE_LIMITED"
    assert [row[0] for row in seen] == ["openai", "groq"]
    assert next_seen == []


def test_seven_provider_chain_cannot_exceed_existing_six_request_invocation_limit():
    task, context, registry, counts, calls = task_and_context()
    client, seen = chain()
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(client, sleep=lambda _: None).run(task, registry, context)
    assert caught.value.code == "MODEL_OUTPUT_INVALID"
    assert caught.value.reason == "REQUEST_BUDGET_EXHAUSTED"
    assert len(seen) == counts.count("model_requests_per_run") == 6
    assert [row[0] for row in seen] == ["openai", *PROVIDERS[:5]]
    assert calls == []


@pytest.mark.parametrize("provider", ["anthropic", "sambanova", "nvidia", "gemini"])
def test_continuation_preserves_tool_result_role_and_actual_call_correlation(provider):
    task, context, registry, counts, calls = task_and_context()
    packets = []

    def handler(name, body):
        if name == "openai":
            return httpx.Response(429)
        packets.append(deepcopy(body))
        if len(packets) == 1:
            return output(name, body, "get_run_snapshot", {"sections": ["contract"]})
        if name == "gemini":
            content = body["input"][0]["content"][0]["text"]
        else:
            content = body["messages"][0 if name == "anthropic" else 1]["content"]
        wire = _expand_wire_task(json.loads(content)["task"])
        return output(name, body, "submit_role_result", wire["payload"]["prepared_submission"])

    client, seen = chain((provider,), handler=handler)
    result = OpenAIProvider(client).run(task, registry, context)
    assert result.disposition == "COMPLETE" and calls == [{"sections": ["contract"]}]
    assert counts.count("model_requests_per_run") == len(seen) == 3
    second = packets[1]
    if provider == "anthropic":
        tool_call = second["messages"][1]["content"][0]
        tool_result = second["messages"][2]["content"][0]
        assert tool_call["type"] == "tool_use" and tool_result["type"] == "tool_result"
        assert tool_call["id"] == tool_result["tool_use_id"]
        assert second["messages"][2]["role"] == "user"
    elif provider == "gemini":
        steps = second["input"]
        assert steps[1]["type"] == "model_output" and steps[2]["type"] == "user_input"
        assert "untrusted_tool_result" in steps[2]["content"][0]["text"]
    else:
        tool_call = second["messages"][2]["tool_calls"][0]
        tool_result = second["messages"][3]
        assert tool_result["role"] == "tool" and tool_call["id"] == tool_result["tool_call_id"]


@pytest.mark.parametrize("provider", ["anthropic", "sambanova", "nvidia", "gemini"])
@pytest.mark.parametrize("arguments", [{"value": 99}, {"value": 2, "extra": True}, {"value": "2"}])
def test_native_wire_relaxation_never_relaxes_original_argument_schema(provider, arguments):
    tools = bounded_tools()
    original = deepcopy(tools)
    client, seen = chain((provider, "groq"), handler=lambda name, body: (
        httpx.Response(429) if name == "openai" else output(name, body, arguments=arguments)
    ))
    with pytest.raises(ProviderError) as caught:
        client.create(input="untrusted user", instructions="trusted", tools=tools, tool_choice="required")
    assert caught.value.code == "MODEL_OUTPUT_INVALID"
    assert [row[0] for row in seen] == ["openai", provider]  # Never provider-hop on invalid output.
    assert tools == original
    if provider == "anthropic":
        sent = seen[-1][1]["tools"][0]["input_schema"]
        assert "minimum" not in sent["properties"]["value"]
        assert sent["required"] == ["value"] and sent["additionalProperties"] is False


def test_wire_transform_does_not_confuse_property_names_with_schema_keywords_or_lose_definitions():
    tools = bounded_tools()
    tools[0]["parameters"] = {"$defs": {"Value": {"type": "string", "minLength": 2, "maxLength": 4}},
                               "type": "object", "properties": {"minimum": {"$ref": "#/$defs/Value"}},
                               "required": ["minimum"], "additionalProperties": False}
    envelope = tool_envelope(tools, "required")
    remote = wire_schema(envelope, "anthropic")
    assert "minimum" in remote["properties"]["call"]["anyOf"][0]["properties"]["arguments"]["properties"]
    assert remote["$defs"]["T0_Value"]["type"] == "string"
    validate_original({"call": {"name": "bounded", "arguments": {"minimum": "ok"}}}, envelope)
    with pytest.raises(ProviderError):
        validate_original({"call": {"name": "bounded", "arguments": {"minimum": "x"}}}, envelope)
    assert tools[0]["parameters"]["$defs"]["Value"]["minLength"] == 2


@pytest.mark.parametrize("provider", ["anthropic", "sambanova", "nvidia", "gemini"])
def test_real_role_proposal_bounds_reject_before_any_tool_execution(provider):
    task, context, registry, counts, calls = task_and_context()
    bad = deepcopy(task.payload["prepared_submission"])
    bad["summary"] = "x" * 801  # The original submission schema has maxLength=800.
    client, seen = chain((provider, "groq"), handler=lambda name, body: (
        httpx.Response(429) if name == "openai" else output(name, body, "submit_role_result", bad)
    ))
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(client, sleep=lambda _: pytest.fail("No invalid output retry/failover")).run(
            task, registry, context,
        )
    assert caught.value.code == "MODEL_OUTPUT_INVALID" and calls == []
    assert counts.count("model_requests_per_run") == len(seen) == 2


@pytest.mark.parametrize("provider", ["anthropic", "sambanova", "nvidia", "gemini"])
def test_real_role_success_through_native_schema_transport(provider):
    task, context, registry, counts, calls = task_and_context()

    def handler(name, body):
        if name == "openai":
            return httpx.Response(429)
        if name == "gemini":
            content = body["input"][0]["content"][0]["text"]
        else:
            content = body["messages"][0 if name == "anthropic" else 1]["content"]
        wire = _expand_wire_task(json.loads(content)["task"])
        return output(name, body, "submit_role_result", wire["payload"]["prepared_submission"])

    client, seen = chain((provider,), handler=handler)
    result = OpenAIProvider(client).run(task, registry, context)
    assert result.disposition == "COMPLETE" and calls == []
    assert counts.count("model_requests_per_run") == len(seen) == 2


def test_settings_hashes_only_explicit_chain_identity_and_never_loads_private_file(monkeypatch):
    for name in PROVIDERS:
        monkeypatch.delenv(name.upper() + "_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert all(getattr(settings, name + "_api_key") is None for name in PROVIDERS)
    baseline = settings.public_config()
    keys = {name + "_api_key": name + "-marker" for name in PROVIDERS}
    only_keys = Settings(_env_file=None, **keys)
    assert only_keys.public_config() == baseline
    configured = Settings(_env_file=None, **keys, model_fallback_order=["openrouter"],
                          openrouter_model="openai/gpt-5.4-nano", openrouter_upstream="openai")
    public = configured.public_config()
    assert "marker" not in json.dumps(public) and "marker" not in repr(configured)
    assert public["model_fallback_chain"] == [{"provider": "openrouter", "model": "openai/gpt-5.4-nano",
                                               "upstream": "openai", "trigger": "http_429"}]
    assert fallback_options(configured)["fallbacks"][0].provider == "openrouter"
    assert "marker" not in repr(fallback_options(configured)["fallbacks"])
    disabled = Settings(_env_file=None, model_fallback_order=[], groq_fallback_enabled=True)
    assert fallback_options(disabled)["fallbacks"] == ()


@pytest.mark.parametrize("order", [["groq", "groq"], ["deepgram"], ["cloudflare"], ["composio"], ["openrouter"]])
def test_invalid_or_incomplete_chain_is_rejected_without_echoing_keys(order):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, model_fallback_order=order, openrouter_api_key="private-marker")
    assert "private-marker" not in str(caught.value)


def test_provider_secrets_are_removed_from_diagnostics_including_native_headers():
    private = {name + "_api_key": "private-marker" for name in PROVIDERS}
    private.update({"x-api-key": "private-marker", "x-goog-api-key": "private-marker", "safe": "okay"})
    assert sanitize(private) == {"safe": "okay"}
    assert sanitize("nvapi-fake_token AIzaFakeGoogleToken sk-ant-fake") == "[REDACTED] [REDACTED] [REDACTED]"
