"""SCN-08 (science level): COMPARE_REQUIREMENT policies, W1 and the adequacy receipt.

Every outcome is derived from the evidence handed to the pure function; perturbation tests change one input and
assert the verdict changes as predicted.  Independent oracles: SciPy's weighted Wasserstein distance, hand
arithmetic on bin centres.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from scipy.stats import wasserstein_distance

from analogforge.ports import catalog
from analogforge.ports.common import Body, EvidenceKind, EvidenceRef, RuntimeMode
from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import CompareRequirementPayload, Histogram, VerificationSummary
from analogforge.science.comparison.compare import GATE_ORDER, CompareInputs, ComparisonOutcome, compare_requirement
from analogforge.science.comparison.policies import SideEvidence
from analogforge.science.comparison.w1 import W1Result, binned_w1, empirical_w1, w1_from_histograms
from analogforge.science.config import ScienceConfig, load_config
from analogforge.science.errors import RasterError, ScaleError
from analogforge.science.features.histogram import SLOPE_HIST_CENTRES, SLOPE_HIST_EDGES, area_weighted_histogram

KIT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "kit"
CONFIG = load_config()
SHA = "a" * 64


def _requirements() -> dict[str, Requirement]:
    out: dict[str, Requirement] = {}
    for mission in ("mission-mars-mobility.json", "mission-moon-gap.json"):
        data = json.loads((KIT / "missions" / mission).read_text())
        for raw in data["requirements"]:
            out.setdefault(raw["id"], Requirement.model_validate(raw))
    return out


REQ = _requirements()


def metric(
    metric_id: str,
    value: float | None,
    *,
    unit: str = "fraction",
    scale: float | None = 60.0,
    valid: float = 1.0,
    kind: str = "DERIVED",
) -> MeasuredMetric:
    return MeasuredMetric(
        metric_id=metric_id,
        value=value,
        unit=unit,
        support_scale_m=scale,
        quantity_kind=kind,  # type: ignore[arg-type]
        method_id="test",
        valid_fraction=valid,
        uncertainty_note="nominal",
    )


def handle(
    *metrics: MeasuredMetric,
    kind: EvidenceKind = "DERIVED",
    mode: RuntimeMode = "synthetic",
    body: Body = "EARTH",
    algorithm_id: str = "analyze-candidate",
    scale: float | None = None,
    artifact: bool = True,
) -> EvidenceHandle:
    return EvidenceHandle(
        evidence_id=uuid4(),
        kind=kind,
        mode=mode,
        body=body,
        artifact_sha256=SHA if artifact else None,
        algorithm_id=algorithm_id,
        algorithm_version="1.0.0",
        parameters_sha256="b" * 64,
        comparison_scale_m=scale,
        metrics=list(metrics),
    )


def hist(fractions: list[float], scale: float, area: float = 1.0e6) -> Histogram:
    assert len(fractions) == len(SLOPE_HIST_EDGES) - 1
    return Histogram(
        metric_id="surface_slope_deg",
        unit="deg",
        edges=list(SLOPE_HIST_EDGES),
        area_fraction=fractions,
        valid_area_m2=area,
        support_scale_m=scale,
    )


def point(bin_index: int, scale: float) -> Histogram:
    f = [0.0] * 9
    f[bin_index] = 1.0
    return hist(f, scale)


def run(
    requirement_id: str,
    *,
    candidate: SideEvidence | None = None,
    target: SideEvidence | None = None,
    verification: VerificationSummary | None = None,
    mode: RuntimeMode = "synthetic",
    requirement: Requirement | None = None,
    policy_id: str | None = None,
    config: ScienceConfig = CONFIG,
) -> ComparisonOutcome:
    req = requirement or REQ[requirement_id]
    pid = policy_id or catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(req.observable, "unregistered-policy-v1")
    outcome = compare_requirement(
        CompareInputs(req, pid, mode, candidate or SideEvidence(), target or SideEvidence(), verification), config
    )
    assert outcome.confidence in ("MEDIUM", "LOW")  # never HIGH without quantified uncertainty, never UNASSESSED
    assert [g.gate_id for g in outcome.gates] == list(GATE_ORDER)  # SC-02..SC-11, SC-13
    assert all(g.reason for g in outcome.gates)
    return outcome


def slope_side(value: float | None, *, scale: float | None = 60.0, valid: float = 1.0, **kw: object) -> SideEvidence:
    return SideEvidence((handle(metric("slope_area_fraction:12-18", value, scale=scale, valid=valid), **kw),))  # type: ignore[arg-type]


def verification_side(*metrics: MeasuredMetric, analysis_scale: float | None = 60.0) -> SideEvidence:
    handles = [handle(kind="VERIFICATION", algorithm_id="verify-route", scale=60.0)]
    if analysis_scale is not None:
        handles.append(handle(algorithm_id="analyze-candidate", scale=analysis_scale))
    return SideEvidence(tuple(handles))


def summary(
    outcome: str = "PASS",
    category: str | None = None,
    codes: tuple[str, ...] = (),
    metrics: tuple[MeasuredMetric, ...] = (),
) -> VerificationSummary:
    return VerificationSummary(
        outcome=outcome, failure_category=category, violation_codes=list(codes), metrics=list(metrics)
    )  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- R-SLOPE-AVAILABILITY
def test_slope_band_pass_fail_and_inclusive_boundary() -> None:
    ok = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08))
    assert (ok.status, ok.reason_code, ok.evaluation_stage, ok.confidence) == (
        "PASS",
        "MEETS_CRITERION",
        "FINAL",
        "MEDIUM",
    )
    assert ok.measured_value == 0.08 and ok.measured_unit == "fraction" and ok.comparison_scale_m == 60.0
    assert (ok.threshold_lower, ok.threshold_upper) == (0.05, None) and ok.covered_subcriteria == (
        "slope_area_fraction:12-18",
    )
    fail = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.04))
    assert (fail.status, fail.reason_code) == ("FAIL", "INSUFFICIENT_EXPOSURE") and fail.uncovered_subcriteria
    assert run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.05)).status == "PASS"  # thresholds are inclusive
    assert run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.0499999)).status == "FAIL"  # one hair below flips it
    zero = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.0))
    assert zero.status == "FAIL" and zero.measured_value == 0.0  # a real measured zero is a FAIL, not unknown


def test_slope_band_unknown_values_are_never_zero() -> None:
    for side in (SideEvidence(), slope_side(None)):
        out = run("R-SLOPE-AVAILABILITY", candidate=side)
        assert (out.status, out.reason_code) == ("UNKNOWN", "EARTH_EVIDENCE_MISSING")
        assert out.measured_value is None and out.measured_unit is None and out.comparison_scale_m is None
        assert out.confidence == "LOW"


def test_slope_band_scale_coverage_and_confidence_rubric() -> None:
    coarse = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, scale=480.0))  # window is <= 60 m
    assert (coarse.status, coarse.reason_code) == (
        "UNKNOWN",
        "SCALE_UNSUPPORTED",
    ) and coarse.comparison_scale_m == 480.0
    assert [g.outcome for g in coarse.gates if g.gate_id == "SC-04"] == ["UNSATISFIED"]
    assert run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, scale=None)).reason_code == "METADATA_INCOMPLETE"
    thin = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, valid=0.79))
    assert (thin.status, thin.reason_code) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA")
    assert thin.measured_value is None  # an undecidable row does not report a number as if decided
    edge = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, valid=0.80))
    assert edge.status == "PASS" and edge.confidence == "LOW"  # coverage 0.80..0.90 -> LOW
    assert run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, valid=0.90)).confidence == "MEDIUM"


def test_slope_band_metadata_consistency_failures() -> None:
    live = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, mode="live"), mode="synthetic")
    assert (live.status, live.reason_code) == ("UNKNOWN", "METADATA_INCOMPLETE") and "mode" in live.explanation
    mars = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.5, body="MARS"))
    assert mars.reason_code == "METADATA_INCOMPLETE"
    assert [g.outcome for g in mars.gates if g.gate_id == "SC-03"] == ["UNSATISFIED"]
    wrong_unit = REQ["R-SLOPE-AVAILABILITY"].model_copy(update={"unit": "percent"})
    assert run("x", candidate=slope_side(0.5), requirement=wrong_unit).reason_code == "METADATA_INCOMPLETE"


def test_slope_band_underspecified_requirements() -> None:
    base = REQ["R-SLOPE-AVAILABILITY"]
    no_band = base.model_copy(update={"parameters": base.parameters.model_copy(update={"slope_band_deg": None})})
    inverted = base.model_copy(
        update={"parameters": base.parameters.model_copy(update={"slope_band_deg": [18.0, 12.0]})}
    )
    no_threshold = base.model_copy(update={"lower": None})
    lte = base.model_copy(update={"operator": "LTE", "upper": 0.3})
    for req in (no_band, inverted, no_threshold, lte):
        out = run("x", candidate=slope_side(0.5), requirement=req)
        assert (out.status, out.reason_code) == ("UNKNOWN", "REQUIREMENT_UNDERSPECIFIED")


def test_thresholds_come_from_the_versioned_policy_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(Path(__file__).resolve().parents[3] / "config", config_dir)
    text = (config_dir / "algorithms.yaml").read_text()
    assert text.count("min_valid_fraction: 0.80") >= 1
    (config_dir / "algorithms.yaml").write_text(text.replace("min_valid_fraction: 0.80", "min_valid_fraction: 0.99"))
    strict = load_config(config_dir)
    assert strict.algorithm_config_sha256 != CONFIG.algorithm_config_sha256
    assert strict.policy_sha256("slope-band-area-fraction-v1") != CONFIG.policy_sha256("slope-band-area-fraction-v1")
    side = slope_side(0.5, valid=0.95)
    assert run("R-SLOPE-AVAILABILITY", candidate=side).status == "PASS"
    changed = run("R-SLOPE-AVAILABILITY", candidate=side, config=strict)
    assert (changed.status, changed.reason_code) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA")
    assert changed.policy_sha256 == strict.policy_sha256("slope-band-area-fraction-v1")


# ----------------------------------------------------------------------------- R-TARGET-SLOPE-CONTEXT (W1)
def w1_sides(
    target: Histogram | None, candidate: Histogram | None, valid: float = 1.0
) -> tuple[SideEvidence, SideEvidence]:
    cand = SideEvidence((handle(metric("valid_fraction", valid, scale=480.0, valid=valid)),), candidate)
    tgt = SideEvidence((handle(body="MARS", algorithm_id="characterize-target"),), target)
    return cand, tgt


def test_w1_recomputed_at_the_common_support_with_independent_oracle() -> None:
    cand, tgt = w1_sides(point(3, 480.0), point(4, 480.0))  # masses at 10 deg and 13.5 deg
    out = run("R-TARGET-SLOPE-CONTEXT", candidate=cand, target=tgt)
    assert out.measured_value == pytest.approx(3.5, abs=1e-12) and out.measured_unit == "deg"
    assert (out.status, out.reason_code, out.comparison_scale_m) == ("PASS", "MEETS_CRITERION", 480.0)
    assert out.metrics[0].metric_id == "slope_w1_deg" and out.metrics[0].unit == "deg"
    assert out.metrics[0].value == pytest.approx(wasserstein_distance([10.0], [13.5]), abs=1e-9)
    far = run("R-TARGET-SLOPE-CONTEXT", candidate=w1_sides(point(3, 480.0), point(5, 480.0))[0], target=tgt)
    assert far.measured_value == pytest.approx(6.5) and (far.status, far.reason_code) == (
        "FAIL",
        "DISTRIBUTION_MISMATCH",
    )


def test_w1_matches_scipy_on_random_distributions_and_nonuniform_bins() -> None:
    rng = np.random.default_rng(11)
    for _ in range(25):
        a = rng.dirichlet(np.ones(9))
        b = rng.dirichlet(np.ones(9))
        ours = binned_w1(a, b, SLOPE_HIST_CENTRES)
        assert ours == pytest.approx(wasserstein_distance(SLOPE_HIST_CENTRES, SLOPE_HIST_CENTRES, a, b), abs=1e-9)
        assert ours == pytest.approx(empirical_w1(SLOPE_HIST_CENTRES, a, SLOPE_HIST_CENTRES, b), abs=1e-9)
        assert binned_w1(a, a, SLOPE_HIST_CENTRES) == 0.0
        assert ours == pytest.approx(binned_w1(b, a, SLOPE_HIST_CENTRES), abs=1e-12)  # symmetric
    # all mass moved by a known angle: bin centre 1 deg -> 62.5 deg = 61.5 deg
    assert binned_w1(point(0, 1).area_fraction, point(8, 1).area_fraction, SLOPE_HIST_CENTRES) == pytest.approx(61.5)


def test_w1_is_area_weighted_end_to_end_from_slope_rasters() -> None:
    slopes = np.array([[3.0, 3.0], [14.0, 22.0]])
    ones = np.ones((2, 2), dtype=bool)
    uniform = area_weighted_histogram(slopes, ones, 3600.0)
    heavy = area_weighted_histogram(slopes, ones, np.array([[1.0, 1.0], [1.0, 97.0]]))
    a = Histogram(**{**_as_kwargs(uniform), "support_scale_m": 480.0})
    b = Histogram(**{**_as_kwargs(heavy), "support_scale_m": 480.0})
    result = w1_from_histograms(a, b)
    assert isinstance(result, W1Result) and result.w1_deg > 0
    assert result.w1_deg == pytest.approx(
        wasserstein_distance(SLOPE_HIST_CENTRES, SLOPE_HIST_CENTRES, a.area_fraction, b.area_fraction), abs=1e-9
    )
    assert b.area_fraction[6] == pytest.approx(0.97)  # the 22 deg cell dominates by area, not by cell count
    assert w1_from_histograms(a, a).w1_deg == 0.0


def _as_kwargs(h: object) -> dict[str, object]:
    data = h  # HistogramData
    return {
        "metric_id": "surface_slope_deg",
        "unit": "deg",
        "edges": list(data.edges),  # type: ignore[attr-defined]
        "area_fraction": list(data.area_fraction),  # type: ignore[attr-defined]
        "valid_area_m2": data.valid_area_m2,  # type: ignore[attr-defined]
    }


def test_w1_boundary_is_inclusive_and_perturbation_flips_it() -> None:
    req = REQ["R-TARGET-SLOPE-CONTEXT"].model_copy(update={"upper": 6.5})
    cand, tgt = w1_sides(point(3, 480.0), point(5, 480.0))
    assert run("x", candidate=cand, target=tgt, requirement=req).status == "PASS"  # 6.5 <= 6.5
    tighter = req.model_copy(update={"upper": 6.4999})
    assert run("x", candidate=cand, target=tgt, requirement=tighter).status == "FAIL"
    # PERT-05: shifting the target histogram (all area to 22 deg) flips the context row
    shifted = run(
        "R-TARGET-SLOPE-CONTEXT",
        candidate=w1_sides(point(3, 480.0), point(3, 480.0))[0],
        target=SideEvidence(tgt.handles, point(7, 480.0)),
    )
    unshifted = run(
        "R-TARGET-SLOPE-CONTEXT",
        candidate=w1_sides(point(3, 480.0), point(3, 480.0))[0],
        target=SideEvidence(tgt.handles, point(3, 480.0)),
    )
    assert (unshifted.status, shifted.status) == ("PASS", "FAIL")


def test_w1_missing_evidence_scale_and_coverage_paths() -> None:
    cand, tgt = w1_sides(point(3, 480.0), point(3, 480.0))
    assert (
        run("R-TARGET-SLOPE-CONTEXT", candidate=cand, target=SideEvidence(tgt.handles, None)).reason_code
        == "TARGET_EVIDENCE_MISSING"
    )
    assert (
        run("R-TARGET-SLOPE-CONTEXT", candidate=SideEvidence(cand.handles, None), target=tgt).reason_code
        == "EARTH_EVIDENCE_MISSING"
    )
    # the seeded scale defect: 60 m Earth evidence cited for a 480-1000 m context requirement
    c60, t480 = w1_sides(point(3, 480.0), point(3, 60.0))
    defect = run("R-TARGET-SLOPE-CONTEXT", candidate=c60, target=t480)
    assert (defect.status, defect.reason_code, defect.comparison_scale_m) == ("UNKNOWN", "SCALE_UNSUPPORTED", 60.0)
    c1500, t1500 = w1_sides(point(3, 1500.0), point(3, 1500.0))
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=c1500, target=t1500).reason_code == "SCALE_UNSUPPORTED"
    mismatch_c, mismatch_t = w1_sides(point(3, 480.0), point(3, 960.0))
    assert (
        run("R-TARGET-SLOPE-CONTEXT", candidate=mismatch_c, target=mismatch_t).reason_code == "SCALE_UNSUPPORTED"
    )  # not a common support
    no_cov = SideEvidence((handle(),), point(3, 480.0))
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=no_cov, target=tgt).reason_code == "METADATA_INCOMPLETE"
    low_cov, _ = w1_sides(point(3, 480.0), point(3, 480.0), valid=0.5)
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=low_cov, target=tgt).reason_code == "INSUFFICIENT_VALID_DATA"
    empty = hist([0.0] * 9, 480.0, area=0.0)
    assert (
        run("R-TARGET-SLOPE-CONTEXT", candidate=SideEvidence(cand.handles, empty), target=tgt).reason_code
        == "INSUFFICIENT_VALID_DATA"
    )
    other_edges = Histogram(
        metric_id="s",
        unit="deg",
        edges=[0.0, 45.0, 90.0],
        area_fraction=[0.5, 0.5],
        valid_area_m2=1.0,
        support_scale_m=480.0,
    )
    assert (
        run("R-TARGET-SLOPE-CONTEXT", candidate=SideEvidence(cand.handles, other_edges), target=tgt).reason_code
        == "METADATA_INCOMPLETE"
    )
    with pytest.raises(ScaleError):
        w1_from_histograms(point(3, 480.0), point(3, 960.0))
    with pytest.raises(RasterError):
        w1_from_histograms(point(3, 480.0), other_edges.model_copy(update={"support_scale_m": 480.0}))
    with pytest.raises(RasterError):
        binned_w1([0.5, 0.4], [0.5, 0.5], [1.0, 2.0])  # does not sum to one: a missing distribution is unknown
    with pytest.raises(RasterError):
        binned_w1([0.5, 0.5], [0.5, 0.5], [2.0, 1.0])


# ----------------------------------------------------------------------------- route-dependent rows
def test_route_rows_are_preliminary_until_a_verification_is_supplied() -> None:
    for rid in ("R-EXPOSURE", "R-TASKS", "R-RESERVE"):
        prelim = run(rid, candidate=verification_side(analysis_scale=60.0))
        assert (prelim.status, prelim.reason_code, prelim.evaluation_stage) == (
            "UNKNOWN",
            "ROUTE_NOT_VERIFIED",
            "PRELIMINARY",
        )
        assert prelim.measured_value is None and prelim.confidence == "LOW"
        sc11 = next(g for g in prelim.gates if g.gate_id == "SC-11")
        assert sc11.outcome == "NOT_ASSESSED"


def test_exposure_row_follows_the_verifiers_measurement() -> None:
    cand = verification_side()
    exposure = lambda v: metric("unique_exposure_m:R-EXPOSURE", v, unit="m")  # noqa: E731
    ok = run("R-EXPOSURE", candidate=cand, verification=summary("PASS", metrics=(exposure(150.0),)))
    assert (ok.status, ok.reason_code, ok.evaluation_stage, ok.measured_value, ok.measured_unit) == (
        "PASS",
        "ROUTE_VERIFIED",
        "FINAL",
        150.0,
        "m",
    )
    assert next(g for g in ok.gates if g.gate_id == "SC-11").outcome == "SATISFIED" and ok.validation_level == "S1"
    assert run("R-EXPOSURE", candidate=cand, verification=summary("PASS", metrics=(exposure(100.0),))).status == "PASS"
    short = run("R-EXPOSURE", candidate=cand, verification=summary("PASS", metrics=(exposure(99.999),)))
    assert (short.status, short.reason_code) == ("FAIL", "ROUTE_FAILED")
    fail = run(
        "R-EXPOSURE", candidate=cand, verification=summary("FAIL", "ROUTE", ("EXPOSURE_SHORTFALL",), (exposure(0.0),))
    )
    assert (fail.status, fail.reason_code, fail.measured_value) == ("FAIL", "ROUTE_FAILED", 0.0)
    # a violation code overrides a (suspiciously) passing metric: the row cannot be PASS
    contradicted = run(
        "R-EXPOSURE", candidate=cand, verification=summary("FAIL", "ROUTE", ("EXPOSURE_SHORTFALL",), (exposure(150.0),))
    )
    assert contradicted.status == "FAIL"
    # infeasible diagnosis (no route exists): named exposure row fails with INSUFFICIENT_EXPOSURE
    infeasible = run("R-EXPOSURE", candidate=cand, verification=summary("FAIL", "ANALOG", ("EXPOSURE_SHORTFALL",)))
    assert (infeasible.status, infeasible.reason_code) == ("FAIL", "INSUFFICIENT_EXPOSURE")
    # another row of the same attempt is not failed by this attempt's exposure violation
    other = run("R-TASKS", candidate=cand, verification=summary("FAIL", "ANALOG", ("EXPOSURE_SHORTFALL",)))
    assert (other.status, other.reason_code) == ("UNKNOWN", "ROUTE_NOT_VERIFIED") and other.evaluation_stage == "FINAL"


def test_tasks_and_reserve_rows() -> None:
    cand = verification_side()
    tasks = lambda v: metric("tasks_completed", v, unit="count")  # noqa: E731
    assert run("R-TASKS", candidate=cand, verification=summary("PASS", metrics=(tasks(2.0),))).status == "PASS"
    assert (
        run(
            "R-TASKS", candidate=cand, verification=summary("FAIL", "ROUTE", ("WAYPOINT_MISSED",), (tasks(1.0),))
        ).status
        == "FAIL"
    )
    reserve = lambda v, kind="ASSUMED": metric("reserve_pct", v, unit="percent", kind=kind)  # noqa: E731
    ok = run("R-RESERVE", candidate=cand, verification=summary("PASS", metrics=(reserve(98.3),)))
    assert (ok.status, ok.reason_code, ok.measured_unit) == ("PASS", "ROUTE_VERIFIED", "percent")
    assert ok.confidence == "LOW"  # assumed (uncalibrated) energy parameters can never raise confidence
    calibrated = run("R-RESERVE", candidate=cand, verification=summary("PASS", metrics=(reserve(98.3, "DERIVED"),)))
    assert calibrated.confidence == "MEDIUM"
    assert (
        run("R-RESERVE", candidate=cand, verification=summary("PASS", metrics=(reserve(20.0),))).status == "PASS"
    )  # exact equality passes
    low = run(
        "R-RESERVE",
        candidate=cand,
        verification=summary("FAIL", "ROUTE", ("ENERGY_RESERVE_SHORTFALL",), (reserve(-4.0),)),
    )
    assert low.status == "FAIL" and low.measured_value == -4.0  # negative reserve is reported, not clamped
    unknown_energy = run(
        "R-RESERVE", candidate=cand, verification=summary("INCONCLUSIVE", "DATA", (), (reserve(None),))
    )
    assert (unknown_energy.status, unknown_energy.reason_code) == (
        "UNKNOWN",
        "ENERGY_MODEL_MISSING",
    ) and unknown_energy.measured_value is None
    no_metric = run("R-RESERVE", candidate=cand, verification=summary("INCONCLUSIVE", "DATA"))
    assert no_metric.reason_code == "ENERGY_MODEL_MISSING"


def test_route_rows_reject_untrusted_or_inconclusive_verification() -> None:
    exposure = metric("unique_exposure_m:R-EXPOSURE", 500.0, unit="m")
    # the verification evidence handle must be among the candidate evidence ids
    without_handle = run(
        "R-EXPOSURE",
        candidate=SideEvidence((handle(algorithm_id="analyze-candidate", scale=60.0),)),
        verification=summary("PASS", metrics=(exposure,)),
    )
    assert (without_handle.status, without_handle.reason_code, without_handle.evaluation_stage) == (
        "UNKNOWN",
        "METADATA_INCOMPLETE",
        "FINAL",
    )
    for category in ("SEARCH_LIMIT", "SYSTEM"):
        inconclusive = run(
            "R-EXPOSURE", candidate=verification_side(), verification=summary("INCONCLUSIVE", category, (), (exposure,))
        )
        assert (inconclusive.status, inconclusive.reason_code) == ("UNKNOWN", "ROUTE_NOT_VERIFIED")
    coarse = run(
        "R-EXPOSURE",
        candidate=verification_side(analysis_scale=480.0),
        verification=summary("PASS", metrics=(exposure,)),
    )
    assert (coarse.status, coarse.reason_code) == (
        "UNKNOWN",
        "SCALE_UNSUPPORTED",
    )  # a 60 m route claim needs 60 m support
    assert (
        run("R-EXPOSURE", candidate=verification_side(), verification=summary("PASS")).reason_code
        == "ROUTE_NOT_VERIFIED"
    )  # nothing about this row
    lte = REQ["R-EXPOSURE"].model_copy(update={"operator": "LTE", "upper": 10.0, "lower": None})
    assert (
        run("x", candidate=verification_side(), requirement=lte, policy_id="route-exposure-v1").reason_code
        == "REQUIREMENT_UNDERSPECIFIED"
    )
    live_handle = SideEvidence((handle(kind="VERIFICATION", algorithm_id="verify-route", mode="live"),))
    assert (
        run("R-EXPOSURE", candidate=live_handle, verification=summary("PASS", metrics=(exposure,))).reason_code
        == "METADATA_INCOMPLETE"
    )


def test_route_verified_in_live_mode_reaches_s4_only_with_independent_verification() -> None:
    exposure = metric("unique_exposure_m:R-EXPOSURE", 150.0, unit="m")
    live = SideEvidence(
        (
            handle(kind="VERIFICATION", algorithm_id="verify-route", mode="live", scale=60.0),
            handle(mode="live", scale=60.0),
        )
    )
    out = run("R-EXPOSURE", candidate=live, verification=summary("PASS", metrics=(exposure,)), mode="live")
    assert out.status == "PASS" and out.validation_level == "S4"
    search_only = SideEvidence((handle(algorithm_id="search-route", mode="live"),))
    weaker = run("R-EXPOSURE", candidate=search_only, verification=summary("PASS", metrics=(exposure,)), mode="live")
    # without an independent VERIFICATION handle a passing metric earns nothing (review defect: it used to PASS at S3)
    assert (weaker.status, weaker.reason_code) == ("UNKNOWN", "ROUTE_NOT_VERIFIED")
    assert next(g for g in weaker.gates if g.gate_id == "SC-11").outcome == "NOT_ASSESSED"
    assert weaker.validation_level == "S2" and weaker.confidence == "LOW" and weaker.measured_value is None


# ----------------------------------------------------------------------------- optional layers and scale-only rows
def test_mineral_presence_never_decides() -> None:
    earth = SideEvidence((handle(metric("mineral_valid_fraction", 0.6, scale=60.0, valid=0.6)),))
    target = SideEvidence((handle(metric("mineral_valid_fraction", 0.9, scale=480.0), body="MARS"),))
    assert run("R-MINERAL").reason_code == "EARTH_EVIDENCE_MISSING"
    assert run("R-MINERAL", target=target).reason_code == "EARTH_EVIDENCE_MISSING"  # PERT-07: Earth binding removed
    local = run("R-MINERAL", candidate=earth)
    assert (local.status, local.reason_code) == ("UNKNOWN", "TARGET_EVIDENCE_MISSING")
    both = run("R-MINERAL", candidate=earth, target=target)
    assert (both.status, both.reason_code) == (
        "UNKNOWN",
        "THRESHOLD_UNRESOLVED",
    )  # low retrieval coverage is not an absence claim
    unknown_value = SideEvidence((handle(metric("mineral_valid_fraction", None)),))
    assert run("R-MINERAL", candidate=unknown_value, target=target).reason_code == "EARTH_EVIDENCE_MISSING"


def test_thermal_row_stays_unknown_even_with_a_target_thermal_metric() -> None:
    target = SideEvidence((handle(metric("min_temperature_k", 88.0, unit="K", scale=960.0), body="MOON"),))
    out = run("R-THERMAL", target=target)
    assert (out.status, out.reason_code) == ("UNKNOWN", "EARTH_EVIDENCE_MISSING") and out.limitations
    earth = SideEvidence((handle(metric("min_temperature_k", 250.0, unit="K")),))
    assert run("R-THERMAL", candidate=earth, target=target).reason_code == "THRESHOLD_UNRESOLVED"
    sc06 = next(g for g in out.gates if g.gate_id == "SC-06")
    assert sc06.outcome == "NOT_ASSESSED"
    wrong_body = SideEvidence((handle(metric("min_temperature_k", 88.0, unit="K"), body="MARS"),))
    assert (
        run("R-THERMAL", target=wrong_body).reason_code == "METADATA_INCOMPLETE"
    )  # thermal policy is not defined for Mars


def test_clearance_is_unsupported_for_terrain_model_support() -> None:
    cand = SideEvidence((handle(metric("detrended_rms_height_m@180", 0.0, unit="m", scale=60.0), scale=60.0),))
    out = run("R-CLEARANCE", candidate=cand)
    assert (out.status, out.reason_code, out.comparison_scale_m) == ("UNKNOWN", "SCALE_UNSUPPORTED", 60.0)
    both = SideEvidence((handle(scale=60.0), handle(scale=480.0)))
    assert run("R-CLEARANCE", candidate=both).comparison_scale_m == 60.0  # the finest available support is reported
    fine = SideEvidence((handle(scale=0.01),))
    assert (
        run("R-CLEARANCE", candidate=fine).reason_code == "THRESHOLD_UNRESOLVED"
    )  # even fine support has no rule in v1
    assert run("R-CLEARANCE").reason_code == "EARTH_EVIDENCE_MISSING"
    open_window = REQ["R-CLEARANCE"].model_copy(update={"maximum_support_scale_m": None})
    assert (
        run("x", candidate=cand, requirement=open_window, policy_id="clearance-scale-v1").reason_code
        == "REQUIREMENT_UNDERSPECIFIED"
    )
    # perturbation: loosening the window to 100 m flips SCALE_UNSUPPORTED to an evaluable (but unresolved) row
    loose = REQ["R-CLEARANCE"].model_copy(update={"maximum_support_scale_m": 100.0})
    assert (
        run("x", candidate=cand, requirement=loose, policy_id="clearance-scale-v1").reason_code
        == "THRESHOLD_UNRESOLVED"
    )


def test_physical_gap_rows() -> None:
    for rid in ("R-GRAVITY", "R-ATMOSPHERE", "R-VACUUM"):
        out = run(rid, candidate=slope_side(0.9))
        assert (out.status, out.reason_code, out.evaluation_stage) == ("GAP", "PHYSICAL_GAP", "FINAL")
        assert out.measured_value is None and out.confidence == "LOW" and out.limitations
        outcomes = {g.gate_id: g.outcome for g in out.gates}
        assert (
            outcomes["SC-02"] == "NOT_APPLICABLE"
            and outcomes["SC-08"] == "NOT_APPLICABLE"
            and outcomes["SC-03"] == "SATISFIED"
        )
        assert out.validation_level == "S0"
    # the operator, not the policy id or the evidence, makes it a gap
    forced = run("x", requirement=REQ["R-GRAVITY"], policy_id="no-such-policy-v1")
    assert forced.status == "GAP"
    # perturbation: the same observable with a measurable operator is no longer a gap
    measurable = REQ["R-GRAVITY"].model_copy(update={"operator": "GTE", "lower": 3.0})
    assert run("x", requirement=measurable, policy_id="physical-gap-v1").reason_code == "REQUIREMENT_UNDERSPECIFIED"


# ----------------------------------------------------------------------------- dispatch, receipt, payload
def test_dispatch_failures_are_underspecified_not_guessed() -> None:
    odd = REQ["R-SLOPE-AVAILABILITY"].model_copy(update={"observable": "bearing_strength_kpa"})
    out = run("x", candidate=slope_side(0.9), requirement=odd, policy_id="slope-band-area-fraction-v1")
    assert (out.status, out.reason_code) == ("UNKNOWN", "REQUIREMENT_UNDERSPECIFIED")
    mismatch = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.9), policy_id="slope-w1-common-support-v1")
    assert (
        mismatch.reason_code == "REQUIREMENT_UNDERSPECIFIED" and "slope-band-area-fraction-v1" in mismatch.explanation
    )
    unknown_policy = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.9), policy_id="made-up-v9")
    assert unknown_policy.reason_code == "REQUIREMENT_UNDERSPECIFIED"
    assert {g.outcome for g in unknown_policy.gates} == {"NOT_ASSESSED"}
    assert unknown_policy.policy_sha256 != CONFIG.policy_sha256("slope-band-area-fraction-v1")


def test_every_catalog_policy_exists_and_hashes_are_stable_and_distinct() -> None:
    ids = sorted(set(catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.values()))
    hashes = {pid: CONFIG.policy_sha256(pid) for pid in ids}
    assert all(h is not None and len(h) == 64 for h in hashes.values()) and len(set(hashes.values())) == len(ids)
    assert hashes == {pid: CONFIG.policy_sha256(pid) for pid in ids}
    assert CONFIG.policy_sha256("nope") is None and CONFIG.policy("nope") is None


def test_adequacy_receipt_gate_semantics_for_a_numeric_row() -> None:
    cand = slope_side(0.08)
    out = run("R-SLOPE-AVAILABILITY", candidate=cand)
    gates = {g.gate_id: g for g in out.gates}
    ids = {EvidenceRef(evidence_id=h.evidence_id) for h in cand.handles}
    for gid in ("SC-02", "SC-03", "SC-04", "SC-05", "SC-07", "SC-08", "SC-09"):
        assert gates[gid].outcome == "SATISFIED", gid
    assert "uncertainty not quantified" in gates["SC-08"].reason and "nominal" in gates["SC-08"].reason
    assert set(gates["SC-02"].evidence) == ids and gates["SC-07"].evidence == []
    for gid in ("SC-06", "SC-10", "SC-11", "SC-13"):
        assert gates[gid].outcome == "NOT_APPLICABLE" and len(gates[gid].reason) > 20
    assert out.validation_level == "S1"
    # derived evidence without an artifact hash breaks source integrity
    no_artifact = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08, artifact=False))
    assert next(g for g in no_artifact.gates if g.gate_id == "SC-02").outcome == "UNSATISFIED"


def test_validation_level_tracks_mode_and_evidence() -> None:
    live = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08, mode="live"), mode="live")
    assert live.validation_level == "S3"
    unknown = run("R-SLOPE-AVAILABILITY", candidate=slope_side(None, mode="live"), mode="live")
    assert unknown.validation_level == "S2"
    assert run("R-SLOPE-AVAILABILITY", candidate=SideEvidence()).validation_level == "S0"


def test_payload_roundtrips_through_the_kit_model() -> None:
    out = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08))
    payload = out.to_payload(EvidenceRef(local_key="cmp-R-SLOPE-AVAILABILITY"))
    assert isinstance(payload, CompareRequirementPayload)
    parsed = CompareRequirementPayload.model_validate_json(payload.model_dump_json())
    assert parsed == payload and parsed.proposed_status == "PASS" and parsed.reason_code == "MEETS_CRITERION"
    assert [g.gate_id for g in parsed.adequacy.gates] == list(
        GATE_ORDER
    ) and parsed.adequacy.observable_policy_id == "slope-band-area-fraction-v1"
    assert parsed.adequacy.policy_sha256 == CONFIG.policy_sha256("slope-band-area-fraction-v1")
    assert parsed.threshold_lower == 0.05 and parsed.comparison_evidence.local_key == "cmp-R-SLOPE-AVAILABILITY"


def test_comparison_is_deterministic_and_independent_of_handle_order() -> None:
    h1 = handle(metric("slope_area_fraction:12-18", 0.08), metric("valid_fraction", 1.0))
    h2 = handle(metric("other", 1.0))
    a = run("R-SLOPE-AVAILABILITY", candidate=SideEvidence((h1, h2)))
    b = run("R-SLOPE-AVAILABILITY", candidate=SideEvidence((h2, h1)))
    c = run("R-SLOPE-AVAILABILITY", candidate=SideEvidence((h1, h2)))
    assert a == c and a.gates == b.gates and a.consulted_evidence_ids == b.consulted_evidence_ids
    assert isinstance(a.consulted_evidence_ids[0], UUID)


def test_truth_table_of_architecture_40_s5_rows_before_prove_it() -> None:
    """Qualification truth table, preliminary stage: rows are computed from the evidence supplied for each site."""
    sites = {
        "feasible": 0.10,  # f_band within [0.07, 0.15]
        "mesa": 0.40,
        "rolling": 0.03,
        "flat_control": 0.0,
    }
    expected = {"feasible": "PASS", "mesa": "PASS", "rolling": "FAIL", "flat_control": "FAIL"}
    for name, fraction in sites.items():
        availability = run("R-SLOPE-AVAILABILITY", candidate=slope_side(fraction))
        assert availability.status == expected[name], name
        assert run("R-EXPOSURE", candidate=verification_side()).evaluation_stage == "PRELIMINARY"
        assert run("R-CLEARANCE", candidate=slope_side(fraction)).reason_code == "SCALE_UNSUPPORTED"
        assert run("R-GRAVITY", candidate=slope_side(fraction)).status == "GAP"


# ----------------------------------------------------------------------------- review defect 3: route-row credit
@pytest.mark.parametrize("category", ["DATA", "SYSTEM", "SEARCH_LIMIT", "REQUIREMENT", "ROUTE", "ROVER", "ANALOG"])
@pytest.mark.parametrize("rid", ["R-EXPOSURE", "R-TASKS"])
def test_inconclusive_verification_never_credits_a_route_row(rid: str, category: str) -> None:
    mid = "unique_exposure_m:R-EXPOSURE" if rid == "R-EXPOSURE" else "tasks_completed"
    good = metric(mid, 500.0, unit="m")
    out = run(rid, candidate=verification_side(), verification=summary("INCONCLUSIVE", category, (), (good,)))
    assert (out.status, out.reason_code) == ("UNKNOWN", "ROUTE_NOT_VERIFIED")
    assert out.confidence == "LOW" and out.measured_value is None and out.validation_level != "S4"


def test_route_row_needs_an_independent_verification_handle_and_sc11_agrees() -> None:
    exposure = metric("unique_exposure_m:R-EXPOSURE", 500.0, unit="m")
    for algo in ("search-route", "diagnose-result", "verify-route"):
        side = SideEvidence((handle(kind="DERIVED", algorithm_id=algo, scale=60.0), handle(scale=60.0)))
        out = run("R-EXPOSURE", candidate=side, verification=summary("PASS", metrics=(exposure,)))
        assert (out.status, out.reason_code, out.confidence) == ("UNKNOWN", "ROUTE_NOT_VERIFIED", "LOW"), algo
        assert next(g for g in out.gates if g.gate_id == "SC-11").outcome == "NOT_ASSESSED"
    ok = run("R-EXPOSURE", candidate=verification_side(), verification=summary("PASS", metrics=(exposure,)))
    assert (ok.status, ok.reason_code) == ("PASS", "ROUTE_VERIFIED")
    assert next(g for g in ok.gates if g.gate_id == "SC-11").outcome == "SATISFIED"


def test_unknown_terrain_violation_blocks_credit_for_every_row() -> None:
    exposure = metric("unique_exposure_m:R-EXPOSURE", 500.0, unit="m")
    for outcome, codes in (("FAIL", ("UNKNOWN_TERRAIN", "WAYPOINT_MISSED")), ("PASS", ("UNKNOWN_TERRAIN",))):
        out = run(
            "R-EXPOSURE", candidate=verification_side(), verification=summary(outcome, "ROUTE", codes, (exposure,))
        )
        assert out.status != "PASS" and out.reason_code != "ROUTE_VERIFIED" and out.confidence == "LOW", codes


def test_row_credit_after_an_overall_fail_only_for_row_scoped_violations() -> None:
    """Spec (40 section 5): a failed exposure keeps tasks/reserve credit; a route-invalidating violation does not."""
    tasks = metric("tasks_completed", 2.0, unit="count")
    cand = verification_side()
    shortfall = run("R-TASKS", candidate=cand, verification=summary("FAIL", "ROUTE", ("EXPOSURE_SHORTFALL",), (tasks,)))
    assert (shortfall.status, shortfall.reason_code) == ("PASS", "ROUTE_VERIFIED")  # unrelated row keeps its credit
    for code in ("MAX_SLOPE_EXCEEDED", "FORBIDDEN_INTERSECTION", "DISCONTINUOUS_ROUTE", "STALE_INPUT_HASH"):
        hard = run("R-TASKS", candidate=cand, verification=summary("FAIL", "ROUTE", (code,), (tasks,)))
        assert (hard.status, hard.reason_code) == ("FAIL", "ROUTE_FAILED"), code


# ------------------------------------------------------------------- review defects 1 and 5: W1 coverage gates
def test_w1_gates_on_the_coverage_actually_used_not_the_fine_scale_valid_fraction() -> None:
    cand, tgt = w1_sides(point(3, 480.0), point(3, 480.0), valid=0.97)  # fine-scale valid_fraction metric: 0.97
    used = lambda c: SideEvidence(cand.handles, cand.histogram, coverage=c)  # noqa: E731
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=used(None), target=tgt).status == "PASS"  # falls back to metric
    out = run("R-TARGET-SLOPE-CONTEXT", candidate=used(0.56), target=tgt)  # only 56 % of coarse cells were used
    assert (out.status, out.reason_code, out.measured_value) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA", None)
    assert out.confidence == "LOW"
    assert next(g for g in out.gates if g.gate_id == "SC-05").outcome == "UNSATISFIED"
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=used(0.8), target=tgt).status == "PASS"  # exactly the minimum
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=used(0.7999), target=tgt).status == "UNKNOWN"
    # the used coverage overrides a rosy metric in either direction
    low_metric, _ = w1_sides(point(3, 480.0), point(3, 480.0), valid=0.5)
    assert (
        run(
            "R-TARGET-SLOPE-CONTEXT",
            candidate=SideEvidence(low_metric.handles, low_metric.histogram, coverage=0.9),
            target=tgt,
        ).status
        == "PASS"
    )


def test_w1_also_checks_the_target_coverage() -> None:
    cand, _ = w1_sides(point(3, 480.0), point(3, 480.0))
    target_handle = lambda v: handle(  # noqa: E731
        metric("valid_fraction", v, scale=480.0, valid=v), body="MARS", algorithm_id="characterize-target"
    )
    ok = SideEvidence((target_handle(0.8),), point(3, 480.0))
    assert run("R-TARGET-SLOPE-CONTEXT", candidate=cand, target=ok).status == "PASS"  # equal to the minimum passes
    for v in (0.79, 0.3):
        low = SideEvidence((target_handle(v),), point(3, 480.0))
        out = run("R-TARGET-SLOPE-CONTEXT", candidate=cand, target=low)
        assert (out.status, out.reason_code, out.measured_value) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA", None)
        assert "Target" in out.explanation


# ----------------------------------------------------------------------------- review defect 7: conditional gates
def _gate_outcomes(out: ComparisonOutcome) -> dict[str, str]:
    return {g.gate_id: g.outcome for g in out.gates}


def test_sc08_needs_an_uncertainty_statement_on_the_decisive_metric() -> None:
    silent = metric("slope_area_fraction:12-18", 0.08, kind="ASSUMED").model_copy(update={"uncertainty_note": ""})
    out = run("R-SLOPE-AVAILABILITY", candidate=SideEvidence((handle(silent, scale=60.0),)))
    assert out.status == "PASS"
    assert _gate_outcomes(out)["SC-08"] == "UNSATISFIED"
    ok = run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08))
    assert _gate_outcomes(ok)["SC-08"] == "SATISFIED"


def test_sc07_follows_the_quantity_kinds_of_the_consulted_metrics() -> None:
    proxy = run(
        "R-SLOPE-AVAILABILITY",
        candidate=SideEvidence((handle(metric("slope_area_fraction:12-18", 0.08, kind="PROXY")),)),
    )
    assert _gate_outcomes(proxy)["SC-07"] == "UNSATISFIED"
    assumed_metric = metric("slope_area_fraction:12-18", 0.08, kind="ASSUMED")
    assumed = run("R-SLOPE-AVAILABILITY", candidate=SideEvidence((handle(assumed_metric),)))
    assert _gate_outcomes(assumed)["SC-07"] == "NOT_ASSESSED"
    accepted = SideEvidence((handle(assumed_metric), handle(kind="ASSUMPTION", algorithm_id="compare-requirement")))
    assert _gate_outcomes(run("R-SLOPE-AVAILABILITY", candidate=accepted))["SC-07"] == "SATISFIED"
    assert _gate_outcomes(run("R-SLOPE-AVAILABILITY", candidate=slope_side(0.08)))["SC-07"] == "SATISFIED"


def test_sc09_checks_versions_against_the_algorithm_lock() -> None:
    good = slope_side(0.08)
    assert _gate_outcomes(run("R-SLOPE-AVAILABILITY", candidate=good))["SC-09"] == "SATISFIED"
    stale = SideEvidence(tuple(h.model_copy(update={"algorithm_version": "0.0.1"}) for h in good.handles))
    assert _gate_outcomes(run("R-SLOPE-AVAILABILITY", candidate=stale))["SC-09"] == "UNSATISFIED"
    blank = SideEvidence(tuple(h.model_copy(update={"algorithm_version": " "}) for h in good.handles))
    assert _gate_outcomes(run("R-SLOPE-AVAILABILITY", candidate=blank))["SC-09"] == "UNSATISFIED"


def test_assumed_verifier_metric_without_uncertainty_is_not_a_clean_route_row() -> None:
    """Review repro g2: an ASSUMED reserve with an empty uncertainty note PASSed with SC-07/SC-08 SATISFIED."""
    bad = metric("reserve_pct", 30.0, unit="percent", kind="ASSUMED").model_copy(update={"uncertainty_note": ""})
    out = run("R-RESERVE", candidate=verification_side(), verification=summary("PASS", metrics=(bad,)))
    assert (out.status, out.reason_code) == ("PASS", "ROUTE_VERIFIED") and out.confidence == "LOW"
    assert _gate_outcomes(out)["SC-07"] == "NOT_ASSESSED"
    assert _gate_outcomes(out)["SC-08"] == "UNSATISFIED"
