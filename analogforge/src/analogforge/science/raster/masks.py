"""Boolean-mask helpers for rasters.

Invariants: a cell is *usable* only if its value is finite, not the declared nodata value and not water.  Missing
support is never filled with zero or interpolated; the 3x3 (or wider) support requirement is expressed as an
erosion of the usable mask with the raster border treated as *missing*.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from analogforge.science.errors import RasterError

BoolArray = NDArray[np.bool_]
FloatArray = NDArray[np.float64]


def nodata_mask(values: NDArray[np.number], nodata_value: float | None) -> BoolArray:
    """True where the source is missing: non-finite, or equal to the declared nodata value."""
    arr = np.asarray(values)
    missing: BoolArray = ~np.isfinite(arr.astype(np.float64, copy=False))
    if nodata_value is not None:
        missing = missing | (arr == nodata_value)
    return missing


def usable_mask(
    values: NDArray[np.number],
    nodata_value: float | None = None,
    water: BoolArray | None = None,
    extra_invalid: BoolArray | None = None,
) -> BoolArray:
    """Cells that may take part in derivative computations (finite, not nodata, not water, not extra-invalid)."""
    usable: BoolArray = ~nodata_mask(values, nodata_value)
    if water is not None:
        _same_shape(usable, water, "water")
        usable = usable & ~water
    if extra_invalid is not None:
        _same_shape(usable, extra_invalid, "extra_invalid")
        usable = usable & ~extra_invalid
    return usable


def _same_shape(a: NDArray[np.generic], b: NDArray[np.generic], name: str) -> None:
    if a.shape != b.shape:
        raise RasterError(f"{name} mask shape {b.shape} does not match raster shape {a.shape}")


def full_support(usable: BoolArray, window_cells: int = 3) -> BoolArray:
    """Cells whose whole ``window_cells`` x ``window_cells`` neighbourhood is usable (border counts as missing)."""
    if window_cells < 1 or window_cells % 2 == 0:
        raise RasterError("window_cells must be an odd positive integer")
    if window_cells == 1:
        return usable.copy()
    structure = np.ones((window_cells, window_cells), dtype=bool)
    eroded = ndimage.binary_erosion(usable, structure=structure, border_value=0)
    return np.asarray(eroded, dtype=bool)


def dilate(mask: BoolArray, radius_cells: int) -> BoolArray:
    """Dilate a mask by a disk of ``radius_cells`` (0 returns a copy)."""
    if radius_cells < 0:
        raise RasterError("radius_cells must be >= 0")
    if radius_cells == 0:
        return mask.copy()
    yy, xx = np.mgrid[-radius_cells : radius_cells + 1, -radius_cells : radius_cells + 1]
    disk = (xx * xx + yy * yy) <= radius_cells * radius_cells
    return np.asarray(ndimage.binary_dilation(mask, structure=disk), dtype=bool)


def dilate_metres(mask: BoolArray, radius_m: float, cell_size_m: float) -> BoolArray:
    """Dilation by a physical radius; the radius rounds *up* to whole cells (conservative for hazards)."""
    if radius_m < 0 or cell_size_m <= 0:
        raise RasterError("radius_m must be >= 0 and cell_size_m > 0")
    return dilate(mask, int(np.ceil(radius_m / cell_size_m - 1e-12)))


def fraction(mask: BoolArray, within: BoolArray | None = None) -> float:
    """Fraction of cells that are True (optionally inside ``within``); 0.0 for an empty denominator is *not*
    returned: an empty denominator raises, because a missing fraction must stay unknown."""
    if within is None:
        total = mask.size
        hits = int(mask.sum())
    else:
        _same_shape(mask, within, "within")
        total = int(within.sum())
        hits = int((mask & within).sum())
    if total == 0:
        raise RasterError("empty denominator for a mask fraction")
    return hits / total
