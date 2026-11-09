"""Surface slope and aspect from a 3x3 least-squares plane in metric coordinates (architecture 10 section 4).

For each cell centre the nine neighbouring elevations are fitted with ``z = a*x + b*y + c`` using the *true metric
offsets* of the raster (so anisotropic and rotated rasters give the same physical slope).  The fit is linear in the
data, so its gradient is a fixed weighted sum computed once from the pseudo-inverse of the design matrix.

``surface_slope_deg = atan(hypot(a, b))``; aspect is the downslope azimuth clockwise from north, ``atan2(-a, -b)``
for an (east, north) coordinate system, and ``NaN`` (null) when the gradient is below ``flat_gradient_tolerance``.
Cells without a fully usable 3x3 neighbourhood are *invalid* (``NaN`` slope), never zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError
from analogforge.science.features.coverage import classify_cells
from analogforge.science.geometry import PixelGeometry
from analogforge.science.raster.masks import full_support

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
UInt8Array = NDArray[np.uint8]

DEFAULT_FLAT_GRADIENT_TOLERANCE = 1e-12
_OFFSETS: tuple[tuple[int, int], ...] = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))


@lru_cache(maxsize=256)
def _plane_weights(geometry: PixelGeometry) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Weights ``(w_a, w_b)`` such that ``a = sum(w_a[k] * z_k)`` and ``b = sum(w_b[k] * z_k)`` (k over the 3x3)."""
    design = np.empty((9, 3), dtype=np.float64)
    for k, (dr, dc) in enumerate(_OFFSETS):
        x, y = geometry.offset_xy(dc, dr)
        design[k] = (x, y, 1.0)
    normal = design.T @ design
    pinv = np.linalg.solve(normal, design.T)  # (3, 9)
    return tuple(float(v) for v in pinv[0]), tuple(float(v) for v in pinv[1])


def plane_stencil(geometry: PixelGeometry) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """The two 3x3 stencils ``(d/dx, d/dy)`` (rows = row offset -1..1, cols = column offset -1..1)."""
    wa, wb = _plane_weights(geometry)
    return np.array(wa, dtype=np.float64).reshape(3, 3), np.array(wb, dtype=np.float64).reshape(3, 3)


@dataclass(frozen=True)
class GradientField:
    """Plane-fit gradient in (east, north) metres; ``NaN`` where the 3x3 support is incomplete."""

    dz_dx: FloatArray
    dz_dy: FloatArray
    valid: BoolArray


def plane_fit_gradient(elevation: FloatArray, usable: BoolArray, geometry: PixelGeometry) -> GradientField:
    """Least-squares plane gradient over each fully usable 3x3 neighbourhood."""
    if elevation.shape != usable.shape or elevation.ndim != 2:
        raise RasterError("elevation and usable must be 2-D arrays of the same shape")
    height, width = elevation.shape
    valid = full_support(usable, 3)
    wa, wb = _plane_weights(geometry)
    filled = np.where(usable, elevation, 0.0).astype(np.float64, copy=False)
    padded = np.pad(filled, 1, mode="constant", constant_values=0.0)
    centre = filled
    gx = np.zeros((height, width), dtype=np.float64)
    gy = np.zeros((height, width), dtype=np.float64)
    for k, (dr, dc) in enumerate(_OFFSETS):
        # differences to the centre sample keep the arithmetic exact for planes on large elevation offsets
        diff = padded[1 + dr : 1 + dr + height, 1 + dc : 1 + dc + width] - centre
        gx += wa[k] * diff
        gy += wb[k] * diff
    gx[~valid] = np.nan
    gy[~valid] = np.nan
    return GradientField(dz_dx=gx, dz_dy=gy, valid=valid)


@dataclass(frozen=True)
class SlopeField:
    """Per-cell surface slope (deg) and downslope aspect (deg clockwise from north, NaN if flat/invalid)."""

    slope_deg: FloatArray
    aspect_deg: FloatArray
    valid: BoolArray
    dz_dx: FloatArray
    dz_dy: FloatArray


def slope_from_gradient(dz_dx: FloatArray, dz_dy: FloatArray) -> FloatArray:
    """``atan(hypot(a, b))`` in degrees (NaN propagates)."""
    return np.asarray(np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))), dtype=np.float64)


def aspect_from_gradient(
    dz_dx: FloatArray, dz_dy: FloatArray, flat_gradient_tolerance: float = DEFAULT_FLAT_GRADIENT_TOLERANCE
) -> FloatArray:
    """Downslope azimuth clockwise from north in ``[0, 360)``; NaN where the gradient is flat or undefined."""
    with np.errstate(invalid="ignore"):
        aspect = np.degrees(np.arctan2(-dz_dx, -dz_dy)) % 360.0
        flat = ~(np.hypot(dz_dx, dz_dy) > flat_gradient_tolerance)
    aspect = np.asarray(aspect, dtype=np.float64)
    aspect[flat] = np.nan
    return aspect


def compute_slope_aspect(
    elevation: FloatArray,
    usable: BoolArray,
    geometry: PixelGeometry,
    flat_gradient_tolerance: float = DEFAULT_FLAT_GRADIENT_TOLERANCE,
) -> SlopeField:
    """Slope and aspect on the whole raster; invalid cells hold NaN."""
    grad = plane_fit_gradient(elevation, usable, geometry)
    return SlopeField(
        slope_deg=slope_from_gradient(grad.dz_dx, grad.dz_dy),
        aspect_deg=aspect_from_gradient(grad.dz_dx, grad.dz_dy, flat_gradient_tolerance),
        valid=grad.valid,
        dz_dx=grad.dz_dx,
        dz_dy=grad.dz_dy,
    )


def directional_grade_deg(
    dz_dx: FloatArray, dz_dy: FloatArray, heading_east: float, heading_north: float
) -> tuple[FloatArray, FloatArray]:
    """Longitudinal and cross-heading grade angles (deg) for a horizontal heading ``(east, north)``.

    ``grade_long = (a, b) . u`` and ``grade_cross = (a, b) . n`` with ``n`` the left-hand perpendicular.  A route
    that follows a contour has zero longitudinal grade on a steep hillside; the generic rover slope limit gates
    ``surface_slope_deg``, not these.
    """
    norm = math.hypot(heading_east, heading_north)
    if norm == 0.0 or not math.isfinite(norm):
        raise RasterError("heading must be a non-zero finite vector")
    ux, uy = heading_east / norm, heading_north / norm
    longitudinal = np.degrees(np.arctan(dz_dx * ux + dz_dy * uy))
    cross = np.degrees(np.arctan(dz_dx * (-uy) + dz_dy * ux))
    return np.asarray(longitudinal, dtype=np.float64), np.asarray(cross, dtype=np.float64)


@dataclass(frozen=True)
class SurfaceAnalysis:
    """Everything the ANALYSIS_GRID needs, computed over a whole raster."""

    usable: BoolArray  # finite, not nodata, not water
    valid: BoolArray  # usable with full 3x3 support
    land: BoolArray  # not water
    slope_deg: FloatArray  # NaN where invalid
    aspect_deg: FloatArray  # NaN where invalid or flat
    quality: UInt8Array


def analyze_surface(
    elevation: FloatArray,
    geometry: PixelGeometry,
    *,
    nodata: BoolArray | None = None,
    water: BoolArray | None = None,
    outside_source: BoolArray | None = None,
    flat_gradient_tolerance: float = DEFAULT_FLAT_GRADIENT_TOLERANCE,
) -> SurfaceAnalysis:
    """Slope/aspect/validity/quality of a raster.

    ``nodata`` marks missing cells (non-finite elevations are added automatically); ``water`` marks water.  Derivatives
    are computed over the *whole* raster, so a later crop to a window keeps a real halo.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    missing: BoolArray = ~np.isfinite(elev)
    if nodata is not None:
        if nodata.shape != elev.shape:
            raise RasterError("nodata mask shape mismatch")
        missing = missing | nodata
    wet: BoolArray = np.zeros(elev.shape, dtype=bool) if water is None else water
    if wet.shape != elev.shape:
        raise RasterError("water mask shape mismatch")
    usable = ~missing & ~wet
    field = compute_slope_aspect(np.where(missing, 0.0, elev), usable, geometry, flat_gradient_tolerance)
    quality = classify_cells(missing, wet, field.valid, outside_source)
    return SurfaceAnalysis(
        usable=usable,
        valid=field.valid,
        land=~wet,
        slope_deg=field.slope_deg,
        aspect_deg=field.aspect_deg,
        quality=quality,
    )
