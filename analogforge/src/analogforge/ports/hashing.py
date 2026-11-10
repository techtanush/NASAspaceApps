"""FROZEN CONTRACT KIT FILE - analogforge.ports.hashing

The ONE canonical hashing implementation (RFC 8785 JCS + SHA-256) used by every branch.
Do not reimplement canonical hashing elsewhere. DO NOT EDIT in any branch.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import rfc8785
from pydantic import BaseModel


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number cannot be canonicalized")
    if isinstance(value, dict):
        for v in value.values():
            _reject_nonfinite(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _reject_nonfinite(v)


def canonical_json_bytes(value: Any) -> bytes:
    """RFC 8785 canonical UTF-8 bytes. Accepts JSON-compatible values or a pydantic model."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    _reject_nonfinite(value)
    return rfc8785.dumps(value)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def model_sha256(model: BaseModel, exclude: Iterable[str] = ()) -> str:
    """Canonical hash of a model, excluding top-level fields (e.g. ids, timestamps)."""
    data = model.model_dump(mode="json", exclude=set(exclude))
    return canonical_sha256(data)


MISSION_CONTENT_EXCLUDE = frozenset(
    {"schema_version", "id", "mission_id", "workspace_id", "revision", "created_at", "accepted_at", "content_sha256"}
)
ROVER_CONTENT_EXCLUDE = frozenset(
    {"schema_version", "id", "rover_id", "workspace_id", "revision", "created_at", "content_sha256"}
)


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "MISSION_CONTENT_EXCLUDE",
    "ROVER_CONTENT_EXCLUDE",
    "bytes_sha256",
    "canonical_json_bytes",
    "canonical_sha256",
    "file_sha256",
    "model_sha256",
]
