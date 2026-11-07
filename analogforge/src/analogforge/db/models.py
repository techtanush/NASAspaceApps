"""Authoritative named table registry, including private transport aliases."""

from sqlalchemy import Table

from analogforge.db.schema import IMMUTABLE, TABLES
from analogforge.db.store import ALIASES, PersistenceError


def table_for(kind: str) -> Table:
    name = ALIASES.get(kind, kind)
    if name not in TABLES:
        raise PersistenceError("INPUT_INVALID", "Unknown persisted record kind")
    return TABLES[name]


__all__ = ["IMMUTABLE", "TABLES", "table_for"]
