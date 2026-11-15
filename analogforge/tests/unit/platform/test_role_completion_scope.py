"""The director's bounded completion does not certify the mission or suppress a real blocker."""

import json
from copy import deepcopy

import pytest

from analogforge.agents.prompts.bundle import prompt_bundle
from analogforge.agents.runtime.openai_provider import _expand_wire_task
from analogforge.application.scheduler import WorkflowRolePaused
from analogforge.tools.allowlist import ALLOWLISTS
from tests.unit.platform.test_role_invocations import role_attempt

__all__ = ["role_attempt"]


def tool_value(output, task):
    """Resolve the exact task references in these two small read results."""
    wire = json.loads(output)
    assert wire["audit_paths"] == [] and not wire.get("table_paths")
    value = wire["value"]
    for reference in wire.get("task_paths", []):
        source = task
        for key in reference["task_path"]:
            source = source[key]
        destination = value
        for key in reference["path"][:-1]:
            destination = destination[key]
        destination[reference["path"][-1]] = deepcopy(source)
    return value


@pytest.mark.parametrize("role", sorted(ALLOWLISTS))
def test_every_role_receives_bounded_completion_and_scientific_gate_policy(role):
    instructions, _digest = prompt_bundle(role)
    assert "`disposition=COMPLETE` means only the assigned bounded `role_key`/`task_kind`" in instructions
    assert "It is not run state `COMPLETED`, scientific `PASS`" in instructions
    assert "its default COMPLETE is neither a scientific verdict nor a required disposition" in instructions
    assert "Never copy a template disposition to hide a blocker" in instructions
    assert "UNKNOWN: insufficient evidence/unresolved comparison/absent coverage/missing information" in instructions
    assert "backend assurance decides statuses/publication" in instructions


@pytest.mark.parametrize("response", ["continue", "review", "blocking"])
def test_actual_director_task_finishes_only_current_review_and_retains_blockers(
    role_attempt, monkeypatch, response,
):
    engine, store, workspace, run_id, _job = role_attempt
    run = store.require("runs", run_id)
    run["state"] = "CHARACTERIZING"
    original_run = deepcopy(run)
    original_science = {kind: deepcopy(store.list(kind)) for kind in ("qualifications", "passports", "evidence")}
    calls = []

    class Client:
        def create(self, **kwargs):
            instructions = kwargs["instructions"]
            assert "`COMPLETE` finishes this bounded director review" in instructions
            assert "Neither claims that the mission is complete" in instructions
            assert (
                "Accepted operator criteria authorize investigation and comparison; they are not validated facts"
            ) in instructions
            assert "Their absence alone does not undo a matching contract acceptance" in instructions
            assert "A failed current prerequisite" in instructions
            assert "The template's COMPLETE is not mandatory" in instructions
            terminal = next(tool for tool in kwargs["tools"] if tool["name"] == "submit_role_result")
            assert terminal["strict"] is True
            assert {"COMPLETE", "NEEDS_USER_REVIEW", "NEEDS_EVIDENCE"} <= set(
                terminal["parameters"]["properties"]["disposition"]["enum"]
            )
            task = _expand_wire_task(json.loads(kwargs["input"][0]["content"])["task"])
            assert task["task_kind"] == "advance_workflow"
            assert task["payload"]["contract_acceptance"]["scientific_validation"] is False
            assert task["payload"]["contract_acceptance"]["requirement_ids"] == [
                row["id"] for row in engine._load(run_id, workspace)[1]["requirements"]
            ]
            calls.append(len(kwargs["input"]))
            if len(calls) == 1:
                name, arguments = "get_run_snapshot", {"sections": ["state"]}
            elif len(calls) == 2:
                snapshot = tool_value(kwargs["input"][-1]["output"], task)["snapshot"]
                assert snapshot["state"] == "CHARACTERIZING"
                name = "inspect_contract"
                arguments = {"contract_revision_id": task["contract_revision_id"]}
            else:
                contract = tool_value(kwargs["input"][-1]["output"], task)
                assert contract["accepted"] is True
                assert contract["acceptance"]["scientific_validation"] is False
                proposal = deepcopy(task["payload"]["prepared_submission"])
                proposal["summary"] = "Current workflow review finished; scientific qualification remains pending."
                proposal["next_action"] = "continue"
                if response != "continue":
                    proposal["issues"] = [{
                        "code": "MISSING_EVIDENCE", "severity": "BLOCKING", "requirement_id": "req-1",
                        "evidence_ids": [], "message": "Evidence needed for the current task is missing.",
                        "recommended_action": "Review the scoped missing input.",
                    }]
                if response == "review":
                    proposal.update(disposition="NEEDS_USER_REVIEW", next_action="request_review")
                name, arguments = "submit_role_result", proposal
            return {"status": "completed", "output": [{
                "type": "function_call", "name": name, "call_id": f"scoped-review-{len(calls)}",
                "arguments": json.dumps(arguments),
            }]}

    monkeypatch.setattr(engine, "_provider_client", Client)
    if response == "continue":
        submission = engine._role("mission_director", "advance_workflow", run_id, workspace)
        assert submission.disposition == "COMPLETE" and submission.next_action == "continue"
    else:
        with pytest.raises(WorkflowRolePaused) as caught:
            engine._role("mission_director", "advance_workflow", run_id, workspace)
        assert caught.value.disposition == "NEEDS_USER_REVIEW"
    assert len(calls) == 3
    assert store.require("runs", run_id) == original_run
    assert {kind: store.list(kind) for kind in original_science} == original_science
    result = store.list("role_results")[0]
    assert result["status"] == ("SUCCEEDED" if response == "continue" else "BLOCKED")
    assert result["proposed_next_state"] is None
    assert result["payload"]["issues"] == ([] if response == "continue" else [{
        "code": "MISSING_EVIDENCE", "severity": "BLOCKING", "requirement_id": "req-1", "evidence_ids": [],
        "message": "Evidence needed for the current task is missing.",
        "recommended_action": "Review the scoped missing input.",
    }])
