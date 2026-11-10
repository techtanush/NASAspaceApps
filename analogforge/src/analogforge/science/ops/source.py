"""Resolve a :class:`SourceSelector` into a :class:`SourceRaster` plus its SOURCE evidence draft.

``SYNTHETIC_FIXTURE`` sources are generated into the scratch directory by the practice generators and then read through
exactly the same ingest path as ``LOCAL_DATASET`` sources, so the two are identical by construction (PARITY-01).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from analogforge.ports.common import Body, RuntimeMode
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.hashing import bytes_sha256
from analogforge.ports.science import EvidenceDraft
from analogforge.ports.science_payloads import SourceSelector
from analogforge.science.datasets.ingest import (
    DatasetUnreadableError,
    IngestResult,
    ingest_local_dataset,
    source_evidence_draft,
)
from analogforge.science.ops.base import OpBlocked, OpEnv
from analogforge.science.raster.normalized import decode_source
from analogforge.science.raster.project import project_source
from analogforge.science.raster.source import SourceRaster, read_gdal_raster

_GENERATED: dict[str, Path] = {}


@dataclass(frozen=True)
class ResolvedSource:
    raster: SourceRaster
    dataset_id: str
    manifest: DatasetManifest
    ingest: IngestResult | None
    draft: EvidenceDraft
    root: Path

    @property
    def body(self) -> Body:
        return self.manifest.body

    @property
    def product_id(self) -> str | None:
        return self.draft.dataset_product_id


def _fixture_root(env: OpEnv, fixture_id: str) -> Path:
    """Generate the practice datasets into scratch once per scratch directory (deterministic bytes)."""
    base = env.scratch / "_fixtures"
    key = str(base)
    if key not in _GENERATED or not (base / fixture_id).is_dir():
        try:
            practice = importlib.import_module("analogforge.science.fixtures.practice")
        except ModuleNotFoundError as exc:
            raise OpBlocked(
                "practice fixtures are not available in this build",
                code="UNSUPPORTED_PRODUCT",
                detail_code="NO_FIXTURES",
            ) from exc
        practice.generate_all(base)
        _GENERATED[key] = base
    root = base / fixture_id
    if not root.is_dir():
        raise OpBlocked(f"unknown synthetic fixture {fixture_id!r}", code="NO_COVERAGE", detail_code="FIXTURE_UNKNOWN")
    return root


def dataset_root(env: OpEnv, selector: SourceSelector) -> tuple[str, Path]:
    policy = env.request.source_policy
    if selector.kind == "SYNTHETIC_FIXTURE":
        assert selector.fixture_id is not None
        if env.request.mode != "synthetic":
            raise OpBlocked("synthetic fixtures are only available in synthetic mode", detail_code="MODE_MISMATCH")
        if policy.synthetic_fixture_ids and selector.fixture_id not in policy.synthetic_fixture_ids:
            raise OpBlocked(
                f"fixture {selector.fixture_id} is not authorized by the source policy", detail_code="POLICY_DENIED"
            )
        return selector.fixture_id, _fixture_root(env, selector.fixture_id)
    if selector.kind == "LOCAL_DATASET":
        assert selector.dataset_id is not None
        if policy.local_dataset_ids and selector.dataset_id not in policy.local_dataset_ids:
            raise OpBlocked(
                f"dataset {selector.dataset_id} is not authorized by the source policy", detail_code="POLICY_DENIED"
            )
        try:
            return selector.dataset_id, env.context.local_dataset_root(selector.dataset_id)
        except KeyError as exc:
            raise OpBlocked(
                f"dataset {selector.dataset_id} is not registered", code="NO_COVERAGE", detail_code="DATASET_UNKNOWN"
            ) from exc
    raise OpBlocked(
        "adapter-evidence sources are not wired into the offline facade", code="UNSUPPORTED_PRODUCT",
        detail_code="ADAPTER_EVIDENCE_UNSUPPORTED",
    )  # fmt: skip


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise OpBlocked(
            f"manifest.yaml of {root.name} cannot be read", code="SOURCE_UNAVAILABLE", detail_code="MANIFEST_UNREADABLE"
        ) from exc
    if not isinstance(data, dict):
        raise OpBlocked("manifest.yaml must be a mapping", detail_code="MANIFEST_INVALID")
    return data


def _water(manifest: DatasetManifest, root: Path, shape: tuple[int, int]) -> np.ndarray | None:
    masks = [f for f in manifest.files if f.role == "MASK"]
    if not masks:
        return None
    raw = read_gdal_raster(root / masks[0].path)
    if raw.values.shape != shape:
        raise OpBlocked(
            "water mask shape differs from the elevation raster",
            code="SOURCE_CONTENT_INVALID",
            detail_code="MASK_SHAPE",
        )
    primary = read_gdal_raster(root / manifest.primary_file, manifest.band, manifest.variable)
    if raw.crs_wkt != primary.crs_wkt or not np.allclose(
        raw.geotransform, primary.geotransform, rtol=0, atol=1e-8
    ):
        raise OpBlocked(
            "Water mask is not registered to the source raster",
            code="SOURCE_CONTENT_INVALID", detail_code="MASK_GRID_MISMATCH",
        )
    return np.asarray(raw.values > 0, dtype=bool)


def resolve_source(
    env: OpEnv, selector: SourceSelector, *, roles: tuple[str, ...], mode: RuntimeMode | None = None
) -> ResolvedSource:
    if selector.kind == "ADAPTER_EVIDENCE":
        return _resolve_evidence(env, selector, roles)
    dataset_id, root = dataset_root(env, selector)
    raw = read_manifest(root)
    try:
        result = ingest_local_dataset(root, raw, env.scratch, check_cancelled=env.check)
    except DatasetUnreadableError as exc:
        raise OpBlocked(exc.message, code="SOURCE_UNAVAILABLE", detail_code="DATASET_UNREADABLE") from exc
    if result.manifest is None or result.raster is None:
        raise OpBlocked(f"dataset {dataset_id} failed validation: {result.failed}", code="SOURCE_CONTENT_INVALID",
                        detail_code="DATASET_INVALID")  # fmt: skip
    manifest = result.manifest
    if manifest.role not in roles:
        raise OpBlocked(
            f"dataset {dataset_id} has role {manifest.role}, expected one of {roles}", detail_code="ROLE_MISMATCH"
        )
    if not result.usable_for_quantitative_claims:
        raise OpBlocked(
            f"dataset {dataset_id} is not usable for quantitative claims (failed: {list(result.failed)})",
            code="SOURCE_CONTENT_INVALID", detail_code="METADATA_INCOMPLETE",
        )  # fmt: skip
    r = result.raster
    water = _water(manifest, root, r.values.shape)
    assert result.payload is not None and result.payload.bbox_lonlat is not None
    raster = project_source(
        r, manifest, result.payload.bbox_lonlat, water=water,
        source_hashes=tuple(sorted(result.file_hashes.values())),
        product_id=result.product_id, check=env.check,
        max_linear_distortion=env.cfg.algorithms.thresholds.max_linear_distortion,
    )
    draft = source_evidence_draft(
        result,
        mode=mode or env.request.mode,
        algorithm_version=env.algorithm_version("ingest-local-dataset"),
        algorithm_config_sha256=env.cfg.algorithm_config_sha256,
        seed=env.seed,
    )
    return ResolvedSource(raster, dataset_id, manifest, result, draft, root)


def _resolve_evidence(env: OpEnv, selector: SourceSelector, roles: tuple[str, ...]) -> ResolvedSource:
    handles = [env.handle(evidence_id) for evidence_id in selector.evidence_ids]
    candidates = [h for h in handles if h.artifact_media_type == "application/x-npz" and h.kind == "SOURCE"]
    if len(candidates) != 1:
        raise OpBlocked("One normalized source raster is required", detail_code="NORMALIZED_SOURCE_REQUIRED")
    handle = candidates[0]
    if handle.mode != env.request.mode:
        raise OpBlocked("Source evidence mode differs from the request", detail_code="MODE_MISMATCH")
    data = env.artifact_path(handle).read_bytes()
    if bytes_sha256(data) != handle.artifact_sha256:
        raise OpBlocked("Normalized source bytes differ from their checksum", code="SOURCE_CHECKSUM_MISMATCH")
    decoded = decode_source(data)
    meta, manifest = decoded.meta, decoded.meta.manifest
    if manifest.body != handle.body or manifest.role not in roles:
        raise OpBlocked("Normalized source body or role does not match its authorized use", detail_code="ROLE_MISMATCH")
    if (env.mode == "live" and manifest.is_synthetic) or (env.mode == "synthetic" and not manifest.is_synthetic):
        raise OpBlocked("Source provenance is incompatible with this mode", detail_code="MODE_MISMATCH")
    raster = project_source(
        decoded.raster, manifest, meta.bbox_lonlat, water=decoded.water,
        source_hashes=tuple(sorted(meta.file_hashes.values())), product_id=manifest.product_identity.product_id,
        check=env.check,
        max_linear_distortion=env.cfg.algorithms.thresholds.max_linear_distortion,
    )
    params = env.params_hash("ingest-local-dataset", {"normalized_source": handle.artifact_sha256})
    draft = EvidenceDraft(
        local_key="source-" + manifest.dataset_id, kind="SOURCE", body=manifest.body,
        parent_evidence_ids=[handle.evidence_id], license_note=manifest.license_note,
        dataset_product_id=manifest.product_identity.product_id, dataset_version=manifest.product_identity.version,
        algorithm_id="ingest-local-dataset", algorithm_version=env.algorithm_version("ingest-local-dataset"),
        parameters_sha256=params, native_resolution_m=raster.native_resolution_m,
        limitations=[manifest.citation, "Reused immutable normalized source; original byte hashes retained."],
    )
    return ResolvedSource(raster, manifest.dataset_id, manifest, None, draft, env.scratch)


def find_bound_dataset(env: OpEnv, role: str, body: str) -> str | None:
    """First dataset id named by the source policy whose manifest has ``role`` and ``body`` (sorted order)."""
    for dataset_id in sorted(env.request.source_policy.local_dataset_ids):
        try:
            raw = read_manifest(env.context.local_dataset_root(dataset_id))
        except (KeyError, OpBlocked):
            continue
        if raw.get("role") == role and raw.get("body") == body:
            return dataset_id
    return None


def source_limitations(manifest: DatasetManifest) -> list[str]:
    """Retain actual attribution through the frozen evidence-handle limitation field."""
    return [
        "Source citation: " + manifest.citation,
        "Source license: " + manifest.license_note,
        "Source provenance: " + ("SYNTHETIC" if manifest.is_synthetic else "REAL_SOURCE"),
    ]
