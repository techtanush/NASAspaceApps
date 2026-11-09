"""FROZEN CONTRACT KIT FILE - analogforge.ports.domain_models

Generated from architecture files/contracts/domain.schema.json by datamodel-code-generator and
normalized for the kit. DO NOT EDIT in any branch. Every branch materializes this
file byte-identically with `architecture files/contracts/kit/materialize.py`.
A change requires a recorded contract change (see architecture 35).
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    RootModel,
    confloat,
    conint,
    constr,
)


class AreaOfInterest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    body: Literal["EARTH", "MOON", "MARS"]
    bbox: list[float] = Field(..., max_length=4, min_length=4)
    longitude_convention: Literal["NEG180_180", "ZERO_360"]
    latitude_type: Literal["PLANETOCENTRIC", "PLANETOGRAPHIC", "GEODETIC"]
    crs_wkt: str | None
    vertical_datum: str


class RequirementParameters(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    slope_band_deg: list[confloat(ge=0.0, le=90.0)] | None
    exposure_counting: (
        Literal["UNIQUE_UNDIRECTED_EDGE_DISTANCE", "TOTAL_TRAVERSED_DISTANCE"] | None
    )
    task_ids: list[str]
    co_location_group: str | None
    comparison_rule_id: str | None
    temporal_support: str | None


class Requirement(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    id: str
    label: str
    dimension: Literal[
        "TERRAIN",
        "SCIENCE",
        "OPERATIONS",
        "THERMAL",
        "ILLUMINATION",
        "ARIDITY",
        "GRAVITY",
        "ATMOSPHERE",
        "RADIATION",
        "REGOLITH",
    ]
    observable: str
    operator: Literal[
        "BETWEEN", "GTE", "LTE", "EQUALS", "PRESENT", "NOT_NATURALLY_REPRODUCIBLE"
    ]
    lower: float | None
    upper: float | None
    unit: str
    mandatory: bool
    weight: PositiveFloat
    evidence_scope: Literal["regional_context", "terrain_model", "field_validation"]
    minimum_support_scale_m: confloat(ge=0.0) | None
    maximum_support_scale_m: confloat(ge=0.0) | None
    origin: Literal["USER", "TARGET_DERIVED", "PROPOSED_DEFAULT"]
    acceptance_note: str
    parameters: RequirementParameters


class MissionTestContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    mission_id: UUID
    workspace_id: UUID
    revision: conint(ge=1)
    created_at: AwareDatetime
    accepted_at: AwareDatetime | None
    content_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    name: str
    objective: str
    target: AreaOfInterest
    requirements: list[Requirement] = Field(..., min_length=1)
    assumptions: list[str]
    forbidden_actions: list[str]


class EnergyModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    model_id: str
    rolling_coefficient: confloat(ge=0.0, le=1.0)
    drive_efficiency: confloat(le=1.0, gt=0.0)
    idle_power_w: confloat(ge=0.0)
    science_task_wh: confloat(ge=0.0)
    roughness_multiplier: confloat(ge=1.0)
    uncertainty_fraction: confloat(ge=0.0, le=1.0)
    calibration_status: Literal["ASSUMED", "CALIBRATED"]
    calibration_evidence_id: UUID | None


class RoverProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    rover_id: UUID
    workspace_id: UUID
    revision: conint(ge=1)
    created_at: AwareDatetime
    content_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    name: str
    mass_kg: PositiveFloat
    max_slope_deg: confloat(lt=90.0, gt=0.0)
    ground_clearance_m: confloat(ge=0.0)
    wheel_diameter_m: PositiveFloat
    max_obstacle_height_m: confloat(ge=0.0) | None
    battery_wh: PositiveFloat
    min_reserve_pct: confloat(ge=0.0, le=100.0)
    nominal_speed_mps: PositiveFloat
    max_route_m: confloat(ge=0.0) | None
    sensors: list[str]
    capabilities: list[str]
    energy_model: EnergyModel | None
    assumptions: list[str]


class MeasuredMetric(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    metric_id: str
    value: float | None
    unit: str
    support_scale_m: confloat(ge=0.0) | None
    quantity_kind: Literal["MEASURED", "DERIVED", "PROXY", "ASSUMED"]
    method_id: str
    valid_fraction: confloat(ge=0.0, le=1.0)
    uncertainty_note: str


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    kind: Literal[
        "SOURCE",
        "DERIVED",
        "COMPARISON",
        "VERIFICATION",
        "CRITIQUE",
        "ASSUMPTION",
        "REPLAY",
    ]
    artifact_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    artifact_media_type: str | None
    source_uri: str | None
    dataset_product_id: str | None
    dataset_version: str | None
    granule_id: str | None
    license_note: str
    body: Literal["EARTH", "MOON", "MARS"]
    aoi: AreaOfInterest | None
    input_evidence_ids: list[UUID]
    parameters_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    algorithm_id: str
    algorithm_version: str
    native_resolution_m: confloat(ge=0.0) | None
    comparison_scale_m: confloat(ge=0.0) | None
    metrics: list[MeasuredMetric]
    limitations: list[str]


class PlanetaryTargetProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    target: AreaOfInterest
    evidence_ids: list[UUID]
    metrics: list[MeasuredMetric]
    unavailable_dimensions: list[str]


class EarthAnalogCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    name: str
    aoi: AreaOfInterest
    origin: Literal["KNOWN_CONTROL", "DISCOVERED", "USER_SUPPLIED", "SYNTHETIC_CONTROL"]
    discovery_method: str
    novelty_status: Literal["NOT_ASSESSED", "NOT_IN_REFERENCE_LIST", "KNOWN_ANALOG"]
    evidence_ids: list[UUID]
    metrics: list[MeasuredMetric]
    accessibility_status: Literal["NOT_ASSESSED", "DOCUMENTED"]
    limitations: list[str]


class QualificationDimension(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    candidate_id: UUID
    requirement_id: str
    status: Literal["PASS", "PARTIAL", "FAIL", "GAP", "UNKNOWN"]
    evidence_ids: list[UUID]
    rule_id: str
    rule_version: str
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNASSESSED"]
    comparison_scale_m: confloat(ge=0.0) | None
    explanation: str
    limitations: list[str]
    critic_status: Literal["UNREVIEWED", "ACCEPTED", "CHALLENGED", "RESOLVED"]
    critique_evidence_ids: list[UUID]


class RequirementAssignment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    requirement_id: str
    candidate_ids: list[UUID]
    coverage: Literal["FULL", "PARTIAL", "NONE", "UNKNOWN", "GAP"]


class CompositePortfolio(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    candidate_ids: list[UUID]
    requirement_assignments: list[RequirementAssignment]
    objective_value: float
    algorithm_id: str
    residual_requirement_ids: list[str]
    limitations: list[str]


class RequiredExposure(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    requirement_id: str
    metric_id: str
    lower: float | None
    upper: float | None
    minimum_distance_m: confloat(ge=0.0)


class SolverConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    max_expansions: conint(ge=1)
    max_seconds: conint(ge=1)
    max_labels_per_node: conint(ge=1)
    seed: conint(ge=0)


class VerificationTest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    candidate_id: UUID
    mission_revision_id: UUID
    rover_revision_id: UUID
    test_revision: conint(ge=1)
    requirement_ids: list[str]
    route_artifact_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    waypoints_artifact_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    constraints_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    required_exposures: list[RequiredExposure]
    solver_config: SolverConfig
    assumptions: list[str]


class Violation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    requirement_id: str
    code: str
    message: str
    evidence_ids: list[UUID]


class TestResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    test_id: UUID
    outcome: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    failure_category: (
        Literal[
            "ROUTE", "ROVER", "ANALOG", "DATA", "REQUIREMENT", "SEARCH_LIMIT", "SYSTEM"
        ]
        | None
    )
    search_status: Literal[
        "FOUND", "EXHAUSTIVE_INFEASIBLE", "BUDGET_EXHAUSTED", "NOT_RUN", "ERROR"
    ]
    verified_route_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    metrics: list[MeasuredMetric]
    violations: list[Violation]
    evidence_ids: list[UUID]
    verifier_version: str
    limitations: list[str]


class AgentAction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    agent_role: str
    invocation_id: UUID
    action_type: Literal["REQUEST_TOOL", "TOOL_RESULT", "PROPOSAL", "DECISION", "ERROR"]
    tool_name: str | None
    tool_receipt_id: UUID | None
    summary: str
    evidence_ids: list[UUID]
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED"]


class ToolReceipt(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    invocation_id: UUID
    tool_name: str
    tool_version: str
    input_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    output_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    evidence_ids: list[UUID]
    status: Literal["SUCCEEDED", "FAILED", "BLOCKED"]
    error_code: str | None
    elapsed_ms: conint(ge=0)
    cache_hit: bool


class AgentRoleResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    invocation_id: UUID
    role: str
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"]
    proposed_next_state: (
        Literal[
            "DRAFT",
            "VALIDATING",
            "CHARACTERIZING",
            "DISCOVERING",
            "QUALIFYING",
            "CRITIQUING",
            "AWAITING_REVIEW",
            "DESIGNING_TEST",
            "VERIFYING",
            "DIAGNOSING",
            "REPLANNING",
            "BUILDING_PASSPORT",
            "COMPLETED",
            "BLOCKED",
            "FAILED",
            "CANCELLED",
        ]
        | None
    )
    evidence_ids: list[UUID]
    receipt_ids: list[UUID]
    summary: str
    payload: dict[str, Any]
    error_code: str | None


class AnalogPassport(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    mission_revision_id: UUID
    rover_revision_id: UUID | None
    candidate_ids: list[UUID]
    portfolio_id: UUID | None
    qualification_ids: list[UUID]
    test_result_ids: list[UUID]
    qualified_uses: list[str]
    partial_uses: list[str]
    unsupported_uses: list[str]
    unknowns: list[str]
    evidence_ids: list[UUID]
    manifest_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    limitations: list[str]
    next_steps: list[str]
    assurance_evidence_id: UUID = Field(
        ...,
        description="Required DERIVED scientific-assurance evidence; also in evidence_ids and frozen manifest.",
    )


class RunEvent(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    seq: conint(ge=1)
    created_at: AwareDatetime
    event_type: str
    state: Literal[
        "DRAFT",
        "VALIDATING",
        "CHARACTERIZING",
        "DISCOVERING",
        "QUALIFYING",
        "CRITIQUING",
        "AWAITING_REVIEW",
        "DESIGNING_TEST",
        "VERIFYING",
        "DIAGNOSING",
        "REPLANNING",
        "BUILDING_PASSPORT",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "CANCELLED",
    ]
    summary: str
    payload: dict[str, Any]
    evidence_ids: list[UUID]


class ErrorBody(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    code: str
    message: str
    request_id: UUID
    retryable: bool
    details: dict[str, Any]


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    error: ErrorBody


class ReviewRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    review_id: UUID
    kind: Literal["EVIDENCE_READY", "ASSUMPTION", "PROXY", "MATERIAL_TEST_CHANGE"]
    summary: str
    evidence_ids: list[UUID]
    proposal_artifact_sha256: constr(pattern=r"^[a-f0-9]{64}$") | None
    blocked_requirement_ids: list[str]
    allowed_actions: list[str]
    created_at: AwareDatetime
    status: Literal["PENDING", "APPROVED", "REJECTED", "SUPERSEDED"]


class CritiqueIssue(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    issue_id: UUID
    run_id: UUID
    candidate_id: UUID | None
    requirement_id: str | None
    target_evidence_ids: list[UUID]
    reason_code: str
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    status: Literal["OPEN", "RESOLVED", "ACCEPTED_LIMITATION", "REJECTED"]
    summary: str
    repair_request: str
    resolution_evidence_ids: list[UUID]


class EarthCorner(RootModel[list[float]]):
    root: list[float] = Field(..., max_length=2, min_length=2)


class LegendItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    label: str
    lower: float | None
    upper: float | None
    color: constr(pattern=r"^#[a-fA-F0-9]{6}$")


class DisplayLayerManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    candidate_id: UUID | None
    target_profile_id: UUID | None
    body: Literal["EARTH", "MOON", "MARS"]
    layer_kind: Literal[
        "ELEVATION", "SLOPE", "ROUGHNESS", "QUALIFICATION", "THERMAL", "MINERAL"
    ]
    rendering: Literal["EARTH_WEBMERCATOR_IMAGE", "PLANETARY_PLANAR_IMAGE"]
    image_artifact_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    display_crs_wkt: str
    pixel_to_world: list[float] = Field(..., max_length=6, min_length=6)
    width_px: conint(ge=1)
    height_px: conint(ge=1)
    earth_corners: list[EarthCorner] | None
    legend: list[LegendItem]
    unit: str
    support_scale_m: confloat(ge=0.0) | None
    source_evidence_ids: list[UUID]
    nodata_transparent: Literal[True]
    attribution: list[str]
    limitations: list[str]


class RunSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )
    schema_version: Literal["1.0"]
    id: UUID
    workspace_id: UUID
    run_id: UUID
    mode: Literal["live", "replay", "synthetic"]
    created_at: AwareDatetime
    state: Literal[
        "DRAFT",
        "VALIDATING",
        "CHARACTERIZING",
        "DISCOVERING",
        "QUALIFYING",
        "CRITIQUING",
        "AWAITING_REVIEW",
        "DESIGNING_TEST",
        "VERIFYING",
        "DIAGNOSING",
        "REPLANNING",
        "BUILDING_PASSPORT",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "CANCELLED",
    ]
    revision: conint(ge=1)
    last_event_seq: conint(ge=0)
    mission_revision_id: UUID
    rover_revision_id: UUID | None
    target_profile_id: UUID | None
    candidate_ids: list[UUID]
    qualification_ids: list[UUID]
    test_ids: list[UUID]
    test_result_ids: list[UUID]
    portfolio_ids: list[UUID]
    passport_id: UUID | None
    pending_review: ReviewRequest | None
    blocked_dependencies: list[str]
    config_sha256: constr(pattern=r"^[a-f0-9]{64}$")
    selected_candidate_id: UUID | None
    selected_portfolio_id: UUID | None
    scenario_config_id: str
    dataset_lock_id: str
