"""Immutable rover revisions; declared capability is not observed performance."""

from __future__ import annotations

from typing import Any

from analogforge.api.errors import ApiError
from analogforge.application.missions import check_revision, now, uid
from analogforge.domain.validators import validate_rover_input
from analogforge.ports.domain_models import RoverProfile
from analogforge.ports.hashing import canonical_sha256


def create(
    uow: Any,
    workspace_id: str,
    profile: dict[str, Any],
    rover_id: str | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    violations = validate_rover_input(profile)
    if violations:
        raise ApiError(
            "INPUT_INVALID",
            "The rover capabilities are inconsistent.",
            details={"violations": [issue.as_dict() for issue in violations]},
        )
    rover_id = rover_id or uid()
    revision = 1
    if expected_revision is not None:
        header = uow.require("rovers", rover_id)
        check_revision(header, expected_revision)
        revision = expected_revision + 1
    result = RoverProfile.model_validate(
        {
            "schema_version": "1.0",
            "id": uid(),
            "rover_id": rover_id,
            "workspace_id": workspace_id,
            "revision": revision,
            "created_at": now(),
            "content_sha256": canonical_sha256(profile),
            **profile,
        }
    ).model_dump(mode="json")
    header = {
        "id": rover_id,
        "workspace_id": workspace_id,
        "revision": revision,
        "latest_revision_id": result["id"],
        "name": result["name"],
    }
    if expected_revision is None:
        uow.create("rovers", header)
    uow.create("rover_revisions", result)
    if expected_revision is not None:
        uow.replace("rovers", rover_id, header, expected_revision)
    return result
