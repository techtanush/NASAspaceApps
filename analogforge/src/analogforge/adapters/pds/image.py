"""Format-neutral description of a labelled planetary raster (output of the PDS3 / PDS4 label readers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from analogforge.adapters.source_http.errors import AdapterError

_UNIT_TO_METRES = {"m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
                   "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0, "kilometre": 1000.0,
                   "kilometres": 1000.0}
_UNIT_TO_KELVIN = {"k": 0.0, "kelvin": 0.0, "kelvins": 0.0}


def metres_factor(unit: str | None) -> float | None:
    return None if unit is None else _UNIT_TO_METRES.get(unit.strip().lower())


def is_kelvin(unit: str | None) -> bool:
    return unit is not None and unit.strip().lower() in _UNIT_TO_KELVIN


@dataclass(frozen=True)
class ProductImage:
    """Raw label facts plus the scaled array. ``values`` has had ``raw * scale + offset`` applied exactly once."""

    product_id: str | None
    body: str | None  # upper-case target name from the label
    values: NDArray[np.float64]  # NaN at missing/invalid raw samples
    valid: NDArray[np.bool_]
    scale: float
    offset: float
    unit: str | None
    missing_raw: tuple[float, ...]
    west: float | None
    east: float | None
    south: float | None
    north: float | None
    resolution_px_per_deg: float | None
    a_radius_m: float | None
    longitude_direction: str | None
    latitude_type: str | None
    attributes: dict[str, str] = field(default_factory=dict)


def safe_sibling(label_path: Path, name: str) -> Path:
    """Resolve a data-file name from a label next to it, refusing traversal and absolute paths."""
    if not name or "\\" in name or name.startswith("/") or ".." in Path(name).parts:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"unsafe data file reference {name!r} in label",
                           detail_code="ARCHIVE_PATH_TRAVERSAL")
    target = (label_path.parent / name).resolve()
    root = label_path.parent.resolve()
    if root not in target.parents:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"data file {name!r} escapes the label directory",
                           detail_code="ARCHIVE_PATH_TRAVERSAL")
    if not target.is_file():
        # Case-insensitive fallback: PDS archives mix upper/lower case between label and file names.
        for candidate in sorted(root.iterdir()):
            if candidate.name.lower() == Path(name).name.lower() and candidate.is_file():
                return candidate
        raise AdapterError("SOURCE_CONTENT_INVALID", f"data file {name!r} referenced by the label is missing",
                           detail_code="METADATA_INCOMPLETE")
    return target


def read_array(path: Path, dtype: str, lines: int, samples: int, offset_bytes: int) -> NDArray[np.generic]:
    expected = lines * samples * np.dtype(dtype).itemsize
    actual = path.stat().st_size - offset_bytes
    if actual != expected:
        raise AdapterError("SOURCE_CONTENT_INVALID",
                           f"{path.name}: data region is {actual} bytes, label implies {expected} "
                           f"({lines} x {samples} x {np.dtype(dtype).itemsize})", detail_code="SHAPE_MISMATCH")
    with path.open("rb") as handle:
        handle.seek(offset_bytes)
        return np.frombuffer(handle.read(expected), dtype=dtype).reshape(lines, samples)


def scale_once(raw: NDArray[np.generic], scale: float, offset: float,
               missing: tuple[float, ...]) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Apply ``raw * scale + offset`` exactly once; missing raw samples become NaN (never 0)."""
    bad = np.zeros(raw.shape, dtype=bool)
    for constant in missing:
        bad |= raw == constant
    if np.issubdtype(raw.dtype, np.floating):
        bad |= ~np.isfinite(raw)
    values = raw.astype(np.float64) * scale + offset
    values[bad] = np.nan
    return values, ~bad
