"""Durable event publication and replay, separate from SSE transport framing."""

from collections.abc import Mapping
from typing import Any

from analogforge.db.store import Store, UnitOfWork


def append(unit: UnitOfWork, run_id: str, event_type: str, payload: Mapping[str, Any], mode: str) -> dict[str, Any]:
    return unit.append_event(run_id, event_type, payload, mode)


def replay(store: Store, workspace_id: str, run_id: str, after: int = 0) -> list[dict[str, Any]]:
    return store.events(workspace_id, run_id, after)
