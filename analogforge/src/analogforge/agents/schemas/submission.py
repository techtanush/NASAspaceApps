"""Strict common submission wrapper with role-selected payload validation."""

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from analogforge.agents.schemas.payloads import PAYLOAD_MODELS
from analogforge.ports.common import PortModel


class RoleIssue(PortModel):
    code: str
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    requirement_id: str | None
    evidence_ids: list[UUID]
    message: str
    recommended_action: str | None


class RoleSubmission(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    role_key: str
    task_kind: str
    disposition: Literal["COMPLETE", "NEEDS_EVIDENCE", "NEEDS_USER_REVIEW", "NO_VALID_ACTION", "BUDGET_EXHAUSTED"]
    summary: str = Field(max_length=800)
    evidence_ids: list[UUID]
    assumption_ids: list[UUID]
    issues: list[RoleIssue]
    next_action: str | None
    payload: dict[str, Any]

    def validate_payload(self) -> None:
        if self.role_key not in PAYLOAD_MODELS:
            raise ValueError("Unregistered role")
        PAYLOAD_MODELS[self.role_key].model_validate(self.payload)
