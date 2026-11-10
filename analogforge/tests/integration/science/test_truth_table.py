# ruff: noqa: E501
"""SCN-08: the qualification truth table of architecture 40 section 5, with an independent W1 oracle."""

from __future__ import annotations

import zipfile
from io import BytesIO
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


def independent_w1(grid_path: Path, target_fractions: list[float], support_m: float) -> float:
    """W1 at ``support_m`` re-derived from the stored grid with plain numpy/scipy (no science.* code)."""
    z = zipfile.ZipFile(grid_path)

    def arr(name: str) -> np.ndarray:
        return np.load(BytesIO(z.read(name + ".npy")))

    elev, quality, land = arr("elevation_m"), arr("quality"), arr("land")
    cell = 60.0
    f = round(support_m / cell)
    usable = land & np.isin(quality, (0, 3))
    h, w = (elev.shape[0] // f) * f, (elev.shape[1] // f) * f
    e = np.where(usable, elev, 0.0)[:h, :w].reshape(h // f, f, w // f, f).sum(axis=(1, 3))
    n = usable[:h, :w].reshape(h // f, f, w // f, f).sum(axis=(1, 3))
    ok = n == f * f
    mean = np.where(ok, e / np.maximum(n, 1), 0.0)
    # 3x3 least-squares plane through the centre of a full-support neighbourhood on a uniform grid
    valid = np.zeros_like(ok)
    gx = np.zeros_like(mean)
    gy = np.zeros_like(mean)
    for r in range(1, mean.shape[0] - 1):
        for c in range(1, mean.shape[1] - 1):
            blk = mean[r - 1 : r + 2, c - 1 : c + 2]
            if ok[r - 1 : r + 2, c - 1 : c + 2].all():
                valid[r, c] = True
                gx[r, c] = (blk[:, 2].sum() - blk[:, 0].sum()) / (6.0 * support_m)
                gy[r, c] = (blk[0, :].sum() - blk[2, :].sum()) / (6.0 * support_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))[valid]
    if slope.size == 0:
        return float("nan")  # no coarse cell has full support
    counts, _ = np.histogram(slope, bins=EDGES)
    frac = counts / counts.sum()
    return float(wasserstein_distance(CENTRES, CENTRES, frac, target_fractions))


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    ctx = make_practice_context(tmp_path_factory.mktemp("truth"))
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
    return flow, target, target_handle, out, grids


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
    flow, target, _, rows, grids = table
    assert target.slope_histogram is not None and target.slope_histogram.support_scale_m == 480.0
    seen = set()
    for w, path in grids.items():
        r = rows[w]["R-TARGET-SLOPE-CONTEXT"]
        w1 = independent_w1(path, list(target.slope_histogram.area_fraction), 480.0)
        if np.isnan(w1):  # the island window has no 480 m cell with a full 3x3 neighbourhood: honest UNKNOWN
            assert (r.proposed_status, r.reason_code) == ("UNKNOWN", "INSUFFICIENT_VALID_DATA")
            assert r.measured_value is None
            seen.add("NO_DATA")
            continue
        assert r.measured_unit == "deg" and r.comparison_scale_m == 480.0
        assert r.measured_value == pytest.approx(w1, abs=1e-9)
        assert (r.proposed_status == "PASS") == (w1 <= 6.0)
        seen.add(r.proposed_status)
    assert "PASS" in seen and "NO_DATA" in seen


def test_route_dependent_rows_are_preliminary_unknown(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for w in rows:
        for rid in ("R-EXPOSURE", "R-TASKS", "R-RESERVE"):
            r = rows[w][rid]
            assert (r.proposed_status, r.reason_code, r.evaluation_stage) == ("UNKNOWN", "ROUTE_NOT_VERIFIED", "PRELIMINARY")


def test_mineral_clearance_and_gap_rows(table) -> None:  # type: ignore[no-untyped-def]
    *_, rows, _ = table
    for w in rows:
        assert (rows[w]["R-MINERAL"].proposed_status, rows[w]["R-MINERAL"].reason_code) == ("UNKNOWN", "EARTH_EVIDENCE_MISSING")
        assert (rows[w]["R-CLEARANCE"].proposed_status, rows[w]["R-CLEARANCE"].reason_code) == ("UNKNOWN", "SCALE_UNSUPPORTED")
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
