"""Synthetic practice Earth grid (architecture 40 section 4) and the practice mineral raster.

SYNTHETIC PRACTICE DATA - not terrain of any real location.  The 192x192 grid at 60 m holds nine 64x64-cell windows
(``grid-r<R>c<C>``, row 0 north).  Every outcome of the practice stories must *emerge* from slope computation on
these rasters; the generator only places geometric features:

* ``grid-r0c0`` (B): a gently roofed plateau whose east face is a connected 15 degree ramp (a straight part plus a
  wedge that narrows where the roof descends at 5.5 degrees); lowland east of the ramp.  The plateau/roof lies on the
  side of the window centre, so the waypoint rule puts ``W1``/``W2`` on the plateau side of the ramp.
* ``grid-r0c1`` (A): a large 15 degree conical island (cut by the grid's north edge) enclosed by a water moat.
* ``grid-r2c2`` (KNOWN): a small 15 degree conical island enclosed by a water moat.
* fillers: small isolated 15 degree cones; ``grid-r0c2`` flat; ``grid-r1c1`` water; ``grid-r1c2`` nodata stripe.

All feature functions are compactly supported and return to the common base level, so the whole grid is continuous.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
UInt8Array = NDArray[np.uint8]

SEED_DEFAULT = 20261105
GRID_CELLS = 192
WINDOW_CELLS = 64
CELL_SIZE_M = 60.0
SW_EASTING_M = 494240.0
NORTH_NORTHING_M = 3900000.0
EPSG = 32612
NODATA_VALUE = -32768.0
BASE_ELEVATION_M = 1200.0  # relative to SYNTHETIC_REFERENCE_ONLY
WATER_DEPTH_M = 6.0
WINDOW_IDS = tuple(f"grid-r{r}c{c}" for r in range(3) for c in range(3))


def dataset_rng(seed: int, dataset_id: str) -> np.random.Generator:
    """Deterministic generator from ``seed`` plus the dataset id (architecture 40 section 2)."""
    digest = hashlib.sha256(f"{seed}:{dataset_id}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


@dataclass(frozen=True)
class EarthGridParams:
    """Generator parameters (defaults reproduce architecture 40 exactly; perturbation tests change them)."""

    seed: int = SEED_DEFAULT
    noise_m: float = 0.02
    # window B (grid-r0c0)
    ramp_slope_deg: float = 15.0
    ramp_width_cells: float = 10.0
    ramp_foot_col: float = 56.0
    roof_slope_deg: float = 5.5
    roof_start_row: float = 64.0
    # window A (grid-r0c1)
    moat_cells: int = 4
    mesa_slope_deg: float = 15.0
    mesa_rows: int = 24  # slab rows 0..mesa_rows-1 (rising towards the north grid edge)
    mesa_first_col: int = 10
    mesa_last_col: int = 54
    # window KNOWN (grid-r2c2)
    known_moat_cells: int = 4
    known_slope_deg: float = 15.0
    known_radius_cells: float = 11.0
    known_centre_row: float = 31.0
    known_centre_col: float = 31.0
    # fillers: cone radii (cells) for grid-r1c0, grid-r2c0, grid-r2c1
    rolling_1_radius_cells: float = 0.0
    rolling_2_radius_cells: float = 6.6
    gentle_radius_cells: float = 4.1
    filler_slope_deg: float = 15.0
    # grid-r1c1 land patch (cells) in the middle of the water window
    water_land_patch: tuple[int, int] = (4, 5)
    # grid-r1c2 nodata stripe (first local column, width)
    stripe_first_col: int = 20
    stripe_width: int = 25
    # minerals
    mineral_valid_fractions: tuple[float, float] = (0.60, 0.85)


@dataclass(frozen=True)
class EarthGridArrays:
    elevation_m: FloatArray  # nodata cells hold NaN
    nodata: BoolArray
    water: BoolArray
    window_origins: dict[str, tuple[int, int]] = field(default_factory=dict)


def window_origin(window_id: str) -> tuple[int, int]:
    """(row0, col0) cell origin of ``grid-r<R>c<C>``."""
    r, c = int(window_id[6]), int(window_id[8])
    return r * WINDOW_CELLS, c * WINDOW_CELLS


def _tan(deg: float) -> float:
    return math.tan(math.radians(deg))


def _radial(rows: FloatArray, cols: FloatArray, centre_row: float, centre_col: float) -> FloatArray:
    return np.asarray(np.hypot(rows - centre_row, cols - centre_col), dtype=np.float64)


def _cone(radius: FloatArray, cone_radius: float, slope_deg: float, plateau_radius: float) -> FloatArray:
    """Heights of a truncated cone with flank slope ``slope_deg`` (0 outside ``cone_radius``)."""
    k = _tan(slope_deg) * CELL_SIZE_M
    cap = k * max(cone_radius - plateau_radius, 0.0)
    return np.asarray(
        np.where(radius < cone_radius, np.minimum(cap, k * (cone_radius - radius)), 0.0), dtype=np.float64
    )


def _local_grids(shape: int = WINDOW_CELLS) -> tuple[FloatArray, FloatArray]:
    r, c = np.meshgrid(np.arange(shape, dtype=np.float64), np.arange(shape, dtype=np.float64), indexing="ij")
    return r, c


def _ramp_field(p: EarthGridParams, n_rows: int) -> FloatArray:
    """The B plateau/ramp/roof over the first ``n_rows`` grid rows and columns 0-63 (global row coordinates).

    The roof starts to descend at ``roof_start_row`` (default: the south edge of B), so the straight 15 degree ramp
    spans the whole window and the narrowing wedge where the roof meets the ramp lies in ``grid-r1c0`` (whose band
    content it provides).
    """
    rows, cols = np.meshgrid(
        np.arange(n_rows, dtype=np.float64), np.arange(WINDOW_CELLS, dtype=np.float64), indexing="ij"
    )
    k = _tan(p.ramp_slope_deg) * CELL_SIZE_M
    g = _tan(p.roof_slope_deg) * CELL_SIZE_M
    height = k * p.ramp_width_cells
    roof = height - g * np.maximum(0.0, rows - p.roof_start_row)
    ramp = k * (p.ramp_foot_col - cols)
    return np.asarray(np.maximum(0.0, np.minimum(ramp, roof)), dtype=np.float64)


def _window_cone_with_moat(
    p_slope: float,
    radius: float,
    plateau: float,
    moat: int,
    centre_row: float,
    centre_col: float,
) -> tuple[FloatArray, BoolArray]:
    rows, cols = _local_grids()
    dist = _radial(rows, cols, centre_row, centre_col)
    z = _cone(dist, radius, p_slope, plateau)
    water = (dist >= radius - 0.5) & (dist < radius + moat + 0.5) if moat > 0 else np.zeros(dist.shape, dtype=bool)
    return z, np.asarray(water, dtype=bool)


def _window_slab_with_moat(p: EarthGridParams) -> tuple[FloatArray, BoolArray]:
    """Window A: a tilted 15 degree slab (plane rising north) with a straight foot on its south side.

    The slab's south edge has height 0 like the mainland, so without a moat it joins the mainland smoothly (the
    perturbation ``moat_cells=0``) while its west/east sides become cliffs; with a moat it is an island.
    """
    rows, cols = _local_grids()
    k = _tan(p.mesa_slope_deg) * CELL_SIZE_M
    on_slab = (rows < p.mesa_rows) & (cols >= p.mesa_first_col) & (cols <= p.mesa_last_col)
    z = np.where(on_slab, k * (p.mesa_rows - rows), 0.0)
    water = np.zeros(z.shape, dtype=bool)
    if p.moat_cells > 0:
        m = p.moat_cells
        box = (rows < p.mesa_rows + m) & (cols >= p.mesa_first_col - m) & (cols <= p.mesa_last_col + m)
        water = box & ~on_slab
    return np.asarray(z, dtype=np.float64), water


def build_earth_grid(params: EarthGridParams | None = None) -> EarthGridArrays:
    """Elevation (m, NaN at nodata), nodata mask and water mask of the whole 192x192 practice grid."""
    p = params or EarthGridParams()
    z = np.zeros((GRID_CELLS, GRID_CELLS), dtype=np.float64)
    water = np.zeros((GRID_CELLS, GRID_CELLS), dtype=bool)
    nodata = np.zeros((GRID_CELLS, GRID_CELLS), dtype=bool)

    def put(window_id: str, zl: FloatArray, wl: BoolArray | None = None) -> None:
        r0, c0 = window_origin(window_id)
        z[r0 : r0 + WINDOW_CELLS, c0 : c0 + WINDOW_CELLS] += zl
        if wl is not None:
            water[r0 : r0 + WINDOW_CELLS, c0 : c0 + WINDOW_CELLS] = wl

    z[0:128, 0:WINDOW_CELLS] += _ramp_field(p, 128)
    za, wa = _window_slab_with_moat(p)
    put("grid-r0c1", za, wa)
    # grid-r0c2: flat negative control (base level only)
    zk, wk = _window_cone_with_moat(
        p.known_slope_deg, p.known_radius_cells, 2.0, p.known_moat_cells, p.known_centre_row, p.known_centre_col
    )
    put("grid-r2c2", zk, wk)
    rows, cols = _local_grids()
    for window_id, radius in (
        ("grid-r1c0", p.rolling_1_radius_cells),
        ("grid-r2c0", p.rolling_2_radius_cells),
        ("grid-r2c1", p.gentle_radius_cells),
    ):
        if radius > 0:
            put(window_id, _cone(_radial(rows, cols, 32.0, 32.0), radius, p.filler_slope_deg, 1.0))
    # grid-r1c1: water window with a small land patch
    wl = np.ones((WINDOW_CELLS, WINDOW_CELLS), dtype=bool)
    ph, pw = p.water_land_patch
    r_start, c_start = (WINDOW_CELLS - ph) // 2, (WINDOW_CELLS - pw) // 2
    wl[r_start : r_start + ph, c_start : c_start + pw] = False
    put("grid-r1c1", np.zeros((WINDOW_CELLS, WINDOW_CELLS)), wl)

    z += BASE_ELEVATION_M
    rng = dataset_rng(p.seed, "practice-earth-grid-v1")
    z += rng.normal(0.0, p.noise_m, size=z.shape) if p.noise_m > 0 else 0.0
    z[water] = BASE_ELEVATION_M - WATER_DEPTH_M
    r0, c0 = window_origin("grid-r1c2")
    nodata[r0 : r0 + WINDOW_CELLS, c0 + p.stripe_first_col : c0 + p.stripe_first_col + p.stripe_width] = True
    z[nodata] = np.nan
    origins = {w: window_origin(w) for w in WINDOW_IDS}
    return EarthGridArrays(elevation_m=z, nodata=nodata, water=water, window_origins=origins)


def elevation_file_array(arrays: EarthGridArrays) -> NDArray[np.float32]:
    """The float32 raster stored in the GeoTIFF (nodata = -32768); loaders must go through this quantisation."""
    out = np.where(arrays.nodata, NODATA_VALUE, arrays.elevation_m)
    return np.asarray(out, dtype=np.float32)


def water_file_array(arrays: EarthGridArrays) -> UInt8Array:
    return np.asarray(arrays.water, dtype=np.uint8)


MINERAL_CLASS_NAMES = {
    1: "SYNTHETIC_CLASS_1",
    2: "SYNTHETIC_CLASS_2",
    3: "SYNTHETIC_CLASS_3",
    4: "SYNTHETIC_CLASS_4",
}


def build_minerals(params: EarthGridParams | None = None) -> UInt8Array:
    """Categorical ids 1-4 valid only over grid-r0c0 (fraction 0.60) and grid-r2c2 (0.85); 0 is nodata."""
    p = params or EarthGridParams()
    out = np.zeros((GRID_CELLS, GRID_CELLS), dtype=np.uint8)
    rng = dataset_rng(p.seed, "practice-earth-minerals-v1")
    for window_id, fraction in zip(("grid-r0c0", "grid-r2c2"), p.mineral_valid_fractions, strict=True):
        r0, c0 = window_origin(window_id)
        n_valid = round(fraction * WINDOW_CELLS * WINDOW_CELLS)
        flat = np.zeros(WINDOW_CELLS * WINDOW_CELLS, dtype=bool)
        # fill column-major so the valid region is a clean block of columns (partial last column)
        order = np.arange(WINDOW_CELLS * WINDOW_CELLS).reshape(WINDOW_CELLS, WINDOW_CELLS).T.reshape(-1)
        flat[order[:n_valid]] = True
        valid = flat.reshape(WINDOW_CELLS, WINDOW_CELLS)
        block = 16
        shift = int(rng.integers(0, 4))
        rr, cc = np.meshgrid(np.arange(WINDOW_CELLS), np.arange(WINDOW_CELLS), indexing="ij")
        ids = 1 + ((rr // block + cc // block + shift) % 4)
        out[r0 : r0 + WINDOW_CELLS, c0 : c0 + WINDOW_CELLS] = np.where(valid, ids, 0).astype(np.uint8)
    return out
