"""Search graphs: the shared ``RouteGraph`` structure and the raster 8-neighbour builder.

The raster builder follows architecture 12 section 2:

* nodes are cell centres that are valid, land, not within ``footprint_dilation_m`` of an invalid/water cell and with
  surface slope <= the effective cap;
* an edge between 8-neighbours exists only if the SUPERCOVER of its segment (DDA, corner touches included) contains
  only valid, land, un-dilated, un-blocked cells, and every cell with a positive intersection length has slope <= cap;
* the edge hazard slope is the maximum cell slope over cells with intersection length > 1e-9 m;
* exposure is accumulated per edge from the intersection lengths of cells whose slope lies in the band.

The abstract graph builder lives in ``fixture_graph``; both produce a ``RouteGraph``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import ExposureSpec
from analogforge.science.routing import (
    EPS_LEN_M,
    GridArrays,
    RouteInputError,
    parse_raster_node_id,
    raster_node_id,
    undirected_edge_id,
)
from analogforge.science.routing.exposure import slope_in_band
from analogforge.science.routing.supercover import supercover

Arc = tuple[int, int, int]  # (neighbour node index, edge index, sign: +1 when travelling u->v, -1 for v->u)

_FORWARD_DIRS: tuple[tuple[int, int], ...] = ((0, 1), (1, -1), (1, 0), (1, 1))
_SLOPE_TOL = 1e-9


@dataclass(frozen=True)
class EdgeRec:
    """An undirected edge; ``dz_m`` is ``z[v] - z[u]`` (travelling v->u has the opposite sign)."""

    edge_id: str
    u: int
    v: int
    d_xy_m: float
    dz_m: float
    hazard_slope_deg: float
    band_len_m: tuple[float, ...]  # horizontal metres in band, aligned with the exposure specs used to build
    mock_energy_wh: float | None = None


@dataclass(frozen=True, eq=False)
class RouteGraph:
    node_ids: tuple[str, ...]
    node_xy: tuple[tuple[float, float], ...] | None
    node_z: tuple[float, ...]
    edges: tuple[EdgeRec, ...]
    adj: tuple[tuple[Arc, ...], ...]
    index_of: dict[str, int]
    revision: str
    kind: str  # "RASTER" | "ABSTRACT"

    def xy(self, node: int) -> tuple[float, float]:
        """Projected centre of a raster node (abstract graphs have no geometry)."""
        if self.node_xy is None:
            raise RouteInputError("abstract graph nodes have no projected coordinates", detail_code="GRAPH_KIND")
        return self.node_xy[node]

    def cell(self, node: int) -> tuple[int, int]:
        """``(row, col)`` of a raster node."""
        parsed = parse_raster_node_id(self.node_ids[node])
        if parsed is None:
            raise RouteInputError(f"{self.node_ids[node]} is not a raster node id", detail_code="GRAPH_KIND")
        return parsed

    def edge_index(self, edge_id: str) -> int | None:
        return self._edge_lookup().get(edge_id)

    def _edge_lookup(self) -> dict[str, int]:
        cached: dict[str, int] | None = self.__dict__.get("_lookup")
        if cached is None:
            cached = {rec.edge_id: i for i, rec in enumerate(self.edges)}
            object.__setattr__(self, "_lookup", cached)
        return cached

    def directed_dz(self, edge_index: int, sign: int) -> float:
        return self.edges[edge_index].dz_m * sign


def finalize_graph(
    node_ids: Sequence[str],
    node_xy: Sequence[tuple[float, float]] | None,
    node_z: Sequence[float],
    edges: Sequence[EdgeRec],
    *,
    revision: str,
    kind: str,
) -> RouteGraph:
    """Attach deterministic adjacency (neighbours ordered by node-id string)."""
    ids = tuple(node_ids)
    adjacency: list[list[Arc]] = [[] for _ in ids]
    for ei, rec in enumerate(edges):
        adjacency[rec.u].append((rec.v, ei, 1))
        adjacency[rec.v].append((rec.u, ei, -1))
    for arcs in adjacency:
        arcs.sort(key=lambda arc: ids[arc[0]])
    return RouteGraph(
        node_ids=ids,
        node_xy=None if node_xy is None else tuple(node_xy),
        node_z=tuple(node_z),
        edges=tuple(edges),
        adj=tuple(tuple(a) for a in adjacency),
        index_of={nid: i for i, nid in enumerate(ids)},
        revision=revision,
        kind=kind,
    )


def grid_digest(grid: GridArrays) -> str:
    """SHA-256 over the arrays/metadata the route engine consumes (graph revision input)."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(grid.elevation_m, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(grid.valid, dtype=np.uint8).tobytes())
    h.update(np.ascontiguousarray(grid.land, dtype=np.uint8).tobytes())
    h.update(np.ascontiguousarray(np.where(grid.valid, grid.slope_deg, 0.0), dtype=np.float64).tobytes())
    h.update(repr((grid.elevation_m.shape, grid.cell_size_m, grid.origin_x_m, grid.origin_y_m)).encode())
    return h.hexdigest()


def passable_mask(grid: GridArrays, dilation_m: float) -> np.ndarray:
    """Cells that may be intersected by a route: valid, land and outside the footprint dilation of bad cells."""
    bad = ~(grid.valid & grid.land)
    passable = ~bad
    if dilation_m > 0.0 and bad.any():
        distance_m = ndimage.distance_transform_edt(passable) * grid.cell_size_m
        passable = passable & (distance_m > dilation_m + _SLOPE_TOL)
    # a VALID cell with a NaN/inf slope or elevation is corrupt data, not terrain: it can neither be a node nor be
    # crossed (never silently treated as flat/safe; the verifier reports routes touching such cells as a DATA problem)
    finite = np.isfinite(grid.slope_deg) & np.isfinite(grid.elevation_m)
    return np.asarray(passable & (finite | ~grid.valid), dtype=np.bool_)


def build_raster_graph(
    grid: GridArrays,
    *,
    slope_cap_deg: float,
    exposures: Sequence[ExposureSpec],
    dilation_m: float = 0.0,
    blocked_edge_ids: Iterable[str] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> RouteGraph:
    blocked = frozenset(blocked_edge_ids)
    passable = passable_mask(grid, dilation_m)
    slope = np.where(grid.valid, grid.slope_deg, np.inf)
    node_ok = passable & (slope <= slope_cap_deg + _SLOPE_TOL)
    cs = grid.cell_size_m

    node_index: dict[tuple[int, int], int] = {}
    node_ids: list[str] = []
    node_xy: list[tuple[float, float]] = []
    node_z: list[float] = []
    for row in range(grid.height):
        for col_idx in np.flatnonzero(node_ok[row]):
            c = int(col_idx)
            node_index[(row, c)] = len(node_ids)
            node_ids.append(raster_node_id(row, c))
            node_xy.append(grid.center_xy(row, c))
            node_z.append(float(grid.elevation_m[row, c]))

    edges: list[EdgeRec] = []
    for (row, col), u in node_index.items():
        if check_cancelled is not None and u % 64 == 0:
            check_cancelled()
        for d_row, d_col in _FORWARD_DIRS:
            v = node_index.get((row + d_row, col + d_col))
            if v is None:
                continue
            eid = undirected_edge_id(node_ids[u], node_ids[v])
            if eid in blocked:
                continue
            x0, y0 = node_xy[u]
            x1, y1 = node_xy[v]
            hits = supercover(x0, y0, x1, y1, cell_size_m=cs, origin_x_m=grid.origin_x_m, origin_y_m=grid.origin_y_m)
            hazard = 0.0
            ok = True
            positive: list[tuple[float, float]] = []
            for hit in hits:
                if not grid.contains(hit.row, hit.col) or not passable[hit.row, hit.col]:
                    ok = False
                    break
                if hit.length_m > EPS_LEN_M:
                    cell_slope = float(slope[hit.row, hit.col])
                    if cell_slope > slope_cap_deg + _SLOPE_TOL:
                        ok = False
                        break
                    hazard = max(hazard, cell_slope)
                    positive.append((cell_slope, hit.length_m))
            if not ok:
                continue
            band_len = tuple(
                sum(length for s, length in positive if slope_in_band(s, spec.band_deg, spec.upper_inclusive))
                for spec in exposures
            )
            edges.append(
                EdgeRec(
                    edge_id=eid,
                    u=u,
                    v=v,
                    d_xy_m=cs * float(np.hypot(d_row, d_col)),
                    dz_m=node_z[v] - node_z[u],
                    hazard_slope_deg=hazard,
                    band_len_m=band_len,
                )
            )
    revision = (
        "graph-"
        + canonical_sha256(
            {
                "kind": "RASTER",
                "grid": grid_digest(grid),
                "cap": slope_cap_deg,
                "dilation_m": dilation_m,
                "blocked": sorted(blocked),
                "bands": [[s.band_deg[0], s.band_deg[1], s.upper_inclusive] for s in exposures],
            }
        )[:16]
    )
    return finalize_graph(node_ids, node_xy, node_z, edges, revision=revision, kind="RASTER")


def components(graph: RouteGraph) -> list[list[int]]:
    """Connected components over graph edges (each sorted by node id string; largest first, ties by first id)."""
    parent = list(range(len(graph.node_ids)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for rec in graph.edges:
        ru, rv = find(rec.u), find(rec.v)
        if ru != rv:
            parent[max(ru, rv)] = min(ru, rv)
    groups: dict[int, list[int]] = {}
    for node in range(len(graph.node_ids)):
        groups.setdefault(find(node), []).append(node)
    ordered = sorted(groups.values(), key=lambda g: (-len(g), min(g)))
    return ordered


def reachable_from(graph: RouteGraph, start: int) -> set[int]:
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for nbr, _ei, _sign in graph.adj[node]:
            if nbr not in seen:
                seen.add(nbr)
                stack.append(nbr)
    return seen
