"""PLT-01: real PostgreSQL/PostGIS forward migrations and immutable assurance constraints."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa

from analogforge.db.schema import STAGES, TABLES
from analogforge.db.store import PersistenceError, Store


@pytest.fixture
def platform_store() -> Iterator[Store]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required for executed PostgreSQL gates")
    store = Store(database_url)
    store.migrate()
    yield store
    store.close()


def seed_run(store: Store, workspace_id: str | None = None) -> tuple[str, dict[str, Any]]:
    workspace_id = workspace_id or str(uuid4())
    store.ensure_workspace(workspace_id, "Persistence test")
    with store.transaction(workspace_id) as unit:
        mission = unit.create("missions", {"name": "Persistence mission"})
        revision = unit.create(
            "mission_revisions",
            {"mission_id": mission["id"], "revision": 1, "content_sha256": "a" * 64, "accepted_at": None},
        )
        run = unit.create(
            "runs",
            {
                "mission_revision_id": revision["id"],
                "rover_revision_id": None,
                "mode": "synthetic",
                "state": "VALIDATING",
                "config_sha256": "b" * 64,
            },
        )
    return workspace_id, run


@pytest.mark.db
def test_migrations_all_tables_constraints_indexes(platform_store: Store) -> None:
    inspector = sa.inspect(platform_store.engine)
    assert set(TABLES) <= set(inspector.get_table_names())
    passport = {column["name"]: column for column in inspector.get_columns("passports")}
    assert passport["assurance_evidence_id"]["nullable"] is False
    assert any(foreign["name"] == "fk_passports_assurance_scope" for foreign in inspector.get_foreign_keys("passports"))
    assert any(index["name"] == "ix_jobs_ready" for index in inspector.get_indexes("jobs"))
    assert any(index["name"] == "ix_candidates_earth_extent" for index in inspector.get_indexes("candidates"))
    with platform_store.engine.connect() as connection:
        assert connection.execute(sa.text("SELECT postgis_version()")).scalar_one()
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "0007"


@pytest.mark.db
def test_migration_empty_and_seeded_previous_schema(platform_store: Store) -> None:
    # A disposable database proves the initial and incremental path without touching shared data.
    database = "migration_" + uuid4().hex
    with platform_store.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            sa.text(f'''CREATE DATABASE "{database}" TEMPLATE template0 ENCODING 'UTF8'
            LC_COLLATE 'C' LC_CTYPE 'C' ''')
        )
    url = platform_store.engine.url
    isolated = Store(url.set(database=database).render_as_string(hide_password=False))
    try:
        isolated.migrate("0002")
        workspace = str(uuid4())
        isolated.ensure_workspace(workspace, "Previous revision")
        with isolated.transaction(workspace) as unit:
            mission = unit.create("missions", {"name": "Must survive migration"})
        isolated.migrate("head")
        passport_columns = {column["name"]: column for column in sa.inspect(isolated.engine).get_columns("passports")}
        assert passport_columns["assurance_evidence_id"]["nullable"] is False
        with isolated.transaction(workspace) as unit:
            assert unit.require("missions", mission["id"])["name"] == "Must survive migration"
        assert set(name for group in STAGES.values() for name in group) <= set(
            sa.inspect(isolated.engine).get_table_names()
        )
    finally:
        isolated.close()


@pytest.mark.db
def test_immutable_revision_and_assurance_fk(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with pytest.raises(PersistenceError, match="assurance"):
        with platform_store.transaction(workspace) as unit:
            unit.create(
                "passports",
                {
                    "run_id": run["id"],
                    "mode": "synthetic",
                    "revision": 1,
                    "manifest_sha256": "c" * 64,
                    "assurance_evidence_id": None,
                },
            )
    with platform_store.transaction(workspace) as unit:
        revision = unit.require("mission_revisions", run["mission_revision_id"])
        with pytest.raises(PersistenceError, match="superseding"):
            unit.replace("mission_revisions", revision["id"], revision)
