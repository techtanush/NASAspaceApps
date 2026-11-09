"""ANALYSIS_GRID container (``application/x-npz``): a deterministic ZIP of ``.npy`` members.

Format (guide 08 section 3): fixed member timestamps (1980-01-01), sorted member names, stored (uncompressed), so
the bytes -- and therefore ``GridSpec.analysis_grid_sha256`` -- depend only on the content.  Members:

``aspect_deg``, ``elevation_m``, ``land``, ``quality``, ``slope_deg``, ``valid`` (``.npy``) and ``meta.json``.

``elevation_m`` is NaN-free (invalid cells hold 0 with ``valid=false``), ``valid`` means "not nodata with a full 3x3
usable neighbourhood", ``land`` is false for water, ``slope_deg`` is defined where ``valid`` (0 elsewhere) and
``aspect_deg`` is the only member that may hold NaN.  This module is the only code that parses the container; the
independent verifier and the solver both use :func:`decode_analysis_grid`.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes
from analogforge.science.errors import RasterError
from analogforge.science.geometry import AnalysisGridSpec

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
UInt8Array = NDArray[np.uint8]

MEDIA_TYPE: Final = "application/x-npz"
ARRAY_MEMBERS: Final = ("aspect_deg", "elevation_m", "land", "quality", "slope_deg", "valid")
META_MEMBER: Final = "meta.json"
MEMBER_NAMES: Final = tuple(sorted([f"{n}.npy" for n in ARRAY_MEMBERS] + [META_MEMBER]))
_ZIP_DATE: Final = (1980, 1, 1, 0, 0, 0)
_MAX_UNCOMPRESSED_BYTES: Final = 512 * 1024 * 1024
_EXPECTED_DTYPES: Final = {
    "aspect_deg": np.dtype("<f8"),
    "elevation_m": np.dtype("<f8"),
    "land": np.dtype(bool),
    "quality": np.dtype("uint8"),
    "slope_deg": np.dtype("<f8"),
    "valid": np.dtype(bool),
}


@dataclass(frozen=True)
class AnalysisGridMeta:
    cell_size_m: float
    width: int
    height: int
    origin_x_m: float
    origin_y_m: float
    crs_wkt: str
    body: str
    source_evidence_ids: tuple[str, ...]
    algorithm_id: str
    algorithm_version: str
    parameters_sha256: str

    def as_json_dict(self) -> dict[str, Any]:
        return {
            "cell_size_m": self.cell_size_m,
            "width": self.width,
            "height": self.height,
            "origin_x_m": self.origin_x_m,
            "origin_y_m": self.origin_y_m,
            "crs_wkt": self.crs_wkt,
            "body": self.body,
            "source_evidence_ids": list(self.source_evidence_ids),
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "parameters_sha256": self.parameters_sha256,
        }


@dataclass(frozen=True)
class AnalysisGrid:
    """Decoded ANALYSIS_GRID."""

    meta: AnalysisGridMeta
    elevation_m: FloatArray
    valid: BoolArray
    land: BoolArray
    slope_deg: FloatArray
    aspect_deg: FloatArray
    quality: UInt8Array

    @property
    def spec(self) -> AnalysisGridSpec:
        m = self.meta
        if m.body not in ("EARTH", "MOON", "MARS"):
            raise RasterError(f"unknown body {m.body!r} in ANALYSIS_GRID")
        return AnalysisGridSpec(m.body, m.crs_wkt, m.origin_x_m, m.origin_y_m, m.cell_size_m, m.width, m.height)  # type: ignore[arg-type]


def build_analysis_grid(
    spec: AnalysisGridSpec,
    *,
    elevation_m: FloatArray,
    valid: BoolArray,
    land: BoolArray,
    slope_deg: FloatArray,
    aspect_deg: FloatArray,
    quality: UInt8Array,
    source_evidence_ids: tuple[str, ...],
    algorithm_id: str,
    algorithm_version: str,
    parameters_sha256: str,
) -> AnalysisGrid:
    """Canonicalise raw analysis arrays (invalid cells -> elevation 0, slope 0) into an :class:`AnalysisGrid`."""
    shape = spec.shape
    for name, arr in (
        ("elevation_m", elevation_m),
        ("valid", valid),
        ("land", land),
        ("slope_deg", slope_deg),
        ("aspect_deg", aspect_deg),
        ("quality", quality),
    ):
        if arr.shape != shape:
            raise RasterError(f"{name} shape {arr.shape} does not match grid {shape}")
    meta = AnalysisGridMeta(
        cell_size_m=float(spec.cell_size_m),
        width=spec.width,
        height=spec.height,
        origin_x_m=float(spec.origin_x_m),
        origin_y_m=float(spec.origin_y_m),
        crs_wkt=spec.crs_wkt,
        body=spec.body,
        source_evidence_ids=tuple(sorted(source_evidence_ids)),
        algorithm_id=algorithm_id,
        algorithm_version=algorithm_version,
        parameters_sha256=parameters_sha256,
    )
    ok = np.asarray(valid, dtype=bool)
    aspect = np.where(ok, aspect_deg, np.nan).astype(np.float64)
    return AnalysisGrid(
        meta=meta,
        elevation_m=np.where(ok, elevation_m, 0.0).astype(np.float64),
        valid=ok,
        land=np.asarray(land, dtype=bool),
        slope_deg=np.where(ok, slope_deg, 0.0).astype(np.float64),
        aspect_deg=aspect,
        quality=np.asarray(quality, dtype=np.uint8),
    )


def _check_invariants(grid: AnalysisGrid) -> None:
    shape = (grid.meta.height, grid.meta.width)
    arrays: dict[str, NDArray[Any]] = {
        "elevation_m": grid.elevation_m, "valid": grid.valid, "land": grid.land,
        "slope_deg": grid.slope_deg, "aspect_deg": grid.aspect_deg, "quality": grid.quality,
    }  # fmt: skip
    for name, arr in arrays.items():
        if arr.shape != shape:
            raise RasterError(f"{name} shape {arr.shape} != meta shape {shape}")
        if arr.dtype != _EXPECTED_DTYPES[name]:
            raise RasterError(f"{name} dtype {arr.dtype} != {_EXPECTED_DTYPES[name]}")
    if not np.all(np.isfinite(grid.elevation_m)):
        raise RasterError("elevation_m must be NaN-free")
    if np.any(grid.elevation_m[~grid.valid] != 0.0):
        raise RasterError("invalid cells must hold elevation 0")
    if not np.all(np.isfinite(grid.slope_deg)) or np.any(grid.slope_deg < 0) or np.any(grid.slope_deg >= 90):
        raise RasterError("slope_deg must be finite in [0, 90)")
    if np.any(grid.slope_deg[~grid.valid] != 0.0):
        raise RasterError("invalid cells must hold slope 0")
    if np.any(grid.valid & ~grid.land):
        raise RasterError("valid cells must be land")
    finite_aspect = grid.aspect_deg[np.isfinite(grid.aspect_deg)]
    if np.any(finite_aspect < 0) or np.any(finite_aspect >= 360):
        raise RasterError("aspect_deg must lie in [0, 360)")
    if np.isinf(grid.aspect_deg).any():
        raise RasterError("aspect_deg may be NaN but never infinite")


def _npy_bytes(array: NDArray[Any]) -> bytes:
    buf = io.BytesIO()
    np.lib.format.write_array(buf, np.ascontiguousarray(array), version=(1, 0), allow_pickle=False)
    return buf.getvalue()


def encode_analysis_grid(grid: AnalysisGrid) -> bytes:
    """Deterministic container bytes (same grid => identical bytes)."""
    _check_invariants(grid)
    members: dict[str, bytes] = {f"{name}.npy": _npy_bytes(getattr(grid, name)) for name in ARRAY_MEMBERS}
    members[META_MEMBER] = canonical_json_bytes(grid.meta.as_json_dict())
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in MEMBER_NAMES:
            info = zipfile.ZipInfo(filename=name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, members[name])
    return out.getvalue()


def analysis_grid_sha256(grid: AnalysisGrid) -> str:
    """``GridSpec.analysis_grid_sha256`` of the container bytes."""
    return bytes_sha256(encode_analysis_grid(grid))


def write_analysis_grid(path: Path, grid: AnalysisGrid) -> tuple[str, int]:
    """Write the container; returns ``(sha256, size_bytes)``."""
    data = encode_analysis_grid(grid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return bytes_sha256(data), len(data)


def decode_analysis_grid(data: bytes) -> AnalysisGrid:
    """Parse and validate container bytes (no pickle, bounded size, exact member set)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RasterError("ANALYSIS_GRID is not a valid ZIP container") from exc
    with zf:
        infos = zf.infolist()
        if tuple(sorted(i.filename for i in infos)) != MEMBER_NAMES or len(infos) != len(MEMBER_NAMES):
            raise RasterError("ANALYSIS_GRID members differ from the specification")
        if sum(i.file_size for i in infos) > _MAX_UNCOMPRESSED_BYTES:
            raise RasterError("ANALYSIS_GRID is too large", code="RESOURCE_LIMIT")
        raw = {i.filename: zf.read(i) for i in infos}
    try:
        meta_json = json.loads(raw[META_MEMBER].decode("utf-8"))
        meta = AnalysisGridMeta(
            cell_size_m=float(meta_json["cell_size_m"]),
            width=int(meta_json["width"]),
            height=int(meta_json["height"]),
            origin_x_m=float(meta_json["origin_x_m"]),
            origin_y_m=float(meta_json["origin_y_m"]),
            crs_wkt=str(meta_json["crs_wkt"]),
            body=str(meta_json["body"]),
            source_evidence_ids=tuple(str(v) for v in meta_json["source_evidence_ids"]),
            algorithm_id=str(meta_json["algorithm_id"]),
            algorithm_version=str(meta_json["algorithm_version"]),
            parameters_sha256=str(meta_json["parameters_sha256"]),
        )
    except (KeyError, ValueError, TypeError, UnicodeDecodeError) as exc:
        raise RasterError("ANALYSIS_GRID meta.json is malformed") from exc
    arrays: dict[str, Any] = {}
    for name in ARRAY_MEMBERS:
        try:
            arrays[name] = np.lib.format.read_array(io.BytesIO(raw[f"{name}.npy"]), allow_pickle=False)
        except ValueError as exc:
            raise RasterError(f"ANALYSIS_GRID member {name} is not a plain .npy array") from exc
    grid = AnalysisGrid(
        meta=meta,
        elevation_m=arrays["elevation_m"],
        valid=arrays["valid"],
        land=arrays["land"],
        slope_deg=arrays["slope_deg"],
        aspect_deg=arrays["aspect_deg"],
        quality=arrays["quality"],
    )
    _check_invariants(grid)
    return grid


def read_analysis_grid(path: Path) -> AnalysisGrid:
    """Read and validate a container from disk."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RasterError(f"cannot read ANALYSIS_GRID {path.name}") from exc
    return decode_analysis_grid(data)
