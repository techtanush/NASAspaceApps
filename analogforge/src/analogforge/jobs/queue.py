"""PostgreSQL SKIP LOCKED lease queue. No transaction spans external work."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import sqlalchemy as sa

from analogforge.db.schema import TABLES
from analogforge.db.store import document

if TYPE_CHECKING:
    from analogforge.db.store import Store

LEASE_SECONDS = 120
HEARTBEAT_SECONDS = 20
REAPER_SECONDS = 30


def _job_document(row: sa.RowMapping) -> dict[str, Any]:
    doc = document(row["document_json"])
    for key in ("state", "attempt", "lease_token", "lease_expires_at", "heartbeat_at", "available_at"):
        doc[key] = row[key]
    return document(doc)


def claim_job(
    store: Store, lease_seconds: int = LEASE_SECONDS, workspace_id: str | None = None
) -> dict[str, Any] | None:
    if lease_seconds <= 0:
        raise ValueError("Lease must be positive")
    with store.engine.begin() as connection:
        result = (
            connection.execute(
                sa.text("""
          WITH picked AS (
            SELECT id FROM jobs
            WHERE state = 'QUEUED' AND available_at <= now()
              AND (CAST(:workspace AS uuid) IS NULL OR workspace_id = CAST(:workspace AS uuid))
            ORDER BY priority DESC, available_at ASC, id ASC
            FOR UPDATE SKIP LOCKED LIMIT 1
          ) UPDATE jobs j SET state='RUNNING', lease_token=:token,
            lease_expires_at=now()+make_interval(secs => :seconds),
            heartbeat_at=now(), attempt=attempt+1
          FROM picked WHERE j.id=picked.id RETURNING j.*
        """),
                {"token": str(uuid4()), "seconds": lease_seconds, "workspace": workspace_id},
            )
            .mappings()
            .one_or_none()
        )
        if result is None:
            return None
        doc = _job_document(result)
        connection.execute(TABLES["jobs"].update().where(TABLES["jobs"].c.id == doc["id"]).values(document_json=doc))
        return doc


def heartbeat_job(store: Store, job_id: str, token: str, lease_seconds: int = LEASE_SECONDS) -> bool:
    table = TABLES["jobs"]
    with store.engine.begin() as connection:
        result = connection.execute(
            table.update()
            .where(
                table.c.id == job_id,
                table.c.state == "RUNNING",
                table.c.lease_token == token,
                table.c.lease_expires_at > sa.func.clock_timestamp(),
            )
            .values(heartbeat_at=sa.func.now(), lease_expires_at=sa.func.now() + timedelta(seconds=lease_seconds))
            .returning(table)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return False
        doc = _job_document(row)
        connection.execute(table.update().where(table.c.id == job_id).values(document_json=doc))
        return True


def reap_expired_jobs(store: Store) -> int:
    """Use the same context-before-job lock order as cancellation/publication."""
    from analogforge.db.store import UnitOfWork

    table = TABLES["jobs"]
    count = 0
    with store.engine.begin() as connection:
        candidates = (
            connection.execute(
                sa.select(table)
                .where(table.c.state == "RUNNING", table.c.lease_expires_at <= sa.func.clock_timestamp())
                .order_by(table.c.workspace_id, table.c.run_id, table.c.preparation_id, table.c.id)
            )
            .mappings()
            .all()
        )
        for candidate in candidates:
            unit = UnitOfWork(connection, str(candidate["workspace_id"]))
            run = unit.require("runs", str(candidate["run_id"]), lock=True) if candidate["run_id"] else None
            preparation = (
                unit.require("preparations", str(candidate["preparation_id"]), lock=True)
                if candidate["preparation_id"]
                else None
            )
            row = (
                connection.execute(
                    sa.select(table)
                    .where(
                        table.c.id == candidate["id"],
                        table.c.state == "RUNNING",
                        table.c.lease_expires_at <= sa.func.clock_timestamp(),
                    )
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                continue
            doc = _job_document(row)
            exhausted = row["attempt"] >= row["max_attempts"]
            cancelled = run is not None and run["state"] == "CANCELLED"
            doc.update(
                state="CANCELLED" if cancelled else "FAILED" if exhausted else "QUEUED",
                lease_token=None,
                lease_expires_at=None,
                available_at=datetime.now(UTC) + timedelta(seconds=min(2 ** row["attempt"], 30)),
            )
            if exhausted and not cancelled:
                doc["error"] = {"code": "WORKER_LOST"}
            connection.execute(
                table.update()
                .where(table.c.id == row["id"])
                .values(
                    state=doc["state"],
                    lease_token=None,
                    lease_expires_at=None,
                    available_at=doc["available_at"],
                    document_json=document(doc),
                )
            )
            if exhausted and not cancelled and run is not None:
                if run["state"] not in {"COMPLETED", "FAILED"}:
                    run["state"] = "FAILED"
                    run.setdefault("runtime", {})["stop_reason"] = "WORKER_LOST"
                    unit.replace("runs", run["id"], run, run["revision"])
                    unit.append_event(
                        run["id"], "run.failed", {"code": "WORKER_LOST", "job_id": str(row["id"])}, run["mode"]
                    )
            elif exhausted and preparation is not None:
                unit.replace(
                    "preparations",
                    preparation["id"],
                    {**preparation, "status": "FAILED", "error": {"code": "WORKER_LOST"}},
                )
            count += 1
    return count
