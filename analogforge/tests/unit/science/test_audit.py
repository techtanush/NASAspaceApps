"""AUDIT_EVIDENCE gate evidence SC-02..SC-11 and SC-13: each gate can pass and fail on computed inputs."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import AuditEvidenceInput, AuditEvidencePayload, ClaimScope
from analogforge.science.audit import (
    AUDIT_GATES,
    DiscoveryEvidence,
    audit_evidence,
)
from analogforge.science.config import load_config

CFG = load_config()
H64 = "a" * 64
ALL_CHECKS = ["provenance", "units", "crs", "scale", "coverage", "uncertainty", "proxies", "independence"]


def requirement(
    observable: str = "slope_distribution_w1_deg", lo: float | None = 480.0, hi: float | None = None
) -> Requirement:
    return Requirement.model_validate(
        {
            "id": "R1",
            "label": "r",
            "dimension": "TERRAIN",
            "observable": observable,
            "operator": "LTE",
            "lower": None,
            "upper": 5.0,
            "unit": "deg",
            "mandatory": True,
            "weight": 1.0,
            "evidence_scope": "regional_context",
            "minimum_support_scale_m": lo,
            "maximum_support_scale_m": hi,
            "origin": "USER",
            "acceptance_note": "n",
            "parameters": {
                "slope_band_deg": None,
                "exposure_counting": None,
                "task_ids": [],
                "co_location_group": None,
                "comparison_rule_id": None,
                "temporal_support": None,
            },
        }
    )


def metric(
    mid: str = "slope_w1_deg",
    value: float | None = 2.0,
    unit: str = "deg",
    vf: float = 1.0,
    kind: str = "DERIVED",
    note: str = "uncertainty not quantified",
) -> MeasuredMetric:
    return MeasuredMetric(
        metric_id=mid,
        value=value,
        unit=unit,
        support_scale_m=480.0,
        quantity_kind=kind,  # type: ignore[arg-type]
        method_id="m",
        valid_fraction=vf,
        uncertainty_note=note,
    )


def handle(
    kind: str = "COMPARISON",
    algo: str = "compare-requirement",
    scale: float | None = 480.0,
    mode: str = "synthetic",
    body: str = "EARTH",
    metrics: list[MeasuredMetric] | None = None,
    art: str | None = H64,
    version: str | None = None,
    limits: list[str] | None = None,
    hid: UUID | None = None,
) -> EvidenceHandle:
    return EvidenceHandle(
        evidence_id=hid or uuid4(),
        kind=kind,
        mode=mode,
        body=body,
        artifact_sha256=art,  # type: ignore[arg-type]
        algorithm_id=algo,
        algorithm_version=CFG.algorithms.algorithm_lock.get(algo, "1.0.0") if version is None else version,
        parameters_sha256=H64,
        comparison_scale_m=scale,
        metrics=metrics if metrics is not None else [metric()],
        limitations=limits or [],
    )


def audit(
    handles: list[EvidenceHandle],
    *,
    claim_type: str = "QUALIFICATION",
    req: Requirement | None = None,
    checks: list[str] | None = None,
    ids: list[UUID] | None = None,
    **kw: Any,
) -> AuditEvidencePayload:
    claim = ClaimScope(
        claim_id="c1",
        claim_type=claim_type,
        requirement_id="R1" if req else None,  # type: ignore[arg-type]
        candidate_window_ids=["W"],
        evidence_ids=ids if ids is not None else [h.evidence_id for h in handles],
    )
    return audit_evidence(
        AuditEvidenceInput(claims=[claim], check_set=ALL_CHECKS if checks is None else checks),  # type: ignore[arg-type]
        mode="synthetic",
        evidence=handles,
        config=CFG,
        requirements={"R1": req} if req else {},
        **kw,
    )


def gates(p: AuditEvidencePayload) -> dict[str, str]:
    return {g.gate_id: g.outcome for g in p.claim_gates[0].gates}


def rules(p: AuditEvidencePayload) -> set[str]:
    return {f.rule_code for f in p.findings}


def test_clean_comparison_claim_satisfies_every_applicable_gate_and_lists_exactly_the_science_gates() -> None:
    p = audit([handle()], req=requirement())
    assert [g.gate_id for g in p.claim_gates[0].gates] == list(AUDIT_GATES)
    g = gates(p)
    assert g["SC-02"] == g["SC-03"] == g["SC-04"] == g["SC-05"] == g["SC-07"] == g["SC-08"] == g["SC-09"] == "SATISFIED"
    assert g["SC-06"] == g["SC-10"] == g["SC-11"] == g["SC-13"] == "NOT_APPLICABLE"
    for gate in p.claim_gates[0].gates:
        if gate.outcome == "NOT_APPLICABLE":
            assert gate.reason.strip()
    assert "SC-01" not in g and "SC-12" not in g and not [f for f in p.findings if f.severity == "BLOCKING"]


def test_sc04_scale_mismatch_finer_and_coarser_and_perturbation() -> None:
    finer = audit([handle(scale=60.0)], req=requirement())
    assert gates(finer)["SC-04"] == "UNSATISFIED" and "SCALE_MISMATCH" in rules(finer)
    assert any(f.severity == "BLOCKING" and f.requirement_id == "R1" for f in finer.findings)
    coarse = audit([handle(scale=2000.0)], req=requirement(lo=None, hi=500.0))
    assert gates(coarse)["SC-04"] == "UNSATISFIED" and "SCALE_MISMATCH" in rules(coarse)
    assert gates(audit([handle(scale=480.0)], req=requirement()))["SC-04"] == "SATISFIED"  # boundary is inclusive
    assert gates(audit([handle(scale=479.0)], req=requirement()))["SC-04"] == "UNSATISFIED"
    assert gates(audit([handle(scale=500.0)], req=requirement(lo=None, hi=500.0)))["SC-04"] == "SATISFIED"
    assert gates(audit([handle(scale=500.1)], req=requirement(lo=None, hi=500.0)))["SC-04"] == "UNSATISFIED"
    # the seeded critic defect: 60 m analysis evidence cited instead of the 480 m comparison evidence
    analysis, comparison = handle("DERIVED", "analyze-candidate", 60.0), handle("COMPARISON", scale=480.0)
    assert gates(audit([analysis], req=requirement()))["SC-04"] == "UNSATISFIED"
    assert gates(audit([analysis, comparison], req=requirement()))["SC-04"] == "SATISFIED"
    assert gates(audit([handle(scale=None)], req=requirement()))["SC-04"] == "NOT_ASSESSED"
    assert gates(audit([handle()]))["SC-04"] == "NOT_ASSESSED"  # no requirement window known
    assert gates(audit([handle()], req=requirement(lo=None, hi=None)))["SC-04"] == "NOT_ASSESSED"


def test_sc02_provenance_missing_ids_mode_and_artifact_hash() -> None:
    h = handle()
    ghost = uuid4()
    p = audit([h], ids=[h.evidence_id, ghost])
    assert gates(p)["SC-02"] == "UNSATISFIED" and "MISSING_PROVENANCE" in rules(p)
    assert ghost in [i for f in p.findings for i in f.evidence_ids]
    assert gates(audit([handle(art=None)]))["SC-02"] == "UNSATISFIED"
    assert gates(audit([handle("SOURCE", art=None)]))["SC-02"] == "SATISFIED"
    p2 = audit([handle(mode="live")])
    assert gates(p2)["SC-02"] == "UNSATISFIED" and "MODE_MISMATCH" in rules(p2)
    assert gates(audit([], ids=[]))["SC-02"] == "UNSATISFIED"


def test_sc03_body_and_units() -> None:
    req = requirement("surface_temperature_min_k")
    assert gates(audit([handle(body="MARS")], req=req))["SC-03"] == "UNSATISFIED"  # thermal policy is Earth/Moon only
    p = audit([handle(metrics=[metric("slope_w1_deg", 2.0, "rad")])], req=requirement())
    assert gates(p)["SC-03"] == "UNSATISFIED" and "UNIT_MISMATCH" in rules(p)
    p2 = audit([handle(body="MARS")], req=requirement("unique_slope_exposure_m"))
    assert "CRS_MISMATCH" in rules(p2) and gates(p2)["SC-03"] == "UNSATISFIED"
    assert gates(audit([handle()]))["SC-03"] == "NOT_ASSESSED"  # no policy -> cannot judge body


def test_sc05_coverage_zero_filled_and_threshold_from_policy() -> None:
    assert gates(audit([handle(metrics=[metric(vf=0.79)])], req=requirement()))["SC-05"] == "UNSATISFIED"
    assert gates(audit([handle(metrics=[metric(vf=0.80)])], req=requirement()))["SC-05"] == "SATISFIED"
    p = audit([handle(metrics=[metric(value=0.0, vf=0.0)])], req=requirement())
    assert gates(p)["SC-05"] == "UNSATISFIED" and "COVERAGE_MISSING" in rules(p)
    assert gates(audit([handle(metrics=[metric(value=None, vf=0.0)])], req=requirement()))["SC-05"] == "NOT_ASSESSED"
    assert (
        gates(audit([handle(metrics=[metric(vf=0.85), metric("valid_fraction", 0.5, "fraction", 0.5)])]))["SC-05"]
        == "UNSATISFIED"
    )


def test_sc06_temporal() -> None:
    assert gates(audit([handle()], req=requirement("surface_temperature_min_k")))["SC-06"] == "NOT_ASSESSED"
    assert gates(audit([handle()], req=requirement()))["SC-06"] == "NOT_APPLICABLE"
    assert gates(audit([handle()]))["SC-06"] == "NOT_ASSESSED"


def test_sc07_proxy_and_assumption() -> None:
    p = audit([handle(metrics=[metric(kind="PROXY")])], req=requirement())
    assert gates(p)["SC-07"] == "UNSATISFIED" and "PROXY_OVERSTATED" in rules(p)
    assumed = handle(metrics=[metric("reserve_pct", 50.0, "percent", kind="ASSUMED")])
    p2 = audit([assumed], req=requirement("final_battery_reserve_pct"))
    assert gates(p2)["SC-07"] == "NOT_ASSESSED" and "PROXY_OVERSTATED" in rules(p2)
    assert (
        gates(
            audit(
                [assumed, handle("ASSUMPTION", "assumption", None, metrics=[])],
                req=requirement("final_battery_reserve_pct"),
            )
        )["SC-07"]
        == "SATISFIED"
    )


def test_sc08_uncertainty() -> None:
    p = audit([handle(metrics=[metric(note="")])], req=requirement())
    assert gates(p)["SC-08"] == "UNSATISFIED" and "UNCERTAINTY_UNQUANTIFIED" in rules(p)
    nominal = audit([handle()], req=requirement())
    assert gates(nominal)["SC-08"] == "SATISFIED" and "nominal" in next(
        g.reason for g in nominal.claim_gates[0].gates if g.gate_id == "SC-08"
    )
    assert (
        gates(audit([handle(metrics=[metric(note="+/- 0.2 deg (1 sigma)")])], req=requirement()))["SC-08"]
        == "SATISFIED"
    )
    assert gates(audit([handle(metrics=[])], req=requirement()))["SC-08"] == "NOT_ASSESSED"


def test_sc09_version_and_lock() -> None:
    assert gates(audit([handle(version=" ")]))["SC-09"] == "UNSATISFIED"
    assert gates(audit([handle(version="9.9.9")]))["SC-09"] == "UNSATISFIED"  # differs from the algorithm lock
    assert gates(audit([handle(algo="third-party", version="0.1")]))["SC-09"] == "SATISFIED"


def test_sc10_shared_ancestry_nasadem_srtm_but_not_distinct_families() -> None:
    nasadem = handle("SOURCE", "ingest-local-dataset", None, limits=["NASADEM one arc-second"], art=None)
    srtm = handle("SOURCE", "ingest-local-dataset", None, limits=["SRTM v3"], art=None)
    mola = handle("SOURCE", "ingest-local-dataset", None, limits=["MOLA topography"], art=None)
    p = audit([nasadem, srtm])
    assert gates(p)["SC-10"] == "UNSATISFIED" and "SHARED_ANCESTRY" in rules(p)
    assert gates(audit([nasadem, mola]))["SC-10"] == "SATISFIED"
    assert gates(audit([nasadem]))["SC-10"] == "NOT_APPLICABLE"
    ex = {nasadem.evidence_id: frozenset({"A"}), srtm.evidence_id: frozenset({"B"})}
    assert gates(audit([nasadem, srtm], source_families=ex))["SC-10"] == "SATISFIED"  # explicit map overrides tokens
    assert gates(audit([nasadem, srtm], checks=[]))["SC-10"] == "NOT_ASSESSED"


def test_sc11_independent_verification_vs_search_algorithm() -> None:
    search = handle("DERIVED", "search-route", 60.0, metrics=[])
    verify = handle("VERIFICATION", "verify-route", 60.0, metrics=[])
    assert gates(audit([search, verify], claim_type="VERIFICATION"))["SC-11"] == "SATISFIED"
    same = handle("VERIFICATION", "search-route", 60.0, metrics=[])
    p = audit([search, same], claim_type="VERIFICATION")
    assert gates(p)["SC-11"] == "UNSATISFIED" and "ROUTE_NOT_VERIFIED" in rules(p)
    p2 = audit([search], claim_type="VERIFICATION")
    assert gates(p2)["SC-11"] == "UNSATISFIED"  # solver self-certification
    assert gates(audit([handle()], claim_type="VERIFICATION"))["SC-11"] == "NOT_ASSESSED"
    assert gates(audit([search], claim_type="QUALIFICATION"))["SC-11"] == "UNSATISFIED"
    assert gates(audit([verify], claim_type="VERIFICATION", checks=["scale"]))["SC-11"] == "NOT_ASSESSED"


def test_sc13_discovery_controls() -> None:
    screen = handle("DERIVED", "screen-candidates", None, metrics=[])
    good = DiscoveryEvidence(True, "ref-v1", ("grid-r0c2",), True, (uuid4(),))
    assert gates(audit([screen], claim_type="DISCOVERY", discovery={screen.evidence_id: good}))["SC-13"] == "SATISFIED"
    for bad, text in (
        (DiscoveryEvidence(True, "ref-v1", (), True, (uuid4(),)), "negative control"),
        (DiscoveryEvidence(True, "ref-v1", ("n",), True, ()), "mission sensitivity"),
        (DiscoveryEvidence(True, None, ("n",), True, (uuid4(),)), "reference-set"),
        (DiscoveryEvidence(False, "r", ("n",), True, (uuid4(),)), "search extent"),
    ):
        p = audit([screen], claim_type="DISCOVERY", discovery={screen.evidence_id: bad})
        assert gates(p)["SC-13"] == "UNSATISFIED" and text in p.claim_gates[0].gates[-1].reason
    assert gates(audit([screen], claim_type="DISCOVERY"))["SC-13"] == "NOT_ASSESSED"
    assert gates(audit([handle()], claim_type="DISCOVERY"))["SC-13"] == "UNSATISFIED"
    assert gates(audit([handle()], claim_type="QUALIFICATION"))["SC-13"] == "NOT_APPLICABLE"


def test_check_set_controls_assessment_and_audit_is_deterministic() -> None:
    hs = [handle(scale=60.0)]
    only_scale = audit(hs, req=requirement(), checks=["scale"])
    g = gates(only_scale)
    assert g["SC-04"] == "UNSATISFIED" and g["SC-02"] == g["SC-05"] == g["SC-08"] == "NOT_ASSESSED"
    a, b = audit(hs, req=requirement()), audit(list(reversed(hs)), req=requirement())
    assert a.model_dump() == b.model_dump()
    assert [f.finding_id for f in a.findings] == sorted(f.finding_id for f in a.findings)


def test_audit_reports_never_a_publication_decision() -> None:
    p = audit([handle(scale=60.0, art=None)], req=requirement())
    assert set(AuditEvidencePayload.model_fields) == {"operation", "claim_gates", "findings"}
    assert any(f.severity == "BLOCKING" for f in p.findings)


# ----------------------------------------------------------------------------- review defects 7 and 8
def test_sc10_matches_source_products_as_whole_words_not_substrings() -> None:
    # "raster" contains "aster"; "emitted" contains "emit"; "lolabel" contains "lola": none names a source product
    decoys = [
        handle("SOURCE", "ingest-local-dataset", None, limits=["Resampled raster grid"], art=None),
        handle("SOURCE", "ingest-local-dataset", None, limits=["emitted by the lolabel tool, modula"], art=None),
        handle("SOURCE", "ingest-local-dataset", None, limits=["srtmgl-like but unrelated"], art=None),
    ]
    srtm = handle("SOURCE", "ingest-local-dataset", None, limits=["SRTM v3"], art=None)
    p = audit([*decoys, srtm])
    assert gates(p)["SC-10"] == "NOT_APPLICABLE" and "SHARED_ANCESTRY" not in rules(p)  # only one real product
    # real products are still found as words, with punctuation and product-id suffixes
    nasadem = handle("SOURCE", "adapter", None, limits=["earth_nasadem_hgt_v001 tile"], art=None)
    aster = handle("SOURCE", "adapter", None, limits=["ASTER GDEM v3"], art=None)
    assert gates(audit([nasadem, srtm]))["SC-10"] == "UNSATISFIED"
    assert gates(audit([nasadem, aster]))["SC-10"] == "SATISFIED"
    assert (
        gates(audit([aster, handle("SOURCE", "adapter", None, limits=["ASTER"], art=None)]))["SC-10"]
        == "NOT_APPLICABLE"
    )


def test_sc07_accepted_assumption_still_needs_an_uncertainty_statement() -> None:
    silent = handle(metrics=[metric("reserve_pct", 50.0, "percent", kind="ASSUMED", note="")])
    assumption = handle("ASSUMPTION", "assumption", None, metrics=[])
    p = audit([silent, assumption], req=requirement("final_battery_reserve_pct"))
    assert gates(p)["SC-07"] == "NOT_ASSESSED" and "UNCERTAINTY_UNQUANTIFIED" in rules(p)
    stated = handle(metrics=[metric("reserve_pct", 50.0, "percent", kind="ASSUMED", note="assumed, +/-10 %")])
    assert gates(audit([stated, assumption], req=requirement("final_battery_reserve_pct")))["SC-07"] == "SATISFIED"


def _screening_payload(extent: list[float], screened: int = 9):  # type: ignore[no-untyped-def]
    from analogforge.ports.domain_models import AreaOfInterest
    from analogforge.ports.science_payloads import ScreenCandidatesPayload

    return ScreenCandidatesPayload(
        screened_count=screened, windows=[], shortlist_window_ids=[], stop_reason="GRID_EXHAUSTED",
        search_extent=AreaOfInterest(
            body="EARTH", bbox=extent, longitude_convention="NEG180_180", latitude_type="GEODETIC", crs_wkt=None,
            vertical_datum="WGS84",
        ),
    )  # fmt: skip


def test_search_extent_is_derived_from_the_screening_payload() -> None:
    from analogforge.science.audit import discovery_evidence_from_screening

    assert discovery_evidence_from_screening(
        _screening_payload([-112.0, 35.0, -111.9, 35.1]), reference_set_id="r"
    ).search_extent_recorded
    for bbox, n in (
        ([-112.0, 35.0, -112.0, 35.1], 9),
        ([-112.0, 35.0, -111.9, 35.0], 9),
        ([-112.0, 35.0, -111.9, 35.1], 0),
    ):
        ev = discovery_evidence_from_screening(_screening_payload(bbox, n), reference_set_id="r")
        assert not ev.search_extent_recorded and "search extent" in ev.missing(), (bbox, n)


def test_mission_sensitivity_needs_comparisons_under_distinct_contracts() -> None:
    from analogforge.science.ops.audit import _mission_sensitivity_ids

    def comparison(sha: str) -> EvidenceHandle:
        return handle("COMPARISON", "compare-requirement", 480.0).model_copy(update={"parameters_sha256": sha})

    one = comparison("1" * 64)
    assert _mission_sensitivity_ids([one]) == []  # a single verdict is not a sensitivity analysis
    assert _mission_sensitivity_ids([one, one.model_copy(update={"evidence_id": uuid4()})]) == []  # same contract twice
    two = comparison("2" * 64)
    assert sorted(map(str, _mission_sensitivity_ids([one, two]))) == sorted(
        map(str, [one.evidence_id, two.evidence_id])
    )
    assert _mission_sensitivity_ids([handle("DERIVED", "analyze-candidate", 60.0), one]) == []
