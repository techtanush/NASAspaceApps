"""``INGEST_LOCAL_DATASET`` as a pure function (guide 08 section 4.1, architecture 36 section 4).

:func:`ingest_local_dataset` validates a manifest against the files of one dataset directory, runs **every**
``check_id`` of :data:`checks.CHECK_IDS` in order without short-circuiting, normalises the raster to physical values
(scale/offset exactly once, ``RADIUS`` -> height exactly once) and returns an :class:`IngestResult`.  Failed checks are
a successful computation; only an unreadable directory raises (:class:`DatasetUnreadableError`).

Purity: the dataset directory is read-only; the only writes are archive extractions below the passed ``scratch_dir``.
No environment, network, clock or randomness is used.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pyproj import CRS
from pyproj.exceptions import CRSError
from rasterio.errors import NotGeoreferencedWarning

from analogforge.adapters.source_http.archive import ArchiveLimits, safe_extract_zip
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.ports.catalog import ALGORITHM_IDS
from analogforge.ports.common import Body, EvidenceRef, RuntimeMode
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import EvidenceDraft
from analogforge.ports.science_payloads import IngestLocalDatasetPayload, ValidationCheck
from analogforge.science.datasets import checks as ck
from analogforge.science.errors import RasterError, ScienceError
from analogforge.science.geometry import body_geometry
from analogforge.science.hashing_utils import array_sha256, parameters_sha256
from analogforge.science.provenance import evidence_draft, synthetic_product_id
from analogforge.science.raster.mosaic import Tile, mosaic_tiles
from analogforge.science.raster.normalize import normalize_elevation
from analogforge.science.raster.source import RawRaster, native_cell_size_m, read_gdal_raster

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
GeoTransform = tuple[float, float, float, float, float, float]

_DRIVER_FAMILY: dict[str, frozenset[str]] = {
    "GEOTIFF": frozenset({"GTiff"}),
    "COG": frozenset({"GTiff"}),
    "HGT": frozenset({"SRTMHGT"}),
    "HGT_ZIP": frozenset({"SRTMHGT"}),
    "PDS3_IMG": frozenset({"PDS"}),
    "PDS4_IMG": frozenset({"PDS4"}),
    "NETCDF": frozenset({"netCDF", "h5netcdf"}),
    "HDF5": frozenset({"h5netcdf"}),
    "ASCII_GRID": frozenset({"AAIGrid"}),
}


@dataclass(frozen=True)
class ReadSpec:
    """What the readers need from a manifest (also buildable without a valid manifest, for scaffolding)."""

    dataset_id: str
    format: str
    files: tuple[tuple[str, str], ...]  # (relative path, role)
    variable: str | None = None
    band: int = 1

    @classmethod
    def from_manifest(cls, m: DatasetManifest) -> ReadSpec:
        return cls(m.dataset_id, m.format, tuple((f.path, f.role) for f in m.files), m.variable, m.band)


class DatasetUnreadableError(ScienceError):
    """The dataset directory or its manifest cannot be read (the BLOCKED case of guide 08 section 4.1)."""

    code = "SOURCE_UNAVAILABLE"


@dataclass(frozen=True)
class AppliedTransform:
    """Exactly what was done to the raw values (recorded so a reviewer can see the single transformation)."""

    quantity: str
    units_in: str
    scale_factor: float
    offset: float
    scale_applied_by: str
    unit_factor_to_m: float
    reference_radius_m: float | None
    radius_subtracted: bool


@dataclass(frozen=True)
class NormalizedRaster:
    """Physical values on the source grid: metres of height (ELEVATION/RADIUS) or scaled values; NaN = missing."""

    values: FloatArray
    missing: BoolArray
    geotransform: GeoTransform
    crs_wkt: str | None
    native_resolution_m: float | None
    vertical_reference: str
    source_driver: str
    values_sha256: str


@dataclass(frozen=True)
class IngestResult:
    payload: IngestLocalDatasetPayload | None  # None only when body/dataset identity are unrecoverable
    checks: tuple[ValidationCheck, ...]
    usable_for_quantitative_claims: bool
    manifest: DatasetManifest | None
    manifest_sha256: str | None
    file_hashes: Mapping[str, str]
    raster: NormalizedRaster | None
    applied: AppliedTransform | None
    scale_decision: ck.ScaleDecision | None
    product_id: str | None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(c.check_id for c in self.checks if c.status == "FAIL")

    @property
    def local_key(self) -> str | None:
        return (
            None
            if self.payload is None or self.payload.normalized_evidence is None
            else "source-" + self.payload.dataset_id
        )


# ----------------------------------------------------------------------------------------------- readers
def _read_h5(path: Path, variable: str, band: int) -> RawRaster:
    """EMIT-style NetCDF/HDF5: global/variable ``geotransform`` + ``spatial_ref``; array stored north-up."""
    try:
        import h5netcdf
    except ImportError as exc:  # pragma: no cover - dependency note in API-ADAPTERS
        raise RasterError("h5netcdf/h5py is not installed", code="UNSUPPORTED_PRODUCT") from exc
    try:
        with h5netcdf.File(str(path), "r") as handle:
            node: Any = handle
            for part in [p for p in variable.split("/") if p]:
                node = node[part]
            data = np.asarray(node[...])
            attrs = {**dict(handle.attrs), **dict(node.attrs)}
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise RasterError(f"cannot read variable {variable!r}: {exc}", code="SOURCE_CONTENT_INVALID") from exc
    if data.ndim == 3:
        if not 1 <= band <= data.shape[0]:
            raise RasterError(f"band {band} not present (variable has {data.shape[0]})")
        data = data[band - 1]
    if data.ndim != 2:
        raise RasterError(f"variable {variable!r} is not a 2-D raster")
    raw_gt = attrs.get("GeoTransform", attrs.get("geotransform"))
    if raw_gt is None:
        raise RasterError("no georeference (GeoTransform/geotransform attribute) in the file")
    try:
        parts = [float(x) for x in (raw_gt.split() if isinstance(raw_gt, str) else np.asarray(raw_gt).ravel())]
        gt = (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
    except (ValueError, IndexError) as exc:
        raise RasterError(f"unparseable GeoTransform {raw_gt!r}") from exc
    wkt = attrs.get("spatial_ref", attrs.get("crs_wkt"))
    fill = attrs.get("_FillValue", attrs.get("missing_value"))
    return RawRaster(
        values=data,
        geotransform=gt,
        crs_wkt=None if wkt is None else (wkt.decode() if isinstance(wkt, bytes) else str(wkt)),
        nodata_value=None if fill is None else float(np.asarray(fill).ravel()[0]),
        dtype=str(data.dtype),
        driver="h5netcdf",
        reader_scale=float(np.asarray(attrs.get("scale_factor", 1.0)).ravel()[0]),
        reader_offset=float(np.asarray(attrs.get("add_offset", 0.0)).ravel()[0]),
    )


def _open_one(path: Path, manifest: ReadSpec) -> RawRaster:
    fmt = manifest.format
    if fmt in ("NETCDF", "HDF5") and not manifest.variable:
        raise RasterError(f"{fmt} requires manifest.variable")
    if fmt == "HDF5":
        assert manifest.variable is not None
        return _read_h5(path, manifest.variable, manifest.band)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        try:
            raw = read_gdal_raster(path, manifest.band, manifest.variable if fmt == "NETCDF" else None)
        except RasterError as gdal_error:
            if fmt == "NETCDF" and manifest.variable:
                return _read_h5(path, manifest.variable, manifest.band)
            raise gdal_error
    if fmt == "NETCDF" and raw.crs_wkt is None and raw.geotransform == (0.0, 1.0, 0.0, 0.0, 0.0, 1.0):
        assert manifest.variable is not None
        return _read_h5(path, manifest.variable, manifest.band)
    return raw


def _data_paths(manifest: ReadSpec, present: Mapping[str, Path]) -> list[tuple[str, Path]]:
    if manifest.format in ("PDS3_IMG", "PDS4_IMG"):
        labels = [p for p, role in manifest.files if role == "LABEL"]
        suffixes = (".lbl",) if manifest.format == "PDS3_IMG" else (".xml",)
        chosen = labels or [p for p, _ in manifest.files if p.lower().endswith(suffixes)]
        if not chosen:
            raise RasterError(f"{manifest.format} needs a LABEL file ({'/'.join(suffixes)}) to be opened by GDAL")
        return [(sorted(chosen)[0], present[sorted(chosen)[0]])]
    return [(p, present[p]) for p, role in sorted(manifest.files) if role == "DATA"]


def read_dataset_rasters(manifest: ReadSpec, present: Mapping[str, Path], scratch: Path) -> list[RawRaster]:
    """Open every DATA file (lexicographic path order); archives are extracted below ``scratch`` safely."""
    if manifest.format == "OTHER":
        raise RasterError("format OTHER has no reader", code="UNSUPPORTED_PRODUCT")
    paths = _data_paths(manifest, present)
    if not paths:
        raise RasterError("manifest lists no DATA file")
    opened: list[tuple[str, Path]] = []
    if manifest.format == "HGT_ZIP":
        for name, zip_path in paths:
            dest = scratch / manifest.dataset_id / Path(name).stem
            try:
                members = safe_extract_zip(zip_path, dest, ArchiveLimits(allowed_suffixes=frozenset({".hgt"})))
            except AdapterError as exc:
                raise RasterError(f"{name}: {exc.message}", detail_code=exc.detail_code) from exc
            opened += [(f"{name}!{m.name}", m) for m in members]
    else:
        opened = paths
    rasters: list[RawRaster] = []
    for name, path in opened:
        try:
            raw = _open_one(path, manifest)
        except RasterError as exc:
            raise RasterError(f"{name}: {exc.message}", code=exc.code, detail_code=exc.detail_code) from exc
        family = _DRIVER_FAMILY[manifest.format]
        if raw.driver not in family:
            raise RasterError(f"{name}: opened by driver {raw.driver}, expected one of {sorted(family)}")
        rasters.append(raw)
    return rasters


def _consistent(rasters: list[RawRaster]) -> str | None:
    first = rasters[0]
    for r in rasters[1:]:
        if (r.crs_wkt is None) != (first.crs_wkt is None) or r.dtype != first.dtype:
            return "tiles differ in CRS presence or data type"
        if (r.reader_scale, r.reader_offset) != (first.reader_scale, first.reader_offset):
            return "tiles differ in scale/offset"
        if r.nodata_value != first.nodata_value:
            return "tiles differ in nodata"
    return None


def nominal_posting_m(body: Body, crs: CRS | None, gt: GeoTransform, height: int, width: int) -> float | None:
    """Posting a human would declare: the larger cell side (geographic rasters shrink east-west with latitude)."""
    if crs is None:
        return None
    if crs.is_projected:
        return max(abs(gt[1]), abs(gt[5]))
    lon_c, lat_c = gt[0] + 0.5 * width * gt[1], gt[3] + 0.5 * height * gt[5]
    geod = body_geometry(body).geod()
    _, _, dx = geod.inv(lon_c, lat_c, lon_c + abs(gt[1]), lat_c)
    _, _, dy = geod.inv(lon_c, lat_c, lon_c, lat_c + abs(gt[5]))
    return float(max(dx, dy))


# ----------------------------------------------------------------------------------------------- normalisation
def normalize_values(
    manifest: DatasetManifest, raw: NDArray[Any], nodata: float | None, decision: ck.ScaleDecision
) -> tuple[FloatArray, BoolArray, AppliedTransform]:
    """Scale/offset applied once (``decision``), nodata matched on the raw values, RADIUS -> height once."""
    if manifest.quantity in ("ELEVATION", "RADIUS"):
        values, missing, rec = normalize_elevation(
            raw,
            quantity="RADIUS" if manifest.quantity == "RADIUS" else "ELEVATION",
            units="km" if manifest.units == "km" else "m",
            scale_factor=decision.scale,
            offset=decision.offset,
            scale_already_applied=False,
            reference_radius_m=manifest.reference_radius_m,
            nodata_value=nodata,
        )
        applied = AppliedTransform(
            manifest.quantity, manifest.units, decision.scale, decision.offset, decision.side,
            rec.unit_factor_to_m, rec.reference_radius_m, rec.radius_subtracted,
        )  # fmt: skip
        return values, missing, applied
    arr = np.asarray(raw).astype(np.float64)
    missing = ~np.isfinite(arr)
    if nodata is not None:
        missing = missing | (np.asarray(raw) == nodata)
    values = np.where(missing, np.nan, arr * decision.scale + decision.offset)
    applied = AppliedTransform(
        manifest.quantity, manifest.units, decision.scale, decision.offset, decision.side, 1.0, None, False
    )
    return np.asarray(values, dtype=np.float64), missing, applied


def _combine(
    manifest: DatasetManifest, rasters: list[RawRaster], nodata: float | None, decision: ck.ScaleDecision
) -> tuple[FloatArray, BoolArray, GeoTransform, AppliedTransform]:
    parts = [normalize_values(manifest, r.values, nodata, decision) for r in rasters]
    applied = parts[0][2]
    if len(rasters) == 1:
        return parts[0][0], parts[0][1], rasters[0].geotransform, applied
    tiles = []
    for index, (raster, (vals, _, _)) in enumerate(zip(rasters, parts, strict=True)):
        gt = raster.geotransform
        if abs(abs(gt[1]) - abs(gt[5])) > 1e-9 * abs(gt[1]):
            raise RasterError("multi-tile mosaics need square cells")
        tiles.append(Tile(f"tile{index}", vals, gt[0], gt[3], abs(gt[1])))
    mosaic = mosaic_tiles(tiles)
    gt = (mosaic.origin_x_m, mosaic.cell_size_m, 0.0, mosaic.origin_y_m, 0.0, -mosaic.cell_size_m)
    return mosaic.values, ~mosaic.covered, gt, applied


# ----------------------------------------------------------------------------------------------- orchestration
def _noop() -> None:
    return None


def _identity_of(raw: Mapping[str, Any]) -> tuple[str | None, Body | None, str | None]:
    body = raw.get("body")
    return (
        raw.get("dataset_id") if isinstance(raw.get("dataset_id"), str) else None,
        body if body in ("EARTH", "MOON", "MARS") else None,
        raw.get("role") if isinstance(raw.get("role"), str) else None,
    )


def ingest_local_dataset(
    dataset_dir: Path,
    manifest: DatasetManifest | Mapping[str, Any],
    scratch_dir: Path,
    *,
    max_download_bytes: int = ck.MAX_DOWNLOAD_BYTES,
    check_cancelled: Callable[[], None] = _noop,
) -> IngestResult:
    """Run all fifteen checks and normalise the raster.  ``manifest`` may be the raw mapping (strict re-validation)."""
    if not dataset_dir.is_dir():
        raise DatasetUnreadableError(f"dataset directory {dataset_dir.name!r} does not exist")
    raw_manifest = manifest.model_dump(mode="json") if isinstance(manifest, DatasetManifest) else dict(manifest)
    out: dict[str, ck.CheckOutcome] = {}

    schema, parsed = ck.check_manifest_schema(raw_manifest)
    out["manifest_schema"] = schema
    present: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    rasters: list[RawRaster] | None = None
    raster: NormalizedRaster | None = None
    applied: AppliedTransform | None = None
    decision: ck.ScaleDecision | None = None
    read_error: str | None = None
    html: list[str] = []
    physical: FloatArray | None = None
    gt: GeoTransform | None = None
    effective_crs: CRS | None = None
    effective_wkt: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    native: float | None = None
    valid_fraction: float | None = None
    nodata_eff: float | None = None

    if parsed is None:
        reason = "manifest invalid"
        for cid in ck.CHECK_IDS[1:]:
            out[cid] = ck.not_evaluated(cid, reason)
    else:
        m = parsed
        out["files_present"], present = ck.check_files_present(m, dataset_dir, max_download_bytes)
        check_cancelled()
        out["checksums"], hashes = ck.check_checksums(m, present)
        check_cancelled()
        html = ck.html_files(m, present)
        out["html_login_page"] = ck.check_html_login_page(m, present)
        # --- format_readable
        missing_files = [e.path for e in m.files if e.path not in present]
        if missing_files:
            read_error = "NOT_EVALUATED: listed file(s) missing"
        elif html:
            read_error = "NOT_EVALUATED: HTML page saved as data (see html_login_page)"
        else:
            try:
                rasters = read_dataset_rasters(ReadSpec.from_manifest(m), present, scratch_dir)
                mismatch = _consistent(rasters)
                if mismatch:
                    read_error, rasters = mismatch, None
            except ScienceError as exc:
                read_error = f"{exc.message}" + (f" [{exc.detail_code}]" if exc.detail_code else "")
        check_cancelled()
        if rasters is not None:
            first = rasters[0]
            out["format_readable"] = ck.CheckOutcome(
                "format_readable",
                "PASS",
                f"{len(rasters)} file(s) opened with driver {first.driver} "
                f"({first.values.shape[1]}x{first.values.shape[0]}, {first.dtype})",
            )
        elif read_error is not None and read_error.startswith("NOT_EVALUATED"):
            out["format_readable"] = ck.CheckOutcome("format_readable", "WARN", read_error)
        else:
            out["format_readable"] = ck.CheckOutcome("format_readable", "FAIL", read_error or "unreadable")
        # --- raster-independent checks
        file_wkt = rasters[0].crs_wkt if rasters else None
        out["crs_resolved"] = ck.check_crs_resolved(m, file_wkt, rasters is not None)
        out["body_consistent"] = ck.check_body_consistent(m, file_wkt)
        out["lineage_fields"] = ck.check_lineage_fields(m)
        # --- raster-dependent checks
        reader = (rasters[0].reader_scale, rasters[0].reader_offset) if rasters else (1.0, 0.0)
        decision = ck.decide_scale(m, *reader)
        nodata_eff = m.nodata_value if m.nodata_value is not None else (rasters[0].nodata_value if rasters else None)
        out["nodata_declared"] = ck.check_nodata_declared(
            m.nodata_value,
            rasters[0].nodata_value if rasters else None,
            [r.values for r in rasters] if rasters else None,
        )
        if rasters is None:
            out["scale_offset_once"] = ck.not_evaluated("scale_offset_once", "raster could not be read")
            out["units_and_quantity"] = ck.check_units_and_quantity(m, None)
        else:
            out["scale_offset_once"] = ck.check_scale_offset_once(decision)
            try:
                physical_all, missing, gt, applied = _combine(m, rasters, nodata_eff, decision)
                physical = physical_all
            except ScienceError as exc:
                read_error = f"{exc.message}" + (f" [{exc.detail_code}]" if exc.detail_code else "")
                out["format_readable"] = ck.CheckOutcome("format_readable", "FAIL", read_error)
                rasters = None
                out["units_and_quantity"] = ck.check_units_and_quantity(m, None)
            else:
                out["units_and_quantity"] = ck.check_units_and_quantity(m, physical)
        if rasters is not None and physical is not None and gt is not None:
            try:
                effective_crs = CRS.from_wkt(file_wkt) if file_wkt is not None else ck.crs_from_spec(m.crs)
                effective_wkt = effective_crs.to_wkt()
            except CRSError:
                effective_crs = None
            h, w = physical.shape
            valid_fraction = float(np.count_nonzero(~missing)) / float(h * w)
            if effective_wkt is not None:
                try:
                    native = native_cell_size_m(
                        RawRaster(physical, gt, effective_wkt, nodata_eff, "float64", "", 1.0, 0.0), m.body
                    )
                    bbox = ck.lonlat_bbox(effective_crs, gt, h, w, m.longitude_convention) if effective_crs else None
                except (ScienceError, ValueError, CRSError):
                    native, bbox = None, None
            if native is not None and not (math.isfinite(native) and native > 0.0):
                native = None  # e.g. cells beyond the poles: unknown, never NaN
            pixel_deg = abs(gt[1]) if effective_crs is not None and effective_crs.is_geographic else None
            out["transform_sane"] = ck.check_transform_sane(gt, m.pixel_registration, bbox)
            if bbox is not None and not (
                all(math.isfinite(x) for x in bbox)
                and -90.0 - ck.LATITUDE_EPS <= bbox[1]
                and bbox[3] <= 90.0 + ck.LATITUDE_EPS
            ):
                bbox = None  # an off-globe extent is reported by transform_sane, never published as a bbox
            posting = nominal_posting_m(m.body, effective_crs, gt, h, w) if native is not None else None
            if posting is not None and not (math.isfinite(posting) and posting > 0.0):
                posting = None
            out["resolution_cross_check"] = ck.check_resolution_cross_check(m.declared_native_resolution_m, posting)
            out["valid_fraction"] = ck.check_valid_fraction(valid_fraction)
            out["longitude_convention"] = ck.check_longitude_convention(m, effective_crs, bbox, pixel_deg)
            raster = NormalizedRaster(
                values=physical,
                missing=missing,
                geotransform=gt,
                crs_wkt=effective_wkt,
                native_resolution_m=native,
                vertical_reference=m.vertical_reference,
                source_driver=rasters[0].driver,
                values_sha256=array_sha256(physical),
            )
        else:
            for cid in ("transform_sane", "resolution_cross_check", "valid_fraction", "longitude_convention"):
                out[cid] = ck.not_evaluated(cid, "raster could not be read")

    ordered = [out[cid] for cid in ck.CHECK_IDS]
    is_usable = ck.usable(parsed, ordered)
    checks = tuple(o.to_check() for o in ordered)
    limitations = _limitations(parsed, ordered, is_usable)
    payload: IngestLocalDatasetPayload | None = None
    dataset_id, body, role = (parsed.dataset_id, parsed.body, parsed.role) if parsed else _identity_of(raw_manifest)
    if dataset_id is not None and body is not None and role is not None:
        payload = IngestLocalDatasetPayload(
            dataset_id=dataset_id,
            body=body,
            role=role,
            usable_for_quantitative_claims=is_usable,
            normalized_evidence=EvidenceRef(local_key="source-" + dataset_id) if raster is not None else None,
            checks=list(checks),
            native_resolution_m=native,
            valid_fraction=valid_fraction,
            bbox_lonlat=bbox,
        )
    product = None
    if parsed is not None:
        product = (
            synthetic_product_id(parsed.dataset_id)
            if parsed.is_synthetic
            else (parsed.product_identity.product_id or parsed.dataset_id)
        )
    return IngestResult(
        payload=payload,
        checks=checks,
        usable_for_quantitative_claims=is_usable,
        manifest=parsed,
        manifest_sha256=canonical_sha256(parsed.model_dump(mode="json")) if parsed else None,
        file_hashes=dict(hashes),
        raster=raster,
        applied=applied,
        scale_decision=decision if raster is not None else None,
        product_id=product,
        limitations=limitations,
    )


def _limitations(manifest: DatasetManifest | None, outcomes: list[ck.CheckOutcome], usable: bool) -> tuple[str, ...]:
    notes: list[str] = []
    if manifest is None:
        return ("manifest invalid: dataset cannot be used",)
    if manifest.role == "CONTEXT_ONLY":
        notes.append("CONTEXT_ONLY: display layer only, never evidence for a qualification")
    elif not usable:
        notes.append("not usable for quantitative claims: dependent requirements are UNKNOWN (METADATA_INCOMPLETE)")
    notes += [f"{o.check_id}: {o.message}" for o in outcomes if o.status != "PASS"]
    if manifest.is_synthetic:
        notes.append("SYNTHETIC data - not NASA terrain")
    return tuple(notes)


def source_evidence_draft(
    result: IngestResult,
    *,
    mode: RuntimeMode,
    algorithm_version: str,
    algorithm_config_sha256: str,
    seed: int = 0,
) -> EvidenceDraft:
    """The single SOURCE draft (no artifact bytes) for a dataset whose raster was read."""
    if result.manifest is None or result.local_key is None or result.manifest_sha256 is None:
        raise ScienceError("no normalised raster: there is no evidence to register", code="INPUT_INVALID")
    m = result.manifest
    assert result.applied is not None
    params = parameters_sha256(
        operation="INGEST_LOCAL_DATASET",
        algorithm_id=ALGORITHM_IDS["INGEST_LOCAL_DATASET"],
        algorithm_version=algorithm_version,
        parameters={
            "manifest_sha256": result.manifest_sha256,
            "file_hashes": dict(sorted(result.file_hashes.items())),
            "applied": vars(result.applied),
            "checks": {c.check_id: c.status for c in result.checks},
        },
        input_hashes=[result.manifest_sha256, *result.file_hashes.values()],
        seed=seed,
        algorithm_config_sha256=algorithm_config_sha256,
    )
    return evidence_draft(
        mode=mode,
        local_key=result.local_key,
        kind="SOURCE",
        body=m.body,
        algorithm_id=ALGORITHM_IDS["INGEST_LOCAL_DATASET"],
        algorithm_version=algorithm_version,
        parameters_sha256=params,
        license_note=m.license_note,
        dataset_product_id=result.product_id,
        dataset_version=m.product_identity.version,
        source_uri=None if m.is_synthetic else ck.sanitized_source_url(m.product_identity.source_url),
        native_resolution_m=None if result.payload is None else result.payload.native_resolution_m,
        aoi_bbox=None if result.payload is None else result.payload.bbox_lonlat,
        limitations=list(result.limitations),
    )


__all__ = [
    "AppliedTransform",
    "DatasetUnreadableError",
    "IngestResult",
    "NormalizedRaster",
    "ReadSpec",
    "nominal_posting_m",
    "ingest_local_dataset",
    "normalize_values",
    "read_dataset_rasters",
    "source_evidence_draft",
]
