"""``AUDIT_EVIDENCE``: science-owned gate evidence SC-02..SC-11 and SC-13 per claim (guide 08 section 4.15).

Pure and mechanical: every outcome follows from the cited evidence handles, the requirement window and the versioned
observable policy.  The audit never decides publication; it reports gates and findings that the platform's assurance
layer (SC-01, SC-12, SC-14, SC-15 and the ALLOWED/LIMITED/BLOCKED decision) consumes.

Gate semantics used here (``NOT_ASSESSED`` = could not be established, never a silent pass):

* SC-02 every cited evidence id resolves to an authorized handle of this mode with parameter hashes (and an artifact
  hash for derived evidence).
* SC-03 body valid for the observable policy and metric units consistent with the metric id.
* SC-04 the claim's evidence support (``comparison_scale_m``) lies inside the requirement window; finer **or** coarser
  is ``SCALE_MISMATCH``.  Comparison evidence defines the claim scale when cited; otherwise all scaled evidence does.
* SC-05 coverage (``MeasuredMetric.valid_fraction``) meets the policy minimum; a value with zero valid coverage is a
  zero-filled nodata signature and fails.
* SC-06 ``NOT_APPLICABLE`` (with reason) for non-temporal policies; ``NOT_ASSESSED`` for unresolved temporal support.
* SC-07 proxy metrics fail when the policy accepts no proxy; assumed parameters need an ASSUMPTION evidence.
* SC-08 an explicit uncertainty statement exists on every cited value ("not quantified" => nominal wording).
* SC-09 finite (guaranteed by the models), versioned, hashed and consistent with the algorithm lock.
* SC-10 two distinct source products of one ancestry family are not independent corroboration.
* SC-11 VERIFICATION claims need VERIFICATION evidence whose ``algorithm_id`` differs from the search evidence's.
* SC-13 DISCOVERY claims need search extent, reference set, negative controls and mission-sensitivity evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef, RuntimeMode
from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import (
    AuditEvidenceInput,
    AuditEvidencePayload,
    AuditFinding,
    ClaimGateEvidence,
    ClaimScope,
    GateEvidence,
    ScreenCandidatesPayload,
)
from analogforge.science.comparison.scale import check_support_window
from analogforge.science.config import GateId, ObservablePolicy, ScienceConfig

Outcome = Literal["SATISFIED", "UNSATISFIED", "NOT_ASSESSED", "NOT_APPLICABLE"]
Rule = Literal[
    "CRS_MISMATCH", "SCALE_MISMATCH", "COVERAGE_MISSING", "PROXY_OVERSTATED", "MODE_MISMATCH",
    "MISSING_PROVENANCE", "UNIT_MISMATCH", "SHARED_ANCESTRY", "UNCERTAINTY_UNQUANTIFIED", "ROUTE_NOT_VERIFIED",
]  # fmt: skip
Severity = Literal["INFO", "WARNING", "BLOCKING"]
Repair = Literal[
    "RECOMPUTE", "ACQUIRE_EVIDENCE_OR_DOWNGRADE", "CORRECT_METADATA", "RESTORE_CONTRACT",
    "NARROW_LANGUAGE", "REVIEW_ASSUMPTION", "INVESTIGATE_ALTERNATIVE", "RECORD_UNKNOWN",
]  # fmt: skip

AUDIT_GATES: Final[tuple[GateId, ...]] = (
    "SC-02", "SC-03", "SC-04", "SC-05", "SC-06", "SC-07", "SC-08", "SC-09", "SC-10", "SC-11", "SC-13",
)  # fmt: skip
_CHECK_FOR_GATE: Final[dict[str, tuple[str, ...]]] = {
    "SC-02": ("provenance",),
    "SC-03": ("units", "crs"),
    "SC-04": ("scale",),
    "SC-05": ("coverage",),
    "SC-07": ("proxies",),
    "SC-08": ("uncertainty",),
    "SC-09": ("provenance",),
    "SC-10": ("independence",),
    "SC-11": ("independence",),
}
SEARCH_ALGORITHM_ID: Final = catalog.ALGORITHM_IDS["SEARCH_ROUTE"]
VERIFY_ALGORITHM_ID: Final = catalog.ALGORITHM_IDS["VERIFY_ROUTE"]
SCREEN_ALGORITHM_ID: Final = catalog.ALGORITHM_IDS["SCREEN_CANDIDATES"]
# product token -> ancestry family.  NASADEM re-processes SRTM, so the two are one family.
ANCESTRY_FAMILY_BY_PRODUCT: Final[dict[str, str]] = {
    "NASADEM": "SRTM",
    "SRTM": "SRTM",
    "ASTER": "ASTER",
    "MOLA": "MOLA",
    "LOLA": "LOLA",
    "DIVINER": "DIVINER",
    "EMIT": "EMIT",
}
# metric id (prefix before ':' or '@') -> accepted units
EXPECTED_UNITS: Final[dict[str, frozenset[str]]] = {
    "valid_fraction": frozenset({"fraction"}),
    "mineral_valid_fraction": frozenset({"fraction"}),
    "slope_area_fraction": frozenset({"fraction"}),
    "surface_slope_deg": frozenset({"deg"}),
    "max_surface_slope_deg": frozenset({"deg"}),
    "slope_w1_deg": frozenset({"deg"}),
    "route_distance_m": frozenset({"m"}),
    "unique_exposure_m": frozenset({"m"}),
    "traversed_exposure_m": frozenset({"m"}),
    "detrended_rms_height_m": frozenset({"m"}),
    "robust_relief_m": frozenset({"m"}),
    "route_duration_s": frozenset({"s"}),
    "min_temperature_k": frozenset({"K"}),
    "reserve_pct": frozenset({"percent", "%"}),
    "tasks_completed": frozenset({"tasks", "count"}),
}


@dataclass(frozen=True)
class DiscoveryEvidence:
    """What a screening evidence record establishes for SC-13 (read from its payload by the facade)."""

    search_extent_recorded: bool
    reference_set_id: str | None
    negative_control_window_ids: tuple[str, ...]
    novelty_statuses_recorded: bool
    mission_sensitivity_evidence_ids: tuple[UUID, ...]

    def missing(self) -> list[str]:
        out: list[str] = []
        if not self.search_extent_recorded:
            out.append("search extent")
        if not self.reference_set_id or not self.novelty_statuses_recorded:
            out.append("reference-set membership")
        if not self.negative_control_window_ids:
            out.append("negative control")
        if not self.mission_sensitivity_evidence_ids:
            out.append("mission sensitivity")
        return out


def discovery_evidence_from_screening(
    payload: ScreenCandidatesPayload,
    *,
    reference_set_id: str | None,
    mission_sensitivity_evidence_ids: Iterable[UUID] = (),
) -> DiscoveryEvidence:
    """Derive :class:`DiscoveryEvidence` from a ``SCREEN_CANDIDATES`` payload (no value is invented)."""
    return DiscoveryEvidence(
        search_extent_recorded=True,
        reference_set_id=reference_set_id,
        negative_control_window_ids=tuple(sorted(w.window_id for w in payload.windows if w.is_negative_control)),
        novelty_statuses_recorded=bool(payload.windows)
        and all(w.novelty_status != "NOT_ASSESSED" for w in payload.windows if not w.excluded),
        mission_sensitivity_evidence_ids=tuple(sorted(mission_sensitivity_evidence_ids, key=str)),
    )


def _refs(handles: Iterable[EvidenceHandle]) -> list[EvidenceRef]:
    return [EvidenceRef(evidence_id=i) for i in sorted({h.evidence_id for h in handles}, key=str)]


def _metric_family(metric_id: str) -> str:
    for sep in (":", "@"):
        metric_id = metric_id.split(sep, 1)[0]
    return metric_id


def _product_tokens(handle: EvidenceHandle) -> set[str]:
    text = " ".join([handle.local_key_origin or "", handle.algorithm_id, *handle.limitations]).upper()
    return {token for token in ANCESTRY_FAMILY_BY_PRODUCT if token in text}


class _ClaimAudit:
    def __init__(
        self,
        claim: ClaimScope,
        handles: list[EvidenceHandle],
        missing: list[UUID],
        *,
        mode: RuntimeMode,
        requirement: Requirement | None,
        policy: ObservablePolicy | None,
        config: ScienceConfig,
        checks: frozenset[str],
        source_families: Mapping[UUID, frozenset[str]],
        discovery: Mapping[UUID, DiscoveryEvidence],
    ) -> None:
        self.claim, self.handles, self.missing = claim, handles, missing
        self.mode, self.requirement, self.policy, self.config = mode, requirement, policy, config
        self.checks, self.source_families, self.discovery = checks, source_families, discovery
        self.findings: list[AuditFinding] = []
        self.refs = _refs(handles)

    # ---- helpers
    def _finding(self, rule: Rule, severity: Severity, ids: Iterable[UUID], message: str, repair: Repair) -> None:
        n = sum(1 for f in self.findings if f.rule_code == rule)
        self.findings.append(
            AuditFinding(
                finding_id=f"{self.claim.claim_id}:{rule}:{n + 1}",
                rule_code=rule,
                severity=severity,
                requirement_id=self.claim.requirement_id,
                evidence_ids=sorted(set(ids), key=str),
                message=message,
                required_repair=repair,
            )
        )

    def _gate(self, gate_id: GateId, outcome: Outcome, reason: str, *, refs: bool = True) -> GateEvidence:
        return GateEvidence(gate_id=gate_id, outcome=outcome, reason=reason, evidence=self.refs if refs else [])

    def _skipped(self, gate_id: GateId) -> GateEvidence | None:
        wanted = _CHECK_FOR_GATE.get(gate_id)
        if wanted is not None and not any(c in self.checks for c in wanted):
            return self._gate(
                gate_id, "NOT_ASSESSED", f"check '{wanted[0]}' was not requested in check_set", refs=False
            )
        return None

    def _metrics(self) -> list[tuple[EvidenceHandle, MeasuredMetric]]:
        return [(h, m) for h in self.handles for m in h.metrics]

    # ---- gates
    def sc02(self) -> GateEvidence:
        if (skip := self._skipped("SC-02")) is not None:
            return skip
        problems: list[str] = []
        if not self.claim.evidence_ids:
            problems.append("the claim cites no evidence")
        if self.missing:
            problems.append(f"unresolvable evidence ids {sorted(str(i) for i in self.missing)}")
        wrong_mode = [h for h in self.handles if h.mode != self.mode]
        if wrong_mode:
            problems.append(f"evidence from another mode than '{self.mode}'")
            self._finding(
                "MODE_MISMATCH", "BLOCKING", (h.evidence_id for h in wrong_mode),
                f"evidence recorded in mode(s) {sorted({h.mode for h in wrong_mode})} cited by a '{self.mode}' claim",
                "RESTORE_CONTRACT",
            )  # fmt: skip
        no_artifact = [h for h in self.handles if h.kind != "SOURCE" and h.artifact_sha256 is None]
        if no_artifact:
            problems.append(
                f"derived evidence without an artifact hash: {sorted(str(h.evidence_id) for h in no_artifact)}"
            )
        if problems:
            self._finding(
                "MISSING_PROVENANCE", "BLOCKING", [*self.missing, *(h.evidence_id for h in no_artifact)],
                "; ".join(problems), "ACQUIRE_EVIDENCE_OR_DOWNGRADE",
            )  # fmt: skip
            return self._gate("SC-02", "UNSATISFIED", "; ".join(problems))
        return self._gate(
            "SC-02", "SATISFIED", f"{len(self.handles)} evidence record(s) resolve with parameter and artifact hashes"
        )

    def sc03(self) -> GateEvidence:
        if (skip := self._skipped("SC-03")) is not None:
            return skip
        if not self.handles:
            return self._gate("SC-03", "NOT_ASSESSED", "no resolvable evidence to inspect")
        problems: list[str] = []
        if self.policy is not None:
            bad_body = [h for h in self.handles if h.body not in self.policy.valid_bodies]
            if bad_body:
                problems.append(
                    f"body {sorted({h.body for h in bad_body})} is not valid for the policy "
                    f"(valid {list(self.policy.valid_bodies)})"
                )
                self._finding(
                    "CRS_MISMATCH", "BLOCKING", (h.evidence_id for h in bad_body), problems[-1], "CORRECT_METADATA"
                )
        wrong_units = [
            (h, m) for h, m in self._metrics()
            if (allowed := EXPECTED_UNITS.get(_metric_family(m.metric_id))) is not None and m.unit not in allowed
        ]  # fmt: skip
        for h, m in wrong_units:
            problems.append(f"metric {m.metric_id} has unit '{m.unit}'")
            self._finding(
                "UNIT_MISMATCH", "BLOCKING", [h.evidence_id], f"metric {m.metric_id} is reported in '{m.unit}'",
                "CORRECT_METADATA",
            )  # fmt: skip
        if problems:
            return self._gate("SC-03", "UNSATISFIED", "; ".join(problems))
        if self.policy is None:
            return self._gate("SC-03", "NOT_ASSESSED", "no observable policy is known, so the body cannot be judged")
        return self._gate(
            "SC-03", "SATISFIED", "body is valid for the observable policy and metric units match their ids"
        )

    def _claim_scale_handles(self) -> list[EvidenceHandle]:
        scaled = [h for h in self.handles if h.comparison_scale_m is not None]
        comparison = [h for h in scaled if h.kind == "COMPARISON"]
        return comparison or scaled

    def sc04(self) -> GateEvidence:
        if (skip := self._skipped("SC-04")) is not None:
            return skip
        req = self.requirement
        if req is None:
            return self._gate("SC-04", "NOT_ASSESSED", "no requirement window is available for this claim")
        if req.minimum_support_scale_m is None and req.maximum_support_scale_m is None:
            return self._gate("SC-04", "NOT_ASSESSED", f"requirement {req.id} declares no support window")
        scaled = self._claim_scale_handles()
        if not scaled:
            return self._gate("SC-04", "NOT_ASSESSED", "no cited evidence states a comparison scale")
        bad: list[tuple[EvidenceHandle, str]] = []
        for h in scaled:
            assert h.comparison_scale_m is not None
            verdict = check_support_window(
                h.comparison_scale_m, req.minimum_support_scale_m, req.maximum_support_scale_m
            )
            if not verdict.supported:
                side = "finer than the minimum" if verdict.reason == "BELOW_MINIMUM" else "coarser than the maximum"
                bad.append((h, f"comparison scale {h.comparison_scale_m:g} m is {side} of the requirement window"))
        window = f"[{req.minimum_support_scale_m}, {req.maximum_support_scale_m}] m"
        if bad:
            for h, text in bad:
                self._finding("SCALE_MISMATCH", "BLOCKING", [h.evidence_id], f"{text} {window}", "RECOMPUTE")
            return self._gate("SC-04", "UNSATISFIED", f"{bad[0][1]} {window}")
        return self._gate(
            "SC-04", "SATISFIED", f"all cited comparison scales lie inside the requirement window {window}"
        )

    def sc05(self) -> GateEvidence:
        if (skip := self._skipped("SC-05")) is not None:
            return skip
        valued = [(h, m) for h, m in self._metrics() if m.value is not None]
        if not valued:
            return self._gate("SC-05", "NOT_ASSESSED", "no cited metric carries a value to assess coverage for")
        floor = self.policy.min_valid_fraction if self.policy else self.config.algorithms.thresholds.min_valid_fraction
        zero = [(h, m) for h, m in valued if m.valid_fraction == 0.0]
        if zero:
            ids = [h.evidence_id for h, _ in zero]
            self._finding(
                "COVERAGE_MISSING", "BLOCKING", ids,
                f"metric(s) {sorted({m.metric_id for _, m in zero})} report a value with zero valid coverage "
                "(nodata filled with a number)", "ACQUIRE_EVIDENCE_OR_DOWNGRADE",
            )  # fmt: skip
            return self._gate("SC-05", "UNSATISFIED", "a value is reported with zero valid coverage")
        low = [(h, m) for h, m in valued if m.valid_fraction < floor]
        coverage = min(m.valid_fraction for _, m in valued)
        if low:
            self._finding(
                "COVERAGE_MISSING", "WARNING", [h.evidence_id for h, _ in low],
                f"valid coverage {coverage:.3f} is below the policy minimum {floor:.2f}",
                "ACQUIRE_EVIDENCE_OR_DOWNGRADE",
            )  # fmt: skip
            return self._gate(
                "SC-05", "UNSATISFIED", f"valid coverage {coverage:.3f} is below the policy minimum {floor:.2f}"
            )
        return self._gate("SC-05", "SATISFIED", f"valid coverage {coverage:.3f} meets the policy minimum {floor:.2f}")

    def sc06(self) -> GateEvidence:
        if self.policy is None:
            return self._gate(
                "SC-06", "NOT_ASSESSED", "no observable policy is known, so temporal support is undetermined"
            )
        if self.policy.temporal_support == "UNRESOLVED":
            return self._gate(
                "SC-06", "NOT_ASSESSED", "thermal variable, local time and aggregation are unresolved in v1"
            )
        return self._gate(
            "SC-06", "NOT_APPLICABLE", "static terrain observable with no acquisition-time dependence", refs=False
        )

    def sc07(self) -> GateEvidence:
        if (skip := self._skipped("SC-07")) is not None:
            return skip
        if not self.handles:
            return self._gate("SC-07", "NOT_ASSESSED", "no resolvable evidence to inspect")
        proxies = [(h, m) for h, m in self._metrics() if m.quantity_kind == "PROXY"]
        assumed = [(h, m) for h, m in self._metrics() if m.quantity_kind == "ASSUMED"]
        accepts_proxy = self.policy is not None and self.policy.proxy_policy not in ("DIRECT_ONLY", "NO_PROXY_ACCEPTED")
        if proxies and not accepts_proxy:
            self._finding(
                "PROXY_OVERSTATED", "BLOCKING", [h.evidence_id for h, _ in proxies],
                f"proxy metric(s) {sorted({m.metric_id for _, m in proxies})} cited but the policy accepts no proxy",
                "NARROW_LANGUAGE",
            )  # fmt: skip
            return self._gate("SC-07", "UNSATISFIED", "a proxy is cited where only direct measurement is accepted")
        if assumed:
            if any(h.kind == "ASSUMPTION" for h in self.handles):
                return self._gate("SC-07", "SATISFIED", "assumed parameters are covered by cited ASSUMPTION evidence")
            self._finding(
                "PROXY_OVERSTATED", "WARNING", [h.evidence_id for h, _ in assumed],
                "assumed model parameters are used and no ASSUMPTION evidence is cited; acceptance must be supplied",
                "REVIEW_ASSUMPTION",
            )  # fmt: skip
            return self._gate("SC-07", "NOT_ASSESSED", "assumed parameters are used; no acceptance evidence is cited")
        return self._gate("SC-07", "SATISFIED", "direct measurements only; no proxy or assumed parameter is cited")

    def sc08(self) -> GateEvidence:
        if (skip := self._skipped("SC-08")) is not None:
            return skip
        valued = [(h, m) for h, m in self._metrics() if m.value is not None]
        if not valued:
            return self._gate("SC-08", "NOT_ASSESSED", "no numerical value is cited")
        silent = [(h, m) for h, m in valued if not m.uncertainty_note.strip()]
        if silent:
            self._finding(
                "UNCERTAINTY_UNQUANTIFIED", "WARNING", [h.evidence_id for h, _ in silent],
                f"metric(s) {sorted({m.metric_id for _, m in silent})} carry no uncertainty statement",
                "NARROW_LANGUAGE",
            )  # fmt: skip
            return self._gate("SC-08", "UNSATISFIED", "a cited value has no uncertainty statement")
        nominal = [(h, m) for h, m in valued if "not quantified" in m.uncertainty_note.lower()]
        if nominal:
            self._finding(
                "UNCERTAINTY_UNQUANTIFIED", "INFO", [h.evidence_id for h, _ in nominal],
                "uncertainty not quantified; results are nominal modeled values", "NARROW_LANGUAGE",
            )  # fmt: skip
            return self._gate("SC-08", "SATISFIED", "uncertainty not quantified; nominal modeled result")
        return self._gate("SC-08", "SATISFIED", "every cited value states its uncertainty")

    def sc09(self) -> GateEvidence:
        if (skip := self._skipped("SC-09")) is not None:
            return skip
        if not self.handles:
            return self._gate("SC-09", "NOT_ASSESSED", "no resolvable evidence to inspect")
        lock = self.config.algorithms.algorithm_lock
        bad: list[str] = []
        for h in self.handles:
            if not h.algorithm_version.strip():
                bad.append(f"{h.evidence_id}: unversioned algorithm")
            elif h.algorithm_id in lock and lock[h.algorithm_id] != h.algorithm_version:
                bad.append(
                    f"{h.evidence_id}: {h.algorithm_id} {h.algorithm_version} differs from "
                    f"locked {lock[h.algorithm_id]}"
                )
        if bad:
            return self._gate("SC-09", "UNSATISFIED", "; ".join(bad))
        return self._gate(
            "SC-09", "SATISFIED", "finite values; versioned algorithms match the lock; parameter hashes present"
        )

    def _families(self, h: EvidenceHandle) -> dict[str, str]:
        explicit = self.source_families.get(h.evidence_id)
        tokens = set(explicit) if explicit is not None else _product_tokens(h)
        return {t: ANCESTRY_FAMILY_BY_PRODUCT.get(t.upper(), t.upper()) for t in tokens}

    def sc10(self) -> GateEvidence:
        if (skip := self._skipped("SC-10")) is not None:
            return skip
        products: dict[str, str] = {}
        owners: dict[str, list[UUID]] = {}
        for h in self.handles:
            for product, family in self._families(h).items():
                products[product.upper()] = family
                owners.setdefault(product.upper(), []).append(h.evidence_id)
        if len(products) < 2:
            return self._gate(
                "SC-10", "NOT_APPLICABLE", "claim rests on a single source product lineage; no corroboration claimed",
                refs=False,
            )  # fmt: skip
        by_family: dict[str, list[str]] = {}
        for product, family in sorted(products.items()):
            by_family.setdefault(family, []).append(product)
        shared = {f: p for f, p in by_family.items() if len(p) > 1}
        if shared:
            ids = [i for p in shared.values() for prod in p for i in owners[prod]]
            text = "; ".join(f"{'+'.join(p)} share ancestry family {f}" for f, p in sorted(shared.items()))
            self._finding(
                "SHARED_ANCESTRY",
                "WARNING",
                ids,
                f"{text}: agreement is not independent replication",
                "NARROW_LANGUAGE",
            )
            return self._gate("SC-10", "UNSATISFIED", f"{text}; not independent corroboration")
        return self._gate(
            "SC-10", "SATISFIED", f"source products {sorted(products)} belong to distinct ancestry families"
        )

    def sc11(self) -> GateEvidence:
        if (skip := self._skipped("SC-11")) is not None:
            return skip
        search = [h for h in self.handles if h.algorithm_id == SEARCH_ALGORITHM_ID]
        verification = [h for h in self.handles if h.kind == "VERIFICATION"]
        if self.claim.claim_type != "VERIFICATION":
            if search and not verification:
                self._finding(
                    "ROUTE_NOT_VERIFIED", "BLOCKING", [h.evidence_id for h in search],
                    "route search evidence is cited without an independent verification", "RECOMPUTE",
                )  # fmt: skip
                return self._gate(
                    "SC-11", "UNSATISFIED", "a route search result is cited without independent verification"
                )
            return self._gate(
                "SC-11", "NOT_APPLICABLE", "the claim does not rest on a route experiment verification", refs=False
            )
        if not verification:
            if search:
                self._finding(
                    "ROUTE_NOT_VERIFIED", "BLOCKING", [h.evidence_id for h in search],
                    "the solver result is cited as its own verification", "RECOMPUTE",
                )  # fmt: skip
                return self._gate("SC-11", "UNSATISFIED", "solver output is not independent verification")
            return self._gate("SC-11", "NOT_ASSESSED", "no verification evidence is cited")
        search_ids = {h.algorithm_id for h in search}
        same = [h for h in verification if h.algorithm_id in search_ids]
        if same:
            self._finding(
                "ROUTE_NOT_VERIFIED", "BLOCKING", [h.evidence_id for h in same],
                "verification and search evidence share one algorithm_id; the check is not independent", "RECOMPUTE",
            )  # fmt: skip
            return self._gate("SC-11", "UNSATISFIED", "verification uses the same algorithm_id as the search evidence")
        return self._gate(
            "SC-11", "SATISFIED",
            f"independent verification ({sorted({h.algorithm_id for h in verification})}) differs from the search "
            "algorithm",
        )  # fmt: skip

    def sc13(self) -> GateEvidence:
        if self.claim.claim_type != "DISCOVERY":
            return self._gate(
                "SC-13", "NOT_APPLICABLE", "the claim makes no discovery or control statement", refs=False
            )
        screening = [h for h in self.handles if h.algorithm_id == SCREEN_ALGORITHM_ID]
        if not screening:
            return self._gate("SC-13", "UNSATISFIED", "a discovery claim cites no screening evidence")
        records = [self.discovery[h.evidence_id] for h in screening if h.evidence_id in self.discovery]
        if not records:
            return self._gate("SC-13", "NOT_ASSESSED", "screening evidence is cited but its controls were not supplied")
        missing = sorted({m for r in records for m in r.missing()})
        if missing:
            return self._gate("SC-13", "UNSATISFIED", f"discovery evidence lacks: {', '.join(missing)}")
        return self._gate(
            "SC-13", "SATISFIED", "search extent, reference set, negative control and mission sensitivity are recorded"
        )

    def run(self) -> ClaimGateEvidence:
        builders: dict[str, Callable[[], GateEvidence]] = {
            "SC-02": self.sc02, "SC-03": self.sc03, "SC-04": self.sc04, "SC-05": self.sc05, "SC-06": self.sc06,
            "SC-07": self.sc07, "SC-08": self.sc08, "SC-09": self.sc09, "SC-10": self.sc10, "SC-11": self.sc11,
            "SC-13": self.sc13,
        }  # fmt: skip
        gates = [builders[g]() for g in AUDIT_GATES]
        return ClaimGateEvidence(claim_id=self.claim.claim_id, gates=gates)


def audit_evidence(
    inputs: AuditEvidenceInput,
    *,
    mode: RuntimeMode,
    evidence: Sequence[EvidenceHandle],
    config: ScienceConfig,
    requirements: Mapping[str, Requirement] | None = None,
    source_families: Mapping[UUID, frozenset[str]] | None = None,
    discovery: Mapping[UUID, DiscoveryEvidence] | None = None,
) -> AuditEvidencePayload:
    """Gate evidence for every claim, in claim order, with findings sorted by id.  Never decides publication."""
    by_id = {h.evidence_id: h for h in evidence}
    checks = frozenset(inputs.check_set)
    out: list[ClaimGateEvidence] = []
    findings: list[AuditFinding] = []
    for claim in inputs.claims:
        handles = [by_id[i] for i in dict.fromkeys(claim.evidence_ids) if i in by_id]
        missing = [i for i in dict.fromkeys(claim.evidence_ids) if i not in by_id]
        requirement = (requirements or {}).get(claim.requirement_id) if claim.requirement_id else None
        policy_id = catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(requirement.observable) if requirement else None
        policy = config.policy(policy_id) if policy_id else None
        audit = _ClaimAudit(
            claim, handles, missing, mode=mode, requirement=requirement, policy=policy, config=config, checks=checks,
            source_families=source_families or {}, discovery=discovery or {},
        )  # fmt: skip
        out.append(audit.run())
        findings.extend(audit.findings)
    findings.sort(key=lambda f: f.finding_id)
    return AuditEvidencePayload(claim_gates=out, findings=findings)


__all__ = [
    "ANCESTRY_FAMILY_BY_PRODUCT",
    "AUDIT_GATES",
    "DiscoveryEvidence",
    "EXPECTED_UNITS",
    "audit_evidence",
    "discovery_evidence_from_screening",
]
