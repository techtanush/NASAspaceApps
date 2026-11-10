"""NASADEM / SRTM ``.hgt`` decoding and seam-aware mosaicking.

Format assumptions (documented, tested only on format-faithful synthetic tiles): ``.hgt`` is big-endian
signed 16-bit, ``N x N`` samples (1201 or 3601), first row = northern edge, samples registered at integer
degrees so adjoining tiles share one row/column. ``-32768`` is void. ``.num`` (source codes) and ``.swb``
(water body) are ``uint8`` rasters of the same shape and stay separate arrays: NUM is a coded provenance
indicator, never a per-pixel uncertainty. Heights are EGM96 orthometric, horizontal reference WGS84.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from analogforge.adapters.source_http.archive import ArchiveLimits, safe_extract_zip
from analogforge.adapters.source_http.decoded import DecodedRaster, RasterMetadata
from analogforge.adapters.source_http.errors import AdapterError

HGT_VOID = -32768
STANDARD_SAMPLES = frozenset({1201, 3601})
TILE_RE = re.compile(r"([ns])(\d{2})([ew])(\d{3})", re.IGNORECASE)
WGS84_WKT = (
    'GEOGCRS["WGS 84",DATUM["World Geodetic System 1984",ELLIPSOID["WGS 84",6378137,298.257223563,'
    'LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0],CS[ellipsoidal,2],AXIS["longitude",east,ORDER[1]],'
    'AXIS["latitude",north,ORDER[2]],ANGLEUNIT["degree",0.0174532925199433]]'
)
VERTICAL_REFERENCE = "EGM96 geoid (orthometric height); horizontal reference WGS84"
NASADEM_ARCHIVE_SUFFIXES = frozenset({".hgt", ".num", ".swb", ".nc", ".met", ".xml", ".txt", ".json"})


@dataclass(frozen=True)
class NasademParams:
    adapter_id: str = "earth_nasadem_hgt_v001"
    expected_samples: int | None = None  # None accepts only the standard 1201 / 3601 tile shapes
    work_dir: Path | None = None  # extraction directory for zips (default: next to the archive)


def parse_tile_name(name: str) -> tuple[int, int]:
    """Return (lat0, lon0) of the south-west corner encoded in a tile name like ``n30w100``."""
    match = TILE_RE.search(name)
    if match is None:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", f"cannot read tile corner from name {name!r}", detail_code="METADATA_INCOMPLETE"
        )
    lat = int(match.group(2)) * (1 if match.group(1).lower() == "n" else -1)
    lon = int(match.group(4)) * (1 if match.group(3).lower() == "e" else -1)
    return lat, lon


def _read_samples(path: Path, dtype: str, expected_samples: int | None) -> NDArray[np.generic]:
    size = path.stat().st_size
    itemsize = np.dtype(dtype).itemsize
    if size % itemsize:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"{path.name}: size {size} is not a multiple of {itemsize}",
            detail_code="SHAPE_MISMATCH",
        )
    count = size // itemsize
    n = math.isqrt(count)
    allowed = STANDARD_SAMPLES if expected_samples is None else frozenset({expected_samples})
    if n * n != count or n not in allowed:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"{path.name}: {count} samples is not a square tile of {sorted(allowed)} samples per side",
            detail_code="SHAPE_MISMATCH",
        )
    return np.fromfile(path, dtype=dtype).reshape(n, n)


def _find_member(files: list[Path], suffix: str, stem: str) -> Path | None:
    matches = sorted(p for p in files if p.suffix.lower() == suffix and p.stem.lower() == stem.lower())
    return matches[0] if matches else None


def decode(path: Path, params: NasademParams | None = None) -> DecodedRaster:
    """Decode one tile from a ``.zip`` (extracted safely) or a bare ``.hgt``."""
    prm = params or NasademParams()
    if path.suffix.lower() == ".zip":
        work = prm.work_dir or path.with_name(path.stem + "_members")
        files = safe_extract_zip(path, work, ArchiveLimits(max_members=16, allowed_suffixes=NASADEM_ARCHIVE_SUFFIXES))
    else:
        files = [path] + [p for p in path.parent.iterdir() if p.stem.lower() == path.stem.lower() and p != path]
    hgt_files = sorted(p for p in files if p.suffix.lower() == ".hgt")
    if len(hgt_files) != 1:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"expected exactly one .hgt member, found {len(hgt_files)}",
            detail_code="METADATA_INCOMPLETE",
        )
    hgt = hgt_files[0]
    lat0, lon0 = parse_tile_name(hgt.stem)
    raw = _read_samples(hgt, ">i2", prm.expected_samples)
    n = raw.shape[0]
    void = raw == HGT_VOID
    data = np.where(void, np.nan, raw.astype(np.float64))
    valid = ~void
    aux: dict[str, NDArray[np.generic]] = {}
    notes = [
        "Heights are EGM96 orthometric; not ellipsoidal and not bare-ground surveyed terrain.",
        "Samples are registered at integer degrees; adjoining tiles share a border row/column.",
        "One arc-second spacing is angular, not a square 30 m pixel and not independent 30 m resolution.",
    ]
    num_path = _find_member(files, ".num", hgt.stem)
    if num_path is not None:
        aux["num"] = _read_samples(num_path, "u1", n)
        notes.append("NUM is a coded source indicator, not a per-pixel uncertainty in metres.")
    swb_path = _find_member(files, ".swb", hgt.stem)
    water = np.zeros((n, n), dtype=bool)
    if swb_path is not None:
        water = _read_samples(swb_path, "u1", n) != 0
        notes.append("SWB interpreted as non-zero = water body (unverified against a real tile).")
    else:
        notes.append("No water-body (.swb) member present; water cells cannot be excluded.")
    aux["water"] = water
    aux["land"] = valid & ~water
    step = 1.0 / (n - 1)
    meta = RasterMetadata(
        adapter_id=prm.adapter_id,
        body="EARTH",
        quantity="orthometric_height",
        units="m",
        vertical_reference=VERTICAL_REFERENCE,
        crs_wkt=WGS84_WKT,
        transform=(step, 0.0, lon0 - step / 2, 0.0, -step, lat0 + 1 + step / 2),
        width=n,
        height=n,
        pixel_registration="CELL_CENTER_AT_INTEGER_DEGREE",
        longitude_domain="NEG180_180",
        nodata_raw=float(HGT_VOID),
        product_id=hgt.stem.lower(),
        notes=tuple(notes),
        attributes={"tile_lat0": str(lat0), "tile_lon0": str(lon0), "samples_per_side": str(n)},
    )
    return DecodedRaster(data=data, valid=valid, metadata=meta, aux=aux)


def mosaic(tiles: list[DecodedRaster]) -> DecodedRaster:
    """Merge adjoining tiles de-duplicating shared border samples; report disagreements, never hide them."""
    if not tiles:
        raise AdapterError("NO_COVERAGE", "no tiles to mosaic", detail_code="NO_GRANULES")
    ordered = sorted(tiles, key=lambda t: t.metadata.product_id or "")
    n = ordered[0].metadata.width
    keys: set[tuple[int, int]] = set()
    for tile in ordered:
        if tile.metadata.width != n or tile.metadata.height != n:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID",
                "tiles of differing sample counts cannot be mosaicked",
                detail_code="SHAPE_MISMATCH",
            )
        key = (int(tile.metadata.attributes["tile_lat0"]), int(tile.metadata.attributes["tile_lon0"]))
        if key in keys:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID", f"duplicate tile {tile.metadata.product_id}", detail_code="DUPLICATE_TILE"
            )
        keys.add(key)
    lat_min = min(k[0] for k in keys)
    lat_max = max(k[0] for k in keys)
    lon_min = min(k[1] for k in keys)
    lon_max = max(k[1] for k in keys)
    step_n = n - 1
    rows = (lat_max - lat_min + 1) * step_n + 1
    cols = (lon_max - lon_min + 1) * step_n + 1
    data = np.full((rows, cols), np.nan)
    valid = np.zeros((rows, cols), dtype=bool)
    covered = np.zeros((rows, cols), dtype=bool)
    water = np.zeros((rows, cols), dtype=bool)
    has_num = all("num" in t.aux for t in ordered)
    num = np.zeros((rows, cols), dtype=np.uint8)
    mismatched = 0
    deduplicated = 0
    for tile in ordered:
        lat0 = int(tile.metadata.attributes["tile_lat0"])
        lon0 = int(tile.metadata.attributes["tile_lon0"])
        r0 = (lat_max - lat0) * step_n
        c0 = (lon0 - lon_min) * step_n
        region = (slice(r0, r0 + n), slice(c0, c0 + n))
        g_valid = valid[region]
        both = g_valid & tile.valid
        deduplicated += int(both.sum())
        mismatched += int((both & (data[region] != tile.data)).sum())
        take = tile.valid & ~g_valid
        g_data = data[region]
        g_data[take] = tile.data[take]
        g_valid |= take
        fresh = ~covered[region]
        g_water = water[region]
        g_water[fresh] = tile.aux["water"][fresh]
        if has_num:
            g_num = num[region]
            g_num[fresh] = tile.aux["num"][fresh]
        covered[region] = True
    base = ordered[0].metadata
    step = 1.0 / step_n
    notes = [
        *base.notes,
        f"Mosaic of {len(ordered)} tile(s); {deduplicated} shared border sample(s) de-duplicated.",
        "Tile precedence is deterministic: lexicographic tile name; first valid sample wins.",
    ]
    if mismatched:
        notes.append(f"{mismatched} shared sample(s) disagreed between tiles; first tile retained.")
    aux: dict[str, NDArray[np.generic]] = {"water": water, "land": valid & ~water, "covered": covered}
    if has_num:
        aux["num"] = num
    meta = RasterMetadata(
        adapter_id=base.adapter_id,
        body="EARTH",
        quantity=base.quantity,
        units="m",
        vertical_reference=base.vertical_reference,
        crs_wkt=base.crs_wkt,
        transform=(step, 0.0, lon_min - step / 2, 0.0, -step, lat_max + 1 + step / 2),
        width=cols,
        height=rows,
        pixel_registration=base.pixel_registration,
        longitude_domain="NEG180_180",
        nodata_raw=base.nodata_raw,
        product_id=None,
        notes=tuple(notes),
        attributes={
            "tiles": ",".join(t.metadata.product_id or "" for t in ordered),
            "seam_mismatch_cells": str(mismatched),
            "seam_deduplicated_samples": str(deduplicated),
            "samples_per_side": str(n),
        },
    )
    return DecodedRaster(data=data, valid=valid, metadata=meta, aux=aux)
