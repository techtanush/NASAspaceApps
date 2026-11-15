"""Role validation/publication failures finish diagnostics without publishing partial proposals."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider
from analogforge.agents.runtime.provider import ProviderError
from analogforge.application.scheduler import WorkflowEngine, WorkflowError, WorkflowRolePaused
from analogforge.domain.policy import PolicyViolation
from analogforge.jobs.worker import Worker
from analogforge.settings import Settings
from tests.unit.platform.test_scientific_invocations import WorkerStoreDouble


@pytest.fixture
def role_attempt(tmp_path, monkeypatch):
    workspace, run_id, job_id = (str(uuid4()) for _ in range(3))
    store = WorkerStoreDouble(workspace, run_id)
    run = store.require("runs", run_id)
    run.update(mode="live", scenario_config_id="live-hackathon-v1", runtime={})
    job = {"id": job_id, "workspace_id": workspace, "run_id": run_id,
           "lease_token": str(uuid4()), "state": "QUEUED"}
    store.create("jobs", job)
    mission = {"id": str(uuid4()), "content_sha256": "a" * 64,
               "requirements": [{"id": "req-1", "origin": "PROPOSED_DEFAULT",
                                 "acceptance_note": "Proposed threshold requires explicit user review"}],
               "accepted_at": "2026-11-14T00:00:00Z"}
    run["mission_revision_id"] = mission["id"]
    run["runtime"] = {"mission_content_sha256": mission["content_sha256"]}
    store.create("mission_acceptances", {
        "id": str(uuid4()), "workspace_id": workspace, "mission_revision_id": mission["id"],
        "accepted_at": mission["accepted_at"], "created_at": mission["accepted_at"],
    })
    settings = Settings(_env_file=None, data_root=tmp_path,
                        config_dir=Path(__file__).resolve().parents[3] / "config")
    engine = WorkflowEngine(store, settings)
    monkeypatch.setattr(engine, "_load", lambda *_: (deepcopy(store.require("runs", run_id)), mission, None))
    monkeypatch.setattr(engine, "_charge", lambda *_: None)
    monkeypatch.setattr(engine, "_provider_client", lambda: object())
    return engine, store, workspace, run_id, job


def active_invocation(store):
    return next(row for row in store.list("invocations") if row["task_kind"] == "advance_workflow")


def test_accepted_proposed_default_has_exact_pinned_acceptance_context(role_attempt, monkeypatch):
    engine, store, workspace, run_id, _ = role_attempt
    acceptance = store.list("mission_acceptances")[0]
    # A later accepted revision must not replace the acceptance governing this older run.
    store.create("mission_acceptances", {**acceptance, "id": str(uuid4()), "mission_revision_id": str(uuid4())})
    captured = []

    def propose(_provider, task, registry, context):
        trusted = task.payload["contract_acceptance"]
        assert trusted == {
            "acceptance_id": acceptance["id"], "accepted_at": acceptance["accepted_at"],
            "mission_revision_id": str(task.contract_revision_id), "contract_sha256": task.contract_hash,
            "scope": "OPERATOR_CRITERIA_FOR_PINNED_REVISION", "scientific_validation": False,
        }
        contract = registry.execute("inspect_contract", {"contract_revision_id": str(task.contract_revision_id)},
                                    context, call_id="inspect-accepted")
        assert contract["acceptance"] == trusted and contract["accepted"] is True
        assert contract["requirements"][0]["origin"] == "PROPOSED_DEFAULT"
        assert "requires explicit user review" in contract["requirements"][0]["acceptance_note"]
        captured.append(task)
        return task.payload["prepared_submission"]

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert len(captured) == 1


def test_unaccepted_pinned_revision_cannot_invoke_role_even_with_accepted_other_revision(role_attempt, monkeypatch):
    engine, store, workspace, run_id, _ = role_attempt
    acceptance = store.list("mission_acceptances")[0]
    acceptance["mission_revision_id"] = str(uuid4())
    monkeypatch.setattr(OpenAIProvider, "run", lambda *_: pytest.fail("An unaccepted contract reached the provider"))
    with pytest.raises(WorkflowError) as caught:
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert caught.value.code == "CONTRACT_NOT_ACCEPTED"
    assert store.list("invocations") == []


def test_acceptance_context_rejects_pinned_content_hash_mismatch(role_attempt, monkeypatch):
    engine, store, workspace, run_id, _ = role_attempt
    store.require("runs", run_id)["runtime"]["mission_content_sha256"] = "b" * 64
    monkeypatch.setattr(OpenAIProvider, "run", lambda *_: pytest.fail("A hash mismatch reached the provider"))
    with pytest.raises(WorkflowError) as caught:
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert caught.value.code == "REVISION_CONFLICT"
    assert store.list("invocations") == []


def test_role_provider_failure_finalizes_invocation_and_worker_run_job(role_attempt, monkeypatch):
    engine, store, workspace, run_id, job = role_attempt
    failure = ProviderError("MODEL_OUTPUT_INVALID", "Repeated invalid tool/submission arguments")

    def reject(*_args):
        raise failure

    monkeypatch.setattr(OpenAIProvider, "run", reject)
    worker = Worker(store, lambda _job: engine._role("mission_director", "advance_workflow", run_id, workspace))
    monkeypatch.setattr(worker, "_heartbeats", lambda *_: None)
    assert worker.run_once()
    assert store.require("jobs", job["id"])["error"]["code"] == "MODEL_OUTPUT_INVALID"
    assert store.require("runs", run_id)["state"] == "FAILED"
    assert active_invocation(store)["status"] == "FAILED"
    assert store.list("role_results") == [] and store.list("agent_actions") == []


@pytest.mark.parametrize("failure_kind", ["schema", "policy"])
def test_role_schema_and_policy_rejection_terminalize_without_publication(role_attempt, monkeypatch, failure_kind):
    engine, store, workspace, run_id, _ = role_attempt

    def propose(_provider, task, _registry, _context):
        if failure_kind == "schema":
            return {}
        proposal = deepcopy(task.payload["prepared_submission"])
        proposal["payload"]["portfolio_revision_id"] = str(uuid4())
        return proposal

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    with pytest.raises(ValueError):
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert active_invocation(store)["status"] == "FAILED"
    assert store.list("role_results") == [] and store.list("agent_actions") == []


def test_late_role_publication_failure_rolls_back_success_and_finishes_failed(role_attempt, monkeypatch):
    engine, store, workspace, run_id, job = role_attempt
    monkeypatch.setattr(OpenAIProvider, "run", lambda _p, task, *_: task.payload["prepared_submission"])
    engine._job_context.set((job["id"], job["lease_token"]))
    staged = []

    def reject_event(_run_id, event_type, payload, *_args):
        if event_type == "agent.started" or payload.get("status") == "FAILED":
            return {}
        staged.append(active_invocation(store)["status"])
        raise PolicyViolation("TEST_PUBLICATION_REJECTED")

    monkeypatch.setattr(store, "append_event", reject_event)
    with pytest.raises(PolicyViolation, match="TEST_PUBLICATION_REJECTED"):
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert staged == ["SUCCEEDED"]
    assert active_invocation(store)["status"] == "FAILED"
    assert store.list("role_results") == [] and store.list("agent_actions") == []


def test_role_review_pause_preserves_successful_atomic_publication(role_attempt, monkeypatch):
    engine, store, workspace, run_id, job = role_attempt

    def propose(_p, task, *_):
        return {**task.payload["prepared_submission"], "disposition": "NEEDS_USER_REVIEW",
                "next_action": "request_review"}

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    engine._job_context.set((job["id"], job["lease_token"]))
    with pytest.raises(WorkflowRolePaused):
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert active_invocation(store)["status"] == "SUCCEEDED"
    assert len(store.list("role_results")) == len(store.list("agent_actions")) == 1


def test_explicit_retry_clears_previous_role_pause_without_resolving_material_review_or_history(
    role_attempt, monkeypatch,
):
    engine, store, workspace, run_id, _ = role_attempt
    run = store.require("runs", run_id)
    run.update(state="BLOCKED", blocked_dependencies=["USER_REVIEW_REQUIRED"], pending_review={
        "kind": "MATERIAL_EVIDENCE_CONCERN", "status": "PENDING", "critique_ids": ["critique-1"],
        "allowed_actions": ["APPROVE_EVIDENCE", "REJECT_EVIDENCE"],
    })
    run["runtime"].update(resume_state="BUILDING_PASSPORT", role_disposition="NEEDS_USER_REVIEW",
                          budget={"counters": {"model_requests_per_run": 21}})
    mission = deepcopy(engine._load(run_id, workspace)[1])
    mission.update(target={"body": "MARS", "radius_m": 500}, requirements=[{
        "id": "req-1", "origin": "USER", "operator": "LTE", "threshold": {"upper": 5},
    }])
    store.create("mission_revisions", mission)
    store.create("critiques", {"id": "critique-1", "run_id": run_id, "status": "OPEN",
                              "summary": "Pending material evidence concern"})
    store.create("role_results", {"id": "previous-role", "run_id": run_id,
                                 "payload": {"disposition": "NEEDS_USER_REVIEW"}})
    original = deepcopy(run)
    protected = {kind: deepcopy(rows) for kind, rows in store.data.items() if kind != "runs"}
    enqueued = []
    monkeypatch.setattr(store, "enqueue", lambda kind, payload, **_: enqueued.append((kind, payload)), raising=False)

    resumed = engine.apply_action(run_id, workspace, "RETRY", {}, run["revision"])
    assert resumed["state"] == "BUILDING_PASSPORT" and resumed["blocked_dependencies"] == []
    assert "role_disposition" not in resumed["runtime"]
    expected = deepcopy(original)
    expected.update(state="BUILDING_PASSPORT", blocked_dependencies=[])
    expected["runtime"].pop("role_disposition")
    assert resumed == expected
    assert enqueued == [("ADVANCE_RUN", {"run_id": run_id, "state": "BUILDING_PASSPORT"})]
    assert {kind: rows for kind, rows in store.data.items() if kind != "runs"} == protected

    def current_review(*_args):
        assert "role_disposition" not in store.require("runs", run_id)["runtime"]
        raise WorkflowRolePaused("NEEDS_USER_REVIEW", "Fresh review still requires operator attention")

    monkeypatch.setattr(engine, "_advance_step", current_review)
    paused = engine.advance(run_id, workspace)
    assert paused["state"] == "BLOCKED" and paused["blocked_dependencies"] == ["USER_REVIEW_REQUIRED"]
    assert paused["runtime"]["role_disposition"] == "NEEDS_USER_REVIEW"
    assert paused["pending_review"] == original["pending_review"]
    assert {kind: rows for kind, rows in store.data.items() if kind != "runs"} == protected


def test_role_cleanup_error_preserves_original_and_logs_no_private_exception(role_attempt, monkeypatch, caplog):
    engine, store, workspace, run_id, _ = role_attempt
    failure = ProviderError("MODEL_OUTPUT_INVALID", "Original validation failure")

    def reject(*_args):
        raise failure

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private database connection details")

    monkeypatch.setattr(OpenAIProvider, "run", reject)
    monkeypatch.setattr(store, "replace", unavailable)
    with pytest.raises(ProviderError) as caught:
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert caught.value is failure
    assert "role.invocation_finalize_failed" in caplog.text
    assert "private database" not in caplog.text


@pytest.mark.parametrize("failure", [False, True])
def test_actual_provider_trace_persists_for_success_and_failure(role_attempt, monkeypatch, failure):
    from types import SimpleNamespace

    engine, store, workspace, run_id, _ = role_attempt
    attempts = [{"provider": "openai", "model": "primary", "status": "FAILED", "http_status": 429},
                {"provider": "groq", "model": "secondary", "status": "SUCCEEDED"}]
    monkeypatch.setattr(engine, "_provider_client", lambda: SimpleNamespace(attempts=attempts))

    def propose(_provider, task, _registry, _context):
        if failure:
            raise ProviderError("MODEL_OUTPUT_INVALID", "Rejected proposal")
        return task.payload["prepared_submission"]

    monkeypatch.setattr(OpenAIProvider, "run", propose)
    if failure:
        with pytest.raises(ProviderError):
            engine._role("mission_director", "advance_workflow", run_id, workspace)
    else:
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    row = active_invocation(store)
    assert row["status"] == ("FAILED" if failure else "SUCCEEDED")
    assert row["provider_attempts"] == attempts


def test_role_start_is_committed_and_fenced_before_provider_execution(role_attempt, monkeypatch):
    engine, store, workspace, run_id, job = role_attempt
    engine._job_context.set((job["id"], job["lease_token"]))
    events = []

    def record(_run_id, event_type, payload, _mode):
        assert store.in_publication
        events.append((event_type, deepcopy(payload)))

    def propose(_provider, task, *_args):
        assert events[0][0] == "agent.started"
        assert events[0][1]["invocation_id"] == str(task.invocation_id)
        assert active_invocation(store)["status"] == "RUNNING"
        assert not store.in_publication  # No transaction/row lock held across provider work.
        return task.payload["prepared_submission"]

    monkeypatch.setattr(store, "append_event", record)
    monkeypatch.setattr(OpenAIProvider, "run", propose)
    engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert [event[0] for event in events] == ["agent.started", "agent.completed"]
    assert events[-1][1]["status"] == "SUCCEEDED"


def test_role_start_cannot_invoke_provider_after_lease_loss(role_attempt, monkeypatch):
    from contextlib import contextmanager

    from analogforge.db.store import LeaseLost

    engine, store, workspace, run_id, job = role_attempt
    engine._job_context.set((job["id"], job["lease_token"]))
    events = []

    @contextmanager
    def lost(*_args):
        raise LeaseLost()
        yield

    monkeypatch.setattr(store, "publication", lost)
    monkeypatch.setattr(store, "append_event", lambda *_args: events.append(_args))
    monkeypatch.setattr(OpenAIProvider, "run", lambda *_args: pytest.fail("A lost lease invoked the provider"))
    with pytest.raises(LeaseLost):
        engine._role("mission_director", "advance_workflow", run_id, workspace)
    assert events == []
    assert not any(invocation["task_kind"] == "advance_workflow" for invocation in store.list("invocations"))
