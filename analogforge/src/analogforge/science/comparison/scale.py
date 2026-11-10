"""Support-scale rules: the common comparison support, aggregation factors and requirement-window checks.

Coarsening is by *area averaging* only; a coarser source stays coarse (``upsampled`` is always False and a
fine-scale requirement against a coarse source is ``SCALE_UNSUPPORTED``, never a pass).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from analogforge.science.config import default_thresholds
from analogforge.science.errors import ScaleError

_FACTOR_TOLERANCE = 1e-6


@dataclass(frozen=True)
class SupportPlan:
    """How a raster of native support ``native_m`` reaches the comparison support ``effective_m``."""

    native_m: float
    effective_m: float
    factor: int
    upsampled: bool = False


def common_support_m(*native_supports_m: float, requested_m: float | None = None) -> float:
    """``max(native supports, requested)``: the finest support at which every source can honestly be compared."""
    values = [v for v in native_supports_m if v is not None]
    if requested_m is not None:
        values.append(requested_m)
    if not values:
        raise ScaleError("at least one support scale is required")
    if any(not (math.isfinite(v) and v > 0) for v in values):
        raise ScaleError("support scales must be positive and finite")
    return max(values)


def aggregation_factor(native_m: float, effective_m: float) -> int:
    """Integer block factor from ``native_m`` to ``effective_m`` (``effective_m`` must be a whole multiple)."""
    if not (native_m > 0 and effective_m > 0):
        raise ScaleError("support scales must be positive")
    if effective_m < native_m * (1.0 - _FACTOR_TOLERANCE):
        raise ScaleError(
            f"requested support {effective_m} m is finer than native {native_m} m; upsampling is not allowed"
        )
    ratio = effective_m / native_m
    factor = round(ratio)
    if factor < 1 or abs(ratio - factor) > _FACTOR_TOLERANCE * max(1.0, ratio):
        raise ScaleError(f"support {effective_m} m is not an integer multiple of the native {native_m} m")
    return int(factor)


def plan_support(native_m: float, requested_m: float | None) -> SupportPlan:
    """Plan area-average aggregation to ``max(native, requested)``."""
    effective = common_support_m(native_m, requested_m=requested_m)
    return SupportPlan(native_m=native_m, effective_m=effective, factor=aggregation_factor(native_m, effective))


SupportReason = Literal["BELOW_MINIMUM", "ABOVE_MAXIMUM"]


@dataclass(frozen=True)
class SupportVerdict:
    """Result of checking an evidence support against a requirement's ``[minimum, maximum]`` window."""

    supported: bool
    reason: SupportReason | None


def check_support_window(
    support_m: float, minimum_m: float | None, maximum_m: float | None, tolerance: float | None = None
) -> SupportVerdict:
    """Is ``support_m`` inside ``[minimum_m, maximum_m]`` (``None`` bound = unbounded; bounds inclusive)?

    ``tolerance`` defaults to ``thresholds.numeric_tolerance`` of ``config/algorithms.yaml``.
    """
    if tolerance is None:
        tolerance = default_thresholds().numeric_tolerance
    if not (math.isfinite(support_m) and support_m >= 0):
        raise ScaleError("support scale must be finite and non-negative")
    if minimum_m is not None and support_m < minimum_m - tolerance:
        return SupportVerdict(False, "BELOW_MINIMUM")
    if maximum_m is not None and support_m > maximum_m + tolerance:
        return SupportVerdict(False, "ABOVE_MAXIMUM")
    return SupportVerdict(True, None)
