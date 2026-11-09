"""EMIT L2B mineral NetCDF decoding: explicit variable path, categorical ids, masks, valid-retrieval fraction.

The arrays stay in sensor geometry (not orthorectified); ``lat``/``lon`` arrays from the ``location`` group are
carried as auxiliary rasters when present. Mineral ids are categorical and are never interpolated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5netcdf
import numpy as np
from numpy.typing import NDArray

from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata
from analogforge.adapters.source_http.errors import AdapterError

INVALID_ID = -1  # value in ``data`` where the retrieval is invalid; ``valid`` is authoritative
WGS84_NOTE = "Geolocation arrays are WGS84 degrees; the product is in sensor geometry, not an orthorectified map."


@dataclass(frozen=True)
class EmitDecodeParams:
    group_prefix: str = "group_1"  # id variable path: f"{prefix}_mineral_id"
    mask_variable: str | None = None  # path of an in-file mask variable (nonzero => bad unless bad_values given)
    mask_array: NDArray[Any] | None = None  # externally supplied mask (e.g. from the L2A mask product)
    mask_bad_values: frozenset[int] | None = None
    no_identification_ids: frozenset[int] = field(default_factory=lambda: frozenset({0}))
    dictionary_group: str = "mineral_metadata"


def _variable(root: Any, path: str) -> Any:
    node = root
    parts = [p for p in path.split("/") if p]
    for group in parts[:-1]:
        if group not in node.groups:
            raise AdapterError("UNSUPPORTED_PRODUCT", f"group {group!r} of variable path {path!r} not found",
                               detail_code="UNSUPPORTED_FORMAT")
        node = node.groups[group]
    if not parts or parts[-1] not in node.variables:
        raise AdapterError("UNSUPPORTED_PRODUCT", f"variable path {path!r} not found in the product",
                           detail_code="UNSUPPORTED_FORMAT")
    return node.variables[parts[-1]]


def _read(root: Any, path: str) -> tuple[NDArray[Any], Any]:
    var = _variable(root, path)
    return np.asarray(var[...]), var.attrs.get("_FillValue")


def _dictionary(root: Any, group: str) -> dict[int, str]:
    if group not in root.groups:
        return {}
    grp = root.groups[group]
    if "index" not in grp.variables or "name" not in grp.variables:
        return {}
    idx = np.asarray(grp.variables["index"][...]).astype(int).tolist()
    names = np.asarray(grp.variables["name"][...]).tolist()
    return {int(i): (n.decode("utf-8") if isinstance(n, bytes) else str(n)).strip()
            for i, n in zip(idx, names, strict=True)}


def decode(path: Path, params: EmitDecodeParams | None = None) -> DecodedRaster:
    prm = params or EmitDecodeParams()
    try:
        handle = h5netcdf.File(str(path), "r")
    except (OSError, ValueError) as exc:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"{path.name} is not a readable NetCDF/HDF5 file",
                           detail_code="BAD_ARCHIVE") from exc
    with handle as root:
        ids_raw, fill = _read(root, f"{prm.group_prefix}_mineral_id")
        if ids_raw.ndim != 2:
            raise AdapterError("SOURCE_CONTENT_INVALID", "mineral id variable is not two-dimensional",
                               detail_code="SHAPE_MISMATCH")
        notes = [WGS84_NOTE,
                 "Mineral ids are categorical (nearest-neighbour semantics only); 'no identification' is not proof "
                 "of absence without the product's documented detection limits."]
        valid = np.ones(ids_raw.shape, dtype=bool)
        if fill is not None:
            valid &= ids_raw != np.asarray(fill).reshape(-1)[0]
        else:
            notes.append("No _FillValue declared on the id variable; every sample was treated as a retrieval.")
        mask: NDArray[Any] | None = None
        if prm.mask_array is not None:
            mask = np.asarray(prm.mask_array)
        elif prm.mask_variable is not None:
            mask = _read(root, prm.mask_variable)[0]
        if mask is not None:
            if mask.shape != ids_raw.shape:
                raise AdapterError("SOURCE_CONTENT_INVALID", "mask shape differs from the id raster",
                                   detail_code="SHAPE_MISMATCH")
            bad = np.isin(mask, list(prm.mask_bad_values)) if prm.mask_bad_values is not None else mask != 0
            valid &= ~bad
            notes.append("Quality mask applied before any statistic.")
        else:
            notes.append("No quality mask supplied; valid retrieval reflects the fill value only.")
        aux: dict[str, NDArray[Any]] = {}
        for key, var_path in (("band_depth", f"{prm.group_prefix}_band_depth"),
                              ("band_depth_unc", f"{prm.group_prefix}_band_depth_unc")):
            try:
                arr, arr_fill = _read(root, var_path)
            except AdapterError:
                continue
            arr = arr.astype(np.float64)
            if arr_fill is not None:
                arr[arr == float(np.asarray(arr_fill).reshape(-1)[0])] = np.nan
            arr[~valid] = np.nan
            aux[key] = arr
        for key, var_path in (("lat", "location/lat"), ("lon", "location/lon")):
            try:
                aux[key] = _read(root, var_path)[0].astype(np.float64)
            except AdapterError:
                notes.append(f"No {var_path} geolocation array in the file.")
        dictionary = _dictionary(root, prm.dictionary_group)
        root_attrs = {str(k): str(v) for k, v in root.attrs.items()}
    data = np.where(valid, ids_raw.astype(np.int64), INVALID_ID)
    unknown = sorted({int(v) for v in np.unique(data[valid])} - set(dictionary) - set(prm.no_identification_ids))
    if unknown:
        notes.append(f"Ids absent from the product dictionary: {unknown}.")
    identified = valid & ~np.isin(data, list(prm.no_identification_ids))
    meta = RasterMetadata(
        adapter_id="earth_emit_l2bmin_v001", body="EARTH", quantity="mineral_id", units="categorical",
        vertical_reference=None, crs_wkt=None, transform=None, width=ids_raw.shape[1], height=ids_raw.shape[0],
        pixel_registration="SENSOR_GEOMETRY_NOT_ORTHORECTIFIED", nodata_raw=float(np.asarray(fill).reshape(-1)[0])
        if fill is not None else None, product_id=root_attrs.get("title") or path.stem, notes=tuple(notes),
        attributes={"valid_retrieval_fraction": f"{float(valid.mean()):.12g}",
                    "identified_fraction": f"{float(identified.mean()):.12g}", "variable_group": prm.group_prefix,
                    **{f"nc_{k}": v for k, v in sorted(root_attrs.items())}},
    )
    return DecodedRaster(data=data, valid=valid, metadata=meta, aux=aux, dictionary=dictionary)


@dataclass(frozen=True)
class RetrievalInBox:
    pixels_in_box: int
    valid_pixels: int
    fraction: float | None  # None (unknown) when no pixel of the scene falls in the box


def retrieval_in_bbox(raster: DecodedRaster, bbox: Sequence[float]) -> RetrievalInBox:
    """Valid-retrieval fraction inside a lon/lat box (west, south, east, north; -180..180) using the
    geolocation arrays. An empty intersection yields ``fraction=None`` rather than 0."""
    if "lat" not in raster.aux or "lon" not in raster.aux:
        raise AdapterError("SOURCE_CONTENT_INVALID", "geolocation arrays are required for AOI statistics",
                           detail_code="METADATA_INCOMPLETE")
    west, south, east, north = (float(v) for v in bbox)
    lat, lon = raster.aux["lat"], raster.aux["lon"]
    inside = (lat >= south) & (lat <= north)
    inside &= (lon >= west) & (lon <= east) if west <= east else (lon >= west) | (lon <= east)
    total = int(inside.sum())
    if total == 0:
        return RetrievalInBox(0, 0, None)
    good = int((inside & raster.valid).sum())
    return RetrievalInBox(total, good, good / total)


def class_area_fractions(raster: DecodedRaster, bbox: Sequence[float] | None = None) -> dict[int, float]:
    """Fraction of valid pixels per mineral id (explicit area fractions, no interpolation of ids)."""
    sel = raster.valid.copy()
    if bbox is not None:
        west, south, east, north = (float(v) for v in bbox)
        sel &= (raster.aux["lat"] >= south) & (raster.aux["lat"] <= north)
        sel &= (raster.aux["lon"] >= west) & (raster.aux["lon"] <= east)
    count = int(sel.sum())
    if count == 0:
        return {}
    ids, counts = np.unique(raster.data[sel], return_counts=True)
    return {int(i): float(c) / count for i, c in zip(ids, counts, strict=True)}
