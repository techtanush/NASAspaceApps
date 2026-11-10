# ruff: noqa: E501
"""SCN-07: SCREEN_CANDIDATES reproduces architecture 40 section 4.1 exactly, from computation."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml
from support.builders import load_mission
from support.practice import Flow, characterize_mars, make_practice_context, screen, service

from analogforge.ports import catalog
from analogforge.science.facade import create_science_service

A, B, KNOWN = catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR, catalog.WINDOW_KNOWN_REFERENCE
R1, R2, C = catalog.WINDOW_ROLLING_1, catalog.WINDOW_ROLLING_2, catalog.WINDOW_C_FLAT


@pytest.fixture(scope="module")
def screened(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    ctx = make_practice_context(tmp_path_factory.mktemp("screen"))
    flow = Flow(service(), ctx)
    target, _ = characterize_mars(flow)
    return flow, target, screen(flow, target)


def test_shortlist_is_exactly_the_specified_set(screened) -> None:  # type: ignore[no-untyped-def]
    _, _, sc = screened
    assert set(sc.shortlist_window_ids) == {A, B, KNOWN, R1, R2, C}
    assert len(sc.shortlist_window_ids) == 6
    assert sc.screened_count == 9 and sc.stop_reason == "GRID_EXHAUSTED"


def test_exclusions_ranks_and_cutoff(screened) -> None:  # type: ignore[no-untyped-def]
    _, _, sc = screened
    by = {w.window_id: w for w in sc.windows}
    assert by[catalog.WINDOW_WATER].excluded and by[catalog.WINDOW_WATER].exclusion_reason == "WATER_ONLY"
    nd = by[catalog.WINDOW_NODATA_STRIPE]
    assert nd.excluded and nd.exclusion_reason == "INSUFFICIENT_VALID_DATA" and nd.rank is None
    assert sum(1 for w in sc.windows if not w.excluded) == 7
    assert {by[w].rank for w in (A, B, KNOWN)} == {1, 2, 3}
    assert [by[w].rank for w in (R1, R2, catalog.WINDOW_GENTLE, C)] == [4, 5, 6, 7]
    gentle = by[catalog.WINDOW_GENTLE]
    assert not gentle.excluded and gentle.exclusion_reason == "BELOW_SHORTLIST_CUTOFF"
    assert gentle.window_id not in sc.shortlist_window_ids
    assert by[C].is_negative_control and not by[A].is_negative_control


def test_origins_and_novelty(screened) -> None:  # type: ignore[no-untyped-def]
    _, _, sc = screened
    by = {w.window_id: w for w in sc.windows}
    assert (by[KNOWN].origin, by[KNOWN].novelty_status) == ("KNOWN_CONTROL", "KNOWN_ANALOG")
    assert by[C].origin == "SYNTHETIC_CONTROL"
    for w in (A, B, R1, R2):
        assert (by[w].origin, by[w].novelty_status) == ("DISCOVERED", "NOT_IN_REFERENCE_LIST")


def test_feature_scores_are_deficits_not_similarity(screened) -> None:  # type: ignore[no-untyped-def]
    _, _, sc = screened
    by = {w.window_id: w for w in sc.windows}
    key = "deficit:R-SLOPE-AVAILABILITY"
    for w in (A, B, KNOWN):
        assert by[w].feature_scores[key] == 0.0
    assert by[C].feature_scores[key] == pytest.approx(0.05)  # f_band = 0 -> full deficit
    assert all("similar" not in k and "percent" not in k for w in sc.windows for k in w.feature_scores)
    # zero-deficit windows are ordered by W1 (independent check of the rank key)
    top = sorted((by[w] for w in (A, B, KNOWN)), key=lambda x: x.rank or 0)
    w1s = [x.feature_scores["slope_w1_deg"] for x in top]
    assert w1s == sorted(w1s)  # type: ignore[type-var]


def test_screening_evidence_structure(screened) -> None:  # type: ignore[no-untyped-def]
    flow, _, sc = screened
    res = flow.results[-1]
    ids = [e.algorithm_id for e in res.evidence_drafts]
    assert ids.count("screen-candidates") == 7 + 1  # one per non-excluded window plus the table
    table = next(e for e in res.evidence_drafts if e.local_key == "screening")
    art = next(a for a in res.artifacts if a.local_key == table.artifact_key)
    assert art.media_type == "application/json"
    assert any("bounded search" in x.lower() for x in sc.limitations) and any("reference_set=" in x for x in sc.limitations)
    src = next(e for e in res.evidence_drafts if e.kind == "SOURCE")
    assert src.dataset_product_id is not None and src.dataset_product_id.startswith("SYNTHETIC_") and src.source_uri is None


def test_screening_depends_on_the_data_not_the_names(tmp_path: Path) -> None:
    """Perturbation: remove window B's ramp (10 deg) -> B leaves the zero-deficit set and the shortlist changes."""
    ctx = make_practice_context(tmp_path, ramp_slope_deg=8.0)
    flow = Flow(service(), ctx)
    target, _ = characterize_mars(flow)
    sc = screen(flow, target)
    by = {w.window_id: w for w in sc.windows}
    assert by[B].feature_scores["deficit:R-SLOPE-AVAILABILITY"] > 0.0
    assert by[B].rank is not None and by[B].rank > 3


def test_thresholds_are_read_from_yaml(tmp_path: Path) -> None:
    """Changing min_valid_fraction in a config copy excludes the island windows (valid fractions 0.81-0.82)."""
    ctx = make_practice_context(tmp_path / "w")
    conf = tmp_path / "config"
    shutil.copytree(Path(__file__).resolve().parents[3] / "config", conf)
    raw = yaml.safe_load((conf / "algorithms.yaml").read_text())
    raw["thresholds"]["min_valid_fraction"] = 0.9
    (conf / "algorithms.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    flow = Flow(create_science_service(conf), ctx)
    target, _ = characterize_mars(flow)
    sc = screen(flow, target)
    by = {w.window_id: w for w in sc.windows}
    assert by[A].excluded and by[A].exclusion_reason == "INSUFFICIENT_VALID_DATA"
    assert not by[B].excluded
    assert np.isfinite(by[B].feature_scores["slope_w1_deg"])  # type: ignore[arg-type]


def test_unknown_region_set_and_reference_set_are_blocked(screened) -> None:  # type: ignore[no-untyped-def]
    flow, target, _ = screened
    from analogforge.ports.science_payloads import ScreenCandidatesInput
    from support.practice import local

    mission = load_mission("mission-mars-mobility")
    base = dict(source=local("practice-earth-grid-v1"), target_metrics=target.metrics, target_histogram=target.slope_histogram, requirements=mission.requirements, max_detailed=6)
    for bad in ({"search_region_set_id": "nope", "reference_set_id": catalog.REFERENCE_SET_PRACTICE}, {"search_region_set_id": catalog.SEARCH_REGION_PRACTICE, "reference_set_id": "nope"}):
        res, _ = flow.call(ScreenCandidatesInput(**base, **bad), datasets=["practice-earth-grid-v1"])
        assert res.status.value == "BLOCKED" and res.payload is None and res.issues
