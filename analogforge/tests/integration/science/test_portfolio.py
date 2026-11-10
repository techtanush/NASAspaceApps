"""SCN-16: architecture 13 section 6 fixtures 1-7, input-order stability, coupling, limits and perturbations."""

from __future__ import annotations

import itertools
import random
from typing import Any

import pytest

from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import Requirement
from analogforge.ports.science_payloads import (
    CandidateRef,
    OptimizePortfolioInput,
    OptimizePortfolioPayload,
    QualificationRowInput,
    VerificationSummary,
)
from analogforge.science.errors import ScienceError
from analogforge.science.portfolio import MAX_ELIGIBLE, check_single_scope, optimize_portfolio

EV = EvidenceRef(local_key="portfolio")


def req(
    rid: str,
    observable: str,
    *,
    weight: float = 1.0,
    mandatory: bool = True,
    group: str | None = None,
    operator: str = "GTE",
    dimension: str = "TERRAIN",
) -> Requirement:
    return Requirement.model_validate(
        {
            "id": rid,
            "label": rid.lower(),
            "dimension": dimension,
            "observable": observable,
            "operator": operator,
            "lower": None if operator == "NOT_NATURALLY_REPRODUCIBLE" else 1.0,
            "upper": None,
            "unit": "x",
            "mandatory": mandatory,
            "weight": weight,
            "evidence_scope": "terrain_model",
            "minimum_support_scale_m": None,
            "maximum_support_scale_m": None,
            "origin": "USER",
            "acceptance_note": "n",
            "parameters": {
                "slope_band_deg": None,
                "exposure_counting": None,
                "task_ids": [],
                "co_location_group": group,
                "comparison_rule_id": None,
                "temporal_support": None,
            },
        }
    )


def cand(wid: str) -> CandidateRef:
    return CandidateRef.model_validate(
        {
            "window_id": wid,
            "name": wid,
            "origin": "SYNTHETIC_CONTROL",
            "novelty_status": "NOT_ASSESSED",
            "discovery_method": "t",
            "aoi": {
                "body": "EARTH",
                "bbox": [0, 0, 1, 1],
                "longitude_convention": "NEG180_180",
                "latitude_type": "GEODETIC",
                "crs_wkt": None,
                "vertical_datum": "EGM96",
            },
        }
    )


def row(w: str, r: str, status: str = "PASS", stage: str = "FINAL", blocked: bool = False) -> QualificationRowInput:
    return QualificationRowInput(
        candidate_window_id=w, requirement_id=r, status=status, evaluation_stage=stage, critic_blocking_open=blocked
    )  # type: ignore[arg-type]


def ver(outcome: str) -> VerificationSummary:
    return VerificationSummary(outcome=outcome, failure_category=None)  # type: ignore[arg-type]


MOB = req("R-MOB", "slope_band_area_fraction")
THERM = req("R-THERM", "surface_temperature_min_k", dimension="THERMAL")
GRAV = req("R-GRAV", "planetary_gravity", operator="NOT_NATURALLY_REPRODUCIBLE", mandatory=False, dimension="GRAVITY")


def run(
    reqs: list[Requirement],
    windows: list[str],
    rows: list[QualificationRowInput],
    *,
    max_sites: int = 3,
    verification: dict[str, VerificationSummary] | None = None,
) -> OptimizePortfolioPayload:
    return optimize_portfolio(
        OptimizePortfolioInput(
            requirements=reqs,
            candidates=[cand(w) for w in windows],
            qualification_rows=rows,
            verification_by_window_id=verification or {},
            max_sites=max_sites,
        ),
        portfolio_evidence=EV,
    )


def cov(p: OptimizePortfolioPayload) -> dict[str, str]:
    return {a.requirement_id: a.coverage for a in p.assignments}


def test_fixture1_one_site_covering_everything_beats_two() -> None:
    rows = [row("A", "R-MOB"), row("B", "R-THERM"), row("C", "R-MOB"), row("C", "R-THERM")]
    p = run([MOB, THERM, GRAV], ["A", "B", "C"], rows)
    assert p.selected_window_ids == ["C"] and p.objective_value == 2.0
    assert cov(p) == {"R-GRAV": "GAP", "R-MOB": "FULL", "R-THERM": "FULL"}
    assert p.residual_requirement_ids == ["R-GRAV"]
    assert p.lexicographic_objective[:3] == [2.0, 0.0, -1.0]


def test_fixture2_without_c_choose_a_plus_b_and_keep_gravity_gap() -> None:
    rows = [row("A", "R-MOB"), row("B", "R-THERM")]
    p = run([MOB, THERM, GRAV], ["A", "B"], rows)
    assert p.selected_window_ids == ["A", "B"] and p.objective_value == 2.0
    assert cov(p)["R-GRAV"] == "GAP" and "R-GRAV" in p.residual_requirement_ids
    assert {a.requirement_id: a.window_ids for a in p.assignments}["R-MOB"] == ["A"]
    assert all(a.responsibility for a in p.assignments if a.coverage == "FULL")
    assert run([MOB, THERM, GRAV], ["A", "B"], rows, max_sites=1).objective_value == 1.0  # max_sites respected


def test_fixture3_coupled_requirements_cannot_be_split_across_sites() -> None:
    mob, therm = (
        req("R-MOB", "slope_band_area_fraction", group="G"),
        req("R-THERM", "surface_temperature_min_k", group="G"),
    )
    rows = [row("A", "R-MOB"), row("B", "R-THERM")]
    p = run([mob, therm, GRAV], ["A", "B"], rows, verification={"A": ver("PASS"), "B": ver("PASS")})
    assert p.objective_value == 0.0 and p.selected_window_ids == []
    assert "FULL" not in cov(p).values()
    assert {"R-MOB", "R-THERM"} <= set(p.residual_requirement_ids)
    # one site holding both member rows, verified, covers the group jointly
    rows2 = rows + [row("C", "R-MOB"), row("C", "R-THERM")]
    p2 = run([mob, therm, GRAV], ["A", "B", "C"], rows2, verification={"C": ver("PASS")})
    assert p2.selected_window_ids == ["C"] and p2.objective_value == 2.0
    # without the site's verification PASS the joint item is not covered (and a PRELIMINARY member also blocks it)
    rows_c = rows2[2:]
    assert run([mob, therm], ["C"], rows_c).selected_window_ids == []
    assert run([mob, therm], ["C"], rows_c, verification={"C": ver("INCONCLUSIVE")}).selected_window_ids == []
    rows3 = [row("C", "R-MOB"), row("C", "R-THERM", stage="PRELIMINARY")]
    assert run([mob, therm], ["C"], rows3, verification={"C": ver("PASS")}).selected_window_ids == []


def test_fixture4_unknown_thermal_does_not_count_and_adds_no_site() -> None:
    rows = [row("A", "R-MOB"), row("B", "R-THERM", status="UNKNOWN")]
    p = run([MOB, THERM, GRAV], ["A", "B"], rows)
    assert p.selected_window_ids == ["A"] and p.objective_value == 1.0
    assert cov(p)["R-THERM"] == "UNKNOWN" and "R-THERM" in p.residual_requirement_ids
    # perturbation: making B's thermal PASS selects B too
    rows[1] = row("B", "R-THERM")
    assert run([MOB, THERM, GRAV], ["A", "B"], rows).selected_window_ids == ["A", "B"]


def test_fixture5_inconclusive_verification_removes_route_dependent_full_but_keeps_context() -> None:
    expo = req("R-EXPOSURE", "unique_slope_exposure_m")
    rows = [row("A", "R-EXPOSURE"), row("A", "R-MOB"), row("B", "R-EXPOSURE")]
    ok = run([expo, MOB], ["A", "B"], rows, verification={"A": ver("PASS"), "B": ver("PASS")})
    assert ok.selected_window_ids == ["A"] and cov(ok) == {"R-EXPOSURE": "FULL", "R-MOB": "FULL"}
    bad = run([expo, MOB], ["A", "B"], rows, verification={"A": ver("INCONCLUSIVE"), "B": ver("PASS")})
    assert cov(bad)["R-MOB"] == "FULL" and "A" in bad.selected_window_ids
    assert cov(bad)["R-EXPOSURE"] == "FULL" and {a.requirement_id: a.window_ids for a in bad.assignments}[
        "R-EXPOSURE"
    ] == ["B"]
    only_a = run([expo, MOB], ["A"], rows[:2], verification={"A": ver("INCONCLUSIVE")})
    assert cov(only_a)["R-EXPOSURE"] != "FULL" and cov(only_a)["R-MOB"] == "FULL"
    assert any("verification is not PASS at A" in s for s in only_a.limitations)
    prelim = run([expo], ["A"], [row("A", "R-EXPOSURE", stage="PRELIMINARY")])
    assert cov(prelim)["R-EXPOSURE"] == "UNKNOWN" and prelim.selected_window_ids == []


def test_fixture6_equal_solutions_are_stable_across_input_order() -> None:
    rows = [row("S2", "R-MOB"), row("S1", "R-MOB"), row("S3", "R-MOB")]
    base = run([MOB, THERM], ["S1", "S2", "S3"], rows)
    assert base.selected_window_ids == ["S1"]  # smallest sorted window id wins the tie
    rng = random.Random(7)  # noqa: S311
    for _ in range(12):
        w = ["S1", "S2", "S3"]
        r = list(rows)
        q = [MOB, THERM]
        rng.shuffle(w), rng.shuffle(r), rng.shuffle(q)
        assert run(q, w, r).model_dump() == base.model_dump()
    for perm in itertools.permutations(rows):
        assert run([MOB], ["S3", "S1", "S2"], list(perm)).selected_window_ids == ["S1"]


def test_fixture7_mode_and_revision_mixing_rejected_before_optimisation() -> None:
    inp = OptimizePortfolioInput(
        requirements=[MOB], candidates=[cand("A")], qualification_rows=[row("A", "R-MOB")], max_sites=1
    )
    with pytest.raises(ScienceError) as e:
        optimize_portfolio(inp, portfolio_evidence=EV, mode="synthetic", evidence_modes=["synthetic", "live"])
    assert e.value.detail_code == "MODE_MISMATCH"
    with pytest.raises(ScienceError) as e2:
        optimize_portfolio(inp, portfolio_evidence=EV, mode="live", mission_revisions=[1, 2])
    assert e2.value.detail_code == "REVISION_MISMATCH"
    check_single_scope(mode="live", evidence_modes=["live"], mission_revisions=[3, 3])
    assert optimize_portfolio(inp, portfolio_evidence=EV, mode="live", evidence_modes=["live"]).selected_window_ids == [
        "A"
    ]


def test_empty_portfolio_is_valid_and_honest() -> None:
    p = run([MOB, THERM], ["A"], [row("A", "R-MOB", status="FAIL"), row("A", "R-THERM", status="UNKNOWN")])
    assert p.selected_window_ids == [] and p.objective_value == 0.0
    assert cov(p) == {"R-MOB": "NONE", "R-THERM": "UNKNOWN"}
    assert any("Empty portfolio" in s for s in p.limitations)
    assert any("Qualification-only" in s for s in p.limitations)


def test_blocking_critic_issue_and_partial_rows_give_no_coverage() -> None:
    p = run([MOB], ["A"], [row("A", "R-MOB", blocked=True)])
    assert p.selected_window_ids == [] and cov(p)["R-MOB"] == "UNKNOWN"
    q = run(
        [MOB, THERM],
        ["A", "B"],
        [row("A", "R-MOB"), row("A", "R-THERM", status="PARTIAL"), row("B", "R-THERM", status="PARTIAL")],
    )
    assert q.selected_window_ids == ["A"] and cov(q)["R-THERM"] == "PARTIAL" and q.objective_value == 1.0
    assert "R-THERM" in q.residual_requirement_ids


def test_weights_mandatory_before_optional_and_evidence_rank_tiebreak() -> None:
    heavy_opt = req("R-OPT", "surface_temperature_min_k", weight=100.0, mandatory=False)
    p = run([MOB, heavy_opt], ["A", "B"], [row("A", "R-MOB"), row("B", "R-OPT")], max_sites=1)
    assert p.selected_window_ids == ["A"]  # mandatory weight dominates a heavier optional weight
    assert p.lexicographic_objective[:2] == [1.0, 0.0]
    # equal weight: FINAL evidence outranks PRELIMINARY even though the id sorts later
    q = run([MOB], ["A", "B"], [row("A", "R-MOB", stage="PRELIMINARY"), row("B", "R-MOB")], max_sites=1)
    assert q.selected_window_ids == ["B"]
    # coupled weights are counted once per member, not group plus children
    mob, therm = (
        req("R-MOB", "slope_band_area_fraction", weight=2.0, group="G"),
        req("R-THERM", "surface_temperature_min_k", weight=3.0, group="G"),
    )
    g = run([mob, therm], ["C"], [row("C", "R-MOB"), row("C", "R-THERM")], verification={"C": ver("PASS")})
    assert g.objective_value == 5.0


def test_resource_limit_and_input_validation() -> None:
    names = [f"W{i:02d}" for i in range(MAX_ELIGIBLE + 1)]
    with pytest.raises(ScienceError) as e:
        run([MOB], names, [row(n, "R-MOB") for n in names], max_sites=2)
    assert e.value.code == "RESOURCE_LIMIT"
    ok = names[:MAX_ELIGIBLE]
    assert run([MOB], ok, [row(n, "R-MOB") for n in ok], max_sites=2).selected_window_ids == ["W00"]
    # ineligible windows do not count toward the limit
    assert run([MOB], names, [row("W00", "R-MOB")], max_sites=2).selected_window_ids == ["W00"]
    with pytest.raises(ScienceError):
        run([MOB], ["A"], [row("Z", "R-MOB")])
    with pytest.raises(ScienceError):
        run([MOB], ["A"], [row("A", "R-NOPE")])
    with pytest.raises(ScienceError):
        run([MOB], ["A"], [row("A", "R-MOB"), row("A", "R-MOB")])
    with pytest.raises(ScienceError):
        run([MOB], ["A"], [row("A", "R-MOB")], verification={"Q": ver("PASS")})
    with pytest.raises(ScienceError):
        run([MOB, MOB], ["A"], [])


def test_matches_brute_force_on_random_matrices() -> None:
    rng = random.Random(3)  # noqa: S311
    reqs = [
        req(f"R{i}", "slope_band_area_fraction", weight=float(rng.randint(1, 4)), mandatory=i % 2 == 0)
        for i in range(5)
    ]
    windows = [f"W{i}" for i in range(6)]
    for _ in range(25):
        rows = [row(w, r.id) for w in windows for r in reqs if rng.random() < 0.4]
        got = run(reqs, windows, rows, max_sites=3)
        cover = {(x.candidate_window_id, x.requirement_id) for x in rows}
        best: tuple[float, float, int, tuple[str, ...]] | None = None
        for k in range(0, 4):
            for s in itertools.combinations(windows, k):
                m = sum(r.weight for r in reqs if r.mandatory and any((w, r.id) in cover for w in s))
                o = sum(r.weight for r in reqs if not r.mandatory and any((w, r.id) in cover for w in s))
                cand_key = (m, o, -k, tuple(s))
                if best is None or cand_key[:3] > best[:3] or (cand_key[:3] == best[:3] and cand_key[3] < best[3]):
                    best = (m, o, -k, tuple(s))
        assert best is not None
        # evidence rank is identical (all FINAL) so the oracle is exact
        assert got.objective_value == best[0] + best[1]
        assert tuple(got.selected_window_ids) == best[3]


def _unused(_: Any) -> None:  # keep Any import meaningful for typed helpers
    return None
