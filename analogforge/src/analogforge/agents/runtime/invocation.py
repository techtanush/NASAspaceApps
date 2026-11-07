"""Validate role/task identity before policy evaluates any terminal proposal."""

from importlib import import_module

from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask


def validate_task(task: AgentTask) -> None:
    module = import_module("analogforge.agents.roles." + task.role_key)
    if task.task_kind not in module.TASK_KINDS:
        raise ValueError("Unlisted task kind")


def validate_submission(task: AgentTask, submission: RoleSubmission) -> None:
    validate_task(task)
    submission.validate_payload()
    validate_authoritative_payload(task, submission)
    if submission.role_key != task.role_key or submission.task_kind != task.task_kind:
        raise ValueError("Submission identity mismatch")
    if submission.next_action is not None and submission.next_action not in task.allowed_actions:
        raise ValueError("Unlisted action")


def _nested_references(value: object, field: str = "") -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            references.extend(_nested_references(item, str(key)))
    elif isinstance(value, list):
        if "evidence_id" in field or "receipt_id" in field:
            references.extend((field, str(item)) for item in value)
        else:
            for item in value:
                references.extend(_nested_references(item, field))
    elif value is not None and ("evidence_id" in field or "receipt_id" in field):
        references.append((field, str(value)))
    return references


def validate_authoritative_payload(task: AgentTask, submission: RoleSubmission) -> None:
    """Validate nested facts as well as the common envelope; source prose has no authority."""
    from analogforge.domain.confidence import bounded_confidence
    from analogforge.domain.policy import PolicyViolation

    evidence = {str(identifier) for identifier in task.input_evidence_ids}
    receipt_ids = {str(r["id"]) for r in task.payload.get("receipt_summaries", []) if r["status"] == "SUCCEEDED"}
    expected = task.payload.get("authoritative_submission", task.payload.get("prepared_submission", {})).get(
        "payload", {}
    )
    receipt_ids.update(identifier for field, identifier in _nested_references(expected) if "receipt_id" in field)
    for field, identifier in _nested_references(submission.payload):
        allowed = receipt_ids if "receipt_id" in field else evidence
        if identifier not in allowed:
            raise PolicyViolation("NESTED_REFERENCE_NOT_AUTHORIZED")
    payload = submission.payload
    for field, authoritative in (
        ("contract_revision_id", str(task.contract_revision_id)),
        ("contract_hash", task.contract_hash),
        ("rover_revision_id", str(task.rover_revision_id) if task.rover_revision_id else None),
    ):
        if field in payload and str(payload[field]) != str(authoritative):
            raise PolicyViolation("FROZEN_ROLE_INPUT_CHANGED")
    if task.role_key == "requirements" and (payload.get("new_contract_required") or not payload.get("unchanged")):
        if submission.disposition == "COMPLETE":
            raise PolicyViolation("CONTRACT_CHANGE_REQUIRES_REVIEW")
    if task.role_key == "rover_systems":
        rover = task.payload.get("authoritative_rover", {})
        for limit in payload["hard_limit_summary"]:
            if limit["field_path"] not in rover or limit["value"] != rover[limit["field_path"]]:
                raise PolicyViolation("ROVER_LIMIT_SUMMARY_CHANGED")
    if task.role_key == "qualification":
        computed_rows = {row["requirement_id"]: row for row in expected.get("rows", [])}
        if set(computed_rows) != {row["requirement_id"] for row in payload["rows"]}:
            raise PolicyViolation("QUALIFICATION_SCOPE_CHANGED")
        if payload["candidate_revision_id"] != expected.get("candidate_revision_id"):
            raise PolicyViolation("CANDIDATE_REVISION_CHANGED")
        for row in payload["rows"]:
            computed = computed_rows[row["requirement_id"]]
            if row["proposed_status"] != computed["proposed_status"]:
                raise PolicyViolation("STATUS_INFLATION")
            try:
                bounded_confidence(row["confidence"], computed["confidence"])
            except ValueError as exc:
                raise PolicyViolation("CONFIDENCE_INFLATION") from exc
            if not set(row["evidence_ids"]) <= set(computed["evidence_ids"]):
                raise PolicyViolation("COMPARISON_CITATION_CHANGED")
            if row["proposed_status"] in {"PASS", "PARTIAL", "FAIL"} and not row["evidence_ids"]:
                raise PolicyViolation("COMPARISON_CITATION_MISSING")
        for key in ("qualified_use_requirement_ids", "partial_use_requirement_ids", "unsupported_use_requirement_ids"):
            if set(payload[key]) != set(expected.get(key, [])):
                raise PolicyViolation("QUALIFIED_USE_CHANGED")
    choices = task.payload.get("allowed_choices", {})
    if task.role_key == "test_designer" and choices:
        if payload["candidate_revision_id"] not in choices.get("candidate_revision_ids", []):
            raise PolicyViolation("CANDIDATE_CHOICE_NOT_PERMITTED")
        if payload["strategy"] not in choices.get("strategies", []):
            raise PolicyViolation("STRATEGY_CHOICE_NOT_PERMITTED")
    # Revision pointers/verification verdicts remain fixed; explicitly issued operational choices vary.
    for key, value in payload.items():
        if key in expected and (
            key.endswith("_revision_id")
            or key in {"outcome", "primary_failure_category", "strategy", "screened_region_count"}
        ):
            if task.role_key == "test_designer" and choices and key in {"candidate_revision_id", "strategy"}:
                continue
            if value != expected[key]:
                raise PolicyViolation("AUTHORITATIVE_ROLE_FACT_CHANGED")
    if task.role_key == "verification_replanning" and payload.get("repair"):
        repair = payload["repair"]
        permitted = task.payload.get("permitted_repairs", [])
        if repair["kind"] not in permitted or repair["preserved_contract_sha256"] != task.contract_hash:
            raise PolicyViolation("REPAIR_NOT_PERMITTED")
        if choices:
            if repair["kind"] not in choices.get("repair_kinds", []):
                raise PolicyViolation("REPAIR_CHOICE_NOT_PERMITTED")
            targets = choices.get("repair_target_revision_ids", {}).get(repair["kind"], [])
            selected = repair["target_revision_ids"]
            if not selected or any(target not in targets for target in selected) or len(selected) != len(set(selected)):
                raise PolicyViolation("REPAIR_TARGET_CHOICE_NOT_PERMITTED")
            if repair["kind"] == "NEW_CANDIDATE" and len(selected) != 1:
                raise PolicyViolation("REPAIR_TARGET_CHOICE_NOT_PERMITTED")
            if repair["strategy"] is not None and repair["strategy"] not in choices.get("strategies", []):
                raise PolicyViolation("STRATEGY_CHOICE_NOT_PERMITTED")
