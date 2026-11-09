"""Normalisation of raw raster values to elevation metres, and area-average aggregation.

* Scale/offset are applied **exactly once**, and the :class:`NormalizationRecord` says on which side
  (``ANALYSIS`` or ``READER``).  Nodata is matched on the *raw* values, before any scaling.
* ``RADIUS`` products are converted to height by subtracting the reference radius exactly once.
* Coarsening is by area averaging (never interpolation); categorical ids are never averaged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError
from analogforge.science.raster.masks import nodata_mask

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int64]

ScaleSide = Literal["NONE", "ANALYSIS", "READER"]
_UNIT_TO_M = {"m": 1.0, "km": 1000.0}
# Heights relative to a reference sphere never legitimately reach this magnitude on Earth, the Moon or Mars.
SUSPECT_RADIUS_MAGNITUDE_M = 100_000.0


@dataclass(frozen=True)
class NormalizationRecord:
    """Exactly what was done to the raw values."""

    quantity: Literal["ELEVATION", "RADIUS"]
    units_in: str
    scale_factor: float
    offset: float
    scale_applied_by: ScaleSide
    unit_factor_to_m: float
    reference_radius_m: float | None
    radius_subtracted: bool


def normalize_elevation(
    raw: NDArray[np.number],
    *,
    quantity: Literal["ELEVATION", "RADIUS"],
    units: Literal["m", "km"],
    scale_factor: float = 1.0,
    offset: float = 0.0,
    scale_already_applied: bool = False,
    reference_radius_m: float | None = None,
    nodata_value: float | None = None,
) -> tuple[FloatArray, BoolArray, NormalizationRecord]:
    """Elevation in metres (NaN where missing), the missing mask and the normalisation record.

    ``physical = raw * scale_factor + offset`` is applied unless ``scale_already_applied`` (the reader did it).
    ``units`` describes ``physical``.  For ``RADIUS`` the height is ``radius_m - reference_radius_m``.
    """
    if quantity not in ("ELEVATION", "RADIUS"):
        raise RasterError(f"quantity {quantity!r} is not an elevation-like quantity", code="UNSUPPORTED_PRODUCT")
    if units not in _UNIT_TO_M:
        raise RasterError(f"unsupported elevation unit {units!r}", code="UNSUPPORTED_PRODUCT")
    if not (math.isfinite(scale_factor) and scale_factor != 0.0 and math.isfinite(offset)):
        raise RasterError("scale_factor must be finite and non-zero, offset finite")
    if quantity == "RADIUS" and (reference_radius_m is None or not reference_radius_m > 0):
        raise RasterError("a RADIUS product needs a positive reference_radius_m")
    values = np.asarray(raw)
    missing = nodata_mask(values, nodata_value)
    as_float = values.astype(np.float64)
    physical = as_float if scale_already_applied else as_float * scale_factor + offset
    metres = physical * _UNIT_TO_M[units]
    radius_subtracted = False
    if quantity == "RADIUS":
        assert reference_radius_m is not None
        metres = metres - reference_radius_m
        radius_subtracted = True
    out = np.where(missing, np.nan, metres)
    record = NormalizationRecord(
        quantity=quantity,
        units_in=units,
        scale_factor=scale_factor,
        offset=offset,
        scale_applied_by="READER"
        if scale_already_applied
        else ("NONE" if (scale_factor == 1.0 and offset == 0.0) else "ANALYSIS"),
        unit_factor_to_m=_UNIT_TO_M[units],
        reference_radius_m=reference_radius_m if quantity == "RADIUS" else None,
        radius_subtracted=radius_subtracted,
    )
    return np.asarray(out, dtype=np.float64), missing, record


def looks_like_radius_not_height(elevation_m: FloatArray) -> bool:
    """Heuristic guard: median |value| above 100 km means a radius was labelled as elevation."""
    finite = elevation_m[np.isfinite(elevation_m)]
    if finite.size == 0:
        return False
    return bool(np.median(np.abs(finite)) > SUSPECT_RADIUS_MAGNITUDE_M)


def aggregate_blocks(
    values: FloatArray, valid: BoolArray, factor: int, min_valid_fraction: float = 1.0
) -> tuple[FloatArray, BoolArray]:
    """Area-average ``factor`` x ``factor`` blocks of valid cells.

    A block is valid only if at least ``min_valid_fraction`` of its cells are valid (default: all), so aggregation
    never bridges a nodata hole.  Trailing partial blocks are dropped.  Invalid blocks hold NaN.
    """
    if factor < 1:
        raise RasterError("aggregation factor must be >= 1")
    if values.shape != valid.shape or values.ndim != 2:
        raise RasterError("values and valid must be 2-D arrays of the same shape")
    if not 0.0 < min_valid_fraction <= 1.0:
        raise RasterError("min_valid_fraction must be in (0, 1]")
    height, width = (values.shape[0] // factor) * factor, (values.shape[1] // factor) * factor
    if height == 0 or width == 0:
        raise RasterError("raster is smaller than one aggregation block", code="SCALE_INCOMPATIBLE")
    v = np.where(valid, values, 0.0)[:height, :width].reshape(height // factor, factor, width // factor, factor)
    m = valid[:height, :width].reshape(height // factor, factor, width // factor, factor)
    count = m.sum(axis=(1, 3))
    total = v.sum(axis=(1, 3))
    block_valid = count >= min_valid_fraction * factor * factor - 1e-9
    block_valid &= count > 0
    mean = np.full(count.shape, np.nan)
    np.divide(total, count, out=mean, where=block_valid)
    return mean, np.asarray(block_valid, dtype=bool)


def aggregate_any(mask: BoolArray, factor: int) -> BoolArray:
    """A block is flagged if *any* cell is flagged (conservative for water/hazard masks)."""
    if factor < 1:
        raise RasterError("aggregation factor must be >= 1")
    height, width = (mask.shape[0] // factor) * factor, (mask.shape[1] // factor) * factor
    if height == 0 or width == 0:
        raise RasterError("raster is smaller than one aggregation block", code="SCALE_INCOMPATIBLE")
    blocks = mask[:height, :width].reshape(height // factor, factor, width // factor, factor)
    return np.asarray(blocks.any(axis=(1, 3)), dtype=bool)


def aggregate_categorical_mode(ids: NDArray[np.integer], factor: int, nodata_id: int) -> tuple[IntArray, FloatArray]:
    """Dominant class per block and its area share of the block (ties: smallest id; all-nodata: ``nodata_id``).

    Class ids are categorical: they are never averaged or interpolated.
    """
    if factor < 1:
        raise RasterError("aggregation factor must be >= 1")
    height, width = (ids.shape[0] // factor) * factor, (ids.shape[1] // factor) * factor
    if height == 0 or width == 0:
        raise RasterError("raster is smaller than one aggregation block", code="SCALE_INCOMPATIBLE")
    blocks = ids[:height, :width].reshape(height // factor, factor, width // factor, factor)
    flat = blocks.transpose(0, 2, 1, 3).reshape(height // factor, width // factor, factor * factor)
    out = np.full(flat.shape[:2], nodata_id, dtype=np.int64)
    share = np.zeros(flat.shape[:2], dtype=np.float64)
    for r in range(flat.shape[0]):
        for c in range(flat.shape[1]):
            cell = flat[r, c]
            classes, counts = np.unique(cell[cell != nodata_id], return_counts=True)
            if classes.size == 0:
                continue
            best = int(np.argmax(counts))  # np.unique sorts ids ascending: argmax keeps the smallest on ties
            out[r, c] = int(classes[best])
            share[r, c] = float(counts[best]) / float(factor * factor)
    return out, share


def class_area_fractions(ids: NDArray[np.integer], classes: tuple[int, ...], nodata_id: int) -> dict[int, float]:
    """Fraction of valid (non-nodata) cells in each class, plus nothing interpolated."""
    valid = ids != nodata_id
    total = int(valid.sum())
    if total == 0:
        raise RasterError("no valid class cells")
    return {int(cls): float(np.count_nonzero(ids == cls)) / total for cls in classes}
