"""Execute a command and retain its response inside the same database transaction."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from analogforge.db.store import UnitOfWork, document
from analogforge.ports.hashing import canonical_sha256


@dataclass(frozen=True)
class IdempotencyScope:
    subject_id: str
    method: str
    path: str
    key: str


def execute(
    unit: UnitOfWork,
    scope: IdempotencyScope,
    body: Mapping[str, Any],
    command: Callable[[], tuple[int, dict[str, Any]]],
) -> tuple[int, dict[str, Any]]:
    previous = unit.idempotency_begin(
        scope.subject_id, scope.method, scope.path, scope.key, canonical_sha256(document(body))
    )
    if previous is not None:
        return previous
    status, response = command()
    unit.idempotency_complete(scope.subject_id, scope.method, scope.path, scope.key, status, response)
    return status, response
