"""Crash and restart the actual API and worker OS processes against one durable database."""

from __future__ import annotations

import os
import signal
import socket
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa

from analogforge.api.contracts import validate
from analogforge.api.dependencies import LOCAL_WORKSPACE_ID
from analogforge.db.store import LeaseLost, Store
from analogforge.jobs.cpu import run_science
from analogforge.jobs.worker import Worker
from analogforge.main import create_app
from analogforge.ports.catalog import DATASET_LOCK_SYNTHETIC
from analogforge.ports.domain_models import RunSnapshot
from analogforge.settings import Settings
from tests.integration.platform.test_migrations import seed_run


@pytest.fixture
def isolated_store() -> Iterator[tuple[Store, str]]:
    base_url = Settings().test_database_url or os.environ.get("TEST_DATABASE_URL")
    assert base_url, "TEST_DATABASE_URL is required for real process recovery"
    database = "process_recovery_" + uuid4().hex
    admin = sa.create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(
            sa.text(f"CREATE DATABASE \"{database}\" TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'")
        )
    url = admin.url.set(database=database).render_as_string(hide_password=False)
    store = Store(url)
    try:
        store.migrate()
        yield store, url
    finally:
        store.close()
        with admin.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _api_process(url: str, data_root: str, port: int) -> None:
    import uvicorn

    settings = Settings(_env_file=None, database_url=url, data_root=Path(data_root), api_port=port)
    store = Store(url)
    uvicorn.run(
        create_app(settings=settings, store=store), host="127.0.0.1", port=port, access_log=False, log_level="error"
    )


def _kill(process: Any, *, group: bool = False) -> None:
    if process.pid is None:
        return
    if process.is_alive():
        if group:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    process.join(timeout=3)
    assert not process.is_alive(), "Child process remained alive after SIGKILL"


def _await_api(process: Any, client: httpx.Client) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert process.is_alive(), f"API process exited early with {process.exitcode}"
        try:
            if client.get("/api/v1/health/live").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.05)
    pytest.fail("API did not become ready within eight seconds")


@pytest.mark.db
def test_api_sigkill_restart_preserves_snapshot_and_sse_cursor(isolated_store, tmp_path):
    store, url = isolated_store
    workspace = LOCAL_WORKSPACE_ID
    store.ensure_workspace(workspace, "Process recovery")
    with store.transaction(workspace) as unit:
        mission = unit.create("missions", {"name": "Process recovery"})
        revision = unit.create(
            "mission_revisions",
            {"mission_id": mission["id"], "revision": 1, "content_sha256": "a" * 64, "accepted_at": None},
        )
        run_id = str(uuid4())
        complete = {
            "schema_version": "1.0",
            "id": run_id,
            "workspace_id": workspace,
            "run_id": run_id,
            "mode": "synthetic",
            "created_at": datetime.now(UTC).isoformat(),
            "state": "COMPLETED",
            "revision": 1,
            "last_event_seq": 0,
            "mission_revision_id": revision["id"],
            "rover_revision_id": None,
            "target_profile_id": None,
            "candidate_ids": [],
            "qualification_ids": [],
            "test_ids": [],
            "test_result_ids": [],
            "portfolio_ids": [],
            "passport_id": None,
            "pending_review": None,
            "blocked_dependencies": [],
            "selected_candidate_id": None,
            "selected_portfolio_id": None,
            "config_sha256": "b" * 64,
            "scenario_config_id": "synthetic-mars-mobility-v1",
            "dataset_lock_id": DATASET_LOCK_SYNTHETIC,
        }
        RunSnapshot.model_validate(complete)
        run = unit.create("runs", complete)
        event = unit.append_event(run_id, "run.state_changed", {"summary": "Durable after restart"}, "synthetic")
    port = _free_port()
    process = None
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
        try:
            reads = []
            for _ in range(2):
                process = get_context("spawn").Process(target=_api_process, args=(url, str(tmp_path), port))
                process.start()
                _await_api(process, client)
                snapshot = client.get(f"/api/v1/runs/{run['id']}")
                assert snapshot.status_code == 200, snapshot.text
                validate(snapshot.json(), {"$ref": "#/components/schemas/RunSnapshot"})
                RunSnapshot.model_validate(snapshot.json())
                stream = client.get(f"/api/v1/runs/{run['id']}/events?after=0")
                assert stream.status_code == 200, stream.text
                assert f"id:{event['seq']}\n" in stream.text
                assert "Durable after restart" in stream.text
                resumed = client.get(f"/api/v1/runs/{run['id']}/events?after={event['seq']}")
                assert resumed.status_code == 200 and resumed.text == ""
                reads.append(snapshot.json())
                _kill(process)
                process = None
            assert reads[0] == reads[1]
        finally:
            if process is not None:
                _kill(process)


class _SlowScience:
    def __init__(self, marker: str) -> None:
        self.marker = marker

    def execute(self, _request: Any, _context: Any) -> Any:
        Path(self.marker).write_text(str(os.getpid()), encoding="ascii")
        time.sleep(20)
        raise RuntimeError("The slow science process should be killed before returning")


def _worker_process(url: str, marker: str | None) -> None:
    os.setsid()  # Put the worker and its spawned CPU science child in one killable process group.
    store = Store(url)

    def handler(job: dict[str, Any]) -> None:
        if marker is not None:
            run_science(_SlowScience(marker), None, None, timeout_seconds=25)
            return
        with store.publication(job["workspace_id"], job["id"], job["lease_token"]) as unit:
            unit.create("evidence", {"run_id": job["run_id"], "kind": "DERIVED"})

    try:
        Worker(store, handler, lease_seconds=6, heartbeat_seconds=0.5).run_once()
    finally:
        store.close()


def _terminate_orphan(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _await_marker(marker: Path, process: Any) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert process.is_alive(), f"Worker process exited early with {process.exitcode}"
        if marker.is_file():
            return
        time.sleep(0.05)
    pytest.fail("Slow science never started within eight seconds")


@pytest.mark.db
def test_worker_sigkill_reap_replacement_publishes_once(isolated_store, tmp_path):
    store, url = isolated_store
    workspace, run = seed_run(store)
    with store.transaction(workspace) as unit:
        job = unit.enqueue("ADVANCE_RUN", {"stage": "VALIDATING"}, run_id=run["id"])
    marker = tmp_path / "science-entered"
    first = get_context("spawn").Process(target=_worker_process, args=(url, str(marker)), daemon=False)
    first.start()
    science_pid = None
    try:
        _await_marker(marker, first)
        science_pid = int(marker.read_text(encoding="ascii"))
        assert science_pid != first.pid
        with store.transaction(workspace) as unit:
            active = unit.require("jobs", job["id"])
            assert active["state"] == "RUNNING" and active["lease_token"]
        old_token = active["lease_token"]
    finally:
        _kill(first, group=True)
        if science_pid is not None:
            _terminate_orphan(science_pid)
    with store.engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE jobs SET lease_expires_at=now()-interval '1 second' WHERE id=:id"), {"id": job["id"]}
        )
    assert store.reap_expired_jobs() >= 1
    with store.engine.begin() as connection:
        connection.execute(sa.text("UPDATE jobs SET available_at=now() WHERE id=:id"), {"id": job["id"]})
    with pytest.raises(LeaseLost):
        with store.publication(workspace, job["id"], old_token):
            pytest.fail("The dead worker's token still permits publication")
    replacement = get_context("spawn").Process(target=_worker_process, args=(url, None), daemon=False)
    replacement.start()
    try:
        replacement.join(timeout=8)
        assert replacement.exitcode == 0, f"Replacement worker did not finish: {replacement.exitcode}"
    finally:
        _kill(replacement, group=True)
    with store.transaction(workspace) as unit:
        settled = unit.require("jobs", job["id"])
        evidence = unit.list("evidence", {"run_id": run["id"]})
        assert settled["state"] == "SUCCEEDED" and settled["attempt"] == 2
        assert settled["lease_token"] != old_token
        assert len(evidence) == 1
    extra = get_context("spawn").Process(target=_worker_process, args=(url, None), daemon=False)
    extra.start()
    try:
        extra.join(timeout=8)
        assert extra.exitcode == 0
    finally:
        _kill(extra, group=True)
    with store.transaction(workspace) as unit:
        assert len(unit.list("evidence", {"run_id": run["id"]})) == 1
