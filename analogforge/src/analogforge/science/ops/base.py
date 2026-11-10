"""Shared plumbing of the facade operations: environment, outcome container, evidence/artifact helpers.

Operations are plain functions ``(OpEnv) -> OpOutcome``.  They raise :class:`OpBlocked` (or a
:class:`~analogforge.science.errors.ScienceError`) for expected data problems; the facade turns those into ``BLOCKED``
results.  ``ScienceCancelled`` / ``ScienceDeadlineExceeded`` are never caught here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from analogforge.ports.common import Body, EvidenceKind, ScienceIssue
from analogforge.ports.domain_models import MeasuredMetric
from analogforge.ports.hashing import canonical_json_bytes
from analogforge.ports.science import (
    ArtifactDraft,
    ArtifactRole,
    ComputationStatus,
    EvidenceDraft,
    EvidenceHandle,
    ScienceContext,
    ScienceRequest,
)
from analogforge.ports.science_payloads import OperationPayload
from analogforge.science.config import ScienceConfig
from analogforge.science.errors import ScienceError
from analogforge.science.hashing_utils import parameters_sha256
from analogforge.science.provenance import evidence_draft, write_payload_artifact, write_scratch_artifact

M = TypeVar("M", bound=BaseModel)

SYNTHETIC_LICENSE = "SYNTHETIC PRACTICE DATA - not terrain of this location"
DERIVED_LICENSE_NOTE = "Derived by AnalogForge from the cited input evidence; inherits the licence of its sources."


class OpBlocked(ScienceError):
    """An expected input/policy problem: the operation cannot run and returns ``BLOCKED`` with this issue."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INPUT_INVALID",
        detail_code: str | None = None,
        retryable: bool = False,
        affected: Sequence[str] = (),
        scope: str | None = None,
    ) -> None:
        super().__init__(message, code=code, detail_code=detail_code)
        self.retryable = retryable
        self.affected = list(affected)
        self.scope = scope

    def to_issue(self) -> ScienceIssue:
        return ScienceIssue(
            code=self.code,
            detail_code=self.detail_code,
            message=self.message,
            retryable=self.retryable,
            affected_requirement_ids=self.affected,
            scope=self.scope,
        )


@dataclass(frozen=True)
class OpEnv:
    """Everything an operation needs: the request, the platform context and the loaded configuration."""

    request: ScienceRequest
    context: ScienceContext
    cfg: ScienceConfig

    @property
    def mode(self) -> str:
        return self.request.mode

    @property
    def seed(self) -> int:
        return self.request.options.seed

    @property
    def scratch(self) -> Path:
        return self.context.scratch_dir()

    def check(self) -> None:
        self.context.check_cancelled()

    def handle(self, evidence_id: object) -> EvidenceHandle:
        for h in self.request.input_evidence:
            if h.evidence_id == evidence_id:
                return h
        raise OpBlocked(
            f"evidence {evidence_id} is not among the request's input_evidence",
            detail_code="EVIDENCE_NOT_SUPPLIED",
        )

    def artifact_path(self, handle: EvidenceHandle) -> Path:
        if handle.artifact_sha256 is None:
            raise OpBlocked(f"evidence {handle.evidence_id} carries no artifact", detail_code="ARTIFACT_MISSING")
        try:
            return self.context.read_artifact(handle.artifact_sha256)
        except KeyError as exc:
            raise OpBlocked(
                f"artifact {handle.artifact_sha256[:12]} of evidence {handle.evidence_id} is not authorized/available",
                detail_code="ARTIFACT_MISSING",
            ) from exc

    def read_artifact_by_sha(self, sha256: str) -> Path:
        try:
            return self.context.read_artifact(sha256)
        except KeyError as exc:
            raise OpBlocked(
                f"artifact {sha256[:12]} is not authorized/available",
                code="STALE_INPUT_HASH",
                detail_code="ARTIFACT_MISSING",
            ) from exc

    def read_model(self, handle: EvidenceHandle, model: type[M]) -> M:
        path = self.artifact_path(handle)
        try:
            return model.model_validate_json(path.read_bytes())
        except ValueError as exc:
            raise OpBlocked(
                f"artifact of evidence {handle.evidence_id} is not a valid {model.__name__}",
                code="SOURCE_CONTENT_INVALID",
                detail_code="ARTIFACT_INVALID",
            ) from exc

    def algorithm_version(self, algorithm_id: str) -> str:
        return self.cfg.algorithm_version(algorithm_id)

    def params_hash(
        self,
        algorithm_id: str,
        parameters: Mapping[str, Any] | BaseModel,
        extra_input_hashes: Sequence[str] = (),
    ) -> str:
        """``parameters_sha256`` per guide 08 section 1 (inputs: the supplied evidence hashes plus ``extra``)."""
        params = parameters.model_dump(mode="json") if isinstance(parameters, BaseModel) else dict(parameters)
        hashes = [h.parameters_sha256 for h in self.request.input_evidence]
        hashes += [h.artifact_sha256 for h in self.request.input_evidence if h.artifact_sha256 is not None]
        hashes += list(extra_input_hashes)
        return parameters_sha256(
            operation=self.request.operation.value,
            algorithm_id=algorithm_id,
            algorithm_version=self.algorithm_version(algorithm_id),
            parameters=params,
            input_hashes=sorted(set(hashes)),
            seed=self.seed,
            algorithm_config_sha256=self.cfg.algorithm_config_sha256,
        )

    def operation_params(self) -> dict[str, Any]:
        """The request inputs minus the platform-generated request id (cache-key semantics)."""
        return self.request.inputs.model_dump(mode="json")

    def relpath(self, params_sha: str, name: str) -> str:
        return f"{self.request.operation.value.lower()}/{params_sha[:16]}/{name}"


@dataclass
class OpOutcome:
    """What an operation returns; the facade adds ids, hashes and the result envelope."""

    status: ComputationStatus
    payload: OperationPayload | None
    algorithm_id: str
    parameters_sha256: str
    artifacts: list[ArtifactDraft] = field(default_factory=list)
    evidence: list[EvidenceDraft] = field(default_factory=list)
    issues: list[ScienceIssue] = field(default_factory=list)
    counters: dict[str, int | float] = field(default_factory=dict)


def json_artifact(
    env: OpEnv,
    *,
    params_sha: str,
    key: str,
    name: str,
    payload: BaseModel,
    role: ArtifactRole = ArtifactRole.DERIVED_JSON,
    body: Body | None = None,
) -> ArtifactDraft:
    """Write ``payload`` as canonical JSON (architecture 35 section 5b) under the scratch directory."""
    return write_payload_artifact(
        env.scratch,
        local_key=key,
        relpath=env.relpath(params_sha, name),
        payload=payload,
        role=role,
        body=body,
    )


def bytes_artifact(
    env: OpEnv,
    *,
    params_sha: str,
    key: str,
    name: str,
    data: bytes,
    media_type: str,
    role: ArtifactRole,
    body: Body | None = None,
    crs_wkt: str | None = None,
    support_scale_m: float | None = None,
    metadata: Mapping[str, str | float | int | bool | None] | None = None,
) -> ArtifactDraft:
    return write_scratch_artifact(
        env.scratch,
        local_key=key,
        relpath=env.relpath(params_sha, name),
        data=data,
        media_type=media_type,
        role=role,
        body=body,
        crs_wkt=crs_wkt,
        support_scale_m=support_scale_m,
        metadata=metadata,
    )


def derived_evidence(
    env: OpEnv,
    *,
    key: str,
    kind: EvidenceKind,
    body: Body,
    algorithm_id: str,
    params_sha: str,
    artifact: ArtifactDraft | None,
    parent_keys: Sequence[str] = (),
    parent_evidence_ids: Sequence[Any] = (),
    metrics: Sequence[MeasuredMetric] = (),
    limitations: Sequence[str] = (),
    native_resolution_m: float | None = None,
    comparison_scale_m: float | None = None,
    aoi_bbox: tuple[float, float, float, float] | None = None,
    dataset_product_id: str | None = None,
    dataset_version: str | None = None,
    license_note: str | None = None,
) -> EvidenceDraft:
    """One evidence draft with the algorithm id/version from the lock; parents sorted and de-duplicated."""
    draft = evidence_draft(
        mode=env.request.mode,
        local_key=key,
        kind=kind,
        body=body,
        algorithm_id=algorithm_id,
        algorithm_version=env.algorithm_version(algorithm_id),
        parameters_sha256=params_sha,
        license_note=license_note or (SYNTHETIC_LICENSE if env.request.mode == "synthetic" else DERIVED_LICENSE_NOTE),
        artifact=artifact,
        parent_local_keys=parent_keys,
        dataset_product_id=dataset_product_id,
        dataset_version=dataset_version,
        native_resolution_m=native_resolution_m,
        comparison_scale_m=comparison_scale_m,
        aoi_bbox=aoi_bbox,
        metrics=metrics,
        limitations=limitations,
    )
    ids = sorted({i for i in parent_evidence_ids}, key=str)
    return draft.model_copy(update={"parent_evidence_ids": ids}) if ids else draft


def payload_json_bytes(payload: BaseModel) -> bytes:
    return canonical_json_bytes(payload)
