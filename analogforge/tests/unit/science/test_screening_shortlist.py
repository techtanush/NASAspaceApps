"""Complementary coarse advice survives bounded retention without becoming qualification."""

import itertools
import math

import pytest
from pyproj import CRS

from analogforge.science.config import load_config
from analogforge.science.geometry import AnalysisGridSpec
from analogforge.science.ops.screen import _Row, _shortlist
from analogforge.science.ops.windows import WindowSpec, region_windows
from tests.integration.science.test_portfolio import req

BANDS = [(0.0, 5.0), (10.0, 15.0), (20.0, 25.0)]


def requirement(identifier, band=0, **changes):
    item = req(identifier, "slope_band_area_fraction").model_copy(update={"lower": 0.6, "unit": "fraction", **changes})
    return item.model_copy(update={"parameters": item.parameters.model_copy(update={"slope_band_deg": BANDS[band]})})


def rows(*entries):
    out = []
    for index, (identifier, fractions) in enumerate(entries):
        known = [max(0.0, 0.6 - value) for value in fractions if value is not None]
        out.append(_Row(WindowSpec(identifier, index, 0, index * 3, 0, 3, 3, False, True),
                        False, None, 1.0, dict(zip(BANDS, fractions, strict=False)),
                        max(known, default=0.0) if len(known) == len(fractions) else None, None, None))
    return rank(out)


def rank(candidates):
    return sorted(candidates, key=lambda row: (row.deficit if row.deficit is not None else math.inf,
                  row.w1 if row.w1 is not None else math.inf, row.spec.window_id))


def w1_requirement(**changes):
    return req("W1", "slope_distribution_w1_deg").model_copy(update={
        "operator": "LTE", "lower": None, "upper": 2.0, "unit": "deg", **changes,
    })


@pytest.mark.parametrize("cap,expected", [
    (1, ["specialist-a"]), (2, ["specialist-a", "specialist-b"]),
    (6, ["compromise", "specialist-a", "specialist-b"]),
])
def test_specialists_survive_compromise_ranking_at_each_cap(cap, expected):
    ranked = rows(("compromise", (.4, .4)), ("specialist-a", (.8, 0)), ("specialist-b", (0, .8)))
    assert ranked[0].spec.window_id == "compromise"  # The old max-deficit-only shortlist lost one specialist.
    assert _shortlist(ranked, [requirement("A"), requirement("B", 1)], cap, 60) == expected


def test_duplicate_feature_vectors_do_not_displace_the_other_benchmark_and_ties_are_stable():
    entries = [("a1", (.8, 0)), ("a2", (.8, 0)), ("b", (0, .8))]
    requirements = [requirement("A"), requirement("B", 1)]
    for shuffled in itertools.permutations(entries):
        assert _shortlist(rows(*shuffled), requirements, 2, 60) == ["a1", "b"]
        assert _shortlist(rows(*shuffled), requirements[::-1], 1, 60) == ["a1"]


def test_observed_deficit_diversity_retains_complements_even_when_no_threshold_is_met():
    ranked = rows(("a1", (.5, 0)), ("a2", (.49, 0)), ("b", (0, .5)))
    assert _shortlist(ranked, [requirement("A"), requirement("B", 1)], 2, 60) == ["a1", "b"]
    assert all(row.deficit > 0 for row in ranked)  # Advice does not create any PASS evidence.


def test_unknown_unsupported_and_physical_gap_requirements_cannot_earn_representation():
    supported = requirement("A")
    missing = requirement("missing", 1, weight=1000)
    unsupported = requirement("weather", 1, observable="surface_temperature_min_k", weight=1000)
    physical = req("gravity", "planetary_gravity", operator="NOT_NATURALLY_REPRODUCIBLE", weight=1000)
    ranked = rows(("unknown", (None, None)), ("known", (.8, None)))
    assert _shortlist(ranked, [physical, missing, unsupported, supported], 1, 60) == ["known"]
    # An incompatible support window contributes no apparent representation, even with an observed fraction.
    incompatible = requirement("coarse", 1, weight=1000, minimum_support_scale_m=120)
    ranked = rows(("a-unsupported", (.4, .8)), ("z-supported", (.8, .4)))
    assert _shortlist(ranked, [supported, incompatible], 1, 60) == ["z-supported"]


def test_declared_mandatory_priority_precedes_optional_weight():
    ranked = rows(("a-optional", (0, .8)), ("z-mandatory", (.8, 0)))
    requirements = [requirement("A"), requirement("B", 1, mandatory=False, weight=1000)]
    assert _shortlist(ranked, requirements, 1, 60) == ["z-mandatory"]


def test_mixed_band_and_w1_specialists_survive_band_deficit_ranking():
    ranked = rows(("a-band", (.8,)), ("b-band", (.8,)), ("z-w1", (0,)))
    for row in ranked:
        row.w1 = {"a-band": 4.0, "b-band": 5.0, "z-w1": 1.0}[row.spec.window_id]
    ranked = rank(ranked)
    assert [row.spec.window_id for row in ranked[:2]] == ["a-band", "b-band"]
    assert _shortlist(ranked, [requirement("A"), w1_requirement()], 2, 60, 120) == ["a-band", "z-w1"]


@pytest.mark.parametrize("w1_support,expected", [
    (None, ["a-band", "b-band"]), (60, ["a-band", "b-band"]),
    (120, ["a-band", "z-w1"]), (240, ["a-band", "b-band"]),
])
def test_w1_uses_actual_common_support_instead_of_fine_band_cell_support(w1_support, expected):
    ranked = rows(("a-band", (.8,)), ("b-band", (.8,)), ("z-w1", (0,)))
    for row in ranked:
        row.w1 = {"a-band": 4.0, "b-band": 5.0, "z-w1": 1.0}[row.spec.window_id]
    assert _shortlist(rank(ranked), [requirement("A"), w1_requirement(
        minimum_support_scale_m=120, maximum_support_scale_m=120)], 2, 60, w1_support) == expected


@pytest.mark.parametrize("changes", [{"operator": "GTE", "lower": 1.0, "upper": None}, {"unit": "fraction"}])
def test_w1_wrong_operator_or_unit_cannot_earn_representation(changes):
    ranked = rows(("a-band", (.8,)), ("b-band", (.8,)), ("z-w1", (0,)))
    for row in ranked:
        row.w1 = {"a-band": 4.0, "b-band": 5.0, "z-w1": 1.0}[row.spec.window_id]
    assert _shortlist(rank(ranked), [requirement("A"), w1_requirement(**changes)], 2, 60, 120) == ["a-band", "b-band"]


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1.0])
def test_unavailable_or_invalid_w1_never_earns_representation(value):
    ranked = rows(("a-band", (.8,)), ("b-band", (.8,)), ("z-w1", (0,)))
    for row in ranked:
        row.w1 = {"a-band": 4.0, "b-band": 5.0, "z-w1": value}[row.spec.window_id]
    assert _shortlist(ranked, [requirement("A"), w1_requirement()], 2, 60, 120) == ["a-band", "b-band"]


def test_coupled_members_cannot_earn_joint_representation_across_different_windows():
    requirements = [requirement("A"), requirement("B", 1)]
    requirements = [r.model_copy(update={"parameters": r.parameters.model_copy(update={"co_location_group": "joint"})})
                    for r in requirements]
    ranked = rows(("compromise", (.4, .4)), ("specialist-a", (.8, 0)), ("specialist-b", (0, .8)))
    assert _shortlist(ranked, requirements, 1, 60) == ["compromise"]
    # An unresolved group member cannot grant the known member independent representation.
    unknown = requirements[1].model_copy(update={"observable": "surface_temperature_min_k"})
    independent = requirement("C", 2)
    ranked = rows(("a-group", (.8, .8, .4)), ("z-independent", (.4, .4, .8)))
    assert _shortlist(ranked, [requirements[0], unknown, independent], 1, 60) == ["z-independent"]


@pytest.mark.parametrize("cap", [1, 2, 6])
def test_existing_negative_control_reservation_and_detail_cap_are_preserved(cap):
    ranked = rows(("specialist-a", (.8, 0)), ("specialist-b", (0, .8)), ("control", (0, 0)))
    next(row for row in ranked if row.spec.window_id == "control").spec = WindowSpec(
        "control", 2, 0, 6, 0, 3, 3, True, True)
    shortlist = _shortlist(ranked, [requirement("A"), requirement("B", 1)], cap, 60)
    assert "control" in shortlist and len(shortlist) == min(cap, len(ranked))
    assert len(shortlist) == len(set(shortlist))


def test_valid_source_smaller_than_a_declared_window_has_no_complete_windows():
    cfg = load_config()
    grid = AnalysisGridSpec("EARTH", CRS.from_epsg(32612).to_wkt(), 500000, 3900000, 60, 63, 64)
    assert region_windows(cfg.candidates.search_region_sets["local-dataset-grid-v1"], grid) == []
