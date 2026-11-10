"""SCN-01 / SCN-14: geometry oracles (GEO-08..GEO-10), body-aware projections, normalisation, aggregation,
mosaics and the deterministic ANALYSIS_GRID container."""

from __future__ import annotations

import io
import math
import zipfile

import numpy as np
import pytest
from pyproj import CRS, Transformer

from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import ArtifactRole
from analogforge.science.comparison.scale import (
    aggregation_factor,
    check_support_window,
    common_support_m,
    plan_support,
)
from analogforge.science.errors import GeometryError, RasterError, ScaleError
from analogforge.science.features.slope import analyze_surface
from analogforge.science.geometry import (
    MARS_RADIUS_M,
    MOON_RADIUS_M,
    AnalysisGridSpec,
    BodyGeometry,
    PixelGeometry,
    assert_crs_matches_body,
    bbox_to_projected_bounds,
    body_distance_m,
    body_geometry,
    convert_latitude,
    frame_from_crs_wkt,
    grid_for_bbox,
    lonlat_to_xy,
    normalize_longitude,
    pixel_to_world_gdal,
    projected_bounds_to_bbox,
    projected_frame_for_aoi,
    split_bbox_at_antimeridian,
    unwrap_bbox,
    world_to_pixel_continuous,
    xy_to_lonlat,
)
from analogforge.science.hashing_utils import array_sha256, parameters_sha256
from analogforge.science.provenance import (
    check_source_naming,
    evidence_draft,
    safe_relpath,
    synthetic_product_id,
    write_scratch_artifact,
)
from analogforge.science.raster import store
from analogforge.science.raster.mosaic import ControlPoint, Tile, check_control_points, mosaic_tiles
from analogforge.science.raster.normalize import (
    aggregate_any,
    aggregate_blocks,
    aggregate_categorical_mode,
    class_area_fractions,
    looks_like_radius_not_height,
    normalize_elevation,
)


# ----------------------------------------------------------------------------- GEO-10: wrap and polar
def test_moon_longitude_wrap_zero_360_bounds_are_analytic() -> None:
    bbox = (359.9, -1.0, 0.1, 1.0)
    assert unwrap_bbox(bbox, "ZERO_360") == (359.9, -1.0, 360.1, 1.0)
    frame = projected_frame_for_aoi("MOON", bbox, "ZERO_360")
    assert frame.kind == "EQUIRECTANGULAR"
    xmin, ymin, xmax, ymax = bbox_to_projected_bounds(frame, bbox, "ZERO_360")
    half_x = MOON_RADIUS_M * math.radians(0.1)  # eqc with lat_ts = 0 -> x = R * dlon
    half_y = MOON_RADIUS_M * math.radians(1.0)
    assert xmin == pytest.approx(-half_x, abs=1e-6) and xmax == pytest.approx(half_x, abs=1e-6)
    assert ymin == pytest.approx(-half_y, abs=1e-6) and ymax == pytest.approx(half_y, abs=1e-6)


def test_wrap_equals_unwrapped_neighbour_longitudes() -> None:
    """Perturbation: the same AOI described as 359.9..0.1 or as -0.1..0.1 has identical projected geometry."""
    a = projected_frame_for_aoi("MARS", (359.9, -1.0, 0.1, 1.0), "ZERO_360")
    b = projected_frame_for_aoi("MARS", (-0.1, -1.0, 0.1, 1.0), "NEG180_180")
    ba = bbox_to_projected_bounds(a, (359.9, -1.0, 0.1, 1.0), "ZERO_360")
    bb = bbox_to_projected_bounds(b, (-0.1, -1.0, 0.1, 1.0), "NEG180_180")
    assert ba == pytest.approx(bb, abs=1e-6)


def test_antimeridian_split_and_normalisation() -> None:
    assert split_bbox_at_antimeridian((170.0, 10.0, -170.0, 20.0), "NEG180_180") == [
        (170.0, 10.0, 180.0, 20.0),
        (-180.0, 10.0, -170.0, 20.0),
    ]
    assert split_bbox_at_antimeridian((-10.0, 0.0, 10.0, 5.0), "NEG180_180") == [(-10.0, 0.0, 10.0, 5.0)]
    assert unwrap_bbox((170.0, 0.0, -170.0, 1.0), "NEG180_180") == (170.0, 0.0, 190.0, 1.0)
    assert unwrap_bbox((0.0, 0.0, 360.0, 1.0), "ZERO_360") == (0.0, 0.0, 360.0, 1.0)
    assert normalize_longitude(-0.1, "ZERO_360") == pytest.approx(359.9)
    assert normalize_longitude(180.0, "NEG180_180") == -180.0
    with pytest.raises(GeometryError):
        unwrap_bbox((0.0, 10.0, 1.0, -10.0), "NEG180_180")  # min_lat > max_lat
    with pytest.raises(GeometryError):
        normalize_longitude(float("nan"), "NEG180_180")


def test_south_polar_wedge_bounds_match_stereographic_formula() -> None:
    bbox = (-10.0, -89.5, 10.0, -87.5)
    frame = projected_frame_for_aoi("MOON", bbox)
    assert frame.kind == "POLAR_STEREOGRAPHIC"
    xmin, ymin, xmax, ymax = bbox_to_projected_bounds(frame, bbox)
    r_outer = 2 * MOON_RADIUS_M * math.tan(math.radians(2.5) / 2)  # colatitude 2.5 deg
    r_inner = 2 * MOON_RADIUS_M * math.tan(math.radians(0.5) / 2)
    assert r_outer == pytest.approx(75_820.4057, abs=1e-3)  # matches "r ~ 75.8 km" of architecture 40
    assert xmax == pytest.approx(r_outer * math.sin(math.radians(10)), abs=1e-6)
    assert xmin == pytest.approx(-xmax, abs=1e-6)
    assert ymax == pytest.approx(r_outer, abs=1e-6)  # the outer arc at lon 0 is sampled, not just the corners
    assert ymin == pytest.approx(r_inner * math.cos(math.radians(10)), abs=1e-6)
    assert frame.max_linear_distortion < 0.01


def test_polar_aoi_containing_the_pole_gives_full_longitude_range() -> None:
    bbox = (-180.0, -90.0, 180.0, -88.0)
    frame = projected_frame_for_aoi("MARS", bbox)
    bounds = bbox_to_projected_bounds(frame, bbox)
    back = projected_bounds_to_bbox(frame, bounds)
    assert back[0] == -180.0 and back[2] == 180.0 and back[1] == -90.0


def test_planetary_frames_never_use_earth_crs() -> None:
    for body, bbox in (("MOON", (-10.0, -89.5, 10.0, -87.5)), ("MARS", (137.0, -5.0, 138.0, -4.0))):
        frame = projected_frame_for_aoi(body, bbox)  # type: ignore[arg-type]
        crs = CRS.from_wkt(frame.crs_wkt)
        assert frame.epsg is None
        assert crs.to_epsg(min_confidence=100) is None
        label = "Moon" if body == "MOON" else "Mars"
        assert "WGS 84" not in frame.crs_wkt and "WGS84" not in frame.crs_wkt
        assert f"{label}_2000_IAU_IAG" in frame.crs_wkt and "unknown" not in frame.crs_wkt
        assert 'ID["EPSG",4326]' not in frame.crs_wkt and 'ID["EPSG",3857]' not in frame.crs_wkt
        assert crs.ellipsoid is not None
        assert crs.ellipsoid.semi_major_metre == pytest.approx(body_geometry(body).semi_major_m)  # type: ignore[arg-type]
        assert_crs_matches_body(body, frame.crs_wkt)  # type: ignore[arg-type]


def test_earth_crs_rejected_for_planets_and_planet_crs_rejected_for_earth() -> None:
    wgs84 = CRS.from_epsg(4326).to_wkt()
    utm = CRS.from_epsg(32612).to_wkt()
    web_mercator = CRS.from_epsg(3857).to_wkt()
    mars = projected_frame_for_aoi("MARS", (137.0, -5.0, 138.0, -4.0)).crs_wkt
    moon = projected_frame_for_aoi("MOON", (0.0, -1.0, 1.0, 1.0)).crs_wkt
    for body in ("MOON", "MARS"):
        for earth_wkt in (wgs84, utm, web_mercator):
            with pytest.raises(GeometryError) as err:
                assert_crs_matches_body(body, earth_wkt)  # type: ignore[arg-type]
            assert err.value.detail_code == "BODY_MISMATCH"
    with pytest.raises(GeometryError):
        assert_crs_matches_body("EARTH", mars)
    with pytest.raises(GeometryError):
        assert_crs_matches_body("MARS", moon)  # a Moon sphere is not a Mars sphere
    assert_crs_matches_body("EARTH", utm)
    with pytest.raises(GeometryError):
        frame_from_crs_wkt("MARS", utm)
    with pytest.raises(GeometryError) as unresolved:
        assert_crs_matches_body("MARS", "not a wkt")
    assert unresolved.value.detail_code == "FRAME_UNRESOLVED"


# ----------------------------------------------------------------------------- Earth frames and distortion
def test_earth_zone_selection_and_hemisphere() -> None:
    north = projected_frame_for_aoi("EARTH", (-111.5, 35.2, -111.4, 35.3))
    assert (north.kind, north.epsg) == ("UTM", 32612)
    south = projected_frame_for_aoi("EARTH", (-70.6, -33.5, -70.5, -33.4))
    assert (south.kind, south.epsg) == ("UTM", 32719)
    polar = projected_frame_for_aoi("EARTH", (0.0, 85.0, 5.0, 86.0))
    assert (polar.kind, polar.epsg) == ("UPS", 32661)


def test_aoi_straddling_two_utm_zones_uses_declared_local_projection() -> None:
    frame = projected_frame_for_aoi("EARTH", (-108.5, 35.0, -107.5, 36.0))  # 108 W is a zone boundary
    assert frame.kind == "LOCAL_TM" and frame.epsg is None
    assert frame.max_linear_distortion < 0.01


def test_excess_distortion_is_rejected_not_hidden() -> None:
    with pytest.raises(GeometryError) as err:
        projected_frame_for_aoi("EARTH", (-170.0, 10.0, 170.0, 50.0))
    assert err.value.detail_code == "DISTORTION_EXCEEDED"
    with pytest.raises(GeometryError) as err2:
        projected_frame_for_aoi("MARS", (0.0, -70.0, 90.0, 70.0))
    assert err2.value.detail_code == "DISTORTION_EXCEEDED"
    # perturbation: a smaller AOI passes, a larger tolerance is an explicit, visible choice
    assert projected_frame_for_aoi("MARS", (0.0, -5.0, 2.0, 5.0)).max_linear_distortion < 0.01
    relaxed = projected_frame_for_aoi("MARS", (0.0, -70.0, 90.0, 70.0), max_linear_distortion=5.0)
    assert relaxed.max_linear_distortion > 0.01


# ----------------------------------------------------------------------------- body distances and latitudes
def test_one_degree_arc_depends_on_the_body() -> None:
    mars = body_distance_m("MARS", 0.0, 0.0, 1.0, 0.0)
    moon = body_distance_m("MOON", 0.0, 0.0, 1.0, 0.0)
    earth = body_distance_m("EARTH", 0.0, 0.0, 1.0, 0.0)
    assert mars == pytest.approx(MARS_RADIUS_M * math.radians(1.0), abs=1e-6)
    assert moon == pytest.approx(MOON_RADIUS_M * math.radians(1.0), abs=1e-6)
    assert earth == pytest.approx(111_319.4908, abs=1e-3)
    assert len({round(mars), round(moon), round(earth)}) == 3
    # meridian arcs on a sphere equal equatorial arcs; on WGS84 they do not
    assert body_distance_m("MARS", 10.0, 0.0, 10.0, 1.0) == pytest.approx(mars, abs=1e-6)
    assert body_distance_m("EARTH", 10.0, 0.0, 10.0, 1.0) == pytest.approx(110_574.3886, abs=1e-3)


def test_latitude_types_differ_only_on_an_ellipsoid() -> None:
    sphere = body_geometry("MARS")
    assert convert_latitude(45.0, "PLANETOGRAPHIC", "PLANETOCENTRIC", sphere) == 45.0
    oblate = BodyGeometry("MARS", 3_396_190.0, 3_376_200.0, "test oblate", "test")
    centric = convert_latitude(45.0, "PLANETOGRAPHIC", "PLANETOCENTRIC", oblate)
    ratio = (3_376_200.0 / 3_396_190.0) ** 2
    assert centric == pytest.approx(math.degrees(math.atan(ratio * math.tan(math.radians(45.0)))), abs=1e-12)
    assert centric < 45.0
    assert convert_latitude(centric, "PLANETOCENTRIC", "PLANETOGRAPHIC", oblate) == pytest.approx(45.0, abs=1e-12)
    assert convert_latitude(90.0, "PLANETOGRAPHIC", "PLANETOCENTRIC", oblate) == 90.0
    with pytest.raises(GeometryError):
        convert_latitude(95.0, "PLANETOGRAPHIC", "PLANETOCENTRIC", oblate)


# ----------------------------------------------------------------------------- analysis grid (practice geometry)
def _practice_grid() -> AnalysisGridSpec:
    return AnalysisGridSpec("EARTH", CRS.from_epsg(32612).to_wkt(), 494240.0, 3900000.0, 60.0, 192, 192)


def test_practice_window_extents_follow_architecture_40() -> None:
    grid = _practice_grid()
    # window grid-r1c2: easting 494240 + 2*3840 .. +3840, northing 3900000 - 3840 - 3840 .. 3900000 - 3840
    window = grid.window(64, 128, 64, 64)
    assert window.bounds == (494240.0 + 2 * 3840.0, 3900000.0 - 2 * 3840.0, 494240.0 + 3 * 3840.0, 3900000.0 - 3840.0)
    assert window.geotransform == (501920.0, 60.0, 0.0, 3896160.0, 0.0, -60.0) == pixel_to_world_gdal(window)
    assert grid.bounds == (494240.0, 3900000.0 - 192 * 60.0, 494240.0 + 11520.0, 3900000.0)
    frame = frame_from_crs_wkt("EARTH", grid.crs_wkt)
    bbox = projected_bounds_to_bbox(frame, window.bounds)
    corners = Transformer.from_crs("EPSG:32612", "EPSG:4326", always_xy=True)
    xs = [window.bounds[0], window.bounds[2], window.bounds[0], window.bounds[2]]
    ys = [window.bounds[1], window.bounds[1], window.bounds[3], window.bounds[3]]
    lon, lat = corners.transform(xs, ys)
    assert bbox[0] == pytest.approx(min(lon), abs=2e-4) and bbox[2] == pytest.approx(max(lon), abs=2e-4)
    assert bbox[1] == pytest.approx(min(lat), abs=2e-4) and bbox[3] == pytest.approx(max(lat), abs=2e-4)


def test_grid_index_centres_and_roundtrips() -> None:
    grid = _practice_grid()
    assert grid.cell_centre(0, 0) == (494270.0, 3899970.0)
    assert grid.index_of(494270.0, 3899970.0) == (0, 0)
    assert grid.index_of(494240.0 + 192 * 60.0 - 0.001, 3900000.0 - 192 * 60.0 + 0.001) == (191, 191)
    assert grid.index_of(494239.9, 3899999.0) is None and grid.index_of(494250.0, 3900001.0) is None
    x, y = grid.centre_coordinates()
    assert (
        x.shape == y.shape == grid.shape
        and x[5, 7] == grid.cell_centre(5, 7)[0]
        and y[5, 7] == grid.cell_centre(5, 7)[1]
    )
    col, row = world_to_pixel_continuous(grid, 494240.0 + 60.0 * 10.25, 3900000.0 - 60.0 * 3.5)
    assert (col, row) == (pytest.approx(10.25), pytest.approx(3.5))
    frame = frame_from_crs_wkt("EARTH", grid.crs_wkt)
    lon, lat = xy_to_lonlat(frame, np.array([500000.0]), np.array([3890000.0]))
    x2, y2 = lonlat_to_xy(frame, lon, lat)
    assert (x2[0], y2[0]) == (pytest.approx(500000.0, abs=1e-6), pytest.approx(3890000.0, abs=1e-6))
    with pytest.raises(GeometryError):
        grid.window(180, 0, 64, 64)
    assert grid.aggregated(8).cell_size_m == 480.0 and grid.aggregated(8).shape == (24, 24)


def test_grid_for_bbox_covers_the_aoi_and_snaps_to_cells() -> None:
    bbox = (137.0, -5.0, 138.0, -4.0)
    frame = projected_frame_for_aoi("MARS", bbox)
    exact = bbox_to_projected_bounds(frame, bbox)
    grid = grid_for_bbox(frame, bbox, 480.0)
    assert grid.bounds[0] <= exact[0] and grid.bounds[2] >= exact[2]
    assert grid.bounds[1] <= exact[1] and grid.bounds[3] >= exact[3]
    assert grid.bounds[0] % 480.0 == 0 and grid.bounds[3] % 480.0 == 0
    assert grid.width == pytest.approx((exact[2] - exact[0]) / 480.0, abs=2.0)


def test_pixel_geometry_validation() -> None:
    with pytest.raises(GeometryError):
        PixelGeometry(1.0, 0.0, 2.0, 0.0)  # singular
    with pytest.raises(GeometryError):
        PixelGeometry(float("nan"), 0.0, 0.0, -1.0)
    with pytest.raises(GeometryError):
        AnalysisGridSpec("MARS", "x", 0.0, 0.0, 0.0, 4, 4)
    assert PixelGeometry.north_up(10.0, 30.0).cell_area_m2 == 300.0
    rot = PixelGeometry.rotated(10.0, 30.0, 33.0)
    assert rot.cell_area_m2 == pytest.approx(300.0)


# ----------------------------------------------------------------------------- normalisation: scale and radius once
def test_moon_radius_to_height_and_scale_applied_exactly_once() -> None:
    raw = np.array([[0, 200, -400], [10, -32768, 30]], dtype=np.int16)
    heights, missing, rec = normalize_elevation(
        raw,
        quantity="RADIUS",
        units="m",
        scale_factor=0.5,
        offset=1_737_400.0,
        reference_radius_m=1_737_400.0,
        nodata_value=-32768,
    )
    expected = raw.astype(float) * 0.5  # radius = raw*0.5 + 1737400 ; height = radius - 1737400
    assert missing.tolist() == [[False, False, False], [False, True, False]]
    assert np.array_equal(heights[~missing], expected[~missing])
    assert np.isnan(heights[missing]).all()
    assert rec.scale_applied_by == "ANALYSIS" and rec.radius_subtracted and rec.reference_radius_m == 1_737_400.0
    # reader-side scaling: values arrive as radii in metres already -> identical heights, scale not applied again
    radius_m = raw.astype(float) * 0.5 + 1_737_400.0
    again, _, rec2 = normalize_elevation(
        np.where(raw == -32768, -32768.0, radius_m),
        quantity="RADIUS",
        units="m",
        scale_factor=0.5,
        offset=1_737_400.0,
        scale_already_applied=True,
        reference_radius_m=1_737_400.0,
        nodata_value=-32768,
    )
    assert rec2.scale_applied_by == "READER"
    assert np.allclose(again[~missing], expected[~missing], atol=1e-9)
    # a double application would be wrong by exactly the offset: prove the guard distinguishes them
    double = raw.astype(float) * 0.5 + 1_737_400.0
    assert abs(double[0, 1] - 1_737_400.0 - expected[0, 1]) == 0  # single application
    assert abs((double[0, 1] * 0.5 + 1_737_400.0 - 1_737_400.0) - expected[0, 1]) > 800_000  # double is nonsense
    assert looks_like_radius_not_height(radius_m)
    assert not looks_like_radius_not_height(heights)


def test_kilometre_units_and_elevation_quantity() -> None:
    km, _, rec = normalize_elevation(np.array([1.5, -0.2]), quantity="ELEVATION", units="km")
    assert km.tolist() == [1500.0, -200.0] and rec.unit_factor_to_m == 1000.0 and not rec.radius_subtracted
    radius_km, _, _ = normalize_elevation(
        np.array([3396.19 + 1.0]), quantity="RADIUS", units="km", reference_radius_m=3_396_190.0
    )
    assert radius_km[0] == pytest.approx(1000.0, abs=1e-6)


def test_normalisation_failure_paths() -> None:
    raw = np.zeros((2, 2))
    with pytest.raises(RasterError):
        normalize_elevation(raw, quantity="RADIUS", units="m")  # radius without reference radius
    with pytest.raises(RasterError):
        normalize_elevation(raw, quantity="ELEVATION", units="m", scale_factor=0.0)
    with pytest.raises(RasterError):
        normalize_elevation(raw, quantity="ELEVATION", units="m", offset=float("inf"))
    with pytest.raises(RasterError):
        normalize_elevation(raw, quantity="SLOPE_DEG", units="m")  # type: ignore[arg-type]
    with pytest.raises(RasterError):
        normalize_elevation(raw, quantity="ELEVATION", units="ft")  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- aggregation and support
def test_area_average_aggregation_and_nodata_is_never_bridged() -> None:
    values = np.arange(16, dtype=float).reshape(4, 4)
    valid = np.ones((4, 4), dtype=bool)
    mean, ok = aggregate_blocks(values, valid, 2)
    assert ok.all() and mean.tolist() == [[2.5, 4.5], [10.5, 12.5]]
    valid[0, 0] = False
    mean2, ok2 = aggregate_blocks(np.where(valid, values, np.nan), valid, 2)
    assert ok2.tolist() == [[False, True], [True, True]] and np.isnan(mean2[0, 0])
    mean3, ok3 = aggregate_blocks(np.where(valid, values, np.nan), valid, 2, min_valid_fraction=0.75)
    assert ok3.all() and mean3[0, 0] == pytest.approx((1 + 4 + 5) / 3)
    with pytest.raises(RasterError):
        aggregate_blocks(values, valid, 8)
    water = np.zeros((4, 4), dtype=bool)
    water[3, 3] = True
    assert aggregate_any(water, 2).tolist() == [[False, False], [False, True]]


def test_categorical_ids_are_never_interpolated() -> None:
    ids = np.array([[1, 1, 3, 4], [1, 2, 3, 3], [0, 0, 2, 2], [0, 0, 2, 4]], dtype=np.uint8)
    out, share = aggregate_categorical_mode(ids, 2, nodata_id=0)
    assert set(np.unique(out)) <= {0, 1, 2, 3, 4}  # only existing class ids, never a mean such as 1.5
    assert out.tolist() == [[1, 3], [0, 2]] and share.tolist() == [[0.75, 0.75], [0.0, 0.75]]
    tie, _ = aggregate_categorical_mode(np.array([[1, 3], [3, 1]], dtype=np.uint8), 2, nodata_id=0)
    assert tie[0, 0] == 1  # deterministic tie-break: smallest id
    fractions = class_area_fractions(ids, (1, 2, 3, 4), nodata_id=0)
    assert sum(fractions.values()) == pytest.approx(1.0) and fractions[2] == pytest.approx(4 / 12)
    with pytest.raises(RasterError):
        class_area_fractions(np.zeros((2, 2), dtype=np.uint8), (1,), nodata_id=0)


def test_support_planning_never_upsamples() -> None:
    plan = plan_support(60.0, 480.0)
    assert (plan.effective_m, plan.factor, plan.upsampled) == (480.0, 8, False)
    assert plan_support(960.0, 480.0).effective_m == 960.0  # coarser native support stays coarse
    assert plan_support(960.0, None).factor == 1
    assert common_support_m(480.0, 60.0, requested_m=None) == 480.0
    assert aggregation_factor(60.0, 960.0) == 16
    with pytest.raises(ScaleError):
        aggregation_factor(60.0, 30.0)  # finer than native: refused
    with pytest.raises(ScaleError):
        aggregation_factor(60.0, 100.0)  # not an integer multiple
    with pytest.raises(ScaleError):
        common_support_m()


def test_support_window_bounds_are_inclusive_and_open_ended() -> None:
    assert check_support_window(480.0, 480.0, 1000.0).supported
    assert check_support_window(1000.0, 480.0, 1000.0).supported
    assert check_support_window(60.0, 480.0, 1000.0).reason == "BELOW_MINIMUM"
    assert check_support_window(1000.5, 480.0, 1000.0).reason == "ABOVE_MAXIMUM"
    assert check_support_window(60.0, None, 60.0).supported and not check_support_window(61.0, None, 60.0).supported
    assert check_support_window(5e6, None, None).supported
    with pytest.raises(ScaleError):
        check_support_window(float("nan"), None, None)


# --------------------------------------------------------------------------- GEO-08 / GEO-09: mosaics, registration
def _ramp_tile(name: str, col0: int, cols: int, rows: int = 4, cell: float = 30.0) -> Tile:
    jj = np.arange(col0, col0 + cols, dtype=float)
    values = np.tile(100.0 + 2.0 * jj, (rows, 1))  # value depends only on the global column index
    return Tile(name, values, origin_x_m=1000.0 + col0 * cell, origin_y_m=5000.0, cell_size_m=cell)


def test_mosaic_with_shared_border_samples_has_no_duplicate_column_or_shift() -> None:
    left = _ramp_tile("left", 0, 5)
    right = _ramp_tile("right", 4, 5)  # shares global column 4 with `left`
    merged = mosaic_tiles([right, left])  # order must not matter
    assert merged.values.shape == (4, 9) and merged.covered.all()
    assert np.array_equal(merged.values[0], 100.0 + 2.0 * np.arange(9))
    assert merged.origin_x_m == 1000.0 and merged.origin_y_m == 5000.0
    # distances are unshifted: global column 6 sits 6 cells east of the origin
    assert merged.origin_x_m + 6 * merged.cell_size_m == right.origin_x_m + 2 * right.cell_size_m


def test_mosaic_failure_paths() -> None:
    left = _ramp_tile("left", 0, 5)
    shifted_values = _ramp_tile("right", 4, 5)
    bad = Tile("bad", shifted_values.values + 0.5, shifted_values.origin_x_m, shifted_values.origin_y_m, 30.0)
    with pytest.raises(RasterError) as seam:
        mosaic_tiles([left, bad])
    assert seam.value.detail_code == "SEAM_CONFLICT"
    off = Tile("off", shifted_values.values, shifted_values.origin_x_m + 7.5, shifted_values.origin_y_m, 30.0)
    with pytest.raises(RasterError) as reg:
        mosaic_tiles([left, off])
    assert reg.value.detail_code == "REGISTRATION_OFFSET"
    with pytest.raises(RasterError):
        mosaic_tiles([])
    with pytest.raises(RasterError):
        mosaic_tiles([left, Tile("coarse", left.values, 0.0, 0.0, 60.0)])


def test_mosaic_gap_stays_unknown_not_zero() -> None:
    a = _ramp_tile("a", 0, 3)
    c = _ramp_tile("c", 5, 3)  # column 3, 4 absent
    merged = mosaic_tiles([a, c])
    assert np.isnan(merged.values[:, 3:5]).all() and not merged.covered[:, 3:5].any()


def test_one_pixel_registration_offset_is_caught_by_control_points() -> None:
    cell = 30.0
    grid = AnalysisGridSpec("EARTH", CRS.from_epsg(32612).to_wkt(), 1000.0, 5000.0, cell, 9, 4)
    truth = np.tile(100.0 + 2.0 * np.arange(9.0), (4, 1))
    controls = [
        ControlPoint(f"cp{c}", 1000.0 + (c + 0.5) * cell, 5000.0 - 1.5 * cell, 100.0 + 2.0 * c, 1e-9) for c in (1, 4, 7)
    ]
    assert all(r.passed for r in check_control_points(grid, truth, controls))
    shifted = np.roll(truth, 1, axis=1)  # deliberate one-pixel registration offset
    results = check_control_points(grid, shifted, controls)
    assert not any(r.passed for r in results)
    outside = ControlPoint("out", 0.0, 0.0, 1.0, 1.0)
    assert check_control_points(grid, truth, [outside])[0].observed is None
    nan_grid = truth.copy()
    nan_grid[1, 1] = np.nan
    assert check_control_points(grid, nan_grid, controls)[0].observed is None


# ----------------------------------------------------------------------------- ANALYSIS_GRID container
def _sample_elevation() -> np.ndarray:
    _, xx = np.mgrid[0:10, 0:12]
    return 50.0 + np.tan(np.radians(15.0)) * 60.0 * xx


def _sample_grid() -> store.AnalysisGrid:
    spec = AnalysisGridSpec(
        "MARS", projected_frame_for_aoi("MARS", (137.0, -5.0, 138.0, -4.0)).crs_wkt, -1000.0, 2000.0, 60.0, 12, 10
    )
    elevation = _sample_elevation()
    water = np.zeros((10, 12), dtype=bool)
    water[8:, 9:] = True
    surf = analyze_surface(elevation, spec.pixel_geometry(), water=water)
    return store.build_analysis_grid(
        spec,
        elevation_m=elevation,
        valid=surf.valid,
        land=surf.land,
        slope_deg=np.nan_to_num(surf.slope_deg),
        aspect_deg=surf.aspect_deg,
        quality=surf.quality,
        source_evidence_ids=("b-ev", "a-ev"),
        algorithm_id="analyze-candidate",
        algorithm_version="1.0.0",
        parameters_sha256="0" * 64,
    )


def test_analysis_grid_roundtrip_and_semantics() -> None:
    grid = _sample_grid()
    data = store.encode_analysis_grid(grid)
    back = store.decode_analysis_grid(data)
    for name in store.ARRAY_MEMBERS:
        a, b = getattr(grid, name), getattr(back, name)
        assert a.dtype == b.dtype and a.shape == b.shape
        assert np.array_equal(a, b, equal_nan=True)
    assert back.meta == grid.meta and back.meta.source_evidence_ids == ("a-ev", "b-ev")
    assert back.spec == grid.spec
    assert back.slope_deg[back.valid] == pytest.approx(15.0, abs=1e-6)
    assert not back.slope_deg[~back.valid].any()
    # elevation is zero only where there is no source elevation (water here); border land keeps its real value
    assert not back.elevation_m[~back.land].any()
    border = (back.quality == 3) & back.land
    assert border.any() and np.all(back.elevation_m[border] == _sample_elevation()[border])
    assert np.isnan(back.aspect_deg[~back.valid]).all()
    assert not back.land[8:, 9:].any() and not back.valid[8:, 9:].any()
    assert not np.isnan(back.elevation_m).any()


def test_analysis_grid_bytes_are_deterministic_and_content_addressed() -> None:
    grid = _sample_grid()
    first, second = store.encode_analysis_grid(grid), store.encode_analysis_grid(_sample_grid())
    assert first == second and store.analysis_grid_sha256(grid) == canonical_free_sha(first)
    with zipfile.ZipFile(io.BytesIO(first)) as zf:
        names = [i.filename for i in zf.infolist()]
        assert names == sorted(names) == list(store.MEMBER_NAMES)
        assert all(
            i.date_time == (1980, 1, 1, 0, 0, 0) and i.compress_type == zipfile.ZIP_STORED for i in zf.infolist()
        )
        meta = zf.read("meta.json")
    assert b"cell_size_m" in meta and b"crs_wkt" in meta and meta.startswith(b"{")
    # perturbation: one changed cell -> different hash
    changed = _sample_grid()
    changed.elevation_m[2, 2] += 1.0
    assert store.analysis_grid_sha256(changed) != store.analysis_grid_sha256(grid)


def canonical_free_sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def test_analysis_grid_writer_reader_files(tmp_path: pytest.TempPathFactory) -> None:
    grid = _sample_grid()
    path = tmp_path / "nested" / "grid.npz"  # type: ignore[operator]
    sha, size = store.write_analysis_grid(path, grid)
    assert path.stat().st_size == size and sha == store.analysis_grid_sha256(grid)
    assert store.read_analysis_grid(path).meta == grid.meta
    with pytest.raises(RasterError):
        store.read_analysis_grid(tmp_path / "missing.npz")  # type: ignore[operator]


def test_analysis_grid_invariant_and_corruption_failures() -> None:
    good = _sample_grid()

    def mutated(**changes: object) -> store.AnalysisGrid:
        fields = {n: getattr(good, n).copy() for n in store.ARRAY_MEMBERS}
        fields.update(changes)  # type: ignore[arg-type]
        return store.AnalysisGrid(meta=good.meta, **fields)

    nan_elev = good.elevation_m.copy()
    nan_elev[0, 0] = np.nan
    with pytest.raises(RasterError):
        store.encode_analysis_grid(mutated(elevation_m=nan_elev))
    bad_invalid_elev = good.elevation_m.copy()
    r, c = np.argwhere(~good.land)[0]  # a water cell has no usable elevation: must hold 0
    bad_invalid_elev[r, c] = 5.0
    with pytest.raises(RasterError):
        store.encode_analysis_grid(mutated(elevation_m=bad_invalid_elev))
    water_valid = good.land.copy()
    rr, cc = np.argwhere(good.valid)[0]
    water_valid[rr, cc] = False
    with pytest.raises(RasterError):
        store.encode_analysis_grid(mutated(land=water_valid))  # valid cell flagged as water
    with pytest.raises(RasterError):
        store.encode_analysis_grid(mutated(slope_deg=np.full_like(good.slope_deg, 95.0)))
    with pytest.raises(RasterError):
        store.encode_analysis_grid(mutated(quality=good.quality.astype(np.int32)))
    with pytest.raises(RasterError):
        store.decode_analysis_grid(b"not a zip")
    data = store.encode_analysis_grid(good)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            if info.filename != "valid.npy":
                zout.writestr(info, zin.read(info))
    with pytest.raises(RasterError):
        store.decode_analysis_grid(out.getvalue())  # member missing
    out2 = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out2, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, zin.read(info))
        zout.writestr("extra.npy", b"x")
    with pytest.raises(RasterError):
        store.decode_analysis_grid(out2.getvalue())  # unexpected member


# ----------------------------------------------------------------------------- provenance helpers
def test_parameters_hash_is_canonical_and_sensitive() -> None:
    kwargs = dict(
        operation="ANALYZE_CANDIDATE",
        algorithm_id="analyze-candidate",
        algorithm_version="1.0.0",
        parameters={"cell_size_m": 60.0},
        input_hashes=["b" * 64, "a" * 64],
        seed=0,
        algorithm_config_sha256="c" * 64,
    )
    base = parameters_sha256(**kwargs)  # type: ignore[arg-type]
    assert base == parameters_sha256(**{**kwargs, "input_hashes": ["a" * 64, "b" * 64]})  # type: ignore[arg-type]
    assert base == canonical_sha256(
        {
            "operation": "ANALYZE_CANDIDATE",
            "algorithm_id": "analyze-candidate",
            "algorithm_version": "1.0.0",
            "parameters": {"cell_size_m": 60.0},
            "input_hashes": ["a" * 64, "b" * 64],
            "seed": 0,
            "algorithm_config_sha256": "c" * 64,
        }
    )
    for key, value in (("seed", 1), ("algorithm_config_sha256", "d" * 64), ("parameters", {"cell_size_m": 61.0})):
        assert parameters_sha256(**{**kwargs, key: value}) != base  # type: ignore[arg-type]
    assert array_sha256(np.zeros((2, 3))) != array_sha256(np.zeros((3, 2)))
    assert array_sha256(np.zeros(3, dtype=np.float32)) != array_sha256(np.zeros(3))


def test_source_naming_and_scratch_safety(tmp_path: pytest.TempPathFactory) -> None:
    assert synthetic_product_id("practice-earth-grid-v1") == "SYNTHETIC_PRACTICE_EARTH_GRID_V1"
    check_source_naming("synthetic", "SYNTHETIC_X", None)
    with pytest.raises(Exception, match="SYNTHETIC"):
        check_source_naming("synthetic", "NASADEM_HGT", None)
    with pytest.raises(Exception, match="source_uri"):
        check_source_naming("synthetic", "SYNTHETIC_X", "https://example.org/a")
    with pytest.raises(Exception, match="live"):
        check_source_naming("live", "SYNTHETIC_X", None)
    with pytest.raises(Exception, match="query"):
        check_source_naming("live", "NASADEM_HGT", "https://example.org/a?token=1")
    for bad in ("../x", "/etc/passwd", "a/../../b", ""):
        with pytest.raises(Exception, match="unsafe"):
            safe_relpath(bad)
    art = write_scratch_artifact(
        tmp_path,  # type: ignore[arg-type]
        local_key="art",
        relpath="out/x.json",
        data=b"{}",
        media_type="application/json",
        role=ArtifactRole.DERIVED_JSON,
    )
    assert art.size_bytes == 2 and (tmp_path / "out" / "x.json").read_bytes() == b"{}"  # type: ignore[operator]
    ev = evidence_draft(
        mode="synthetic",
        local_key="ev",
        kind="DERIVED",
        body="EARTH",
        algorithm_id="analyze-candidate",
        algorithm_version="1.0.0",
        parameters_sha256="0" * 64,
        license_note="SYNTHETIC PRACTICE DATA",
        artifact=art,
        parent_local_keys=["z", "a", "z"],
        dataset_product_id="SYNTHETIC_X",
    )
    assert (
        ev.parent_local_keys == ["a", "z"] and ev.artifact_key == "art" and ev.artifact_media_type == "application/json"
    )


def test_oblate_planetary_ellipsoids_are_rejected_not_approximated() -> None:
    """Moon and Mars are modelled as spheres; a CRS on the oblate IAU-2000 Mars figure would shift coordinates."""
    oblate_mars = CRS.from_proj4("+proj=eqc +lat_ts=-4.5 +lon_0=137.5 +a=3396190 +b=3376200 +units=m +no_defs").to_wkt()
    sphere_mars = CRS.from_proj4("+proj=eqc +lat_ts=-4.5 +lon_0=137.5 +R=3396190 +units=m +no_defs").to_wkt()
    with pytest.raises(GeometryError) as err:
        assert_crs_matches_body("MARS", oblate_mars)
    assert err.value.detail_code == "BODY_MISMATCH" and "oblate" in err.value.message
    with pytest.raises(GeometryError):
        frame_from_crs_wkt("MARS", oblate_mars)
    assert_crs_matches_body("MARS", sphere_mars)  # same semi-major axis, spherical: accepted


def test_to_positive_east_flips_only_positive_west_products() -> None:
    from analogforge.science.geometry import to_positive_east

    assert to_positive_east(137.5, "POSITIVE_EAST") == 137.5
    assert to_positive_east(222.5, "POSITIVE_WEST") == -222.5  # a positive-west product: 222.5 W is 137.5 E mod 360
    assert (to_positive_east(222.5, "POSITIVE_WEST") % 360.0) == pytest.approx(137.5)
    assert to_positive_east(-10.0, "POSITIVE_WEST") == 10.0


def test_analysis_grid_keeps_elevation_of_border_land_and_zeroes_nodata_and_water() -> None:
    spec = AnalysisGridSpec(
        "MARS", projected_frame_for_aoi("MARS", (137.0, -5.0, 138.0, -4.0)).crs_wkt, 0.0, 600.0, 60.0, 10, 10
    )
    elevation = 100.0 + np.arange(100, dtype=np.float64).reshape(10, 10)
    nodata = np.zeros((10, 10), dtype=bool)
    nodata[4, 4] = True
    water = np.zeros((10, 10), dtype=bool)
    water[7, 7] = True
    surf = analyze_surface(np.where(nodata, np.nan, elevation), spec.pixel_geometry(), water=water, nodata=nodata)
    grid = store.build_analysis_grid(
        spec, elevation_m=np.where(nodata, 0.0, elevation), valid=surf.valid, land=surf.land,
        slope_deg=np.nan_to_num(surf.slope_deg), aspect_deg=surf.aspect_deg, quality=surf.quality,
        source_evidence_ids=("e",), algorithm_id="analyze-candidate", algorithm_version="1.0.0",
        parameters_sha256="0" * 64,
    )  # fmt: skip
    border = (grid.quality == 3) & grid.land
    assert border[0, :].all() and border[3, 4] and not grid.valid[0, 0]  # the raster border and nodata neighbours
    assert np.array_equal(grid.elevation_m[border], elevation[border])  # real elevation, not a zero placeholder
    assert grid.elevation_m[4, 4] == 0.0 and grid.elevation_m[7, 7] == 0.0  # nodata and water: no elevation
    assert np.array_equal(grid.elevation_m[grid.valid], elevation[grid.valid])
    store.decode_analysis_grid(store.encode_analysis_grid(grid))  # the invariant accepts exactly this layout
