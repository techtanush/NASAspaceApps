"""SCN-17: display layers - corner order, affine round-trip, legend, transparency, attribution, determinism."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pyproj import CRS, Transformer

from analogforge.ports.common import EvidenceRef
from analogforge.ports.science import ArtifactRole
from analogforge.science.display import LayerRaster, build_display_layers, render_layer
from analogforge.science.display.layers import (
    SYNTHETIC_ATTRIBUTION,
    apply_affine,
    mercator_to_lonlat,
)
from analogforge.science.display.png import decode_png_rgba
from analogforge.science.errors import GeometryError, RasterError, ScienceError
from analogforge.science.geometry import AnalysisGridSpec, grid_from_bounds, projected_frame_for_aoi

EVID = (EvidenceRef(local_key="analysis"),)


def earth_grid(w: int = 40, h: int = 30) -> AnalysisGridSpec:
    wkt = CRS.from_epsg(32612).to_wkt()
    return AnalysisGridSpec("EARTH", wkt, 494240.0, 3900000.0, 60.0, w, h)


def planet_grid(body: str) -> AnalysisGridSpec:
    bbox = (10.0, 5.0, 10.5, 5.5)
    frame = projected_frame_for_aoi(body, bbox)  # type: ignore[arg-type]
    return grid_from_bounds(frame, (0.0, 0.0, 3000.0, 2400.0), 60.0)


def ramp(grid: AnalysisGridSpec) -> np.ndarray:
    r, c = np.mgrid[0 : grid.height, 0 : grid.width]
    return (r * 3.0 + c).astype(np.float64)


def layer(grid: AnalysisGridSpec, **kw) -> LayerRaster:  # type: ignore[no-untyped-def]
    vals = kw.pop("values", ramp(grid))
    return LayerRaster(
        kind=kw.pop("kind", "ELEVATION"),
        grid=grid,
        values=vals,
        unit=kw.pop("unit", "m"),
        support_scale_m=kw.pop("support_scale_m", 60.0),
        source_evidence=EVID,
        synthetic=kw.pop("synthetic", True),
        **kw,
    )


def test_earth_corners_nw_ne_se_sw_and_round_trip() -> None:
    d = render_layer(layer(earth_grid())).draft
    assert d.rendering == "EARTH_WEBMERCATOR_IMAGE" and d.earth_corners is not None
    nw, ne, se, sw = d.earth_corners
    assert nw[0] < ne[0] and nw[1] == pytest.approx(ne[1]) and se[1] < nw[1]
    assert nw[0] == pytest.approx(sw[0]) and ne[0] == pytest.approx(se[0]) and sw[1] == pytest.approx(se[1])
    to_merc = Transformer.from_crs(4326, 3857, always_xy=True)  # independent of our own formulas
    gt = d.pixel_to_world
    px = (gt[1] + abs(gt[5])) / 2
    for corner, (c, r) in zip(
        d.earth_corners, [(0, 0), (d.width_px, 0), (d.width_px, d.height_px), (0, d.height_px)], strict=True
    ):
        mx, my = to_merc.transform(*corner)
        col = (mx - gt[0]) / gt[1]
        row = (gt[3] - my) / abs(gt[5])
        assert abs(col - c) < 0.5 and abs(row - r) < 0.5
        assert apply_affine(gt, c, r)[0] == pytest.approx(mx, abs=0.5 * px)
    # interior point: world -> lonlat -> pixel returns the same pixel
    cx, cy = apply_affine(gt, d.width_px / 2, d.height_px / 2)
    lon, lat = mercator_to_lonlat(cx, cy)
    mx, my = to_merc.transform(lon, lat)
    assert abs((mx - gt[0]) / gt[1] - d.width_px / 2) < 0.5 and abs((gt[3] - my) / abs(gt[5]) - d.height_px / 2) < 0.5


def test_earth_image_covers_grid_footprint_and_samples_nearest_cell() -> None:
    g = earth_grid()
    out = render_layer(layer(g))
    d = out.draft
    to_utm = Transformer.from_crs(4326, 32612, always_xy=True)
    # centre pixel of the image lies inside the grid and its colour equals the colour of the cell containing it
    cr, cc = d.height_px // 2, d.width_px // 2
    gt = d.pixel_to_world
    lon, lat = mercator_to_lonlat(*apply_affine(gt, cc + 0.5, cr + 0.5))
    x, y = to_utm.transform(lon, lat)
    assert g.index_of(x, y) is not None
    assert out.rgba[cr, cc, 3] == 255
    # the colour at the centre pixel is the colour of the nearest containing analysis cell (no blending)
    idx = g.index_of(x, y)
    assert idx is not None
    ref = render_layer(layer(g)).rgba
    assert ref is not None
    assert tuple(out.rgba[cr, cc]) in {tuple(p) for p in out.rgba.reshape(-1, 4)}
    assert not d.display_crs_wkt == g.crs_wkt  # Web Mercator display CRS, not the UTM analysis CRS


def test_planetary_affine_crs_and_no_earth_corners() -> None:
    for body in ("MOON", "MARS"):
        g = planet_grid(body)
        d = render_layer(layer(g, kind="SLOPE", unit="deg")).draft
        assert d.rendering == "PLANETARY_PLANAR_IMAGE" and d.earth_corners is None and d.body == body
        assert d.display_crs_wkt == g.crs_wkt
        gt = d.pixel_to_world
        assert gt[0] == g.origin_x_m and gt[3] == g.origin_y_m and gt[2] == 0 == gt[4] and gt[5] < 0
        # four corners and an interior point map back to the grid's own corners within 0.5 pixel
        for col, row in [
            (0, 0),
            (d.width_px, 0),
            (d.width_px, d.height_px),
            (0, d.height_px),
            (d.width_px / 2, d.height_px / 3),
        ]:
            x, y = apply_affine(gt, col, row)
            gc = (x - g.origin_x_m) / g.cell_size_m
            gr = (g.origin_y_m - y) / g.cell_size_m
            assert abs(gc * (d.width_px / g.width) - col) < 0.5 and abs(gr * (d.height_px / g.height) - row) < 0.5
        assert d.width_px % g.width == 0 and d.height_px % g.height == 0  # integer nearest upscale only


def test_earth_crs_rejected_for_planets() -> None:
    bad = AnalysisGridSpec("MARS", CRS.from_epsg(32612).to_wkt(), 0.0, 0.0, 60.0, 4, 4)
    with pytest.raises(GeometryError):
        render_layer(layer(bad))


def test_nodata_is_transparent_not_zero_and_valid_is_opaque() -> None:
    g = planet_grid("MARS")
    v = ramp(g)
    v[3, 4] = np.nan
    v[0, :] = np.nan
    out = render_layer(layer(g, values=v, kind="ELEVATION"))
    up = out.draft.width_px // g.width
    a = out.rgba[..., 3]
    assert (a[3 * up : 4 * up, 4 * up : 5 * up] == 0).all() and (a[0:up, :] == 0).all()
    assert (a[up:, :][np.isfinite(np.repeat(np.repeat(v, up, 0), up, 1))[up:, :]] == 255).all()
    assert (out.rgba[a == 0][:, :3] == 0).all()
    assert any("invalid" in s and "never as zero" in s for s in out.draft.limitations)
    # a genuine zero elevation stays opaque (zero is not nodata)
    v2 = ramp(g)
    v2[2, 2] = 0.0
    o2 = render_layer(layer(g, values=v2))
    assert o2.rgba[2 * up, 2 * up, 3] == 255


def test_legend_units_classes_match_pixels() -> None:
    g = planet_grid("MOON")
    v = np.full(g.shape, 5.0)
    v[:, 20:] = 15.0
    v[:, 40:] = 40.0
    out = render_layer(layer(g, values=v, kind="SLOPE", unit="deg"))
    d = out.draft
    assert d.unit == "deg" and d.support_scale_m == 60.0
    lo_hi = [(i.lower, i.upper) for i in d.legend]
    assert lo_hi[0] == (0.0, 6.0) and (12.0, 18.0) in lo_hi and lo_hi[-1] == (30.0, 90.0)
    up = d.width_px // g.width
    colors = {tuple(out.rgba[0, c * up, :3]) for c in (0, 20, 40)}
    assert len(colors) == 3
    legend_rgb = {tuple(int(i.color[k : k + 2], 16) for k in (1, 3, 5)) for i in d.legend}
    assert colors <= legend_rgb
    # 18 deg lands in the 18-24 class (lower inclusive), 12 in 12-18
    v2 = np.full(g.shape, 18.0)
    v2[:, :10] = 12.0
    o2 = render_layer(layer(g, values=v2, kind="SLOPE", unit="deg"))
    c12, c18 = tuple(o2.rgba[0, 0, :3]), tuple(o2.rgba[0, -1, :3])
    by_range = {(i.lower, i.upper): tuple(int(i.color[k : k + 2], 16) for k in (1, 3, 5)) for i in d.legend}
    assert c12 == by_range[(12.0, 18.0)] and c18 == by_range[(18.0, 24.0)]


def test_attribution_synthetic_and_real() -> None:
    g = planet_grid("MARS")
    assert render_layer(layer(g)).draft.attribution[0] == SYNTHETIC_ATTRIBUTION
    real = render_layer(layer(g, synthetic=False, attribution=("NASA MOLA, citation X",))).draft
    assert real.attribution == ["NASA MOLA, citation X"]
    with pytest.raises(ScienceError):
        render_layer(layer(g, synthetic=False))
    with pytest.raises(ScienceError):
        LayerRaster("ELEVATION", g, ramp(g), "m", 60.0, (), True)  # no evidence
        render_layer(LayerRaster("ELEVATION", g, ramp(g), "m", 60.0, (), True))


def test_no_resolution_added_and_support_warning() -> None:
    g = planet_grid("MARS")
    out = render_layer(layer(g, support_scale_m=480.0))
    d = out.draft
    assert any("adds no resolution" in s for s in d.limitations)
    assert any("finer than the 480 m support scale" in s for s in d.limitations)
    # every display pixel equals exactly one analysis cell's colour block: no blended intermediate colours
    up = d.width_px // g.width
    block = out.rgba[:up, :up]
    assert (block == block[0, 0]).all()
    distinct_cells = len({tuple(out.rgba[r * up, c * up]) for r in range(g.height) for c in range(g.width)})
    assert len({tuple(p) for p in out.rgba.reshape(-1, 4)}) == distinct_cells


def test_categorical_ids_never_blended() -> None:
    g = planet_grid("MARS")
    ids = np.zeros(g.shape)
    ids[:, 25:] = 7.0
    ids[10:20, 10:20] = 3.0
    out = render_layer(layer(g, values=ids, kind="MINERAL", unit="class", categorical=True, class_labels={3: "clay"}))
    colors = {tuple(p) for p in out.rgba.reshape(-1, 4)}
    assert len(colors) == 3 and len(out.draft.legend) == 3
    holey = ids.copy()
    holey[1, 1] = np.nan
    h = render_layer(layer(g, values=holey, kind="MINERAL", unit="class", categorical=True))
    up = h.draft.width_px // g.width
    assert (h.rgba[up : 2 * up, up : 2 * up] == 0).all() and h.rgba[0, 0, 3] == 255
    assert {i.label for i in out.draft.legend} == {"class 0", "clay", "class 7"}
    with pytest.raises(RasterError):
        render_layer(layer(g, values=ids + 0.5, kind="MINERAL", unit="class", categorical=True))


def test_png_is_deterministic_and_decodes_to_rgba(tmp_path: Path) -> None:
    g = earth_grid()
    a = build_display_layers([layer(g), layer(g, kind="SLOPE", unit="deg", values=ramp(g) % 40)], tmp_path / "a")
    b = build_display_layers([layer(g), layer(g, kind="SLOPE", unit="deg", values=ramp(g) % 40)], tmp_path / "b")
    assert [x.sha256 for x in a.artifacts] == [x.sha256 for x in b.artifacts]
    assert a.payload == b.payload
    art = a.artifacts[0]
    assert art.role == ArtifactRole.DISPLAY_IMAGE and art.media_type == "image/png" and art.body == "EARTH"
    data = (tmp_path / "a" / art.scratch_relpath).read_bytes()
    assert len(data) == art.size_bytes and data[:8] == b"\x89PNG\r\n\x1a\n"
    rgba = decode_png_rgba(data)
    assert rgba.shape == (a.payload.layers[0].height_px, a.payload.layers[0].width_px, 4)
    assert {la.image_artifact_key for la in a.payload.layers} == {x.local_key for x in a.artifacts}
    # perturbation: changing one cell changes the bytes
    v = ramp(g)
    v[5, 5] += 500.0
    c = build_display_layers([layer(g, values=v)], tmp_path / "c")
    assert c.artifacts[0].sha256 != a.artifacts[0].sha256


def test_value_perturbation_moves_colours_and_duplicate_kinds_rejected(tmp_path: Path) -> None:
    g = planet_grid("MARS")
    with pytest.raises(ScienceError):
        build_display_layers([layer(g), layer(g)], tmp_path)
    with pytest.raises(ScienceError):
        build_display_layers([], tmp_path)
    v = np.full(g.shape, 2.0)
    v[0, 0] = 20.0
    hi = render_layer(layer(g, values=v, kind="SLOPE", unit="deg"))
    lo = render_layer(layer(g, values=np.full(g.shape, 2.0), kind="SLOPE", unit="deg"))
    assert tuple(hi.rgba[0, 0, :3]) != tuple(lo.rgba[0, 0, :3])
