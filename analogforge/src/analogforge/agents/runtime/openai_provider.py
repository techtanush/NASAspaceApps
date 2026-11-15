"""Bounded strict Responses tool loop; provider output has no commit authority."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from copy import deepcopy
from functools import partial
from typing import Any, Literal
from uuid import UUID

from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

from analogforge.adapters.openai.client import ResponsesClient
from analogforge.agents.prompts.bundle import prompt_bundle
from analogforge.agents.runtime.invocation import _nested_references, validate_submission
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.provider_backoff import provider_backoff
from analogforge.agents.runtime.tool_projection import (
    OPERATOR_CONTEXT_INSTRUCTIONS,
    PROJECTION_INSTRUCTIONS,
    project_tool_result,
    specialize_tool_schemas,
)
from analogforge.agents.runtime.wire_context import (
    WIRE_INSTRUCTIONS,
    UnknownWireAlias,
    WireCodec,
    expand_wire_columns,
)
from analogforge.agents.schemas.payloads import PAYLOAD_MODELS
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask
from analogforge.domain.policy import PolicyViolation
from analogforge.ports.catalog import BUDGETS
from analogforge.tools.registry import ToolContext, ToolRegistry, strict_schema

OutputFailureReason = Literal[
    "INCOMPLETE_RESPONSE", "REFUSAL", "SERIAL_CALL_COUNT", "REPEATED_INVALID_ARGUMENTS", "REQUEST_BUDGET_EXHAUSTED"
]
_OUTPUT_FAILURE_MESSAGES = {
    "INCOMPLETE_RESPONSE": "Provider returned an incomplete response",
    "REFUSAL": "Provider refused the bounded task",
    "SERIAL_CALL_COUNT": "Expected exactly one serial function call",
    "REPEATED_INVALID_ARGUMENTS": "Repeated invalid tool/submission arguments",
    "REQUEST_BUDGET_EXHAUSTED": "Invocation exhausted model request budget",
}
_POLICY_FAILURE_FIELDS = {
    "NESTED_REFERENCE_NOT_AUTHORIZED": "payload",
    "FROZEN_ROLE_INPUT_CHANGED": "payload",
    "CONTRACT_CHANGE_REQUIRES_REVIEW": "payload",
    "ROVER_LIMIT_SUMMARY_CHANGED": "payload",
    "QUALIFICATION_SCOPE_CHANGED": "payload",
    "CANDIDATE_REVISION_CHANGED": "payload",
    "STATUS_INFLATION": "payload",
    "CONFIDENCE_INFLATION": "payload",
    "COMPARISON_CITATION_CHANGED": "payload",
    "COMPARISON_CITATION_MISSING": "payload",
    "QUALIFIED_USE_CHANGED": "payload",
    "CANDIDATE_CHOICE_NOT_PERMITTED": "payload",
    "STRATEGY_CHOICE_NOT_PERMITTED": "payload",
    "AUTHORITATIVE_ROLE_FACT_CHANGED": "payload",
    "REPAIR_NOT_PERMITTED": "payload",
    "REPAIR_CHOICE_NOT_PERMITTED": "payload",
    "REPAIR_TARGET_CHOICE_NOT_PERMITTED": "payload",
    "EVIDENCE_NOT_ESTABLISHED": "evidence_ids",
    "ISSUE_EVIDENCE_NOT_ESTABLISHED": "issues.evidence_ids",
    "CLAIM_REFERENCE_NOT_AUTHORIZED": "payload",
    "PUBLICATION_HOLD_REASON_REQUIRED": "payload.ready_to_publish",
}
_WIRE_INSTRUCTIONS = (
    "\nTask _wire_encoding describes lossless references only. When prepared_submission is omitted, it is identical "
    "to authoritative_submission. In scientific_audit, each gate's reason_ref/evidence_ref is a zero-based index "
    "into reason_catalog/evidence_catalog: substitute that exact value to reconstruct every full gate. All outcomes, "
    "findings, scopes and evidence IDs are retained. Catalog indexes are not evidence IDs. "
    "Review every gate and finding."
)


def _wire_task(task: AgentTask) -> dict[str, Any]:
    """Lossless model-only projection; canonical task and policy validation remain unchanged."""
    wire = task.model_dump(mode="json")
    payload = wire["payload"]
    encoding = {}
    if ("prepared_submission" in payload and "authoritative_submission" in payload
            and payload["prepared_submission"] == payload["authoritative_submission"]):
        payload.pop("prepared_submission")
        encoding["prepared_submission"] = "authoritative_submission"
    audit = payload.get("scientific_audit")
    if isinstance(audit, dict) and isinstance(audit.get("claim_gates"), list):
        gates = [gate for row in audit["claim_gates"] if isinstance(row, dict)
                 for gate in row.get("gates", []) if isinstance(gate, dict)]
        if (gates and not {"reason_catalog", "evidence_catalog"}.intersection(audit)
                and not any({"reason_ref", "evidence_ref"}.intersection(gate) for gate in gates)):
            for field in ("reason", "evidence"):
                catalog: list[Any] = []
                indexes = {}
                for gate in gates:
                    if field not in gate:
                        continue
                    value = gate.pop(field)
                    key = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    if key not in indexes:
                        indexes[key] = len(catalog)
                        catalog.append(value)
                    gate[field + "_ref"] = indexes[key]
                audit[field + "_catalog"] = catalog
            encoding["scientific_audit"] = "reason_evidence_catalogs_v1"
    if encoding:
        wire["_wire_encoding"] = encoding
    return wire


def _expand_wire_task(wire: dict[str, Any]) -> dict[str, Any]:
    """Inverse of the private wire projection, including distinct copies of repeated values."""
    canonical = expand_wire_columns(wire)
    encoding = canonical.pop("_wire_encoding", {})
    payload = canonical["payload"]
    if encoding.get("prepared_submission") == "authoritative_submission":
        payload["prepared_submission"] = deepcopy(payload["authoritative_submission"])
    if encoding.get("scientific_audit") == "reason_evidence_catalogs_v1":
        audit = payload["scientific_audit"]
        catalogs = {field: audit.pop(field + "_catalog") for field in ("reason", "evidence")}
        for row in audit["claim_gates"]:
            if not isinstance(row, dict):
                continue
            for gate in row.get("gates", []):
                if isinstance(gate, dict):
                    for field, catalog in catalogs.items():
                        if field + "_ref" in gate:
                            gate[field] = deepcopy(catalog[gate.pop(field + "_ref")])
    return canonical


class ProviderOutputError(ProviderError):
    """A controlled output-failure category, containing no model response content."""

    def __init__(self, reason: OutputFailureReason) -> None:
        super().__init__("MODEL_OUTPUT_INVALID", _OUTPUT_FAILURE_MESSAGES[reason])
        self.reason = reason


def _output_failure(task: AgentTask, reason: OutputFailureReason) -> ProviderOutputError:
    logging.getLogger(__name__).error(
        "provider.output_rejected.%s",
        reason,
        extra={
            "provider_failure_reason": reason,
            "invocation_id": str(task.invocation_id),
            "role": task.role_key,
            "task_kind": task.task_kind,
        },
    )
    return ProviderOutputError(reason)


def _task_receipt_ids(task: AgentTask) -> list[str]:
    expected = task.payload.get("authoritative_submission", task.payload.get("prepared_submission", {})).get(
        "payload", {}
    )
    receipts = {str(row["id"]) for row in task.payload.get("receipt_summaries", []) if row["status"] == "SUCCEEDED"}
    receipts.update(identifier for field, identifier in _nested_references(expected) if "receipt_id" in field)
    return sorted(receipts)


def _bind_reference_fields(schema: dict[str, Any], namespaces: dict[str, list[str]]) -> None:
    for field, reference in schema.get("properties", {}).items():
        kind = next((kind for kind in namespaces if kind + "_id" in field), None)
        if kind is None:
            continue
        eligible = namespaces[kind]
        item = {"$ref": "#/$defs/Task" + kind.title() + "Id"}
        if reference.get("type") == "array":
            if eligible:
                reference["items"] = item
            else:
                reference["maxItems"] = 0
        else:
            nullable = any(option.get("type") == "null" for option in reference.get("anyOf", []))
            if not eligible and not nullable:
                raise ProviderError("INPUT_INVALID", "Task lacks an authorized required reference")
            replacement = {"anyOf": [item, {"type": "null"}]} if nullable and eligible else (
                item if eligible else {"type": "null"}
            )
            schema["properties"][field] = replacement
    for value in schema.values():
        if isinstance(value, dict):
            _bind_reference_fields(value, namespaces)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _bind_reference_fields(item, namespaces)


def submission_schema(
    role: str, *, allowed_actions: Sequence[str] = (), allowed_evidence_ids: Sequence[UUID | str] | None = None,
    allowed_claim_ids: Sequence[str] | None = None, allowed_receipt_ids: Sequence[UUID | str] | None = None,
) -> dict[str, Any]:
    common = RoleSubmission.model_json_schema()
    payload = PAYLOAD_MODELS[role].model_json_schema()
    common.setdefault("$defs", {}).update(payload.pop("$defs", {}))
    common["properties"]["payload"] = payload
    common["properties"]["role_key"] = {"type": "string", "const": role}
    if allowed_evidence_ids is not None:
        eligible = sorted({str(identifier) for identifier in allowed_evidence_ids})
        if eligible:
            common["$defs"]["TaskEvidenceId"] = {"type": "string", "format": "uuid", "enum": eligible}
        for references in (
            common["properties"]["evidence_ids"], common["$defs"]["RoleIssue"]["properties"]["evidence_ids"]
        ):
            references["description"] = (
                "Use only this task's input_evidence_ids. Receipt, qualification, claim and revision IDs are not "
                "evidence IDs. Use [] when no supplied evidence supports this statement."
            )
            if eligible:
                references["items"] = {"$ref": "#/$defs/TaskEvidenceId"}
            else:
                references["maxItems"] = 0
    if allowed_claim_ids is not None and role in {"scientific_critic", "evidence_passport"}:
        claims = sorted(set(allowed_claim_ids))
        if claims:
            common["$defs"]["TaskClaimId"] = {"type": "string", "enum": claims}
        if role == "scientific_critic":
            accepted = payload["properties"]["accepted_claim_ids"]
            objection = common["$defs"]["Objection"]["properties"]
            if claims:
                accepted["items"] = {"$ref": "#/$defs/TaskClaimId"}
                objection["claim_id"] = {"anyOf": [{"$ref": "#/$defs/TaskClaimId"}, {"type": "null"}]}
            else:
                accepted["maxItems"] = 0
                objection["claim_id"] = {"type": "null"}
        elif claims:
            common["$defs"]["ClaimAnnotation"]["properties"]["claim_id"] = {"$ref": "#/$defs/TaskClaimId"}
        else:
            payload["properties"]["claim_annotations"]["maxItems"] = 0
    namespaces = {}
    for kind, identifiers in (("evidence", allowed_evidence_ids), ("receipt", allowed_receipt_ids)):
        if identifiers is not None:
            eligible = sorted({str(identifier) for identifier in identifiers})
            namespaces[kind] = eligible
            if eligible:
                common["$defs"]["Task" + kind.title() + "Id"] = {"type": "string", "format": "uuid", "enum": eligible}
    _bind_reference_fields(common, namespaces)
    common["properties"]["next_action"] = {
        "type": ["string", "null"],
        "enum": [*allowed_actions, None],
        "description": (
            "Exact allowed token/null; explanations in summary/issues. continue ends only this role; "
            "stop_investigation needs a supported run stop. Retain justified request_review/record_unknown."
        ),
    }
    return strict_schema(common)


def _nested_reference_details(task: AgentTask, proposal: RoleSubmission) -> list[dict[str, Any]]:
    # Shape validation makes every emitted path a schema-owned field/index, never untrusted prose or keys.
    proposal.validate_payload()
    namespaces = {"evidence": {str(identifier) for identifier in task.input_evidence_ids},
                  "receipt": set(_task_receipt_ids(task))}
    details = []

    def visit(value: Any, path: str, field: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, path + "." + key, key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, path + "." + str(index), field)
        elif value is not None:
            kind = next((kind for kind in namespaces if kind + "_id" in field), None)
            if kind is not None and str(value) not in namespaces[kind]:
                details.append({"field": path, "code": "NESTED_REFERENCE_NOT_AUTHORIZED", "reference_kind": kind,
                                "remediation": "Use only supplied committed evidence and receipt references in the "
                                               "matching task namespace; retain justified review or blockers."})

    visit(proposal.payload, "payload")
    return details[:8]


def _validation_details(
    error: ValueError, task: AgentTask, proposal: RoleSubmission | None = None,
) -> list[dict[str, Any]]:
    """Actionable field/code diagnostics without echoing untrusted values or private exception text."""
    if isinstance(error, UnknownWireAlias):
        return [{"field": "arguments", "code": "UNKNOWN_WIRE_ALIAS",
                 "remediation": "Use exact supplied wire aliases; never invent identifiers."}]
    if isinstance(error, PolicyViolation) and error.detail_code == "NESTED_REFERENCE_NOT_AUTHORIZED" and proposal:
        details = _nested_reference_details(task, proposal)
        if details:
            return details
    if isinstance(error, PolicyViolation) and error.detail_code == "STATUS_INFLATION" and proposal:
        expected = task.payload.get("authoritative_submission", task.payload.get("prepared_submission", {}))
        computed = {row["requirement_id"]: row["proposed_status"]
                    for row in expected.get("payload", {}).get("rows", [])}
        details = [{"field": f"payload.rows.{index}.proposed_status", "code": "STATUS_INFLATION",
                    "expected": computed[row["requirement_id"]],
                    "remediation": "Retain the exact computed status, including FAIL/GAP/UNKNOWN. "
                    "Contest evidence in issues/disposition, never by changing a computed row. "
                    "The exact task-bound payload reference is available."}
                   for index, row in enumerate(proposal.payload.get("rows", []))
                   if row.get("requirement_id") in computed
                   and row.get("proposed_status") != computed[row["requirement_id"]]]
        if details:
            return details[:8]
    if isinstance(error, PolicyViolation) and error.detail_code in _POLICY_FAILURE_FIELDS:
        remediation = (
            "Use only supplied committed evidence and receipt references: task.input_evidence_ids, "
            "authoritative_submission receipt references, and successful receipt_summaries."
            if error.detail_code == "NESTED_REFERENCE_NOT_AUTHORIZED"
            else "Use only task.input_evidence_ids."
            if error.detail_code in {"EVIDENCE_NOT_ESTABLISHED", "ISSUE_EVIDENCE_NOT_ESTABLISHED"}
            else "Preserve authoritative_submission facts and frozen task inputs; retain justified review or blockers."
        )
        if error.detail_code == "PUBLICATION_HOLD_REASON_REQUIRED":
            remediation = ("Keep false when justified: cite known unresolved issues or supply a concrete "
                           "WARNING/BLOCKING issue and repair. Non-PASS science alone does not block an honest report.")
        return [{"field": _POLICY_FAILURE_FIELDS[error.detail_code], "code": error.detail_code,
                 "remediation": remediation}]
    if isinstance(error, ValidationError):
        details = []
        for item in error.errors(include_input=False, include_url=False)[:8]:
            detail: dict[str, Any] = {"field": ".".join(str(part) for part in item["loc"]), "code": item["type"]}
            # Only schema-owned numeric bounds; never exception input/message/context prose.
            bounds = {key: value for key, value in item.get("ctx", {}).items()
                      if key in {"max_length", "min_length"}
                      and isinstance(value, int) and not isinstance(value, bool)}
            if bounds:
                detail["constraints"] = bounds
            if item["loc"] == ("summary",) and item["type"] == "string_too_long":
                detail["remediation"] = (
                    "Use one short outcome sentence without identifiers; cite evidence_ids instead. "
                    "The character limit applies after restoring wire aliases."
                )
            details.append(detail)
        return details
    if isinstance(error, json.JSONDecodeError):
        return [{"field": "arguments", "code": "invalid_json"}]
    if str(error) in {"Unlisted next action", "Unlisted action"}:
        return [{"field": "next_action", "code": "unlisted_action", "allowed_values": [*task.allowed_actions, None]}]
    if str(error) in {"Role/task mismatch", "Submission identity mismatch"}:
        return [{"field": "role_key/task_kind", "code": "task_identity_mismatch"}]
    return [{"field": "arguments", "code": "schema_or_policy_validation_failed"}]


class OpenAIProvider:
    def __init__(self, client: ResponsesClient, *, sleep: Any = time.sleep) -> None:
        self.client = client
        self.sleep = sleep

    def run(self, task: AgentTask, registry: ToolRegistry, context: ToolContext) -> RoleSubmission:
        if task.runtime_mode != "live":
            raise ProviderError("MODE_MISMATCH", "Live provider is unavailable in synthetic or replay mode")
        instructions, _ = prompt_bundle(task.role_key)
        codec = WireCodec(task, _task_receipt_ids(task))
        wire = codec.task(_wire_task(task))
        instructions += WIRE_INSTRUCTIONS + PROJECTION_INSTRUCTIONS
        if "target_profile_context" in task.payload:
            instructions += (" target_profile_context contains registered target primitives. "
                             "Pair-comparison metrics are produced downstream, not target-only scalars. "
                             "target_coordinate_context binds source frames and geometry preparation to real receipts; "
                             "the operator AOI is a horizontal footprint, not a source height-reference declaration.")
        if task.payload.get("untrusted_operator_context_ref"):
            instructions += OPERATOR_CONTEXT_INSTRUCTIONS
        items: list[dict[str, Any]] = [
            {"role": "user", "content": json.dumps({"task": wire}, separators=(",", ":"), ensure_ascii=False)}
        ]
        tools = registry.schemas(task.role_key, available_only=True)
        tools.append(
            {
                "type": "function",
                "name": "submit_role_result",
                "description": "Submit one final evidence-linked proposal.",
                "strict": True,
                "parameters": submission_schema(
                    task.role_key, allowed_actions=task.allowed_actions, allowed_evidence_ids=task.input_evidence_ids,
                    allowed_claim_ids=[claim["claim_id"] for claim in task.payload.get("authoritative_claims", [])],
                    allowed_receipt_ids=_task_receipt_ids(task),
                ),
            }
        )
        tools = specialize_tool_schemas(task, tools)
        tools = [{**tool, "parameters": (
            codec.submission_schema(tool["parameters"]) if tool["name"] == "submit_role_result"
            else codec.schema(tool["parameters"])
        )} for tool in tools]
        correction_used = False
        transport_attempts = 0

        request_count = 0

        def charge_request() -> None:
            nonlocal request_count
            if request_count >= BUDGETS["model_requests_per_invocation"]:
                raise _output_failure(task, "REQUEST_BUDGET_EXHAUSTED")
            if context.charge:
                context.charge("model_requests_per_invocation")
                context.charge("model_requests_per_run")
            request_count += 1

        for _ in range(BUDGETS["model_requests_per_invocation"]):
            charge_request()
            final_request = (request_count == BUDGETS["model_requests_per_invocation"]
                             or request_count >= task.budget.get("model_requests_per_run", float("inf")))
            request_tools = ([tool for tool in tools if tool["name"] == "submit_role_result"]
                             if final_request else tools)
            try:
                create_budgeted = getattr(self.client, "create_budgeted", None)
                create = (
                    partial(create_budgeted, charge_request)
                    if callable(create_budgeted) else self.client.create
                )
                response = create(
                    instructions=instructions, input=items, tools=request_tools, tool_choice="required",
                    max_output_tokens=4096,
                )
                transport_attempts = 0
            except (APIConnectionError, APITimeoutError) as exc:
                transport_attempts += 1
                if transport_attempts >= 3:
                    raise ProviderError("TOOL_TIMEOUT", "Provider transport exhausted its retry budget", True) from exc
                self.sleep(2**transport_attempts)
                continue
            except APIStatusError as exc:
                if (
                    getattr(self.client, "provider", None) == "groq" and exc.status_code == 400
                    and isinstance(exc.body, dict) and exc.body.get("code") == "tool_use_failed"
                ):
                    # Groq can reject malformed tool generation before returning a tool call.
                    # Share the existing single correction allowance; never parse/execute failed_generation.
                    if correction_used:
                        raise _output_failure(task, "REPEATED_INVALID_ARGUMENTS") from exc
                    correction_used = True
                    transport_attempts = 0
                    items.append({"role": "user", "content": json.dumps({"error": {
                        "code": "MODEL_OUTPUT_INVALID",
                        "message": "Return exactly one registered function call satisfying its supplied strict schema.",
                    }})})
                    continue
                if exc.status_code in {401, 403}:
                    raise ProviderError("PROVIDER_AUTH_FAILED", "Provider credentials were rejected") from exc
                provider_body = exc.body if isinstance(exc.body, dict) else {}
                provider_error = provider_body.get("error", provider_body)
                error_code = provider_error.get("code") if isinstance(provider_error, dict) else None
                if exc.status_code == 413 or isinstance(error_code, str) and error_code in {
                    "context_length_exceeded", "request_too_large", "input_too_large", "tokens_exceeded",
                }:
                    raise ProviderError(
                        "RESOURCE_LIMIT", "Provider input/context size exceeds the available request budget", False
                    ) from exc
                transport_attempts += 1
                if exc.status_code not in {429, 500, 502, 503, 504} or transport_attempts >= 3:
                    code = "PROVIDER_RATE_LIMITED" if exc.status_code == 429 else "SOURCE_UNAVAILABLE"
                    raise ProviderError(code, "Provider request failed", exc.status_code >= 429) from exc
                self.sleep(provider_backoff(exc.response.headers, transport_attempts))
                continue
            if response.get("status") != "completed":
                raise _output_failure(task, "INCOMPLETE_RESPONSE")
            output = response.get("output", [])
            if any(
                item.get("type") == "message" and any(c.get("type") == "refusal" for c in item.get("content", []))
                for item in output
            ):
                raise _output_failure(task, "REFUSAL")
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) != 1:
                raise _output_failure(task, "SERIAL_CALL_COUNT")
            # Continuation items remain private/in-memory; no reasoning is persisted or rendered.
            items.extend(output)
            call = calls[0]
            if final_request and call["name"] != "submit_role_result":
                raise _output_failure(task, "REQUEST_BUDGET_EXHAUSTED")
            proposal = None
            feedback = False
            try:
                raw_arguments = json.loads(call["arguments"])
                arguments = (codec.submission(raw_arguments) if call["name"] == "submit_role_result"
                             else codec.decode(raw_arguments))
                if call["name"] == "submit_role_result":
                    proposal = RoleSubmission.model_validate(arguments)
                    validate_submission(task, proposal)
                    if not set(proposal.evidence_ids) <= set(task.input_evidence_ids):
                        raise PolicyViolation("EVIDENCE_NOT_ESTABLISHED")
                    if any(not set(issue.evidence_ids) <= set(task.input_evidence_ids) for issue in proposal.issues):
                        raise PolicyViolation("ISSUE_EVIDENCE_NOT_ESTABLISHED")
                    return proposal
                result = registry.execute(call["name"], arguments, context, call_id=call["call_id"])
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                feedback = True
                details = _validation_details(exc, task, proposal)
                logging.getLogger(__name__).warning(
                    "provider.arguments_rejected.%s", ",".join(detail["code"] for detail in details),
                    extra={"invocation_id": str(task.invocation_id), "role": task.role_key,
                           "validation_fields": [detail["field"] for detail in details]},
                )
                if isinstance(exc, PolicyViolation):
                    detail_code = details[0]["code"]
                    logging.getLogger(__name__).warning(
                        "provider.proposal_rejected.%s", detail_code,
                        extra={"policy_detail_code": detail_code, "invocation_id": str(task.invocation_id),
                               "policy_failure_fields": [detail["field"] for detail in details]},
                    )
                if correction_used:
                    raise _output_failure(task, "REPEATED_INVALID_ARGUMENTS") from exc
                correction_used = True
                result = {
                    "error": {
                        "code": "MODEL_OUTPUT_INVALID",
                        "message": "Arguments failed schema/policy validation; correct once",
                        "details": details,
                    }
                }
            projected = result if feedback else project_tool_result(task, call["name"], arguments, result)
            wire_result = projected if feedback else codec.result(projected, call_id=call["call_id"])
            items.append({"type": "function_call_output", "call_id": call["call_id"],
                          "output": json.dumps(wire_result,
                                               separators=(",", ":"), ensure_ascii=False)})
        raise _output_failure(task, "REQUEST_BUDGET_EXHAUSTED")
