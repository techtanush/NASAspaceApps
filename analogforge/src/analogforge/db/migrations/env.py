"""Alembic environment uses an explicit connection, never ambient secrets."""

from alembic import context

from analogforge.db.schema import metadata

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use Store.migrate() or supply an explicit migration connection")
context.configure(connection=connection, target_metadata=metadata)
with context.begin_transaction():
    context.run_migrations()
