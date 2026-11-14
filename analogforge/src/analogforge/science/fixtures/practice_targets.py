"""Synthetic practice target rasters: Mars strips, Moon polar rings, Moon thermal (architecture 40 section 3).

SYNTHETIC PRACTICE DATA - not terrain of the named location.  The slope-area fractions are produced by geometry
(strip widths / ring radii derived from the requested fractions); nothing here stores a histogram.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from analogforge.science.fixtures.practice_earth import SEED_DEFAULT, dataset_rng
from analogforge.science.geometry import (
    AnalysisGridSpec,
    ProjectedFrame,
    lonlat_to_xy,
    projected_frame_for_aoi,
)

FloatArray = NDArray[np.float64]
Int16Array = NDArray[np.int16]

MARS_AOI = (137.0, -5.0, 138.0, -4.0)
MOON_AOI = (-10.0, -89.5, 10.0, -87.5)
MARS_CELLS = 128
MARS_CELL_M = 480.0
MOON_CELLS = 160
MOON_CELL_M = 960.0
MARS_FRACTIONS: tuple[tuple[float, float], ...] = ((3.0, 0.40), (7.0, 0.30), (14.0, 0.20), (22.0, 0.10))
MOON_FRACTIONS: tuple[tuple[float, float], ...] = ((2.0, 0.50), (6.0, 0.30), (13.0, 0.15), (20.0, 0.05))
MARS_BASE_ELEVATION_M = 2500.0
MOON_SCALE_FACTOR = 0.5
MOON_OFFSET_M = 1737400.0
MOON_REFERENCE_RADIUS_M = 1737400.0
MARS_VERTICAL_REFERENCE = "SYNTHETIC_MARS_REFERENCE_SPHERE_3396190M"
MOON_VERTICAL_REFERENCE = "SYNTHETIC lunar reference sphere radius 1737400 m"
NODATA_MARS = -32768.0
THERMAL_COLD_TRAP_MIN_K = 88.0


def _check_fractions(fractions: tuple[tuple[float, float], ...]) -> None:
    if not fractions or any(f < 0 for _, f in fractions) or abs(sum(f for _, f in fractions) - 1.0) > 1e-9:
        raise ValueError("target_fractions must be (slope_deg, fraction) pairs summing to 1")


@dataclass(frozen=True)
class TargetRaster:
    """Generated target raster: ``values`` are the stored (file) values, ``grid`` their georeference."""

    values: NDArray[np.number]
    grid: AnalysisGridSpec
    frame: ProjectedFrame
    nodata_value: float | None


def _centred_grid(frame: ProjectedFrame, cx: float, cy: float, cells: int, cell_m: float) -> AnalysisGridSpec:
    half = 0.5 * cells * cell_m
    return AnalysisGridSpec(
        body=frame.body,
        crs_wkt=frame.crs_wkt,
        origin_x_m=cx - half,
        origin_y_m=cy + half,
        cell_size_m=cell_m,
        width=cells,
        height=cells,
    )


def mars_target(
    target_fractions: tuple[tuple[float, float], ...] = MARS_FRACTIONS, seed: int = SEED_DEFAULT, noise_m: float = 0.0
) -> TargetRaster:
    """128x128 at 480 m: alternating-sign planar column strips whose widths are ``fraction * 128`` cells."""
    _check_fractions(target_fractions)
    frame = projected_frame_for_aoi("MARS", MARS_AOI, "ZERO_360")
    lon_c, lat_c = 0.5 * (MARS_AOI[0] + MARS_AOI[2]), 0.5 * (MARS_AOI[1] + MARS_AOI[3])
    cx, cy = lonlat_to_xy(frame, lon_c, lat_c)
    grid = _centred_grid(frame, float(cx), float(cy), MARS_CELLS, MARS_CELL_M)
    edges = [0]
    acc = 0.0
    for _, frac in target_fractions:
        acc += frac * MARS_CELLS
        edges.append(round(acc))
    edges[-1] = MARS_CELLS
    profile = np.zeros(MARS_CELLS, dtype=np.float64)
    height = 0.0
    for i, (slope, _) in enumerate(target_fractions):
        sign = 1.0 if i % 2 == 0 else -1.0
        step = sign * math.tan(math.radians(slope)) * MARS_CELL_M
        for c in range(edges[i], edges[i + 1]):
            profile[c] = height
            height += step
    profile -= profile.min()
    z = np.tile(profile + MARS_BASE_ELEVATION_M, (MARS_CELLS, 1))
    if noise_m > 0:
        z += dataset_rng(seed, "practice-mars-target-v1").normal(0.0, noise_m, size=z.shape)
    return TargetRaster(np.asarray(z, dtype=np.float32), grid, frame, NODATA_MARS)


def _ring_radii(rho_min: float, rho_max: float, fractions: tuple[tuple[float, float], ...]) -> list[float]:
    """Outer radii of the rings: area (proportional to rho squared) shares equal the requested fractions."""
    out: list[float] = []
    acc = 0.0
    for _, frac in fractions:
        acc += frac
        out.append(math.sqrt(rho_min**2 + acc * (rho_max**2 - rho_min**2)))
    return out


def moon_wedge_radii() -> tuple[float, float]:
    """Projected radial distances (m) of the AOI wedge's inner and outer latitude circles."""
    frame = projected_frame_for_aoi("MOON", MOON_AOI, "NEG180_180")
    inner = lonlat_to_xy(frame, 0.0, MOON_AOI[1])
    outer = lonlat_to_xy(frame, 0.0, MOON_AOI[3])
    return float(math.hypot(*inner)), float(math.hypot(*outer))


def moon_target(
    target_fractions: tuple[tuple[float, float], ...] = MOON_FRACTIONS, seed: int = SEED_DEFAULT, noise_m: float = 0.0
) -> TargetRaster:
    """160x160 at 960 m, polar stereographic: rings of constant radial slope about the pole, stored as int16 radius.

    The stored value is ``round(height / 0.5)``; with ``scale_factor=0.5``, ``offset=1737400`` (metres) the radius
    is ``raw * 0.5 + 1737400`` and the height is that minus the reference radius.
    """
    _check_fractions(target_fractions)
    frame = projected_frame_for_aoi("MOON", MOON_AOI, "NEG180_180")
    grid = _centred_grid(frame, 0.0, 0.0, MOON_CELLS, MOON_CELL_M)
    rho_min, rho_max = moon_wedge_radii()
    radii = _ring_radii(rho_min, rho_max, target_fractions)
    cx = grid.origin_x_m + (np.arange(MOON_CELLS) + 0.5) * MOON_CELL_M
    cy = grid.origin_y_m - (np.arange(MOON_CELLS) + 0.5) * MOON_CELL_M
    xx, yy = np.meshgrid(cx, cy)
    rho = np.hypot(xx, yy)
    slopes = [math.tan(math.radians(s)) for s, _ in target_fractions]
    flat_beyond = rho_max + 6000.0  # the last ring continues a little past the wedge, then flattens
    bounds = [0.0, *radii[:-1], flat_beyond]
    z = np.zeros_like(rho)
    for i, tan_s in enumerate(slopes):
        z += tan_s * (np.clip(rho, bounds[i], bounds[i + 1]) - bounds[i])
    z -= 0.5 * (z.max() + z.min())  # centre the relief on the reference sphere so int16 covers +-16 km
    if noise_m > 0:
        z += dataset_rng(seed, "practice-moon-target-v1").normal(0.0, noise_m, size=z.shape)
    raw = np.rint(z / MOON_SCALE_FACTOR)
    if np.abs(raw).max() > 32767:
        raise ValueError("moon target heights overflow int16 at scale 0.5")
    return TargetRaster(np.asarray(raw, dtype=np.int16), grid, frame, None)


def moon_wedge_mask(grid: AnalysisGridSpec) -> NDArray[np.bool_]:
    """Cells of ``grid`` whose centres lie inside the AOI wedge (longitude -10..10, latitude -89.5..-87.5)."""
    from analogforge.science.geometry import xy_to_lonlat

    cx = grid.origin_x_m + (np.arange(grid.width) + 0.5) * grid.cell_size_m
    cy = grid.origin_y_m - (np.arange(grid.height) + 0.5) * grid.cell_size_m
    xx, yy = np.meshgrid(cx, cy)
    frame = projected_frame_for_aoi("MOON", MOON_AOI, "NEG180_180")
    lon, lat = xy_to_lonlat(frame, xx, yy, "NEG180_180")
    return np.asarray(
        (lon >= MOON_AOI[0]) & (lon <= MOON_AOI[2]) & (lat >= MOON_AOI[1]) & (lat <= MOON_AOI[3]), dtype=bool
    )


def moon_thermal(seed: int = SEED_DEFAULT, cold_trap_radius_m: float = 5000.0) -> TargetRaster:
    """Float32 kelvin on the Moon polar grid: 160-250 K, with a cold-trap disc at 88 K (nodata 0, none present)."""
    frame = projected_frame_for_aoi("MOON", MOON_AOI, "NEG180_180")
    grid = _centred_grid(frame, 0.0, 0.0, MOON_CELLS, MOON_CELL_M)
    cx = grid.origin_x_m + (np.arange(MOON_CELLS) + 0.5) * MOON_CELL_M
    cy = grid.origin_y_m - (np.arange(MOON_CELLS) + 0.5) * MOON_CELL_M
    xx, yy = np.meshgrid(cx, cy)
    rng = dataset_rng(seed, "practice-moon-thermal-v1")
    phase = rng.uniform(0.0, 2.0 * math.pi, size=2)
    smooth = 0.5 + 0.5 * np.sin(xx / 23000.0 + phase[0]) * np.cos(yy / 31000.0 + phase[1])
    temp = 160.0 + 90.0 * smooth
    rho_min, rho_max = moon_wedge_radii()
    trap_xy = (0.0, 0.5 * (rho_min + rho_max))  # on the lon=0 meridian inside the wedge
    d = np.hypot(xx - trap_xy[0], yy - trap_xy[1])
    edge = np.clip((d / cold_trap_radius_m - 0.5) / 0.5, 0.0, 1.0)  # flat 88 K core, smooth rise to the rim
    temp = np.where(d <= cold_trap_radius_m, THERMAL_COLD_TRAP_MIN_K + 6.0 * edge**2, temp)
    return TargetRaster(np.asarray(temp, dtype=np.float32), grid, frame, 0.0)
