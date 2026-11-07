"""Server-issued immutable task context; no credentials or lease token reaches a model."""

from typing import Any, Literal
from uuid import UUID

from analogforge.ports.common import PortModel, RuntimeMode


class AgentTask(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    workspace_id: UUID
    run_id: UUID
    invocation_id: UUID
    role_key: str
    task_kind: str
    runtime_mode: RuntimeMode
    expected_run_revision: int
    contract_revision_id: UUID
    rover_revision_id: UUID | None
    contract_hash: str
    rover_hash: str | None
    input_evidence_ids: list[UUID]
    accepted_assumption_ids: list[UUID]
    allowed_actions: list[str]
    budget: dict[str, float]
    payload: dict[str, Any]


class PreparationTask(PortModel):
    preparation_id: UUID
    workspace_id: UUID
    mission_id: UUID
    draft_revision_id: UUID
    invocation_id: UUID
    mode: RuntimeMode
    task_kind: Literal["draft_contract", "revise_draft"]
    mission_text: str
    allowed_actions: list[str]
    payload: dict[str, Any]
