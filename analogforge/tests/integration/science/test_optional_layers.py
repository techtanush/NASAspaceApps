# ruff: noqa: E501
"""SCN-15: absent/partial mineral and thermal layers give the specified UNKNOWN reasons; categorical ids stay categorical."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from support.builders import load_mission, requirement
from support.practice import (
    Flow,
    analyze,
    candidate_ref,
    characterize_mars,
    compare,
    local,
    make_practice_context,
    screen,
    service,
)

from analogforge.ports import catalog
from analogforge.ports.science_payloads import (
    CharacterizeTargetInput,
    CharacterizeTargetPayload,
    CompareRequirementPayload,
)

A, B, KNOWN = catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR, catalog.WINDOW_KNOWN_REFERENCE
MINERALS = ["practice-earth-grid-v1", "practice-earth-minerals-v1"]


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    root = tmp_path_factory.mktemp("optional")
    ctx = make_practice_context(root)
    flow = Flow(service(), ctx)
    target, th = characterize_mars(flow)
    return root, flow, th, screen(flow, target)


def _metric(handle, metric_id):  # type: ignore[no-untyped-def]
    return next((m for m in handle.metrics if m.metric_id == metric_id), None)


def test_partial_mineral_coverage_is_reported_as_a_fraction_not_as_absence(world) -> None:  # type: ignore[no-untyped-def]
    _, flow, th, sc = world
    expected = {B: 0.60, KNOWN: 0.85}
    for w, frac in expected.items():
        _, handles = analyze(flow, candidate_ref(sc, w), MINERALS)
        m = _metric(handles[0], "mineral_valid_fraction")
        assert m is not None and m.value == pytest.approx(frac, abs=1e-3)
        req = requirement(load_mission("mission-mars-mobility"), "R-MINERAL")
        row = compare(flow, req, candidate_ref(sc, w), [th], handles).payload
        assert isinstance(row, CompareRequirementPayload)
        assert (row.proposed_status, row.reason_code) == ("UNKNOWN", "TARGET_EVIDENCE_MISSING")


def test_window_without_retrievals_is_unknown_not_zero(world) -> None:  # type: ignore[no-untyped-def]
    _, flow, th, sc = world
    _, handles = analyze(flow, candidate_ref(sc, A), MINERALS)
    m = _metric(handles[0], "mineral_valid_fraction")
    assert m is not None and m.value is None  # unknown, never 0
    assert not any(x.metric_id.startswith("mineral_class_fraction") for x in handles[0].metrics)
    row = compare(flow, requirement(load_mission("mission-mars-mobility"), "R-MINERAL"), candidate_ref(sc, A), [th], handles).payload
    assert isinstance(row, CompareRequirementPayload) and row.reason_code == "EARTH_EVIDENCE_MISSING"


def test_categorical_ids_are_counted_never_interpolated(world) -> None:  # type: ignore[no-untyped-def]
    root, flow, _, sc = world
    _, handles = analyze(flow, candidate_ref(sc, B), MINERALS)
    manifest = yaml.safe_load((root / "data" / "practice-earth-minerals-v1" / "manifest.yaml").read_text())
    with rasterio.open(root / "data" / "practice-earth-minerals-v1" / manifest["primary_file"]) as ds:
        ids = ds.read(1)[0:64, 0:64]  # window grid-r0c0
    fracs = {int(m.metric_id.split(":")[1]): m.value for m in handles[0].metrics if m.metric_id.startswith("mineral_class_fraction:")}
    assert set(fracs) == {int(v) for v in np.unique(ids) if v != 0}
    for cid, value in fracs.items():
        assert value == pytest.approx(float((ids == cid).sum()) / ids.size, abs=1e-12)
    assert sum(fracs.values()) == pytest.approx(0.60, abs=1e-3)
    assert all(float(k).is_integer() and 1 <= k <= 4 for k in fracs)


def test_thermal_row_stays_unknown_even_when_the_target_has_a_thermal_metric(tmp_path: Path) -> None:
    ctx = make_practice_context(tmp_path)
    flow = Flow(service(), ctx)
    moon = load_mission("mission-moon-gap")

    def characterize(datasets: list[str]):  # type: ignore[no-untyped-def]
        inp = CharacterizeTargetInput(target=moon.target, source=local("practice-moon-target-v1"), measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET, requested_dimensions=["TERRAIN", "THERMAL"])
        res, reg = flow.call(inp, datasets=datasets)
        assert isinstance(res.payload, CharacterizeTargetPayload), res.issues
        assert reg is not None
        return res.payload, reg.handles["profile"]

    unbound, h_unbound = characterize(["practice-moon-target-v1"])
    assert [(u.dimension, u.reason_code) for u in unbound.unavailable_dimensions] == [("THERMAL", "NO_COVERAGE")]
    assert not any(m.metric_id == "min_temperature_k" for m in unbound.metrics)

    bound, h_bound = characterize(["practice-moon-target-v1", "practice-moon-thermal-v1"])
    assert bound.unavailable_dimensions == []
    t = next(m for m in bound.metrics if m.metric_id == "min_temperature_k")
    assert t.value == pytest.approx(88.0, abs=1.0) and t.unit == "K"

    sc = screen(flow, bound, "mission-moon-gap")
    cand = candidate_ref(sc, B)
    _, handles = analyze(flow, cand)
    req = requirement(moon, "R-THERMAL")
    for th in (h_unbound, h_bound):
        row = compare(flow, req, cand, [th], handles).payload
        assert isinstance(row, CompareRequirementPayload)
        assert (row.proposed_status, row.reason_code) == ("UNKNOWN", "EARTH_EVIDENCE_MISSING")
    # the Moon scenario compares slope distributions at the 960 m common support
    ctx_row = compare(flow, requirement(moon, "R-TARGET-SLOPE-CONTEXT"), cand, [h_bound], handles).payload
    assert isinstance(ctx_row, CompareRequirementPayload)
    assert ctx_row.comparison_scale_m == 960.0 and ctx_row.measured_unit == "deg" and ctx_row.proposed_status in ("PASS", "FAIL")
    assert ctx_row.proposed_status == ("PASS" if ctx_row.measured_value <= 6.0 else "FAIL")  # type: ignore[operator]
    for rid in ("R-GRAVITY", "R-VACUUM"):
        gap = compare(flow, requirement(moon, rid), cand, [h_bound], handles).payload
        assert isinstance(gap, CompareRequirementPayload) and (gap.proposed_status, gap.reason_code) == ("GAP", "PHYSICAL_GAP")
