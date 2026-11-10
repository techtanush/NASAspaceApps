# ruff: noqa: E501
"""SCN-08: the qualification truth table of architecture 40 section 5, with an independent W1 oracle."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import wasserstein_distance
from support.builders import load_mission, requirement
from support.practice import (
    Flow,
    analyze,
    candidate_ref,
    characterize_mars,
    compare,
    make_practice_context,
    screen,
    service,
)

from analogforge.ports import catalog
from analogforge.ports.science import EvidenceHandle
from analogforge.ports.science_payloads import CompareRequirementPayload

A, B, KNOWN = catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR, catalog.WINDOW_KNOWN_REFERENCE
R1, R2, C = catalog.WINDOW_ROLLING_1, catalog.WINDOW_ROLLING_2, catalog.WINDOW_C_FLAT
EDGES = [0, 2, 5, 8, 12, 15, 18, 25, 35, 90]
CENTRES = [1, 3.5, 6.5, 10, 13.5, 16.5, 21.5, 30, 62.5]


_TIF_NODATA = -32768.0


def _grid_meta(grid_path: Path) -> dict[str, float]:
    import json

    return json.loads(zipfile.ZipFile(grid_path).read("meta.json"))


def independent_w1(
    grid_path: Path, raw_dir: Path, target_fractions: list[float], support_m: float, min_valid_fraction: float = 0.8
) -> tuple[float, float]:
    """``(W1, coverage)`` at ``support_m`` for the window of a stored grid, derived from the RAW rasters.

    Only the window geometry (origin/size) is read from the stored grid's ``meta.json``; every elevation comes from
    the source GeoTIFF and the water mask, never from the stored (zero-filled) arrays.  A fine cell is usable when it
    is finite and not water; a coarse cell is the mean of a full ``f x f`` block of usable cells; the slope is the 3x3
    least-squares plane through full-support coarse neighbourhoods inside the window; coverage is the share of
    interior coarse cells (those that can have a 3x3 neighbourhood in a window-only grid) that obtained a slope.
    ``W1`` is NaN when no coarse cell has a slope.
    """
    import rasterio

    meta = _grid_meta(grid_path)
    with rasterio.open(raw_dir / "practice-earth-grid-v1.tif") as src:
        z_all = src.read(1).astype(float)
        t = src.transform
    with rasterio.open(raw_dir / "practice-earth-grid-v1-water.tif") as src:
        water_all = src.read(1) > 0
    cell = float(meta["cell_size_m"])
    c0 = round((meta["origin_x_m"] - t.c) / cell)
    r0 = round((t.f - meta["origin_y_m"]) / cell)
    h, w = int(meta["height"]), int(meta["width"])
    z = z_all[r0 : r0 + h, c0 : c0 + w]
    usable = (z != _TIF_NODATA) & np.isfinite(z) & ~water_all[r0 : r0 + h, c0 : c0 + w]
    f = round(support_m / cell)
    hh, ww = (h // f) * f, (w // f) * f
    zz = np.where(usable, z, 0.0)[:hh, :ww].reshape(hh // f, f, ww // f, f)
    n = usable[:hh, :ww].reshape(hh // f, f, ww // f, f).sum(axis=(1, 3))
    ok = n == f * f
    mean = np.where(ok, zz.sum(axis=(1, 3)) / (f * f), 0.0)
    slopes = []
    for r in range(1, mean.shape[0] - 1):
        for c in range(1, mean.shape[1] - 1):
            if ok[r - 1 : r + 2, c - 1 : c + 2].all():
                blk = mean[r - 1 : r + 2, c - 1 : c + 2]
                gx = (blk[:, 2].sum() - blk[:, 0].sum()) / (6.0 * support_m)
                gy = (blk[0, :].sum() - blk[2, :].sum()) / (6.0 * support_m)
                slopes.append(np.degrees(np.arctan(np.hypot(gx, gy))))
    eligible = max(0, mean.shape[0] - 2) * max(0, mean.shape[1] - 2)
    coverage = len(slopes) / eligible if eligible else 0.0
    if not slopes:
        return float("nan"), coverage
    counts, _ = np.histogram(np.asarray(slopes), bins=EDGES)
    frac = counts / counts.sum()
    return float(wasserstein_distance(CENTRES, CENTRES, frac, target_fractions)), coverage


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    root = tmp_path_factory.mktemp("truth")
    ctx = make_practice_context(root)
    flow = Flow(service(), ctx)
    target, target_handle = characterize_mars(flow)
    sc = screen(flow, target)
    mission = load_mission("mission-mars-mobility")
    out: dict[str, dict[str, CompareRequirementPayload]] = {}
    grids: dict[str, Path] = {}
    for wid in (A, B, KNOWN, R1, R2, C):
        cand = candidate_ref(sc, wid)
        _, handles = analyze(flow, cand)
        grids[wid] = ctx.artifact_paths[handles[0].artifact_sha256]  # type: ignore[index]
        rows: dict[str, CompareRequirementPayload] = {}
        for req in mission.requirements:
            res = compare(flow, req, cand, [target_handle], handles)
            assert isinstance(res.payload, CompareRequirementPayload), res.issues
            rows[req.id] = res.payload
        out[wid] = rows
    raw_dir = root / "data" / "practice-earth-grid-v1"
    return flow, target, target_handle, out, (grids, raw_dir)


def test_slope_availability_row(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for w in (A, B, KNOWN):
        r = rows[w]["R-SLOPE-AVAILABILITY"]
        assert (r.proposed_status, r.reason_code, r.evaluation_stage) == ("PASS", "MEETS_CRITERION", "FINAL")
        assert r.comparison_scale_m == 60.0
        # rubric (11): MEDIUM needs coverage >= 0.9; the island windows have 0.81-0.82 valid land coverage -> LOW
        assert r.confidence == ("MEDIUM" if w == B else "LOW")
    for w in (R1, R2, C):
        r = rows[w]["R-SLOPE-AVAILABILITY"]
        assert (r.proposed_status, r.reason_code) == ("FAIL", "INSUFFICIENT_EXPOSURE")
    assert rows[B]["R-SLOPE-AVAILABILITY"].measured_value == pytest.approx(0.1429, abs=0.02)
    assert rows[C]["R-SLOPE-AVAILABILITY"].measured_value == 0.0


def test_target_context_row_follows_independent_w1(table) -> None:  # type: ignore[no-untyped-def]
    flow, target, _, rows, (grids, raw_dir) = table
    assert target.slope_histogram is not None and target.slope_histogram.support_scale_m == 480.0
    seen = set()
    for w, path in grids.items():
        r = rows[w]["R-TARGET-SLOPE-CONTEXT"]
        w1, coverage = independent_w1(path, raw_dir, list(target.slope_histogram.area_fraction), 480.0)
        if np.isnan(w1) or coverage < 0.8:  # too little of the window carries a 480 m slope: honest UNKNOWN
            assert (r.proposed_status, r.reason_code) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA"), (w, coverage)
            assert r.measured_value is None
            seen.add("NO_DATA")
            continue
        assert r.measured_unit == "deg" and r.comparison_scale_m == 480.0
        assert r.measured_value == pytest.approx(w1, abs=1e-9), w
        assert (r.proposed_status == "PASS") == (w1 <= 6.0)
        seen.add(r.proposed_status)
    assert {"PASS", "FAIL", "NO_DATA"} <= seen


def test_flat_negative_control_w1_is_not_deflated_by_zero_filled_borders(table) -> None:  # type: ignore[no-untyped-def]
    """Regression: the stored grid holds 0 m on nodata/water; aggregating it invented cliffs (W1 3.595 vs 6.806)."""
    _, target, _, rows, (grids, raw_dir) = table
    assert target.slope_histogram is not None
    w1, coverage = independent_w1(grids[C], raw_dir, list(target.slope_histogram.area_fraction), 480.0)
    assert coverage >= 0.8 and w1 == pytest.approx(6.806451612903225, abs=1e-9)  # flat: all mass in the first bin
    r = rows[C]["R-TARGET-SLOPE-CONTEXT"]
    assert (r.proposed_status, r.reason_code) == ("FAIL", "DISTRIBUTION_MISMATCH")
    assert r.measured_value == pytest.approx(w1, abs=1e-9)


def test_route_dependent_rows_are_preliminary_unknown(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for w in rows:
        for rid in ("R-EXPOSURE", "R-TASKS", "R-RESERVE"):
            r = rows[w][rid]
            assert (r.proposed_status, r.reason_code, r.evaluation_stage) == (
                "UNKNOWN",
                "ROUTE_NOT_VERIFIED",
                "PRELIMINARY",
            )


def test_mineral_clearance_and_gap_rows(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for w in rows:
        assert (rows[w]["R-MINERAL"].proposed_status, rows[w]["R-MINERAL"].reason_code) == (
            "UNKNOWN",
            "EARTH_EVIDENCE_MISSING",
        )
        assert (rows[w]["R-CLEARANCE"].proposed_status, rows[w]["R-CLEARANCE"].reason_code) == (
            "UNKNOWN",
            "SCALE_UNSUPPORTED",
        )
        for rid in ("R-GRAVITY", "R-ATMOSPHERE"):
            assert (rows[w][rid].proposed_status, rows[w][rid].reason_code) == ("GAP", "PHYSICAL_GAP")


def test_confidence_never_high_and_gates_present(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for per_window in rows.values():
        for r in per_window.values():
            assert r.confidence in ("MEDIUM", "LOW") and r.confidence != "HIGH"
            assert {g.gate_id for g in r.adequacy.gates} >= {"SC-02", "SC-03", "SC-04", "SC-05", "SC-08", "SC-09"}
            sc08 = next(g for g in r.adequacy.gates if g.gate_id == "SC-08")
            assert sc08.outcome in ("SATISFIED", "NOT_ASSESSED", "NOT_APPLICABLE")


def test_scale_defect_is_detected_mechanically(table) -> None:  # type: ignore[no-untyped-def]
    """Using only the 60 m analysis-summary evidence for the 480 m context row gives SCALE_UNSUPPORTED, not a verdict."""
    flow, target, target_handle, _, _ = table
    sc_payload = screen(flow, target)
    cand = candidate_ref(sc_payload, B)
    _, handles = analyze(flow, cand)
    mission = load_mission("mission-mars-mobility")
    req = requirement(mission, "R-TARGET-SLOPE-CONTEXT")
    summary_only: list[EvidenceHandle] = [handles[1]]
    res = compare(flow, req, cand, [target_handle], summary_only)
    assert isinstance(res.payload, CompareRequirementPayload)
    assert (res.payload.proposed_status, res.payload.reason_code) == ("UNKNOWN", "SCALE_UNSUPPORTED")
    assert res.payload.comparison_scale_m == 60.0


def test_mode_mismatched_evidence_is_metadata_incomplete(table) -> None:  # type: ignore[no-untyped-def]
    flow, target, target_handle, _, _ = table
    cand = candidate_ref(screen(flow, target), B)
    _, handles = analyze(flow, cand)
    replay = handles[0].model_copy(update={"mode": "replay"})
    mission = load_mission("mission-mars-mobility")
    res = compare(flow, requirement(mission, "R-SLOPE-AVAILABILITY"), cand, [target_handle], [replay, handles[1]])
    assert isinstance(res.payload, CompareRequirementPayload)
    assert (res.payload.proposed_status, res.payload.reason_code) == ("UNKNOWN", "METADATA_INCOMPLETE")


def test_unknown_observable_is_underspecified(table) -> None:  # type: ignore[no-untyped-def]
    flow, target, target_handle, _, _ = table
    cand = candidate_ref(screen(flow, target), B)
    _, handles = analyze(flow, cand)
    mission = load_mission("mission-mars-mobility")
    odd = requirement(mission, "R-SLOPE-AVAILABILITY").model_copy(update={"observable": "made_up_observable"})
    res = compare(flow, odd, cand, [target_handle], handles)
    assert isinstance(res.payload, CompareRequirementPayload)
    assert (res.payload.proposed_status, res.payload.reason_code) == ("UNKNOWN", "REQUIREMENT_UNDERSPECIFIED")


def test_missing_evidence_is_blocked_not_guessed(table) -> None:  # type: ignore[no-untyped-def]
    flow, target, target_handle, _, _ = table
    from analogforge.ports.science_payloads import CompareRequirementInput

    cand = candidate_ref(screen(flow, target), B)
    mission = load_mission("mission-mars-mobility")
    inp = CompareRequirementInput(
        requirement=requirement(mission, "R-SLOPE-AVAILABILITY"), candidate=cand,
        target_evidence_ids=[target_handle.evidence_id], candidate_evidence_ids=[target_handle.evidence_id],
        observable_policy_id="slope-band-area-fraction-v1",
    )  # fmt: skip
    res, _ = flow.call(inp, evidence=[], check_registrar=False)
    assert res.status.value == "BLOCKED" and res.payload is None
