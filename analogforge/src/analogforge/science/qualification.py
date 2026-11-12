"""Qualification decision primitives (architecture 11, 33): thresholds, intervals, confidence and coverage.

Pure functions; nothing here knows about a particular site, scenario or window.  Statuses are
``PASS | PARTIAL | FAIL | GAP | UNKNOWN`` with the exact meanings of architecture 11 section 3.  ``UNKNOWN`` is never
turned into ``0``/``False``; thresholds are inclusive unless a rule says otherwise.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final, Literal

from analogforge.ports.common import Confidence, QualificationStatus
from analogforge.science.errors import ScienceError

ReasonCode = Literal[
    "MEETS_CRITERION",
    "INSUFFICIENT_EXPOSURE",
    "SCALE_UNSUPPORTED",
    "TARGET_EVIDENCE_MISSING",
    "EARTH_EVIDENCE_MISSING",
    "TEMPORAL_MISMATCH",
    "PHYSICAL_GAP",
    "THRESHOLD_UNRESOLVED",
    "ROUTE_NOT_VERIFIED",
    "ROUTE_VERIFIED",
    "ROUTE_FAILED",
    "CAPABILITY_DECLARED",
    "PROXY_NOT_ACCEPTED",
    "REQUIREMENT_UNDERSPECIFIED",
    "INSUFFICIENT_VALID_DATA",
    "METADATA_INCOMPLETE",
    "DISTRIBUTION_MISMATCH",
    "ENERGY_MODEL_MISSING",
]
Operator = Literal["BETWEEN", "GTE", "LTE", "EQUALS", "PRESENT", "NOT_NATURALLY_REPRODUCIBLE"]
GateOutcomeName = Literal["SATISFIED", "UNSATISFIED", "NOT_ASSESSED", "NOT_APPLICABLE"]
UncertaintyKind = Literal["quantified", "bounded_sensitivity", "not_quantified"]
DEFAULT_MEDIUM_CONFIDENCE_MIN_COVERAGE: Final = 0.90


class RequirementUnderspecifiedError(ScienceError):
    """The requirement lacks a threshold/operator the policy needs (maps to ``REQUIREMENT_UNDERSPECIFIED``)."""

    code = "INPUT_INVALID"


@dataclass(frozen=True)
class ThresholdVerdict:
    """Outcome of comparing a measured value with a requirement threshold."""

    meets: bool
    shortfall: Literal["BELOW_LOWER", "ABOVE_UPPER", "NOT_EQUAL"] | None


def evaluate_threshold(
    value: float, operator: Operator, lower: float | None, upper: float | None, tolerance: float = 0.0
) -> ThresholdVerdict:
    """Inclusive threshold test: ``GTE value >= lower``, ``LTE value <= upper``, ``BETWEEN lower <= value <= upper``.

    ``tolerance`` absorbs floating-point noise only (policy-defined, tiny).  Raises
    :class:`RequirementUnderspecifiedError` when the operator needs a bound the requirement does not give.
    """
    if not math.isfinite(value):
        raise ScienceError("measured value must be finite; unknown values must stay None", code="INPUT_INVALID")
    if tolerance < 0:
        raise ScienceError("tolerance must be >= 0", code="INPUT_INVALID")
    if operator == "GTE":
        if lower is None:
            raise RequirementUnderspecifiedError("GTE needs a lower bound")
        return ThresholdVerdict(value >= lower - tolerance, None if value >= lower - tolerance else "BELOW_LOWER")
    if operator == "LTE":
        if upper is None:
            raise RequirementUnderspecifiedError("LTE needs an upper bound")
        return ThresholdVerdict(value <= upper + tolerance, None if value <= upper + tolerance else "ABOVE_UPPER")
    if operator == "BETWEEN":
        if lower is None or upper is None:
            raise RequirementUnderspecifiedError("BETWEEN needs both bounds")
        if value < lower - tolerance:
            return ThresholdVerdict(False, "BELOW_LOWER")
        if value > upper + tolerance:
            return ThresholdVerdict(False, "ABOVE_UPPER")
        return ThresholdVerdict(True, None)
    if operator == "EQUALS":
        if lower is None:
            raise RequirementUnderspecifiedError("EQUALS needs a target value in 'lower'")
        ok = abs(value - lower) <= tolerance
        return ThresholdVerdict(ok, None if ok else "NOT_EQUAL")
    raise RequirementUnderspecifiedError(f"operator {operator} has no numeric threshold rule")


def interval_decision(
    operator: Operator,
    lower: float | None,
    upper: float | None,
    interval_low: float,
    interval_high: float,
) -> Literal["PASS", "FAIL", "UNKNOWN"]:
    """Conservative decision for a *defensible* evidence interval ``[L, U]`` (architecture 11 section 4).

    ``x >= T``: PASS if ``L >= T``, FAIL if ``U < T``, else UNKNOWN.  ``x <= T``: PASS if ``U <= T``, FAIL if
    ``L > T``, else UNKNOWN.  Range ``[A, B]``: PASS if the interval lies inside, FAIL if disjoint, else UNKNOWN.
    No interval may be fabricated; without an uncertainty model use :func:`evaluate_threshold` on the nominal value.
    """
    if not (math.isfinite(interval_low) and math.isfinite(interval_high)) or interval_low > interval_high:
        raise ScienceError("evidence interval must be finite with low <= high", code="INPUT_INVALID")
    if operator == "GTE":
        if lower is None:
            raise RequirementUnderspecifiedError("GTE needs a lower bound")
        if interval_low >= lower:
            return "PASS"
        return "FAIL" if interval_high < lower else "UNKNOWN"
    if operator == "LTE":
        if upper is None:
            raise RequirementUnderspecifiedError("LTE needs an upper bound")
        if interval_high <= upper:
            return "PASS"
        return "FAIL" if interval_low > upper else "UNKNOWN"
    if operator == "BETWEEN":
        if lower is None or upper is None:
            raise RequirementUnderspecifiedError("BETWEEN needs both bounds")
        if interval_low >= lower and interval_high <= upper:
            return "PASS"
        return "FAIL" if (interval_high < lower or interval_low > upper) else "UNKNOWN"
    raise RequirementUnderspecifiedError(f"operator {operator} has no interval rule")


@dataclass(frozen=True)
class ConfidenceDimensions:
    """Structured confidence (architecture 11 section 5); the wire summary is :func:`confidence_label`."""

    source_quality: Literal["documented", "mixed", "unsupported"]
    scale_match: Literal["direct", "permitted_proxy", "incompatible"]
    coverage: Literal["sufficient", "partial", "missing"]
    temporal_match: Literal["applicable", "limited", "incompatible", "not_applicable"]
    uncertainty: UncertaintyKind
    independence: Literal["independent", "shared_source", "not_assessed"]
    limitations: tuple[str, ...] = field(default_factory=tuple)


def confidence_label(
    *,
    adequate: bool,
    direct_evidence: bool,
    coverage: float | None,
    uncertainty: UncertaintyKind,
    assumed_parameters: bool = False,
    medium_min_coverage: float = DEFAULT_MEDIUM_CONFIDENCE_MIN_COVERAGE,
) -> Confidence:
    """Wire confidence label.  Never ``UNASSESSED`` (the rubric has been evaluated) and never ``HIGH`` unless the
    uncertainty is quantified and the evidence is direct, fully adequate and free of assumed parameters.

    ``MEDIUM``: direct terrain-model evidence, coverage >= ``medium_min_coverage``, nominal (unquantified but
    accepted) uncertainty, no assumed model parameters.  Everything else is ``LOW``.
    """
    strong = adequate and direct_evidence and coverage is not None and coverage >= medium_min_coverage
    if strong and uncertainty == "quantified" and not assumed_parameters:
        return "HIGH"
    if strong and not assumed_parameters:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class StrictCoverage:
    """``sum(weight * [PASS]) / sum(weight of reproducible requirements)`` with visible denominators."""

    passed_weight: float
    reproducible_weight: float
    gap_weight: float
    value: float | None  # None when there is no reproducible requirement


def strict_coverage(rows: Iterable[tuple[QualificationStatus, float]]) -> StrictCoverage:
    """Requirement coverage (11 section 6).  ``UNKNOWN`` and ``FAIL`` stay in the denominator; ``GAP`` is excluded
    from it but reported separately.  This is coverage of requirements, never percent resemblance to a world."""
    passed = reproducible = gap = 0.0
    for status, weight in rows:
        if not (math.isfinite(weight) and weight > 0):
            raise ScienceError("requirement weights must be positive and finite", code="INPUT_INVALID")
        if status == "GAP":
            gap += weight
            continue
        reproducible += weight
        if status == "PASS":
            passed += weight
    value = None if reproducible == 0.0 else passed / reproducible
    return StrictCoverage(passed, reproducible, gap, value)
