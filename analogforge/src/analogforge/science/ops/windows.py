"""Candidate-window geometry from ``config/candidates.yaml`` (fixed practice grid and generated local-dataset grid)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pyproj import CRS

from analogforge.science.config import ScienceConfig, SearchRegionSet
from analogforge.science.geometry import AnalysisGridSpec
from analogforge.science.ops.base import OpBlocked


@dataclass(frozen=True)
class WindowSpec:
    window_id: str
    row: int
    col: int
    r0: int  # first cell row/col in the source grid (may be negative/outside when the window misses the source)
    c0: int
    height: int
    width: int
    negative_control: bool
    inside_source: bool

    @property
    def bounds_cells(self) -> tuple[int, int, int, int]:
        return self.r0, self.c0, self.height, self.width


def _epsg(grid: AnalysisGridSpec) -> int | None:
    return CRS.from_wkt(grid.crs_wkt).to_epsg(min_confidence=70)


def _make(
    rs: SearchRegionSet, grid: AnalysisGridSpec, window_id: str, row: int, col: int, nc: bool, r0: int, c0: int
) -> WindowSpec:
    n = rs.window_cells
    inside = 0 <= r0 and 0 <= c0 and r0 + n <= grid.height and c0 + n <= grid.width
    return WindowSpec(window_id, row, col, r0, c0, n, n, nc, inside)


def region_windows(rs: SearchRegionSet, grid: AnalysisGridSpec) -> list[WindowSpec]:
    """All windows of a region set on ``grid`` in declaration order (fixed) or NW row-major order (generated)."""
    if abs(grid.cell_size_m - rs.cell_size_m) > 1e-6 * rs.cell_size_m:
        raise OpBlocked(
            f"source cell {grid.cell_size_m} m differs from the region-set cell {rs.cell_size_m} m",
            code="SCALE_INCOMPATIBLE",
            detail_code="CELL_MISMATCH",
        )
    out: list[WindowSpec] = []
    n = rs.window_cells
    if rs.kind == "FIXED_GRID":
        assert rs.sw_easting_m is not None and rs.north_northing_m is not None
        if _epsg(grid) != rs.crs_epsg:
            raise OpBlocked(
                f"source CRS is not EPSG:{rs.crs_epsg} required by the fixed grid",
                code="UNSUPPORTED_CRS",
                detail_code="CRS_MISMATCH",
            )
        for w in rs.windows:
            x0 = rs.sw_easting_m + w.col * n * rs.cell_size_m
            top = rs.north_northing_m - w.row * n * rs.cell_size_m
            c0 = round((x0 - grid.origin_x_m) / grid.cell_size_m)
            r0 = round((grid.origin_y_m - top) / grid.cell_size_m)
            out.append(_make(rs, grid, w.window_id, w.row, w.col, w.negative_control, r0, c0))
        return out
    rows, cols = grid.height // n, grid.width // n
    for r in range(rows):
        for c in range(cols):
            wid = rs.id_pattern.format(row=r, col=c)
            out.append(_make(rs, grid, wid, r, c, wid in rs.negative_control_window_ids, r * n, c * n))
    return out


def find_window(cfg: ScienceConfig, window_id: str, grid: AnalysisGridSpec) -> WindowSpec:
    """The window with this id in the first region set that defines it on ``grid`` (fixed sets first)."""
    sets = sorted(cfg.candidates.search_region_sets.items(), key=lambda kv: (kv[1].kind != "FIXED_GRID", kv[0]))
    last: OpBlocked | None = None
    for _, rs in sets:
        pattern = re.compile(
            "^" + re.escape(rs.id_pattern).replace(r"\{row\}", r"\d+").replace(r"\{col\}", r"\d+") + "$"
        )
        if not pattern.match(window_id):
            continue
        try:
            for w in region_windows(rs, grid):
                if w.window_id == window_id:
                    return w
        except OpBlocked as exc:
            last = exc
    if last is not None:
        raise last
    raise OpBlocked(
        f"window {window_id!r} is not defined by any search region set",
        code="NO_COVERAGE",
        detail_code="WINDOW_UNKNOWN",
    )
