"""``BUILD_DISPLAY_LAYERS`` core (guide 08 section 4.14, architecture 18).

A :class:`LayerRaster` (values on an analysis grid, ``NaN`` = invalid) becomes a PNG plus a
:class:`~analogforge.ports.science_payloads.DisplayLayerDraft`.

* EARTH: the image is rendered in Web Mercator (EPSG:3857).  ``pixel_to_world`` is the GDAL-order affine of that image
  in metres, ``earth_corners`` are the four WGS84 image corners in NW, NE, SE, SW order.
* MOON / MARS: planar image on the grid's own body-specific CRS (Earth CRS rejected); ``pixel_to_world`` is the grid
  geotransform scaled by the integer display factor; ``earth_corners`` is ``None``.

Display pixels are nearest-neighbour samples of analysis cells: nothing is smoothed or interpolated, so the display
adds no resolution, and categorical ids are never blended.  Invalid cells get alpha 0 (never a colour or zero).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from pyproj import CRS

from analogforge.ports.common import EvidenceRef
from analogforge.ports.science import ArtifactDraft, ArtifactRole
from analogforge.ports.science_payloads import BuildDisplayLayersPayload, DisplayLayerDraft
from analogforge.rendering.tiles.legend import ColorClass, colorize, hex_to_rgb
from analogforge.science.display.legend import (
    categorical_classes,
    continuous_classes,
    slope_classes,
    to_legend,
)
from analogforge.science.display.png import PNG_MEDIA_TYPE, encode_png_rgba
from analogforge.science.errors import GeometryError, RasterError, ScienceError
from analogforge.science.geometry import (
    AnalysisGridSpec,
    assert_crs_matches_body,
    frame_from_crs_wkt,
    lonlat_to_xy,
    xy_to_lonlat,
)
from analogforge.science.provenance import write_scratch_artifact
from analogforge.science.raster.store import AnalysisGrid

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
LayerKind = Literal["ELEVATION", "SLOPE", "ROUGHNESS", "THERMAL", "MINERAL"]

SYNTHETIC_ATTRIBUTION: Final = "SYNTHETIC PRACTICE DATA — not terrain of this location"
NO_RESOLUTION_LIMITATION: Final = "Display smoothing adds no resolution."
WEB_MERCATOR_RADIUS_M: Final = 6378137.0
MERCATOR_MAX_LAT_DEG: Final = 85.0511287798066
TARGET_PX: Final = 256
MAX_DIM_PX: Final = 2048
ROUND_TRIP_TOLERANCE_PX: Final = 0.5


@dataclass(frozen=True)
class LayerRaster:
    """Values to display, georeferenced by ``grid`` (``values`` shape ``(height, width)``, NaN = invalid)."""

    kind: LayerKind
    grid: AnalysisGridSpec
    values: FloatArray
    unit: str
    support_scale_m: float | None
    source_evidence: tuple[EvidenceRef, ...]
    synthetic: bool
    attribution: tuple[str, ...] = ()
    categorical: bool = False
    class_labels: Mapping[int, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderedLayer:
    """Rendered pixels and geometry before any file is written."""

    draft: DisplayLayerDraft
    png: bytes
    rgba: NDArray[np.uint8]


@dataclass(frozen=True)
class BuiltLayers:
    payload: BuildDisplayLayersPayload
    artifacts: tuple[ArtifactDraft, ...]


def layer_from_analysis_grid(
    grid: AnalysisGrid,
    kind: Literal["ELEVATION", "SLOPE"],
    *,
    source_evidence: Sequence[EvidenceRef],
    synthetic: bool,
    attribution: Sequence[str] = (),
    support_scale_m: float | None = None,
) -> LayerRaster:
    """ELEVATION (m) or SLOPE (deg) layer of an ANALYSIS_GRID; invalid cells become NaN (transparent)."""
    raw = grid.elevation_m if kind == "ELEVATION" else grid.slope_deg
    values = np.where(grid.valid, raw, np.nan).astype(np.float64)
    return LayerRaster(
        kind=kind,
        grid=grid.spec,
        values=values,
        unit="m" if kind == "ELEVATION" else "deg",
        support_scale_m=grid.meta.cell_size_m if support_scale_m is None else support_scale_m,
        source_evidence=tuple(source_evidence),
        synthetic=synthetic,
        attribution=tuple(attribution),
    )


@lru_cache(maxsize=1)
def web_mercator_wkt() -> str:
    return CRS.from_epsg(3857).to_wkt()


def lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    if abs(lat) > MERCATOR_MAX_LAT_DEG:
        raise GeometryError("latitude is outside the Web Mercator range", code="INPUT_INVALID")
    x = WEB_MERCATOR_RADIUS_M * math.radians(lon)
    y = WEB_MERCATOR_RADIUS_M * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def mercator_to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / WEB_MERCATOR_RADIUS_M)
    lat = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS_M)) - math.pi / 2.0)
    return lon, lat


def apply_affine(
    affine: tuple[float, float, float, float, float, float], col: float, row: float
) -> tuple[float, float]:
    """GDAL-order affine: pixel-corner ``(col, row)`` -> world ``(x, y)``."""
    return (
        affine[0] + col * affine[1] + row * affine[2],
        affine[3] + col * affine[4] + row * affine[5],
    )


def _validate(layer: LayerRaster) -> None:
    if layer.values.shape != layer.grid.shape:
        raise RasterError(f"layer values {layer.values.shape} do not match grid {layer.grid.shape}")
    if not layer.source_evidence:
        raise ScienceError("a display layer needs at least one source evidence reference", code="INPUT_INVALID")
    if not layer.synthetic and not layer.attribution:
        raise ScienceError(
            "real display layers need attribution from the manifest citation/license note", code="INPUT_INVALID"
        )
    if layer.support_scale_m is not None and layer.support_scale_m < 0:
        raise ScienceError("support_scale_m must be non-negative", code="INPUT_INVALID")
    finite = np.isfinite(layer.values)
    if layer.categorical:
        ids = layer.values[finite]
        if ids.size and not np.all(ids == np.round(ids)):
            raise RasterError("categorical ids must be integers; they are never interpolated")


def _classes(layer: LayerRaster) -> list[ColorClass]:
    finite = np.isfinite(layer.values)
    if layer.categorical:
        ids = [int(v) for v in np.unique(layer.values[finite])]
        return categorical_classes(ids, layer.class_labels)
    if layer.kind == "SLOPE":
        return slope_classes()
    if not finite.any():
        return continuous_classes(layer.kind, 0.0, 0.0, layer.unit)
    lo, hi = float(layer.values[finite].min()), float(layer.values[finite].max())
    return continuous_classes(layer.kind, lo, hi, layer.unit)


def _colorize(values: FloatArray, classes: list[ColorClass], categorical: bool) -> NDArray[np.uint8]:
    valid = np.isfinite(values)
    if not categorical:
        return colorize(values, valid, classes)
    rgba = np.zeros(values.shape + (4,), dtype=np.uint8)
    if not classes:
        return rgba
    ids = np.array([c.lower for c in classes], dtype=np.float64)
    palette = np.array([hex_to_rgb(c.color) for c in classes], dtype=np.uint8)
    index = np.searchsorted(ids, np.where(valid, values, ids[0]))
    rgba[..., :3] = palette[np.clip(index, 0, len(classes) - 1)]
    rgba[..., 3] = 255
    rgba[~valid] = 0
    return rgba


def _factor(width: int, height: int) -> tuple[int, int]:
    """``(upscale, stride)``: integer nearest-neighbour upscale for small grids, decimation for huge ones."""
    longest = max(width, height)
    if longest > MAX_DIM_PX:
        return 1, math.ceil(longest / MAX_DIM_PX)
    return max(1, TARGET_PX // longest), 1


def _planar(layer: LayerRaster) -> tuple[NDArray[np.float64], tuple[float, ...], str, float]:
    grid = layer.grid
    upscale, stride = _factor(grid.width, grid.height)
    values = layer.values
    if stride > 1:
        off = stride // 2
        values = values[off::stride, off::stride]
        pixel_m = grid.cell_size_m * stride
    else:
        values = np.repeat(np.repeat(values, upscale, axis=0), upscale, axis=1)
        pixel_m = grid.cell_size_m / upscale
    affine = (grid.origin_x_m, pixel_m, 0.0, grid.origin_y_m, 0.0, -pixel_m)
    return values, affine, grid.crs_wkt, pixel_m


def _earth(layer: LayerRaster) -> tuple[FloatArray, tuple[float, ...], str, float]:
    grid = layer.grid
    frame = frame_from_crs_wkt("EARTH", grid.crs_wkt)
    xmin, ymin, xmax, ymax = grid.bounds
    t = np.linspace(0.0, 1.0, 41)
    xs = np.concatenate([xmin + (xmax - xmin) * t, np.full(41, xmax), xmax - (xmax - xmin) * t, np.full(41, xmin)])
    ys = np.concatenate([np.full(41, ymin), ymin + (ymax - ymin) * t, np.full(41, ymax), ymax - (ymax - ymin) * t])
    lon, lat = xy_to_lonlat(frame, xs, ys)
    x0, y_south = lonlat_to_mercator(float(lon.min()), float(lat.min()))
    x1, y_north = lonlat_to_mercator(float(lon.max()), float(lat.max()))
    scale = 1.0 / math.cos(math.radians(0.5 * (float(lat.min()) + float(lat.max()))))
    upscale, stride = _factor(grid.width, grid.height)
    pixel = grid.cell_size_m * scale * stride / upscale
    width = max(1, math.ceil((x1 - x0) / pixel))
    height = max(1, math.ceil((y_north - y_south) / pixel))
    affine = (x0, pixel, 0.0, y_north, 0.0, -pixel)
    cols = x0 + (np.arange(width) + 0.5) * pixel
    rows = y_north - (np.arange(height) + 0.5) * pixel
    mx, my = np.meshgrid(cols, rows)
    lon_px = np.degrees(mx / WEB_MERCATOR_RADIUS_M)
    lat_px = np.degrees(2.0 * np.arctan(np.exp(my / WEB_MERCATOR_RADIUS_M)) - math.pi / 2.0)
    gx, gy = lonlat_to_xy(frame, lon_px, lat_px)
    col = np.floor((gx - grid.origin_x_m) / grid.cell_size_m).astype(np.int64)
    row = np.floor((grid.origin_y_m - gy) / grid.cell_size_m).astype(np.int64)
    inside = (col >= 0) & (col < grid.width) & (row >= 0) & (row < grid.height)
    out = np.full((height, width), np.nan, dtype=np.float64)
    out[inside] = layer.values[row[inside], col[inside]]
    return out, affine, web_mercator_wkt(), pixel


def earth_corners_from_affine(affine: tuple[float, ...], width: int, height: int) -> list[tuple[float, float]]:
    """WGS84 ``(lon, lat)`` of the image corners in NW, NE, SE, SW order."""
    a = (affine[0], affine[1], affine[2], affine[3], affine[4], affine[5])
    pts = [(0, 0), (width, 0), (width, height), (0, height)]
    return [mercator_to_lonlat(*apply_affine(a, c, r)) for c, r in pts]


def render_layer(layer: LayerRaster) -> RenderedLayer:
    """Render one layer to pixels, PNG bytes and its :class:`DisplayLayerDraft` (nothing is written to disk)."""
    _validate(layer)
    body = layer.grid.body
    if body == "EARTH":
        values, affine, crs_wkt, pixel_m = _earth(layer)
    else:
        assert_crs_matches_body(body, layer.grid.crs_wkt)
        values, affine, crs_wkt, pixel_m = _planar(layer)
    classes = _classes(layer)
    rgba = _colorize(values, classes, layer.categorical)
    png = encode_png_rgba(rgba)
    height, width = values.shape
    corners = earth_corners_from_affine(affine, width, height) if body == "EARTH" else None
    kind = layer.kind.lower()
    limitations = [NO_RESOLUTION_LIMITATION, "Display image only; no later operation consumes it."]
    if body == "EARTH":
        limitations.append(
            "Web Mercator display resampling by nearest analysis cell; scientific values stay on the analysis grid."
        )
    invalid = float(np.mean(~np.isfinite(layer.values)))
    if invalid > 0:
        limitations.append(f"{invalid:.1%} of analysis cells are invalid and shown transparent, never as zero.")
    if layer.support_scale_m is not None and pixel_m < layer.support_scale_m:
        limitations.append(
            f"Display pixels ({pixel_m:.3g} m) are finer than the {layer.support_scale_m:g} m support scale; "
            "zooming adds no information."
        )
    limitations.extend(layer.limitations)
    attribution = [SYNTHETIC_ATTRIBUTION] if layer.synthetic else list(layer.attribution)
    if layer.synthetic:
        attribution.extend(a for a in layer.attribution if a != SYNTHETIC_ATTRIBUTION)
    draft = DisplayLayerDraft(
        local_key=f"display-{kind}",
        body=body,
        layer_kind=layer.kind,
        rendering="EARTH_WEBMERCATOR_IMAGE" if body == "EARTH" else "PLANETARY_PLANAR_IMAGE",
        image_artifact_key=f"display-{kind}-png",
        display_crs_wkt=crs_wkt,
        pixel_to_world=(affine[0], affine[1], affine[2], affine[3], affine[4], affine[5]),
        width_px=width,
        height_px=height,
        earth_corners=corners,
        legend=to_legend(classes),
        unit=layer.unit,
        support_scale_m=layer.support_scale_m,
        source_evidence=list(layer.source_evidence),
        attribution=attribution,
        limitations=limitations,
    )
    return RenderedLayer(draft=draft, png=png, rgba=rgba)


def build_display_layers(layers: Sequence[LayerRaster], scratch_dir: Path) -> BuiltLayers:
    """Render every layer, write the PNGs under ``scratch_dir`` and return the payload and artifact drafts."""
    if not layers:
        raise ScienceError("at least one layer is required", code="INPUT_INVALID")
    drafts: list[DisplayLayerDraft] = []
    artifacts: list[ArtifactDraft] = []
    keys: set[str] = set()
    for layer in layers:
        rendered = render_layer(layer)
        key = rendered.draft.local_key
        if key in keys:
            raise ScienceError(f"duplicate display layer kind {layer.kind}", code="INPUT_INVALID")
        keys.add(key)
        artifacts.append(
            write_scratch_artifact(
                scratch_dir,
                local_key=rendered.draft.image_artifact_key,
                relpath=f"display/{key}.png",
                data=rendered.png,
                media_type=PNG_MEDIA_TYPE,
                role=ArtifactRole.DISPLAY_IMAGE,
                body=layer.grid.body,
                crs_wkt=rendered.draft.display_crs_wkt,
                support_scale_m=layer.support_scale_m,
            )
        )
        drafts.append(rendered.draft)
    return BuiltLayers(BuildDisplayLayersPayload(layers=drafts), tuple(artifacts))


__all__ = [
    "BuiltLayers",
    "LayerKind",
    "LayerRaster",
    "RenderedLayer",
    "SYNTHETIC_ATTRIBUTION",
    "apply_affine",
    "build_display_layers",
    "earth_corners_from_affine",
    "layer_from_analysis_grid",
    "lonlat_to_mercator",
    "mercator_to_lonlat",
    "render_layer",
    "web_mercator_wkt",
]
