"""Worker coordinator keeps long work leased and publishes final state atomically."""

from typing import Any

import pytest

from analogforge.api.errors import ApiError
from analogforge.db.store import Store
from analogforge.jobs.worker import Worker
from analogforge.ports.science import ScienceCancelled, ScienceDeadlineExceeded
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
def test_worker_handler_completes_one_job_and_graceful_stop(
    platform_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        queued = unit.enqueue("ADVANCE_RUN", {"operation": "test"}, run_id=run["id"])
    real_claim = platform_store.claim_job
    monkeypatch.setattr(platform_store, "claim_job", lambda lease_seconds: real_claim(lease_seconds, workspace))

    def handle(job: dict[str, Any]) -> None:
        with platform_store.publication(workspace, job["id"], job["lease_token"]) as unit:
            unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})

    worker = Worker(platform_store, handle)
    assert worker.run_once()
    assert platform_store.worker_healthy(workspace)
    with platform_store.transaction(workspace) as unit:
        assert unit.require("jobs", queued["id"])["state"] == "SUCCEEDED"
        assert len(unit.list("evidence", {"run_id": run["id"]})) == 1
    worker.stop()
    assert not worker.run_once()


@pytest.mark.db
@pytest.mark.parametrize("exception,terminal", [(ScienceDeadlineExceeded, "BLOCKED"), (ScienceCancelled, "CANCELLED")])
def test_worker_survives_deadline_and_cancellation_then_processes_next_job(
    platform_store: Store, monkeypatch: pytest.MonkeyPatch, exception: type[Exception], terminal: str
) -> None:
    workspace, first_run = seed_run(platform_store)
    _, next_run = seed_run(platform_store, workspace)
    with platform_store.transaction(workspace) as unit:
        first = unit.enqueue("ADVANCE_RUN", {"run": first_run["id"]}, run_id=first_run["id"])
        second = unit.enqueue("ADVANCE_RUN", {"run": next_run["id"]}, run_id=next_run["id"])
    real_claim = platform_store.claim_job
    monkeypatch.setattr(platform_store, "claim_job", lambda lease_seconds: real_claim(lease_seconds, workspace))
    handled: list[str] = []

    def handler(job: dict[str, Any]) -> None:
        handled.append(job["id"])
        if job["id"] == first["id"]:
            raise exception()

    worker = Worker(platform_store, handler)
    assert worker.run_once() and worker.run_once()
    assert handled == [first["id"], second["id"]]
    with platform_store.transaction(workspace) as unit:
        assert unit.require("jobs", first["id"])["state"] == terminal
        assert unit.require("runs", first_run["id"])["state"] == terminal
        assert unit.require("jobs", second["id"])["state"] == "SUCCEEDED"


@pytest.mark.db
def test_export_failure_preserves_completed_scientific_run(
    platform_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        current = unit.require("runs", run["id"])
        unit.replace("runs", run["id"], {**current, "state": "COMPLETED"}, current["revision"])
        job = unit.enqueue("EXPORT_PASSPORT", {"run_id": run["id"]}, run_id=run["id"])
    real_claim = platform_store.claim_job
    monkeypatch.setattr(platform_store, "claim_job", lambda lease_seconds: real_claim(lease_seconds, workspace))

    def broken_renderer(_job: dict[str, Any]) -> None:
        raise RuntimeError("Renderer unavailable")

    assert Worker(platform_store, broken_renderer).run_once()
    with platform_store.transaction(workspace) as unit:
        assert unit.require("runs", run["id"])["state"] == "COMPLETED"
        assert unit.require("jobs", job["id"])["state"] == "FAILED"


@pytest.mark.db
@pytest.mark.parametrize("error_kind", ["key", "attribute", "api", "assertion"])
def test_unexpected_handler_error_fails_closed_and_next_job_runs(
    platform_store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error_kind: str
) -> None:
    workspace, failing_run = seed_run(platform_store)
    _, following_run = seed_run(platform_store, workspace)
    with platform_store.transaction(workspace) as unit:
        failing = unit.enqueue("ADVANCE_RUN", {"run_id": failing_run["id"]}, run_id=failing_run["id"])
        following = unit.enqueue("ADVANCE_RUN", {"run_id": following_run["id"]}, run_id=following_run["id"])
    real_claim = platform_store.claim_job
    monkeypatch.setattr(platform_store, "claim_job", lambda lease_seconds: real_claim(lease_seconds, workspace))
    private_message = "private-handler-content-that-must-not-be-logged"
    handled: list[str] = []

    def malformed(job: dict[str, Any]) -> None:
        handled.append(job["id"])
        if job["id"] == failing["id"]:
            errors: dict[str, Exception] = {
                "key": KeyError(private_message),
                "attribute": AttributeError(private_message),
                "api": ApiError("INPUT_INVALID", private_message),
                "assertion": AssertionError(private_message),
            }
            raise errors[error_kind]

    worker = Worker(platform_store, malformed)
    assert worker.run_once() and worker.run_once()
    assert handled == [failing["id"], following["id"]]
    with platform_store.transaction(workspace) as unit:
        assert unit.require("jobs", failing["id"])["state"] == "FAILED"
        assert unit.require("jobs", failing["id"])["error"]["code"] == "SYSTEM"
        assert unit.require("runs", failing_run["id"])["state"] == "FAILED"
        assert unit.require("jobs", following["id"])["state"] == "SUCCEEDED"
    assert private_message not in caplog.text
    errors = [record for record in caplog.records if record.getMessage() == "worker.handler_failed"]
    assert errors and all(record.exc_info is None for record in errors)
