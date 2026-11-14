"""Robust relief: ``quantile(z, 0.95) - quantile(z, 0.05)`` over a window (architecture 10 section 5).

The quantile implementation is NumPy's ``method="linear"`` (Hyndman-Fan type 7).  Relief includes slope-induced
relief and must never be called obstacle height or compared with ground clearance.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError
from analogforge.science.raster.masks import full_support

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

_CHUNK_ROWS = 64


def robust_relief_m(
    elevation: FloatArray,
    usable: BoolArray,
    window_cells: int,
    q_low: float = 0.05,
    q_high: float = 0.95,
) -> tuple[FloatArray, BoolArray]:
    """Per-cell robust relief; NaN where the whole window is not usable."""
    if elevation.ndim != 2 or elevation.shape != usable.shape:
        raise RasterError("elevation and usable must be 2-D arrays of the same shape")
    if window_cells < 3 or window_cells % 2 == 0:
        raise RasterError("window_cells must be an odd integer >= 3")
    if not 0.0 <= q_low < q_high <= 1.0:
        raise RasterError("quantiles must satisfy 0 <= q_low < q_high <= 1")
    h = window_cells // 2
    valid = full_support(usable, window_cells)
    height, width = elevation.shape
    filled = np.where(usable, elevation, 0.0).astype(np.float64, copy=False)
    padded = np.pad(filled, h, mode="constant", constant_values=0.0)
    out = np.full((height, width), np.nan)
    for r0 in range(0, height, _CHUNK_ROWS):
        r1 = min(height, r0 + _CHUNK_ROWS)
        stack = np.empty((window_cells * window_cells, r1 - r0, width))
        k = 0
        for dr in range(-h, h + 1):
            for dc in range(-h, h + 1):
                stack[k] = padded[h + r0 + dr : h + r1 + dr, h + dc : h + dc + width]
                k += 1
        lo, hi = np.quantile(stack, [q_low, q_high], axis=0, method="linear")
        out[r0:r1] = hi - lo
    out[~valid] = np.nan
    return out, valid
