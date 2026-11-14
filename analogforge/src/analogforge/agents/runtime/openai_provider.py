"""Bounded strict Responses tool loop; provider output has no commit authority."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from analogforge.adapters.openai.client import ResponsesClient
from analogforge.agents.prompts.bundle import prompt_bundle
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.schemas.payloads import PAYLOAD_MODELS
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask
from analogforge.ports.catalog import BUDGETS
from analogforge.tools.registry import ToolContext, ToolRegistry, strict_schema


def submission_schema(role: str) -> dict[str, Any]:
    common = RoleSubmission.model_json_schema()
    payload = PAYLOAD_MODELS[role].model_json_schema()
    common.setdefault("$defs", {}).update(payload.pop("$defs", {}))
    common["properties"]["payload"] = payload
    common["properties"]["role_key"] = {"type": "string", "const": role}
    return strict_schema(common)


class OpenAIProvider:
    def __init__(self, client: ResponsesClient, *, sleep: Any = time.sleep) -> None:
        self.client = client
        self.sleep = sleep

    def run(self, task: AgentTask, registry: ToolRegistry, context: ToolContext) -> RoleSubmission:
        if task.runtime_mode != "live":
            raise ProviderError("MODE_MISMATCH", "Live provider is unavailable in synthetic or replay mode")
        instructions, _ = prompt_bundle(task.role_key)
        items: list[dict[str, Any]] = [{"role": "user", "content": json.dumps({"task": task.model_dump(mode="json")})}]
        tools = registry.schemas(task.role_key)
        tools.append(
            {
                "type": "function",
                "name": "submit_role_result",
                "description": "Submit one final evidence-linked proposal.",
                "strict": True,
                "parameters": submission_schema(task.role_key),
            }
        )
        correction_used = False
        transport_attempts = 0
        for _ in range(BUDGETS["model_requests_per_invocation"]):
            if context.charge:
                context.charge("model_requests_per_invocation")
                context.charge("model_requests_per_run")
            try:
                response = self.client.create(
                    instructions=instructions, input=items, tools=tools, tool_choice="required"
                )
                transport_attempts = 0
            except (APIConnectionError, APITimeoutError) as exc:
                transport_attempts += 1
                if transport_attempts >= 3:
                    raise ProviderError("TOOL_TIMEOUT", "Provider transport exhausted its retry budget", True) from exc
                self.sleep(2**transport_attempts)
                continue
            except APIStatusError as exc:
                if exc.status_code in {401, 403}:
                    raise ProviderError("PROVIDER_AUTH_FAILED", "Provider credentials were rejected") from exc
                transport_attempts += 1
                if exc.status_code not in {429, 500, 502, 503, 504} or transport_attempts >= 3:
                    code = "PROVIDER_RATE_LIMITED" if exc.status_code == 429 else "SOURCE_UNAVAILABLE"
                    raise ProviderError(code, "Provider request failed", exc.status_code >= 429) from exc
                self.sleep(2**transport_attempts)
                continue
            if response.get("status") != "completed":
                raise ProviderError("MODEL_OUTPUT_INVALID", "Provider returned an incomplete response")
            output = response.get("output", [])
            if any(
                item.get("type") == "message" and any(c.get("type") == "refusal" for c in item.get("content", []))
                for item in output
            ):
                raise ProviderError("MODEL_OUTPUT_INVALID", "Provider refused the bounded task")
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) != 1:
                raise ProviderError("MODEL_OUTPUT_INVALID", "Expected exactly one serial function call")
            # Continuation items remain private/in-memory; no reasoning is persisted or rendered.
            items.extend(output)
            call = calls[0]
            try:
                arguments = json.loads(call["arguments"])
                if call["name"] == "submit_role_result":
                    proposal = RoleSubmission.model_validate(arguments)
                    proposal.validate_payload()
                    if proposal.role_key != task.role_key or proposal.task_kind != task.task_kind:
                        raise ValueError("Role/task mismatch")
                    if proposal.next_action is not None and proposal.next_action not in task.allowed_actions:
                        raise ValueError("Unlisted next action")
                    return proposal
                result = registry.execute(call["name"], arguments, context, call_id=call["call_id"])
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                if correction_used:
                    raise ProviderError("MODEL_OUTPUT_INVALID", "Repeated invalid tool/submission arguments") from exc
                correction_used = True
                result = {
                    "error": {
                        "code": "MODEL_OUTPUT_INVALID",
                        "message": "Arguments failed schema/policy validation; correct once",
                    }
                }
            items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result)})
        raise ProviderError("MODEL_OUTPUT_INVALID", "Invocation exhausted model request budget")
