"""Detrended RMS height (architecture 10 section 5).

``detrended_rms_height_m(window) = sqrt(mean((z - z_plane)^2))`` where ``z_plane`` is the least-squares plane of the
window.  The residual of a plane fit does not depend on the (linear) coordinate system, so the fit is done in the
orthogonal index basis ``{1, i, j}``; this makes the result identical for anisotropic or rotated rasters.  Only the
*physical* window size depends on the pixel geometry and is reported in the metric id.

Numerics: values are taken relative to the window-centre sample and the residuals are formed explicitly, so a
perfect plane returns ~1e-14 m (the analytic roughness of a plane is exactly zero).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError
from analogforge.science.raster.masks import full_support

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _check(elevation: FloatArray, usable: BoolArray, window_cells: int) -> int:
    if elevation.ndim != 2 or elevation.shape != usable.shape:
        raise RasterError("elevation and usable must be 2-D arrays of the same shape")
    if window_cells < 3 or window_cells % 2 == 0:
        raise RasterError("window_cells must be an odd integer >= 3")
    return window_cells // 2


def physical_window_m(window_cells: int, cell_size_m: float) -> float:
    """Physical edge length of an odd cell window."""
    return window_cells * cell_size_m


def roughness_metric_id(window_cells: int, cell_size_m: float) -> str:
    """``detrended_rms_height_m@<window_m>`` with the physical window in the id (e.g. ``@180``)."""
    return f"detrended_rms_height_m@{physical_window_m(window_cells, cell_size_m):g}"


def relief_metric_id(window_cells: int, cell_size_m: float) -> str:
    """``robust_relief_m@<window_m>``."""
    return f"robust_relief_m@{physical_window_m(window_cells, cell_size_m):g}"


def detrended_rms_height_m(elevation: FloatArray, usable: BoolArray, window_cells: int) -> tuple[FloatArray, BoolArray]:
    """Per-cell detrended RMS height over ``window_cells`` x ``window_cells``; NaN where support is incomplete."""
    h = _check(elevation, usable, window_cells)
    valid = full_support(usable, window_cells)
    height, width = elevation.shape
    filled = np.where(usable, elevation, 0.0).astype(np.float64, copy=False)
    padded = np.pad(filled, h, mode="constant", constant_values=0.0)
    n = float(window_cells * window_cells)
    offsets = [(i, j) for i in range(-h, h + 1) for j in range(-h, h + 1)]  # (row offset, col offset)

    def view(dr: int, dc: int) -> FloatArray:
        return padded[h + dr : h + dr + height, h + dc : h + dc + width] - filled

    sum_d = np.zeros((height, width))
    sum_id = np.zeros((height, width))
    sum_jd = np.zeros((height, width))
    for dr, dc in offsets:
        d = view(dr, dc)
        sum_d += d
        sum_id += dr * d
        sum_jd += dc * d
    sum_ii = float(sum(dr * dr for dr, _ in offsets))
    sum_jj = float(sum(dc * dc for _, dc in offsets))
    mean = sum_d / n
    slope_i = sum_id / sum_ii
    slope_j = sum_jd / sum_jj
    ss = np.zeros((height, width))
    for dr, dc in offsets:
        resid = view(dr, dc) - mean - slope_i * dr - slope_j * dc
        ss += resid * resid
    rms = np.sqrt(ss / n)
    rms[~valid] = np.nan
    return rms, valid


def tpi_m(elevation: FloatArray, usable: BoolArray, window_cells: int) -> tuple[FloatArray, BoolArray]:
    """Topographic position index: centre elevation minus the mean of the window *including* the centre."""
    h = _check(elevation, usable, window_cells)
    valid = full_support(usable, window_cells)
    height, width = elevation.shape
    filled = np.where(usable, elevation, 0.0).astype(np.float64, copy=False)
    padded = np.pad(filled, h, mode="constant", constant_values=0.0)
    total = np.zeros((height, width))
    for dr in range(-h, h + 1):
        for dc in range(-h, h + 1):
            total += padded[h + dr : h + dr + height, h + dc : h + dc + width] - filled
    tpi = -total / float(window_cells * window_cells)
    tpi[~valid] = np.nan
    return tpi, valid
