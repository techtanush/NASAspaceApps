"""SCN-01: terrain feature oracles (GEO-01..GEO-07): slope/aspect, roughness, relief, histograms, zones, coverage.

Expected values are derived analytically (planes, paraboloids, closed-form residuals) or from an independent
NumPy implementation -- never from the production function under test.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from analogforge.ports.science_payloads import Histogram
from analogforge.science.errors import RasterError
from analogforge.science.features.connected import (
    Band,
    connected_zones,
    label_components,
    largest_component,
    safe_mask,
    to_port_zone,
)
from analogforge.science.features.coverage import (
    QUALITY_NO_FULL_SUPPORT,
    QUALITY_NODATA,
    QUALITY_OK,
    QUALITY_OUTSIDE_SOURCE,
    QUALITY_WATER,
    classify_cells,
    coverage_summary,
    is_water_only,
)
from analogforge.science.features.histogram import (
    SLOPE_HIST_CENTRES,
    SLOPE_HIST_EDGES,
    area_weighted_histogram,
    band_area_fraction,
    band_label,
    bin_centres,
    slope_area_metric_id,
    slope_statistics,
    to_port_histogram,
    weighted_quantile,
)
from analogforge.science.features.relief import robust_relief_m
from analogforge.science.features.roughness import (
    detrended_rms_height_m,
    relief_metric_id,
    roughness_metric_id,
    tpi_m,
)
from analogforge.science.features.slope import (
    analyze_surface,
    aspect_from_gradient,
    compute_slope_aspect,
    directional_grade_deg,
    plane_fit_gradient,
    plane_stencil,
)
from analogforge.science.geometry import PixelGeometry
from analogforge.science.raster.masks import (
    dilate,
    dilate_metres,
    fraction,
    full_support,
    nodata_mask,
    usable_mask,
)

N = 101
SPACING = 10.0


def plane(
    a: float, b: float, c: float, *, rows: int = N, cols: int = N, sx: float = SPACING, sy: float = SPACING
) -> np.ndarray:
    """z = a*x + b*y + c with x east (column * sx) and y north (-row * sy), centred on the raster."""
    jj, ii = np.meshgrid(np.arange(cols, dtype=float), np.arange(rows, dtype=float))
    x = (jj - cols // 2) * sx
    y = -(ii - rows // 2) * sy
    return a * x + b * y + c


def interior(arr: np.ndarray, margin: int = 2) -> np.ndarray:
    return arr[margin:-margin, margin:-margin]


GEOM = PixelGeometry.north_up(SPACING)
ALL = np.ones((N, N), dtype=bool)


# ----------------------------------------------------------------------------- GEO-01 / GEO-02 / GEO-03
def test_geo01_flat_plane_has_zero_slope_null_aspect_and_zero_roughness() -> None:
    z = np.full((N, N), 100.0)
    field = compute_slope_aspect(z, ALL, GEOM)
    assert field.valid[1:-1, 1:-1].all()
    assert np.abs(field.slope_deg[1:-1, 1:-1]).max() <= 1e-12
    assert np.isnan(field.aspect_deg[1:-1, 1:-1]).all()  # aspect is null on a flat plane, not 0
    for w in (3, 5, 9):
        rms, ok = detrended_rms_height_m(z, ALL, w)
        assert np.abs(rms[ok]).max() <= 1e-9
        relief, _ = robust_relief_m(z, ALL, w)
        assert np.abs(relief[ok]).max() == 0.0


@pytest.mark.parametrize("angle", [5.0, 10.0, 12.0, 20.0, 35.0, 60.0, 80.0])
def test_geo02_inclined_plane_slope_is_exact_to_1e6_degrees(angle: float) -> None:
    z = plane(math.tan(math.radians(angle)), 0.0, 100.0)
    field = compute_slope_aspect(z, ALL, GEOM)
    inner = interior(field.slope_deg)
    assert np.abs(inner - angle).max() <= 1e-6
    # directional grade along +x equals the surface slope; along +y it is zero (GEO-03)
    long_x, cross_x = directional_grade_deg(field.dz_dx, field.dz_dy, 1.0, 0.0)
    long_y, cross_y = directional_grade_deg(field.dz_dx, field.dz_dy, 0.0, 1.0)
    assert np.abs(interior(long_x) - angle).max() <= 1e-6
    assert np.abs(interior(cross_x)).max() <= 1e-9
    assert np.abs(interior(long_y)).max() <= 1e-9  # contour travel: zero grade on a steep hillside
    assert np.abs(interior(cross_y) - angle).max() <= 1e-6 or np.abs(interior(cross_y) + angle).max() <= 1e-6


def test_slope_is_strictly_monotone_in_plane_gradient_and_orientation_invariant() -> None:
    previous = -1.0
    for angle in (1.0, 4.0, 9.0, 16.0, 25.0):
        s = compute_slope_aspect(plane(math.tan(math.radians(angle)), 0.0, 0.0), ALL, GEOM).slope_deg[50, 50]
        assert s > previous
        previous = s
    ang = math.radians(18.0)
    gx = compute_slope_aspect(plane(math.tan(ang), 0.0, 0.0), ALL, GEOM).slope_deg[50, 50]
    gy = compute_slope_aspect(plane(0.0, math.tan(ang), 0.0), ALL, GEOM).slope_deg[50, 50]
    gd = compute_slope_aspect(plane(math.tan(ang) * math.cos(0.7), math.tan(ang) * math.sin(0.7), 0.0), ALL, GEOM)
    assert gx == pytest.approx(18.0, abs=1e-6) and gy == pytest.approx(18.0, abs=1e-6)
    assert gd.slope_deg[50, 50] == pytest.approx(18.0, abs=1e-6)


@pytest.mark.parametrize(
    ("a", "b", "azimuth"),
    [(0.3, 0.0, 270.0), (-0.3, 0.0, 90.0), (0.0, 0.3, 180.0), (0.0, -0.3, 0.0), (0.3, 0.3, 225.0), (-0.3, 0.3, 135.0)],
)
def test_aspect_is_downslope_azimuth_clockwise_from_north(a: float, b: float, azimuth: float) -> None:
    field = compute_slope_aspect(plane(a, b, 0.0), ALL, GEOM)
    assert field.aspect_deg[50, 50] == pytest.approx(azimuth, abs=1e-6)  # terrain rising east -> faces west (270)


def test_aspect_flat_tolerance_is_explicit() -> None:
    gx, gy = np.array([1e-13, 1e-3]), np.array([0.0, 0.0])
    aspect = aspect_from_gradient(gx, gy, flat_gradient_tolerance=1e-12)
    assert np.isnan(aspect[0]) and aspect[1] == pytest.approx(270.0)
    assert not np.isnan(aspect_from_gradient(gx, gy, flat_gradient_tolerance=0.0)[0])


# ----------------------------------------------------------------------------- GEO-04 / GEO-05
def test_geo04_anisotropic_spacing_recovers_the_true_gradient() -> None:
    a, b = 0.21, -0.37
    sx, sy = 10.0, 30.0
    z = plane(a, b, 5.0, sx=sx, sy=sy)
    geom = PixelGeometry.north_up(sx, sy)
    grad = plane_fit_gradient(z, ALL, geom)
    assert np.abs(interior(grad.dz_dx) - a).max() <= 1e-12 and np.abs(interior(grad.dz_dy) - b).max() <= 1e-12
    expected = math.degrees(math.atan(math.hypot(a, b)))
    assert np.abs(interior(compute_slope_aspect(z, ALL, geom).slope_deg) - expected).max() <= 1e-9
    # the same physical surface on a square 10 m grid gives the same slope: no square-pixel assumption
    square = plane(a, b, 5.0)
    assert compute_slope_aspect(square, ALL, GEOM).slope_deg[50, 50] == pytest.approx(expected, abs=1e-9)
    # perturbation: pretending the grid is square would be wrong
    wrong = compute_slope_aspect(z, ALL, GEOM).slope_deg[50, 50]
    assert abs(wrong - expected) > 1.0


@pytest.mark.parametrize("angle_deg", [30.0, 90.0, 137.0, -15.0])
def test_geo05_rotated_affine_gives_the_same_physical_slope_and_aspect(angle_deg: float) -> None:
    a, b = 0.25, 0.10
    geom = PixelGeometry.rotated(10.0, 10.0, angle_deg)
    jj, ii = np.meshgrid(np.arange(N, dtype=float), np.arange(N, dtype=float))
    x = jj * geom.dx_dcol + ii * geom.dx_drow
    y = jj * geom.dy_dcol + ii * geom.dy_drow
    z = a * x + b * y + 100.0
    field = compute_slope_aspect(z, ALL, geom)
    expected = math.degrees(math.atan(math.hypot(a, b)))
    expected_aspect = math.degrees(math.atan2(-a, -b)) % 360.0
    assert np.abs(interior(field.slope_deg) - expected).max() <= 1e-9
    assert np.abs(interior(field.aspect_deg) - expected_aspect).max() <= 1e-7
    # anisotropic AND rotated
    geom2 = PixelGeometry.rotated(10.0, 30.0, angle_deg)
    x2 = jj * geom2.dx_dcol + ii * geom2.dx_drow
    y2 = jj * geom2.dy_dcol + ii * geom2.dy_drow
    field2 = compute_slope_aspect(a * x2 + b * y2, ALL, geom2)
    assert np.abs(interior(field2.slope_deg) - expected).max() <= 1e-9


def test_plane_stencil_matches_the_classic_square_grid_result() -> None:
    d_dx, d_dy = plane_stencil(GEOM)
    # for a square unrotated grid the least-squares plane gradient is the 3-row/3-column Prewitt stencil
    expected_dx = np.array([[-1, 0, 1]] * 3) / (6 * SPACING)
    assert np.allclose(d_dx, expected_dx, atol=1e-15)
    assert np.allclose(d_dy, -expected_dx.T, atol=1e-15)  # rows run south: +row is -y


# ----------------------------------------------------------------------------- GEO-06: nodata halo
def test_geo06_nodata_invalidates_exactly_its_3x3_halo_and_is_never_zero_filled() -> None:
    z = plane(math.tan(math.radians(12.0)), 0.0, 100.0)
    missing = np.zeros((N, N), dtype=bool)
    missing[40, 60] = True
    clean = analyze_surface(z, GEOM, nodata=np.zeros_like(missing))
    for fill in (0.0, -32768.0, 1e6, np.nan):
        zz = z.copy()
        zz[missing] = fill
        res = analyze_surface(zz, GEOM, nodata=missing)
        halo = np.zeros_like(missing)
        halo[39:42, 59:62] = True
        interior_ok = np.zeros_like(missing)
        interior_ok[1:-1, 1:-1] = True
        assert not res.valid[halo].any()
        assert res.valid[interior_ok & ~halo].all()
        assert np.isnan(res.slope_deg[halo]).all()  # invalid, not "0 deg"
        both = res.valid & clean.valid
        assert np.array_equal(res.slope_deg[both], clean.slope_deg[both])  # unaffected by the fill value
        assert (res.quality[missing] == QUALITY_NODATA).all()
        assert (res.quality[halo & ~missing] == QUALITY_NO_FULL_SUPPORT).all()


def test_raster_border_is_nodata_not_zero_slope() -> None:
    res = analyze_surface(plane(0.2, 0.0, 0.0), GEOM)
    border = np.ones((N, N), dtype=bool)
    border[1:-1, 1:-1] = False
    assert not res.valid[border].any() and np.isnan(res.slope_deg[border]).all()
    assert (res.quality[border] == QUALITY_NO_FULL_SUPPORT).all() and (res.quality[~border] == QUALITY_OK).all()


def test_water_neighbours_invalidate_slope_and_land_flag_is_reported() -> None:
    z = plane(0.3, 0.0, 10.0)
    water = np.zeros((N, N), dtype=bool)
    water[50:55, 50:55] = True
    res = analyze_surface(z, GEOM, water=water)
    assert not res.land[water].any() and res.land[~water].all()
    assert not res.valid[49:56, 49:56].any()  # water plus one-cell halo
    assert res.valid[10, 10] and not (res.valid & ~res.land).any()
    assert (res.quality[water] == QUALITY_WATER).all()
    assert res.quality[49, 49] == QUALITY_NO_FULL_SUPPORT


def test_derivatives_are_computed_before_cropping_so_window_halo_is_real_data() -> None:
    z = plane(0.2, 0.1, 0.0)
    whole = analyze_surface(z, GEOM)
    r0, c0, h, w = 20, 30, 16, 16
    cropped_from_whole = whole.valid[r0 : r0 + h, c0 : c0 + w]
    alone = analyze_surface(z[r0 : r0 + h, c0 : c0 + w], GEOM)
    assert cropped_from_whole.all()  # window border cells keep their real neighbours
    assert not alone.valid.all() and alone.valid.sum() == (h - 2) * (w - 2)
    assert np.array_equal(whole.slope_deg[r0 : r0 + h, c0 : c0 + w][alone.valid], alone.slope_deg[alone.valid])


def test_slope_input_validation() -> None:
    with pytest.raises(RasterError):
        plane_fit_gradient(np.zeros((4, 4)), np.ones((4, 5), dtype=bool), GEOM)
    with pytest.raises(RasterError):
        analyze_surface(np.zeros((4, 4)), GEOM, nodata=np.zeros((3, 3), dtype=bool))
    with pytest.raises(RasterError):
        analyze_surface(np.zeros((4, 4)), GEOM, water=np.zeros((3, 3), dtype=bool))
    with pytest.raises(RasterError):
        directional_grade_deg(np.zeros(2), np.zeros(2), 0.0, 0.0)


# ----------------------------------------------------------------------------- bump (paraboloid)
def test_paraboloid_bump_slope_and_roughness_follow_closed_forms() -> None:
    k, s = 0.01, 10.0
    jj, ii = np.meshgrid(np.arange(41.0), np.arange(41.0))
    x, y = (jj - 20) * s, -(ii - 20) * s
    z = 500.0 - k * (x * x + y * y)
    res = compute_slope_aspect(z, np.ones(z.shape, dtype=bool), PixelGeometry.north_up(s))
    r = np.hypot(x, y)
    expected = np.degrees(np.arctan(2 * k * r))  # |grad z| = 2 k r ; odd moments vanish so the LSQ plane is exact
    assert np.abs(interior(res.slope_deg, 1) - interior(expected, 1)).max() <= 1e-9
    assert res.slope_deg[20, 20] == pytest.approx(0.0, abs=1e-12)
    # a peak: downslope aspect points away from the summit (east of the summit faces east = 90)
    assert res.aspect_deg[20, 30] == pytest.approx(90.0, abs=1e-6) and res.aspect_deg[10, 20] == pytest.approx(
        0.0, abs=1e-6
    )
    # detrended 3x3 RMS of z = c + k(u^2 + v^2): residual about the mean -> rms = 2 k s^2 / 3 everywhere
    rms, ok = detrended_rms_height_m(z, np.ones(z.shape, dtype=bool), 3)
    assert np.abs(rms[ok] - 2 * k * s * s / 3).max() <= 1e-10
    # perturbation: doubling the curvature doubles the roughness
    rms2, _ = detrended_rms_height_m(500.0 - 2 * k * (x * x + y * y), np.ones(z.shape, dtype=bool), 3)
    assert np.abs(rms2[ok] / rms[ok] - 2.0).max() <= 1e-9


# ----------------------------------------------------------------------------- GEO-07: roughness oracles
@pytest.mark.parametrize("window", [3, 5, 9])
def test_plane_roughness_is_zero_within_1e9_even_on_large_offsets(window: int) -> None:
    z = plane(math.tan(math.radians(20.0)), -0.3, 1234.5)
    rms, ok = detrended_rms_height_m(z, ALL, window)
    assert ok.sum() == (N - window + 1) ** 2
    assert np.abs(rms[ok]).max() <= 1e-9


def test_geo07_known_residual_pattern_matches_manual_projection() -> None:
    eps = 0.37
    z = np.zeros((7, 7))
    ii, jj = np.meshgrid(np.arange(7) - 3, np.arange(7) - 3, indexing="ij")
    # a plane plus eps*i*j, where i*j is orthogonal to {1, i, j} over a window centred on (3, 3)
    z = 2.0 + 0.5 * jj - 0.25 * ii + eps * ii * jj
    usable = np.ones((7, 7), dtype=bool)
    rms3, _ = detrended_rms_height_m(z, usable, 3)
    rms5, _ = detrended_rms_height_m(z, usable, 5)
    # window 3: residual = eps*i*j -> sum(i*j)^2 over the 9 cells = 4 (the four corners) -> rms = eps*sqrt(4/9)
    assert rms3[3, 3] == pytest.approx(eps * 2.0 / 3.0, abs=1e-12)
    # window 5: sum((i*j)^2) = (sum i^2)^2 = 10^2 = 100 over 25 cells -> rms = eps*sqrt(100/25) = 2 eps
    assert rms5[3, 3] == pytest.approx(2.0 * eps, abs=1e-12)
    # a naive alternating pattern is partly absorbed by the plane fit: it must NOT be used as a naive oracle
    alt = 2.0 + 0.5 * jj + 0.1 * (-1.0) ** (ii + jj)
    naive = 0.1
    assert detrended_rms_height_m(alt, usable, 3)[0][3, 3] != pytest.approx(naive, abs=1e-6)


@pytest.mark.parametrize("window", [3, 5, 9])
def test_roughness_matches_an_independent_lstsq_implementation(window: int) -> None:
    rng = np.random.default_rng(20261105)
    z = rng.normal(0.0, 3.0, (21, 21)) + plane(0.2, -0.1, 50.0, rows=21, cols=21)
    usable = np.ones(z.shape, dtype=bool)
    rms, ok = detrended_rms_height_m(z, usable, window)
    h = window // 2
    for r, c in ((h, h), (10, 10), (21 - h - 1, 5), (7, 21 - h - 1)):
        patch = z[r - h : r + h + 1, c - h : c + h + 1]
        ii, jj = np.meshgrid(np.arange(window), np.arange(window), indexing="ij")
        design = np.column_stack([np.ones(window * window), ii.ravel(), jj.ravel()])
        coef, *_ = np.linalg.lstsq(design, patch.ravel(), rcond=None)
        resid = patch.ravel() - design @ coef
        assert rms[r, c] == pytest.approx(math.sqrt(float(np.mean(resid**2))), abs=1e-10)
    assert not ok[:h].any() and not ok[:, -h:].any()


def test_roughness_requires_full_window_support() -> None:
    z = plane(0.1, 0.0, 0.0)
    usable = np.ones((N, N), dtype=bool)
    usable[50, 50] = False
    rms, ok = detrended_rms_height_m(z, usable, 5)
    assert not ok[48:53, 48:53].any() and np.isnan(rms[48:53, 48:53]).all()
    assert ok[47, 47] and ok[53, 53]  # windows that do not touch the missing cell stay valid
    assert ok[10, 10] and not ok[0, 0]
    with pytest.raises(RasterError):
        detrended_rms_height_m(z, usable, 4)
    with pytest.raises(RasterError):
        detrended_rms_height_m(z, usable[:-1], 3)


def test_metric_ids_carry_the_physical_window() -> None:
    assert roughness_metric_id(3, 60.0) == "detrended_rms_height_m@180"
    assert roughness_metric_id(9, 60.0) == "detrended_rms_height_m@540"
    assert relief_metric_id(5, 60.0) == "robust_relief_m@300"
    assert (
        slope_area_metric_id(12, 18) == "slope_area_fraction:12-18" == f"slope_area_fraction:{band_label(12.0, 18.0)}"
    )


# ----------------------------------------------------------------------------- relief / TPI
@pytest.mark.parametrize("window", [3, 5, 9])
def test_ramp_robust_relief_is_analytic(window: int) -> None:
    g = 0.2
    z = plane(g, 0.0, 10.0)
    relief, ok = robust_relief_m(z, ALL, window)
    # q05 and q95 land in the extreme columns of the window: relief = (window - 1) * spacing * g
    assert np.abs(relief[ok] - (window - 1) * SPACING * g).max() <= 1e-9


def test_relief_matches_numpy_quantiles_on_random_terrain() -> None:
    rng = np.random.default_rng(7)
    z = rng.normal(0, 5.0, (30, 30))
    usable = np.ones(z.shape, dtype=bool)
    relief, ok = robust_relief_m(z, usable, 5)
    for r, c in ((2, 2), (15, 15), (27, 10)):
        patch = z[r - 2 : r + 3, c - 2 : c + 3].ravel()
        expected = np.quantile(patch, 0.95) - np.quantile(patch, 0.05)
        assert relief[r, c] == pytest.approx(expected, abs=1e-12)
    wide, _ = robust_relief_m(z, usable, 5, q_low=0.0, q_high=1.0)
    assert (wide[ok] >= relief[ok] - 1e-12).all()  # perturbation: wider quantiles never shrink relief
    with pytest.raises(RasterError):
        robust_relief_m(z, usable, 5, q_low=0.9, q_high=0.1)
    with pytest.raises(RasterError):
        robust_relief_m(z, usable, 2)


def test_relief_is_unknown_not_zero_near_nodata() -> None:
    z = plane(0.1, 0.0, 0.0)
    usable = np.ones((N, N), dtype=bool)
    usable[20, 20] = False
    relief, ok = robust_relief_m(z, usable, 3)
    assert np.isnan(relief[19:22, 19:22]).all() and not ok[19:22, 19:22].any()


def test_tpi_of_a_single_spike() -> None:
    z = np.zeros((5, 5))
    z[2, 2] = 9.0
    tpi, ok = tpi_m(z, np.ones((5, 5), dtype=bool), 3)
    assert tpi[2, 2] == pytest.approx(9.0 - 1.0)  # centre minus the 3x3 mean (which includes the centre)
    assert tpi[1, 1] == pytest.approx(0.0 - 1.0) and ok[1:4, 1:4].all() and not ok[0].any()


# ----------------------------------------------------------------------------- histograms
def test_histogram_constants_are_the_specified_edges_and_centres() -> None:
    assert SLOPE_HIST_EDGES == (0, 2, 5, 8, 12, 15, 18, 25, 35, 90)
    assert SLOPE_HIST_CENTRES == (1, 3.5, 6.5, 10, 13.5, 16.5, 21.5, 30, 62.5)
    assert bin_centres(SLOPE_HIST_EDGES) == SLOPE_HIST_CENTRES


def test_area_weighted_histogram_bins_are_half_open_and_sum_to_one() -> None:
    values = np.array([0.0, 1.999999, 2.0, 11.999999, 12.0, 14.999999, 15.0, 18.0, 34.9, 35.0, 89.999, 90.0])
    valid = np.ones(values.shape, dtype=bool)
    hist = area_weighted_histogram(values, valid, 3600.0)
    counts = np.array(hist.area_m2) / 3600.0
    assert counts.tolist() == [2.0, 1.0, 0.0, 1.0, 2.0, 1.0, 1.0, 1.0, 3.0]
    # exact edge values go to the upper bin: 12.0 is in [12,15), 15.0 in [15,18), 18.0 in [18,25), 35.0 in [35,90]
    assert hist.area_m2[4] == 2 * 3600.0 and hist.area_m2[5] == 3600.0 and hist.area_m2[6] == 3600.0
    assert hist.area_m2[8] == 3 * 3600.0  # 35.0, 89.999 and the closed final edge 90.0
    assert sum(hist.area_fraction) == pytest.approx(1.0, abs=1e-12) and hist.valid_area_m2 == 12 * 3600.0


def test_histogram_is_area_weighted_and_ignores_invalid_cells() -> None:
    values = np.array([[1.0, 10.0], [20.0, np.nan]])
    valid = np.array([[True, True], [True, False]])
    areas = np.array([[100.0, 300.0], [600.0, 1e9]])
    hist = area_weighted_histogram(values, valid, areas)
    assert hist.area_m2[0] == 100.0 and hist.area_m2[3] == 300.0 and hist.area_m2[6] == 600.0
    assert hist.area_fraction[6] == pytest.approx(0.6)
    empty = area_weighted_histogram(values, np.zeros((2, 2), dtype=bool), 1.0)
    assert (
        empty.valid_area_m2 == 0.0 and sum(empty.area_fraction) == 0.0
    )  # unknown stays distinguishable via valid area


def test_histogram_failure_paths() -> None:
    ok = np.array([True])
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([-0.5]), ok, 1.0)
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([90.5]), ok, 1.0)
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([np.nan]), ok, 1.0)  # NaN under a valid flag is a bug, never a bin
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([1.0]), ok, 0.0)
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([1.0]), ok, 1.0, edges=(0.0, 0.0, 1.0))
    with pytest.raises(RasterError):
        area_weighted_histogram(np.array([1.0, 2.0]), ok, 1.0)


def test_band_fraction_upper_bound_is_exclusive_unless_requested() -> None:
    values = np.array([11.99, 12.0, 15.0, 17.999, 18.0, 18.0001])
    valid = np.ones(values.shape, dtype=bool)
    assert band_area_fraction(values, valid, 12.0, 18.0, 1.0) == pytest.approx(3 / 6)
    assert band_area_fraction(values, valid, 12.0, 18.0, 1.0, upper_inclusive=True) == pytest.approx(4 / 6)
    assert band_area_fraction(values, np.zeros(6, dtype=bool), 12.0, 18.0, 1.0) is None  # unknown, not 0
    with pytest.raises(RasterError):
        band_area_fraction(values, valid, 18.0, 12.0, 1.0)


def test_weighted_quantiles_and_statistics() -> None:
    v = np.array([1.0, 2.0, 3.0, 4.0])
    assert weighted_quantile(v, np.ones(4), 0.5) == 2.0
    assert weighted_quantile(v, np.array([1.0, 1.0, 1.0, 97.0]), 0.5) == 4.0  # area weight dominates
    assert weighted_quantile(v, np.ones(4), 1.0) == 4.0 and weighted_quantile(v, np.ones(4), 0.0) == 1.0
    assert weighted_quantile(np.array([]), np.array([]), 0.5) is None
    stats = slope_statistics(np.array([2.0, 4.0, 6.0, 20.0]), np.ones(4, dtype=bool), 10.0)
    assert stats["mean"] == pytest.approx(8.0) and stats["max"] == 20.0 and stats["p50"] == 4.0
    none = slope_statistics(np.array([1.0]), np.array([False]), 10.0)
    assert none == {"p05": None, "p50": None, "p95": None, "mean": None, "max": None}
    with pytest.raises(RasterError):
        weighted_quantile(v, np.ones(4), 1.5)


def test_port_histogram_conversion_validates_against_the_kit_model() -> None:
    values = np.array([3.0, 7.0, 14.0, 22.0])
    hist = area_weighted_histogram(values, np.ones(4, dtype=bool), 3600.0)
    port = to_port_histogram(hist, support_scale_m=60.0)
    assert isinstance(port, Histogram) and port.support_scale_m == 60.0 and port.valid_area_m2 == 4 * 3600.0
    assert port.metric_id == "surface_slope_deg" and port.unit == "deg" and port.edges == list(SLOPE_HIST_EDGES)
    empty = to_port_histogram(area_weighted_histogram(values, np.zeros(4, dtype=bool), 1.0), support_scale_m=60.0)
    assert empty.valid_area_m2 == 0.0


# ----------------------------------------------------------------------------- connected zones
def test_zones_are_8_connected_and_isolated_by_water_moats() -> None:
    slope = np.full((24, 24), 3.0)
    water = np.zeros((24, 24), dtype=bool)
    water[8:16, 8:16] = True
    water[10:14, 10:14] = False  # island inside a 2-cell moat
    slope[10:14, 10:14] = 15.0  # the "mesa" holds all of the 12-18 band
    valid = ~water
    safe = safe_mask(slope, valid, valid, 18.0)
    zones, labels = connected_zones(safe, slope, 3600.0, [Band(12.0, 18.0)], start_cell=(1, 1))
    assert [z.zone_id for z in zones] == ["zone-1", "zone-2"]
    mainland, island = zones
    assert mainland.contains_start and not island.contains_start
    assert (
        island.band_area_m2["12-18"] == 16 * 3600.0 and mainland.band_area_m2["12-18"] == 0.0
    )  # start zone has no band
    assert island.cell_count == 16 and mainland.cell_count > island.cell_count
    assert labels[1, 1] == mainland.label and labels[11, 11] == island.label
    port = to_port_zone(island, (1.0, 2.0, 3.0, 4.0))
    assert port.area_m2 == 16 * 3600.0 and port.bbox_lonlat == (1.0, 2.0, 3.0, 4.0) and not port.contains_start


def test_diagonal_cells_connect_with_8_but_not_4_connectivity() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[1, 1] = mask[2, 2] = mask[3, 3] = True
    assert label_components(mask, 8)[1] == 1 and label_components(mask, 4)[1] == 3
    with pytest.raises(RasterError):
        label_components(mask, 6)


def test_safe_mask_uses_inclusive_cap_and_excludes_invalid_and_water() -> None:
    slope = np.array([[17.999, 18.0, 18.001, np.nan]])
    valid = np.array([[True, True, True, False]])
    land = np.array([[True, True, True, True]])
    assert safe_mask(slope, valid, land, 18.0).tolist() == [[True, True, False, False]]
    assert safe_mask(slope, valid, np.array([[False, True, True, True]]), 18.0).tolist() == [
        [False, True, False, False]
    ]
    assert safe_mask(slope, valid, land, 12.0).sum() == 0  # a lower rover cap shrinks the safe set (never relaxed)
    with pytest.raises(RasterError):
        safe_mask(slope, valid[:, :2], land, 18.0)


def test_disconnected_patches_do_not_form_one_zone() -> None:
    slope = np.full((10, 10), 14.0)
    slope[:, 5] = 40.0  # a steep wall splits the window in two
    safe = safe_mask(slope, np.ones((10, 10), dtype=bool), np.ones((10, 10), dtype=bool), 18.0)
    zones, _ = connected_zones(safe, slope, 100.0, [Band(12.0, 18.0)])
    assert len(zones) == 2 and zones[0].band_area_m2["12-18"] == zones[0].cell_count * 100.0
    assert all(not z.contains_start for z in zones)
    assert zones[0].first_cell < zones[1].first_cell or zones[0].cell_count > zones[1].cell_count
    tiny, _ = connected_zones(safe, slope, 100.0, min_cells=1000)
    assert tiny == []
    with pytest.raises(RasterError):
        connected_zones(safe, slope, 100.0, start_cell=(99, 99))


def test_largest_component_tie_goes_to_first_row_major_cell() -> None:
    safe = np.zeros((6, 6), dtype=bool)
    safe[0:2, 4:6] = True  # first in row-major order, 4 cells
    safe[4:6, 0:2] = True  # 4 cells too
    best = largest_component(safe)
    assert best is not None and best[0, 4] and not best[4, 0]
    safe[3, 3] = safe[2, 2] = True  # 8-connected pair, smaller
    assert int(largest_component(safe).sum()) == 4  # type: ignore[union-attr]
    assert largest_component(np.zeros((3, 3), dtype=bool)) is None


# ----------------------------------------------------------------------------- coverage and masks
def test_quality_codes_follow_the_documented_precedence() -> None:
    nodata = np.array([[True, False, False, False, False]])
    water = np.array([[True, True, False, False, False]])
    valid = np.array([[False, False, False, True, False]])
    outside = np.array([[False, False, False, False, True]])
    q = classify_cells(nodata, water, valid, outside)
    assert q.tolist() == [[QUALITY_NODATA, QUALITY_WATER, QUALITY_NO_FULL_SUPPORT, QUALITY_OK, QUALITY_OUTSIDE_SOURCE]]
    summary = coverage_summary(q)
    assert summary.n_cells == 5 and summary.valid_fraction == 0.2 and summary.water_fraction == 0.2
    assert summary.land_data_fraction == pytest.approx(0.4) and summary.outside_fraction == 0.2
    assert is_water_only(coverage_summary(np.full((4, 4), QUALITY_WATER, dtype=np.uint8)), 0.98)
    assert not is_water_only(summary, 0.98)
    with pytest.raises(RasterError):
        coverage_summary(np.zeros((0, 3), dtype=np.uint8))
    with pytest.raises(RasterError):
        classify_cells(nodata, water[:, :2], valid)


def test_mask_helpers() -> None:
    values = np.array([[1.0, -32768.0, np.nan, 4.0]])
    assert nodata_mask(values, -32768.0).tolist() == [[False, True, True, False]]
    assert nodata_mask(values, None).tolist() == [[False, False, True, False]]
    assert nodata_mask(np.array([[0, 7]], dtype=np.uint8), 0).tolist() == [[True, False]]
    assert usable_mask(values, -32768.0, water=np.array([[True, False, False, False]])).tolist() == [
        [False, False, False, True]
    ]
    usable = np.ones((5, 5), dtype=bool)
    assert full_support(usable, 3).sum() == 9 and full_support(usable, 5).sum() == 1 and full_support(usable, 1).all()
    hole = usable.copy()
    hole[2, 2] = False
    assert full_support(hole, 3).sum() == 0
    seed = np.zeros((9, 9), dtype=bool)
    seed[4, 4] = True
    assert dilate(seed, 0).sum() == 1 and dilate(seed, 1).sum() == 5 and dilate(seed, 2).sum() == 13
    assert dilate_metres(seed, 61.0, 60.0).sum() == 13  # 61 m at 60 m cells rounds up to 2 cells (conservative)
    assert fraction(np.array([True, False, True, True])) == 0.75
    assert fraction(np.array([True, False, True, True]), np.array([True, True, False, False])) == 0.5
    with pytest.raises(RasterError):
        fraction(np.array([True]), np.array([False]))
    with pytest.raises(RasterError):
        usable_mask(values, None, water=np.zeros((2, 2), dtype=bool))
    with pytest.raises(RasterError):
        full_support(usable, 4)
    with pytest.raises(RasterError):
        dilate(seed, -1)


def test_zone_band_areas_respect_half_open_bands_and_the_final_inclusive_band() -> None:
    slope = np.array([[11.999, 12.0, 15.0, 18.0, 18.0]])
    safe = np.ones((1, 5), dtype=bool)
    exclusive, _ = connected_zones(safe, slope, 100.0, [Band(12.0, 18.0)])
    inclusive, _ = connected_zones(safe, slope, 100.0, [Band(12.0, 18.0, upper_inclusive=True)])
    assert exclusive[0].band_area_m2["12-18"] == 2 * 100.0  # 12.0 and 15.0 only: 18.0 belongs to the next band
    assert inclusive[0].band_area_m2["12-18"] == 4 * 100.0  # the final capped band keeps its upper endpoint
    assert Band(12.0, 18.0).contains(np.array([18.0, 17.9999])).tolist() == [False, True]
