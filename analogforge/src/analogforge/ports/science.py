"""FROZEN CONTRACT KIT FILE - analogforge.ports.science

The ScienceService port: the ONLY call boundary between the platform (Tanush) and the
scientific library (Ayan). DO NOT EDIT in any branch. Every branch materializes this file
byte-identically with `architecture files/contracts/kit/materialize.py`.

Binding rules (architecture 35 section 3):
* The platform builds a ScienceRequest from frozen, persisted domain records and calls
  ``ScienceService.execute(request, context)`` inside the worker (never in an HTTP handler).
* The science library never touches a database, an LLM, FastAPI, or arbitrary network.
  It reads authorized artifacts through ``context.read_artifact`` and writes only inside
  ``context.scratch_dir()``.
* The science library returns *drafts*: artifacts and evidence identified by result-local
  ``local_key`` strings. The platform registrar allocates real UUIDs, moves bytes into the
  content-addressed store and commits EvidenceRecord / ToolReceipt rows atomically.
* A scientific outcome (FAIL, UNKNOWN, INCONCLUSIVE ...) is NOT a computation failure.
  ``ComputationStatus`` describes whether the computation ran; scientific verdicts live in
  the operation payload.
* Production entry point (fixed dotted path, loaded by the platform):
  ``analogforge.science.facade:create_science_service`` -> ScienceService
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator

from analogforge.ports.common import (
    Body,
    EvidenceKind,
    EvidenceRef,
    PortModel,
    RuntimeMode,
    ScienceIssue,
)
from analogforge.ports.domain_models import MeasuredMetric
from analogforge.ports.science_payloads import OperationInput, OperationPayload

SCIENCE_PORT_VERSION = "1.0.0"
SCIENCE_FACADE_ENTRY_POINT = "analogforge.science.facade:create_science_service"

class ScienceOperation(StrEnum):
    RESOLVE_COVERAGE = "RESOLVE_COVERAGE"
    FETCH_SOURCE = "FETCH_SOURCE"
    INGEST_LOCAL_DATASET = "INGEST_LOCAL_DATASET"
    CHARACTERIZE_TARGET = "CHARACTERIZE_TARGET"
    SCREEN_CANDIDATES = "SCREEN_CANDIDATES"
    ANALYZE_CANDIDATE = "ANALYZE_CANDIDATE"
    COMPARE_REQUIREMENT = "COMPARE_REQUIREMENT"
    ASSESS_COMPATIBILITY = "ASSESS_COMPATIBILITY"
    DESIGN_BENCHMARK = "DESIGN_BENCHMARK"
    SEARCH_ROUTE = "SEARCH_ROUTE"
    VERIFY_ROUTE = "VERIFY_ROUTE"
    DIAGNOSE_RESULT = "DIAGNOSE_RESULT"
    OPTIMIZE_PORTFOLIO = "OPTIMIZE_PORTFOLIO"
    BUILD_DISPLAY_LAYERS = "BUILD_DISPLAY_LAYERS"
    AUDIT_EVIDENCE = "AUDIT_EVIDENCE"


class ComputationStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"  # computation ran; payload complete for its declared scope
    LIMITED = "LIMITED"  # computation ran; payload valid but explicitly partial (issues list why)
    BLOCKED = "BLOCKED"  # could not run: missing input/coverage/credential/policy (no payload numbers)
    FAILED = "FAILED"  # unexpected engine error (SYSTEM); never a scientific verdict


class ArtifactRole(StrEnum):
    SOURCE_BYTES = "SOURCE_BYTES"
    NORMALIZED_RASTER = "NORMALIZED_RASTER"
    ANALYSIS_GRID = "ANALYSIS_GRID"
    DERIVED_JSON = "DERIVED_JSON"
    CONSTRAINTS = "CONSTRAINTS"
    ROUTE = "ROUTE"
    TELEMETRY = "TELEMETRY"
    DISPLAY_IMAGE = "DISPLAY_IMAGE"
    REPORT = "REPORT"


class EvidenceHandle(PortModel):
    """Authorized, persisted evidence the platform passes INTO a request (read-only)."""

    evidence_id: UUID
    kind: EvidenceKind
    mode: RuntimeMode
    body: Body
    artifact_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    artifact_media_type: str | None = None
    algorithm_id: str
    algorithm_version: str
    parameters_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    native_resolution_m: float | None = None
    comparison_scale_m: float | None = None
    metrics: list[MeasuredMetric] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    local_key_origin: str | None = None  # the local_key this evidence had when it was registered


class ExtentBox(PortModel):
    body: Body
    bbox: tuple[float, float, float, float]  # [min_lon, min_lat, max_lon, max_lat], positive-east


class SourcePolicy(PortModel):
    """Frozen source-policy lock for the run (architecture 09 section 3, 21 lock rules)."""

    policy_id: str
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_adapter_ids: list[str] = Field(default_factory=list)
    allowed_extents: list[ExtentBox] = Field(default_factory=list)
    local_dataset_ids: list[str] = Field(default_factory=list)
    synthetic_fixture_ids: list[str] = Field(default_factory=list)
    allow_network: bool = False  # MUST be False for synthetic and replay modes


class ScienceOptions(PortModel):
    """Operational budgets and tuning. Never a place to change accepted requirements."""

    max_expansions: int | None = Field(default=None, ge=1)
    max_seconds: float | None = Field(default=None, gt=0)
    max_labels_per_node: int | None = Field(default=None, ge=1)
    seed: int = Field(default=0, ge=0)
    algorithm_config_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ArtifactDraft(PortModel):
    local_key: str = Field(min_length=1)
    scratch_relpath: str = Field(min_length=1)  # relative to context.scratch_dir(); no '..'
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str
    role: ArtifactRole
    body: Body | None = None
    crs_wkt: str | None = None
    support_scale_m: float | None = Field(default=None, ge=0)
    metadata: dict[str, str | float | int | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _safe_path(self) -> ArtifactDraft:
        p = Path(self.scratch_relpath)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("scratch_relpath must be relative and inside the scratch dir")
        return self


class EvidenceDraft(PortModel):
    """Becomes one EvidenceRecord after registration (architecture 05/09)."""

    local_key: str = Field(min_length=1)
    kind: EvidenceKind
    body: Body
    artifact_key: str | None = None  # ArtifactDraft.local_key in the same result
    artifact_media_type: str | None = None
    parent_local_keys: list[str] = Field(default_factory=list)
    parent_evidence_ids: list[UUID] = Field(default_factory=list)
    source_uri: str | None = None
    dataset_product_id: str | None = None
    dataset_version: str | None = None
    granule_id: str | None = None
    license_note: str
    algorithm_id: str
    algorithm_version: str
    parameters_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    native_resolution_m: float | None = Field(default=None, ge=0)
    comparison_scale_m: float | None = Field(default=None, ge=0)
    aoi_bbox: tuple[float, float, float, float] | None = None
    metrics: list[MeasuredMetric] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ScienceRequest(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID  # platform-generated; identical request_id + inputs => identical result
    operation: ScienceOperation
    mode: RuntimeMode
    inputs: OperationInput  # discriminated by .operation; must equal self.operation
    input_evidence: list[EvidenceHandle] = Field(default_factory=list)
    source_policy: SourcePolicy
    options: ScienceOptions = Field(default_factory=ScienceOptions)

    @model_validator(mode="after")
    def _consistent(self) -> ScienceRequest:
        if self.inputs.operation != self.operation:
            raise ValueError("inputs.operation must equal request.operation")
        if self.mode in ("synthetic", "replay") and self.source_policy.allow_network:
            raise ValueError("synthetic/replay requests may never allow network access")
        return self


class ScienceComputationResult(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    operation: ScienceOperation
    mode: RuntimeMode
    status: ComputationStatus
    algorithm_id: str
    algorithm_version: str
    parameters_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")  # canonical hash of the request
    counters: dict[str, int | float] = Field(default_factory=dict)
    artifacts: list[ArtifactDraft] = Field(default_factory=list)
    evidence_drafts: list[EvidenceDraft] = Field(default_factory=list)
    payload: OperationPayload | None = None  # None only when status is BLOCKED or FAILED
    issues: list[ScienceIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def _closure(self) -> ScienceComputationResult:
        art = {a.local_key for a in self.artifacts}
        ev = {e.local_key for e in self.evidence_drafts}
        if len(art) != len(self.artifacts) or len(ev) != len(self.evidence_drafts):
            raise ValueError("duplicate local_key in artifacts or evidence_drafts")
        for e in self.evidence_drafts:
            if e.artifact_key is not None and e.artifact_key not in art:
                raise ValueError(f"evidence {e.local_key} references unknown artifact_key")
            for parent in e.parent_local_keys:
                if parent not in ev or parent == e.local_key:
                    raise ValueError(f"evidence {e.local_key} has invalid parent_local_key")
        if self.status in (ComputationStatus.SUCCEEDED, ComputationStatus.LIMITED):
            if self.payload is None:
                raise ValueError("SUCCEEDED/LIMITED results require a payload")
            if self.payload.operation != self.operation:
                raise ValueError("payload.operation must equal result.operation")
        if self.status == ComputationStatus.LIMITED and not self.issues:
            raise ValueError("LIMITED results must list at least one issue")
        if self.status in (ComputationStatus.BLOCKED, ComputationStatus.FAILED) and not self.issues:
            raise ValueError("BLOCKED/FAILED results must list at least one issue")
        return self


class ScienceCancelled(Exception):
    """Raised by ScienceContext.check_cancelled(); the platform records cancellation."""


class ScienceDeadlineExceeded(Exception):
    """Raised by ScienceContext.check_cancelled() when the monotonic deadline passed."""


@runtime_checkable
class ScienceContext(Protocol):
    run_id: UUID | None
    workspace_id: UUID
    job_id: UUID
    mode: RuntimeMode
    algorithm_versions: dict[str, str]

    def scratch_dir(self) -> Path: ...

    def read_artifact(self, sha256: str) -> Path:
        """Read-only local path of an authorized immutable blob. Raises KeyError if absent."""
        ...

    def local_dataset_root(self, dataset_id: str) -> Path:
        """Root directory of a registered drop-in dataset (architecture 36). KeyError if unknown."""
        ...

    def check_cancelled(self) -> None:
        """Raise ScienceCancelled / ScienceDeadlineExceeded. Call at every loop checkpoint."""
        ...

    def report_progress(self, step: str, done: int | None = None, total: int | None = None) -> None: ...

    def http_client(self) -> object | None:
        """Approved source HTTP client for live mode only; None in synthetic/replay."""
        ...


@runtime_checkable
class ScienceService(Protocol):
    def supported_operations(self) -> frozenset[ScienceOperation]: ...

    def execute(self, request: ScienceRequest, context: ScienceContext) -> ScienceComputationResult: ...


@dataclass
class LocalScienceContext:
    """Reference ScienceContext for tests and CLI tools (both branches may use it).

    Not a production context: the platform's worker context additionally enforces leases,
    workspace scoping and authorized artifact resolution.
    """

    scratch: Path
    workspace_id: UUID
    job_id: UUID
    mode: RuntimeMode = "synthetic"
    run_id: UUID | None = None
    algorithm_versions: dict[str, str] = field(default_factory=dict)
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    dataset_roots: dict[str, Path] = field(default_factory=dict)
    deadline_monotonic: float | None = None
    cancelled: bool = False
    progress: list[tuple[str, int | None, int | None]] = field(default_factory=list)

    def scratch_dir(self) -> Path:
        self.scratch.mkdir(parents=True, exist_ok=True)
        return self.scratch

    def read_artifact(self, sha256: str) -> Path:
        return self.artifact_paths[sha256]

    def local_dataset_root(self, dataset_id: str) -> Path:
        return self.dataset_roots[dataset_id]

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise ScienceCancelled()
        if self.deadline_monotonic is not None and time.monotonic() > self.deadline_monotonic:
            raise ScienceDeadlineExceeded()

    def report_progress(self, step: str, done: int | None = None, total: int | None = None) -> None:
        self.progress.append((step, done, total))

    def http_client(self) -> object | None:
        return None


__all__ = [
    "SCIENCE_FACADE_ENTRY_POINT",
    "SCIENCE_PORT_VERSION",
    "ArtifactDraft",
    "ArtifactRole",
    "Body",
    "ComputationStatus",
    "EvidenceDraft",
    "EvidenceHandle",
    "EvidenceKind",
    "EvidenceRef",
    "ExtentBox",
    "LocalScienceContext",
    "OperationInput",
    "OperationPayload",
    "PortModel",
    "RuntimeMode",
    "ScienceCancelled",
    "ScienceComputationResult",
    "ScienceContext",
    "ScienceDeadlineExceeded",
    "ScienceIssue",
    "ScienceOperation",
    "ScienceOptions",
    "ScienceRequest",
    "ScienceService",
    "SourcePolicy",
]
