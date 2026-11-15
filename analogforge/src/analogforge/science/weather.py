"""Earth task-window weather checks with explicit limits, no similarity weighting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from analogforge.adapters.meteomatics import WeatherContext
from analogforge.adapters.meteomatics.adapter import PARAMETERS


@dataclass(frozen=True)
class WeatherLimit:
    parameter: str
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if self.parameter not in PARAMETERS or (self.lower is None and self.upper is None):
            raise ValueError("A weather limit needs a supported parameter and explicit bound")
        if any(v is not None and not math.isfinite(v) for v in (self.lower, self.upper)):
            raise ValueError("Weather limits must be finite")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("Weather limit lower bound exceeds upper bound")


def compare_operating_weather(context: WeatherContext, limits: tuple[WeatherLimit, ...]) -> dict[str, Any]:
    """Compare every requested sample against inclusive, caller-provided Earth limits.

    A limit violation is established by an available sample. Meeting all limits
    requires a complete requested series for each limited parameter. This result
    is a forecast/historical context check, not physical safety certification.
    """
    rows = []
    expected = set(context.query.expected_dates())
    for limit in limits:
        samples = [s for s in context.samples if s["parameter"] == limit.parameter and s["value"] is not None]
        samples = [s for s in samples if s["valid_at"] in expected]
        violations = [s for s in samples if (limit.lower is not None and s["value"] < limit.lower)
                      or (limit.upper is not None and s["value"] > limit.upper)]
        usable = context.query.body == "EARTH" and context.status in {"AVAILABLE", "LIMITED"}
        complete = {s["valid_at"] for s in samples} == expected
        status = "UNKNOWN"
        if usable and violations:
            status = "OUTSIDE_LIMITS"
        elif usable and complete:
            status = "WITHIN_LIMITS"
        rows.append({"parameter": limit.parameter, "unit": PARAMETERS[limit.parameter][1],
                     "lower": limit.lower, "upper": limit.upper, "status": status,
                     "valid_sample_count": len(samples), "expected_sample_count": len(expected),
                     "violating_samples": violations})
    overall = "UNKNOWN"
    if any(r["status"] == "OUTSIDE_LIMITS" for r in rows):
        overall = "OUTSIDE_LIMITS"
    elif rows and all(r["status"] == "WITHIN_LIMITS" for r in rows):
        overall = "WITHIN_LIMITS"
    return {"status": overall, "scope": "earth_operating_weather_context", "rows": rows,
            "qualification_supported": False, "cross_planet_equivalence": "UNKNOWN",
            "limitations": list(context.limitations)}
