"""Shared SQLAlchemy metadata and explicit engine lifecycle."""

from sqlalchemy import Engine

from analogforge.db.schema import metadata
from analogforge.db.store import Store


def database_engine(store: Store) -> Engine:
    """Expose the configured pool to migrations and operator tooling."""
    return store.engine


__all__ = ["database_engine", "metadata"]
