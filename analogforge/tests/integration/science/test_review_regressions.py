# ruff: noqa: E501
"""Regression tests for adversarially reviewed defects (characterize coverage, comparison binding, audit gates, ...)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from support.practice import Flow, local, make_practice_context, mars_target_aoi, service

from analogforge.ports import catalog
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import CharacterizeTargetInput, CharacterizeTargetPayload

MARS_RADIUS_M = 3_396_190.0
STD_PARALLEL_DEG = -4.5  # practice Mars CRS: equidistant cylindrical about -4.5 deg, central meridian 137.5 deg
HALF_WIDTH_M = 128 * 480.0 / 2.0  # the 128 x 128 dataset is centred on the projection origin


def _lon_half_width_deg() -> float:
    return math.degrees(HALF_WIDTH_M / (MARS_RADIUS_M * math.cos(math.radians(STD_PARALLEL_DEG))))


@pytest.fixture(scope="module")
def mars_flow(tmp_path_factory: pytest.TempPathFactory) -> Flow:
    return Flow(service(), make_practice_context(tmp_path_factory.mktemp("review")))


def _characterize(flow: Flow, dx: float):  # type: ignore[no-untyped-def]
    aoi = mars_target_aoi()
    shifted = aoi.model_copy(update={"bbox": [aoi.bbox[0] + dx, aoi.bbox[1], aoi.bbox[2] + dx, aoi.bbox[3]]})
    inp = CharacterizeTargetInput(
        target=shifted, source=local("practice-mars-target-v1"),
        measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET, requested_dimensions=["TERRAIN"],
    )  # fmt: skip
    res, _ = flow.call(inp, datasets=["practice-mars-target-v1"])
    return res


@pytest.mark.parametrize("dx", [0.0, 0.5, 0.9])
def test_characterize_valid_fraction_counts_the_part_of_the_aoi_outside_the_dataset(mars_flow: Flow, dx: float) -> None:
    """valid_fraction is over the WHOLE AOI: an AOI shifted east by dx degrees is only partly covered."""
    res = _characterize(mars_flow, dx)
    assert isinstance(res.payload, CharacterizeTargetPayload), res.issues
    vf = next(m for m in res.payload.metrics if m.metric_id == "valid_fraction").value
    assert vf is not None
    # independent oracle: dataset spans central meridian 137.5 +- half-width; the AOI is [137 + dx, 138 + dx]
    east_edge = 137.5 + _lon_half_width_deg()
    inside = max(0.0, min(1.0, east_edge - (137.0 + dx)))
    assert vf <= inside + 1e-9
    assert vf >= inside - 0.03  # the one-cell derivative ring around the raster edge is not valid (1/128 per side)
    if dx > 0.0:
        assert vf < 1.0


def test_characterize_blocks_an_aoi_that_is_mostly_outside_the_dataset(mars_flow: Flow) -> None:
    res = _characterize(mars_flow, 0.99)  # only ~3 % of the AOI lies inside the dataset (< 0.05 hard minimum)
    assert res.status == ComputationStatus.BLOCKED, res.status
    assert res.payload is None
    assert any(i.code == "INSUFFICIENT_VALID_DATA" for i in res.issues), [i.code for i in res.issues]


# ----------------------------------------------------------------------------- defect 6: evidence binds to the candidate
@pytest.fixture(scope="module")
def practice(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    from support.practice import characterize_mars, screen

    flow = Flow(service(), make_practice_context(tmp_path_factory.mktemp("bind")))
    target, th = characterize_mars(flow)
    return flow, th, screen(flow, target)


def test_compare_blocks_evidence_of_another_window_and_mixed_evidence(practice) -> None:  # type: ignore[no-untyped-def]
    from support.builders import load_mission, requirement
    from support.practice import analyze, candidate_ref, compare

    from analogforge.ports.science_payloads import CompareRequirementPayload

    flow, th, sc = practice
    req = requirement(load_mission("mission-mars-mobility"), "R-SLOPE-AVAILABILITY")
    flat, corridor = candidate_ref(sc, catalog.WINDOW_C_FLAT), candidate_ref(sc, catalog.WINDOW_B_CORRIDOR)
    _, h_flat = analyze(flow, flat)
    _, h_corr = analyze(flow, corridor)
    own = compare(flow, req, flat, [th], h_flat)
    assert isinstance(own.payload, CompareRequirementPayload) and own.payload.proposed_status == "FAIL"
    for evidence in (h_corr, h_corr + h_flat, h_flat + h_corr):  # foreign evidence, then mixed evidence
        res = compare(flow, req, flat, [th], evidence)
        assert res.status == ComputationStatus.BLOCKED and res.payload is None, evidence
        assert any(i.code == "INPUT_INVALID" for i in res.issues)
    # the same evidence is fine for its own window: the check is by geometry, not by a hard-coded id
    assert isinstance(compare(flow, req, corridor, [th], h_corr).payload, CompareRequirementPayload)


def test_analysis_states_which_slope_cap_the_connected_zones_use(practice) -> None:  # type: ignore[no-untyped-def]
    """ANALYZE_CANDIDATE has no rover input (kit), so zones use the config default cap and say so."""
    from support.practice import analyze, candidate_ref

    from analogforge.science.config import load_config

    flow, _, sc = practice
    _, handles = analyze(flow, candidate_ref(sc, catalog.WINDOW_B_CORRIDOR))
    cap = load_config().algorithms.thresholds.default_cap_deg
    assert any(f"safe-slope cap of {cap:g} deg" in lim and "no rover" in lim for lim in handles[0].limitations)


# ----------------------------------------------------------------------------- mutation survivor: screening boundary
def _screen_with_min_valid(tmp_path: Path, min_valid: float):  # type: ignore[no-untyped-def]
    import shutil

    import yaml
    from support.practice import characterize_mars, screen

    from analogforge.science.facade import create_science_service

    conf = tmp_path / f"config-{min_valid!r}"
    shutil.copytree(Path(__file__).resolve().parents[3] / "config", conf)
    raw = yaml.safe_load((conf / "algorithms.yaml").read_text())
    raw["thresholds"]["min_valid_fraction"] = min_valid
    (conf / "algorithms.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    flow = Flow(create_science_service(conf), make_practice_context(tmp_path / f"w-{min_valid!r}"))
    target, _ = characterize_mars(flow)
    return {w.window_id: w for w in screen(flow, target).windows}


def test_screening_keeps_a_window_whose_valid_fraction_equals_the_minimum_exactly(practice, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """`valid_fraction < min` excludes; equality stays in (kills the `<` -> `<=` mutant)."""
    from support.practice import analyze, candidate_ref

    flow, _, sc = practice
    _, handles = analyze(flow, candidate_ref(sc, catalog.WINDOW_A_MESA))
    vf = next(m.value for m in handles[0].metrics if m.metric_id == "valid_fraction")
    assert vf is not None and 0.0 < vf < 1.0
    at_minimum = _screen_with_min_valid(tmp_path, vf)[catalog.WINDOW_A_MESA]
    assert not at_minimum.excluded and at_minimum.rank is not None
    above = _screen_with_min_valid(tmp_path, math.nextafter(vf, 1.0))[catalog.WINDOW_A_MESA]
    assert above.excluded and above.exclusion_reason == "INSUFFICIENT_VALID_DATA"
