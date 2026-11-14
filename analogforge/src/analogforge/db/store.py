"""Short, scoped transactions, optimistic revisions and durable publication fencing."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from analogforge.db.rls import configure_workspace
from analogforge.db.schema import IMMUTABLE, TABLES
from analogforge.ports.hashing import canonical_sha256

ALIASES = {
    "tests": "verification_tests",
    "preparations": "preparation_jobs",
    "invocations": "agent_invocations",
    "compatibility": "compatibility_assessments",
    "artifacts": "artifact_blobs",
    "drafts": "mission_drafts",
    "acceptances": "mission_acceptances",
}


class PersistenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class NotFound(PersistenceError):
    def __init__(self, message: str = "Record not found") -> None:
        super().__init__("NOT_FOUND", message)


class RevisionConflict(PersistenceError):
    def __init__(self, message: str = "Revision is stale") -> None:
        super().__init__("REVISION_CONFLICT", message)


class IdempotencyConflict(PersistenceError):
    def __init__(self, message: str = "Idempotency key was used with another request") -> None:
        super().__init__("IDEMPOTENCY_CONFLICT", message)


class LeaseLost(PersistenceError):
    def __init__(self, message: str = "Worker no longer owns this publication lease") -> None:
        super().__init__("LEASE_LOST", message)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def document(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    raw = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    result: dict[str, Any] = json.loads(json.dumps(raw, default=_json_default, allow_nan=False))
    return result


def _table(kind: str) -> sa.Table:
    return TABLES[ALIASES.get(kind, kind)]


def _payload(table: sa.Table, exclude: Sequence[str]) -> sa.ColumnElement[Any]:
    """The stored document, minus ``exclude`` keys removed by PostgreSQL (jsonb ``- text[]``)."""
    if not exclude:
        return table.c.document_json
    keys = sa.cast(postgresql.array(list(exclude)), postgresql.ARRAY(sa.Text))
    return table.c.document_json.op("-", return_type=JSONB)(keys)


def _columns(table: sa.Table, doc: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {"document_json": doc}
    for col in table.c:
        if col.name in doc and col.name != "document_json":
            value = doc[col.name]
            if isinstance(col.type, sa.DateTime) and isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            values[col.name] = value
    if table.name == "run_events":
        values["type"] = doc["event_type"]
    return values


class UnitOfWork:
    def __init__(self, connection: sa.Connection, workspace_id: str) -> None:
        self.connection = connection
        self.workspace_id = str(UUID(str(workspace_id)))

    def get(
        self, kind: str, entity_id: str | UUID, *, lock: bool = False, exclude: Sequence[str] = ()
    ) -> dict[str, Any] | None:
        table = _table(kind)
        query = sa.select(_payload(table, exclude)).where(
            table.c.workspace_id == self.workspace_id, table.c.id == str(entity_id)
        )
        if lock:
            query = query.with_for_update()
        result = self.connection.execute(query).scalar_one_or_none()
        return document(result) if result is not None else None

    def require(
        self, kind: str, entity_id: str | UUID, *, lock: bool = False, exclude: Sequence[str] = ()
    ) -> dict[str, Any]:
        result = self.get(kind, entity_id, lock=lock, exclude=exclude)
        if result is None:
            raise NotFound()
        return result

    def list(
        self,
        kind: str,
        filters: Mapping[str, Any] | None = None,
        *,
        exclude: Sequence[str] = (),
        after: tuple[str, str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rows of one kind in (created_at, id) order.

        ``exclude`` drops stored-only payload keys inside PostgreSQL, ``after`` is a keyset position
        ``(created_at, id)`` and ``limit`` bounds the page, so a page never loads more than it returns.
        """
        table = _table(kind)
        query = sa.select(_payload(table, exclude)).where(table.c.workspace_id == self.workspace_id)
        for name, value in (filters or {}).items():
            if name in table.c:
                query = query.where(
                    table.c[name].is_(None)
                    if value is None
                    else table.c[name] == str(value)
                    if isinstance(value, UUID)
                    else table.c[name] == value
                )
            else:
                query = query.where(table.c.document_json[name].astext == str(value))
        if after is not None:
            moment = datetime.fromisoformat(after[0].replace("Z", "+00:00"))
            query = query.where(
                sa.tuple_(table.c.created_at, table.c.id)
                > sa.tuple_(sa.literal(moment, table.c.created_at.type), sa.literal(UUID(after[1]), table.c.id.type))
            )
        query = query.order_by(table.c.created_at, table.c.id)
        if limit is not None:
            query = query.limit(limit)
        return [document(row) for row in self.connection.execute(query).scalars()]

    def create(self, kind: str, value: Mapping[str, Any] | Any) -> dict[str, Any]:
        table = _table(kind)
        doc = document(value)
        if doc.get("workspace_id", self.workspace_id) != self.workspace_id:
            raise NotFound()
        doc.setdefault("id", str(uuid4()))
        doc.setdefault("workspace_id", self.workspace_id)
        doc.setdefault("created_at", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        if "revision" in table.c:
            doc.setdefault("revision", 1)
        if table.name == "runs":
            if doc.get("run_id") not in (None, doc["id"]):
                raise PersistenceError("MODEL_OUTPUT_INVALID", "Run id and id must agree")
            doc.setdefault("last_event_seq", 0)
        elif "run_id" in table.c and doc.get("run_id") is not None:
            run = self.require("runs", doc["run_id"])
            if "mode" in table.c:
                doc.setdefault("mode", run["mode"])
                if doc["mode"] != run["mode"]:
                    raise PersistenceError("MODE_MISMATCH", "Record mode differs from run")
        for field, related_kind in {
            "candidate_id": "candidates",
            "test_id": "verification_tests",
            "passport_id": "passports",
            "invocation_id": "agent_invocations",
            "parent_test_id": "verification_tests",
        }.items():
            if doc.get(field):
                related = self.require(related_kind, doc[field])
                if doc.get("run_id") and related.get("run_id") != doc["run_id"]:
                    raise NotFound()
        if table.name == "evidence":
            for parent_id in doc.get("input_evidence_ids", []):
                parent = self.require("evidence", parent_id)
                if (parent.get("run_id"), parent.get("mode")) != (doc.get("run_id"), doc.get("mode")):
                    raise NotFound()
        if table.name == "passports":
            if not doc.get("assurance_evidence_id"):
                raise PersistenceError("SCIENTIFIC_CLAIM_REJECTED", "Passport requires scientific assurance")
            assurance = self.require("evidence", doc.get("assurance_evidence_id", str(UUID(int=0))))
            if (assurance.get("run_id"), assurance.get("mode")) != (doc.get("run_id"), doc.get("mode")):
                raise NotFound()
            if assurance["id"] not in doc.get("evidence_ids", []):
                raise PersistenceError("SCIENTIFIC_CLAIM_REJECTED", "Assurance must appear in passport evidence")
            if assurance.get("kind") != "DERIVED" or assurance.get("algorithm_id") != "scientific-assurance":
                raise PersistenceError("SCIENTIFIC_CLAIM_REJECTED", "Passport requires scientific assurance")
        self.connection.execute(table.insert().values(**_columns(table, doc)))
        return doc

    def replace(
        self, kind: str, entity_id: str | UUID, value: Mapping[str, Any] | Any, expected_revision: int | None = None
    ) -> dict[str, Any]:
        table = _table(kind)
        if table.name in IMMUTABLE:
            raise PersistenceError("IMMUTABLE_RECORD", "Create a superseding revision")
        current = self.require(kind, entity_id, lock=True)
        if expected_revision is not None and current.get("revision") != expected_revision:
            raise RevisionConflict()
        doc = document(value)
        if (
            str(doc.get("id", entity_id)) != str(entity_id)
            or doc.get("workspace_id", self.workspace_id) != self.workspace_id
        ):
            raise NotFound()
        doc["id"] = str(entity_id)
        doc["workspace_id"] = self.workspace_id
        if table.name == "runs":
            for field in (
                "mission_revision_id",
                "rover_revision_id",
                "mode",
                "config_sha256",
                "scenario_config_id",
                "dataset_lock_id",
            ):
                if doc.get(field) != current.get(field):
                    raise PersistenceError("IMMUTABLE_RECORD", "Run inputs require a new accepted revision and run")
        if table.name == "jobs":
            for field in ("run_id", "preparation_id", "kind", "input_hash"):
                if doc.get(field) != current.get(field):
                    raise PersistenceError("IMMUTABLE_RECORD", "Job context and input identity cannot change")
        doc.setdefault("created_at", current["created_at"])
        if "revision" in table.c:
            doc["revision"] = current["revision"] + 1
        self.connection.execute(
            table.update()
            .where(table.c.workspace_id == self.workspace_id, table.c.id == str(entity_id))
            .values(**_columns(table, doc))
        )
        return doc

    def append_event(
        self, run_id: str | UUID, event_type: str, payload: Mapping[str, Any], mode: str
    ) -> dict[str, Any]:
        run = self.require("runs", run_id, lock=True)
        if run["mode"] != mode:
            raise PersistenceError("MODE_MISMATCH", "Event mode differs from run")
        seq = run.get("last_event_seq", 0) + 1
        run["last_event_seq"] = seq
        self.replace("runs", run_id, run, expected_revision=run["revision"])
        event = {
            "schema_version": "1.0",
            "id": str(uuid4()),
            "workspace_id": self.workspace_id,
            "run_id": str(run_id),
            "mode": mode,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "seq": seq,
            "event_type": event_type,
            "state": run["state"],
            "summary": str(payload.get("summary", event_type)),
            "payload": document(payload),
            "evidence_ids": list(payload.get("evidence_ids", [])),
        }
        if len(json.dumps(event).encode()) > 16384:
            raise PersistenceError("RESOURCE_LIMIT", "Event payload exceeds 16 KiB")
        return self.create("run_events", event)

    def enqueue(
        self,
        kind: str,
        payload: Mapping[str, Any],
        run_id: str | UUID | None = None,
        preparation_id: str | UUID | None = None,
        input_hash: str | None = None,
    ) -> dict[str, Any]:
        if (run_id is None) == (preparation_id is None):
            raise ValueError("Exactly one job context is required")
        digest = input_hash or canonical_sha256(document(payload))
        matches = self.list("jobs", {"kind": kind, "input_hash": digest})
        for job in matches:
            if (
                job.get("run_id") == (str(run_id) if run_id else None)
                and job.get("preparation_id") == (str(preparation_id) if preparation_id else None)
                and job["state"] in {"QUEUED", "RUNNING"}
            ):
                return job
        return self.create(
            "jobs",
            {
                "kind": kind,
                "payload": document(payload),
                "run_id": str(run_id) if run_id else None,
                "preparation_id": str(preparation_id) if preparation_id else None,
                "state": "QUEUED",
                "priority": 0,
                "attempt": 0,
                "max_attempts": 3,
                "available_at": datetime.now(UTC),
                "input_hash": digest,
            },
        )

    def idempotency_begin(
        self, subject_id: str, method: str, path: str, key: str, body_hash: str
    ) -> tuple[int, dict[str, Any]] | None:
        scope = [self.workspace_id, subject_id, method, path, key]
        lock = int(canonical_sha256(scope)[:15], 16)
        self.connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        filters = {"subject_id": subject_id, "method": method, "path": path, "key": key}
        matches = self.list("idempotency_requests", filters)
        if matches:
            existing = matches[0]
            if existing["body_hash"] != body_hash:
                raise IdempotencyConflict()
            if existing.get("status") is not None:
                return int(existing["status"]), existing["response_json"]
            raise PersistenceError("IDEMPOTENCY_IN_PROGRESS", "Request has not completed")
        self.create(
            "idempotency_requests",
            {**filters, "body_hash": body_hash, "status": None, "expires_at": datetime.now(UTC) + timedelta(hours=24)},
        )
        return None

    def idempotency_complete(
        self, subject_id: str, method: str, path: str, key: str, status: int, response: Mapping[str, Any]
    ) -> None:
        matches = self.list(
            "idempotency_requests", {"subject_id": subject_id, "method": method, "path": path, "key": key}
        )
        if not matches:
            raise NotFound("Idempotency transaction was not begun")
        row = matches[0]
        row.update(status=status, response_json=document(response))
        self.replace("idempotency_requests", row["id"], row)


class Store:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.engine = sa.create_engine(database_url, pool_pre_ping=True, connect_args={"client_encoding": "utf8"})

    def health(self) -> bool:
        try:
            with self.engine.connect() as connection:
                if connection.execute(sa.text("SELECT to_regclass('alembic_version')")).scalar_one() is None:
                    return False
                revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
                artifacts = connection.execute(sa.text("SELECT to_regclass('artifact_blobs')")).scalar_one()
                return bool(revision == "0007" and artifacts is not None)
        except SQLAlchemyError:
            return False

    def close(self) -> None:
        self.engine.dispose()

    def migrate(self, revision: str = "head") -> None:
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, revision)

    def ensure_workspace(self, workspace_id: str | UUID, name: str = "Local") -> None:
        with self.engine.begin() as connection:
            connection.execute(
                insert(TABLES["workspaces"]).values(id=str(workspace_id), name=name).on_conflict_do_nothing()
            )

    def record_worker_heartbeat(self, worker_name: str) -> None:
        """Privileged queue service records presence separately in every known workspace."""
        with self.engine.connect() as connection:
            workspaces = list(connection.execute(sa.select(TABLES["workspaces"].c.id)).scalars())
        for workspace in workspaces:
            with self.transaction(workspace) as unit:
                rows = unit.list("worker_heartbeats", {"worker_name": worker_name})
                body = {"worker_name": worker_name, "heartbeat_at": datetime.now(UTC)}
                if rows:
                    unit.replace("worker_heartbeats", rows[0]["id"], {**rows[0], **body})
                else:
                    unit.create("worker_heartbeats", body)

    def worker_healthy(self, workspace_id: str | UUID | None = None, max_age_seconds: int = 60) -> bool:
        table = TABLES["worker_heartbeats"]
        query = sa.select(table.c.id).where(table.c.heartbeat_at >= sa.func.now() - timedelta(seconds=max_age_seconds))
        if workspace_id is not None:
            query = query.where(table.c.workspace_id == str(workspace_id))
        try:
            with self.engine.connect() as connection:
                return connection.execute(query.limit(1)).first() is not None
        except SQLAlchemyError:
            return False

    @contextmanager
    def transaction(self, workspace_id: str | UUID) -> Iterator[UnitOfWork]:
        try:
            with self.engine.begin() as connection:
                scoped = configure_workspace(connection, workspace_id)
                yield UnitOfWork(connection, scoped)
        except IntegrityError as exc:
            raise PersistenceError("INTEGRITY_CONFLICT", "Database integrity constraint rejected the write") from exc

    @contextmanager
    def publication(self, workspace_id: str | UUID, job_id: str | UUID, token: str | UUID) -> Iterator[UnitOfWork]:
        with self.transaction(workspace_id) as unit:
            # Global lock order: run (or preparation) -> job -> derived rows.
            # Cancellation follows the same order, so it cannot deadlock a publisher.
            context = unit.require("jobs", job_id)
            if context.get("run_id"):
                unit.require("runs", context["run_id"], lock=True)
            elif context.get("preparation_id"):
                unit.require("preparations", context["preparation_id"], lock=True)
            job = unit.require("jobs", job_id, lock=True)
            self._assert_lease(unit, job, token)
            yield unit
            self._assert_lease(unit, job, token, allow_completed=True)

    @staticmethod
    def _assert_lease(
        unit: UnitOfWork, job: Mapping[str, Any], token: str | UUID, allow_completed: bool = False
    ) -> None:
        # Re-read authoritative columns because clock expiry and cancellation can change while computing.
        table = TABLES["jobs"]
        valid = unit.connection.execute(
            sa.select(table.c.id).where(
                table.c.workspace_id == unit.workspace_id,
                table.c.id == job["id"],
                table.c.state.in_(["RUNNING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"])
                if allow_completed
                else table.c.state == "RUNNING",
                table.c.lease_token == str(token),
                table.c.lease_expires_at > sa.func.clock_timestamp(),
            )
        ).scalar_one_or_none()
        if valid is None:
            raise LeaseLost()
        if job.get("run_id"):
            run = unit.require("runs", job["run_id"], lock=True)
            if run.get("cancel_requested_at") or run["state"] == "CANCELLED":
                raise PersistenceError("RUN_CANCELLED", "Cancelled work cannot publish")

    def claim_job(self, lease_seconds: int = 120, workspace_id: str | None = None) -> dict[str, Any] | None:
        from analogforge.jobs.queue import claim_job

        return claim_job(self, lease_seconds, workspace_id)

    def heartbeat_job(self, job_id: str | UUID, token: str | UUID, lease_seconds: int = 120) -> bool:
        from analogforge.jobs.queue import heartbeat_job

        return heartbeat_job(self, str(job_id), str(token), lease_seconds)

    def reap_expired_jobs(self) -> int:
        from analogforge.jobs.queue import reap_expired_jobs

        return reap_expired_jobs(self)

    def events(self, workspace_id: str | UUID, run_id: str | UUID, after: int = 0) -> list[dict[str, Any]]:
        with self.transaction(workspace_id) as unit:
            run = unit.require("runs", run_id)
            events = unit.list("run_events", {"run_id": str(run_id)})
        events.sort(key=lambda event: event["seq"])
        if after < 0 or after > run.get("last_event_seq", 0) or (events and after < events[0]["seq"] - 1):
            raise PersistenceError("EVENT_CURSOR_EXPIRED", "Reload the run snapshot before resuming events")
        return [event for event in events if event["seq"] > after]

    def cancel_run(self, workspace_id: str | UUID, run_id: str | UUID) -> dict[str, Any]:
        with self.transaction(workspace_id) as unit:
            run = unit.require("runs", run_id, lock=True)
            if run["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                return run
            run.update(state="CANCELLED", cancel_requested_at=datetime.now(UTC))
            unit.replace("runs", run_id, run, run["revision"])
            unit.append_event(run_id, "run.cancelled", {"reason": "USER_REQUEST"}, run["mode"])
            for job in unit.list("jobs", {"run_id": str(run_id)}):
                if job["state"] in {"QUEUED", "RUNNING"}:
                    job.update(state="CANCELLED", lease_token=None, lease_expires_at=None)
                    unit.replace("jobs", job["id"], job)
            return unit.require("runs", run_id)
