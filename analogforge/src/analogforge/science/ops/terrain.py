"""Terrain-analysis helpers shared by CHARACTERIZE_TARGET, SCREEN_CANDIDATES and ANALYZE_CANDIDATE."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from analogforge.ports.domain_models import AreaOfInterest, MeasuredMetric
from analogforge.science.comparison.scale import aggregation_factor
from analogforge.science.features.histogram import (
    area_weighted_histogram,
    band_area_fraction,
    slope_area_metric_id,
    slope_statistics,
)
from analogforge.science.features.relief import robust_relief_m
from analogforge.science.features.roughness import detrended_rms_height_m, relief_metric_id, roughness_metric_id
from analogforge.science.features.slope import SurfaceAnalysis, analyze_surface
from analogforge.science.geometry import AnalysisGridSpec, PixelGeometry, ProjectedFrame, projected_bounds_to_bbox
from analogforge.science.raster.normalize import aggregate_any, aggregate_blocks
from analogforge.science.raster.source import SourceRaster

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class Prepared:
    """A source analysed over its WHOLE extent at ``support_m`` (derivatives first, windows cropped afterwards)."""

    grid: AnalysisGridSpec
    elevation: FloatArray  # NaN where missing
    nodata: BoolArray
    water: BoolArray
    surf: SurfaceAnalysis
    support_m: float
    factor: int


def prepare(src: SourceRaster, support_m: float | None, flat_tol: float) -> Prepared:
    """Area-average to ``max(native, support_m)`` (never upsample) and compute the surface over the whole raster."""
    native = src.native_resolution_m
    target = native if support_m is None else max(native, support_m)
    factor = aggregation_factor(native, target)
    water = np.zeros(src.values.shape, dtype=bool) if src.water is None else src.water
    if factor == 1:
        grid, elev, nodata, wet = src.grid, src.values, src.nodata, water
    else:
        wet_any = aggregate_any(water, factor)
        usable = ~src.nodata & ~water
        elev, ok = aggregate_blocks(src.values, usable, factor)
        grid = src.grid.aggregated(factor)
        wet = wet_any
        nodata = ~ok & ~wet_any
    surf = analyze_surface(
        elev, PixelGeometry.north_up(grid.cell_size_m), nodata=nodata, water=wet, flat_gradient_tolerance=flat_tol
    )
    return Prepared(grid, elev, nodata, wet, surf, grid.cell_size_m, factor)


def metric(
    metric_id: str,
    value: float | None,
    unit: str,
    scale: float | None,
    valid_fraction: float,
    method: str,
    note: str = "Nominal modeled value; uncertainty not quantified.",
) -> MeasuredMetric:
    return MeasuredMetric(
        metric_id=metric_id,
        value=value,
        unit=unit,
        support_scale_m=scale,
        quantity_kind="DERIVED",
        method_id=method,
        valid_fraction=min(1.0, max(0.0, valid_fraction)),
        uncertainty_note=note,
    )


def band_pairs(edges: tuple[float, ...]) -> list[tuple[float, float]]:
    return [(edges[i], edges[j]) for i in range(len(edges)) for j in range(i + 1, len(edges))]


def band_metrics(
    slope: FloatArray, valid: BoolArray, cell_area: float, edges: tuple[float, ...], scale: float, vf: float
) -> list[MeasuredMetric]:
    out: list[MeasuredMetric] = []
    for lo, hi in band_pairs(edges):
        frac = band_area_fraction(slope, valid, lo, hi, cell_area)
        out.append(metric(slope_area_metric_id(lo, hi), frac, "fraction", scale, vf, "slope-lsq-plane-3x3-v1"))
    return out


def slope_stat_metrics(
    slope: FloatArray, valid: BoolArray, cell_area: float, scale: float, vf: float
) -> list[MeasuredMetric]:
    stats = slope_statistics(slope, valid, cell_area)
    return [metric(f"surface_slope_deg:{k}", v, "deg", scale, vf, "slope-lsq-plane-3x3-v1") for k, v in stats.items()]


def roughness_metrics(
    elevation: FloatArray,
    usable: BoolArray,
    windows: tuple[int, ...],
    cell_m: float,
    valid: BoolArray,
    vf: float,
) -> list[MeasuredMetric]:
    out: list[MeasuredMetric] = []
    elev = np.where(usable, elevation, 0.0)
    for w in windows:
        if min(elev.shape) < w:
            continue
        rms, ok = detrended_rms_height_m(elev, usable, w)
        rel, ok2 = robust_relief_m(elev, usable, w)
        m1, m2 = ok & valid, ok2 & valid
        out.append(
            metric(
                roughness_metric_id(w, cell_m),
                float(np.mean(rms[m1])) if m1.any() else None,
                "m",
                cell_m * w,
                vf,
                "roughness-detrended-rms-v1",
            )
        )
        out.append(
            metric(
                relief_metric_id(w, cell_m),
                float(np.mean(rel[m2])) if m2.any() else None,
                "m",
                cell_m * w,
                vf,
                "relief-robust-q05-q95-v1",
            )
        )
    return out


def hist_of(slope: FloatArray, valid: BoolArray, cell_area: float, edges: tuple[float, ...]):  # type: ignore[no-untyped-def]
    return area_weighted_histogram(np.where(valid, slope, 0.0), valid, cell_area, edges)


def aoi_for_bounds(
    frame: ProjectedFrame, bounds: tuple[float, float, float, float], vertical_datum: str
) -> AreaOfInterest:
    bbox = projected_bounds_to_bbox(frame, bounds, "NEG180_180")
    return AreaOfInterest(
        body="EARTH",
        bbox=[float(v) for v in bbox],
        longitude_convention="NEG180_180",
        latitude_type="GEODETIC",
        crs_wkt=None,
        vertical_datum=vertical_datum,
    )


def clean_aspect(aspect: FloatArray) -> FloatArray:
    """Fold aspect values that round to exactly 360.0 back to 0 (``-1e-15 % 360.0 == 360.0`` in floating point)."""
    return np.asarray(np.where(aspect >= 360.0, aspect - 360.0, aspect), dtype=np.float64)
