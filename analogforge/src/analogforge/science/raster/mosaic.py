"""Tile mosaicking on a common sample lattice, and registration control points.

Adjacent tiles that share border samples (e.g. SRTM/NASADEM ``.hgt`` tiles overlap by one sample) are placed on one
lattice so the shared row/column appears **once**: no duplicated column, no seam, no distance shift.  Tile origins
that do not fall on the lattice (a sub-pixel registration offset) are rejected.  Overlapping samples must agree.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from analogforge.science.errors import RasterError
from analogforge.science.geometry import AnalysisGridSpec

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class Tile:
    """A north-up tile; ``origin_x_m``/``origin_y_m`` are the west and north edges of its first cell."""

    name: str
    values: FloatArray  # NaN where missing
    origin_x_m: float
    origin_y_m: float
    cell_size_m: float


@dataclass(frozen=True)
class MosaicResult:
    values: FloatArray  # NaN where no tile supplied a valid sample
    covered: BoolArray
    origin_x_m: float
    origin_y_m: float
    cell_size_m: float


def mosaic_tiles(
    tiles: Sequence[Tile], *, lattice_tolerance_cells: float = 1e-6, value_tolerance: float = 1e-9
) -> MosaicResult:
    """Merge tiles onto one lattice.  Overlapping valid samples must agree within ``value_tolerance``."""
    if not tiles:
        raise RasterError("no tiles to mosaic")
    cell = tiles[0].cell_size_m
    if not cell > 0:
        raise RasterError("cell size must be positive")
    for t in tiles:
        if t.values.ndim != 2:
            raise RasterError(f"tile {t.name} is not 2-D")
        if abs(t.cell_size_m - cell) > 1e-9 * cell:
            raise RasterError(f"tile {t.name} has a different cell size", code="SCALE_INCOMPATIBLE")
    ordered = sorted(tiles, key=lambda t: (-t.origin_y_m, t.origin_x_m, t.name))
    x0 = min(t.origin_x_m for t in ordered)
    y0 = max(t.origin_y_m for t in ordered)
    placements: list[tuple[Tile, int, int]] = []
    for t in ordered:
        col_f = (t.origin_x_m - x0) / cell
        row_f = (y0 - t.origin_y_m) / cell
        if abs(col_f - round(col_f)) > lattice_tolerance_cells or abs(row_f - round(row_f)) > lattice_tolerance_cells:
            raise RasterError(
                f"tile {t.name} is offset by a fraction of a cell from the lattice (registration error)",
                detail_code="REGISTRATION_OFFSET",
            )
        placements.append((t, int(round(row_f)), int(round(col_f))))
    height = max(r + t.values.shape[0] for t, r, _ in placements)
    width = max(c + t.values.shape[1] for t, _, c in placements)
    out = np.full((height, width), np.nan)
    for t, r, c in placements:
        window = out[r : r + t.values.shape[0], c : c + t.values.shape[1]]
        incoming = t.values
        both = np.isfinite(window) & np.isfinite(incoming)
        if np.any(np.abs(window[both] - incoming[both]) > value_tolerance):
            raise RasterError(
                f"tile {t.name} disagrees with its neighbour on shared samples", detail_code="SEAM_CONFLICT"
            )
        take = np.isfinite(incoming) & ~np.isfinite(window)
        window[take] = incoming[take]
    return MosaicResult(values=out, covered=np.isfinite(out), origin_x_m=x0, origin_y_m=y0, cell_size_m=cell)


@dataclass(frozen=True)
class ControlPoint:
    """A location with an independently known value (chosen from the inspected product, never invented)."""

    name: str
    x_m: float
    y_m: float
    expected_value: float
    tolerance: float


@dataclass(frozen=True)
class ControlPointResult:
    name: str
    observed: float | None  # None: outside the grid or missing sample
    expected: float
    passed: bool


def check_control_points(
    grid: AnalysisGridSpec, values: FloatArray, controls: Sequence[ControlPoint]
) -> list[ControlPointResult]:
    """Compare the sample under each control point with its expected value (catches a one-pixel offset)."""
    if values.shape != grid.shape:
        raise RasterError("values shape does not match the grid")
    results: list[ControlPointResult] = []
    for cp in controls:
        idx = grid.index_of(cp.x_m, cp.y_m)
        observed: float | None = None
        if idx is not None and math.isfinite(float(values[idx])):
            observed = float(values[idx])
        passed = observed is not None and abs(observed - cp.expected_value) <= cp.tolerance
        results.append(ControlPointResult(cp.name, observed, cp.expected_value, passed))
    return results
