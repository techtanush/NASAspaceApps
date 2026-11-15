"""Read-only human activity derived from committed events, never provider reasoning.

Each transition keeps its event sequence and timestamp. Reloading or paging does not
invent work, collapse history, or turn computation completion into scientific success.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, cast
from uuid import UUID

from analogforge.agents.runtime.sanitize import sanitize
from analogforge.api.errors import ApiError
from analogforge.ports import catalog

OPERATIONS = {
    "RESOLVE_COVERAGE": "Check approved source coverage",
    "FETCH_SOURCE": "Fetch approved source data",
    "INGEST_LOCAL_DATASET": "Validate local dataset inputs",
    "CHARACTERIZE_TARGET": "Measure planetary target",
    "SCREEN_CANDIDATES": "Screen Earth sites against accepted requirements",
    "ANALYZE_CANDIDATE": "Analyze candidate terrain",
    "COMPARE_REQUIREMENT": "Compare accepted requirement",
    "ASSESS_COMPATIBILITY": "Check rover compatibility",
    "DESIGN_BENCHMARK": "Design route benchmark",
    "SEARCH_ROUTE": "Search routes within frozen constraints",
    "VERIFY_ROUTE": "Independently verify proposed route",
    "DIAGNOSE_RESULT": "Diagnose recorded verification result",
    "OPTIMIZE_PORTFOLIO": "Build requirement coverage portfolio",
    "BUILD_DISPLAY_LAYERS": "Prepare evidence display layers",
    "AUDIT_EVIDENCE": "Audit evidence and publication claims",
}
STAGES = {
    "DRAFT": "Investigation created",
    "VALIDATING": "Validate accepted mission inputs",
    "CHARACTERIZING": "Characterize planetary target",
    "DISCOVERING": "Investigate Earth analog candidates",
    "QUALIFYING": "Compare candidates with accepted requirements",
    "CRITIQUING": "Review evidence and scientific limitations",
    "AWAITING_REVIEW": "Awaiting operator review or verification request",
    "DESIGNING_TEST": "Design a benchmark within accepted constraints",
    "VERIFYING": "Verify proposed route",
    "DIAGNOSING": "Diagnose recorded verification findings",
    "REPLANNING": "Evaluate permitted investigation repairs",
    "BUILDING_PASSPORT": "Assemble audited investigation report",
    "COMPLETED": "Investigation and report completed",
    "BLOCKED": "Investigation blocked; intervention required",
    "FAILED": "Investigation stopped after an execution failure",
    "CANCELLED": "Investigation cancelled",
}
TASKS = {
    "advance_workflow": "Review the next permitted investigation step",
    "validate_accepted_contract": "Review accepted mission requirements",
    "validate_profile": "Review saved rover capabilities",
    "characterize_target": "Review planetary target evidence",
    "inspect_contract": "Inspect accepted mission contract",
    "screen_candidates": "Review investigated Earth candidate evidence",
    "qualify_candidate": "Review candidate requirement comparisons",
    "revise_qualification": "Review a corrected requirement comparison",
    "design_benchmark": "Review benchmark design against accepted constraints",
    "design_replan": "Review a permitted benchmark repair",
    "verify_proposed_route": "Review the independent route verification",
    "diagnose_failed_attempt": "Review a recorded failed attempt and permitted repairs",
    "assemble_passport": "Review report evidence and publication limits",
    "review_qualification": "Challenge requirement evidence and unsupported claims",
}
FAILURE_SUMMARIES = {
    "MODEL_OUTPUT_INVALID": (
        "The model response failed required format or evidence checks; no invalid proposal was accepted."
    ),
    "PROVIDER_RATE_LIMITED": "The model provider's request or token rate limit was reached.",
    "PROVIDER_AUTH_FAILED": "The configured model provider credentials were not accepted.",
    "NO_COVERAGE": "The approved sources do not cover the required area or measurement.",
    "RESOURCE_LIMIT": "A request or operation exceeded the available size or resource budget.",
    "BUDGET_EXHAUSTED": "The investigation reached a configured execution budget.",
    "TOOL_TIMEOUT": "A required operation or provider request did not finish within its deadline.",
    "SOURCE_UNAVAILABLE": "A required source or external service was unavailable.",
    "SOURCE_CHECKSUM_MISMATCH": "Source bytes did not match their recorded checksum.",
    "SOURCE_CONTENT_INVALID": "Required source or stored evidence content failed validation.",
    "DATASETS_UNBOUND": "The selected scenario has no complete approved dataset binding.",
    "SCIENCE_FACADE_MISSING": "The configured scientific service was unavailable.",
    "RENDERER_MISSING": "The configured report renderer was unavailable.",
    "REVISION_CONFLICT": "The operation no longer matched the required input revision.",
    "INPUT_INVALID": "The operation's inputs did not pass the required validation.",
    "SCIENTIFIC_CLAIM_REJECTED": "A scientific claim did not pass its required evidence checks.",
    "USER_REVIEW_REQUIRED": "Operator review is required before the investigation can continue.",
    "ROLE_INVESTIGATION_BLOCKED": "A role recorded a blocker that requires intervention.",
    "SYSTEM": "An internal execution error prevented this operation from completing.",
}
FAILURE_EVENTS = {
    "run.failed", "run.blocked", "run.state_changed", "job.failed",
    "agent.completed", "tool.completed", "agent.proposal_rejected", "tool.rejected",
}


def failure_code(event_type: str, status: str, payload: dict[str, Any]) -> str | None:
    """Publish only known terminal event codes, never free text or inferred causes."""
    code = payload.get("code")
    if (
        event_type in FAILURE_EVENTS and status in {"FAILED", "BLOCKED"}
        and isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", code)
        and code in FAILURE_SUMMARIES
    ):
        return code
    return None


def safe_label(value: Any, fallback: str, *, limit: int = 160) -> str:
    """A bounded public record label, with credentials/URLs and controls removed."""
    if not isinstance(value, str):
        return fallback
    value = str(sanitize(value))
    value = re.sub(r"https?://\S+", "[link omitted]", value)
    value = re.sub(r"(?i)(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+", "[REDACTED]", value)
    value = " ".join("".join(c for c in value if c.isprintable()).split())
    return value[:limit] or fallback


def encode_cursor(workspace_id: str, run_id: str, seq: int) -> str:
    value = {"v": 1, "workspace": workspace_id, "run": run_id, "after": seq}
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str | None, workspace_id: str, run_id: str) -> int:
    if cursor is None:
        return 0
    try:
        if len(cursor) > 512:
            raise ValueError("cursor size")
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if (
            not isinstance(value, dict)
            or value.get("v") != 1
            or value.get("workspace") != workspace_id
            or value.get("run") != run_id
            or type(value.get("after")) is not int
            or not 0 <= value["after"] < 2**63
        ):
            raise ValueError("cursor scope or position")
        return cast(int, value["after"])
    except (ValueError, TypeError, binascii.Error, RecursionError) as exc:
        raise ApiError("INPUT_INVALID", "The activity cursor is invalid for this run.") from exc


def _uuid(value: Any) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


class ActivityProjection:
    def __init__(self, unit: Any, run: dict[str, Any]) -> None:
        self.unit, self.run = unit, run
        self.cache: dict[tuple[str, str], dict[str, Any] | None] = {}
        mission = unit.get("mission_revisions", run["mission_revision_id"]) or {}
        self.mission_name = safe_label(mission.get("name"), "accepted mission")
        self.requirements = {r["id"]: r for r in mission.get("requirements", []) if isinstance(r, dict) and "id" in r}

    def scoped(self, kind: str, identifier: Any) -> dict[str, Any] | None:
        identifier = _uuid(identifier)
        if identifier is None:
            return None
        key = kind, identifier
        if key not in self.cache:
            row = self.unit.get(kind, identifier)
            self.cache[key] = row if row and row.get("run_id") == self.run["id"] else None
        return self.cache[key]

    def review_concerns(self, result: dict[str, Any], status: str) -> list[dict[str, Any]]:
        """Admitted review concerns are operator-facing statements, never provider reasoning or verdicts."""
        if status != "BLOCKED" or result.get("status") != "BLOCKED":
            return []
        submission = result.get("payload")
        issues = submission.get("issues") if isinstance(submission, dict) else None
        if not isinstance(issues, list):
            return []
        concerns = []
        for issue in issues:
            if not isinstance(issue, dict) or not isinstance(issue.get("severity"), str):
                continue
            if issue["severity"] not in {"WARNING", "BLOCKING"}:
                continue
            message = issue.get("message")
            if not isinstance(message, str) or not message.strip():
                continue
            identifier = issue.get("requirement_id")
            requirement = self.requirements.get(identifier, {}) if isinstance(identifier, str) else {}
            public_message = safe_label(message, "Review concern unavailable", limit=801)
            concerns.append({
                "message": public_message[:800], "message_truncated": len(public_message) > 800,
                "severity": issue["severity"],
                "requirement_label": safe_label(requirement.get("label"), str(identifier)) if requirement else None,
            })
            if len(concerns) == 8:
                break
        return concerns

    def event(self, event: dict[str, Any]) -> dict[str, Any]:
        raw_payload = event.get("payload")
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        event_type = event["event_type"]
        raw_state = event.get("state")
        state = raw_state if isinstance(raw_state, str) and raw_state in STAGES else "UNKNOWN"
        receipt = self.scoped("tool_receipts", payload.get("receipt_id")) or {}
        invocation = self.scoped("invocations", payload.get("invocation_id") or receipt.get("invocation_id")) or {}
        operation = payload.get("operation") or payload.get("task_kind") or invocation.get("task_kind")
        operation = operation if isinstance(operation, str) else ""
        task_kind = operation if operation in OPERATIONS or operation in TASKS else None
        role = payload.get("role") or invocation.get("role")
        role = role if isinstance(role, str) else None
        role = role if role in catalog.ROLE_DISPLAY_NAMES or role == "scientific_worker" else None
        role_result = self.scoped("role_results", payload.get("role_result_id")) or {}
        if role_result and (
            role_result.get("invocation_id") != invocation.get("id")
            or role_result.get("role") != role or role_result.get("mode") != self.run["mode"]
        ):
            role_result = {}
        candidate = self.scoped("candidates", payload.get("candidate_id") or invocation.get("candidate_id")) or {}
        requirement_id = payload.get("requirement_id") or invocation.get("requirement_id")
        requirement_id = (
            requirement_id if isinstance(requirement_id, str) and requirement_id in self.requirements else None
        )
        candidate_name = safe_label(candidate.get("name"), "candidate") if candidate else None
        label = OPERATIONS.get(operation, TASKS.get(operation, "Review committed investigation evidence"))
        if requirement_id:
            requirement_label = self.requirements[requirement_id].get("label", requirement_id)
            label += f": {safe_label(requirement_label, 'accepted requirement')}"
        if candidate_name:
            label += f" at {candidate_name}"
        elif operation in {
            "CHARACTERIZE_TARGET",
            "SCREEN_CANDIDATES",
            "validate_accepted_contract",
            "advance_workflow",
        }:
            label += f" for {self.mission_name}"
        if role and role != "scientific_worker":
            label = f"{catalog.ROLE_DISPLAY_NAMES[role]}: {label}"

        status = "INFO"
        if event_type in {"agent.started", "tool.started"}:
            status, summary = "RUNNING", f"Started: {label}"
        elif event_type in {"agent.completed", "tool.completed"}:
            result_status = payload.get("status", receipt.get("status", "SUCCEEDED"))
            result_status = result_status if isinstance(result_status, str) else "FAILED"
            status = {"BLOCKED": "BLOCKED", "FAILED": "FAILED", "CANCELLED": "CANCELLED"}.get(
                result_status, "COMPLETED"
            )
            prefix = "Completed with limited evidence" if result_status == "LIMITED" else status.capitalize()
            summary = f"{prefix}: {label}"
        elif event_type in {"tool.rejected", "agent.proposal_rejected"}:
            status, summary = "FAILED", f"Publication rejected before scientific results were accepted: {label}"
        elif event_type == "run.state_changed":
            summary = f"{STAGES.get(state, 'Investigation state updated')} — {self.mission_name}"
            status = {"COMPLETED": "COMPLETED", "BLOCKED": "BLOCKED", "FAILED": "FAILED", "CANCELLED": "CANCELLED"}.get(
                state, "INFO"
            )
        elif event_type in {"run.blocked", "run.failed", "run.cancelled", "job.failed"}:
            status = (
                "BLOCKED" if event_type == "run.blocked" else "CANCELLED" if event_type == "run.cancelled" else "FAILED"
            )
            summary = {
                "BLOCKED": "Investigation blocked; intervention required",
                "FAILED": "Execution failed; completed evidence retained",
                "CANCELLED": "Investigation cancelled; completed evidence retained",
            }[status]
            if event_type == "job.failed":
                summary = "A background job failed; the recorded investigation outcome is unchanged"
        else:
            summary = {
                "evidence.created": "Evidence committed to the investigation",
                "qualification.updated": "Requirement comparison committed",
                "critic.issue_created": "Scientific evidence concern recorded",
                "critic.issue_opened": "Scientific evidence concern opened",
                "critic.issue_resolved": "Scientific evidence concern resolved",
                "review.required": "Operator review requested",
                "test.designed": "Benchmark design committed",
                "verification.completed": "Independent verification result committed",
                "replan.started": "Permitted investigation repair started",
                "passport.created": "Audited investigation report committed",
                "run.action": "Operator action recorded",
            }.get(event_type, "Investigation update committed")
        code = failure_code(event_type, status, payload)
        if code is not None:
            summary = f"{summary.rstrip('. ')}. {FAILURE_SUMMARIES[code]}"
        # Only authorized references cross this read boundary. Raw payloads/summaries are intentionally never copied.
        evidence = role_result.get("evidence_ids", []) if role_result else event.get("evidence_ids", [])
        evidence_ids = list(dict.fromkeys(
            [row["id"] for eid in evidence if (row := self.scoped("evidence", eid))]
            if isinstance(evidence, list)
            else []
        ))
        return {
            "id": f"{self.run['id']}:{event['seq']}",
            "run_id": self.run["id"],
            "seq": event["seq"],
            "event_type": event_type if re.fullmatch(r"[a-z_.]{1,64}", event_type) else "activity.updated",
            "created_at": event["created_at"],
            "state": state,
            "status": status,
            "summary": summary,
            "failure_code": code,
            "task_kind": task_kind,
            "role": role,
            "candidate_id": candidate.get("id"),
            "candidate_name": candidate_name,
            "requirement_id": safe_label(requirement_id, "accepted requirement") if requirement_id else None,
            "invocation_id": invocation.get("id"),
            "tool_receipt_id": receipt.get("id"),
            "role_result_id": role_result.get("id"),
            "review_concerns": self.review_concerns(role_result, status),
            "evidence_count": len(evidence_ids),
            "evidence_ids_truncated": len(evidence_ids) > 128,
            "evidence_ids": evidence_ids[:128],
        }


def page(store: Any, workspace_id: str, run_id: str, *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
    after = decode_cursor(cursor, workspace_id, run_id)
    if not 1 <= limit <= 100:
        raise ApiError("INPUT_INVALID", "Activity page size must be between 1 and 100.")
    with store.transaction(workspace_id) as unit:
        run = unit.require("runs", run_id, exclude=("runtime", "audit_payload"))
        if after > run.get("last_event_seq", 0):
            raise ApiError("INPUT_INVALID", "The activity cursor is ahead of this run.")
        # READ COMMITTED may see a newer event after reading the run. Freeze this
        # page at the observed watermark so item sequences never exceed it.
        events = unit.activity_events(run_id, after=after, limit=limit + 1, through=run.get("last_event_seq", 0))
        projection = ActivityProjection(unit, run)
        items = [projection.event(event) for event in events[:limit]]
        return {
            "items": items,
            "next_cursor": encode_cursor(workspace_id, run_id, items[-1]["seq"]) if len(events) > limit else None,
            "last_event_seq": run.get("last_event_seq", 0),
        }
