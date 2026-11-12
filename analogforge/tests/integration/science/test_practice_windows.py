"""SCN practice data: every architecture 40 section 4 window property (independent checker), the Mars/Moon target
fractions of section 3, parity with the library's slope code, and generator perturbations (the checked properties
change when a generator parameter changes - nothing is hard-coded)."""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fixtures" / "science"))
import window_checker as wc  # noqa: E402

from analogforge.science.features.coverage import coverage_summary  # noqa: E402
from analogforge.science.features.slope import analyze_surface  # noqa: E402
from analogforge.science.fixtures import practice  # noqa: E402
from analogforge.science.fixtures.practice_earth import MINERAL_CLASS_NAMES, WINDOW_IDS  # noqa: E402
from analogforge.science.geometry import PixelGeometry  # noqa: E402

EARTH = "practice-earth-grid-v1"


@pytest.fixture(scope="module")
def default_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("practice")
    practice.generate_all(out)
    return out


@cache
def _perturbed(key: tuple[tuple[str, Any], ...]) -> wc.GridAnalysis:
    """Regenerate only the Earth grid through the public API with changed parameters and analyse the files."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        practice.generate_all(tmp, only=[EARTH], **dict(key))
        return wc.read_practice_grid(Path(tmp))


def perturbed(**kwargs: Any) -> wc.GridAnalysis:
    return _perturbed(tuple(sorted(kwargs.items())))


def grid_of(directory: Path) -> wc.GridAnalysis:
    return wc.read_practice_grid(directory)


# ----------------------------------------------------------------------------------------------- the nine windows
def test_all_nine_windows_meet_every_property(default_dir: Path) -> None:
    reports = wc.check_all_windows(grid_of(default_dir))
    assert set(reports) == set(WINDOW_IDS)
    failures = {w: r.violations for w, r in reports.items() if not r.ok}
    assert failures == {}


def test_window_numbers_match_the_design_table(default_dir: Path) -> None:
    g = grid_of(default_dir)
    m = {w: wc.window_metrics(g, w) for w in WINDOW_IDS}
    assert 0.07 <= m["grid-r0c0"].f_band <= 0.15
    assert 0.25 <= m["grid-r0c1"].f_band <= 0.60
    assert m["grid-r0c2"].f_band == 0.0 and m["grid-r0c2"].max_slope_deg <= 3.0
    assert 0.02 <= m["grid-r1c0"].f_band <= 0.04
    assert m["grid-r1c1"].water_fraction >= 0.98
    assert 0.50 <= m["grid-r1c2"].valid_fraction <= 0.60
    assert 0.01 <= m["grid-r2c0"].f_band <= 0.03
    assert 0.0 < m["grid-r2c1"].f_band <= 0.01
    assert 0.06 <= m["grid-r2c2"].f_band <= 0.10
    # every window that must be analysable meets the 0.80 valid-land policy; the two excluded ones do not
    for w in WINDOW_IDS:
        if w not in ("grid-r1c1", "grid-r1c2"):
            assert m[w].valid_fraction >= 0.80, w
    assert m["grid-r1c1"].valid_fraction < 0.05 and m["grid-r1c2"].valid_fraction < 0.80


def test_screening_order_emerges_from_deficits(default_dir: Path) -> None:
    g = grid_of(default_dir)
    deficit = {w: wc.screening_deficit(wc.window_metrics(g, w).f_band) for w in WINDOW_IDS}
    zero = {w for w, d in deficit.items() if d == 0.0}
    assert zero == {"grid-r0c0", "grid-r0c1", "grid-r2c2"}  # A, B, KNOWN
    ranked = sorted(set(WINDOW_IDS) - zero - {"grid-r1c1", "grid-r1c2"}, key=lambda w: deficit[w])
    assert ranked == ["grid-r1c0", "grid-r2c0", "grid-r2c1", "grid-r0c2"]  # ROLLING_1, ROLLING_2, GENTLE, C


def test_start_component_properties_of_b_and_island_windows(default_dir: Path) -> None:
    g = grid_of(default_dir)
    for window, expect_band_in_start_component in (("grid-r0c0", True), ("grid-r0c1", False), ("grid-r2c2", False)):
        sl = wc.window_slices(window)
        wp = wc.auto_waypoints(g.slope[sl], g.valid[sl])
        band = wc.in_band(g.slope[sl]) & g.valid[sl]
        assert bool((wp.component & band).any()) is expect_band_in_start_component, window
        loop = wc.waypoint_return_loop(g.slope[sl], g.valid[sl], wp)
        assert loop.exposure_max_m < 100.0  # attempt 1 of the storyline earns no exposure
    sl = wc.window_slices("grid-r0c0")
    assert wc.exposure_route_exists(g.slope[sl], g.valid[sl], wc.auto_waypoints(g.slope[sl], g.valid[sl]))


def test_largest_safe_component_is_mainland_in_window_a(default_dir: Path) -> None:
    g = grid_of(default_dir)
    sl = wc.window_slices("grid-r0c1")
    safe = wc.safe_mask(g.slope[sl], g.valid[sl])
    labels, n = wc.components8(safe)
    sizes = sorted(np.bincount(labels.reshape(-1))[1:], reverse=True)
    assert n >= 2 and sizes[0] > sizes[1]
    main = wc.largest_component(safe)
    assert not (main & wc.in_band(g.slope[sl])).any()


def test_checker_matches_the_library_slope_code(default_dir: Path) -> None:
    """Decision C-01: same valid definition and the same slopes as science.features (independent implementations)."""
    g = grid_of(default_dir)
    import rasterio

    with rasterio.open(default_dir / EARTH / f"{EARTH}.tif") as src:
        elev = src.read(1).astype(np.float64)
        nodata = elev == src.nodata
    geom = PixelGeometry(dx_dcol=60.0, dy_dcol=0.0, dx_drow=0.0, dy_drow=-60.0)
    lib = analyze_surface(np.where(nodata, np.nan, elev), geom, nodata=nodata, water=g.water)
    assert np.array_equal(lib.valid, g.valid)
    both = lib.valid
    assert np.max(np.abs(lib.slope_deg[both] - g.slope[both])) < 1e-6
    for w in WINDOW_IDS:
        sl = wc.window_slices(w)
        summary = coverage_summary(lib.quality[sl])
        assert summary.valid_fraction == pytest.approx(wc.window_metrics(g, w).valid_fraction, abs=1e-12)


# ----------------------------------------------------------------------------------------------- targets
def test_mars_and_moon_target_fractions(default_dir: Path) -> None:
    mars = wc.mars_target_fractions(default_dir)
    for got, want in zip(mars, (0.40, 0.30, 0.20, 0.10), strict=True):
        assert abs(got - want) <= 0.03
    moon, n_cells = wc.moon_wedge_fractions(default_dir)
    assert n_cells > 800
    for got, want in zip(moon, (0.50, 0.30, 0.15, 0.05), strict=True):
        assert abs(got - want) <= 0.03


def test_minerals_are_categorical_and_valid_only_in_two_windows(default_dir: Path) -> None:
    import rasterio

    with rasterio.open(default_dir / "practice-earth-minerals-v1" / "practice-earth-minerals-v1.tif") as src:
        ids = src.read(1)
        assert src.nodata == 0 and str(ids.dtype) == "uint8"
    assert set(np.unique(ids)) <= {0, *MINERAL_CLASS_NAMES}
    fractions = {w: float((ids[wc.window_slices(w)] != 0).mean()) for w in WINDOW_IDS}
    assert fractions["grid-r0c0"] == pytest.approx(0.60, abs=0.001)
    assert fractions["grid-r2c2"] == pytest.approx(0.85, abs=0.001)
    assert all(v == 0.0 for w, v in fractions.items() if w not in ("grid-r0c0", "grid-r2c2"))
    assert len(set(np.unique(ids[ids != 0]))) == 4


def test_thermal_cold_trap(default_dir: Path) -> None:
    import rasterio

    with rasterio.open(default_dir / "practice-moon-thermal-v1" / "practice-moon-thermal-v1.tif") as src:
        t = src.read(1)
    assert float(t.min()) == 88.0 and 160.0 <= float(t[t > 100.0].min()) and float(t.max()) <= 250.0


# ----------------------------------------------------------------------------------------------- the checker itself
def test_checker_slope_is_exact_on_a_plane_and_marks_halo_invalid() -> None:
    k = np.tan(np.radians(15.0)) * 60.0
    rows, cols = np.mgrid[0:12, 0:12]
    elev = (k * cols + 3.0 * 0).astype(np.float64)
    slope, valid = wc.plane_fit_slope(elev, np.ones((12, 12), dtype=bool), 60.0)
    assert np.allclose(slope[valid], 15.0, atol=1e-9)
    assert not valid[0].any() and not valid[:, -1].any() and valid[1:-1, 1:-1].all()
    usable = np.ones((12, 12), dtype=bool)
    usable[5, 5] = False
    _, valid2 = wc.plane_fit_slope(elev, usable, 60.0)
    assert not valid2[4:7, 4:7].any() and valid2[3, 3]


def test_checker_detects_a_broken_window() -> None:
    """Failure path: a flat grid cannot satisfy window B's ramp properties."""
    flat = wc.analyze(np.zeros((192, 192)), np.zeros((192, 192), dtype=bool))
    report = wc.check_window(flat, "grid-r0c0")
    assert not report.ok and any("f_band" in v for v in report.violations)


# ----------------------------------------------------------------------------------------------- perturbations
def test_pert01_moat_zero_connects_the_island() -> None:
    g = perturbed(moat_cells=0)
    sl = wc.window_slices("grid-r0c1")
    wp = wc.auto_waypoints(g.slope[sl], g.valid[sl])
    band = wc.in_band(g.slope[sl]) & g.valid[sl]
    assert (wp.component & band).any()  # the band is now reachable
    loop = wc.waypoint_return_loop(g.slope[sl], g.valid[sl], wp)
    assert loop.exposure_max_m < 100.0  # attempt 1 (WAYPOINT_RETURN) still earns nothing: FAIL
    assert wc.exposure_route_exists(g.slope[sl], g.valid[sl], wp)  # attempt 2 (EXPOSURE_COVERAGE) can succeed
    report = wc.check_window(g, "grid-r0c1")
    assert any("start-reachable component contains band" in v for v in report.violations)
    default_grid = perturbed()
    default_sl = wc.window_slices("grid-r0c1")
    default_wp = wc.auto_waypoints(default_grid.slope[default_sl], default_grid.valid[default_sl])
    assert wc.check_window(default_grid, "grid-r0c1").ok
    assert not wc.exposure_route_exists(default_grid.slope[default_sl], default_grid.valid[default_sl], default_wp)


def test_pert02_ramp_slope_ten_removes_the_band() -> None:
    g = perturbed(ramp_slope_deg=10.0)
    m = wc.window_metrics(g, "grid-r0c0")
    assert m.f_band == 0.0 and m.max_slope_deg == pytest.approx(10.0, abs=0.1)
    assert not wc.check_window(g, "grid-r0c0").ok


def test_ramp_slope_above_cap_breaks_the_safe_property() -> None:
    g = perturbed(ramp_slope_deg=20.0)
    report = wc.check_window(g, "grid-r0c0")
    assert wc.window_metrics(g, "grid-r0c0").max_slope_deg > 18.0
    assert any("exceeds 18" in v for v in report.violations)


def test_ramp_slope_is_what_the_interior_tolerance_measures() -> None:
    g = perturbed(ramp_slope_deg=14.0)
    assert not wc.check_window(g, "grid-r0c0", ramp_target_deg=15.0).ok
    assert wc.check_window(g, "grid-r0c0", ramp_target_deg=14.0).ok


def test_narrow_ramp_fails_the_width_property() -> None:
    g = perturbed(ramp_width_cells=5.0)
    report = wc.check_window(g, "grid-r0c0")
    assert any("inscribed" in v for v in report.violations)
    assert wc.window_metrics(g, "grid-r0c0").f_band < wc.window_metrics(perturbed(), "grid-r0c0").f_band


def test_moat_thinner_than_four_cells_is_detected() -> None:
    g = perturbed(moat_cells=2)
    report = wc.check_window(g, "grid-r0c1")
    assert report.details["moat_cells_measured"] == pytest.approx(2.0, abs=0.01)
    assert any("moat" in v for v in report.violations)


def test_stripe_width_controls_the_valid_fraction() -> None:
    narrow = wc.window_metrics(perturbed(stripe_width=10), "grid-r1c2").valid_fraction
    wide = wc.window_metrics(perturbed(stripe_width=40), "grid-r1c2").valid_fraction
    assert wide < 0.5 < 0.6 < narrow
    assert not wc.check_window(perturbed(stripe_width=10), "grid-r1c2").ok


def test_seed_changes_bytes_not_properties(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    practice.generate_all(a, only=[EARTH], seed=1)
    practice.generate_all(b, only=[EARTH], seed=2)
    assert (a / EARTH / f"{EARTH}.tif").read_bytes() != (b / EARTH / f"{EARTH}.tif").read_bytes()
    for directory in (a, b):
        assert all(r.ok for r in wc.check_all_windows(wc.read_practice_grid(directory)).values())


def test_target_fractions_perturbation_shifts_the_measured_fractions(tmp_path: Path) -> None:
    practice.generate_all(tmp_path, target_fractions=((22.0, 1.0),), moon_fractions=((20.0, 1.0),))
    mars = wc.mars_target_fractions(tmp_path)
    assert mars[3] > 0.9
    moon, _ = wc.moon_wedge_fractions(tmp_path)
    assert moon[3] > 0.9


def test_unknown_generator_parameter_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        practice.generate_all(tmp_path, not_a_parameter=1)
    with pytest.raises(ValueError):
        practice.generate_all(tmp_path, target_fractions=((3.0, 0.5),))
