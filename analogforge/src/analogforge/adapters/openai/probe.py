"""Probe strict function calling and structured output with the configured model."""

import json

from analogforge.adapters.openai.client import ResponsesClient
from analogforge.agents.runtime.provider import ProviderError


def probe(client: ResponsesClient) -> dict[str, str]:
    response = client.create(
        input="Call capability_probe with ok=true.",
        tools=[
            {
                "type": "function",
                "name": "capability_probe",
                "description": "Capability test",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            }
        ],
        tool_choice={"type": "function", "name": "capability_probe"},
    )
    calls = [i for i in response.get("output", []) if i.get("type") == "function_call"]
    if (
        response.get("status") != "completed"
        or len(calls) != 1
        or calls[0].get("name") != "capability_probe"
        or json.loads(calls[0]["arguments"]) != {"ok": True}
    ):
        raise ProviderError("MODEL_CAPABILITY_FAILED", "Strict function-call probe failed")
    response2 = client.create(
        input=[
            *response["output"],
            {"type": "function_call_output", "call_id": calls[0]["call_id"], "output": '{"ok":true}'},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "probe_result",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            }
        },
    )
    texts = [
        c.get("text", "")
        for i in response2.get("output", [])
        if i.get("type") == "message"
        for c in i.get("content", [])
        if c.get("type") == "output_text"
    ]
    if response2.get("status") != "completed" or len(texts) != 1 or json.loads(texts[0]) != {"ok": True}:
        raise ProviderError("MODEL_CAPABILITY_FAILED", "Structured-output probe failed")
    return {"status": "PASSED", "model": client.model}
