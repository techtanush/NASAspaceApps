"""Workspace-scoped PostgreSQL schema; scientific documents remain kit-shaped JSON."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = sa.MetaData()
TABLES: dict[str, sa.Table] = {}
STAGES: dict[int, tuple[str, ...]] = {
    1: ("workspaces", "users", "workspace_memberships", "sessions", "login_flows"),
    2: ("missions", "mission_drafts", "mission_revisions", "mission_acceptances", "rovers", "rover_revisions"),
    3: ("runs", "preparation_jobs", "jobs", "run_events", "idempotency_requests", "audit_events", "worker_heartbeats"),
    4: (
        "artifact_blobs",
        "evidence",
        "evidence_edges",
        "agent_invocations",
        "tool_receipts",
        "agent_actions",
        "role_results",
        "scientific_operations",
    ),
    5: (
        "target_profiles",
        "candidates",
        "qualifications",
        "compatibility_assessments",
        "critiques",
        "reviews",
        "display_layers",
        "screenings",
    ),
    6: (
        "verification_tests",
        "test_results",
        "portfolios",
        "passports",
        "export_artifacts",
        "scenario_bindings",
        "dataset_locks",
    ),
}
IMMUTABLE = frozenset(
    {
        "mission_drafts",
        "mission_revisions",
        "mission_acceptances",
        "rover_revisions",
        "run_events",
        "evidence",
        "evidence_edges",
        "tool_receipts",
        "reviews",
        "verification_tests",
        "test_results",
        "passports",
        "export_artifacts",
    }
)


def _table(name: str, *extra: sa.Column[Any] | sa.Constraint) -> sa.Table:
    table = sa.Table(
        name,
        metadata,
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("document_json", JSONB, nullable=False),
        *extra,
        sa.UniqueConstraint("workspace_id", "id", name=f"uq_{name}_workspace_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
    )
    sa.Index(f"ix_{name}_workspace_created", table.c.workspace_id, table.c.created_at)
    TABLES[name] = table
    return table


workspaces = sa.Table(
    "workspaces",
    metadata,
    sa.Column("id", UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)
TABLES["workspaces"] = workspaces


def _uuid(name: str, nullable: bool = True) -> sa.Column[Any]:
    return sa.Column(name, UUID(as_uuid=False), nullable=nullable)


def _text(name: str, nullable: bool = True) -> sa.Column[Any]:
    return sa.Column(name, sa.Text, nullable=nullable)


def _int(name: str, default: str | None = None) -> sa.Column[Any]:
    return sa.Column(name, sa.Integer, nullable=default is None, server_default=default)


def _run_columns() -> list[sa.Column[Any] | sa.Constraint]:
    return [
        _uuid("run_id", False),
        _text("mode", False),
        sa.ForeignKeyConstraint(["workspace_id", "run_id"], ["runs.workspace_id", "runs.id"]),
        sa.CheckConstraint("mode IN ('synthetic','replay','live')"),
    ]


_table("users", _text("issuer", False), _text("subject", False), sa.UniqueConstraint("issuer", "subject"))
_table(
    "workspace_memberships",
    _uuid("user_id", False),
    _text("role", False),
    sa.UniqueConstraint("workspace_id", "user_id"),
    sa.CheckConstraint("role IN ('OWNER','EDITOR','VIEWER')"),
)
_table(
    "sessions",
    _text("token_hash", False),
    _uuid("user_id", False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("token_hash"),
)
_table("login_flows", _text("state_hash", False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
_table("missions", _text("name"), _int("revision", "1"), _uuid("current_draft_revision_id"))
for _name in ("mission_drafts", "mission_revisions"):
    _table(
        _name,
        _uuid("mission_id", False),
        _int("revision", "1"),
        _text("content_sha256"),
        sa.UniqueConstraint("workspace_id", "mission_id", "revision"),
        sa.ForeignKeyConstraint(["workspace_id", "mission_id"], ["missions.workspace_id", "missions.id"]),
    )
_table(
    "mission_acceptances",
    _uuid("mission_revision_id", False),
    _text("accepted_by"),
    sa.UniqueConstraint("workspace_id", "mission_revision_id"),
    sa.ForeignKeyConstraint(
        ["workspace_id", "mission_revision_id"], ["mission_revisions.workspace_id", "mission_revisions.id"]
    ),
)
_table("rovers", _text("name"), _int("revision", "1"))
_table(
    "rover_revisions",
    _uuid("rover_id", False),
    _int("revision", "1"),
    _text("content_sha256"),
    sa.UniqueConstraint("workspace_id", "rover_id", "revision"),
    sa.ForeignKeyConstraint(["workspace_id", "rover_id"], ["rovers.workspace_id", "rovers.id"]),
)
_table(
    "runs",
    _uuid("mission_revision_id", False),
    _uuid("rover_revision_id"),
    _text("mode", False),
    _text("state", False),
    _int("revision", "1"),
    sa.Column("last_event_seq", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
    _text("config_sha256"),
    sa.ForeignKeyConstraint(
        ["workspace_id", "mission_revision_id"], ["mission_revisions.workspace_id", "mission_revisions.id"]
    ),
    sa.ForeignKeyConstraint(
        ["workspace_id", "rover_revision_id"], ["rover_revisions.workspace_id", "rover_revisions.id"]
    ),
    sa.UniqueConstraint("workspace_id", "id", "mode"),
    sa.CheckConstraint("mode IN ('synthetic','replay','live')"),
)
_table(
    "preparation_jobs",
    _uuid("mission_draft_revision_id", False),
    _text("mode", False),
    _text("status", False),
    _uuid("proposed_revision_id"),
    _int("revision", "1"),
    sa.ForeignKeyConstraint(
        ["workspace_id", "mission_draft_revision_id"], ["mission_drafts.workspace_id", "mission_drafts.id"]
    ),
)
jobs = _table(
    "jobs",
    _uuid("run_id"),
    _uuid("preparation_id"),
    _text("kind", False),
    _text("state", False),
    _int("priority", "0"),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    _int("attempt", "0"),
    _int("max_attempts", "3"),
    _uuid("lease_token"),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
    _text("input_hash", False),
    sa.CheckConstraint("(run_id IS NULL) <> (preparation_id IS NULL)", name="ck_jobs_one_context"),
    sa.CheckConstraint("state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','BLOCKED','CANCELLED')"),
    sa.CheckConstraint("attempt >= 0 AND max_attempts > 0"),
    sa.ForeignKeyConstraint(["workspace_id", "run_id"], ["runs.workspace_id", "runs.id"]),
    sa.ForeignKeyConstraint(
        ["workspace_id", "preparation_id"], ["preparation_jobs.workspace_id", "preparation_jobs.id"]
    ),
)
sa.Index(
    "ix_jobs_ready", jobs.c.priority.desc(), jobs.c.available_at, jobs.c.id, postgresql_where=jobs.c.state == "QUEUED"
)
sa.Index(
    "uq_jobs_active_work",
    jobs.c.workspace_id,
    jobs.c.kind,
    sa.func.coalesce(jobs.c.run_id, jobs.c.preparation_id),
    jobs.c.input_hash,
    unique=True,
    postgresql_where=jobs.c.state.in_(["QUEUED", "RUNNING"]),
)
_table(
    "run_events",
    *_run_columns(),
    sa.Column("seq", sa.BigInteger, nullable=False),
    _text("type", False),
    sa.UniqueConstraint("workspace_id", "run_id", "seq"),
)
_table(
    "idempotency_requests",
    _text("subject_id", False),
    _text("method", False),
    _text("path", False),
    _text("key", False),
    _text("body_hash", False),
    _int("status"),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("workspace_id", "subject_id", "method", "path", "key"),
)
_table("audit_events", _text("actor"), _text("action"), _uuid("object_id"))
_table(
    "worker_heartbeats",
    _text("worker_name", False),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
)
_table(
    "artifact_blobs",
    _text("sha256", False),
    _text("media_type", False),
    sa.Column("bytes", sa.BigInteger, nullable=False),
    _text("relative_path", False),
    sa.CheckConstraint("bytes >= 0"),
    sa.UniqueConstraint("workspace_id", "sha256"),
)
_table(
    "evidence",
    *_run_columns(),
    _text("kind", False),
    _text("artifact_sha256"),
    _text("algorithm_id"),
    _text("algorithm_version"),
    _text("parameters_sha256"),
    sa.UniqueConstraint("workspace_id", "run_id", "mode", "id"),
)
_table(
    "evidence_edges",
    _uuid("run_id", False),
    _text("mode", False),
    _uuid("parent_evidence_id", False),
    _uuid("child_evidence_id", False),
    _text("relation", False),
    sa.CheckConstraint("parent_evidence_id <> child_evidence_id"),
    sa.UniqueConstraint("workspace_id", "parent_evidence_id", "child_evidence_id", "relation"),
    sa.ForeignKeyConstraint(
        ["workspace_id", "run_id", "mode", "parent_evidence_id"],
        ["evidence.workspace_id", "evidence.run_id", "evidence.mode", "evidence.id"],
    ),
    sa.ForeignKeyConstraint(
        ["workspace_id", "run_id", "mode", "child_evidence_id"],
        ["evidence.workspace_id", "evidence.run_id", "evidence.mode", "evidence.id"],
    ),
)
_table(
    "agent_invocations",
    _uuid("run_id"),
    _uuid("preparation_id"),
    _text("role"),
    _text("status"),
    _text("input_hash"),
    sa.CheckConstraint("(run_id IS NULL) <> (preparation_id IS NULL)"),
)
_table(
    "tool_receipts",
    *_run_columns(),
    _uuid("invocation_id"),
    _text("tool_call_id"),
    _text("tool_name", False),
    _text("input_sha256"),
    _text("output_sha256"),
    _text("status", False),
    sa.UniqueConstraint("workspace_id", "invocation_id", "tool_call_id"),
)
for _name in ("agent_actions", "role_results", "scientific_operations"):
    _table(_name, *_run_columns(), _text("status"))
for _name in (
    "target_profiles",
    "candidates",
    "qualifications",
    "compatibility_assessments",
    "critiques",
    "reviews",
    "display_layers",
    "screenings",
):
    _extra: list[sa.Column[Any] | sa.Constraint] = [*_run_columns()]
    if _name == "candidates":
        _extra.extend([_text("name"), _text("origin"), _text("window_id")])
    elif _name == "qualifications":
        _extra.extend(
            [_uuid("candidate_id"), _text("requirement_id"), _int("evaluation_version", "1"), _text("status")]
        )
        _extra.append(
            sa.UniqueConstraint("workspace_id", "run_id", "candidate_id", "requirement_id", "evaluation_version")
        )
    _table(_name, *_extra)
_table(
    "verification_tests",
    *_run_columns(),
    _uuid("candidate_id", False),
    _int("test_revision", "1"),
    _text("constraints_sha256"),
    _int("attempt_number", "1"),
    _uuid("parent_test_id"),
    _text("strategy"),
    _text("search_status"),
)
_table(
    "test_results",
    *_run_columns(),
    _uuid("test_id", False),
    _text("outcome", False),
    _text("verifier_version"),
    sa.ForeignKeyConstraint(["workspace_id", "test_id"], ["verification_tests.workspace_id", "verification_tests.id"]),
)
_table("portfolios", *_run_columns())
_table(
    "passports",
    *_run_columns(),
    _int("revision", "1"),
    _text("manifest_sha256", False),
    _uuid("assurance_evidence_id", False),
    sa.UniqueConstraint("workspace_id", "run_id", "revision"),
    sa.ForeignKeyConstraint(
        ["workspace_id", "run_id", "mode", "assurance_evidence_id"],
        ["evidence.workspace_id", "evidence.run_id", "evidence.mode", "evidence.id"],
        name="fk_passports_assurance_scope",
    ),
)
_table(
    "export_artifacts",
    _uuid("passport_id", False),
    _text("format", False),
    _text("artifact_hash", False),
    _text("renderer_version", False),
    sa.UniqueConstraint("workspace_id", "passport_id", "format", "renderer_version"),
    sa.ForeignKeyConstraint(["workspace_id", "passport_id"], ["passports.workspace_id", "passports.id"]),
)
_table("scenario_bindings", _text("scenario_config_id", False), _text("dataset_lock_id"))
_table("dataset_locks", _text("lock_id", False), _text("sha256", False), _text("relative_path", False))


def migrate_stage(connection: sa.Connection, stage: int) -> None:
    """Run one forward-only schema stage; safe on seeded earlier revisions."""
    if stage == 1:
        connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    if stage in STAGES:
        metadata.create_all(connection, tables=[TABLES[name] for name in STAGES[stage]], checkfirst=True)
    if stage == 5:
        connection.execute(
            sa.text("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS earth_extent geometry(MultiPolygon,4326)")
        )
        connection.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_candidates_earth_extent ON candidates USING GIST(earth_extent)")
        )
    if stage == 7:
        connection.execute(
            sa.text("""
          CREATE OR REPLACE FUNCTION deny_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'immutable record: %', TG_TABLE_NAME USING ERRCODE='23514'; END; $$
        """)
        )
        for name, table in TABLES.items():
            if name == "workspaces":
                continue
            connection.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
            connection.execute(sa.text(f'DROP POLICY IF EXISTS workspace_scope ON "{name}"'))
            connection.execute(
                sa.text(f'''CREATE POLICY workspace_scope ON "{name}" USING
              (workspace_id::text = current_setting('app.workspace_id', true)) WITH CHECK
              (workspace_id::text = current_setting('app.workspace_id', true))''')
            )
            if name in IMMUTABLE:
                connection.execute(sa.text(f'DROP TRIGGER IF EXISTS immutable_guard ON "{name}"'))
                connection.execute(
                    sa.text(f'''CREATE TRIGGER immutable_guard BEFORE UPDATE OR DELETE ON "{name}"
                    FOR EACH ROW EXECUTE FUNCTION deny_immutable_change()''')
                )
            if "run_id" in table.c:
                connection.execute(
                    sa.text(f'CREATE INDEX IF NOT EXISTS "ix_{name}_run" ON "{name}" (workspace_id, run_id)')
                )
        connection.execute(
            sa.text("""
          CREATE OR REPLACE FUNCTION check_evidence_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN
            IF EXISTS (WITH RECURSIVE descendants(id) AS (
              SELECT NEW.child_evidence_id UNION
              SELECT e.child_evidence_id FROM evidence_edges e JOIN descendants d ON e.parent_evidence_id=d.id
              WHERE e.workspace_id=NEW.workspace_id
            ) SELECT 1 FROM descendants WHERE id=NEW.parent_evidence_id)
            THEN RAISE EXCEPTION 'evidence lineage cycle' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END; $$
        """)
        )
        connection.execute(sa.text("DROP TRIGGER IF EXISTS evidence_cycle_guard ON evidence_edges"))
        connection.execute(
            sa.text("""CREATE TRIGGER evidence_cycle_guard BEFORE INSERT ON evidence_edges
           FOR EACH ROW EXECUTE FUNCTION check_evidence_cycle()""")
        )
