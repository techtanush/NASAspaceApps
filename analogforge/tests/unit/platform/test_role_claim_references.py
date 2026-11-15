"""Role annotations reference the same opaque IDs as the authoritative scientific claims."""

from copy import deepcopy
from uuid import uuid4

import pytest

from analogforge.agents.runtime.invocation import validate_submission
from analogforge.agents.runtime.openai_provider import OpenAIProvider
from analogforge.agents.runtime.scripted_provider import project_payload
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.application.scheduler import WorkflowRolePaused
from analogforge.domain.policy import PolicyViolation
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_role_invocations import role_attempt

__all__ = ["role_attempt"]


def objection(claim_id):
    return {
        "finding_id": str(uuid4()), "claim_id": claim_id, "requirement_id": "req-1", "evidence_ids": [],
        "rule_code": "MISSING_EVIDENCE", "severity": "WARNING", "observation": "Review the evidence limitation.",
        "required_repair": {"kind": "RECORD_UNKNOWN", "target_ids": ["req-1"],
                            "success_condition": "Preserve the supported limitation."},
        "resolved_by_receipt_ids": [],
    }


def proposal_for(role, claim_id):
    task, *_ = task_and_context()
    if role == "scientific_critic":
        payload = {"review_revision_id": str(uuid4()), "objections": [objection(claim_id)],
                   "accepted_claim_ids": [claim_id], "gate_recommendation": "CLEAR_WITH_LIMITATIONS"}
        kind = "review_qualification"
    else:
        payload = {
            "passport_draft_revision_id": str(uuid4()), "source_run_revision": 1,
            "selected_candidate_revision_ids": [], "portfolio_revision_id": None,
            "claim_annotations": [{"claim_id": claim_id, "display_text": "Scoped evidence limitation.",
                                   "evidence_ids": [], "assumption_ids": [], "limitation_ids": [],
                                   "claim_kind": "MISSING_EVIDENCE"}],
            "unresolved_issue_ids": [], "not_verified_requirement_ids": ["req-1"],
            "export_artifact_ids": [], "ready_to_publish": False,
        }
        kind = "assemble_passport"
    raw = {**deepcopy(task.payload["prepared_submission"]), "role_key": role, "task_kind": kind, "payload": payload}
    if role == "evidence_passport":
        raw["issues"] = [{"code": "MISSING_EVIDENCE", "severity": "WARNING", "requirement_id": "req-1",
                          "evidence_ids": [], "message": "Review the unresolved claim evidence before publication.",
                          "recommended_action": "Inspect the registered claim lineage."}]
    task = task.model_copy(update={
        "role_key": role, "task_kind": kind,
        "payload": {"authoritative_submission": deepcopy(raw), "authoritative_claims": [{
            "claim_id": claim_id, "claim_type": "CONTEXT", "requirement_id": "req-1",
            "candidate_window_ids": [], "evidence_ids": [],
        }]},
    })
    return task, raw


def test_passport_projection_lists_each_nonpassing_requirement_once_across_candidates_in_first_seen_order():
    qualifications = [
        {"candidate_id": "a", "requirement_id": "pass-only", "status": "PASS"},
        {"candidate_id": "a", "requirement_id": "req-1", "status": "FAIL"},
        {"candidate_id": "b", "requirement_id": "req-1", "status": "PASS"},
        {"candidate_id": "b", "requirement_id": "req-2", "status": "PARTIAL"},
        {"candidate_id": "c", "requirement_id": "req-1", "status": "GAP"},
        {"candidate_id": "c", "requirement_id": "req-3", "status": "UNKNOWN"},
        {"candidate_id": "d", "requirement_id": "req-2", "status": "FAIL"},
        {"candidate_id": "d", "requirement_id": "pass-only", "status": "PASS"},
        {"candidate_id": "e", "requirement_id": "req-4", "status": "GAP"},
        {"candidate_id": "e", "requirement_id": "req-5", "status": "UNKNOWN"},
    ]
    facts = {"mission": {"requirements": []}, "validation_receipt_id": str(uuid4()),
             "run": {"revision": 17}, "qualifications": qualifications,
             "passport": {"id": str(uuid4()), "candidate_ids": ["a", "b", "c", "d", "e"],
                          "portfolio_id": None}}
    original = deepcopy(facts)
    payload = project_payload("evidence_passport", facts)
    assert payload["not_verified_requirement_ids"] == ["req-1", "req-2", "req-3", "req-4", "req-5"]
    assert payload["selected_candidate_revision_ids"] == ["a", "b", "c", "d", "e"]
    assert facts == original


@pytest.mark.parametrize("role", ["scientific_critic", "evidence_passport"])
@pytest.mark.parametrize("claim_id", [f"q:{uuid4()}", f"v:{uuid4()}", f"discovery:{uuid4()}", "uncovered:req-1"])
def test_role_claim_references_preserve_authoritative_namespaced_ids(role, claim_id):
    task, raw = proposal_for(role, claim_id)
    submission = RoleSubmission.model_validate(raw)
    validate_submission(task, submission)
    assert submission.payload == raw["payload"]


@pytest.mark.parametrize("reference", ["objection", "accepted", "annotation"])
def test_role_claim_reference_cannot_invent_or_borrow_an_unissued_id(reference):
    task, raw = proposal_for("evidence_passport" if reference == "annotation" else "scientific_critic",
                             f"q:{uuid4()}")
    foreign = f"q:{uuid4()}"
    if reference == "annotation":
        raw["payload"]["claim_annotations"][0]["claim_id"] = foreign
    elif reference == "objection":
        raw["payload"]["objections"][0]["claim_id"] = foreign
    else:
        raw["payload"]["accepted_claim_ids"] = [foreign]
    with pytest.raises(PolicyViolation, match="CLAIM_REFERENCE_NOT_AUTHORIZED"):
        validate_submission(task, RoleSubmission.model_validate(raw))


def claim_rows(store, run_id):
    candidate_id, qualification_id = str(uuid4()), str(uuid4())
    store.create("candidates", {"id": candidate_id, "run_id": run_id, "window_id": "window-1",
                                "origin": "DISCOVERED", "evidence_ids": []})
    store.create("qualifications", {"id": qualification_id, "run_id": run_id, "candidate_id": candidate_id,
                                    "requirement_id": "req-1", "evidence_ids": []})
    return f"q:{qualification_id}", f"discovery:{candidate_id}"


@pytest.mark.parametrize("role", ["scientific_critic", "evidence_passport"])
def test_review_roles_receive_the_current_authoritative_claim_catalog(role_attempt, monkeypatch, role):
    engine, store, workspace, run_id, _ = role_attempt
    expected = set(claim_rows(store, run_id))
    audit = {"claim_gates": [], "findings": []}

    def propose(_provider, task, *_):
        assert {claim["claim_id"] for claim in task.payload["authoritative_claims"]} == expected
        assert task.payload["scientific_audit"] == audit
        return task.payload["prepared_submission"]

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    extra = {"review_revision_id": str(uuid4()), "objections": [], "scientific_audit": audit}
    if role == "evidence_passport":
        extra.update(passport={"id": str(uuid4()), "candidate_ids": [], "portfolio_id": None}, qualifications=[])
    engine._role(role, "review_qualification" if role == "scientific_critic" else "assemble_passport",
                 run_id, workspace, extra)


@pytest.mark.parametrize("has_objection", [True, False], ids=["supported-objection", "repair-request"])
def test_complete_critic_concern_is_retained_and_routed_to_review(role_attempt, monkeypatch, has_objection):
    engine, store, workspace, run_id, _ = role_attempt
    claim_id, _ = claim_rows(store, run_id)

    def propose(_provider, task, *_):
        raw = deepcopy(task.payload["prepared_submission"])
        raw["payload"]["objections"] = [objection(claim_id)] if has_objection else []
        raw["payload"]["gate_recommendation"] = "CLEAR_WITH_LIMITATIONS" if has_objection else "REPAIR_REQUIRED"
        return raw

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    with pytest.raises(WorkflowRolePaused) as caught:
        engine._critic(run_id, workspace, {"requirements": [{"id": "req-1"}]}, {"findings": []})
    assert caught.value.disposition == "NEEDS_USER_REVIEW"
    saved = store.list("role_results")
    assert len(saved) == 1 and saved[0]["payload"]["payload"]["gate_recommendation"] in {
        "CLEAR_WITH_LIMITATIONS", "REPAIR_REQUIRED",
    }
    assert store.list("critiques") == [] and store.list("passports") == []


def test_scripted_critic_without_new_objections_keeps_existing_workflow(role_attempt):
    engine, store, workspace, run_id, _ = role_attempt
    claim_rows(store, run_id)
    store.require("runs", run_id)["mode"] = "synthetic"
    assert engine._critic(run_id, workspace, {"requirements": [{"id": "req-1"}]}, {"findings": []}) is False
    assert store.list("role_results")[0]["payload"]["payload"]["objections"] == []


@pytest.mark.parametrize("severity", ["BLOCKING", "WARNING"])
def test_common_blocking_issue_requires_review_without_converting_it_to_scientific_fact(
    role_attempt, monkeypatch, severity
):
    engine, store, workspace, run_id, _ = role_attempt

    def propose(_provider, task, *_):
        raw = deepcopy(task.payload["prepared_submission"])
        raw["issues"] = [{"code": "ROLE_CONCERN", "severity": severity, "requirement_id": "req-1",
                          "evidence_ids": [], "message": "Review the scoped concern.", "recommended_action": "review"}]
        return raw

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    if severity == "BLOCKING":
        with pytest.raises(WorkflowRolePaused) as caught:
            engine._role("mission_director", "advance_workflow", run_id, workspace)
        assert caught.value.disposition == "NEEDS_USER_REVIEW"
    else:
        assert engine._role("mission_director", "advance_workflow", run_id, workspace).disposition == "COMPLETE"
    assert store.list("role_results")[0]["status"] == ("BLOCKED" if severity == "BLOCKING" else "SUCCEEDED")
    invocation = next(row for row in store.list("invocations") if row["task_kind"] == "advance_workflow")
    assert invocation["status"] == "SUCCEEDED" and store.list("critiques") == []
