"""Route engine: constraints design, graph, bounded search with certificates, independent verifier, diagnosis.

This package root holds the *neutral* vocabulary shared by the solver side and the verifier side: error type,
node/edge identifier conventions, numeric tolerances and the raster-array container.  It deliberately imports no
solver module, so the verifier can use it without depending on the search or graph builders.

Identifier conventions (normative for solver and verifier):

* raster node id        ``r{row}c{col}`` (row 0 is the NORTH row of the analysis grid)
* undirected edge id    ``{lo}--{hi}`` where ``lo <= hi`` in plain string order of the two node ids
* abstract graph nodes  the ``GraphSpec.nodes`` strings
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from analogforge.ports.hashing import bytes_sha256
from analogforge.science.errors import ScienceError
from analogforge.science.raster.store import AnalysisGrid, decode_analysis_grid

EPS_LEN_M: Final = 1e-9  # intersection lengths at or below this count as a corner/point touch
EPS_VALUE: Final = 1e-9  # comparison slack for thresholds that are exact by construction
CONSTRAINT_TERRAIN_MASK: Final = "C-TERRAIN-MASK"
CONSTRAINT_INPUT_HASH: Final = "C-INPUT-HASH"
METRIC_SURFACE_SLOPE: Final = "surface_slope_deg"

_NODE_RE: Final = re.compile(r"^r(\d+)c(\d+)$")


class RouteInputError(ScienceError):
    """A route-engine precondition failed (stale hash, missing grid, mock provider in live mode, ...).

    The facade translates this into a ``BLOCKED`` result carrying the canonical ``code``/``detail_code``.
    """

    code = "INPUT_INVALID"


def raster_node_id(row: int, col: int) -> str:
    return f"r{row}c{col}"


def parse_raster_node_id(node_id: str) -> tuple[int, int] | None:
    match = _NODE_RE.match(node_id)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def undirected_edge_id(node_a: str, node_b: str) -> str:
    low, high = sorted((node_a, node_b))
    return f"{low}--{high}"


@dataclass(frozen=True, eq=False)
class GridArrays:
    """Analysis-grid arrays the route engine needs.

    ``origin_x_m`` is the x of the WEST edge of column 0 and ``origin_y_m`` the y of the NORTH edge of row 0, in the
    grid's projected CRS (metres).  Row index grows southwards; column index grows eastwards.  ``slope_deg`` is only
    meaningful where ``valid``.  ``elevation_m`` is the cell-centre elevation (no interpolation).
    """

    elevation_m: NDArray[np.float64]
    valid: NDArray[np.bool_]
    land: NDArray[np.bool_]
    slope_deg: NDArray[np.float64]
    cell_size_m: float
    origin_x_m: float
    origin_y_m: float

    def __post_init__(self) -> None:
        shape = self.elevation_m.shape
        if len(shape) != 2:
            raise RouteInputError("analysis grid arrays must be 2-D", detail_code="GRID_SHAPE")
        for name, arr in (("valid", self.valid), ("land", self.land), ("slope_deg", self.slope_deg)):
            if arr.shape != shape:
                raise RouteInputError(
                    f"analysis grid array {name} has shape {arr.shape} != {shape}", detail_code="GRID_SHAPE"
                )
        if not self.cell_size_m > 0.0:
            raise RouteInputError("cell_size_m must be positive", detail_code="GRID_SHAPE")

    @property
    def height(self) -> int:
        return int(self.elevation_m.shape[0])

    @property
    def width(self) -> int:
        return int(self.elevation_m.shape[1])

    def center_xy(self, row: int, col: int) -> tuple[float, float]:
        return (
            self.origin_x_m + (col + 0.5) * self.cell_size_m,
            self.origin_y_m - (row + 0.5) * self.cell_size_m,
        )

    def cell_of(self, x_m: float, y_m: float) -> tuple[int, int]:
        col = int(np.floor((x_m - self.origin_x_m) / self.cell_size_m))
        row = int(np.floor((self.origin_y_m - y_m) / self.cell_size_m))
        return row, col

    def contains(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width


def grid_arrays_from_analysis(grid: AnalysisGrid) -> GridArrays:
    """Route-engine view of a decoded ANALYSIS_GRID (``raster.store`` is the only container parser)."""
    return GridArrays(
        elevation_m=grid.elevation_m,
        valid=grid.valid,
        land=grid.land,
        slope_deg=grid.slope_deg,
        cell_size_m=grid.meta.cell_size_m,
        origin_x_m=grid.meta.origin_x_m,
        origin_y_m=grid.meta.origin_y_m,
    )


def load_grid_arrays(path: Path, expected_sha256: str | None = None) -> GridArrays:
    """Read an ANALYSIS_GRID blob; when ``expected_sha256`` (``GridSpec.analysis_grid_sha256``) is given the bytes must
    hash to it, otherwise the grid is stale (``STALE_INPUT_HASH``)."""
    data = path.read_bytes()
    if expected_sha256 is not None and bytes_sha256(data) != expected_sha256:
        raise RouteInputError(
            "analysis grid bytes do not match GridSpec.analysis_grid_sha256",
            code="STALE_INPUT_HASH",
            detail_code="GRID_HASH_MISMATCH",
        )
    return grid_arrays_from_analysis(decode_analysis_grid(data))
