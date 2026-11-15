"""Provider headroom and lossless read context never trade away scientific facts or validation."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import httpx
import jsonschema
import pytest
from openai import OpenAI

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task, _task_receipt_ids
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.tool_projection import project_tool_result, specialize_tool_schemas
from analogforge.agents.runtime.wire_context import WireCodec
from analogforge.tools.registry import ToolRegistry
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_groq_fallback import configured, response, tool


def real_contract_task():
    task, context, _registry, counts, _calls = task_and_context()
    mission = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/kit/missions/mission-mars-mobility.json").read_text()
    )
    acceptance = {
        "acceptance_id": str(uuid4()),
        "accepted_at": "2026-11-14T00:00:00Z",
        "mission_revision_id": str(task.contract_revision_id),
        "contract_sha256": task.contract_hash,
        "scientific_validation": False,
        "scope": "OPERATOR_CRITERIA_FOR_PINNED_REVISION",
    }
    payload = {
        **task.payload,
        "authoritative_submission": deepcopy(task.payload["prepared_submission"]),
        "contract_acceptance": acceptance,
    }
    task = task.model_copy(update={"payload": payload})
    contract = {
        "accepted": True,
        "acceptance": acceptance,
        "contract_revision_id": str(task.contract_revision_id),
        "hash": task.contract_hash,
        "requirements": mission["requirements"],
    }
    budget = {
        "limits": {"active_run_seconds": 900, "tool_calls_per_run": 160, "replans_total": 3},
        "counters": {"tool_calls_per_run": 2},
    }
    snapshot = {
        "id": str(task.run_id),
        "run_id": str(task.run_id),
        "workspace_id": str(task.workspace_id),
        "mission_revision_id": str(task.contract_revision_id),
        "rover_revision_id": None,
        "state": "CHARACTERIZING",
        "mode": "live",
        "revision": task.expected_run_revision,
        "candidate_ids": [],
        "pending_review": None,
        "runtime": {
            "budget": budget,
            "mission_content_sha256": task.contract_hash,
            "worker_processing_cache": ["INTERNAL_CACHE_SENTINEL" * 3000],
        },
    }
    return task, context, counts, contract, snapshot


def test_contract_table_and_repeated_tool_reads_are_exact_and_keep_all_scientific_fields():
    task, _context, _counts, contract, _snapshot = real_contract_task()
    original = deepcopy(contract)
    codec = WireCodec(task, _task_receipt_ids(task))
    first = codec.result(contract, call_id="inspect-one")
    assert codec.expand_result(first) == original and contract == original
    assert ["requirements"] in first["table_paths"]
    assert first["task_paths"]  # Acceptance is already supplied in the initial task, with identical values.
    assert len(json.dumps(first)) < len(json.dumps(contract)) * 0.8
    second = codec.result(contract, call_id="inspect-two")
    assert second["value"] == {"_tool_result_ref": "inspect-one"}
    assert codec.expand_result(second) == original and len(json.dumps(second)) < 150
    # Unknown future fields and explicit nulls must survive the same encoding.
    changed = deepcopy(contract)
    changed["requirements"][0]["future_field"] = {"negative": -3.5, "unknown": None}
    assert codec.expand_result(codec.result(changed, call_id="inspect-new")) == changed


def test_run_read_view_honors_sections_and_keeps_every_operator_limit_without_worker_caches():
    task, _context, _counts, _contract, snapshot = real_contract_task()
    canonical = {"run_revision": snapshot["revision"], "snapshot": snapshot}
    original = deepcopy(canonical)
    projected = project_tool_result(task, "get_run_snapshot", {"sections": ["contract"]}, canonical)
    assert canonical == original
    assert projected["snapshot"]["runtime"]["budget"] == snapshot["runtime"]["budget"]
    assert projected["snapshot"]["mission_revision_id"] == str(task.contract_revision_id)
    assert "worker_processing_cache" not in projected["snapshot"]["runtime"]
    assert "INTERNAL_CACHE_SENTINEL" not in json.dumps(projected)
    assert "candidate_ids" not in projected["snapshot"]
    assert (
        "candidate_ids"
        in project_tool_result(task, "get_run_snapshot", {"sections": ["selection"]}, canonical)["snapshot"]
    )
    foreign = {**canonical, "snapshot": {**snapshot, "run_id": str(uuid4())}}
    with pytest.raises(ProviderError):
        project_tool_result(task, "get_run_snapshot", {"sections": ["contract"]}, foreign)


def test_role_tool_schemas_bind_exact_task_without_weakening_strict_validation():
    task, _context, _counts, _contract, _snapshot = real_contract_task()
    registry = ToolRegistry({"inspect_contract": lambda _args: {}, "get_run_snapshot": lambda _args: {}})
    schemas = specialize_tool_schemas(task, registry.schemas(task.role_key, available_only=True))
    contract_schema = next(schema["parameters"] for schema in schemas if schema["name"] == "inspect_contract")
    validator = jsonschema.Draft202012Validator(contract_schema)
    validator.validate({"contract_revision_id": str(task.contract_revision_id)})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"contract_revision_id": str(uuid4())})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"contract_revision_id": str(task.contract_revision_id), "extra": "forbidden"})


def test_fallback_conversation_stays_small_across_contract_snapshot_and_repeated_reads():
    task, context, counts, contract, snapshot = real_contract_task()
    registry = ToolRegistry(
        {
            "inspect_contract": lambda _args: contract,
            "get_run_snapshot": lambda _args: {
                "run_revision": snapshot["revision"],
                "snapshot": snapshot,
            },
        }
    )
    packets = []

    def fallback(body):
        packets.append(deepcopy(body))
        wire_task = _expand_wire_task(json.loads(body["input"][0]["content"])["task"])
        if len(packets) in {1, 3}:
            schema = next(tool["parameters"] for tool in body["tools"] if tool["name"] == "inspect_contract")
            output = tool(
                "inspect_contract",
                {"contract_revision_id": schema["properties"]["contract_revision_id"]["enum"][0]},
                call_id=f"inspect-{len(packets)}",
            )
        elif len(packets) == 2:
            output = tool("get_run_snapshot", {"sections": ["contract", "budget"]}, call_id="snapshot")
        else:
            output = tool("submit_role_result", wire_task["payload"]["authoritative_submission"], call_id="submit")
        return httpx.Response(200, json=response(body, [output]))

    client, seen = configured(groq_handler=fallback)
    result = OpenAIProvider(client, sleep=lambda _seconds: None).run(task, registry, context)
    assert result.disposition == "COMPLETE"
    assert counts.count("model_requests_per_run") == len(seen) == 5
    assert all(body["max_output_tokens"] == 1024 for body in packets)
    assert seen[0][1]["max_output_tokens"] == 4096  # Primary remains independently configured.
    sizes = [len(json.dumps(packet, separators=(",", ":")).encode()) for packet in packets]
    assert max(sizes) < 22000, sizes
    assert "INTERNAL_CACHE_SENTINEL" not in json.dumps(packets)
    # The second identical contract read adds a handle, rather than another copy of every requirement.
    assert sizes[3] - sizes[2] < 800, sizes
    assert "_tool_result_ref" in json.dumps(packets[-1]["input"])


@pytest.mark.parametrize("status,code", [(413, None), (400, "context_length_exceeded"), (400, "input_too_large")])
def test_oversize_provider_request_is_precise_nonretryable_and_never_becomes_source_unavailable(status, code):
    task, context, registry, counts, _calls = task_and_context()
    client, _seen = configured()
    requests = []

    def rejected(request):
        requests.append(True)
        return httpx.Response(status, json={"error": {"code": code, "message": "PRIVATE_PROVIDER_BODY"}})

    client.client = OpenAI(
        api_key="primary-marker", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(rejected))
    )
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(client, sleep=lambda _seconds: pytest.fail("Oversized requests must not retry")).run(
            task, registry, context
        )
    assert caught.value.code == "RESOURCE_LIMIT" and caught.value.retryable is False
    assert "PRIVATE_PROVIDER_BODY" not in str(caught.value)
    assert len(requests) == counts.count("model_requests_per_run") == 1
    assert client.provider == "openai"  # Only429 permits a provider switch.


def test_fallback_headroom_never_accepts_a_truncated_structured_proposal():
    task, context, registry, _counts, _calls = task_and_context()
    packets = []

    def incomplete(body):
        packets.append(body)
        return httpx.Response(200, json={**response(body, []), "status": "incomplete"})

    client, _seen = configured(groq_handler=incomplete)
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(client).run(task, registry, context)
    assert caught.value.code == "MODEL_OUTPUT_INVALID" and caught.value.reason == "INCOMPLETE_RESPONSE"
    assert packets[0]["max_output_tokens"] == 1024


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
@pytest.mark.parametrize("requested_budget,effective_budget", [(4096, 1024), (512, 512)])
def test_groq_gpt_oss_reserves_bounded_output_for_tool_arguments(model, requested_budget, effective_budget):
    client, seen = configured()
    client.groq_model = model
    client.create(input="bounded task", max_output_tokens=requested_budget)
    primary, fallback = [body for _provider, body, _key in seen]
    assert primary["max_output_tokens"] == requested_budget and "reasoning" not in primary
    assert fallback["max_output_tokens"] == effective_budget
    assert fallback["reasoning"] == {"effort": "low"}
    assert fallback["store"] is False and fallback["parallel_tool_calls"] is False


def test_groq_reasoning_policy_preserves_other_options_and_never_changes_primary_requests():
    client, seen = configured()
    client.groq_model = "openai/gpt-oss-20b"
    reasoning = {"effort": "high", "summary": "auto"}
    client.create(input="bounded task", max_output_tokens=4096, reasoning=reasoning)
    assert seen[0][1]["reasoning"] == reasoning
    assert seen[1][1]["reasoning"] == {"effort": "low", "summary": "auto"}
    assert reasoning == {"effort": "high", "summary": "auto"}


def test_other_groq_models_receive_no_unsupported_reasoning_parameter():
    client, seen = configured()
    client.create(input="bounded task", max_output_tokens=4096)
    assert seen[1][1]["max_output_tokens"] == 1024
    assert "reasoning" not in seen[1][1]


def test_fallback_oversize_is_charged_once_and_retains_precise_resource_failure():
    task, context, registry, counts, _calls = task_and_context()
    client, seen = configured(
        groq_handler=lambda _body: httpx.Response(413, json={"error": {"message": "PRIVATE_PROVIDER_BODY"}})
    )
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(client, sleep=lambda _seconds: pytest.fail("Oversize cannot retry")).run(task, registry, context)
    assert caught.value.code == "RESOURCE_LIMIT" and not caught.value.retryable
    assert [provider for provider, _body, _key in seen] == ["openai", "groq"]
    assert counts.count("model_requests_per_run") == 2
    assert client.provider == "groq" and client.attempts[-1]["http_status"] == 413


def test_new_tool_returned_identifiers_remain_resolvable_after_reference_reuse():
    task, _context, _counts, _contract, _snapshot = real_contract_task()
    codec = WireCodec(task, _task_receipt_ids(task))
    identifier = str(uuid4())
    result = {"review_revision_id": identifier, "limitations": ["Negative finding must remain visible"]}
    wire = codec.result(result, call_id="new-id")
    alias = wire["value"]["review_revision_id"]
    assert alias != identifier and codec.decode({"review_revision_id": alias}) == {"review_revision_id": identifier}
    assert codec.expand_result(codec.result(result, call_id="reuse-new-id")) == result
