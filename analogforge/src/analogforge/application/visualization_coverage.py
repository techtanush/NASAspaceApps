"""Read-only footprint availability backed by explicit offline locked-source intake.

HTTP never opens raster bytes, executes science, downloads data or writes a cache.
Changing a source filesystem identity invalidates the prepared index. Repreparing
rehashes sources and executes the frozen science facade; this is operator catalog
metadata, never run-scoped evidence or a qualification result.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pyproj import CRS

from analogforge.api.errors import ApiError
from analogforge.application.capabilities import get_scenarios
from analogforge.application.datasets import DatasetError, _entrypoint, dataset_dir, load_manifest, lock_path, read_lock
from analogforge.ports.common import Body
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    LocalScienceContext,
    ScienceComputationResult,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import IngestLocalDatasetInput, IngestLocalDatasetPayload
from analogforge.settings import Settings

BBox = tuple[float, float, float, float]
_MAX_JSON_BYTES = 1024 * 1024
_MAX_DATASETS = 64
_MAX_FILES = 64


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CoverageDataset(_Model):
    id: str
    version: str
    body: Body
    bbox: BBox
    validated: Literal[True] = True
    eligible_for_scenario: bool = True
    native_resolution_m: float | None = Field(default=None, ge=0)
    comparison_support_m: float | None = Field(default=None, ge=0)


class VisualizationCoverage(_Model):
    schema_version: Literal["1.0"] = "1.0"
    body: Body
    bbox: BBox
    scenario_config_id: str
    dataset_lock_id: str | None
    state: Literal["COVERED", "PARTIAL", "NONE", "UNKNOWN"]
    basis: Literal["VALIDATED_FOOTPRINT", "VALID_MASK", "UNAVAILABLE"]
    reason: str = Field(min_length=1)
    datasets: list[CoverageDataset]


class _FileIdentity(_Model):
    path: str
    size: int = Field(ge=0)
    mtime_ns: str = Field(pattern=r"^[0-9]+$")
    ctime_ns: str = Field(pattern=r"^[0-9]+$")
    inode: str = Field(pattern=r"^[0-9]+$")
    device: str = Field(pattern=r"^[0-9]+$")


class _Footprint(_Model):
    dataset_id: str
    manifest_sha256: str
    validation_sha256: str
    files: list[_FileIdentity] = Field(max_length=_MAX_FILES)
    bbox: BBox | None
    native_resolution_m: float | None = Field(default=None, gt=0)


class _Index(_Model):
    schema_version: Literal["1.0"] = "1.0"
    policy_sha256: str
    config_sha256: str
    dataset_lock_id: str
    datasets: list[_Footprint] = Field(max_length=_MAX_DATASETS)
    index_sha256: str


def _safe_path(root: Path, path: Path) -> Path:
    absolute_root, absolute = root.absolute(), path.absolute()
    try:
        relative = absolute.relative_to(absolute_root)
    except ValueError as exc:
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage metadata is outside its configured root") from exc
    if ".." in relative.parts:
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage metadata has an unsafe path")
    cursor = absolute_root
    for part in ("", *relative.parts):
        cursor = cursor / part
        if cursor.is_symlink():
            raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage metadata cannot use symlinks")
    if not absolute.resolve().is_relative_to(absolute_root.resolve()):
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage metadata escapes its configured root")
    return absolute


def _json(settings: Settings, path: Path) -> dict[str, Any]:
    with _safe_path(settings.data_root, path).open("rb") as stream:
        raw = stream.read(_MAX_JSON_BYTES + 1)
    if len(raw) > _MAX_JSON_BYTES:
        raise DatasetError("RESOURCE_LIMIT", "Coverage metadata exceeds its byte budget")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage metadata must be an object")
    return value


def _config_sha256(settings: Settings) -> str:
    values: dict[str, Any] = {}
    for name in ("scenarios.yaml", "algorithms.yaml", "datasets.yaml"):
        path = _safe_path(settings.config_dir, settings.config_dir / name)
        if not path.exists():
            values[name] = None
            continue
        with path.open("rb") as stream:
            raw = stream.read(_MAX_JSON_BYTES + 1)
        if len(raw) > _MAX_JSON_BYTES:
            raise DatasetError("RESOURCE_LIMIT", "Coverage configuration exceeds its byte budget")
        values[name] = yaml.safe_load(raw)
    return canonical_sha256(values)


def _identities(settings: Settings, entry: dict[str, Any]) -> list[_FileIdentity]:
    files = entry["files"]
    if not isinstance(files, list) or not files or len(files) > _MAX_FILES:
        raise DatasetError("RESOURCE_LIMIT", "Coverage dataset exceeds its file budget")
    result = []
    for item in files:
        path = _safe_path(settings.data_root, dataset_dir(settings, entry["dataset_id"]) / item["path"])
        info = path.stat()
        if not path.is_file() or info.st_size != item["size_bytes"]:
            raise DatasetError("SOURCE_CHECKSUM_MISMATCH", "Coverage source identity changed")
        result.append(
            _FileIdentity(
                path=item["path"],
                size=info.st_size,
                mtime_ns=str(info.st_mtime_ns),
                ctime_ns=str(info.st_ctime_ns),
                inode=str(info.st_ino),
                device=str(info.st_dev),
            )
        )
    return result


def _locked(settings: Settings, dataset_lock_id: str) -> dict[str, Any]:
    _json(settings, lock_path(settings, dataset_lock_id))
    lock = read_lock(settings, dataset_lock_id, verify_files=False)
    entries = lock["datasets"]
    if lock["policy_id"] != dataset_lock_id or not isinstance(entries, list) or len(entries) > _MAX_DATASETS:
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage source lock is invalid")
    ids = [entry["dataset_id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise DatasetError("SOURCE_CONTENT_INVALID", "Coverage source lock repeats a dataset")
    return lock


def _manifest_and_report(settings: Settings, entry: dict[str, Any]) -> tuple[DatasetManifest, dict[str, Any]]:
    path = _safe_path(settings.data_root, dataset_dir(settings, entry["dataset_id"]) / "manifest.yaml")
    if path.stat().st_size > _MAX_JSON_BYTES:
        raise DatasetError("RESOURCE_LIMIT", "Coverage manifest exceeds its byte budget")
    manifest = load_manifest(settings, entry["dataset_id"])
    report = _json(settings, settings.data_root / "validation" / f"{manifest.dataset_id}.json")
    digest = canonical_sha256(manifest)
    if (
        digest != entry["manifest_sha256"]
        or report.get("manifest_sha256") != digest
        or report.get("status") != "PASS"
        or entry.get("validation") != "PASS"
        or report.get("usable_for_quantitative_claims") is not True
        or entry.get("usable_for_quantitative_claims") is not True
        or manifest.body != entry["body"]
        or manifest.role != entry["role"]
        or any(check.get("status") == "FAIL" for check in report.get("checks", []))
    ):
        raise DatasetError("DATASET_NOT_VALIDATED", "Coverage source validation is unavailable or stale")
    paths = {item.path: item for item in manifest.files}
    if set(paths) != {item["path"] for item in entry["files"]} or len(paths) != len(entry["files"]):
        raise DatasetError("SOURCE_CHECKSUM_MISMATCH", "Coverage source file catalog changed")
    for item in entry["files"]:
        if paths[item["path"]].sha256 not in {None, item["sha256"]}:
            raise DatasetError("SOURCE_CHECKSUM_MISMATCH", "Coverage source checksum catalog changed")
    return manifest, report


def _bbox(value: BBox) -> BBox:
    if len(value) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise ValueError("A bounding box requires four finite numbers")
    west, south, east, north = value
    if not all(math.isfinite(v) for v in value) or not (-180 <= west < east <= 180 and -90 < south < north < 90):
        raise ValueError("Use ordered non-polar positive-east bounds; split seam-crossing areas")
    return value


def _footprint_bbox(manifest: DatasetManifest, payload: IngestLocalDatasetPayload) -> BBox | None:
    if payload.bbox_lonlat is None or manifest.longitude_direction != "POSITIVE_EAST":
        return None
    if manifest.latitude_type != ("GEODETIC" if manifest.body == "EARTH" else "PLANETOCENTRIC"):
        return None
    crs = CRS.from_epsg(manifest.crs.epsg) if manifest.crs.epsg else CRS.from_wkt(manifest.crs.wkt or "")
    operation = crs.coordinate_operation
    # Intake validates north-up/unrotated transforms. Other projections' bbox is
    # only an outer envelope and must never create a false rectangular green area.
    if not crs.is_geographic and (
        operation is None
        or operation.method_name not in {"Equidistant Cylindrical", "Equidistant Cylindrical (Spherical)"}
    ):
        return None
    bounds = payload.bbox_lonlat
    if manifest.longitude_convention == "ZERO_360" and bounds[0] >= 180:
        bounds = (bounds[0] - 360, bounds[1], bounds[2] - 360, bounds[3])
    try:
        return _bbox(bounds)
    except ValueError:
        return None


def _index_path(settings: Settings, dataset_lock_id: str) -> Path:
    lock_path(settings, dataset_lock_id)
    return _safe_path(settings.data_root, settings.data_root / "visualization" / "coverage" / f"{dataset_lock_id}.json")


def prepare_visualization_coverage(settings: Settings, dataset_lock_id: str) -> dict[str, object]:
    """Explicit offline action, without changing sources, locks or scientific results."""
    lock = _locked(settings, dataset_lock_id)
    before = [_identities(settings, entry) for entry in lock["datasets"]]
    if sum(identity.size for files in before for identity in files) > settings.max_download_bytes:
        raise DatasetError("RESOURCE_LIMIT", "Coverage sources exceed the preparation byte budget")
    for entry in lock["datasets"]:
        _manifest_and_report(settings, entry)
    read_lock(settings, dataset_lock_id, verify_files=True)
    config_sha = _config_sha256(settings)
    service = _entrypoint("analogforge.science.facade", "create_science_service")(config_dir=settings.config_dir)
    if ScienceOperation.INGEST_LOCAL_DATASET not in service.supported_operations():
        raise DatasetError("SCIENCE_OPERATION_MISSING", "Coverage preparation requires dataset intake")
    rows = []
    with tempfile.TemporaryDirectory(prefix="analogforge-coverage-") as scratch:
        for entry, identities in zip(lock["datasets"], before, strict=True):
            manifest, report = _manifest_and_report(settings, entry)
            mode: Literal["synthetic", "live"] = "synthetic" if manifest.is_synthetic else "live"
            request = ScienceRequest(
                request_id=uuid4(),
                operation=ScienceOperation.INGEST_LOCAL_DATASET,
                mode=mode,
                inputs=IngestLocalDatasetInput(manifest=manifest),
                source_policy=SourcePolicy(
                    policy_id=dataset_lock_id,
                    policy_sha256=lock["policy_sha256"],
                    local_dataset_ids=[manifest.dataset_id],
                    allow_network=False,
                ),
            )
            context = LocalScienceContext(
                scratch=Path(scratch) / manifest.dataset_id,
                workspace_id=uuid4(),
                job_id=uuid4(),
                mode=mode,
                dataset_roots={manifest.dataset_id: dataset_dir(settings, manifest.dataset_id)},
            )
            result = service.execute(request, context)
            if not isinstance(result, ScienceComputationResult) or (
                result.request_id != request.request_id
                or result.input_sha256 != canonical_sha256(request)
                or result.mode != mode
                or result.operation != request.operation
                or result.status not in {"SUCCEEDED", "LIMITED"}
            ):
                raise DatasetError("MODEL_OUTPUT_INVALID", "Coverage intake did not match its source request")
            payload = result.payload
            if not isinstance(payload, IngestLocalDatasetPayload) or (
                payload.dataset_id != manifest.dataset_id
                or payload.body != manifest.body
                or payload.role != manifest.role
                or not payload.usable_for_quantitative_claims
                or any(check.status == "FAIL" for check in payload.checks)
            ):
                raise DatasetError("DATASET_VALIDATION_FAILED", "Coverage intake failed source validation")
            if identities != _identities(settings, entry):
                raise DatasetError("SOURCE_CHECKSUM_MISMATCH", "Coverage source changed during preparation")
            rows.append(
                _Footprint(
                    dataset_id=manifest.dataset_id,
                    manifest_sha256=canonical_sha256(manifest),
                    validation_sha256=canonical_sha256(report),
                    files=identities,
                    bbox=_footprint_bbox(manifest, payload),
                    native_resolution_m=payload.native_resolution_m,
                )
            )
    if config_sha != _config_sha256(settings) or lock != _locked(settings, dataset_lock_id):
        raise DatasetError("SOURCE_CHECKSUM_MISMATCH", "Coverage configuration changed during preparation")
    raw = {
        "schema_version": "1.0",
        "dataset_lock_id": dataset_lock_id,
        "policy_sha256": lock["policy_sha256"],
        "config_sha256": config_sha,
        "datasets": [row.model_dump(mode="json") for row in rows],
    }
    raw["index_sha256"] = canonical_sha256(raw)
    index = _Index.model_validate(raw)
    encoded = json.dumps(index.model_dump(mode="json"), sort_keys=True) + "\n"
    if len(encoded.encode("utf-8")) > _MAX_JSON_BYTES:
        raise DatasetError("RESOURCE_LIMIT", "Prepared coverage metadata exceeds its byte budget")
    target = _index_path(settings, dataset_lock_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "status": "PASS",
        "dataset_lock_id": dataset_lock_id,
        "datasets": len(rows),
        "footprints": sum(row.bbox is not None for row in rows),
        "index_sha256": index.index_sha256,
    }


def get_visualization_coverage(
    settings: Settings,
    *,
    body: str,
    bbox: BBox,
    scenario_config_id: str,
    dataset_lock_id: str | None,
) -> VisualizationCoverage:
    """Callers authenticate their workspace before reading the operator source catalog."""
    try:
        bounds = _bbox(bbox)
        if body not in {"EARTH", "MARS", "MOON"}:
            raise ValueError("Unsupported body")
    except (ValueError, TypeError) as exc:
        raise ApiError("INPUT_INVALID", "Use a supported body and ordered finite non-polar bounding box.") from exc
    try:
        _config_sha256(settings)
        scenarios = get_scenarios(settings, include_operator_overrides=False)
    except (ValueError, OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise ApiError("SOURCE_UNAVAILABLE", "Visualization source configuration is unavailable.", 503) from exc
    scenario = scenarios.get(scenario_config_id)
    if scenario is None or (body != "EARTH" and body != scenario["body"]):
        raise ApiError("INPUT_INVALID", "The selected body is incompatible with the scenario.")
    if dataset_lock_id is not None and dataset_lock_id != scenario["default_dataset_lock_id"]:
        raise ApiError("INPUT_INVALID", "Use the scenario's frozen source-policy lock.")
    base = {"body": body, "bbox": bounds, "scenario_config_id": scenario_config_id, "dataset_lock_id": dataset_lock_id}

    def unknown(reason: str) -> VisualizationCoverage:
        return VisualizationCoverage.model_validate(
            {**base, "state": "UNKNOWN", "basis": "UNAVAILABLE", "reason": reason, "datasets": []}
        )

    if dataset_lock_id is None or scenario["status"] != "AVAILABLE" or not scenario["allowed_modes"]:
        return unknown("The scenario's terrain sources are not configured and available.")
    selector = scenario["earth_source"] if body == "EARTH" else scenario["target_source"]
    if not isinstance(selector, dict) or selector.get("kind") != "LOCAL_DATASET":
        return unknown("No validated local terrain footprint is prepared for this scenario and body.")
    try:
        lock = _locked(settings, dataset_lock_id)
        raw = _json(settings, _index_path(settings, dataset_lock_id))
        digest = raw.pop("index_sha256", None)
        if digest != canonical_sha256(raw):
            return unknown("Prepared terrain coverage metadata failed its integrity check.")
        index = _Index.model_validate({**raw, "index_sha256": digest})
        if (
            index.dataset_lock_id != dataset_lock_id
            or index.policy_sha256 != lock["policy_sha256"]
            or index.config_sha256 != _config_sha256(settings)
            or {row.dataset_id for row in index.datasets} != {entry["dataset_id"] for entry in lock["datasets"]}
            or len(index.datasets) != len(lock["datasets"])
        ):
            return unknown("Prepared terrain coverage metadata is stale for the selected source configuration.")
        rows = {row.dataset_id: row for row in index.datasets}
        selected: list[CoverageDataset] = []
        for entry in lock["datasets"]:
            manifest, report = _manifest_and_report(settings, entry)
            row = rows[entry["dataset_id"]]
            if (
                row.manifest_sha256 != entry["manifest_sha256"]
                or row.validation_sha256 != canonical_sha256(report)
                or row.files != _identities(settings, entry)
            ):
                return unknown("Prepared terrain coverage sources changed; prepare coverage again.")
            if manifest.dataset_id != selector.get("dataset_id"):
                continue
            role = "EARTH_TERRAIN" if body == "EARTH" else "TARGET_TERRAIN"
            if (
                manifest.body != body
                or manifest.role != role
                or ("live" in scenario["allowed_modes"] and manifest.is_synthetic)
            ):
                return unknown("The configured terrain source is not eligible for this scenario and body.")
            if row.bbox is None:
                return unknown("The source footprint cannot be represented safely by this coverage API.")
            _bbox(row.bbox)
            selected.append(
                CoverageDataset(
                    id=manifest.dataset_id,
                    version=manifest.product_identity.version or "UNSPECIFIED",
                    body=manifest.body,
                    bbox=row.bbox,
                    native_resolution_m=row.native_resolution_m,
                )
            )
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return unknown("Validated terrain coverage is missing, invalid or stale; prepare coverage again.")
    if not selected:
        return unknown("The scenario's terrain source is absent from its validated source-policy lock.")
    footprint = selected[0].bbox
    intersects = min(bounds[2], footprint[2]) > max(bounds[0], footprint[0]) and (
        min(bounds[3], footprint[3]) > max(bounds[1], footprint[1])
    )
    covered = (
        footprint[0] <= bounds[0]
        and footprint[1] <= bounds[1]
        and (bounds[2] <= footprint[2] and bounds[3] <= footprint[3])
    )
    return VisualizationCoverage.model_validate(
        {
            **base,
            "state": "COVERED" if covered else ("PARTIAL" if intersects else "NONE"),
            "basis": "VALIDATED_FOOTPRINT",
            "datasets": selected,
            "reason": "Availability is limited to the validated locked terrain footprint. "
            "Footprint overlap does not establish valid-cell coverage, comparison support or mission qualification.",
        }
    )
