"""FROZEN CONTRACT KIT FILE - analogforge.ports.assurance_models

Generated from architecture files/contracts/scientific-assurance.schema.json by datamodel-code-generator and
normalized for the kit. DO NOT EDIT in any branch. Every branch materializes this
file byte-identically with `architecture files/contracts/kit/materialize.py`.
A change requires a recorded contract change (see architecture 35).
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, constr


class Gate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    gate_id: Literal[
        "SC-01",
        "SC-02",
        "SC-03",
        "SC-04",
        "SC-05",
        "SC-06",
        "SC-07",
        "SC-08",
        "SC-09",
        "SC-10",
        "SC-11",
        "SC-12",
        "SC-13",
        "SC-14",
        "SC-15",
    ]
    outcome: Literal["SATISFIED", "UNSATISFIED", "NOT_ASSESSED", "NOT_APPLICABLE"]
    reason: constr(min_length=1)
    evidence_ids: list[UUID]


class Claim(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    claim_id: constr(min_length=1)
    claim_type: Literal["QUALIFICATION", "VERIFICATION", "DISCOVERY", "CONTEXT"]
    requirement_id: constr(min_length=1) | None
    candidate_ids: list[UUID]
    scope: constr(min_length=1)
    disposition: Literal[
        "SUPPORTED", "LIMITED", "UNSUPPORTED", "UNKNOWN", "GAP", "REJECTED"
    ]
    qualification_status: Literal["PASS", "PARTIAL", "FAIL", "GAP", "UNKNOWN"] | None
    verification_status: Literal["PASS", "FAIL", "INCONCLUSIVE"] | None
    validation_level: Literal["S0", "S1", "S2", "S3", "S4"]
    evidence_ids: list[UUID]
    assumption_evidence_ids: list[UUID]
    gates: list[Gate] = Field(..., max_length=15, min_length=15)
    permitted_statement: constr(min_length=1)
    limitations: list[constr(min_length=1)]


class ScientificAssuranceArtifact(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    audit_id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["synthetic", "replay", "live"]
    created_at: AwareDatetime
    snapshot_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    mission_content_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    rover_content_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    dataset_policy_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    acquired_manifest_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    algorithm_lock_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    assurance_policy_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    critique_evidence_ids: list[UUID]
    claims: list[Claim] = Field(..., min_length=1)
    publication: Literal["ALLOWED", "LIMITED", "BLOCKED"]
    blocking_issue_codes: list[constr(min_length=1)]
    limitations: list[constr(min_length=1)]
