"""Contract hashing delegates exclusively to RFC8785 port functions."""

from typing import Any

from analogforge.ports.hashing import canonical_sha256

MISSION_EXCLUSIONS = frozenset(
    {"schema_version", "id", "mission_id", "workspace_id", "revision", "created_at", "accepted_at", "content_sha256"}
)
ROVER_EXCLUSIONS = frozenset(
    {"schema_version", "id", "rover_id", "workspace_id", "revision", "created_at", "content_sha256"}
)


def content_hash(value: dict[str, Any], kind: str) -> str:
    exclusions = MISSION_EXCLUSIONS if kind == "mission" else ROVER_EXCLUSIONS
    return canonical_sha256({k: v for k, v in value.items() if k not in exclusions and not k.startswith("_")})


def canonical_hash(value: Any, exclusions: frozenset[str] = frozenset()) -> str:
    return canonical_sha256(
        {k: v for k, v in value.items() if k not in exclusions} if isinstance(value, dict) else value
    )
