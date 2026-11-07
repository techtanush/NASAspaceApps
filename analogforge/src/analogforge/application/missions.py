"""Mission drafts, scientific revisions and explicit acceptance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from analogforge.api.errors import ApiError
from analogforge.domain.validators import validate_mission_content
from analogforge.ports.domain_models import MissionTestContract
from analogforge.ports.hashing import canonical_sha256


def now() -> str:
    return datetime.now(UTC).isoformat()


def uid() -> str:
    return str(uuid4())


def check_revision(document: dict[str, Any], expected: int) -> None:
    if document["revision"] != expected:
        raise ApiError(
            "REVISION_CONFLICT",
            "The record has changed. Reload before submitting.",
            409,
            details={"current_revision": document["revision"]},
        )


def validate_content(content: dict[str, Any]) -> None:
    if content.get("requirements"):
        violations = [issue for issue in validate_mission_content(content) if issue.severity == "ERROR"]
        if violations:
            raise ApiError(
                "INPUT_INVALID",
                "The mission requirements are inconsistent.",
                details={"violations": [issue.as_dict() for issue in violations]},
            )
    target = content["target"]
    west, south, east, north = target["bbox"]
    if not (-90 <= south < north <= 90) or west == east:
        raise ApiError(
            "INPUT_INVALID", "Target bounds must describe a nonempty region.", details={"field": "target.bbox"}
        )
    bounds = (-180, 180) if target["longitude_convention"] == "NEG180_180" else (0, 360)
    if not (bounds[0] <= west <= bounds[1] and bounds[0] <= east <= bounds[1]):
        raise ApiError("INPUT_INVALID", "Longitude bounds disagree with the declared convention.")
    ids: set[str] = set()
    for row in content.get("requirements", []):
        if row["id"] in ids:
            raise ApiError("INPUT_INVALID", "Requirement identifiers must be unique.")
        ids.add(row["id"])
        if row["lower"] is not None and row["upper"] is not None and row["lower"] > row["upper"]:
            raise ApiError("INPUT_INVALID", "Requirement bounds are reversed.")
        band = row["parameters"]["slope_band_deg"]
        if band is not None and (len(band) != 2 or band[0] >= band[1]):
            raise ApiError("INPUT_INVALID", "Slope bands require increasing lower and upper bounds.")


def create(uow: Any, workspace_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    validate_content(draft)
    mission_id, draft_id = uid(), uid()
    document = {
        "id": mission_id,
        "workspace_id": workspace_id,
        "revision": 1,
        "name": draft["name"],
        "current_draft_id": draft_id,
        "current_contract_id": None,
        "accepted_contract_id": None,
    }
    uow.create("missions", document)
    uow.create(
        "mission_drafts",
        {
            "id": draft_id,
            "workspace_id": workspace_id,
            "mission_id": mission_id,
            "revision": 1,
            "created_at": now(),
            "draft": draft,
        },
    )
    return document


def save_draft(uow: Any, mission_id: str, body: dict[str, Any]) -> dict[str, Any]:
    mission = uow.require("missions", mission_id)
    check_revision(mission, body["expected_revision"])
    validate_content(body["draft"])
    draft = {
        "id": uid(),
        "workspace_id": mission["workspace_id"],
        "mission_id": mission_id,
        "revision": mission["revision"] + 1,
        "created_at": now(),
        "draft": body["draft"],
    }
    uow.create("mission_drafts", draft)
    uow.replace(
        "missions",
        mission_id,
        {**mission, "revision": draft["revision"], "name": body["draft"]["name"], "current_draft_id": draft["id"]},
        body["expected_revision"],
    )
    return draft


def propose(uow: Any, mission_id: str, content: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    mission = uow.require("missions", mission_id)
    check_revision(mission, expected_revision)
    validate_content(content)
    revision = {
        "schema_version": "1.0",
        "id": uid(),
        "mission_id": mission_id,
        "workspace_id": mission["workspace_id"],
        "revision": expected_revision + 1,
        "created_at": now(),
        "accepted_at": None,
        "content_sha256": canonical_sha256(content),
        **content,
    }
    revision = MissionTestContract.model_validate(revision).model_dump(mode="json")
    uow.create("mission_revisions", revision)
    uow.replace(
        "missions",
        mission_id,
        {**mission, "revision": revision["revision"], "current_contract_id": revision["id"]},
        expected_revision,
    )
    return revision


def accepted_contract(uow: Any, revision_id: str) -> dict[str, Any]:
    contract = uow.require("mission_revisions", revision_id)
    records = uow.list("mission_acceptances", {"mission_revision_id": revision_id})
    return {**contract, "accepted_at": records[0]["accepted_at"] if records else None}


def accept(uow: Any, mission_id: str, body: dict[str, Any], actor_id: str) -> dict[str, Any]:
    mission = uow.require("missions", mission_id)
    check_revision(mission, body["expected_revision"])
    contract = uow.require("mission_revisions", body["revision_id"])
    if contract["mission_id"] != mission_id or mission["current_contract_id"] != contract["id"]:
        raise ApiError("REVISION_CONFLICT", "Accept only the current displayed scientific revision.", 409)
    existing = uow.list("mission_acceptances", {"mission_revision_id": contract["id"]})
    accepted_at = existing[0]["accepted_at"] if existing else now()
    if not existing:
        uow.create(
            "mission_acceptances",
            {
                "id": uid(),
                "workspace_id": mission["workspace_id"],
                "mission_revision_id": contract["id"],
                "actor_id": actor_id,
                "accepted_at": accepted_at,
            },
        )
    uow.replace(
        "missions",
        mission_id,
        {**mission, "accepted_contract_id": contract["id"], "revision": mission["revision"] + 1},
        body["expected_revision"],
    )
    return {**contract, "accepted_at": accepted_at}
