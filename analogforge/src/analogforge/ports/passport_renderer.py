"""FROZEN CONTRACT KIT FILE - analogforge.ports.passport_renderer

The PassportRenderer port: the call boundary between the platform (Tanush, assembles and
freezes a PassportExportBundle) and the pure renderer (Aradhya, turns it into bytes).
DO NOT EDIT in any branch.

Binding rules (architecture 19, 35 section 4):
* The renderer is PURE: no database, no network, no LLM, no clock reads that change bytes
  (use bundle.generated_at), no environment/secret access, no filesystem writes.
* Same bundle + same assets + same format + same renderer_version => byte-identical output.
* ``RenderedExport.sha256`` is the SHA-256 of ``content`` bytes. It is DIFFERENT from
  ``bundle.manifest_sha256`` (the RFC 8785 digest of the scientific manifest).
* A final (non-draft) bundle that is internally inconsistent raises RendererError.
* Production entry point (fixed dotted path, loaded by the platform):
  ``analogforge.rendering.passport:create_passport_renderer`` -> PassportRenderer
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator

from analogforge.ports.assurance_models import ScientificAssuranceArtifact
from analogforge.ports.common import SHA256_PATTERN, PortModel, RuntimeMode
from analogforge.ports.domain_models import (
    AnalogPassport,
    CompositePortfolio,
    CritiqueIssue,
    EarthAnalogCandidate,
    EvidenceRecord,
    MissionTestContract,
    PlanetaryTargetProfile,
    QualificationDimension,
    RoverProfile,
    TestResult,
    VerificationTest,
)
from analogforge.ports.science_payloads import BenchmarkRow, CompatibilityDimension, RouteViolation

RENDERER_PORT_VERSION = "1.0.0"
RENDERER_ENTRY_POINT = "analogforge.rendering.passport:create_passport_renderer"

ExportFormat = Literal["html", "json", "csv"]

CSV_COLUMNS: tuple[str, ...] = (
    "passport_id",
    "run_id",
    "mode",
    "mission_revision_id",
    "rover_revision_id",
    "candidate_id",
    "candidate_name",
    "requirement_id",
    "requirement_label",
    "mandatory",
    "qualification_status",
    "evaluation_stage",
    "observable",
    "operator",
    "threshold_lower",
    "threshold_upper",
    "unit",
    "target_value",
    "earth_value",
    "comparison_scale_m",
    "confidence",
    "critic_status",
    "limitations",
    "evidence_ids",
    "verification_outcome",
    "assurance_disposition",
    "manifest_sha256",
)
"""Exact, ordered base CSV columns (architecture 19 section 5.3). Multi-valued cells use ' | '."""


class CompatibilityBlock(PortModel):
    candidate_id: UUID
    rover_revision_id: UUID
    preliminary: bool
    dimensions: list[CompatibilityDimension]


class AttemptRecord(PortModel):
    """One PROVE IT attempt, in order. All attempts appear, including failures."""

    attempt_number: int = Field(ge=1)
    parent_attempt_number: int | None
    candidate_id: UUID
    candidate_name: str
    strategy: str
    test: VerificationTest
    result: TestResult
    benchmark_rows: list[BenchmarkRow]
    violations: list[RouteViolation]
    diagnosis_category: str | None
    diagnosis_explanation: str | None
    changed_elements: list[str]  # e.g. ["candidate: SYN-A -> SYN-B", "strategy: WAYPOINT_RETURN -> EXPOSURE_COVERAGE"]
    route_image_asset_key: str | None = None


class SourceLocks(PortModel):
    dataset_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    acquired_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    build_lock_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    config_sha256: str = Field(pattern=SHA256_PATTERN)
    algorithm_lock_sha256: str = Field(pattern=SHA256_PATTERN)


class ProvidedAsset(PortModel):
    asset_key: str
    media_type: Literal["image/png", "image/svg+xml"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    content: bytes


class PassportExportBundle(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    is_draft: bool  # True => renderer adds a conspicuous DRAFT / INCOMPLETE banner
    generated_at: str  # ISO 8601 UTC; the ONLY time value the renderer may print
    mode: RuntimeMode
    replay_source_run_id: UUID | None = None
    passport: AnalogPassport
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    canonical_manifest_json: str  # exact RFC 8785 bytes (UTF-8 text) whose SHA-256 is manifest_sha256
    mission: MissionTestContract
    rover: RoverProfile | None
    target_profile: PlanetaryTargetProfile | None
    candidates: list[EarthAnalogCandidate]
    qualifications: list[QualificationDimension]
    compatibility: list[CompatibilityBlock] = Field(default_factory=list)
    critiques: list[CritiqueIssue] = Field(default_factory=list)
    attempts: list[AttemptRecord] = Field(default_factory=list)
    portfolio: CompositePortfolio | None = None
    evidence_appendix: list[EvidenceRecord] = Field(default_factory=list)
    assurance: ScientificAssuranceArtifact | None  # None allowed ONLY when is_draft
    source_locks: SourceLocks
    search_limitations: list[str] = Field(default_factory=list)
    not_run_reason: str | None = None  # e.g. "No rover supplied - site qualification only"

    @model_validator(mode="after")
    def _final_requires_assurance(self) -> PassportExportBundle:
        if not self.is_draft:
            if self.assurance is None:
                raise ValueError("a final passport bundle requires the resolved assurance artifact")
            if self.assurance.publication == "BLOCKED":
                raise ValueError("a BLOCKED audit cannot produce a final passport")
        if self.passport.manifest_sha256 != self.manifest_sha256:
            raise ValueError("passport.manifest_sha256 must equal bundle.manifest_sha256")
        if self.passport.mode != self.mode:
            raise ValueError("passport.mode must equal bundle.mode")
        return self


class RenderedExport(PortModel):
    format: ExportFormat
    content: bytes
    media_type: Literal["text/html; charset=utf-8", "application/json", "text/csv; charset=utf-8"]
    filename: str = Field(pattern=r"^[A-Za-z0-9._-]{1,120}$")
    sha256: str = Field(pattern=SHA256_PATTERN)  # SHA-256 of content bytes
    renderer_version: str
    referenced_evidence_ids: list[UUID]


class RendererError(Exception):
    """Raised for an inconsistent final bundle. ``code`` is a stable machine string."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@runtime_checkable
class PassportRenderer(Protocol):
    renderer_version: str

    def render(
        self, bundle: PassportExportBundle, assets: list[ProvidedAsset], fmt: ExportFormat
    ) -> RenderedExport: ...


__all__ = [
    "CSV_COLUMNS",
    "RENDERER_ENTRY_POINT",
    "RENDERER_PORT_VERSION",
    "AttemptRecord",
    "CompatibilityBlock",
    "ExportFormat",
    "PassportExportBundle",
    "PassportRenderer",
    "ProvidedAsset",
    "RenderedExport",
    "RendererError",
    "SourceLocks",
]
