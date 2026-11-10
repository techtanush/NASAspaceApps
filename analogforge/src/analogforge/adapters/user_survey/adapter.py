"""User-survey adapter: local Earth GeoTIFF + declared metadata. No network is ever contacted."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import rasterio
from pyproj import CRS
from rasterio.warp import transform_bounds

from analogforge.adapters.source_http.cmr import empty_selection, selection_key
from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata
from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.geo import coverage_fraction, split_bbox
from analogforge.adapters.user_survey.metadata import SurveyMetadata
from analogforge.ports.hashing import file_sha256
from analogforge.ports.science_payloads import AcquiredAsset, CoverageSelection, ResolveCoverageInput

USER_SURVEY_ADAPTER_ID = "earth_user_survey"
PRODUCT_ID = "user_survey_dem"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
EARTH_SEMI_MAJOR_M = 6_378_137.0
_FEET = {"ft": 0.3048, "foot": 0.3048, "feet": 0.3048, "us-ft": 1200.0 / 3937.0}
_METRES = {"m", "meter", "metre", "meters", "metres"}


@dataclass(frozen=True)
class UserSurveyUpload:
    path: Path
    metadata: SurveyMetadata


def _bounds_lonlat(path: Path) -> tuple[float, float, float, float]:
    try:
        with rasterio.open(path) as src:
            if src.crs is None:
                raise AdapterError("UNSUPPORTED_CRS", f"{path.name} has no CRS", detail_code="METADATA_INCOMPLETE")
            west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    except rasterio.errors.RasterioError as exc:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", f"{path.name} is not a readable GeoTIFF", detail_code="BAD_ARCHIVE"
        ) from exc
    return float(west), float(south), float(east), float(north)


def _upload_id(upload: UserSurveyUpload) -> str:
    return f"survey-{file_sha256(upload.path)[:16]}"


def discover(
    request: ResolveCoverageInput, client: httpx.Client | None = None, *, uploads: Sequence[UserSurveyUpload] = ()
) -> list[CoverageSelection]:
    """Select registered uploads that intersect the AOI. ``client`` is accepted for interface symmetry and unused."""
    del client
    if request.adapter_id != USER_SURVEY_ADAPTER_ID:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"unknown adapter {request.adapter_id!r}", detail_code="UNSUPPORTED_FORMAT"
        )
    if request.aoi.body != "EARTH":
        raise AdapterError("UNSUPPORTED_PRODUCT", "user surveys are Earth-only", detail_code="BODY_MISMATCH")
    pieces = split_bbox(request.aoi.bbox, request.aoi.longitude_convention, "NEG180_180")
    hits: list[tuple[str, UserSurveyUpload, float]] = []
    for upload in uploads:
        frac = coverage_fraction(pieces, [_bounds_lonlat(upload.path)])
        if frac > 0:
            hits.append((_upload_id(upload), upload, frac))
    if not hits:
        return [
            empty_selection(
                USER_SURVEY_ADAPTER_ID,
                PRODUCT_ID,
                None,
                request,
                "NO_COVERAGE",
                "no registered user survey intersects the AOI (NO_GRANULES)",
                None,
            )
        ]
    out: list[CoverageSelection] = []
    for uid, upload, frac in sorted(hits, key=lambda h: h[0]):
        missing = upload.metadata.missing_fields()
        notes = ["USER-SUPPLIED data; not NASA evidence."]
        if missing:
            notes.append(f"Preview only: quantitative use blocked until {', '.join(missing)} are declared.")
        out.append(
            CoverageSelection.model_validate(
                {
                    "selection_key": selection_key(USER_SURVEY_ADAPTER_ID, request.aoi.bbox, [uid]),
                    "adapter_id": USER_SURVEY_ADAPTER_ID,
                    "product_id": PRODUCT_ID,
                    "version": None,
                    "granule_ids": [uid],
                    "access_state": "AVAILABLE",
                    "coverage_fraction": frac,
                    "native_resolution_m": upload.metadata.cell_support_m,
                    "notes": notes,
                }
            )
        )
    return out


def fetch(
    selection: CoverageSelection,
    client: httpx.Client | None,
    scratch: Path,
    *,
    uploads: Sequence[UserSurveyUpload] = (),
) -> list[AcquiredAsset]:
    """Copy selected uploads into ``scratch`` (hash-verified); no network."""
    del client
    if selection.adapter_id != USER_SURVEY_ADAPTER_ID:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"selection belongs to {selection.adapter_id}", detail_code="ADAPTER_MISMATCH"
        )
    if not selection.granule_ids:
        raise AdapterError("NO_COVERAGE", "selection lists no uploads", detail_code="NO_GRANULES")
    by_id = {_upload_id(u): u for u in uploads}
    assets: list[AcquiredAsset] = []
    for uid in sorted(selection.granule_ids):
        upload = by_id.get(uid)
        if upload is None:
            raise AdapterError("NO_COVERAGE", f"upload {uid} is not registered", detail_code="NO_GRANULES")
        size = upload.path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise AdapterError("RESOURCE_LIMIT", f"upload {upload.path.name} exceeds {MAX_UPLOAD_BYTES} bytes")
        dest = scratch / "source_bytes" / USER_SURVEY_ADAPTER_ID / uid / upload.path.name
        if scratch.resolve() not in dest.resolve().parents:
            raise AdapterError("SOURCE_CONTENT_INVALID", "scratch path escape", detail_code="PATH_ESCAPE")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upload.path, dest)
        digest = file_sha256(dest)
        if not digest.startswith(uid.removeprefix("survey-")):
            dest.unlink(missing_ok=True)
            raise AdapterError(
                "SOURCE_CHECKSUM_MISMATCH", "upload changed while being copied", detail_code="CHECKSUM_MISMATCH"
            )
        assets.append(
            AcquiredAsset(
                adapter_id=USER_SURVEY_ADAPTER_ID,
                product_id=PRODUCT_ID,
                version=None,
                granule_id=uid,
                source_uri=f"user-upload:{uid}/{upload.path.name}",
                sha256=digest,
                size_bytes=size,
                validation_status="PENDING" if upload.metadata.missing_fields() else "VERIFIED",
                artifact_key=f"source-bytes:{USER_SURVEY_ADAPTER_ID}:{uid}",
            )
        )
    return assets


def asset_path(scratch: Path, asset: AcquiredAsset) -> Path:
    if asset.granule_id is None:
        raise AdapterError("SOURCE_CONTENT_INVALID", "asset has no upload id", detail_code="METADATA_INCOMPLETE")
    return scratch / "source_bytes" / USER_SURVEY_ADAPTER_ID / asset.granule_id / asset.source_uri.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class SurveyDecodeParams:
    metadata: SurveyMetadata


def decode(path: Path, params: SurveyDecodeParams) -> DecodedRaster:
    """Decode band 1 as elevation. Missing metadata yields a preview with ``quantitative_use_allowed=False``."""
    md = params.metadata
    issues = [f"missing:{f}" for f in md.missing_fields()]
    if md.body is not None and md.body.upper() != "EARTH":
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"user surveys are Earth-only; declared body {md.body!r}",
            detail_code="BODY_MISMATCH",
        )
    try:
        src = rasterio.open(path)
    except rasterio.errors.RasterioError as exc:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", f"{path.name} is not a readable GeoTIFF", detail_code="BAD_ARCHIVE"
        ) from exc
    with src:
        if src.crs is None:
            raise AdapterError("UNSUPPORTED_CRS", f"{path.name} has no CRS", detail_code="METADATA_INCOMPLETE")
        crs = CRS.from_wkt(src.crs.to_wkt())
        ellipsoid = crs.ellipsoid
        if ellipsoid is None or abs(ellipsoid.semi_major_metre - EARTH_SEMI_MAJOR_M) > 20_000.0:
            raise AdapterError("UNSUPPORTED_CRS", "raster CRS is not an Earth CRS", detail_code="BODY_MISMATCH")
        band = src.read(1).astype(np.float64)
        nodata = src.nodata if src.nodata is not None else md.nodata_value
        valid = np.isfinite(band)
        if nodata is None:
            issues.append("nodata_not_declared")
        else:
            valid &= band != nodata
        transform = src.transform
        pixel_m = None
        if crs.is_projected:
            factor = crs.axis_info[0].unit_conversion_factor if crs.axis_info else 1.0
            pixel_m = float(abs(transform.a) * factor)
        width, height, crs_wkt = src.width, src.height, src.crs.to_wkt()
        affine = (transform.a, transform.b, transform.c, transform.d, transform.e, transform.f)
    notes = ["USER-SUPPLIED data; labelled separately from NASA evidence."]
    unit = (md.vertical_units or "").strip().lower()
    factor_v = 1.0
    if unit in _FEET:
        factor_v = _FEET[unit]
        notes.append(f"Vertical values converted from {unit} to metres (x{factor_v:.7f}).")
    elif unit and unit not in _METRES:
        raise AdapterError(
            "UNSUPPORTED_PRODUCT", f"unsupported vertical unit {md.vertical_units!r}", detail_code="UNSUPPORTED_FORMAT"
        )
    data = np.where(valid, band * factor_v, np.nan)
    declared = md.cell_support_m
    if pixel_m is not None and declared is not None and abs(pixel_m - declared) > 0.05 * declared:
        issues.append("cell_support_mismatch")
        notes.append(f"Declared cell support {declared:g} m disagrees with raster pixel size {pixel_m:g} m.")
    allowed = not issues
    if not allowed:
        notes.append("Preview only: quantitative qualification is prohibited (" + ", ".join(issues) + ").")
    meta = RasterMetadata(
        adapter_id=USER_SURVEY_ADAPTER_ID,
        body="EARTH",
        quantity="elevation",
        units="m",
        vertical_reference=md.vertical_reference,
        crs_wkt=crs_wkt,
        transform=affine,
        width=width,
        height=height,
        pixel_registration="GDAL_PIXEL_EDGE",
        nodata_raw=float(nodata) if nodata is not None else None,
        product_id=path.stem,
        notes=tuple(notes),
        quantitative_use_allowed=allowed,
        issues=tuple(issues),
        attributes={k: str(v) for k, v in md.model_dump().items() if v is not None},
    )
    return DecodedRaster(data=data, valid=valid, metadata=meta)
