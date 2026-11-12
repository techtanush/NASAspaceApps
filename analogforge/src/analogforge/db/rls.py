"""Transaction-local workspace identity for non-owner PostgreSQL RLS roles."""

from uuid import UUID

import sqlalchemy as sa


def configure_workspace(connection: sa.Connection, workspace_id: str | UUID) -> str:
    scoped = str(UUID(str(workspace_id)))
    connection.execute(sa.text("SELECT set_config('app.workspace_id', :workspace, true)"), {"workspace": scoped})
    return scoped
