"""Observable policies for ``COMPARE_REQUIREMENT`` (guide 08 section 4.7).

Each policy is a pure function ``PolicyContext -> PolicyDecision``.  A decision carries the verdict *and* the facts
the adequacy gates need (units/body/scale/coverage outcomes).  Nothing here depends on a window id, scenario or
fixture: every outcome follows from the evidence, the requirement and the versioned policy in ``algorithms.yaml``.

Evidence handling:

* a metric whose ``value`` is ``None`` is *unknown* and is never read as zero;
* evidence from another mode than the request's is rejected (``METADATA_INCOMPLETE``);
* a requirement support window that excludes the available support yields ``UNKNOWN / SCALE_UNSUPPORTED``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import Histogram, VerificationSummary
from analogforge.science.comparison.scale import check_support_window
from analogforge.science.comparison.w1 import w1_from_histograms
from analogforge.science.config import ObservablePolicy
from analogforge.science.errors import RasterError, ScaleError
from analogforge.science.features.histogram import slope_area_metric_id
from analogforge.science.qualification import ReasonCode, ThresholdVerdict, evaluate_threshold

Status = Literal["PASS", "PARTIAL", "FAIL", "GAP", "UNKNOWN"]
Stage = Literal["PRELIMINARY", "FINAL"]

ROUTE_ALGORITHM_IDS = frozenset({"verify-route", "search-route", "diagnose-result"})
ANALYSIS_ALGORITHM_IDS = frozenset({"analyze-candidate", "analysis-summary"})
_EXPOSURE_VIOLATIONS = frozenset({"EXPOSURE_SHORTFALL"})
_TASK_VIOLATIONS = frozenset({"WAYPOINT_MISSED", "TASK_CAPABILITY_MISSING", "RETURN_NOT_COMPLETED"})
_RESERVE_VIOLATIONS = frozenset({"ENERGY_RESERVE_SHORTFALL"})
NOMINAL_LIMITATION = "Uncertainty not quantified; nominal modeled result."


@dataclass(frozen=True)
class SideEvidence:
    """Evidence handles of one side (target or candidate) plus the parsed histogram read from their artifacts."""

    handles: tuple[EvidenceHandle, ...] = ()
    histogram: Histogram | None = None

    def metric(self, metric_id: str) -> MeasuredMetric | None:
        """First metric with this id (handles are searched in order); its ``value`` may still be ``None``."""
        for handle in self.handles:
            for metric in handle.metrics:
                if metric.metric_id == metric_id:
                    return metric
        return None

    def has_value(self, metric_id: str) -> bool:
        metric = self.metric(metric_id)
        return metric is not None and metric.value is not None

    def has_metric_prefix(self, prefix: str) -> bool:
        return any(m.metric_id.startswith(prefix) and m.value is not None for h in self.handles for m in h.metrics)

    def scales(self) -> list[float]:
        """All comparison scales stated by the handles and their metrics."""
        out = [h.comparison_scale_m for h in self.handles if h.comparison_scale_m is not None]
        out += [m.support_scale_m for h in self.handles for m in h.metrics if m.support_scale_m is not None]
        return out


@dataclass(frozen=True)
class PolicyContext:
    requirement: Requirement
    policy_id: str
    policy: ObservablePolicy
    mode: RuntimeMode
    candidate: SideEvidence
    target: SideEvidence
    verification: VerificationSummary | None


@dataclass(frozen=True)
class PolicyDecision:
    """Verdict plus the facts behind the adequacy gates (``None`` = could not be assessed)."""

    status: Status
    reason: ReasonCode
    stage: Stage
    explanation: str
    measured_value: float | None = None
    measured_unit: str | None = None
    comparison_scale_m: float | None = None
    coverage: float | None = None
    covered: tuple[str, ...] = ()
    uncovered: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    metrics: tuple[MeasuredMetric, ...] = ()
    consulted: tuple[EvidenceHandle, ...] = ()
    units_ok: bool | None = None
    body_ok: bool | None = None
    scale_ok: bool | None = None
    coverage_ok: bool | None = None
    numeric_decided: bool = False
    direct_evidence: bool = False
    assumed_parameters: bool = False
    route_check: Literal["INDEPENDENT", "ABSENT", "NOT_ROUTE"] = "NOT_ROUTE"
    extra: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- shared checks
def _all_handles(ctx: PolicyContext) -> tuple[EvidenceHandle, ...]:
    return ctx.candidate.handles + ctx.target.handles


def underspecified(ctx: PolicyContext, why: str) -> PolicyDecision:
    return PolicyDecision(
        status="UNKNOWN",
        reason="REQUIREMENT_UNDERSPECIFIED",
        stage="FINAL",
        explanation=f"Requirement {ctx.requirement.id} cannot be evaluated: {why}.",
        uncovered=(ctx.requirement.id,),
        consulted=_all_handles(ctx),
    )


def metadata_problem(ctx: PolicyContext) -> PolicyDecision | None:
    """Units, body and mode consistency; returns an ``UNKNOWN / METADATA_INCOMPLETE`` decision on a mismatch."""
    req, policy = ctx.requirement, ctx.policy
    handles = _all_handles(ctx)
    if policy.units != "*" and req.unit != policy.units:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation=f"Requirement unit '{req.unit}' does not match the policy unit '{policy.units}'.",
            uncovered=(req.id,),
            consulted=handles,
            units_ok=False,
        )
    wrong_mode = sorted({h.mode for h in handles if h.mode != ctx.mode})
    if wrong_mode:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation=f"Evidence recorded in mode {wrong_mode} cannot support a {ctx.mode} comparison.",
            uncovered=(req.id,),
            consulted=handles,
            units_ok=True,
        )
    bad_bodies = sorted(
        {h.body for h in handles if h.body not in policy.valid_bodies}
        | {h.body for h in ctx.candidate.handles if h.body != "EARTH"}
    )
    if bad_bodies:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation=f"Evidence body {bad_bodies} is not valid for {ctx.policy_id} (candidates must be EARTH).",
            uncovered=(req.id,),
            consulted=handles,
            units_ok=True,
            body_ok=False,
        )
    return None


def _terrain_limitation(scale: float | None) -> str:
    if scale is None:
        return "Terrain-model evidence; support scale not stated."
    return f"Terrain model at {scale:g} m support; cannot resolve 0.20 m obstacles."


def _bodies_ok(handles: tuple[EvidenceHandle, ...]) -> bool | None:
    return True if handles else None


# --------------------------------------------------------------------------- terrain policies
def _band(ctx: PolicyContext) -> tuple[float, float] | None:
    band = ctx.requirement.parameters.slope_band_deg
    if band is None or len(band) != 2 or not band[1] > band[0]:
        return None
    return float(band[0]), float(band[1])


def slope_band_area_fraction(ctx: PolicyContext) -> PolicyDecision:
    """``slope_area_fraction:<band>`` of the candidate evidence: PASS iff ``>= lower`` (inclusive)."""
    req = ctx.requirement
    band = _band(ctx)
    if band is None:
        return underspecified(ctx, "the slope band (parameters.slope_band_deg) is missing or malformed")
    if req.operator != "GTE" or req.lower is None:
        return underspecified(ctx, "slope-band-area-fraction-v1 needs operator GTE with a lower threshold")
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    metric_id = slope_area_metric_id(*band)
    metric = ctx.candidate.metric(metric_id)
    if metric is None or metric.value is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="EARTH_EVIDENCE_MISSING",
            stage="FINAL",
            explanation=f"No candidate evidence provides {metric_id}.",
            uncovered=(f"slope_band:{band[0]:g}-{band[1]:g}",),
            consulted=ctx.candidate.handles,
            units_ok=True,
            body_ok=_bodies_ok(ctx.candidate.handles),
        )
    scale = metric.support_scale_m
    if scale is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation=f"{metric_id} does not state its support scale.",
            uncovered=(metric_id,),
            consulted=ctx.candidate.handles,
            units_ok=True,
            body_ok=True,
        )
    verdict_scale = check_support_window(scale, req.minimum_support_scale_m, req.maximum_support_scale_m)
    if not verdict_scale.supported:
        return PolicyDecision(
            status="UNKNOWN",
            reason="SCALE_UNSUPPORTED",
            stage="FINAL",
            explanation=(
                f"Evidence support {scale:g} m lies outside the requirement window "
                f"[{req.minimum_support_scale_m}, {req.maximum_support_scale_m}] m."
            ),
            comparison_scale_m=scale,
            uncovered=(metric_id,),
            consulted=ctx.candidate.handles,
            units_ok=True,
            body_ok=True,
            scale_ok=False,
        )
    coverage = metric.valid_fraction
    if coverage < ctx.policy.min_valid_fraction:
        return PolicyDecision(
            status="UNKNOWN",
            reason="INSUFFICIENT_VALID_DATA",
            stage="FINAL",
            explanation=(
                f"Valid coverage {coverage:.3f} is below the policy minimum {ctx.policy.min_valid_fraction:.2f}."
            ),
            comparison_scale_m=scale,
            coverage=coverage,
            uncovered=(metric_id,),
            consulted=ctx.candidate.handles,
            limitations=(_terrain_limitation(scale),),
            units_ok=True,
            body_ok=True,
            scale_ok=True,
            coverage_ok=False,
        )
    verdict = evaluate_threshold(metric.value, "GTE", req.lower, None, ctx.policy.tolerance)
    return _numeric_terrain(ctx, verdict, metric.value, scale, coverage, metric_id, req.unit, "INSUFFICIENT_EXPOSURE")


def _numeric_terrain(
    ctx: PolicyContext,
    verdict: ThresholdVerdict,
    value: float,
    scale: float,
    coverage: float,
    subcriterion: str,
    unit: str,
    fail_reason: ReasonCode,
    metrics: tuple[MeasuredMetric, ...] = (),
) -> PolicyDecision:
    req = ctx.requirement
    bound = f">= {req.lower:g}" if req.operator == "GTE" else f"<= {req.upper:g}" if req.upper is not None else "?"
    return PolicyDecision(
        status="PASS" if verdict.meets else "FAIL",
        reason="MEETS_CRITERION" if verdict.meets else fail_reason,
        stage="FINAL",
        explanation=(
            f"Measured {subcriterion} = {value:.6g} {unit} at {scale:g} m support "
            f"{'meets' if verdict.meets else 'does not meet'} the criterion {bound} (inclusive)."
        ),
        measured_value=value,
        measured_unit=unit,
        comparison_scale_m=scale,
        coverage=coverage,
        covered=(subcriterion,) if verdict.meets else (),
        uncovered=() if verdict.meets else (subcriterion,),
        limitations=(_terrain_limitation(scale), NOMINAL_LIMITATION),
        metrics=metrics,
        consulted=ctx.candidate.handles + ctx.target.handles,
        units_ok=True,
        body_ok=True,
        scale_ok=True,
        coverage_ok=True,
        numeric_decided=True,
        direct_evidence=True,
    )


def slope_w1_common_support(ctx: PolicyContext) -> PolicyDecision:
    """Recompute the binned W1 distance at the common support; PASS iff ``<= upper``."""
    req = ctx.requirement
    if req.operator != "LTE" or req.upper is None:
        return underspecified(ctx, "slope-w1-common-support-v1 needs operator LTE with an upper threshold")
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    target_h, cand_h = ctx.target.histogram, ctx.candidate.histogram
    if target_h is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="TARGET_EVIDENCE_MISSING",
            stage="FINAL",
            explanation="No target slope distribution is available for the comparison.",
            uncovered=("target_slope_histogram",),
            consulted=ctx.candidate.handles + ctx.target.handles,
            units_ok=True,
            body_ok=_bodies_ok(ctx.target.handles),
        )
    if cand_h is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="EARTH_EVIDENCE_MISSING",
            stage="FINAL",
            explanation="No candidate slope distribution is available for the comparison.",
            uncovered=("candidate_slope_histogram",),
            consulted=ctx.candidate.handles + ctx.target.handles,
            units_ok=True,
            body_ok=_bodies_ok(ctx.candidate.handles),
        )
    scale = cand_h.support_scale_m
    in_window = check_support_window(scale, req.minimum_support_scale_m, req.maximum_support_scale_m)
    consulted = ctx.candidate.handles + ctx.target.handles
    if not in_window.supported or abs(scale - target_h.support_scale_m) > 1e-9:
        return PolicyDecision(
            status="UNKNOWN",
            reason="SCALE_UNSUPPORTED",
            stage="FINAL",
            explanation=(
                f"Candidate distribution support {scale:g} m and target support {target_h.support_scale_m:g} m "
                f"must be equal and inside [{req.minimum_support_scale_m}, {req.maximum_support_scale_m}] m."
            ),
            comparison_scale_m=scale,
            uncovered=("slope_distribution_w1",),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
            scale_ok=False,
        )
    coverage_metric = ctx.candidate.metric("valid_fraction")
    if coverage_metric is None or coverage_metric.value is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation="The candidate evidence does not state its valid fraction.",
            comparison_scale_m=scale,
            uncovered=("candidate_valid_fraction",),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
            scale_ok=True,
        )
    coverage = coverage_metric.value
    if coverage < ctx.policy.min_valid_fraction or cand_h.valid_area_m2 <= 0 or target_h.valid_area_m2 <= 0:
        return PolicyDecision(
            status="UNKNOWN",
            reason="INSUFFICIENT_VALID_DATA",
            stage="FINAL",
            explanation=(
                f"Valid coverage {coverage:.3f} is below the policy minimum {ctx.policy.min_valid_fraction:.2f}."
            ),
            comparison_scale_m=scale,
            coverage=coverage,
            uncovered=("slope_distribution_w1",),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
            scale_ok=True,
            coverage_ok=False,
        )
    try:
        result = w1_from_histograms(target_h, cand_h)
    except (RasterError, ScaleError) as exc:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation=f"The distributions cannot be compared: {exc.message}.",
            comparison_scale_m=scale,
            uncovered=("slope_distribution_w1",),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
            scale_ok=True,
            coverage_ok=True,
        )
    verdict = evaluate_threshold(result.w1_deg, "LTE", None, req.upper, ctx.policy.tolerance)
    metric = MeasuredMetric(
        metric_id="slope_w1_deg",
        value=result.w1_deg,
        unit="deg",
        support_scale_m=scale,
        quantity_kind="DERIVED",
        method_id="slope-w1-binned-v1",
        valid_fraction=min(1.0, max(0.0, coverage)),
        uncertainty_note="Binned W1 at the common support; uncertainty not quantified.",
    )
    decision = _numeric_terrain(
        ctx, verdict, result.w1_deg, scale, coverage, "slope_w1_deg", "deg", "DISTRIBUTION_MISMATCH", (metric,)
    )
    return decision


def mineral_presence(ctx: PolicyContext) -> PolicyDecision:
    """No accepted proxy rule exists: Earth absent, then target absent, else ``THRESHOLD_UNRESOLVED``."""
    req = ctx.requirement
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    consulted = ctx.candidate.handles + ctx.target.handles
    if not ctx.candidate.has_value("mineral_valid_fraction"):
        return PolicyDecision(
            status="UNKNOWN",
            reason="EARTH_EVIDENCE_MISSING",
            stage="FINAL",
            explanation=(
                "No Earth mineral evidence is bound for this candidate; "
                "absence of retrievals is not absence of mineral."
            ),
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
        )
    if not ctx.target.has_metric_prefix("mineral"):
        return PolicyDecision(
            status="UNKNOWN",
            reason="TARGET_EVIDENCE_MISSING",
            stage="FINAL",
            explanation="Earth mineral context exists but the planetary target has no supported mineral source.",
            uncovered=(req.id,),
            consulted=consulted,
            limitations=("Earth mineral evidence alone does not establish a planetary mineral match.",),
            units_ok=True,
            body_ok=True,
        )
    scales = ctx.candidate.scales()
    if scales and req.maximum_support_scale_m is not None and min(scales) > req.maximum_support_scale_m:
        return PolicyDecision(
            status="UNKNOWN",
            reason="SCALE_UNSUPPORTED",
            stage="FINAL",
            explanation=f"Mineral evidence support {min(scales):g} m exceeds the requirement window.",
            comparison_scale_m=min(scales),
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=True,
            scale_ok=False,
        )
    return PolicyDecision(
        status="UNKNOWN",
        reason="THRESHOLD_UNRESOLVED",
        stage="FINAL",
        explanation="Both mineral sources exist but no accepted cross-world proxy rule defines a match.",
        comparison_scale_m=min(scales) if scales else None,
        uncovered=(req.id,),
        consulted=consulted,
        limitations=("Categorical mineral classes are never interpolated; no accepted proxy rule exists.",),
        units_ok=True,
        body_ok=True,
        scale_ok=True if scales else None,
    )


def thermal_min(ctx: PolicyContext) -> PolicyDecision:
    """Earth thermal evidence never exists in v1; a target thermal metric alone never decides the row."""
    req = ctx.requirement
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    consulted = ctx.candidate.handles + ctx.target.handles
    target_note = (
        ("The target has a thermal metric, but a target value alone cannot qualify an Earth candidate.",)
        if ctx.target.has_value("min_temperature_k")
        else ()
    )
    if not ctx.candidate.has_value("min_temperature_k"):
        return PolicyDecision(
            status="UNKNOWN",
            reason="EARTH_EVIDENCE_MISSING",
            stage="FINAL",
            explanation="No compatible Earth thermal evidence exists; terrain data is not a thermal proxy.",
            uncovered=(req.id,),
            consulted=consulted,
            limitations=target_note,
            units_ok=True,
            body_ok=True,
        )
    return PolicyDecision(
        status="UNKNOWN",
        reason="THRESHOLD_UNRESOLVED",
        stage="FINAL",
        explanation="Earth thermal evidence is present but no accepted temporal/aggregation comparison rule exists.",
        uncovered=(req.id,),
        consulted=consulted,
        limitations=target_note,
        units_ok=True,
        body_ok=True,
    )


def clearance_scale(ctx: PolicyContext) -> PolicyDecision:
    """Terrain-model support coarser than the requirement window can never support clearance claims."""
    req = ctx.requirement
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    scales = ctx.candidate.scales()
    consulted = ctx.candidate.handles
    if req.maximum_support_scale_m is None:
        return underspecified(ctx, "a clearance requirement needs a maximum support scale")
    if not scales:
        return PolicyDecision(
            status="UNKNOWN",
            reason="EARTH_EVIDENCE_MISSING",
            stage="FINAL",
            explanation="No candidate evidence with a stated support scale exists for obstacle height.",
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=_bodies_ok(consulted),
        )
    finest = min(scales)
    if finest > req.maximum_support_scale_m:
        return PolicyDecision(
            status="UNKNOWN",
            reason="SCALE_UNSUPPORTED",
            stage="FINAL",
            explanation=(
                f"The finest available support {finest:g} m is coarser than the {req.maximum_support_scale_m:g} m "
                "needed; relief or roughness at that support is not obstacle height."
            ),
            comparison_scale_m=finest,
            uncovered=(req.id,),
            consulted=consulted,
            limitations=("Obstacle height needs field-scale survey evidence; terrain-model relief cannot stand in.",),
            units_ok=True,
            body_ok=True,
            scale_ok=False,
        )
    return PolicyDecision(
        status="UNKNOWN",
        reason="THRESHOLD_UNRESOLVED",
        stage="FINAL",
        explanation="Support is fine enough but v1 defines no obstacle-height comparison rule.",
        comparison_scale_m=finest,
        uncovered=(req.id,),
        consulted=consulted,
        units_ok=True,
        body_ok=True,
        scale_ok=True,
    )


def physical_gap(ctx: PolicyContext) -> PolicyDecision:
    """A planetary condition that natural Earth site selection cannot reproduce."""
    req = ctx.requirement
    if req.operator != "NOT_NATURALLY_REPRODUCIBLE":
        return underspecified(ctx, "physical-gap-v1 applies only to NOT_NATURALLY_REPRODUCIBLE requirements")
    return gap_decision(req)


def gap_decision(req: Requirement) -> PolicyDecision:
    return PolicyDecision(
        status="GAP",
        reason="PHYSICAL_GAP",
        stage="FINAL",
        explanation=(
            f"{req.label}: this condition cannot be reproduced by selecting a natural Earth site; "
            "it needs an engineered facility or simulation."
        ),
        uncovered=(req.id,),
        limitations=("Natural Earth sites cannot reproduce this planetary condition.",),
    )


# --------------------------------------------------------------------------- route-dependent policies
_ROUTE_KINDS: dict[str, tuple[str, frozenset[str]]] = {
    "route-exposure-v1": ("exposure", _EXPOSURE_VIOLATIONS),
    "route-tasks-v1": ("tasks", _TASK_VIOLATIONS),
    "route-reserve-v1": ("reserve", _RESERVE_VIOLATIONS),
}


def _route_metric_id(kind: str, requirement_id: str) -> str:
    return {"exposure": f"unique_exposure_m:{requirement_id}", "tasks": "tasks_completed", "reserve": "reserve_pct"}[
        kind
    ]


def _analysis_scale(ctx: PolicyContext) -> float | None:
    scales = [
        h.comparison_scale_m
        for h in ctx.candidate.handles
        if h.algorithm_id in ANALYSIS_ALGORITHM_IDS and h.comparison_scale_m is not None
    ]
    return max(scales) if scales else None


def route_dependent(ctx: PolicyContext) -> PolicyDecision:
    """Route rows: ``PRELIMINARY`` until a verification is supplied, then decided from the verifier's metrics."""
    req = ctx.requirement
    kind, violation_codes = _ROUTE_KINDS[ctx.policy_id]
    if req.operator != "GTE" or req.lower is None:
        return underspecified(ctx, f"{ctx.policy_id} needs operator GTE with a lower threshold")
    if (problem := metadata_problem(ctx)) is not None:
        return problem
    consulted = ctx.candidate.handles
    scale = _analysis_scale(ctx)
    if (
        scale is not None
        and not check_support_window(scale, req.minimum_support_scale_m, req.maximum_support_scale_m).supported
    ):
        return PolicyDecision(
            status="UNKNOWN",
            reason="SCALE_UNSUPPORTED",
            stage="FINAL" if ctx.verification is not None else "PRELIMINARY",
            explanation=f"Analysis support {scale:g} m lies outside the requirement window.",
            comparison_scale_m=scale,
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=_bodies_ok(consulted),
            scale_ok=False,
            route_check="ABSENT",
        )
    if ctx.verification is None:
        return PolicyDecision(
            status="UNKNOWN",
            reason="ROUTE_NOT_VERIFIED",
            stage="PRELIMINARY",
            explanation="Route-dependent: no independently verified route exists yet, so this row stays preliminary.",
            comparison_scale_m=scale,
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=_bodies_ok(consulted),
            scale_ok=True if scale is not None else None,
            route_check="ABSENT",
        )
    route_handles = tuple(h for h in consulted if h.algorithm_id in ROUTE_ALGORITHM_IDS)
    if not route_handles:
        return PolicyDecision(
            status="UNKNOWN",
            reason="METADATA_INCOMPLETE",
            stage="FINAL",
            explanation="A verification was supplied but its evidence handle is not among the candidate evidence.",
            comparison_scale_m=scale,
            uncovered=(req.id,),
            consulted=consulted,
            units_ok=True,
            body_ok=_bodies_ok(consulted),
            scale_ok=True if scale is not None else None,
            route_check="ABSENT",
        )
    v = ctx.verification
    metric = next((m for m in v.metrics if m.metric_id == _route_metric_id(kind, req.id)), None)
    named_violation = any(code in violation_codes for code in v.violation_codes)
    infeasible = v.outcome == "FAIL" and v.failure_category in ("ANALOG", "ROVER")
    independent = any(h.kind == "VERIFICATION" for h in route_handles)
    base = PolicyDecision(
        status="UNKNOWN",
        reason="ROUTE_NOT_VERIFIED",
        stage="FINAL",
        explanation="",
        comparison_scale_m=scale,
        uncovered=(req.id,),
        consulted=consulted,
        units_ok=True,
        body_ok=True,
        scale_ok=True if scale is not None else None,
        route_check="INDEPENDENT" if independent else "ABSENT",
    )
    if v.outcome == "INCONCLUSIVE" and v.failure_category in ("SYSTEM", "SEARCH_LIMIT", "REQUIREMENT"):
        return replace(
            base,
            explanation=f"The verification is inconclusive ({v.failure_category}); no route result can be credited.",
            limitations=("Bounded search or a system fault is not proof about the route.",),
        )
    if metric is not None and metric.value is not None:
        verdict = evaluate_threshold(metric.value, "GTE", req.lower, None, ctx.policy.tolerance)
        meets = verdict.meets and not named_violation
        return replace(
            base,
            status="PASS" if meets else "FAIL",
            reason="ROUTE_VERIFIED" if meets else "ROUTE_FAILED",
            explanation=(
                f"Independent verification measured {metric.metric_id} = {metric.value:.6g} {req.unit} "
                f"against >= {req.lower:g} (inclusive): {'met' if meets else 'not met'}."
            ),
            measured_value=metric.value,
            measured_unit=req.unit,
            covered=(req.id,) if meets else (),
            uncovered=() if meets else (req.id,),
            limitations=(NOMINAL_LIMITATION, "Modeled Earth field-test result; not a physical demonstration."),
            metrics=(metric,),
            numeric_decided=True,
            direct_evidence=True,
            assumed_parameters=metric.quantity_kind == "ASSUMED",
            coverage=metric.valid_fraction,
            coverage_ok=True,
        )
    if kind == "reserve" and (metric is not None or v.failure_category == "DATA") and not named_violation:
        return replace(
            base,
            reason="ENERGY_MODEL_MISSING",
            explanation="The energy reserve could not be evaluated because no usable energy model exists.",
            limitations=("Missing energy model is unknown, never zero consumption.",),
        )
    if named_violation:
        reason: ReasonCode = "INSUFFICIENT_EXPOSURE" if (kind == "exposure" and infeasible) else "ROUTE_FAILED"
        return replace(
            base,
            status="FAIL",
            reason=reason,
            explanation=f"Verification reports {sorted(set(v.violation_codes) & violation_codes)} for this row.",
            limitations=(NOMINAL_LIMITATION,),
            numeric_decided=True,
            direct_evidence=True,
        )
    return replace(base, explanation="The supplied verification carries no result for this requirement.")


PolicyFunction = Callable[[PolicyContext], PolicyDecision]

POLICY_FUNCTIONS: dict[str, PolicyFunction] = {
    "slope-band-area-fraction-v1": slope_band_area_fraction,
    "slope-w1-common-support-v1": slope_w1_common_support,
    "route-exposure-v1": route_dependent,
    "route-tasks-v1": route_dependent,
    "route-reserve-v1": route_dependent,
    "mineral-presence-v1": mineral_presence,
    "thermal-min-v1": thermal_min,
    "clearance-scale-v1": clearance_scale,
    "physical-gap-v1": physical_gap,
}

__all__ = [
    "ANALYSIS_ALGORITHM_IDS",
    "NOMINAL_LIMITATION",
    "POLICY_FUNCTIONS",
    "ROUTE_ALGORITHM_IDS",
    "PolicyContext",
    "PolicyDecision",
    "SideEvidence",
    "gap_decision",
]
