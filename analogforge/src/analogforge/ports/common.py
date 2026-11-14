"""FROZEN CONTRACT KIT FILE - analogforge.ports.common

Base types shared by every port module. DO NOT EDIT in any branch.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuntimeMode = Literal["live", "replay", "synthetic"]
Body = Literal["EARTH", "MOON", "MARS"]
EvidenceKind = Literal[
    "SOURCE", "DERIVED", "COMPARISON", "VERIFICATION", "CRITIQUE", "ASSUMPTION", "REPLAY"
]
QualificationStatus = Literal["PASS", "PARTIAL", "FAIL", "GAP", "UNKNOWN"]
VerificationOutcome = Literal["PASS", "FAIL", "INCONCLUSIVE"]
FailureCategory = Literal["ROUTE", "ROVER", "ANALOG", "DATA", "REQUIREMENT", "SEARCH_LIMIT", "SYSTEM"]
SearchStatus = Literal["FOUND", "EXHAUSTIVE_INFEASIBLE", "BUDGET_EXHAUSTED", "NOT_RUN", "ERROR"]
Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNASSESSED"]
SHA256_PATTERN = r"^[a-f0-9]{64}$"


class PortModel(BaseModel):
    """Base for every port model: strict, immutable, finite numbers only."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class EvidenceRef(PortModel):
    """Reference to evidence: EITHER a draft in the same ScienceComputationResult (local_key)
    OR an existing persisted EvidenceRecord supplied in ScienceRequest.input_evidence."""

    local_key: str | None = None
    evidence_id: UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> EvidenceRef:
        if (self.local_key is None) == (self.evidence_id is None):
            raise ValueError("EvidenceRef needs exactly one of local_key or evidence_id")
        return self


class ScienceIssue(PortModel):
    code: str  # canonical code from contracts/error-codes.json or a qualification reason_code
    detail_code: str | None = None
    message: str = Field(min_length=1)
    retryable: bool = False
    affected_requirement_ids: list[str] = Field(default_factory=list)
    scope: str | None = None


__all__ = [
    "SHA256_PATTERN",
    "Body",
    "Confidence",
    "EvidenceKind",
    "EvidenceRef",
    "FailureCategory",
    "PortModel",
    "QualificationStatus",
    "RuntimeMode",
    "ScienceIssue",
    "SearchStatus",
    "VerificationOutcome",
]
