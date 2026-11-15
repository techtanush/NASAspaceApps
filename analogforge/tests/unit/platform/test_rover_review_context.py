"""A saved declaration needs its actual scoped validator receipt, not a contract-inspection alias."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider
from analogforge.agents.runtime.rover_projection import profile_validation_report
from analogforge.application.scheduler import WorkflowError
from analogforge.domain.policy import PolicyViolation
from analogforge.ports.hashing import canonical_sha256
from tests.unit.platform.test_role_invocations import role_attempt

__all__ = ["role_attempt"]


def attach_rover(role_attempt, monkeypatch, *, energy=True):
    engine, store, workspace, run_id, _ = role_attempt
    content = json.loads((Path(__file__).resolve().parents[2] / "fixtures/kit/rovers/ares-1.json").read_text())
    if not energy:
        content["energy_model"] = None
    rover = {**content, "schema_version": "1.0", "id": str(uuid4()), "rover_id": str(uuid4()),
             "workspace_id": workspace, "revision": 1, "created_at": "2026-11-15T00:00:00Z",
             "content_sha256": canonical_sha256(content)}
    run = store.require("runs", run_id)
    run["rover_revision_id"] = rover["id"]
    run["runtime"]["rover_content_sha256"] = rover["content_sha256"]
    previous_load = engine._load

    def load(*args):
        current, mission, _ = previous_load(*args)
        return current, mission, deepcopy(rover)

    monkeypatch.setattr(engine, "_load", load)
    return engine, store, workspace, run_id, rover


def test_rover_role_gets_actual_validation_and_unknowns_without_requiring_a_future_route(role_attempt, monkeypatch):
    engine, store, workspace, run_id, rover = attach_rover(role_attempt, monkeypatch)
    captured = []

    def review(_provider, task, registry, context):
        validation = task.payload["rover_validation_context"]
        report = validation["report"]
        assert report["valid"] is True and report["physical_performance_validated"] is False
        assert report["energy_calibration_status"] == "ASSUMED"
        assert report["unknown_optional_limits"] == ["max_obstacle_height_m", "max_route_m"]
        assert report["profile_content_sha256"] == rover["content_sha256"]
        result = registry.execute("validate_rover_profile", {"profile_revision_id": rover["id"]},
                                  context, call_id="validate-saved-profile")
        assert result == {"validation_receipt_id": validation["receipt_id"], "report": report}
        result["report"]["valid"] = False
        assert report["valid"] is True  # Returned tool data cannot mutate the retained validator report.
        with pytest.raises(PolicyViolation):
            registry.execute("validate_rover_profile", {"profile_revision_id": str(uuid4())},
                             context, call_id="foreign-profile")
        proposed = task.payload["prepared_submission"]
        assert proposed["payload"]["validation_receipt_id"] == validation["receipt_id"]
        assert proposed["payload"]["capability_mapping"][0]["support"] == "UNKNOWN"
        assert proposed["payload"]["compatibility_revision_id"] is None
        captured.append(task)
        return proposed

    monkeypatch.setattr(OpenAIProvider, "run", review)
    engine._role("rover_systems", "validate_profile", run_id, workspace)
    assert len(captured) == 1
    receipt = next(row for row in store.list("tool_receipts") if row["tool_name"] == "validate_rover_profile")
    invocation = store.require("invocations", receipt["invocation_id"])
    assert receipt["status"] == "SUCCEEDED" and receipt["workspace_id"] == workspace
    assert receipt["input_sha256"] == canonical_sha256(rover)
    assert receipt["output_sha256"] == canonical_sha256(invocation["validation_report"])


def test_contract_inspection_cannot_be_used_as_the_rover_validation_receipt(role_attempt, monkeypatch):
    engine, _, workspace, run_id, _ = attach_rover(role_attempt, monkeypatch)

    def wrong_receipt(_provider, task, *_args):
        result = deepcopy(task.payload["prepared_submission"])
        result["payload"]["validation_receipt_id"] = next(
            row["id"] for row in task.payload["receipt_summaries"] if row["tool_name"] == "inspect_contract"
        )
        return result

    monkeypatch.setattr(OpenAIProvider, "run", wrong_receipt)
    with pytest.raises(PolicyViolation) as caught:
        engine._role("rover_systems", "validate_profile", run_id, workspace)
    assert caught.value.detail_code == "ROVER_VALIDATION_RECEIPT_REQUIRED"


@pytest.mark.parametrize("field,value", [("id", "foreign"), ("workspace_id", "foreign"),
                                        ("content_sha256", "b" * 64)])
def test_changed_or_foreign_saved_profile_never_reaches_the_provider(role_attempt, monkeypatch, field, value):
    engine, store, workspace, run_id, rover = attach_rover(role_attempt, monkeypatch)
    rover[field] = value
    monkeypatch.setattr(OpenAIProvider, "run", lambda *_: pytest.fail("Foreign profile reached the model"))
    with pytest.raises(WorkflowError) as caught:
        engine._role("rover_systems", "validate_profile", run_id, workspace)
    assert caught.value.code == "REVISION_CONFLICT" and not store.list("tool_receipts")


def test_invalid_profile_records_a_failed_validator_receipt_without_model_admission(role_attempt, monkeypatch):
    engine, store, workspace, run_id, rover = attach_rover(role_attempt, monkeypatch)
    rover["mass_kg"] = -1
    monkeypatch.setattr(OpenAIProvider, "run", lambda *_: pytest.fail("Invalid profile reached the model"))
    with pytest.raises(WorkflowError) as caught:
        engine._role("rover_systems", "validate_profile", run_id, workspace)
    assert caught.value.code == "INPUT_INVALID"
    receipt = next(row for row in store.list("tool_receipts") if row["tool_name"] == "validate_rover_profile")
    assert receipt["status"] == "FAILED" and receipt["error_code"] == "INPUT_INVALID"


def test_absent_energy_model_remains_unknown_without_invalidating_the_saved_declaration(role_attempt, monkeypatch):
    _, _, _, _, rover = attach_rover(role_attempt, monkeypatch, energy=False)
    report = profile_validation_report(rover)
    assert report["valid"] is True and report["energy_calibration_status"] == "NOT_SUPPLIED"
    assert report["physical_performance_validated"] is False and rover["energy_model"] is None
