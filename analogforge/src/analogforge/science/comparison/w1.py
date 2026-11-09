"""Wasserstein-1 distance between slope distributions, in degrees.

Binned approximation (architecture 10 section 6): each bin's probability mass sits at its representative centre
``x_i``; with ``F_i`` the cumulative mass through bin ``i``::

    W1 = sum_{i=0}^{n-2} |F_target[i] - F_earth[i]| * (x[i+1] - x[i])

The result is in the unit of the centres (degrees) and is never a percent "Mars-likeness".  Both distributions
must use identical edges, units and support.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from analogforge.ports.science_payloads import Histogram
from analogforge.science.errors import RasterError, ScaleError
from analogforge.science.features.histogram import bin_centres

_SUM_TOLERANCE = 1e-9


def binned_w1(fraction_a: Sequence[float], fraction_b: Sequence[float], centres: Sequence[float]) -> float:
    """W1 of two binned distributions placed at ``centres`` (ascending)."""
    a = np.asarray(fraction_a, dtype=np.float64)
    b = np.asarray(fraction_b, dtype=np.float64)
    x = np.asarray(centres, dtype=np.float64)
    if not (a.shape == b.shape == x.shape) or a.ndim != 1 or a.size < 2:
        raise RasterError("fractions and centres must be 1-D arrays of one length >= 2")
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(np.isfinite(x))):
        raise RasterError("non-finite value in a W1 input")
    if np.any(a < 0) or np.any(b < 0):
        raise RasterError("fractions must be non-negative")
    if abs(float(a.sum()) - 1.0) > _SUM_TOLERANCE or abs(float(b.sum()) - 1.0) > _SUM_TOLERANCE:
        raise RasterError("each distribution must sum to 1 (a missing distribution is unknown, not zero)")
    if np.any(np.diff(x) <= 0):
        raise RasterError("centres must be strictly ascending")
    cdf_diff = np.abs(np.cumsum(a) - np.cumsum(b))[:-1]
    return float(np.sum(cdf_diff * np.diff(x)))


@dataclass(frozen=True)
class W1Result:
    w1_deg: float
    centres_deg: tuple[float, ...]
    support_scale_m: float


def w1_from_histograms(a: Histogram, b: Histogram, *, support_tolerance_m: float = 1e-9) -> W1Result:
    """W1 of two kit histograms at their common support.

    Raises :class:`ScaleError` when the supports differ (re-aggregate first; histograms cannot be re-binned to a
    different support) and :class:`RasterError` for mismatched edges/units or empty distributions.
    """
    if a.edges != b.edges:
        raise RasterError("histograms use different edges")
    if a.unit != b.unit:
        raise RasterError("histograms use different units")
    if abs(a.support_scale_m - b.support_scale_m) > support_tolerance_m:
        raise ScaleError(
            f"histograms are at different supports ({a.support_scale_m} m vs {b.support_scale_m} m); "
            "compare only at a common support"
        )
    if not (a.valid_area_m2 > 0 and b.valid_area_m2 > 0):
        raise RasterError("a histogram without valid area cannot be compared", code="INSUFFICIENT_VALID_DATA")
    centres = bin_centres(a.edges)
    return W1Result(binned_w1(a.area_fraction, b.area_fraction, centres), centres, a.support_scale_m)


def empirical_w1(
    values_a: Sequence[float], weights_a: Sequence[float], values_b: Sequence[float], weights_b: Sequence[float]
) -> float:
    """Exact W1 of two weighted empirical distributions (integral of |F_a - F_b|); independent of binning."""
    xa, wa = np.asarray(values_a, dtype=np.float64), np.asarray(weights_a, dtype=np.float64)
    xb, wb = np.asarray(values_b, dtype=np.float64), np.asarray(weights_b, dtype=np.float64)
    if xa.shape != wa.shape or xb.shape != wb.shape or xa.size == 0 or xb.size == 0:
        raise RasterError("empirical W1 needs non-empty values and matching weights")
    if np.any(wa < 0) or np.any(wb < 0) or not (wa.sum() > 0 and wb.sum() > 0):
        raise RasterError("weights must be non-negative with a positive sum")
    points = np.unique(np.concatenate([xa, xb]))
    if points.size < 2:
        return 0.0
    cdf_a = np.array([wa[xa <= p].sum() for p in points[:-1]]) / wa.sum()
    cdf_b = np.array([wb[xb <= p].sum() for p in points[:-1]]) / wb.sum()
    w1 = float(np.sum(np.abs(cdf_a - cdf_b) * np.diff(points)))
    if not math.isfinite(w1):
        raise RasterError("non-finite W1")
    return w1
