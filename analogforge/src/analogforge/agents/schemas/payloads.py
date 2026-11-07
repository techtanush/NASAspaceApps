"""Strict task-discriminated terminal payloads; numeric claims remain receipt-owned."""

from typing import Literal
from uuid import UUID

from analogforge.ports.common import Confidence, FailureCategory, PortModel, QualificationStatus, VerificationOutcome
from analogforge.ports.science_payloads import RouteStrategy


class DirectorPayload(PortModel):
    dispatch_role: str | None
    dispatch_task_kind: str | None
    dispatch_input_ids: list[UUID]
    requirement_ids: list[str]
    expected_evidence_kinds: list[str]
    priority: Literal["BLOCKER", "REQUIRED", "OPTIONAL"]
    stop_reason: str | None
    portfolio_revision_id: UUID | None


class ConsistencyIssue(PortModel):
    code: str
    requirement_ids: list[str]
    message: str


class RequirementsPayload(PortModel):
    contract_revision_id: UUID
    contract_hash: str
    requirement_ids: list[str]
    validation_receipt_id: UUID
    unchanged: Literal[True]
    consistency_issues: list[ConsistencyIssue]
    new_contract_required: bool


class HardLimit(PortModel):
    field_path: str
    value: float | None
    unit: str
    source_ref: str


class CapabilityMapping(PortModel):
    requirement_id: str
    support: Literal["DECLARED_SUPPORTED", "CONFLICT", "UNKNOWN"]
    profile_fields: list[str]
    evidence_ids: list[UUID]
    limitation: str | None


class MissingInput(PortModel):
    field_path: str
    affects_requirement_ids: list[str]
    consequence: str


class ConstraintReference(PortModel):
    requirement_id: str
    profile_field_paths: list[str]
    constraint_id: str


class RoverPayload(PortModel):
    rover_revision_id: UUID
    validation_receipt_id: UUID
    hard_limit_summary: list[HardLimit]
    capability_mapping: list[CapabilityMapping]
    compatibility_revision_id: UUID | None
    energy_model_revision_id: UUID | None
    missing_engineering_inputs: list[MissingInput]
    benchmark_constraint_refs: list[ConstraintReference]


class DimensionEvidence(PortModel):
    requirement_id: str
    availability: Literal["AVAILABLE", "PROXY_ONLY", "NO_COVERAGE", "UNSUPPORTED", "UNRESOLVED"]
    evidence_ids: list[UUID]
    measurement_spec_id: str | None
    limitation: str | None


class TargetPayload(PortModel):
    target_revision_id: UUID
    target_profile_revision_id: UUID | None
    coverage_receipt_ids: list[UUID]
    source_evidence_ids: list[UUID]
    measurement_evidence_ids: list[UUID]
    dimension_evidence: list[DimensionEvidence]
    geometry_validation_receipt_id: UUID
    comparison_ready: bool


class ShortlistItem(PortModel):
    candidate_revision_id: UUID
    analysis_revision_id: UUID | None
    screen_rank: int
    evidence_ids: list[UUID]
    supported_requirement_ids: list[str]
    unknown_requirement_ids: list[str]
    known_analog_reference: bool
    selection_reason_code: Literal[
        "FEATURE_MATCH", "EVIDENCE_COMPLEMENT", "NOVEL_CANDIDATE", "CRITIC_ALTERNATIVE", "REPLAN_ALTERNATIVE"
    ]


class ExcludedCandidate(PortModel):
    candidate_revision_id: UUID
    reason_code: str
    evidence_ids: list[UUID]


class ScoutPayload(PortModel):
    search_region_set_id: str
    screening_receipt_id: UUID | None
    screened_region_count: int
    shortlist: list[ShortlistItem]
    excluded_candidate_refs: list[ExcludedCandidate]
    search_limitations: list[str]
    portfolio_revision_id: UUID | None
    discovery_exhausted: bool


class QualificationRow(PortModel):
    requirement_id: str
    comparison_receipt_id: UUID | None
    proposed_status: QualificationStatus
    evidence_ids: list[UUID]
    measurement_evidence_ids: list[UUID]
    basis: Literal["DIRECT", "DERIVED", "PROXY", "PHYSICAL_LIMITATION", "MISSING_EVIDENCE"]
    confidence: Confidence
    covered_subcriterion_ids: list[str]
    uncovered_subcriterion_ids: list[str]
    limitations: list[str]


class QualificationPayload(PortModel):
    candidate_revision_id: UUID
    qualification_draft_revision_id: UUID
    rows: list[QualificationRow]
    qualified_use_requirement_ids: list[str]
    partial_use_requirement_ids: list[str]
    unsupported_use_requirement_ids: list[str]
    portfolio_revision_id: UUID | None
    critic_review_required: Literal[True]


class RequiredRepair(PortModel):
    kind: Literal[
        "RECOMPUTE",
        "ACQUIRE_EVIDENCE_OR_DOWNGRADE",
        "CORRECT_METADATA",
        "RESTORE_CONTRACT",
        "NARROW_LANGUAGE",
        "REVIEW_ASSUMPTION",
        "INVESTIGATE_ALTERNATIVE",
        "RECORD_UNKNOWN",
    ]
    target_ids: list[str]
    success_condition: str


class Objection(PortModel):
    finding_id: UUID
    claim_id: UUID | None
    requirement_id: str | None
    evidence_ids: list[UUID]
    rule_code: str
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    observation: str
    required_repair: RequiredRepair
    resolved_by_receipt_ids: list[UUID]


class CriticPayload(PortModel):
    review_revision_id: UUID
    objections: list[Objection]
    accepted_claim_ids: list[UUID]
    gate_recommendation: Literal["CLEAR", "CLEAR_WITH_LIMITATIONS", "REPAIR_REQUIRED", "NO_SUPPORTED_RECOMMENDATION"]


class ConstraintMapping(PortModel):
    requirement_id: str
    benchmark_constraint_ids: list[str]
    treatment: Literal["VERIFIED_BY_TOOL", "DECLARED_ONLY", "GAP", "UNKNOWN"]
    limitation: str | None


class DesignerPayload(PortModel):
    candidate_revision_id: UUID
    test_revision_id: UUID | None
    strategy: RouteStrategy
    constraint_mapping: list[ConstraintMapping]
    compatibility_revision_id: UUID | None
    search_attempt_id: UUID | None
    proposed_route_revision_id: UUID | None
    search_termination: (
        Literal["ROUTE_FOUND", "EXHAUSTIVE_NO_ROUTE", "LIMIT_REACHED", "DATA_BLOCKED", "CANCELLED"] | None
    )
    unverified_requirement_ids: list[str]


class Repair(PortModel):
    kind: Literal[
        "NEW_ROUTE", "NEW_ZONE", "NEW_CANDIDATE", "COMPOSITE_PORTFOLIO", "DATA_REPAIR", "NEW_CONTRACT_REQUIRED"
    ]
    target_revision_ids: list[UUID]
    addresses_constraint_ids: list[str]
    preserved_contract_sha256: str
    strategy: RouteStrategy | None
    expected_check: str
    requires_new_run: bool


class VerificationPayload(PortModel):
    test_revision_id: UUID
    result_revision_id: UUID | None
    search_attempt_id: UUID | None
    outcome: VerificationOutcome
    primary_failure_category: FailureCategory | None
    secondary_failure_categories: list[FailureCategory]
    violated_constraint_ids: list[str]
    diagnosis_receipt_id: UUID | None
    repair: Repair | None
    stop_reason: str | None


class ClaimAnnotation(PortModel):
    claim_id: UUID
    display_text: str
    evidence_ids: list[UUID]
    assumption_ids: list[UUID]
    limitation_ids: list[UUID]
    claim_kind: Literal[
        "MEASURED",
        "DERIVED",
        "DECLARED",
        "ACCEPTED_ASSUMPTION",
        "PHYSICAL_GAP",
        "MISSING_EVIDENCE",
        "MODELED_VERIFICATION",
        "SEARCH_LIMITATION",
    ]


class PassportPayload(PortModel):
    passport_draft_revision_id: UUID
    source_run_revision: int
    selected_candidate_revision_ids: list[UUID]
    portfolio_revision_id: UUID | None
    claim_annotations: list[ClaimAnnotation]
    unresolved_issue_ids: list[UUID]
    not_verified_requirement_ids: list[str]
    export_artifact_ids: list[UUID]
    ready_to_publish: bool


PAYLOAD_MODELS: dict[str, type[PortModel]] = {
    "mission_director": DirectorPayload,
    "requirements": RequirementsPayload,
    "rover_systems": RoverPayload,
    "planetary_target": TargetPayload,
    "earth_scout": ScoutPayload,
    "qualification": QualificationPayload,
    "scientific_critic": CriticPayload,
    "test_designer": DesignerPayload,
    "verification_replanning": VerificationPayload,
    "evidence_passport": PassportPayload,
}
