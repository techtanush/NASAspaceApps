"""Durable preparation context; no run, scientific evidence or accepted contract is invented."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from openai import APITimeoutError, AuthenticationError, OpenAIError, RateLimitError
from pydantic import AwareDatetime, Field

from analogforge.api.errors import ApiError
from analogforge.application import missions
from analogforge.db.store import LeaseLost, PersistenceError
from analogforge.domain.budgets import BudgetExceeded, BudgetLedger
from analogforge.domain.validators import validate_mission_content
from analogforge.ports.catalog import BUDGETS
from analogforge.ports.common import PortModel, RuntimeMode
from analogforge.ports.domain_models import MissionTestContract
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import ScienceCancelled, ScienceDeadlineExceeded
from analogforge.tools.registry import ToolContext, ToolRegistry


class PreparationTask(PortModel):
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    preparation_id: UUID
    mission_id: UUID
    draft_revision_id: UUID
    run_id: None
    invocation_id: UUID
    mode: RuntimeMode
    task_kind: Literal["draft_contract", "revise_draft"]
    source_mission: dict[str, Any]
    target_revision: int
    rover_revision_id: UUID | None
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted_assumption_references: list[str]
    allowed_tools: list[Literal["validate_mission_draft", "submit_role_result"]]
    allowed_actions: list[Literal["PROPOSE_CONTRACT"]]
    remaining_model_requests: int = Field(ge=0, le=4)


class PreparationToolReceipt(PortModel):
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    preparation_id: UUID
    run_id: None
    mode: RuntimeMode
    created_at: AwareDatetime
    invocation_id: UUID
    tool_name: Literal["validate_mission_draft", "submit_role_result"]
    tool_version: Literal["1.0"]
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_sha256: str | None
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"]
    error_code: str | None
    elapsed_ms: float = Field(ge=0)
    cache_hit: bool


class PreparationPayload(PortModel):
    proposed_contract: MissionTestContract | None
    validation_receipt_id: UUID | None
    assumption_proposals: list[str]
    acceptance_required: Literal[True]


class PreparationRoleResult(PortModel):
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    preparation_id: UUID
    mission_id: UUID
    draft_revision_id: UUID
    mode: RuntimeMode
    created_at: AwareDatetime
    invocation_id: UUID
    role: Literal["requirements"]
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"]
    summary: str
    payload: PreparationPayload
    error_code: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _active(preparation: dict[str, Any]) -> None:
    if preparation["status"] == "CANCELLED":
        raise ScienceCancelled()


def _safe_error(error: Exception) -> str:
    default = "MODEL_OUTPUT_INVALID" if isinstance(error, ValueError) else "SYSTEM"
    code = str(getattr(error, "code", default))
    if isinstance(error, ScienceCancelled):
        return "RUN_CANCELLED"
    if isinstance(error, ScienceDeadlineExceeded):
        return "TOOL_TIMEOUT"
    if isinstance(error, (APITimeoutError, httpx.TimeoutException)):
        return "TOOL_TIMEOUT"
    if isinstance(error, AuthenticationError):
        return "PROVIDER_AUTH_FAILED"
    if isinstance(error, RateLimitError):
        return "PROVIDER_RATE_LIMITED"
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", code) else "SYSTEM"


def _result(
    task: PreparationTask,
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"],
    contract: dict[str, Any] | None,
    validation_id: UUID | None,
    error_code: str | None,
) -> PreparationRoleResult:
    return PreparationRoleResult(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=task.workspace_id,
        preparation_id=task.preparation_id,
        mission_id=task.mission_id,
        draft_revision_id=task.draft_revision_id,
        mode=task.mode,
        created_at=_now(),
        invocation_id=task.invocation_id,
        role="requirements",
        status=status,
        summary="Proposed contract requires explicit user acceptance"
        if status == "SUCCEEDED"
        else "Preparation could not publish a validated proposal",
        payload=PreparationPayload(
            proposed_contract=MissionTestContract.model_validate(contract) if contract else None,
            validation_receipt_id=validation_id,
            assumption_proposals=contract["assumptions"] if contract else [],
            acceptance_required=True,
        ),
        error_code=error_code,
    )


def _receipt(
    task: PreparationTask,
    name: Literal["validate_mission_draft", "submit_role_result"],
    arguments: dict[str, Any],
    output: dict[str, Any] | None,
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"],
    error_code: str | None,
    elapsed_ms: float = 0,
) -> PreparationToolReceipt:
    return PreparationToolReceipt(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=task.workspace_id,
        preparation_id=task.preparation_id,
        run_id=None,
        mode=task.mode,
        created_at=_now(),
        invocation_id=task.invocation_id,
        tool_name=name,
        tool_version="1.0",
        input_sha256=canonical_sha256(arguments),
        output_sha256=canonical_sha256(output) if output is not None else None,
        status=status,
        error_code=error_code,
        elapsed_ms=elapsed_ms,
        cache_hit=False,
    )


def _finish_failure(
    runtime: Any, job: dict[str, Any], task: PreparationTask, error: Exception, receipts: list[PreparationToolReceipt]
) -> None:
    code = _safe_error(error)
    blocked = code in {"BUDGET_EXHAUSTED", "PROVIDER_AUTH_FAILED", "PROVIDER_RATE_LIMITED", "TOOL_TIMEOUT"}
    status: Literal["BLOCKED", "FAILED"] = "BLOCKED" if blocked else "FAILED"
    result = _result(task, status, None, receipts[-1].id if receipts else None, code)
    sealed = {
        "role_result": result.model_dump(mode="json"),
        "preparation_receipts": [receipt.model_dump(mode="json") for receipt in receipts],
        "source_sha256": task.source_sha256,
    }
    try:
        with runtime.store.publication(job["workspace_id"], job["id"], job["lease_token"]) as unit:
            preparation = unit.require("preparations", str(task.preparation_id), lock=True)
            invocation = unit.require("agent_invocations", str(task.invocation_id), lock=True)
            if invocation["status"] != "RUNNING":
                return
            unit.replace(
                "agent_invocations",
                invocation["id"],
                {
                    **invocation,
                    **sealed,
                    "status": status,
                    "output_json": None,
                    "error": {"code": code},
                    "sealed_sha256": canonical_sha256(sealed),
                },
            )
            current = unit.require("jobs", job["id"], lock=True)
            state = "CANCELLED" if preparation["status"] == "CANCELLED" or code == "RUN_CANCELLED" else status
            unit.replace("preparations", preparation["id"], {**preparation, "status": state, "error": {"code": code}})
            unit.replace("jobs", current["id"], {**current, "state": state, "error": {"code": code}})
    except LeaseLost:
        # The initial dispatch charge remains durable. A lost worker cannot alter outputs.
        return


def _reserve(
    runtime: Any, job: dict[str, Any]
) -> tuple[PreparationTask, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None] | None:
    workspace_id, preparation_id = job["workspace_id"], job["preparation_id"]
    job_id, token, payload = job["id"], job["lease_token"], job["payload"]
    with runtime.store.publication(workspace_id, job_id, token) as unit:
        preparation = unit.require("preparations", preparation_id, lock=True)
        _active(preparation)
        if preparation["status"] == "SUCCEEDED":
            current = unit.require("jobs", job_id)
            unit.replace(
                "jobs",
                job_id,
                {**current, "state": "SUCCEEDED", "proposed_revision_id": preparation["proposed_revision_id"]},
            )
            return None
        header = unit.require("missions", payload["mission_id"], lock=True)
        missions.check_revision(header, payload["expected_revision"])
        draft = unit.require("mission_drafts", header["current_draft_id"])
        if draft["id"] != preparation["mission_draft_revision_id"]:
            raise PersistenceError("REVISION_CONFLICT", "Preparation draft differs from the queued input")
        rover = (
            unit.require("rover_revisions", payload["rover_revision_id"]) if payload.get("rover_revision_id") else None
        )
        source = {
            **draft["draft"],
            "id": header["id"],
            "mission_id": header["id"],
            "workspace_id": workspace_id,
            "revision": header["revision"],
        }
        source_hash = canonical_sha256(
            {
                "draft": draft,
                "rover_sha256": rover["content_sha256"] if rover else None,
                "mode": payload["mode"],
                "expected_revision": payload["expected_revision"],
            }
        )
        ledger = BudgetLedger.from_document(preparation.get("budget"))
        ledger.limits["preparation_model_requests"] = float(BUDGETS["preparation_model_requests"])
        try:
            ledger.charge("preparation_model_requests")
        except BudgetExceeded:
            current = unit.require("jobs", job_id)
            failure = {"code": "BUDGET_EXHAUSTED"}
            unit.replace("preparations", preparation_id, {**preparation, "status": "BLOCKED", "error": failure})
            unit.replace("jobs", job_id, {**current, "state": "BLOCKED", "error": failure})
            return None
        invocation_id = uuid4()
        task = PreparationTask(
            schema_version="1.0",
            id=uuid4(),
            workspace_id=UUID(workspace_id),
            preparation_id=UUID(preparation_id),
            mission_id=UUID(header["id"]),
            draft_revision_id=UUID(draft["id"]),
            run_id=None,
            invocation_id=invocation_id,
            mode=payload["mode"],
            task_kind="revise_draft" if header.get("current_contract_id") else "draft_contract",
            source_mission=source,
            target_revision=header["revision"],
            rover_revision_id=UUID(rover["id"]) if rover else None,
            source_sha256=source_hash,
            accepted_assumption_references=[],
            allowed_tools=["validate_mission_draft", "submit_role_result"],
            allowed_actions=["PROPOSE_CONTRACT"],
            remaining_model_requests=int(ledger.remaining("preparation_model_requests")),
        )
        unit.create(
            "agent_invocations",
            {
                "id": str(invocation_id),
                "run_id": None,
                "preparation_id": preparation_id,
                "role": "requirements",
                "task_kind": task.task_kind,
                "mode": payload["mode"],
                "status": "RUNNING",
                "prompt_version": "requirements-preparation/1.0",
                "input_hash": source_hash,
                "provider": "openai" if payload["mode"] == "live" else "scripted",
                "model": getattr(runtime.settings, "openai_model", None) if payload["mode"] == "live" else None,
                "task": task.model_dump(mode="json"),
                "usage_json": {"model_dispatches": 1, "completion_confirmed": False},
            },
        )
        unit.replace(
            "preparations",
            preparation_id,
            {
                **preparation,
                "status": "RUNNING",
                "budget": ledger.document(),
                "active_invocation_id": str(invocation_id),
                "source_sha256": source_hash,
                "model_dispatch_cap": int(BUDGETS["preparation_model_requests"]),
            },
        )
    return task, source, header, draft, rover


def handle(runtime: Any, job: dict[str, Any]) -> None:
    try:
        reserved = _reserve(runtime, job)
    except LeaseLost:
        return
    except (ApiError, PersistenceError, ScienceCancelled) as error:
        try:
            with runtime.store.publication(job["workspace_id"], job["id"], job["lease_token"]) as unit:
                preparation = unit.require("preparations", job["preparation_id"], lock=True)
                current = unit.require("jobs", job["id"], lock=True)
                status = "CANCELLED" if isinstance(error, ScienceCancelled) else "FAILED"
                failure = {"code": _safe_error(error)}
                unit.replace("preparations", preparation["id"], {**preparation, "status": status, "error": failure})
                unit.replace("jobs", current["id"], {**current, "state": status, "error": failure})
        except LeaseLost:
            return
        return
    if reserved is None:
        return
    task, source, header, draft, rover = reserved
    workspace_id, preparation_id = job["workspace_id"], job["preparation_id"]
    job_id, token, payload = job["id"], job["lease_token"], job["payload"]
    invocation_id, source_hash = task.invocation_id, task.source_sha256
    # No transaction or lock is held while the provider executes.
    validation_receipts: list[PreparationToolReceipt] = []
    try:
        scenarios = runtime.scenarios()
        scenario_id = next(
            key
            for key, value in scenarios.items()
            if value["body"] == source["target"]["body"] and "synthetic" in value["allowed_modes"]
        )
        proposed = runtime.engine.prepare(
            source, workspace_id, preparation_id=preparation_id, scenario_config_id=scenario_id, mode=payload["mode"]
        )
        for field in ("name", "objective", "target"):
            if proposed[field] != source[field]:
                raise PersistenceError("MODEL_OUTPUT_INVALID", "Preparation changed a supplied mission field")
        supplied = {row["id"]: row for row in source.get("requirements", [])}
        returned = {row["id"]: row for row in proposed["requirements"]}
        for identifier, requirement in supplied.items():
            if identifier not in returned or {k: v for k, v in requirement.items() if k != "origin"} != {
                k: v for k, v in returned[identifier].items() if k != "origin"
            }:
                raise PersistenceError("MODEL_OUTPUT_INVALID", "Preparation changed a supplied requirement")
        started = time.monotonic()

        def validate(arguments: dict[str, Any]) -> dict[str, Any]:
            issues = validate_mission_content(arguments["draft"], rover)
            return {
                "valid": not any(issue.severity == "ERROR" for issue in issues),
                "normalized_draft": arguments["draft"],
                "violations": [issue.as_dict() for issue in issues],
                "assumption_proposals": arguments["draft"]["assumptions"],
                "acceptance_blockers": ["USER_ACCEPTANCE_REQUIRED"],
            }

        validation = ToolRegistry({"validate_mission_draft": validate}).execute(
            "validate_mission_draft",
            {"draft": proposed},
            ToolContext(
                role="requirements",
                workspace_id=workspace_id,
                run_id=None,
                mode=payload["mode"],
                expected_revision=header["revision"],
                contract_hash=source_hash,
                preparation=True,
            ),
            call_id=str(uuid4()),
        )
        validation_receipt = _receipt(
            task,
            "validate_mission_draft",
            {"draft": proposed},
            validation,
            "SUCCEEDED" if validation["valid"] else "FAILED",
            None if validation["valid"] else "MODEL_OUTPUT_INVALID",
            (time.monotonic() - started) * 1000,
        )
        validation_receipts.append(validation_receipt)
        if not validation["valid"]:
            raise PersistenceError("MODEL_OUTPUT_INVALID", "Preparation failed deterministic semantic validation")
        fields = ("name", "objective", "target", "requirements", "assumptions", "forbidden_actions")
        content = {field: proposed[field] for field in fields}
        with runtime.store.publication(workspace_id, job_id, token) as unit:
            current_preparation = unit.require("preparations", preparation_id, lock=True)
            _active(current_preparation)
            current_header = unit.require("missions", header["id"], lock=True)
            missions.check_revision(current_header, payload["expected_revision"])
            if current_header["current_draft_id"] != draft["id"] or current_preparation["source_sha256"] != source_hash:
                raise PersistenceError("REVISION_CONFLICT", "Preparation input changed during generation")
            invocation = unit.require("agent_invocations", str(invocation_id), lock=True)
            if invocation["status"] != "RUNNING" or current_preparation["active_invocation_id"] != str(invocation_id):
                raise PersistenceError("REVISION_CONFLICT", "Preparation invocation was superseded")
            revision = missions.propose(unit, header["id"], content, payload["expected_revision"])
            result = _result(task, "SUCCEEDED", revision, validation_receipt.id, None)
            submission = _receipt(
                task,
                "submit_role_result",
                result.model_dump(mode="json"),
                {"stored_result_id": str(result.id)},
                "SUCCEEDED",
                None,
            )
            sealed = {
                "role_result": result.model_dump(mode="json"),
                "preparation_receipts": [
                    validation_receipt.model_dump(mode="json"),
                    submission.model_dump(mode="json"),
                ],
                "source_sha256": source_hash,
            }
            unit.replace(
                "agent_invocations",
                invocation["id"],
                {
                    **invocation,
                    **sealed,
                    "status": "SUCCEEDED",
                    "output_json": result.model_dump(mode="json"),
                    "sealed_sha256": canonical_sha256(sealed),
                    "usage_json": {"model_dispatches": 1, "completion_confirmed": True},
                },
            )
            current_job = unit.require("jobs", job_id)
            unit.replace(
                "jobs",
                job_id,
                {
                    **current_job,
                    "state": "SUCCEEDED",
                    "proposed_revision_id": revision["id"],
                    "progress_step": "FINGERPRINT_PREPARED",
                },
            )
            unit.replace(
                "preparations",
                preparation_id,
                {
                    **current_preparation,
                    "status": "SUCCEEDED",
                    "proposed_revision_id": revision["id"],
                    "role_result_id": str(result.id),
                    "error": None,
                },
            )
    except (
        ApiError,
        PersistenceError,
        RuntimeError,
        ValueError,
        TypeError,
        OSError,
        httpx.HTTPError,
        OpenAIError,
        ScienceCancelled,
        ScienceDeadlineExceeded,
    ) as error:
        _finish_failure(runtime, job, task, error, validation_receipts)
