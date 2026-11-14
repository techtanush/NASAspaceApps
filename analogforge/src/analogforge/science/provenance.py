"""Provenance helpers: evidence drafts, scratch artifacts and synthetic-source naming.

The platform registrar (architecture 35 section 3.3) enforces the same rules; the helpers here make it hard to
violate them: synthetic sources are named ``SYNTHETIC_*`` with ``source_uri=None``, artifact paths stay inside the
scratch directory, and every artifact draft carries the SHA-256 of the exact bytes written.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from pydantic import BaseModel

from analogforge.ports.common import Body, EvidenceKind, RuntimeMode
from analogforge.ports.domain_models import MeasuredMetric
from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes
from analogforge.ports.science import ArtifactDraft, ArtifactRole, EvidenceDraft
from analogforge.science.errors import ScienceError

SYNTHETIC_PREFIX = "SYNTHETIC_"
SYNTHETIC_LICENSE_NOTE = "SYNTHETIC PRACTICE DATA - not terrain of this location"
JSON_MEDIA_TYPE = "application/json"


def synthetic_product_id(dataset_id: str) -> str:
    """``SYNTHETIC_<DATASET_ID>`` with ``-`` mapped to ``_`` and upper-cased."""
    return SYNTHETIC_PREFIX + dataset_id.upper().replace("-", "_")


def check_source_naming(mode: RuntimeMode, dataset_product_id: str | None, source_uri: str | None) -> None:
    """Raise :class:`ScienceError` when a draft would violate the registrar's source-naming rules."""
    if mode == "synthetic":
        if dataset_product_id is not None and not dataset_product_id.startswith(SYNTHETIC_PREFIX):
            raise ScienceError(f"synthetic evidence must use a {SYNTHETIC_PREFIX}* product id", code="INPUT_INVALID")
        if source_uri is not None:
            raise ScienceError("synthetic evidence must have source_uri=None", code="INPUT_INVALID")
    if mode == "live" and dataset_product_id is not None and dataset_product_id.startswith(SYNTHETIC_PREFIX):
        raise ScienceError("live evidence may not use a SYNTHETIC_* product id", code="INPUT_INVALID")
    if source_uri is not None:
        parts = urlsplit(source_uri)
        if parts.query or parts.username or parts.password:
            raise ScienceError("source_uri may not carry a query string or credentials", code="INPUT_INVALID")


def safe_relpath(relpath: str) -> str:
    """Validate a scratch-relative POSIX path (no absolute path, no ``..``)."""
    path = PurePosixPath(relpath)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ScienceError(f"unsafe scratch path {relpath!r}", code="INPUT_INVALID")
    return str(path)


def write_scratch_artifact(
    scratch_dir: Path,
    *,
    local_key: str,
    relpath: str,
    data: bytes,
    media_type: str,
    role: ArtifactRole,
    body: Body | None = None,
    crs_wkt: str | None = None,
    support_scale_m: float | None = None,
    metadata: Mapping[str, str | float | int | bool | None] | None = None,
) -> ArtifactDraft:
    """Write ``data`` under ``scratch_dir/relpath`` and return its :class:`ArtifactDraft`."""
    rel = safe_relpath(relpath)
    target = scratch_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return ArtifactDraft(
        local_key=local_key,
        scratch_relpath=rel,
        sha256=bytes_sha256(data),
        size_bytes=len(data),
        media_type=media_type,
        role=role,
        body=body,
        crs_wkt=crs_wkt,
        support_scale_m=support_scale_m,
        metadata=dict(metadata or {}),
    )


def write_payload_artifact(
    scratch_dir: Path,
    *,
    local_key: str,
    relpath: str,
    payload: BaseModel,
    role: ArtifactRole = ArtifactRole.DERIVED_JSON,
    body: Body | None = None,
) -> ArtifactDraft:
    """Serialize a payload with the canonical JSON encoder (architecture 35 section 5b) and write it."""
    return write_scratch_artifact(
        scratch_dir,
        local_key=local_key,
        relpath=relpath,
        data=canonical_json_bytes(payload),
        media_type=JSON_MEDIA_TYPE,
        role=role,
        body=body,
    )


def evidence_draft(
    *,
    mode: RuntimeMode,
    local_key: str,
    kind: EvidenceKind,
    body: Body,
    algorithm_id: str,
    algorithm_version: str,
    parameters_sha256: str,
    license_note: str,
    artifact: ArtifactDraft | None = None,
    parent_local_keys: Sequence[str] = (),
    dataset_product_id: str | None = None,
    dataset_version: str | None = None,
    source_uri: str | None = None,
    native_resolution_m: float | None = None,
    comparison_scale_m: float | None = None,
    aoi_bbox: tuple[float, float, float, float] | None = None,
    metrics: Sequence[MeasuredMetric] = (),
    limitations: Sequence[str] = (),
) -> EvidenceDraft:
    """Build an :class:`EvidenceDraft`, enforcing the source-naming rules for ``mode``.

    ``parent_local_keys`` are de-duplicated and sorted so the draft is independent of discovery order.
    """
    check_source_naming(mode, dataset_product_id, source_uri)
    return EvidenceDraft(
        local_key=local_key,
        kind=kind,
        body=body,
        artifact_key=None if artifact is None else artifact.local_key,
        artifact_media_type=None if artifact is None else artifact.media_type,
        parent_local_keys=sorted(set(parent_local_keys)),
        source_uri=source_uri,
        dataset_product_id=dataset_product_id,
        dataset_version=dataset_version,
        license_note=license_note,
        algorithm_id=algorithm_id,
        algorithm_version=algorithm_version,
        parameters_sha256=parameters_sha256,
        native_resolution_m=native_resolution_m,
        comparison_scale_m=comparison_scale_m,
        aoi_bbox=aoi_bbox,
        metrics=list(metrics),
        limitations=list(limitations),
    )


__all__ = [
    "JSON_MEDIA_TYPE",
    "SYNTHETIC_LICENSE_NOTE",
    "SYNTHETIC_PREFIX",
    "check_source_naming",
    "evidence_draft",
    "safe_relpath",
    "synthetic_product_id",
    "write_payload_artifact",
    "write_scratch_artifact",
]
