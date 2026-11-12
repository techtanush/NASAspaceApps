"""Independent checker for the practice-data properties of architecture 40 section 4 (and the target fractions of 3).

Written without importing ``analogforge.science.routing``: slopes use an own 3x3 plane-fit stencil, connected
components use ``scipy.ndimage``, waypoints (``auto-waypoints-v1`` as in 40 section 6) and the minimum-distance
loop use an own 8-neighbour Dijkstra.  Everything is computed from the raster files / arrays only.

Definitions (shared with ``science.features``, decision C-01): a cell is *valid* when it and its whole 3x3
neighbourhood are usable (finite, not nodata, not water); the grid border is never valid; ``f_band`` is the share of
valid cells whose slope lies in [12, 18).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from scipy import ndimage

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

CELL_M = 60.0
WINDOW = 64
GRID = 192
BAND = (12.0, 18.0)
CAP_DEG = 18.0
NODATA = -32768.0
SQRT2 = math.sqrt(2.0)


@dataclass(frozen=True)
class GridAnalysis:
    slope: FloatArray  # NaN where invalid
    valid: BoolArray
    water: BoolArray
    nodata: BoolArray
    cell_m: float


def plane_fit_slope(elev: FloatArray, usable: BoolArray, cell_m: float) -> tuple[FloatArray, BoolArray]:
    """Slope (deg) of the least-squares plane through each 3x3 neighbourhood; NaN where support is incomplete.

    For a regular 3x3 stencil the least-squares gradient is (sum of east-west differences over three rows) / (6h)
    and (sum of north-south differences over three columns) / (6h).
    """
    z = np.where(usable, elev, 0.0)
    kx = np.array([[-1.0, 0.0, 1.0]] * 3) / (6.0 * cell_m)
    ky = np.array([[1.0] * 3, [0.0] * 3, [-1.0] * 3]) / (6.0 * cell_m)  # north (row-1) minus south (row+1)
    gx = ndimage.correlate(z, kx, mode="constant", cval=0.0)
    gy = ndimage.correlate(z, ky, mode="constant", cval=0.0)
    support = ndimage.binary_erosion(usable, structure=np.ones((3, 3), dtype=bool), border_value=0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return np.where(support, slope, np.nan), np.asarray(support, dtype=bool)


def analyze(
    elevation: FloatArray, water: BoolArray, nodata_value: float = NODATA, cell_m: float = CELL_M
) -> GridAnalysis:
    nodata = ~np.isfinite(elevation) | (elevation == nodata_value)
    usable = ~nodata & ~water
    slope, valid = plane_fit_slope(elevation, usable, cell_m)
    return GridAnalysis(slope=slope, valid=valid, water=water, nodata=nodata, cell_m=cell_m)


def read_practice_grid(directory: Path, dataset_id: str = "practice-earth-grid-v1") -> GridAnalysis:
    """Analyse the Earth grid straight from the generated files (raw GeoTIFFs, no science code)."""
    with rasterio.open(directory / dataset_id / f"{dataset_id}.tif") as src:
        elev = src.read(1).astype(np.float64)
        nodata = src.nodata
    with rasterio.open(directory / dataset_id / f"{dataset_id}-water.tif") as src:
        water = src.read(1) == 1
    return analyze(elev, water, NODATA if nodata is None else float(nodata))


def window_slices(window_id: str) -> tuple[slice, slice]:
    r, c = int(window_id[6]), int(window_id[8])
    return slice(r * WINDOW, (r + 1) * WINDOW), slice(c * WINDOW, (c + 1) * WINDOW)


def in_band(slope: FloatArray) -> BoolArray:
    with np.errstate(invalid="ignore"):
        return np.asarray((slope >= BAND[0]) & (slope < BAND[1]), dtype=bool)


@dataclass(frozen=True)
class WindowMetrics:
    window_id: str
    valid_fraction: float
    water_fraction: float
    f_band: float
    max_slope_deg: float
    band_cells: int
    valid_cells: int


def window_metrics(grid: GridAnalysis, window_id: str) -> WindowMetrics:
    sl = window_slices(window_id)
    valid = grid.valid[sl]
    slope = grid.slope[sl]
    band = in_band(slope) & valid
    n_valid = int(valid.sum())
    return WindowMetrics(
        window_id=window_id,
        valid_fraction=n_valid / valid.size,
        water_fraction=float(grid.water[sl].mean()),
        f_band=float(band.sum()) / n_valid if n_valid else 0.0,
        max_slope_deg=float(np.nanmax(slope)) if n_valid else float("nan"),
        band_cells=int(band.sum()),
        valid_cells=n_valid,
    )


def safe_mask(slope: FloatArray, valid: BoolArray) -> BoolArray:
    with np.errstate(invalid="ignore"):
        return np.asarray(valid & (slope <= CAP_DEG), dtype=bool)


def components8(mask: BoolArray) -> tuple[NDArray[np.int32], int]:
    labels, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    return np.asarray(labels, dtype=np.int32), int(n)


def largest_component(mask: BoolArray) -> BoolArray:
    labels, n = components8(mask)
    if n == 0:
        return np.zeros(mask.shape, dtype=bool)
    sizes = np.bincount(labels.reshape(-1))[1:]
    best = int(np.argmax(sizes)) + 1  # first (row-major order of first cell) among equals is label order
    return np.asarray(labels == best, dtype=bool)


@dataclass(frozen=True)
class Waypoints:
    s: tuple[int, int]
    w1: tuple[int, int]
    w2: tuple[int, int]
    component: BoolArray


def auto_waypoints(slope: FloatArray, valid: BoolArray, edge_cells: int = WINDOW) -> Waypoints:
    """``auto-waypoints-v1`` (40 section 6) with the documented decision that W1/W2 are never band cells."""
    safe = safe_mask(slope, valid)
    comp = largest_component(safe)
    rr, cc = np.nonzero(comp)
    centroid = (rr.mean(), cc.mean())
    d = np.hypot(rr - centroid[0], cc - centroid[1])
    order = np.lexsort((cc, rr, d))  # primary distance, then row-major
    s = (int(rr[order[0]]), int(cc[order[0]]))
    band = in_band(slope) & valid
    counts = ndimage.convolve(band.astype(np.int64), np.ones((5, 5), dtype=np.int64), mode="constant", cval=0)
    edge = edge_cells * CELL_M

    def pick(mask: BoolArray) -> tuple[int, int]:
        rows, cols = np.nonzero(mask)
        if rows.size == 0:
            raise ValueError("no waypoint candidate")
        key = np.lexsort((cols, rows, -counts[rows, cols]))
        return int(rows[key[0]]), int(cols[key[0]])

    gr, gc = np.meshgrid(np.arange(slope.shape[0]), np.arange(slope.shape[1]), indexing="ij")
    ds = np.hypot(gr - s[0], gc - s[1]) * CELL_M
    annulus = comp & ~band & (ds >= 0.15 * edge - 1e-9) & (ds <= 0.30 * edge + 1e-9)
    w1 = pick(annulus)
    dw = np.hypot(gr - w1[0], gc - w1[1]) * CELL_M
    w2 = pick(annulus & (dw >= 0.10 * edge - 1e-9) & ~((gr == w1[0]) & (gc == w1[1])))
    return Waypoints(s=s, w1=w1, w2=w2, component=comp)


_MOVES = [
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, SQRT2),
    (-1, 1, SQRT2),
    (1, -1, SQRT2),
    (1, 1, SQRT2),
]


def _edge_exposure(band: BoolArray, a: tuple[int, int], b: tuple[int, int], length_m: float) -> float:
    return 0.5 * length_m * (float(band[a]) + float(band[b]))


def shortest_leg(
    safe: BoolArray, band: BoolArray, src: tuple[int, int], dst: tuple[int, int]
) -> tuple[float, float, float]:
    """(min distance m, minimum and maximum band exposure m over all minimum-distance 8-neighbour paths)."""
    h, w = safe.shape
    dist = np.full((h, w), np.inf)
    dist[src] = 0.0
    heap: list[tuple[float, int, int]] = [(0.0, src[0], src[1])]
    while heap:
        dcur, r, c = heapq.heappop(heap)
        if dcur > dist[r, c] + 1e-12:
            continue
        for dr, dc, length in _MOVES:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w) or not safe[nr, nc]:
                continue
            if dr != 0 and dc != 0 and not (safe[r + dr, c] and safe[r, c + dc]):
                continue
            nd = dcur + length * CELL_M
            if nd < dist[nr, nc] - 1e-9:
                dist[nr, nc] = nd
                heapq.heappush(heap, (nd, nr, nc))
    if not math.isfinite(dist[dst]):
        raise ValueError("destination unreachable")
    # DP over the shortest-path DAG in order of distance
    cells = [(dist[r, c], r, c) for r, c in zip(*np.nonzero(np.isfinite(dist)), strict=True)]
    cells.sort()
    lo = {src: 0.0}
    hi = {src: 0.0}
    for dcur, r, c in cells:
        if (r, c) not in lo:
            continue
        for dr, dc, length in _MOVES:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w) or not safe[nr, nc]:
                continue
            if dr != 0 and dc != 0 and not (safe[r + dr, c] and safe[r, c + dc]):
                continue
            if abs(dcur + length * CELL_M - dist[nr, nc]) > 1e-6:
                continue
            e = _edge_exposure(band, (r, c), (nr, nc), length * CELL_M)
            lo[(nr, nc)] = min(lo.get((nr, nc), math.inf), lo[(r, c)] + e)
            hi[(nr, nc)] = max(hi.get((nr, nc), -math.inf), hi[(r, c)] + e)
    return float(dist[dst]), lo[dst], hi[dst]


@dataclass(frozen=True)
class LoopResult:
    distance_m: float
    exposure_max_m: float  # unique-exposure upper bound over minimum-distance loops S-W1-W2-W1-S
    exposure_min_m: float


def waypoint_return_loop(slope: FloatArray, valid: BoolArray, wp: Waypoints) -> LoopResult:
    """Minimum-distance closed loop S, W1, W2, W1, S (legs repeated on the same edges earn exposure once)."""
    safe = safe_mask(slope, valid)
    band = in_band(slope) & valid
    d1, lo1, hi1 = shortest_leg(safe, band, wp.s, wp.w1)
    d2, lo2, hi2 = shortest_leg(safe, band, wp.w1, wp.w2)
    return LoopResult(distance_m=2.0 * (d1 + d2), exposure_max_m=hi1 + hi2, exposure_min_m=lo1 + lo2)


def start_component_band_edge_m(slope: FloatArray, valid: BoolArray, wp: Waypoints) -> float:
    """Length (m) of 4-neighbour interfaces between band cells and other safe cells inside the start component."""
    band = in_band(slope) & valid
    comp = wp.component
    total = 0
    for dr, dc in ((0, 1), (1, 0)):
        a = band[: band.shape[0] - dr, : band.shape[1] - dc]
        b = band[dr:, dc:]
        ca = comp[: band.shape[0] - dr, : band.shape[1] - dc]
        cb = comp[dr:, dc:]
        total += int(np.count_nonzero(ca & cb & (a ^ b)))
    return total * CELL_M


def exposure_route_exists(slope: FloatArray, valid: BoolArray, wp: Waypoints, max_distance_m: float = 8000.0) -> bool:
    """A closed route from S that traverses >= 100 m of band (two band-band edges) within ``max_distance_m``."""
    safe = safe_mask(slope, valid)
    band = in_band(slope) & valid
    reachable = wp.component & band
    if not reachable.any():
        return False
    rows, cols = np.nonzero(reachable)
    best = math.inf
    # nearest band cell by Dijkstra distance, then require 3 collinear-adjacent band cells (>= 2 edges = 120 m)
    h, w = safe.shape
    dist = np.full((h, w), np.inf)
    dist[wp.s] = 0.0
    heap: list[tuple[float, int, int]] = [(0.0, wp.s[0], wp.s[1])]
    while heap:
        dcur, r, c = heapq.heappop(heap)
        if dcur > dist[r, c]:
            continue
        for dr, dc, length in _MOVES:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and safe[nr, nc] and dcur + length * CELL_M < dist[nr, nc]:
                dist[nr, nc] = dcur + length * CELL_M
                heapq.heappush(heap, (dist[nr, nc], nr, nc))
    for r, c in zip(rows.tolist(), cols.tolist(), strict=True):
        chain = any(
            0 <= r + 2 * dr < h and 0 <= c + 2 * dc < w and band[r + dr, c + dc] and band[r + 2 * dr, c + 2 * dc]
            for dr, dc, _ in _MOVES
        )
        if chain:
            best = min(best, dist[r, c])
    return math.isfinite(best) and 2.0 * (best + 2 * CELL_M * SQRT2) <= max_distance_m


def ramp_interior(slope: FloatArray, valid: BoolArray, target_deg: float = 15.0, tol_deg: float = 0.5) -> BoolArray:
    with np.errstate(invalid="ignore"):
        return np.asarray(valid & (np.abs(slope - target_deg) <= tol_deg), dtype=bool)


@dataclass
class WindowReport:
    window_id: str
    metrics: WindowMetrics
    violations: list[str] = field(default_factory=list)
    details: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.violations


def _expect(report: WindowReport, cond: bool, text: str) -> None:
    if not cond:
        report.violations.append(text)


def check_window(
    grid: GridAnalysis, window_id: str, ramp_target_deg: float = 15.0, moat_min_cells: int = 4
) -> WindowReport:
    """Verify every architecture 40 section 4 property of one window."""
    m = window_metrics(grid, window_id)
    rep = WindowReport(window_id, m)
    sl = window_slices(window_id)
    slope, valid = grid.slope[sl], grid.valid[sl]
    safe = safe_mask(slope, valid)
    ready = m.valid_fraction >= 0.80
    rep.details.update(f_band=m.f_band, valid_fraction=m.valid_fraction, max_slope=m.max_slope_deg)

    if window_id == "grid-r0c0":
        _expect(rep, 0.07 <= m.f_band <= 0.15, f"f_band {m.f_band:.4f} outside [0.07,0.15]")
        _expect(rep, ready, f"valid fraction {m.valid_fraction:.3f} < 0.80")
        _expect(rep, m.max_slope_deg <= CAP_DEG, "a cell exceeds 18 deg")
        interior = ramp_interior(slope, valid, ramp_target_deg)
        comp = largest_component(interior)
        rr, cc = np.nonzero(comp)
        extent = max(int(rr.max() - rr.min()), int(cc.max() - cc.min())) + 1 if rr.size else 0
        inscribed = 2.0 * float(ndimage.distance_transform_edt(np.pad(comp, 1)).max()) if rr.size else 0.0
        rep.details.update(ramp_extent_cells=extent, ramp_inscribed_diameter=inscribed)
        _expect(rep, extent >= 40, f"ramp extent {extent} < 40 cells")
        _expect(rep, inscribed >= 8.0, f"ramp inscribed diameter {inscribed:.1f} < 8 cells")
        near = ndimage.binary_dilation(in_band(slope) & valid, structure=np.ones((3, 3), dtype=bool), iterations=2)
        elsewhere = valid & ~near
        worst = float(np.nanmax(np.where(elsewhere, slope, 0.0)))
        rep.details["max_slope_away_from_ramp"] = worst
        _expect(rep, worst <= 6.0, f"slope {worst:.2f} > 6 away from the ramp")
        _check_route_properties(rep, slope, valid, expect_exposure_shortfall=True)
    elif window_id in ("grid-r0c1", "grid-r2c2"):
        lo, hi = (0.25, 0.60) if window_id == "grid-r0c1" else (0.06, 0.10)
        _expect(rep, lo <= m.f_band <= hi, f"f_band {m.f_band:.4f} outside [{lo},{hi}]")
        _expect(rep, ready, f"valid fraction {m.valid_fraction:.3f} < 0.80")
        _check_island(rep, grid, window_id, slope, valid, safe, moat_min_cells)
    elif window_id == "grid-r0c2":
        _expect(rep, m.f_band == 0.0, f"f_band {m.f_band} != 0")
        _expect(rep, m.max_slope_deg <= 3.0, f"max slope {m.max_slope_deg:.2f} > 3")
    elif window_id == "grid-r1c0":
        _expect(rep, 0.02 <= m.f_band <= 0.04, f"f_band {m.f_band:.4f} outside [0.02,0.04]")
    elif window_id == "grid-r2c0":
        _expect(rep, 0.01 <= m.f_band <= 0.03, f"f_band {m.f_band:.4f} outside [0.01,0.03]")
    elif window_id == "grid-r2c1":
        _expect(rep, 0.0 < m.f_band <= 0.01, f"f_band {m.f_band:.4f} outside (0,0.01]")
    elif window_id == "grid-r1c1":
        _expect(rep, m.water_fraction >= 0.98, f"water fraction {m.water_fraction:.4f} < 0.98")
    elif window_id == "grid-r1c2":
        nodata_share = float(grid.nodata[sl].mean())
        rep.details["nodata_fraction"] = nodata_share
        _expect(rep, 0.50 <= m.valid_fraction <= 0.60, f"valid fraction {m.valid_fraction:.3f} outside [0.50,0.60]")
        _expect(rep, nodata_share > 0.30, "nodata band is not wide")
    else:
        raise ValueError(window_id)
    if window_id in ("grid-r0c0", "grid-r0c1", "grid-r0c2", "grid-r1c0", "grid-r2c0", "grid-r2c1", "grid-r2c2"):
        _expect(rep, m.valid_fraction >= 0.80, f"valid fraction {m.valid_fraction:.3f} < 0.80")
    return rep


def _check_route_properties(
    rep: WindowReport, slope: FloatArray, valid: BoolArray, *, expect_exposure_shortfall: bool
) -> None:
    wp = auto_waypoints(slope, valid)
    loop = waypoint_return_loop(slope, valid, wp)
    edge_m = start_component_band_edge_m(slope, valid, wp)
    rep.details.update(loop_exposure_max_m=loop.exposure_max_m, loop_distance_m=loop.distance_m, band_edge_m=edge_m)
    band = in_band(slope) & valid
    _expect(rep, not band[wp.w1] and not band[wp.w2], "W1/W2 must be non-band cells")
    if expect_exposure_shortfall:
        _expect(rep, loop.exposure_max_m < 100.0, f"min-distance loop earns {loop.exposure_max_m:.0f} m >= 100 m")
        _expect(rep, edge_m >= 400.0, f"start component band-edge length {edge_m:.0f} m < 400 m")
        _expect(rep, exposure_route_exists(slope, valid, wp), "no closed >=100 m exposure route within 8000 m")
    else:
        rep.details["exposure_route_exists"] = float(exposure_route_exists(slope, valid, wp))


def _check_island(
    rep: WindowReport,
    grid: GridAnalysis,
    window_id: str,
    slope: FloatArray,
    valid: BoolArray,
    safe: BoolArray,
    moat_min_cells: int,
) -> None:
    """The band lies on an island fully enclosed by water; waypoints stay on the mainland."""
    sl = window_slices(window_id)
    band = in_band(slope) & valid
    wp = auto_waypoints(slope, valid)
    comp = wp.component
    rep.details["start_component_band_cells"] = float((comp & band).sum())
    _expect(rep, not (comp & band).any(), "start-reachable component contains band cells")
    _expect(rep, not band[wp.s], "start cell is in the band")
    usable = ~grid.water[sl] & ~grid.nodata[sl]
    _expect(rep, not grid.nodata[sl].any(), "nodata inside an island window")
    labels, _ = components8(usable)
    main_label = labels[wp.s]
    island_cells = usable & (labels != main_label)
    _expect(rep, bool((island_cells & band).any()), "the band is not on a separate island")
    _expect(rep, int(comp.sum()) > int((safe & ~comp).sum()), "mainland not larger than the island")
    if island_cells.any():
        dist = ndimage.distance_transform_edt(labels != main_label)
        moat = float(dist[island_cells].min()) - 1.0  # water cells between mainland and island land
        rep.details["moat_cells_measured"] = moat
        _expect(rep, moat >= moat_min_cells, f"moat {moat:.1f} cells < {moat_min_cells}")
    loop = waypoint_return_loop(slope, valid, wp)
    rep.details["loop_exposure_max_m"] = loop.exposure_max_m
    _expect(rep, loop.exposure_max_m < 100.0, "waypoint loop earns exposure on an unreachable island")


def check_all_windows(grid: GridAnalysis) -> dict[str, WindowReport]:
    ids = [f"grid-r{r}c{c}" for r in range(3) for c in range(3)]
    return {w: check_window(grid, w) for w in ids}


def screening_deficit(f_band: float, required: float = 0.05) -> float:
    return max(0.0, required - f_band)


# ----------------------------------------------------------------------------------------------- target rasters
def slope_deg_array(elev: FloatArray, cell_m: float) -> tuple[FloatArray, BoolArray]:
    usable = np.isfinite(elev)
    return plane_fit_slope(np.where(usable, elev, 0.0), usable, cell_m)


def nearest_class_fractions(slope: FloatArray, valid: BoolArray, design: tuple[float, ...]) -> list[float]:
    """Area fractions of valid cells assigned to the nearest design slope (cell area is uniform)."""
    s = slope[valid]
    idx = np.argmin(np.abs(s[:, None] - np.asarray(design)[None, :]), axis=1)
    return [float(np.count_nonzero(idx == i)) / s.size for i in range(len(design))]


def read_band(path: Path) -> tuple[NDArray[np.generic], rasterio.Affine, str, float | None]:
    with rasterio.open(path) as src:
        return src.read(1), src.transform, src.crs.to_wkt(), src.nodata


def mars_target_fractions(directory: Path, design: tuple[float, ...] = (3.0, 7.0, 14.0, 22.0)) -> list[float]:
    """Area fractions of valid cells nearest to each design slope, from the Mars GeoTIFF alone."""
    raw, tf, _, nodata = read_band(directory / "practice-mars-target-v1" / "practice-mars-target-v1.tif")
    elev = raw.astype(np.float64)
    elev[raw == nodata] = np.nan
    slope, valid = slope_deg_array(elev, abs(tf.a))
    return nearest_class_fractions(slope, valid, design)


def moon_wedge_fractions(
    directory: Path, design: tuple[float, ...] = (2.0, 6.0, 13.0, 20.0)
) -> tuple[list[float], int]:
    """Fractions over the AOI wedge lon [-10,10], lat [-89.5,-87.5] (scale 0.5, offset 1737400, radius applied once)."""
    from pyproj import CRS, Transformer

    raw, tf, wkt, _ = read_band(directory / "practice-moon-target-v1" / "practice-moon-target-v1.tif")
    radius = raw.astype(np.float64) * 0.5 + 1737400.0
    height = radius - 1737400.0
    slope, valid = slope_deg_array(height, abs(tf.a))
    rows, cols = np.mgrid[0 : raw.shape[0], 0 : raw.shape[1]]
    x = tf.c + (cols + 0.5) * tf.a
    y = tf.f + (rows + 0.5) * tf.e
    crs = CRS.from_wkt(wkt)
    lon, lat = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True).transform(x, y)
    inside = valid & (lon >= -10.0) & (lon <= 10.0) & (lat >= -89.5) & (lat <= -87.5)
    return nearest_class_fractions(slope, inside, design), int(inside.sum())
