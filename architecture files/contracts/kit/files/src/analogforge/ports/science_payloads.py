"""FROZEN CONTRACT KIT FILE - analogforge.ports.science_payloads

Typed inputs and payloads for each ScienceOperation, plus the cross-branch artifact formats
(ConstraintsArtifact, RouteArtifact, TelemetryArtifact, DisplayLayerDraft) that are stored as
JSON blobs and rendered by the frontend. DO NOT EDIT in any branch.

Conventions (architecture 05/10/12):
* SI units; angles in degrees; energy in Wh; percentages only in fields ending ``_pct``.
* ``None`` means unknown/unavailable. Never encode unknown as 0.
* Candidate identity inside science is ``window_id`` (stable string from the screening grid or
  the drop-in dataset). Persisted candidate UUIDs are optional context supplied by the platform.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from analogforge.ports.common import (
    SHA256_PATTERN,
    Body,
    Confidence,
    EvidenceRef,
    FailureCategory,
    PortModel,
    QualificationStatus,
    RuntimeMode,
    ScienceIssue,
    SearchStatus,
    VerificationOutcome,
)
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.domain_models import (
    AreaOfInterest,
    EnergyModel,
    LegendItem,
    MeasuredMetric,
    MissionTestContract,
    RequiredExposure,
    Requirement,
    RoverProfile,
    SolverConfig,
)

RouteStrategy = Literal[
    # Shortest closed route that satisfies HARD constraints (masks, slope cap, tasks, return,
    # max distance/edge-traversals, energy reserve). Exposure requirements are NOT search
    # constraints for this strategy; the independent verifier evaluates them. This is the
    # default first proposal (architecture 34, erratum E-07).
    "WAYPOINT_RETURN",
    # Minimum-distance closed route satisfying ALL constraints including unique exposure.
    "EXPOSURE_COVERAGE",
    # Same constraints as EXPOSURE_COVERAGE; ordering prefers lowest conservative energy.
    "MINIMUM_FEASIBLE_ROUTE",
    # EXPOSURE_COVERAGE with an additional persisted blocked-segment mask.
    "RECOVERY_ALTERNATIVE",
]
SourceKind = Literal["SYNTHETIC_FIXTURE", "LOCAL_DATASET", "ADAPTER_EVIDENCE"]


# --------------------------------------------------------------------------- shared value types


class SourceSelector(PortModel):
    """Where the raster for an operation comes from."""

    kind: SourceKind
    fixture_id: str | None = None  # SYNTHETIC_FIXTURE, e.g. "practice-earth-grid-v1"
    dataset_id: str | None = None  # LOCAL_DATASET registered via INGEST_LOCAL_DATASET
    evidence_ids: list[UUID] = Field(default_factory=list)  # ADAPTER_EVIDENCE (normalized assets)

    @model_validator(mode="after")
    def _shape(self) -> SourceSelector:
        if self.kind == "SYNTHETIC_FIXTURE" and not self.fixture_id:
            raise ValueError("SYNTHETIC_FIXTURE requires fixture_id")
        if self.kind == "LOCAL_DATASET" and not self.dataset_id:
            raise ValueError("LOCAL_DATASET requires dataset_id")
        if self.kind == "ADAPTER_EVIDENCE" and not self.evidence_ids:
            raise ValueError("ADAPTER_EVIDENCE requires evidence_ids")
        return self


class Histogram(PortModel):
    metric_id: str  # e.g. "surface_slope_deg"
    unit: str  # e.g. "deg"
    edges: list[float] = Field(min_length=2)  # ascending; len(edges) == len(area_fraction) + 1
    area_fraction: list[float]  # sums to 1 over valid area (within 1e-9) when valid_area_m2 > 0
    valid_area_m2: float = Field(ge=0)
    support_scale_m: float = Field(gt=0)

    @model_validator(mode="after")
    def _shape(self) -> Histogram:
        if len(self.edges) != len(self.area_fraction) + 1:
            raise ValueError("len(edges) must equal len(area_fraction) + 1")
        if any(b <= a for a, b in zip(self.edges, self.edges[1:], strict=False)):
            raise ValueError("histogram edges must be strictly ascending")
        if self.valid_area_m2 > 0 and abs(sum(self.area_fraction) - 1.0) > 1e-9:
            raise ValueError("area_fraction must sum to 1")
        return self


class ConnectedZone(PortModel):
    zone_id: str
    area_m2: float = Field(ge=0)
    band_area_m2: dict[str, float]  # band label like "12-18" -> area in that band within zone
    contains_start: bool
    bbox_lonlat: tuple[float, float, float, float] | None = None


class CandidateRef(PortModel):
    window_id: str = Field(min_length=1)
    candidate_id: UUID | None = None  # persisted UUID when known
    name: str
    aoi: AreaOfInterest  # body EARTH, WGS84 lon/lat bbox
    origin: Literal["KNOWN_CONTROL", "DISCOVERED", "USER_SUPPLIED", "SYNTHETIC_CONTROL"]
    novelty_status: Literal["NOT_ASSESSED", "NOT_IN_REFERENCE_LIST", "KNOWN_ANALOG"]
    discovery_method: str


class GateEvidence(PortModel):
    gate_id: Literal[
        "SC-01", "SC-02", "SC-03", "SC-04", "SC-05", "SC-06", "SC-07", "SC-08",
        "SC-09", "SC-10", "SC-11", "SC-12", "SC-13", "SC-14", "SC-15",
    ]
    outcome: Literal["SATISFIED", "UNSATISFIED", "NOT_ASSESSED", "NOT_APPLICABLE"]
    reason: str = Field(min_length=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class AdequacyReceipt(PortModel):
    """Scientific gate evidence the science layer can establish (SC-02..SC-11, SC-13).
    The platform adds SC-01, SC-12, SC-14, SC-15 and decides publication (architecture 33)."""

    observable_policy_id: str
    policy_sha256: str = Field(pattern=SHA256_PATTERN)
    gates: list[GateEvidence]
    validation_level: Literal["S0", "S1", "S2", "S3", "S4"]


class AttemptSummary(PortModel):
    attempt_number: int = Field(ge=1)
    test_revision: int = Field(ge=1)
    candidate_window_id: str
    strategy: RouteStrategy
    outcome: VerificationOutcome
    failure_category: FailureCategory | None
    search_status: SearchStatus
    route_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    violation_codes: list[str] = Field(default_factory=list)


class VerificationSummary(PortModel):
    outcome: VerificationOutcome
    failure_category: FailureCategory | None
    test_result_id: UUID | None = None
    violation_codes: list[str] = Field(default_factory=list)
    metrics: list[MeasuredMetric] = Field(default_factory=list)


class UnavailableDimension(PortModel):
    dimension: str  # Requirement.dimension value, e.g. "THERMAL"
    reason_code: Literal[
        "NOT_REQUESTED", "NO_COVERAGE", "UNSUPPORTED", "FAILED_TO_RETRIEVE", "SCALE_UNSUPPORTED", "METADATA_INCOMPLETE"
    ]
    message: str


# --------------------------------------------------------------------------- route test artifacts


class Waypoint(PortModel):
    node_id: str | None = None  # graph fixtures
    lon: float | None = None  # raster tests: WGS84 display coordinate
    lat: float | None = None
    x_m: float | None = None  # raster tests: analysis-grid projected coordinate
    y_m: float | None = None


class TaskSpec(PortModel):
    task_id: str = Field(min_length=1)
    requirement_ids: list[str]
    kind: Literal["SAMPLING", "IMAGING", "STOP"]
    location: Waypoint
    tolerance_m: float = Field(ge=0)
    dwell_s: float = Field(ge=0)
    incremental_energy_wh: float | None = Field(default=None, ge=0)
    required_capability: str | None = None  # e.g. "geological_sampling"
    evidence_origin: Literal["USER_DESIGNATED", "EVIDENCE_SUPPORTED", "SYNTHETIC_FIXTURE"]


class ExposureSpec(PortModel):
    requirement_id: str
    metric_id: Literal["surface_slope_deg"]
    band_deg: tuple[float, float]
    upper_inclusive: bool  # true only for the final capped band (architecture 12 section 4)
    minimum_distance_m: float = Field(ge=0)
    counting: Literal["UNIQUE_UNDIRECTED_EDGE_DISTANCE", "TOTAL_TRAVERSED_DISTANCE"]


class GridSpec(PortModel):
    analysis_evidence_id: UUID | None = None  # persisted analysis evidence holding the grid
    analysis_grid_sha256: str = Field(pattern=SHA256_PATTERN)  # blob with elevation/slope/masks
    crs_wkt: str
    cell_size_m: float = Field(gt=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class GraphEdge(PortModel):
    a: str
    b: str
    length_m: float = Field(gt=0)
    surface_slope_deg: float = Field(ge=0, le=90)
    mock_energy_wh: float | None = Field(default=None, ge=0)


class GraphSpec(PortModel):
    nodes: list[str] = Field(min_length=1)
    edges: list[GraphEdge] = Field(min_length=1)


class EnergySpec(PortModel):
    model: EnergyModel | None  # None => energy-dependent checks INCONCLUSIVE (DATA)
    battery_wh: float = Field(gt=0)
    min_reserve_pct: float = Field(ge=0, le=100)
    rover_mass_kg: float = Field(gt=0)
    nominal_speed_mps: float = Field(gt=0)
    gravity_mps2: Literal[9.80665] = 9.80665  # Earth field test only (architecture 12 section 5)


class ConstraintsArtifact(PortModel):
    """Immutable frozen constraints for one VerificationTest. Stored as a JSON blob; its
    canonical RFC 8785 SHA-256 is VerificationTest.constraints_sha256."""

    schema_version: Literal["1.0"] = "1.0"
    artifact_kind: Literal["RASTER_ROUTE_TEST", "SYNTHETIC_GRAPH_REGRESSION"]
    mode: RuntimeMode
    resource_provider: Literal["PHYSICAL_EARTH_MODEL", "TEST_ONLY_MOCK_GRAPH"]
    mission_revision_id: UUID
    mission_content_sha256: str = Field(pattern=SHA256_PATTERN)
    rover_revision_id: UUID
    rover_content_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_window_id: str
    test_revision: int = Field(ge=1)
    strategy: RouteStrategy
    grid: GridSpec | None = None
    graph: GraphSpec | None = None
    start: Waypoint
    return_required: bool
    tasks: list[TaskSpec]
    surface_slope_cap_deg: float = Field(gt=0, lt=90)
    exposures: list[ExposureSpec]
    max_distance_m: float | None = Field(default=None, gt=0)
    max_duration_s: float | None = Field(default=None, gt=0)
    max_undirected_edge_traversals: int = Field(default=2, ge=1)
    unknown_is_forbidden: Literal[True] = True
    footprint_dilation_m: float = Field(default=0, ge=0)
    blocked_edge_ids: list[str] = Field(default_factory=list)  # RECOVERY_ALTERNATIVE masks
    energy: EnergySpec
    solver: SolverConfig
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> ConstraintsArtifact:
        if self.artifact_kind == "RASTER_ROUTE_TEST":
            if self.grid is None or self.graph is not None:
                raise ValueError("RASTER_ROUTE_TEST needs grid and no graph")
            if self.resource_provider != "PHYSICAL_EARTH_MODEL":
                raise ValueError("raster tests must use PHYSICAL_EARTH_MODEL")
        else:
            if self.graph is None or self.grid is not None:
                raise ValueError("SYNTHETIC_GRAPH_REGRESSION needs graph and no grid")
            if self.mode != "synthetic" or self.resource_provider != "TEST_ONLY_MOCK_GRAPH":
                raise ValueError("graph regression is synthetic-only with TEST_ONLY_MOCK_GRAPH")
        if self.mode == "live" and self.resource_provider == "TEST_ONLY_MOCK_GRAPH":
            raise ValueError("mock resource provider is forbidden in live mode")
        return self


class GeoJSONLineString(PortModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)  # (lon, lat) WGS84


class TaskEvent(PortModel):
    task_id: str
    node_id: str
    arrival_distance_m: float = Field(ge=0)
    dwell_s: float = Field(ge=0)


class SolverClaimedTotals(PortModel):
    """What the searcher believes. The verifier MUST NOT trust these (architecture 12 s7)."""

    distance_m: float = Field(ge=0)
    energy_conservative_wh: float | None = Field(default=None, ge=0)
    unique_exposure_m: dict[str, float] = Field(default_factory=dict)  # requirement_id -> m


class RouteArtifact(PortModel):
    """Executable route proposal. Stored as a JSON blob (role ROUTE)."""

    schema_version: Literal["1.0"] = "1.0"
    route_key: str
    mode: RuntimeMode
    constraints_sha256: str = Field(pattern=SHA256_PATTERN)
    strategy: RouteStrategy
    graph_revision: str
    node_sequence: list[str] = Field(min_length=2)  # canonical executable route
    task_events: list[TaskEvent] = Field(default_factory=list)
    display_geometry: GeoJSONLineString | None = None  # None for abstract graph fixtures
    solver_claimed: SolverClaimedTotals


class TelemetrySample(PortModel):
    index: int = Field(ge=0)
    node_id: str
    cumulative_distance_m: float = Field(ge=0)
    elapsed_s: float = Field(ge=0)
    lon: float | None = None
    lat: float | None = None
    elevation_m: float | None = None
    segment_surface_slope_deg: float | None = None
    cumulative_energy_conservative_wh: float | None = None
    reserve_pct: float | None = None  # may be negative: never clamp
    in_band_requirement_ids: list[str] = Field(default_factory=list)


class TelemetryArtifact(PortModel):
    """Independently recomputed per-node telemetry (role TELEMETRY), drawn by the Test Lab."""

    schema_version: Literal["1.0"] = "1.0"
    route_sha256: str = Field(pattern=SHA256_PATTERN)
    constraints_sha256: str = Field(pattern=SHA256_PATTERN)
    samples: list[TelemetrySample] = Field(min_length=1)


class RouteViolation(PortModel):
    code: Literal[
        "MAX_SLOPE_EXCEEDED", "FORBIDDEN_INTERSECTION", "UNKNOWN_TERRAIN", "WAYPOINT_MISSED",
        "TASK_CAPABILITY_MISSING", "RETURN_NOT_COMPLETED", "EXPOSURE_SHORTFALL",
        "CLASS_DIVERSITY_SHORTFALL", "ENERGY_RESERVE_SHORTFALL", "MAX_DISTANCE_EXCEEDED",
        "MAX_DURATION_EXCEEDED", "SCALE_UNSUPPORTED", "EDGE_TRAVERSAL_LIMIT_EXCEEDED",
        "DISCONTINUOUS_ROUTE", "STALE_INPUT_HASH",
    ]
    requirement_id: str | None
    constraint_id: str
    observed: float | None
    threshold: float | None
    unit: str | None
    segment_from_index: int | None = None
    segment_to_index: int | None = None
    message: str


class BenchmarkRow(PortModel):
    constraint_id: str
    requirement_id: str | None
    rule: str  # human-readable rule, e.g. ">= 100 m unique in [12,18) deg"
    measured: float | None
    threshold: float | None
    unit: str | None
    margin: float | None  # measured - threshold for GTE; threshold - measured for LTE
    status: VerificationOutcome


# --------------------------------------------------------------------------- display layers


class DisplayLayerDraft(PortModel):
    """Becomes a DisplayLayerManifest after registration (architecture 07/18)."""

    local_key: str
    body: Body
    layer_kind: Literal["ELEVATION", "SLOPE", "ROUGHNESS", "QUALIFICATION", "THERMAL", "MINERAL"]
    rendering: Literal["EARTH_WEBMERCATOR_IMAGE", "PLANETARY_PLANAR_IMAGE"]
    image_artifact_key: str  # ArtifactDraft (PNG, role DISPLAY_IMAGE) in the same result
    display_crs_wkt: str
    pixel_to_world: tuple[float, float, float, float, float, float]  # GDAL order
    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)
    earth_corners: list[tuple[float, float]] | None  # NW,NE,SE,SW lon/lat for Earth; None otherwise
    legend: list[LegendItem]
    unit: str
    support_scale_m: float | None
    source_evidence: list[EvidenceRef] = Field(min_length=1)
    attribution: list[str]
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _body(self) -> DisplayLayerDraft:
        if self.body == "EARTH":
            if self.rendering != "EARTH_WEBMERCATOR_IMAGE" or not self.earth_corners or len(self.earth_corners) != 4:
                raise ValueError("Earth layers use EARTH_WEBMERCATOR_IMAGE with 4 earth_corners")
        else:
            if self.rendering != "PLANETARY_PLANAR_IMAGE" or self.earth_corners is not None:
                raise ValueError("Moon/Mars layers use PLANETARY_PLANAR_IMAGE and earth_corners=None")
        return self


# --------------------------------------------------------------------------- operation inputs


class ResolveCoverageInput(PortModel):
    operation: Literal["RESOLVE_COVERAGE"] = "RESOLVE_COVERAGE"
    subject_kind: Literal["TARGET", "CANDIDATE"]
    aoi: AreaOfInterest
    adapter_id: str  # e.g. "earth_nasadem_hgt_v001", "local_dataset", "synthetic_practice"
    measurement_kinds: list[str]


class CoverageSelection(PortModel):
    selection_key: str
    adapter_id: str
    product_id: str | None
    version: str | None
    granule_ids: list[str] = Field(default_factory=list)
    access_state: Literal["AVAILABLE", "AUTH_REQUIRED", "NO_COVERAGE", "UNSUPPORTED", "UNAVAILABLE"]
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    native_resolution_m: float | None = Field(default=None, gt=0)
    notes: list[str] = Field(default_factory=list)


class FetchSourceInput(PortModel):
    operation: Literal["FETCH_SOURCE"] = "FETCH_SOURCE"
    selection: CoverageSelection
    aoi: AreaOfInterest


class IngestLocalDatasetInput(PortModel):
    operation: Literal["INGEST_LOCAL_DATASET"] = "INGEST_LOCAL_DATASET"
    manifest: DatasetManifest  # files are read via context.local_dataset_root(manifest.dataset_id)


class CharacterizeTargetInput(PortModel):
    operation: Literal["CHARACTERIZE_TARGET"] = "CHARACTERIZE_TARGET"
    target: AreaOfInterest  # body MOON or MARS
    source: SourceSelector
    measurement_spec_id: str  # key in config/algorithms.yaml
    requested_dimensions: list[str]  # Requirement.dimension values present in the contract


class ScreenCandidatesInput(PortModel):
    operation: Literal["SCREEN_CANDIDATES"] = "SCREEN_CANDIDATES"
    search_region_set_id: str  # key in config/candidates.yaml
    source: SourceSelector
    target_metrics: list[MeasuredMetric]
    target_histogram: Histogram | None
    requirements: list[Requirement]
    max_detailed: int = Field(ge=1, le=25)
    reference_set_id: str  # versioned known-analog reference list id


class AnalyzeCandidateInput(PortModel):
    operation: Literal["ANALYZE_CANDIDATE"] = "ANALYZE_CANDIDATE"
    candidate: CandidateRef
    source: SourceSelector
    measurement_spec_id: str


class CompareRequirementInput(PortModel):
    operation: Literal["COMPARE_REQUIREMENT"] = "COMPARE_REQUIREMENT"
    requirement: Requirement
    candidate: CandidateRef
    target_evidence_ids: list[UUID]  # must appear in ScienceRequest.input_evidence
    candidate_evidence_ids: list[UUID]
    verification: VerificationSummary | None = None  # supplied after PROVE IT for continuity rows
    observable_policy_id: str  # key in config/algorithms.yaml observable_policies


class AssessCompatibilityInput(PortModel):
    operation: Literal["ASSESS_COMPATIBILITY"] = "ASSESS_COMPATIBILITY"
    rover: RoverProfile
    requirements: list[Requirement]
    candidate: CandidateRef
    candidate_evidence_ids: list[UUID]
    constraints: ConstraintsArtifact | None = None
    verification: VerificationSummary | None = None


class DesignBenchmarkInput(PortModel):
    operation: Literal["DESIGN_BENCHMARK"] = "DESIGN_BENCHMARK"
    mission: MissionTestContract
    rover: RoverProfile
    candidate: CandidateRef
    analysis_evidence_id: UUID | None  # None only for the synthetic graph scenario
    graph_fixture_id: str | None = None  # "canonical-graph-v1" for the synthetic graph scenario
    strategy: RouteStrategy
    test_revision: int = Field(ge=1)
    prior_attempts: list[AttemptSummary] = Field(default_factory=list)
    blocked_edge_ids: list[str] = Field(default_factory=list)


class SearchRouteInput(PortModel):
    operation: Literal["SEARCH_ROUTE"] = "SEARCH_ROUTE"
    constraints: ConstraintsArtifact
    constraints_sha256: str = Field(pattern=SHA256_PATTERN)


class VerifyRouteInput(PortModel):
    operation: Literal["VERIFY_ROUTE"] = "VERIFY_ROUTE"
    constraints: ConstraintsArtifact
    constraints_sha256: str = Field(pattern=SHA256_PATTERN)
    route: RouteArtifact
    route_sha256: str = Field(pattern=SHA256_PATTERN)
    search_status: SearchStatus  # NOT_RUN for supplied routes


class DiagnoseResultInput(PortModel):
    operation: Literal["DIAGNOSE_RESULT"] = "DIAGNOSE_RESULT"
    constraints: ConstraintsArtifact
    search_status: SearchStatus
    verification: VerificationSummary
    violations: list[RouteViolation]
    attempt_history: list[AttemptSummary]
    remaining_route_repairs: int = Field(ge=0)
    remaining_candidate_switches: int = Field(ge=0)


class QualificationRowInput(PortModel):
    candidate_window_id: str
    requirement_id: str
    status: QualificationStatus
    evaluation_stage: Literal["PRELIMINARY", "FINAL"]
    critic_blocking_open: bool


class OptimizePortfolioInput(PortModel):
    operation: Literal["OPTIMIZE_PORTFOLIO"] = "OPTIMIZE_PORTFOLIO"
    requirements: list[Requirement]
    candidates: list[CandidateRef] = Field(min_length=1, max_length=25)
    qualification_rows: list[QualificationRowInput]
    verification_by_window_id: dict[str, VerificationSummary] = Field(default_factory=dict)
    max_sites: int = Field(ge=1, le=5)


class BuildDisplayLayersInput(PortModel):
    operation: Literal["BUILD_DISPLAY_LAYERS"] = "BUILD_DISPLAY_LAYERS"
    subject: Literal["TARGET", "CANDIDATE"]
    evidence_ids: list[UUID] = Field(min_length=1)
    layer_kinds: list[Literal["ELEVATION", "SLOPE", "ROUGHNESS", "THERMAL", "MINERAL"]] = Field(min_length=1)


class ClaimScope(PortModel):
    claim_id: str
    claim_type: Literal["QUALIFICATION", "VERIFICATION", "DISCOVERY", "CONTEXT"]
    requirement_id: str | None
    candidate_window_ids: list[str]
    evidence_ids: list[UUID]


class AuditEvidenceInput(PortModel):
    operation: Literal["AUDIT_EVIDENCE"] = "AUDIT_EVIDENCE"
    claims: list[ClaimScope] = Field(min_length=1)
    check_set: list[Literal["provenance", "units", "crs", "scale", "coverage", "uncertainty", "proxies", "independence"]]


OperationInput = Annotated[
    ResolveCoverageInput
    | FetchSourceInput
    | IngestLocalDatasetInput
    | CharacterizeTargetInput
    | ScreenCandidatesInput
    | AnalyzeCandidateInput
    | CompareRequirementInput
    | AssessCompatibilityInput
    | DesignBenchmarkInput
    | SearchRouteInput
    | VerifyRouteInput
    | DiagnoseResultInput
    | OptimizePortfolioInput
    | BuildDisplayLayersInput
    | AuditEvidenceInput,
    Field(discriminator="operation"),
]


# --------------------------------------------------------------------------- operation payloads


class ResolveCoveragePayload(PortModel):
    operation: Literal["RESOLVE_COVERAGE"] = "RESOLVE_COVERAGE"
    selections: list[CoverageSelection]
    gaps: list[str] = Field(default_factory=list)


class AcquiredAsset(PortModel):
    adapter_id: str
    product_id: str
    version: str | None
    granule_id: str | None
    source_uri: str  # stable identity; never a signed URL
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    validation_status: Literal["VERIFIED", "PENDING", "REJECTED"]
    artifact_key: str


class FetchSourcePayload(PortModel):
    operation: Literal["FETCH_SOURCE"] = "FETCH_SOURCE"
    source_evidence: list[EvidenceRef]
    acquired_assets: list[AcquiredAsset]


class ValidationCheck(PortModel):
    check_id: str  # e.g. "crs_resolved", "nodata_declared", "body_consistent", "checksum"
    status: Literal["PASS", "FAIL", "WARN"]
    message: str


class IngestLocalDatasetPayload(PortModel):
    operation: Literal["INGEST_LOCAL_DATASET"] = "INGEST_LOCAL_DATASET"
    dataset_id: str
    body: Body
    role: str
    usable_for_quantitative_claims: bool  # False => preview only; dependent rows UNKNOWN
    normalized_evidence: EvidenceRef | None
    checks: list[ValidationCheck] = Field(min_length=1)
    native_resolution_m: float | None
    valid_fraction: float | None = Field(default=None, ge=0, le=1)
    bbox_lonlat: tuple[float, float, float, float] | None


class CharacterizeTargetPayload(PortModel):
    operation: Literal["CHARACTERIZE_TARGET"] = "CHARACTERIZE_TARGET"
    profile_evidence: EvidenceRef
    metrics: list[MeasuredMetric]
    slope_histogram: Histogram | None
    comparison_support_m: float | None = Field(default=None, gt=0)
    unavailable_dimensions: list[UnavailableDimension] = Field(default_factory=list)


class ScreenedWindow(PortModel):
    window_id: str
    name: str
    aoi: AreaOfInterest
    origin: Literal["KNOWN_CONTROL", "DISCOVERED", "USER_SUPPLIED", "SYNTHETIC_CONTROL"]
    novelty_status: Literal["NOT_ASSESSED", "NOT_IN_REFERENCE_LIST", "KNOWN_ANALOG"]
    rank: int | None = Field(default=None, ge=1)  # None when excluded
    excluded: bool
    exclusion_reason: str | None = None  # e.g. "WATER_ONLY", "INSUFFICIENT_VALID_DATA"
    feature_scores: dict[str, float | None]  # mission-relevant deficits; NOT a similarity percent
    is_negative_control: bool = False
    evidence: EvidenceRef | None = None


class ScreenCandidatesPayload(PortModel):
    operation: Literal["SCREEN_CANDIDATES"] = "SCREEN_CANDIDATES"
    screened_count: int = Field(ge=0)
    windows: list[ScreenedWindow]
    shortlist_window_ids: list[str]
    stop_reason: Literal["GRID_EXHAUSTED", "WINDOW_CAP_REACHED", "BUDGET_EXHAUSTED"]
    search_extent: AreaOfInterest
    limitations: list[str] = Field(default_factory=list)


class AnalyzeCandidatePayload(PortModel):
    operation: Literal["ANALYZE_CANDIDATE"] = "ANALYZE_CANDIDATE"
    analysis_evidence: EvidenceRef
    analysis_grid_artifact_key: str | None  # ANALYSIS_GRID blob consumed by DESIGN/SEARCH/VERIFY
    metrics: list[MeasuredMetric]
    slope_histogram: Histogram | None
    connected_zones: list[ConnectedZone] = Field(default_factory=list)
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class CompareRequirementPayload(PortModel):
    operation: Literal["COMPARE_REQUIREMENT"] = "COMPARE_REQUIREMENT"
    requirement_id: str
    proposed_status: QualificationStatus
    reason_code: Literal[
        "MEETS_CRITERION", "INSUFFICIENT_EXPOSURE", "SCALE_UNSUPPORTED", "TARGET_EVIDENCE_MISSING",
        "EARTH_EVIDENCE_MISSING", "TEMPORAL_MISMATCH", "PHYSICAL_GAP", "THRESHOLD_UNRESOLVED",
        "ROUTE_NOT_VERIFIED", "ROUTE_VERIFIED", "ROUTE_FAILED", "CAPABILITY_DECLARED",
        "PROXY_NOT_ACCEPTED", "REQUIREMENT_UNDERSPECIFIED", "INSUFFICIENT_VALID_DATA", "METADATA_INCOMPLETE",
        "DISTRIBUTION_MISMATCH", "ENERGY_MODEL_MISSING",
    ]
    evaluation_stage: Literal["PRELIMINARY", "FINAL"]
    confidence: Confidence
    comparison_scale_m: float | None
    measured_value: float | None
    measured_unit: str | None
    threshold_lower: float | None
    threshold_upper: float | None
    covered_subcriteria: list[str] = Field(default_factory=list)
    uncovered_subcriteria: list[str] = Field(default_factory=list)
    explanation: str
    limitations: list[str] = Field(default_factory=list)
    comparison_evidence: EvidenceRef
    adequacy: AdequacyReceipt


class CompatibilityDimension(PortModel):
    metric_id: str  # e.g. "max_surface_slope_deg", "energy_reserve_pct", "ground_clearance_m"
    status: QualificationStatus
    rover_value: float | None
    required_value: float | None
    unit: str | None
    explanation: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class AssessCompatibilityPayload(PortModel):
    operation: Literal["ASSESS_COMPATIBILITY"] = "ASSESS_COMPATIBILITY"
    preliminary: bool  # True until a verified route exists
    dimensions: list[CompatibilityDimension] = Field(min_length=1)
    compatibility_evidence: EvidenceRef


class ConstraintMapping(PortModel):
    requirement_id: str
    constraint_ids: list[str]
    treatment: Literal["VERIFIED_BY_TOOL", "DECLARED_ONLY", "GAP", "UNKNOWN"]
    limitation: str | None = None


class DesignBenchmarkPayload(PortModel):
    operation: Literal["DESIGN_BENCHMARK"] = "DESIGN_BENCHMARK"
    constraints: ConstraintsArtifact
    constraints_artifact_key: str
    constraints_sha256: str = Field(pattern=SHA256_PATTERN)
    required_exposures: list[RequiredExposure]
    requirement_mapping: list[ConstraintMapping]
    unverified_requirement_ids: list[str] = Field(default_factory=list)
    blockers: list[ScienceIssue] = Field(default_factory=list)


class SearchCounters(PortModel):
    expansions: int = Field(ge=0)
    labels_created: int = Field(ge=0)
    labels_pruned_dominated: int = Field(ge=0)
    labels_pruned_lossy: int = Field(ge=0)  # > 0 forbids EXHAUSTIVE_INFEASIBLE
    elapsed_ms: int = Field(ge=0)


class SearchRoutePayload(PortModel):
    operation: Literal["SEARCH_ROUTE"] = "SEARCH_ROUTE"
    search_status: SearchStatus
    route: RouteArtifact | None
    route_artifact_key: str | None
    route_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    counters: SearchCounters
    approximation_flags: list[str] = Field(default_factory=list)
    optimistic_exposure_bound_m: dict[str, float] = Field(default_factory=dict)  # requirement_id -> m
    termination_reason: str

    @model_validator(mode="after")
    def _shape(self) -> SearchRoutePayload:
        if self.search_status == "FOUND" and (self.route is None or self.route_artifact_key is None):
            raise ValueError("FOUND requires a route and route_artifact_key")
        if self.search_status == "EXHAUSTIVE_INFEASIBLE" and self.counters.labels_pruned_lossy > 0:
            raise ValueError("lossy pruning forbids EXHAUSTIVE_INFEASIBLE (use BUDGET_EXHAUSTED)")
        return self


class VerifyRoutePayload(PortModel):
    operation: Literal["VERIFY_ROUTE"] = "VERIFY_ROUTE"
    outcome: VerificationOutcome
    failure_category: FailureCategory | None
    search_status: SearchStatus
    verified_route_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    metrics: list[MeasuredMetric]  # route_distance_m, unique_exposure_m:<req>, energy_*_wh, reserve_pct ...
    violations: list[RouteViolation] = Field(default_factory=list)
    benchmark_rows: list[BenchmarkRow] = Field(min_length=1)
    telemetry_artifact_key: str | None
    verification_evidence: EvidenceRef
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> VerifyRoutePayload:
        if self.outcome == "PASS":
            if self.failure_category is not None or self.violations or self.verified_route_sha256 is None:
                raise ValueError("PASS requires no category, no violations and a verified route hash")
        elif self.failure_category is None:
            raise ValueError("FAIL/INCONCLUSIVE require a failure_category")
        if self.outcome == "INCONCLUSIVE" and self.failure_category not in ("DATA", "REQUIREMENT", "SEARCH_LIMIT", "SYSTEM"):
            raise ValueError("INCONCLUSIVE uses DATA, REQUIREMENT, SEARCH_LIMIT or SYSTEM")
        return self


class DiagnoseResultPayload(PortModel):
    operation: Literal["DIAGNOSE_RESULT"] = "DIAGNOSE_RESULT"
    primary_category: FailureCategory | None
    secondary_categories: list[FailureCategory] = Field(default_factory=list)
    violated_constraint_ids: list[str] = Field(default_factory=list)
    permitted_repairs: list[
        Literal["NEW_ROUTE", "NEW_ZONE", "NEW_CANDIDATE", "COMPOSITE_PORTFOLIO", "DATA_REPAIR", "NEW_CONTRACT_REQUIRED"]
    ]
    recommended_repair: (
        Literal["NEW_ROUTE", "NEW_ZONE", "NEW_CANDIDATE", "COMPOSITE_PORTFOLIO", "DATA_REPAIR", "NEW_CONTRACT_REQUIRED"]
        | None
    )
    recommended_strategy: RouteStrategy | None
    proof_scope: str  # e.g. "evaluated route only", "discrete graph of zone A under frozen constraints"
    explanation: str
    diagnosis_evidence: EvidenceRef


class PortfolioAssignment(PortModel):
    requirement_id: str
    window_ids: list[str]
    coverage: Literal["FULL", "PARTIAL", "NONE", "UNKNOWN", "GAP"]
    responsibility: str | None = None


class OptimizePortfolioPayload(PortModel):
    operation: Literal["OPTIMIZE_PORTFOLIO"] = "OPTIMIZE_PORTFOLIO"
    selected_window_ids: list[str]  # may be empty: an empty portfolio can be correct
    assignments: list[PortfolioAssignment]
    objective_value: float  # sum of covered requirement weights; NOT a similarity percent
    lexicographic_objective: list[float]
    algorithm_id: Literal["exhaustive-subset-v1"] = "exhaustive-subset-v1"
    residual_requirement_ids: list[str]
    limitations: list[str]
    portfolio_evidence: EvidenceRef


class BuildDisplayLayersPayload(PortModel):
    operation: Literal["BUILD_DISPLAY_LAYERS"] = "BUILD_DISPLAY_LAYERS"
    layers: list[DisplayLayerDraft] = Field(min_length=1)


class ClaimGateEvidence(PortModel):
    claim_id: str
    gates: list[GateEvidence]


class AuditFinding(PortModel):
    finding_id: str
    rule_code: Literal[
        "CRS_MISMATCH", "SCALE_MISMATCH", "COVERAGE_MISSING", "PROXY_OVERSTATED", "MODE_MISMATCH",
        "MISSING_PROVENANCE", "UNIT_MISMATCH", "SHARED_ANCESTRY", "UNCERTAINTY_UNQUANTIFIED", "ROUTE_NOT_VERIFIED",
    ]
    severity: Literal["INFO", "WARNING", "BLOCKING"]
    requirement_id: str | None
    evidence_ids: list[UUID]
    message: str
    required_repair: Literal[
        "RECOMPUTE", "ACQUIRE_EVIDENCE_OR_DOWNGRADE", "CORRECT_METADATA", "RESTORE_CONTRACT",
        "NARROW_LANGUAGE", "REVIEW_ASSUMPTION", "INVESTIGATE_ALTERNATIVE", "RECORD_UNKNOWN",
    ]


class AuditEvidencePayload(PortModel):
    operation: Literal["AUDIT_EVIDENCE"] = "AUDIT_EVIDENCE"
    claim_gates: list[ClaimGateEvidence]
    findings: list[AuditFinding] = Field(default_factory=list)


OperationPayload = Annotated[
    ResolveCoveragePayload
    | FetchSourcePayload
    | IngestLocalDatasetPayload
    | CharacterizeTargetPayload
    | ScreenCandidatesPayload
    | AnalyzeCandidatePayload
    | CompareRequirementPayload
    | AssessCompatibilityPayload
    | DesignBenchmarkPayload
    | SearchRoutePayload
    | VerifyRoutePayload
    | DiagnoseResultPayload
    | OptimizePortfolioPayload
    | BuildDisplayLayersPayload
    | AuditEvidencePayload,
    Field(discriminator="operation"),
]

