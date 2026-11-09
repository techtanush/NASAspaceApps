"""Amanatides-Woo DDA grid traversal ("supercover") used by the SOLVER's graph builder.

The independent verifier deliberately uses a different algorithm (slab clipping per candidate cell), so a defect
in one is caught by the other.  Both must report the same touched cells and the same intersection lengths; the
test-suite checks this on thousands of random segments.

Geometry: ``origin_x_m`` is the west edge of column 0, ``origin_y_m`` the north edge of row 0; rows grow
southwards.  Work is done in grid-index space (cell size 1) and lengths are scaled back to metres.

*Supercover*: when the segment passes exactly through a cell corner, the two cells that only touch the segment at
that corner are reported too, with ``length_m == 0``.  A diagonal step therefore "touches" four cells, so a
one-pixel nodata channel can never become a diagonal bridge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_TIE_EPS = 1e-12


@dataclass(frozen=True)
class CellHit:
    row: int
    col: int
    length_m: float


def supercover(
    x0_m: float,
    y0_m: float,
    x1_m: float,
    y1_m: float,
    *,
    cell_size_m: float,
    origin_x_m: float,
    origin_y_m: float,
) -> list[CellHit]:
    """Cells touched by the segment, in traversal order, with intersection lengths in metres."""
    u0 = (x0_m - origin_x_m) / cell_size_m
    v0 = (origin_y_m - y0_m) / cell_size_m
    u1 = (x1_m - origin_x_m) / cell_size_m
    v1 = (origin_y_m - y1_m) / cell_size_m
    du = u1 - u0
    dv = v1 - v0
    length_cells = math.hypot(du, dv)
    col = math.floor(u0)
    row = math.floor(v0)
    end_col = math.floor(u1)
    end_row = math.floor(v1)
    if length_cells == 0.0:
        return [CellHit(row, col, 0.0)]
    length_m = length_cells * cell_size_m

    step_col = 1 if du > 0 else (-1 if du < 0 else 0)
    step_row = 1 if dv > 0 else (-1 if dv < 0 else 0)
    t_delta_u = 1.0 / abs(du) if du != 0.0 else math.inf
    t_delta_v = 1.0 / abs(dv) if dv != 0.0 else math.inf
    if du > 0:
        t_max_u = (col + 1 - u0) / du
    elif du < 0:
        t_max_u = (u0 - col) / -du
    else:
        t_max_u = math.inf
    if dv > 0:
        t_max_v = (row + 1 - v0) / dv
    elif dv < 0:
        t_max_v = (v0 - row) / -dv
    else:
        t_max_v = math.inf

    hits: list[CellHit] = []
    t_prev = 0.0
    guard = abs(end_col - col) + abs(end_row - row) + 4
    while guard > 0:
        guard -= 1
        t_next = min(t_max_u, t_max_v)
        if t_next >= 1.0 - _TIE_EPS:
            hits.append(CellHit(row, col, max(0.0, 1.0 - t_prev) * length_m))
            break
        hits.append(CellHit(row, col, max(0.0, t_next - t_prev) * length_m))
        t_prev = t_next
        if abs(t_max_u - t_max_v) <= _TIE_EPS:
            # exact corner crossing: also report the two cells that only touch the segment at the corner
            hits.append(CellHit(row, col + step_col, 0.0))
            hits.append(CellHit(row + step_row, col, 0.0))
            col += step_col
            row += step_row
            t_max_u += t_delta_u
            t_max_v += t_delta_v
        elif t_max_u < t_max_v:
            col += step_col
            t_max_u += t_delta_u
        else:
            row += step_row
            t_max_v += t_delta_v
    if (row, col) != (end_row, end_col):
        hits.append(CellHit(end_row, end_col, 0.0))
    return hits
