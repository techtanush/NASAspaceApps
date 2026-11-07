"""SSE framing over durable events, with heartbeat comments outside the cursor."""

from __future__ import annotations

import json
from typing import Any

from analogforge.db.store import PersistenceError


def event_cursor(after: int = 0, last_event_id: str | None = None) -> int:
    if after < 0:
        raise PersistenceError("REQUEST_INVALID", "Event cursor cannot be negative")
    if last_event_id is None:
        return after
    try:
        header = int(last_event_id)
    except ValueError as exc:
        raise PersistenceError("REQUEST_INVALID", "Last-Event-ID must be a nonnegative sequence") from exc
    if header < 0:
        raise PersistenceError("REQUEST_INVALID", "Last-Event-ID cannot be negative")
    return max(after, header)


def frame_event(event: dict[str, Any]) -> str:
    event_type = event["event_type"]
    if "\n" in event_type or "\r" in event_type:
        raise PersistenceError("MODEL_OUTPUT_INVALID", "Event type contains a newline")
    return f"id:{event['seq']}\nevent:{event_type}\ndata:{json.dumps(event, separators=(',', ':'))}\n\n"


def heartbeat() -> str:
    return ": heartbeat\n\n"
