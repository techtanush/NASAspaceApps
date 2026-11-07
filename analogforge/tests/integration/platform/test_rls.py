"""PLT-04 defense in depth: scoped SQL under a non-owner, non-superuser role."""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from analogforge.db.store import Store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
def test_rls_prevents_cross_workspace_direct_sql(platform_store: Store) -> None:
    first, run = seed_run(platform_store)
    second, other = seed_run(platform_store)
    role = "rls_" + uuid4().hex
    with platform_store.engine.begin() as connection:
        connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
        connection.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
        connection.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'))
    with platform_store.engine.begin() as connection:
        connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
        connection.execute(sa.text("SELECT set_config('app.workspace_id', :workspace, true)"), {"workspace": second})
        ids = set(connection.execute(sa.text("SELECT id::text FROM runs")).scalars())
        assert other["id"] in ids and run["id"] not in ids
        changed = connection.execute(sa.text("UPDATE runs SET state='FAILED' WHERE id=:id"), {"id": run["id"]})
        assert changed.rowcount == 0
    with pytest.raises(DBAPIError):
        with platform_store.engine.begin() as connection:
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            connection.execute(
                sa.text("SELECT set_config('app.workspace_id', :workspace, true)"), {"workspace": second}
            )
            connection.execute(
                sa.text("""INSERT INTO missions(id,workspace_id,document_json)
               VALUES (:id,:workspace,'{}'::jsonb)"""),
                {"id": str(uuid4()), "workspace": first},
            )
