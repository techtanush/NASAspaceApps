"""Opaque identifiers and timestamps for persisted envelopes."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def envelope(workspace_id: str, run_id: str, mode: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "id": new_id(),
        "workspace_id": workspace_id,
        "run_id": run_id,
        "mode": mode,
        "created_at": utc_now(),
    }
