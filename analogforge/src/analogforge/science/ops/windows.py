"""Candidate-window geometry from ``config/candidates.yaml`` (fixed practice grid and generated local-dataset grid)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pyproj import CRS

from analogforge.ports.domain_models import AreaOfInterest
from analogforge.science.config import ScienceConfig, SearchRegionSet
from analogforge.science.geometry import AnalysisGridSpec, frame_from_crs_wkt, lonlat_to_xy, unwrap_bbox
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
    n = rs.window_cells if rs.kind == "FIXED_GRID" else max(3, int(rs.window_cells * rs.cell_size_m / grid.cell_size_m))
    inside = 0 <= r0 and 0 <= c0 and r0 + n <= grid.height and c0 + n <= grid.width
    return WindowSpec(window_id, row, col, r0, c0, n, n, nc, inside)


def region_windows(rs: SearchRegionSet, grid: AnalysisGridSpec) -> list[WindowSpec]:
    """All windows of a region set on ``grid`` in declaration order (fixed) or NW row-major order (generated)."""
    if (rs.kind == "FIXED_GRID" and abs(grid.cell_size_m - rs.cell_size_m) > 1e-6 * rs.cell_size_m
            or rs.kind == "GENERATED_GRID" and grid.cell_size_m < rs.cell_size_m - 1e-6):
        raise OpBlocked(
            f"source cell {grid.cell_size_m} m differs from the region-set cell {rs.cell_size_m} m",
            code="SCALE_INCOMPATIBLE",
            detail_code="CELL_MISMATCH",
        )
    out: list[WindowSpec] = []
    if rs.kind == "GENERATED_GRID" and rs.window_cells * rs.cell_size_m < 3 * grid.cell_size_m:
        raise OpBlocked("Source is too coarse for three cells within the configured window",
                        code="SCALE_INCOMPATIBLE", detail_code="WINDOW_SUPPORT_TOO_COARSE")
    n = rs.window_cells if rs.kind == "FIXED_GRID" else max(3, int(rs.window_cells * rs.cell_size_m / grid.cell_size_m))
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


def find_window(
    cfg: ScienceConfig, window_id: str, grid: AnalysisGridSpec, aoi: AreaOfInterest | None = None,
) -> WindowSpec:
    """The window with this id in the first region set that defines it on ``grid`` (fixed sets first)."""
    sets = sorted(cfg.candidates.search_region_sets.items(), key=lambda kv: (kv[1].kind != "FIXED_GRID", kv[0]))
    last: OpBlocked | None = None
    centre = None
    if aoi is not None:
        if aoi.body != grid.body:
            raise OpBlocked("Candidate AOI body differs from its terrain source", detail_code="BODY_MISMATCH")
        west, south, east, north = unwrap_bbox(tuple(aoi.bbox), aoi.longitude_convention)  # type: ignore[arg-type]
        frame = frame_from_crs_wkt(grid.body, grid.crs_wkt)
        centre = lonlat_to_xy(frame, (west + east) / 2, (south + north) / 2)
    for _, rs in sets:
        pattern = re.compile(
            "^" + re.escape(rs.id_pattern).replace(r"\{row\}", r"\d+").replace(r"\{col\}", r"\d+") + "$"
        )
        if not pattern.match(window_id):
            continue
        try:
            for w in region_windows(rs, grid):
                if w.window_id == window_id:
                    if centre is not None:
                        x = grid.origin_x_m + (w.c0 + w.width / 2) * grid.cell_size_m
                        y = grid.origin_y_m - (w.r0 + w.height / 2) * grid.cell_size_m
                        if (abs(x - float(centre[0])) > grid.cell_size_m / 2
                                or abs(y - float(centre[1])) > grid.cell_size_m / 2):
                            continue
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
