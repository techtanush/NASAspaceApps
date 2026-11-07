"""PLT-05/06: exclusive leases, late-publication fencing and cancellation."""

import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
import sqlalchemy as sa

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.db.store import LeaseLost, PersistenceError, Store, UnitOfWork
from analogforge.jobs.cpu import run_science
from analogforge.ports.science import ScienceCancelled, ScienceContext, ScienceRequest, ScienceService
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


class _SlowScience:
    def __init__(self, started: Any) -> None:
        self.started = started

    def execute(self, request: Any, context: Any) -> Any:
        self.started.set()
        time.sleep(10)
        raise RuntimeError("Cancellation did not stop this test child")


def enqueue_run(store: Store) -> tuple[str, dict[str, object], dict[str, object]]:
    workspace, run = seed_run(store)
    with store.transaction(workspace) as unit:
        job = unit.enqueue("ADVANCE_RUN", {"stage": "VALIDATING"}, run_id=run["id"])
    return workspace, run, job


@pytest.mark.db
def test_two_workers_only_one_claim_and_heartbeat(platform_store: Store) -> None:
    workspace, _, queued = enqueue_run(platform_store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: platform_store.claim_job(workspace_id=workspace), range(2)))
    matching = [job for job in jobs if job and job["id"] == queued["id"]]
    assert len(matching) == 1
    job = matching[0]
    assert platform_store.heartbeat_job(job["id"], job["lease_token"])
    assert not platform_store.heartbeat_job(job["id"], "00000000-0000-0000-0000-000000000000")


@pytest.mark.db
def test_expired_lease_cannot_publish_and_reaper_fences(platform_store: Store) -> None:
    workspace, run, _ = enqueue_run(platform_store)
    job = platform_store.claim_job(workspace_id=workspace)
    assert job is not None
    with platform_store.engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE jobs SET lease_expires_at=now()-interval '1 second' WHERE id=:id"), {"id": job["id"]}
        )
    with pytest.raises(LeaseLost):
        with platform_store.publication(workspace, job["id"], job["lease_token"]) as unit:
            unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})
    assert platform_store.reap_expired_jobs() >= 1
    with platform_store.transaction(workspace) as unit:
        assert unit.list("evidence", {"run_id": run["id"]}) == []


@pytest.mark.db
def test_unexpired_lease_requires_exact_owner_token(platform_store: Store) -> None:
    workspace, run, _ = enqueue_run(platform_store)
    job = platform_store.claim_job(workspace_id=workspace)
    assert job is not None
    with pytest.raises(LeaseLost):
        with platform_store.publication(workspace, job["id"], str(uuid4())):
            raise AssertionError("A foreign token acquired a valid, unexpired job lease")
    with platform_store.publication(workspace, job["id"], job["lease_token"]) as unit:
        assert unit.require("runs", run["id"])["id"] == run["id"]


@pytest.mark.db
def test_cancel_during_work_retains_evidence_and_rejects_late_pass(platform_store: Store) -> None:
    workspace, run, _ = enqueue_run(platform_store)
    job = platform_store.claim_job(workspace_id=workspace)
    assert job
    with platform_store.transaction(workspace) as unit:
        prior = unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})
    platform_store.cancel_run(workspace, run["id"])
    with pytest.raises(PersistenceError):
        with platform_store.publication(workspace, job["id"], job["lease_token"]) as unit:
            unit.create("evidence", {"run_id": run["id"], "kind": "VERIFICATION", "outcome": "PASS"})
    with platform_store.transaction(workspace) as unit:
        assert unit.require("runs", run["id"])["state"] == "CANCELLED"
        assert [row["id"] for row in unit.list("evidence", {"run_id": run["id"]})] == [prior["id"]]


@pytest.mark.db
def test_cancellation_marker_fences_even_when_job_lease_is_valid(platform_store: Store) -> None:
    workspace, run, _ = enqueue_run(platform_store)
    job = platform_store.claim_job(workspace_id=workspace)
    assert job
    # Mimic a cancellation checkpoint preceding reconciliation of active job rows.
    with platform_store.transaction(workspace) as unit:
        current = unit.require("runs", run["id"])
        unit.replace("runs", run["id"], {**current, "state": "CANCELLED"}, current["revision"])
    with pytest.raises(PersistenceError) as error:
        with platform_store.publication(workspace, job["id"], job["lease_token"]):
            raise AssertionError("Cancellation guard did not run")
    assert error.value.code == "RUN_CANCELLED"


@pytest.mark.db
def test_crash_after_blob_move_rolls_back_records_and_retry_deduplicates(platform_store: Store, tmp_path: Path) -> None:
    workspace, run = seed_run(platform_store)
    cas = ContentAddressedStore(tmp_path)
    blob = cas.put_bytes(b"verified immutable bytes", "application/json")
    with pytest.raises(RuntimeError, match="simulated"):
        with platform_store.transaction(workspace) as unit:
            unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED", "artifact_sha256": blob.sha256})
            raise RuntimeError("simulated worker crash before commit")
    assert cas.read(blob.sha256) == b"verified immutable bytes"
    assert cas.put_bytes(b"verified immutable bytes").sha256 == blob.sha256
    with platform_store.transaction(workspace) as unit:
        assert unit.list("evidence", {"run_id": run["id"]}) == []
        unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED", "artifact_sha256": blob.sha256})
    with platform_store.transaction(workspace) as unit:
        assert len(unit.list("evidence", {"run_id": run["id"]})) == 1


@pytest.mark.db
def test_cancel_during_actual_cpu_child_is_prompt(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    started = multiprocessing.get_context("spawn").Event()
    previous_children = {process.pid for process in multiprocessing.active_children()}
    timestamps: dict[str, float] = {}
    failures: list[str] = []

    def cancel() -> None:
        if not started.wait(timeout=15):
            failures.append("The science child never entered execute")
            return
        timestamps["cancel_requested"] = time.monotonic()
        platform_store.cancel_run(workspace, run["id"])
        timestamps["cancel_acknowledged"] = time.monotonic()

    def check_cancelled() -> None:
        with platform_store.transaction(workspace) as unit:
            if unit.require("runs", run["id"])["state"] == "CANCELLED":
                raise ScienceCancelled()

    thread = threading.Thread(target=cancel)
    thread.start()
    with pytest.raises(ScienceCancelled):
        run_science(
            cast(ScienceService, _SlowScience(started)),
            cast(ScienceRequest, None),
            cast(ScienceContext, None),
            check_cancelled=check_cancelled,
        )
    child_terminated = time.monotonic()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not failures and started.is_set()
    assert timestamps["cancel_acknowledged"] - timestamps["cancel_requested"] <= 2
    assert child_terminated - timestamps["cancel_acknowledged"] <= 5
    assert {process.pid for process in multiprocessing.active_children()} == previous_children
    with platform_store.transaction(workspace) as unit:
        assert unit.require("runs", run["id"])["state"] == "CANCELLED"
        assert unit.list("test_results", {"run_id": run["id"]}) == []


@pytest.mark.db
def test_concurrent_cancellation_and_publication_share_lock_order(
    platform_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, run, _ = enqueue_run(platform_store)
    job = platform_store.claim_job(workspace_id=workspace)
    assert job
    cancel_holds_run = threading.Event()
    original = UnitOfWork.require

    def observe(unit: UnitOfWork, kind: str, entity_id: Any, *, lock: bool = False) -> dict[str, Any]:
        result = original(unit, kind, entity_id, lock=lock)
        if kind == "runs" and lock and threading.current_thread().name == "cancel-lock-order-test":
            cancel_holds_run.set()
            time.sleep(0.2)
        return result

    monkeypatch.setattr(UnitOfWork, "require", observe)

    def cancel() -> str:
        threading.current_thread().name = "cancel-lock-order-test"
        return platform_store.cancel_run(workspace, run["id"])["state"]

    def publish() -> str:
        try:
            with platform_store.publication(workspace, job["id"], job["lease_token"]) as unit:
                unit.create("evidence", {"run_id": run["id"], "kind": "VERIFICATION", "outcome": "PASS"})
            return "published"
        except PersistenceError:
            return "fenced"

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancelling = pool.submit(cancel)
        assert cancel_holds_run.wait(timeout=2)
        publishing = pool.submit(publish)
        assert cancelling.result(timeout=5) == "CANCELLED"
        assert publishing.result(timeout=5) == "fenced"
    with platform_store.transaction(workspace) as unit:
        assert unit.list("evidence", {"run_id": run["id"]}) == []
