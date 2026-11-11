"""``COMPARE_REQUIREMENT`` logic as a pure function (guide 08 section 4.7).

:func:`compare_requirement` follows the common gate order of architecture 11 section 2:

1. physical-gap check (``NOT_NATURALLY_REPRODUCIBLE`` -> ``GAP / PHYSICAL_GAP``);
2. policy dispatch (an observable absent from ``catalog.OBSERVABLE_POLICY_BY_OBSERVABLE``, an unknown policy id or a
   mismatching id -> ``UNKNOWN / REQUIREMENT_UNDERSPECIFIED``);
3. evidence adequacy (units/body/mode, support window, coverage) and the policy's numeric rule (``policies.py``);
4. confidence per the rubric (``MEDIUM`` at most for nominal terrain-model evidence; never ``HIGH``/``UNASSESSED``
   without quantified uncertainty);
5. the adequacy receipt: gates SC-02..SC-11 and SC-13 with observable-specific reasons.

The facade only has to read artifacts (histograms) into :class:`~policies.SideEvidence`, call this function and
wrap :meth:`ComparisonOutcome.to_payload` plus a ``COMPARISON`` evidence draft.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from analogforge.ports import catalog
from analogforge.ports.common import Confidence, EvidenceRef, QualificationStatus, RuntimeMode
from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import (
    AdequacyReceipt,
    CompareRequirementPayload,
    GateEvidence,
    VerificationSummary,
)
from analogforge.science.comparison.policies import (
    POLICY_FUNCTIONS,
    PolicyContext,
    PolicyDecision,
    SideEvidence,
    gap_decision,
    underspecified,
)
from analogforge.science.config import GateId, ObservablePolicy, ScienceConfig
from analogforge.science.qualification import (
    ConfidenceDimensions,
    GateOutcomeName,
    ReasonCode,
    RequirementUnderspecifiedError,
    confidence_label,
)

GATE_ORDER: tuple[GateId, ...] = (
    "SC-02", "SC-03", "SC-04", "SC-05", "SC-06", "SC-07", "SC-08", "SC-09", "SC-10", "SC-11", "SC-13",
)  # fmt: skip
_EVIDENCE_GATES = frozenset({"SC-02", "SC-03", "SC-04", "SC-05", "SC-08", "SC-09", "SC-11"})
_NOT_APPLICABLE_REASON: dict[str, str] = {
    "SC-06": "static terrain observable with no acquisition-time dependence",
    "SC-10": "this comparison makes no corroboration claim across related sources",
    "SC-11": "no route experiment underlies this observable",
    "SC-13": "a requirement comparison is not a discovery or control claim",
}


@dataclass(frozen=True)
class CompareInputs:
    """Everything ``COMPARE_REQUIREMENT`` needs, already read from the request and its artifacts."""

    requirement: Requirement
    policy_id: str
    mode: RuntimeMode
    candidate: SideEvidence
    target: SideEvidence
    verification: VerificationSummary | None = None


@dataclass(frozen=True)
class ComparisonOutcome:
    """The pieces of a :class:`CompareRequirementPayload` plus the metrics for the COMPARISON evidence draft."""

    requirement_id: str
    policy_id: str
    policy_sha256: str
    status: QualificationStatus
    reason_code: ReasonCode
    evaluation_stage: Literal["PRELIMINARY", "FINAL"]
    confidence: Confidence
    comparison_scale_m: float | None
    measured_value: float | None
    measured_unit: str | None
    threshold_lower: float | None
    threshold_upper: float | None
    covered_subcriteria: tuple[str, ...]
    uncovered_subcriteria: tuple[str, ...]
    explanation: str
    limitations: tuple[str, ...]
    gates: tuple[GateEvidence, ...]
    validation_level: Literal["S0", "S1", "S2", "S3", "S4"]
    metrics: tuple[MeasuredMetric, ...]
    consulted_evidence_ids: tuple[UUID, ...]
    confidence_dimensions: ConfidenceDimensions

    def to_payload(self, comparison_evidence: EvidenceRef) -> CompareRequirementPayload:
        """Kit payload; ``comparison_evidence`` is the local key of the COMPARISON evidence draft."""
        return CompareRequirementPayload(
            requirement_id=self.requirement_id,
            proposed_status=self.status,
            reason_code=self.reason_code,
            evaluation_stage=self.evaluation_stage,
            confidence=self.confidence,
            comparison_scale_m=self.comparison_scale_m,
            measured_value=self.measured_value,
            measured_unit=self.measured_unit,
            threshold_lower=self.threshold_lower,
            threshold_upper=self.threshold_upper,
            covered_subcriteria=list(self.covered_subcriteria),
            uncovered_subcriteria=list(self.uncovered_subcriteria),
            explanation=self.explanation,
            limitations=list(self.limitations),
            comparison_evidence=comparison_evidence,
            adequacy=AdequacyReceipt(
                observable_policy_id=self.policy_id,
                policy_sha256=self.policy_sha256,
                gates=list(self.gates),
                validation_level=self.validation_level,
            ),
        )


def _refs(handles: tuple[EvidenceHandle, ...]) -> list[EvidenceRef]:
    ids = sorted({h.evidence_id for h in handles}, key=str)
    return [EvidenceRef(evidence_id=i) for i in ids]


def _gate(gate_id: GateId, outcome: GateOutcomeName, reason: str, refs: list[EvidenceRef]) -> GateEvidence:
    return GateEvidence(
        gate_id=gate_id, outcome=outcome, reason=reason, evidence=refs if gate_id in _EVIDENCE_GATES else []
    )


def _flag_gate(
    gate_id: GateId, flag: bool | None, ok: str, bad: str, unassessed: str, refs: list[EvidenceRef]
) -> GateEvidence:
    if flag is True:
        return _gate(gate_id, "SATISFIED", ok, refs)
    if flag is False:
        return _gate(gate_id, "UNSATISFIED", bad, refs)
    return _gate(gate_id, "NOT_ASSESSED", unassessed, refs)


def build_gates(
    decision: PolicyDecision,
    policy: ObservablePolicy | None,
    policy_id: str,
    min_valid_fraction: float | None,
    algorithm_lock: Mapping[str, str] | None = None,
) -> tuple[GateEvidence, ...]:
    """Gates SC-02..SC-11 and SC-13 for one decision (``NOT_APPLICABLE`` only with an observable-specific reason)."""
    refs = _refs(decision.consulted)
    gates: list[GateEvidence] = []
    for gate_id in GATE_ORDER:
        if policy is None:
            gates.append(
                _gate(gate_id, "NOT_ASSESSED", f"policy '{policy_id}' is unknown, so no gate can be assessed", refs)
            )
            continue
        if gate_id not in policy.applicable_gates:
            reason = _NOT_APPLICABLE_REASON.get(
                gate_id, f"gate {gate_id} does not apply to observable policy {policy_id}"
            )
            gates.append(_gate(gate_id, "NOT_APPLICABLE", reason, []))
            continue
        gates.append(_evaluate_gate(gate_id, decision, policy, refs, min_valid_fraction, algorithm_lock))
    return tuple(gates)


def _evaluate_gate(
    gate_id: GateId,
    d: PolicyDecision,
    policy: ObservablePolicy,
    refs: list[EvidenceRef],
    min_valid_fraction: float | None,
    algorithm_lock: Mapping[str, str] | None = None,
) -> GateEvidence:
    is_gap = d.status == "GAP"
    if gate_id == "SC-02":
        if is_gap:
            return _gate(gate_id, "NOT_APPLICABLE", "no measurement is consumed: the condition is a physical gap", [])
        if not d.consulted:
            return _gate(gate_id, "NOT_ASSESSED", "no evidence was consulted", refs)
        missing = [str(h.evidence_id) for h in d.consulted if h.kind != "SOURCE" and h.artifact_sha256 is None]
        if missing:
            return _gate(gate_id, "UNSATISFIED", f"derived evidence without an artifact hash: {sorted(missing)}", refs)
        return _gate(
            gate_id, "SATISFIED", f"{len(d.consulted)} evidence record(s) with parameter and artifact hashes", refs
        )
    if gate_id == "SC-03":
        if is_gap:
            return _gate(
                gate_id, "SATISFIED", "the requirement names a planetary condition Earth sites cannot reproduce", refs
            )
        if d.units_ok is False or d.body_ok is False:
            return _gate(gate_id, "UNSATISFIED", d.explanation, refs)
        if d.units_ok and d.consulted:
            return _gate(gate_id, "SATISFIED", "units, body and mode are consistent with the observable policy", refs)
        return _gate(gate_id, "NOT_ASSESSED", "units or body could not be assessed before the comparison stopped", refs)
    if gate_id == "SC-04":
        scale = d.comparison_scale_m
        return _flag_gate(
            gate_id,
            d.scale_ok,
            f"support {scale:g} m lies inside the requirement window" if scale is not None else "support within window",
            f"support {scale:g} m lies outside the requirement window"
            if scale is not None
            else "support outside window",
            "no support scale could be assessed",
            refs,
        )
    if gate_id == "SC-05":
        cov = d.coverage
        floor = "" if min_valid_fraction is None else f" (minimum {min_valid_fraction:.2f})"
        return _flag_gate(
            gate_id,
            d.coverage_ok,
            f"valid coverage {cov:.3f} meets the policy minimum{floor}" if cov is not None else "coverage sufficient",
            f"valid coverage {cov:.3f} is below the policy minimum{floor}"
            if cov is not None
            else "coverage insufficient",
            "coverage could not be assessed for this observable",
            refs,
        )
    if gate_id == "SC-06":
        if policy.temporal_support == "UNRESOLVED":
            return _gate(
                gate_id, "NOT_ASSESSED", "thermal variable, local time and aggregation are unresolved in v1", refs
            )
        return _gate(gate_id, "SATISFIED", "observable is not time dependent", refs)
    if gate_id == "SC-07":
        return _sc07(d, policy, refs)
    if gate_id == "SC-08":
        if is_gap:
            return _gate(gate_id, "NOT_APPLICABLE", "no numerical conclusion is drawn for a physical gap", [])
        if not d.numeric_decided:
            return _gate(gate_id, "NOT_ASSESSED", "no numerical decision was reached", refs)
        decisive = _decisive_metrics(d)
        if not decisive:
            return _gate(
                gate_id, "NOT_ASSESSED", "the decision cites no value whose uncertainty can be inspected", refs
            )
        silent = sorted({m.metric_id for m in decisive if not m.uncertainty_note.strip()})
        if silent:
            return _gate(gate_id, "UNSATISFIED", f"metric(s) {silent} carry no uncertainty statement", refs)
        return _gate(
            gate_id, "SATISFIED", "uncertainty not quantified; nominal modeled result (inclusive threshold)", refs
        )
    if gate_id == "SC-09":
        if is_gap:
            return _gate(gate_id, "NOT_APPLICABLE", "no numerical computation is involved in a physical gap", [])
        if not d.consulted:
            return _gate(gate_id, "NOT_ASSESSED", "no evidence was consulted", refs)
        lock = algorithm_lock or {}
        bad = []
        for h in d.consulted:
            if not h.algorithm_version.strip():
                bad.append(f"{h.evidence_id}: unversioned algorithm")
            elif h.algorithm_id in lock and lock[h.algorithm_id] != h.algorithm_version:
                bad.append(
                    f"{h.evidence_id}: {h.algorithm_id} {h.algorithm_version} differs from "
                    f"locked {lock[h.algorithm_id]}"
                )
        if bad:
            return _gate(gate_id, "UNSATISFIED", "; ".join(sorted(bad)), refs)
        return _gate(
            gate_id, "SATISFIED", "finite values; versioned algorithms match the lock; parameter hashes present", refs
        )
    if gate_id == "SC-11":
        if d.route_check == "INDEPENDENT":
            return _gate(gate_id, "SATISFIED", "an independent verify-route evidence recomputes the route", refs)
        return _gate(gate_id, "NOT_ASSESSED", "no independent verification of a route has been supplied", refs)
    return _gate(gate_id, "NOT_APPLICABLE", _NOT_APPLICABLE_REASON[gate_id], [])


def _decisive_metrics(d: PolicyDecision) -> list[MeasuredMetric]:
    """Metrics that carry the decision: those the policy attached plus the consulted metrics it names as subcriteria."""
    named = set(d.covered) | set(d.uncovered)
    found = list(d.metrics)
    seen = {m.metric_id for m in found}
    for h in d.consulted:
        for m in h.metrics:
            if m.value is not None and m.metric_id in named and m.metric_id not in seen:
                found.append(m)
                seen.add(m.metric_id)
    return found


def _sc07(d: PolicyDecision, policy: ObservablePolicy, refs: list[EvidenceRef]) -> GateEvidence:
    """Proxy/assumption gate from the consulted metrics' quantity kinds (never a blanket SATISFIED)."""
    if d.status == "GAP" and not d.consulted:
        return _gate("SC-07", "NOT_APPLICABLE", "no measurement is consumed: the condition is a physical gap", [])
    if not d.consulted:
        return _gate("SC-07", "NOT_ASSESSED", "no evidence was consulted", refs)
    kinds = {m.quantity_kind for h in d.consulted for m in h.metrics if m.value is not None}
    kinds |= {m.quantity_kind for m in d.metrics if m.value is not None}  # e.g. the verifier's assumed reserve
    accepts_proxy = policy.proxy_policy not in ("DIRECT_ONLY", "NO_PROXY_ACCEPTED")
    if "PROXY" in kinds and not accepts_proxy:
        return _gate("SC-07", "UNSATISFIED", "a proxy metric is consulted but the policy accepts no proxy", refs)
    if "ASSUMED" in kinds:
        if any(h.kind == "ASSUMPTION" for h in d.consulted):
            return _gate("SC-07", "SATISFIED", "assumed parameters are covered by consulted ASSUMPTION evidence", refs)
        return _gate(
            "SC-07", "NOT_ASSESSED", "assumed model parameters are used; no acceptance evidence is consulted", refs
        )
    text = (
        "direct measurement from the terrain model; no proxy is used"
        if policy.proxy_policy == "DIRECT_ONLY"
        else "no proxy is used or accepted for this observable"
    )
    return _gate("SC-07", "SATISFIED", text, refs)


def _validation_level(mode: RuntimeMode, d: PolicyDecision) -> Literal["S0", "S1", "S2", "S3", "S4"]:
    if d.status == "GAP" or not d.consulted:
        return "S0"
    if mode == "synthetic":
        return "S1"
    if d.route_check == "INDEPENDENT" and d.numeric_decided:
        return "S4"
    return "S3" if d.numeric_decided else "S2"


def _dimensions(d: PolicyDecision, policy: ObservablePolicy | None) -> ConfidenceDimensions:
    coverage: Literal["sufficient", "partial", "missing"] = (
        "missing" if d.coverage is None else ("sufficient" if d.coverage_ok else "partial")
    )
    return ConfidenceDimensions(
        source_quality="documented" if d.consulted else "unsupported",
        scale_match="incompatible" if d.scale_ok is False else "direct",
        coverage=coverage,
        temporal_match="limited"
        if policy is not None and policy.temporal_support == "UNRESOLVED"
        else "not_applicable",
        uncertainty="not_quantified",
        independence="not_assessed",
        limitations=d.limitations,
    )


def _resolve(inputs: CompareInputs, config: ScienceConfig) -> tuple[PolicyDecision, ObservablePolicy | None, str]:
    req = inputs.requirement
    if req.operator == "NOT_NATURALLY_REPRODUCIBLE":
        pid = inputs.policy_id if config.policy(inputs.policy_id) is not None else "physical-gap-v1"
        return gap_decision(req), config.policy(pid), pid
    expected = catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(req.observable)
    policy = config.policy(inputs.policy_id)
    ctx_policy = policy if policy is not None else config.policy(expected) if expected is not None else None
    placeholder = ctx_policy if ctx_policy is not None else next(iter(config.algorithms.observable_policies.values()))
    ctx = PolicyContext(
        req, inputs.policy_id, placeholder, inputs.mode, inputs.candidate, inputs.target, inputs.verification
    )
    if expected is None:
        return (
            underspecified(ctx, f"observable '{req.observable}' has no registered observable policy"),
            None,
            inputs.policy_id,
        )
    if policy is None:
        return (
            underspecified(ctx, f"observable policy '{inputs.policy_id}' is not defined in algorithms.yaml"),
            None,
            inputs.policy_id,
        )
    if expected != inputs.policy_id:
        return (
            underspecified(
                ctx, f"observable '{req.observable}' requires policy '{expected}', not '{inputs.policy_id}'"
            ),
            policy,
            inputs.policy_id,
        )
    ctx = PolicyContext(
        req, inputs.policy_id, policy, inputs.mode, inputs.candidate, inputs.target, inputs.verification
    )
    try:
        return POLICY_FUNCTIONS[inputs.policy_id](ctx), policy, inputs.policy_id
    except RequirementUnderspecifiedError as exc:
        return underspecified(ctx, exc.message), policy, inputs.policy_id


def compare_requirement(inputs: CompareInputs, config: ScienceConfig) -> ComparisonOutcome:
    """Evaluate one requirement against one candidate.  Never raises for expected data problems."""
    req = inputs.requirement
    decision, policy, policy_id = _resolve(inputs, config)
    policy_sha = config.policy_sha256(policy_id) or canonical_sha256({"policy_id": policy_id, "resolved": False})
    confidence = confidence_label(
        adequate=decision.numeric_decided,
        direct_evidence=decision.direct_evidence,
        coverage=decision.coverage,
        uncertainty="not_quantified",
        assumed_parameters=decision.assumed_parameters,
        medium_min_coverage=config.algorithms.thresholds.medium_confidence_min_coverage,
    )
    min_cov = None if policy is None else policy.min_valid_fraction
    consulted_ids = tuple(sorted({h.evidence_id for h in decision.consulted}, key=str))
    return ComparisonOutcome(
        requirement_id=req.id,
        policy_id=policy_id,
        policy_sha256=policy_sha,
        status=decision.status,
        reason_code=decision.reason,
        evaluation_stage=decision.stage,
        confidence=confidence,
        comparison_scale_m=decision.comparison_scale_m,
        measured_value=decision.measured_value,
        measured_unit=decision.measured_unit,
        threshold_lower=req.lower,
        threshold_upper=req.upper,
        covered_subcriteria=decision.covered,
        uncovered_subcriteria=decision.uncovered,
        explanation=decision.explanation,
        limitations=decision.limitations,
        gates=build_gates(decision, policy, policy_id, min_cov, config.algorithms.algorithm_lock),
        validation_level=_validation_level(inputs.mode, decision),
        # The COMPARISON evidence carries every value the decision rests on (policy metrics plus the consulted
        # subcriteria), so the claim audit can inspect coverage and uncertainty (SC-05/SC-08) on the cited record.
        metrics=tuple(_decisive_metrics(decision)),
        consulted_evidence_ids=consulted_ids,
        confidence_dimensions=_dimensions(decision, policy),
    )
