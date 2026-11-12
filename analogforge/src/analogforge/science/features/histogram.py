"""Area-weighted slope histograms, band fractions and quantiles.

Bands are ``[lo, hi)``; ``[lo, hi]`` only when the caller states ``upper_inclusive`` (the final capped band).  The
default histogram edges are ``[0, 2, 5, 8, 12, 15, 18, 25, 35, 90]`` degrees (architecture 10 section 6) and the
last bin is closed so a (theoretical) 90 degree slope is not dropped.  All weights are physical cell areas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from analogforge.ports.science_payloads import Histogram
from analogforge.science.errors import RasterError

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

SLOPE_HIST_EDGES: Final[tuple[float, ...]] = (0.0, 2.0, 5.0, 8.0, 12.0, 15.0, 18.0, 25.0, 35.0, 90.0)
# Representative bin centres of architecture 10 section 6 / guide 08 section 3 (midpoints of SLOPE_HIST_EDGES).
SLOPE_HIST_CENTRES: Final[tuple[float, ...]] = (1.0, 3.5, 6.5, 10.0, 13.5, 16.5, 21.5, 30.0, 62.5)


def bin_centres(edges: tuple[float, ...] | list[float]) -> tuple[float, ...]:
    """Midpoint of each bin."""
    return tuple(0.5 * (a + b) for a, b in zip(edges, edges[1:], strict=False))


@dataclass(frozen=True)
class HistogramData:
    """Area per bin (m^2) over the valid cells."""

    edges: tuple[float, ...]
    area_m2: tuple[float, ...]

    @property
    def valid_area_m2(self) -> float:
        return float(sum(self.area_m2))

    @property
    def area_fraction(self) -> tuple[float, ...]:
        """Fractions summing to 1 (all zero when there is no valid area; the caller must treat that as unknown)."""
        total = self.valid_area_m2
        if total <= 0.0:
            return tuple(0.0 for _ in self.area_m2)
        return tuple(a / total for a in self.area_m2)


def _weights(valid: BoolArray, cell_area_m2: float | FloatArray) -> FloatArray:
    if isinstance(cell_area_m2, np.ndarray):
        if cell_area_m2.shape != valid.shape:
            raise RasterError("cell area raster shape mismatch")
        return np.asarray(cell_area_m2[valid], dtype=np.float64)
    if not cell_area_m2 > 0.0:
        raise RasterError("cell area must be positive")
    return np.full(int(valid.sum()), float(cell_area_m2))


def _valid_values(values: FloatArray, valid: BoolArray) -> FloatArray:
    if values.shape != valid.shape:
        raise RasterError("values and valid mask shapes differ")
    chosen = np.asarray(values[valid], dtype=np.float64)
    if not np.all(np.isfinite(chosen)):
        raise RasterError("valid cells hold non-finite values")
    return chosen


def area_weighted_histogram(
    values: FloatArray,
    valid: BoolArray,
    cell_area_m2: float | FloatArray,
    edges: tuple[float, ...] = SLOPE_HIST_EDGES,
    *,
    last_bin_inclusive: bool = True,
) -> HistogramData:
    """Histogram of ``values`` over ``valid`` cells with physical-area weights."""
    if len(edges) < 2 or any(b <= a for a, b in zip(edges, edges[1:], strict=False)):
        raise RasterError("histogram edges must be strictly ascending with at least two values")
    chosen = _valid_values(values, valid)
    weights = _weights(valid, cell_area_m2)
    n_bins = len(edges) - 1
    idx = np.searchsorted(np.asarray(edges), chosen, side="right") - 1
    if last_bin_inclusive:
        idx = np.where(chosen == edges[-1], n_bins - 1, idx)
    if np.any(idx < 0) or np.any(idx >= n_bins):
        raise RasterError("values fall outside the histogram range")
    area = np.bincount(idx, weights=weights, minlength=n_bins)
    return HistogramData(edges=tuple(float(e) for e in edges), area_m2=tuple(float(a) for a in area))


def band_label(lo: float, hi: float) -> str:
    """``12-18`` style label used inside metric ids."""
    return f"{lo:g}-{hi:g}"


def slope_area_metric_id(lo: float, hi: float) -> str:
    """``slope_area_fraction:<lo>-<hi>``."""
    return f"slope_area_fraction:{band_label(lo, hi)}"


def band_area_fraction(
    values: FloatArray,
    valid: BoolArray,
    lo: float,
    hi: float,
    cell_area_m2: float | FloatArray,
    *,
    upper_inclusive: bool = False,
) -> float | None:
    """Valid-area fraction with ``lo <= value < hi`` (``<= hi`` if ``upper_inclusive``); ``None`` if no area."""
    if not hi > lo:
        raise RasterError("band needs hi > lo")
    chosen = _valid_values(values, valid)
    weights = _weights(valid, cell_area_m2)
    total = float(weights.sum())
    if total <= 0.0:
        return None
    upper = chosen <= hi if upper_inclusive else chosen < hi
    in_band = (chosen >= lo) & upper
    return float(weights[in_band].sum()) / total


def weighted_quantile(values: FloatArray, weights: FloatArray, q: float) -> float | None:
    """Inverse empirical CDF: smallest value whose cumulative weight fraction is >= ``q`` (``None`` if empty)."""
    if not 0.0 <= q <= 1.0:
        raise RasterError("quantile must be in [0, 1]")
    if values.size == 0:
        return None
    order = np.argsort(values, kind="stable")
    cum = np.cumsum(weights[order])
    total = cum[-1]
    if not total > 0.0:
        return None
    idx = int(np.searchsorted(cum, q * total - 1e-12 * total, side="left"))
    return float(values[order][min(idx, values.size - 1)])


def slope_statistics(values: FloatArray, valid: BoolArray, cell_area_m2: float | FloatArray) -> dict[str, float | None]:
    """Area-weighted ``p05, p50, p95, mean, max`` (``None`` for every key when there is no valid cell)."""
    chosen = _valid_values(values, valid)
    weights = _weights(valid, cell_area_m2)
    if chosen.size == 0:
        return {"p05": None, "p50": None, "p95": None, "mean": None, "max": None}
    return {
        "p05": weighted_quantile(chosen, weights, 0.05),
        "p50": weighted_quantile(chosen, weights, 0.50),
        "p95": weighted_quantile(chosen, weights, 0.95),
        "mean": float(np.average(chosen, weights=weights)),
        "max": float(chosen.max()),
    }


def to_port_histogram(
    data: HistogramData, *, support_scale_m: float, metric_id: str = "surface_slope_deg", unit: str = "deg"
) -> Histogram:
    """Kit :class:`Histogram` for payloads (fractions renormalised to sum to exactly 1 within 1e-9)."""
    fractions = list(data.area_fraction)
    return Histogram(
        metric_id=metric_id,
        unit=unit,
        edges=list(data.edges),
        area_fraction=fractions,
        valid_area_m2=data.valid_area_m2,
        support_scale_m=support_scale_m,
    )
