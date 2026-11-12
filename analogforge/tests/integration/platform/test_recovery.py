"""Durability survives process replacement without process-local event or job state."""

from uuid import uuid4

import pytest
import sqlalchemy as sa

from analogforge.db.store import LeaseLost, Store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
@pytest.mark.parametrize("preparation", [False, True])
def test_exhausted_worker_retries_settle_parent_atomically(platform_store: Store, preparation: bool) -> None:
    workspace, run = seed_run(platform_store)
    parent_id = run["id"]
    with platform_store.transaction(workspace) as unit:
        if preparation:
            mission = unit.require("mission_revisions", run["mission_revision_id"])
            draft = unit.create("mission_drafts", {"mission_id": mission["mission_id"], "revision": 1, "draft": {}})
            parent = unit.create(
                "preparations",
                {"id": str(uuid4()), "mission_draft_revision_id": draft["id"], "mode": "synthetic", "status": "QUEUED"},
            )
            parent_id = parent["id"]
            job = unit.enqueue("PREPARE_FINGERPRINT", {}, preparation_id=parent_id)
        else:
            job = unit.enqueue("ADVANCE_RUN", {}, run_id=parent_id)
        unit.replace("jobs", job["id"], {**job, "max_attempts": 1})
    claimed = platform_store.claim_job(workspace_id=workspace)
    assert claimed and claimed["id"] == job["id"]
    with platform_store.engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE jobs SET lease_expires_at=now()-interval '1 second' WHERE id=:id"), {"id": job["id"]}
        )
    platform_store.reap_expired_jobs()
    with platform_store.transaction(workspace) as unit:
        settled = unit.require("jobs", job["id"])
        assert settled["state"] == "FAILED" and settled["error"]["code"] == "WORKER_LOST"
        parent = unit.require("preparations" if preparation else "runs", parent_id)
        assert parent["status" if preparation else "state"] == "FAILED"
        if not preparation:
            events = unit.list("run_events", {"run_id": parent_id})
            assert events[-1]["state"] == "FAILED" and events[-1]["event_type"] == "run.failed"


@pytest.mark.db
def test_replacement_api_loads_committed_snapshot_and_events(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        event = unit.append_event(run["id"], "run.state_changed", {"summary": "Durable"}, "synthetic")
    replacement = Store(platform_store.engine.url.render_as_string(hide_password=False))
    try:
        assert replacement.events(workspace, run["id"])[0] == event
        with replacement.transaction(workspace) as unit:
            assert unit.require("runs", run["id"])["last_event_seq"] == 1
    finally:
        replacement.close()


@pytest.mark.db
def test_replacement_worker_reclaims_expired_job_once(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        unit.enqueue("ADVANCE_RUN", {"checkpoint": "CHARACTERIZING"}, run_id=run["id"])
    first = platform_store.claim_job(workspace_id=workspace)
    assert first
    with platform_store.engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE jobs SET lease_expires_at=now()-interval '1 second' WHERE id=:id"), {"id": first["id"]}
        )
    replacement = Store(platform_store.engine.url.render_as_string(hide_password=False))
    try:
        replacement.reap_expired_jobs()
        with replacement.engine.begin() as connection:
            connection.execute(sa.text("UPDATE jobs SET available_at=now() WHERE id=:id"), {"id": first["id"]})
        second = replacement.claim_job(workspace_id=workspace)
        assert second and second["id"] == first["id"]
        assert second["lease_token"] != first["lease_token"] and second["attempt"] == 2
        with pytest.raises(LeaseLost):
            with replacement.publication(workspace, first["id"], first["lease_token"]):
                raise AssertionError("A stale worker entered publication")
        with replacement.publication(workspace, second["id"], second["lease_token"]) as unit:
            evidence = unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})
        with replacement.transaction(workspace) as unit:
            assert [row["id"] for row in unit.list("evidence", {"run_id": run["id"]})] == [evidence["id"]]
    finally:
        replacement.close()
