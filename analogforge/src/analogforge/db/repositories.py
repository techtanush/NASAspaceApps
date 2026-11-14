"""Repositories retain the caller's scoped transaction; they cannot open global queries."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from analogforge.db.models import table_for
from analogforge.db.store import UnitOfWork


class Repository:
    def __init__(self, unit: UnitOfWork, kind: str) -> None:
        table_for(kind)
        self.unit, self.kind = unit, kind

    def get(self, entity_id: str | UUID) -> dict[str, Any] | None:
        return self.unit.get(self.kind, entity_id)

    def require(self, entity_id: str | UUID, *, lock: bool = False) -> dict[str, Any]:
        return self.unit.require(self.kind, entity_id, lock=lock)

    def list(self, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.unit.list(self.kind, filters)

    def create(self, document: Mapping[str, Any]) -> dict[str, Any]:
        return self.unit.create(self.kind, document)

    def replace(self, entity_id: str | UUID, document: Mapping[str, Any], expected_revision: int) -> dict[str, Any]:
        return self.unit.replace(self.kind, entity_id, document, expected_revision)
