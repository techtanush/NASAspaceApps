"""The scripted council shares strict policy with live proposals."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from analogforge.agents.runtime.invocation import validate_submission
from analogforge.agents.runtime.scripted_provider import ScriptedProvider
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.domain.policy import PolicyViolation
from tests.integration.platform.test_live_rehearsal import task_and_context


def test_scripted_submission_uses_existing_receipts_only():
    task, context, registry, _, _ = task_and_context()
    task = task.model_copy(update={"runtime_mode": "synthetic"})
    result = ScriptedProvider().run(task, registry, context)
    validate_submission(task, result)
    forged = result.model_copy(update={"evidence_ids": [uuid4()]})
    with pytest.raises(Exception, match="evidence absent"):
        ScriptedProvider().run(
            task.model_copy(update={"payload": {"prepared_submission": forged.model_dump(mode="json")}}),
            registry,
            context,
        )


def test_nested_qualification_evidence_and_inflation_rejected():
    task, _, _, _, _ = task_and_context()
    cid, qid, receipt, eid = [str(uuid4()) for _ in range(4)]
    row = {
        "requirement_id": "R-EXPOSURE",
        "comparison_receipt_id": receipt,
        "proposed_status": "UNKNOWN",
        "evidence_ids": [eid],
        "measurement_evidence_ids": [eid],
        "basis": "MISSING_EVIDENCE",
        "confidence": "LOW",
        "covered_subcriterion_ids": [],
        "uncovered_subcriterion_ids": [],
        "limitations": ["No verified route"],
    }
    payload = {
        "candidate_revision_id": cid,
        "qualification_draft_revision_id": qid,
        "rows": [row],
        "qualified_use_requirement_ids": [],
        "partial_use_requirement_ids": [],
        "unsupported_use_requirement_ids": ["R-EXPOSURE"],
        "portfolio_revision_id": None,
        "critic_review_required": True,
    }
    base = {
        "schema_version": "1.0",
        "role_key": "qualification",
        "task_kind": "qualify_candidate",
        "disposition": "COMPLETE",
        "summary": "test",
        "evidence_ids": [],
        "assumption_ids": [],
        "issues": [],
        "next_action": None,
        "payload": payload,
    }
    task = task.model_copy(
        update={
            "role_key": "qualification",
            "task_kind": "qualify_candidate",
            "input_evidence_ids": [UUID(eid)],
            "payload": {"prepared_submission": base, "receipt_summaries": [{"id": receipt, "status": "SUCCEEDED"}]},
        }
    )
    validate_submission(task, RoleSubmission.model_validate(base))
    for kind in ("fabricated", "pass", "confidence"):
        submission = deepcopy(base)
        changed = submission["payload"]["rows"][0]
        if kind == "fabricated":
            changed["evidence_ids"] = [str(uuid4())]
        elif kind == "pass":
            changed["proposed_status"] = "PASS"
        else:
            changed["confidence"] = "HIGH"
        with pytest.raises(PolicyViolation):
            validate_submission(task, RoleSubmission.model_validate(submission))


def test_requirements_changed_contract_and_rover_limits_are_rejected():
    task, _, _, _, _ = task_and_context()
    receipt = str(uuid4())
    common = task.payload["prepared_submission"]
    requirements = {
        "contract_revision_id": str(task.contract_revision_id),
        "contract_hash": "b" * 64,
        "requirement_ids": [],
        "validation_receipt_id": receipt,
        "unchanged": True,
        "consistency_issues": [],
        "new_contract_required": False,
    }
    submission = RoleSubmission.model_validate(
        {**common, "role_key": "requirements", "task_kind": "validate_accepted_contract", "payload": requirements}
    )
    task = task.model_copy(
        update={
            "role_key": "requirements",
            "task_kind": "validate_accepted_contract",
            "payload": {
                "prepared_submission": submission.model_dump(mode="json"),
                "receipt_summaries": [{"id": receipt, "status": "SUCCEEDED"}],
            },
        }
    )
    with pytest.raises(PolicyViolation, match="FROZEN"):
        validate_submission(task, submission)


@pytest.mark.parametrize("mutation", ["repair_kind", "foreign_target", "strategy", "verdict"])
def test_repair_choices_are_bounded_by_server_issued_options(mutation):
    task, _, _, _, _ = task_and_context()
    test_id, result_id, candidate_id = [str(uuid4()) for _ in range(3)]
    payload = {
        "test_revision_id": test_id,
        "result_revision_id": result_id,
        "search_attempt_id": None,
        "outcome": "FAIL",
        "primary_failure_category": "ROUTE",
        "secondary_failure_categories": [],
        "violated_constraint_ids": [],
        "diagnosis_receipt_id": None,
        "repair": {
            "kind": "NEW_CANDIDATE",
            "target_revision_ids": [candidate_id],
            "addresses_constraint_ids": [],
            "preserved_contract_sha256": task.contract_hash,
            "strategy": "MINIMUM_FEASIBLE_ROUTE",
            "expected_check": "Independent verification",
            "requires_new_run": False,
        },
        "stop_reason": None,
    }
    baseline = {
        **task.payload["prepared_submission"],
        "role_key": "verification_replanning",
        "task_kind": "diagnose_failed_attempt",
        "payload": payload,
    }
    task = task.model_copy(
        update={
            "role_key": "verification_replanning",
            "task_kind": "diagnose_failed_attempt",
            "payload": {
                "authoritative_submission": deepcopy(baseline),
                "permitted_repairs": ["NEW_ROUTE", "NEW_CANDIDATE"],
                "allowed_choices": {
                    "repair_kinds": ["NEW_CANDIDATE"],
                    "repair_target_revision_ids": {"NEW_CANDIDATE": [candidate_id]},
                    "strategies": ["MINIMUM_FEASIBLE_ROUTE"],
                },
            },
        }
    )
    validate_submission(task, RoleSubmission.model_validate(baseline))
    changed = deepcopy(baseline)
    repair = changed["payload"]["repair"]
    if mutation == "repair_kind":
        repair["kind"] = "NEW_ROUTE"
    elif mutation == "foreign_target":
        repair["target_revision_ids"] = [str(uuid4())]
    elif mutation == "strategy":
        repair["strategy"] = "RECOVERY_ALTERNATIVE"
    else:
        changed["payload"]["outcome"] = "PASS"
    with pytest.raises(PolicyViolation):
        validate_submission(task, RoleSubmission.model_validate(changed))
