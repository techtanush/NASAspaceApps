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
from analogforge.ports.science import EvidenceDraft
from analogforge.ports.science_payloads import SourceSelector
from analogforge.science.datasets.ingest import (
    DatasetUnreadableError,
    IngestResult,
    ingest_local_dataset,
    source_evidence_draft,
)
from analogforge.science.geometry import AnalysisGridSpec
from analogforge.science.ops.base import OpBlocked, OpEnv
from analogforge.science.raster.source import SourceRaster, read_gdal_raster

_GENERATED: dict[str, Path] = {}


@dataclass(frozen=True)
class ResolvedSource:
    raster: SourceRaster
    dataset_id: str
    manifest: DatasetManifest
    ingest: IngestResult
    draft: EvidenceDraft
    root: Path

    @property
    def body(self) -> Body:
        return self.manifest.body

    @property
    def product_id(self) -> str | None:
        return self.ingest.product_id


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
    return np.asarray(raw.values > 0, dtype=bool)


def resolve_source(
    env: OpEnv, selector: SourceSelector, *, roles: tuple[str, ...], mode: RuntimeMode | None = None
) -> ResolvedSource:
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
    gt = r.geotransform
    if r.crs_wkt is None or gt[2] != 0.0 or gt[4] != 0.0 or gt[5] >= 0.0 or abs(abs(gt[5]) - gt[1]) > 1e-6 * gt[1]:
        raise OpBlocked(
            "only north-up square-cell projected rasters are supported",
            code="UNSUPPORTED_CRS",
            detail_code="GRID_UNSUPPORTED",
        )
    height, width = r.values.shape
    grid = AnalysisGridSpec(manifest.body, r.crs_wkt, gt[0], gt[3], gt[1], width, height)
    water = _water(manifest, root, r.values.shape)
    values = np.where(r.missing, np.nan, r.values)
    raster = SourceRaster(
        grid=grid,
        values=values,
        nodata=np.asarray(r.missing, dtype=bool),
        native_resolution_m=gt[1],
        support_scale_m=gt[1],
        vertical_reference=manifest.vertical_reference,
        water=water,
        product_id=result.product_id,
        synthetic=manifest.is_synthetic,
        source_hashes=tuple(sorted(result.file_hashes.values())),
    )
    draft = source_evidence_draft(
        result,
        mode=mode or env.request.mode,
        algorithm_version=env.algorithm_version("ingest-local-dataset"),
        algorithm_config_sha256=env.cfg.algorithm_config_sha256,
        seed=env.seed,
    )
    return ResolvedSource(raster, dataset_id, manifest, result, draft, root)


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
