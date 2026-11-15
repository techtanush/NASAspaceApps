"""Native Messages translation, preserving strict tools and stateless replay.

No SDK dependency, retries, response storage, server tools, or tool execution.
Only public error categories leave this boundary; provider prose is discarded.
"""

import json
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError

from analogforge.adapters.openai.schema_transport import validate_original, wire_schema
from analogforge.agents.runtime.provider import ProviderError


def _invalid() -> ProviderError:
    return ProviderError("MODEL_OUTPUT_INVALID", "Unsupported or invalid native provider message")


def messages_input(items: list[dict[str, Any]] | str) -> list[dict[str, Any]]:
    if isinstance(items, str):
        return [{"role": "user", "content": items}]
    messages: list[dict[str, Any]] = []
    for item in items:
        kind = item.get("type", "message")
        if kind == "function_call":
            try:
                arguments = json.loads(item["arguments"])
            except (KeyError, TypeError, ValueError) as exc:
                raise _invalid() from exc
            if not isinstance(arguments, dict):
                raise _invalid()
            message = {"role": "assistant", "content": [{
                "type": "tool_use", "id": item["call_id"], "name": item["name"], "input": arguments,
            }]}
        elif kind == "function_call_output":
            message = {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": item["call_id"], "content": item["output"],
            }]}
        elif kind == "message" and item.get("role") in {"user", "assistant"}:
            message = {"role": item["role"], "content": item["content"]}
        else:
            # Never promote arbitrary input messages into system instructions.
            raise _invalid()
        messages.append(message)
    return messages


class AnthropicMessages:
    def __init__(self, api_key: str, *, timeout: float = 30) -> None:
        self._key = api_key
        self.http = httpx.Client(timeout=timeout, follow_redirects=False)

    def create(self, model: str, **kwargs: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": min(kwargs.get("max_output_tokens", 1024), 1024),
            "messages": messages_input(kwargs["input"]),
        }
        if "instructions" in kwargs:
            body["system"] = kwargs["instructions"]
        if kwargs.get("tools"):
            body["tools"] = [{
                "name": tool["name"], "description": tool.get("description", ""),
                "input_schema": wire_schema(tool["parameters"], "anthropic"), "strict": True,
            } for tool in kwargs["tools"] if tool.get("type") == "function" and tool.get("strict") is True]
            if len(body["tools"]) != len(kwargs["tools"]):
                raise _invalid()
            choice = kwargs.get("tool_choice", "auto")
            if choice == "required":
                body["tool_choice"] = {"type": "any", "disable_parallel_tool_use": True}
            elif isinstance(choice, dict) and choice.get("type") == "function":
                body["tool_choice"] = {"type": "tool", "name": choice["name"], "disable_parallel_tool_use": True}
            elif choice in {"auto", "none"}:
                body["tool_choice"] = {"type": choice, "disable_parallel_tool_use": True}
            else:
                raise _invalid()
        format_ = kwargs.get("text", {}).get("format")
        if format_:
            if format_.get("type") != "json_schema" or format_.get("strict") is not True:
                raise _invalid()
            body["output_config"] = {"format": {
                "type": "json_schema", "schema": wire_schema(format_["schema"], "anthropic"),
            }}
        request = self.http.build_request(
            "POST", "https://api.anthropic.com/v1/messages", json=body,
            headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
        )
        try:
            response = self.http.send(request)
        except httpx.TimeoutException as exc:
            raise APITimeoutError(request=cast(Any, request)) from exc
        except httpx.RequestError as exc:
            raise APIConnectionError(message="Provider transport failed", request=cast(Any, request)) from exc
        if response.status_code >= 300:
            # APIStatusError normalizes into the existing role failure/budget logic.
            # Neither the error body nor the private request headers enter its message.
            safe_response = httpx.Response(
                response.status_code, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
                headers={key: value for key, value in response.headers.items() if key == "retry-after"},
            )
            raise APIStatusError("Provider request failed", response=cast(Any, safe_response), body=None)
        try:
            data = response.json()
            output = []
            for part in data["content"]:
                if part["type"] == "tool_use":
                    if not isinstance(part["input"], dict):
                        raise _invalid()
                    allowed = {tool["name"]: tool["parameters"] for tool in kwargs.get("tools", [])}
                    if part["name"] not in allowed:
                        raise _invalid()
                    validate_original(part["input"], allowed[part["name"]])
                    output.append({"type": "function_call", "call_id": part["id"], "name": part["name"],
                                   "arguments": json.dumps(part["input"], separators=(",", ":"))})
                elif part["type"] == "text":
                    if format_:
                        validate_original(json.loads(part["text"]), format_["schema"])
                    output.append({"type": "message", "role": "assistant", "content": [
                        {"type": "output_text", "text": part["text"]},
                    ]})
                else:
                    # Hidden thoughts/signatures are never reinterpreted as content.
                    raise _invalid()
            stop = data.get("stop_reason")
            if kwargs.get("tools") and len([part for part in output if part["type"] == "function_call"]) != 1:
                raise _invalid()
            return {"status": "completed" if stop in {"end_turn", "tool_use"} else "incomplete", "output": output}
        except (KeyError, TypeError, ValueError) as exc:
            raise _invalid() from exc
