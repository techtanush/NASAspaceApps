"""Property tests (hypothesis) for the route engine: oracle equality on random graphs, DDA/slab agreement, no invalid
traversal on random rasters, no duplicate exposure credit, monotone reserve, determinism."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from scipy import ndimage

_SUPPORT = Path(__file__).resolve().parents[2] / "unit/science/test_routing_support.py"
_spec = importlib.util.spec_from_file_location("routing_test_support", _SUPPORT)
assert _spec is not None and _spec.loader is not None
support = importlib.util.module_from_spec(_spec)
sys.modules["routing_test_support"] = support
_spec.loader.exec_module(support)

from analogforge.ports import catalog  # noqa: E402
from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.ports.science_payloads import GraphEdge, GraphSpec  # noqa: E402
from analogforge.science.routing import raster_node_id  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.supercover import supercover  # noqa: E402
from analogforge.science.routing.verify import slab_cells, verify_route  # noqa: E402

FAST = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)


def _metric(out, metric_id):  # noqa: ANN001, ANN202
    return next(m.value for m in out.payload.metrics if m.metric_id == metric_id)


# ------------------------------------------------------------------------------------------------ random graphs
@st.composite
def random_graphs(draw):  # noqa: ANN001, ANN202
    extra = draw(st.integers(0, 2))
    nodes = ["S", "W1", "W2", *["A", "B", "C"][:extra]]
    order = draw(st.permutations(nodes))
    edges: dict[frozenset[str], GraphEdge] = {}
    for i in range(1, len(order)):  # random spanning tree guarantees connectivity
        j = draw(st.integers(0, i - 1))
        a, b = order[i], order[j]
        edges[frozenset((a, b))] = GraphEdge(
            a=a,
            b=b,
            length_m=draw(st.sampled_from([40.0, 60.0, 80.0, 100.0])),
            surface_slope_deg=draw(st.sampled_from([5.0, 10.0, 15.0])),
            mock_energy_wh=draw(st.sampled_from([1.0, 2.0, 3.0])),
        )
    for _ in range(draw(st.integers(0, 2))):
        a, b = draw(st.sampled_from(nodes)), draw(st.sampled_from(nodes))
        if a != b and frozenset((a, b)) not in edges:
            edges[frozenset((a, b))] = GraphEdge(
                a=a,
                b=b,
                length_m=draw(st.sampled_from([40.0, 60.0, 80.0, 100.0])),
                surface_slope_deg=draw(st.sampled_from([5.0, 10.0, 15.0])),
                mock_energy_wh=draw(st.sampled_from([1.0, 2.0, 3.0])),
            )
    return GraphSpec(nodes=nodes, edges=list(edges.values()))


@FAST
@given(
    spec=random_graphs(),
    strategy=st.sampled_from(["WAYPOINT_RETURN", "EXPOSURE_COVERAGE"]),
    minimum=st.sampled_from([50.0, 100.0, 160.0]),
)
def test_search_equals_brute_force_on_random_graphs(spec, strategy, minimum) -> None:  # noqa: ANN001
    design = support.graph_design_with(spec, strategy)
    data = design.constraints.exposures[0].model_dump(mode="json") | {"minimum_distance_m": minimum}
    art, digest = support.rebuild(design.constraints, exposures=[data], max_distance_m=420.0)
    out = search_route(art, digest, mode="synthetic")
    oracle = support.brute_force(art)
    assert out.payload.counters.labels_pruned_lossy == 0
    if oracle is None:
        assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and out.route is None
        return
    assert out.payload.search_status == "FOUND" and out.route is not None
    distance, energy, sequence, _ = oracle
    assert tuple(out.route.node_sequence) == sequence
    assert math.isclose(out.route.solver_claimed.distance_m, distance, abs_tol=1e-6)
    assert math.isclose(out.route.solver_claimed.energy_conservative_wh or -1, energy, abs_tol=1e-6)
    # the independent verifier agrees on resources, and accepts exactly the routes that meet the exposure rule
    ver = verify_route(art, digest, out.route, out.route_sha256 or "", "FOUND", mode="synthetic")
    assert math.isclose(_metric(ver, "route_distance_m"), distance, abs_tol=1e-6)
    assert math.isclose(_metric(ver, "energy_conservative_wh"), energy, abs_tol=1e-6)
    assert _metric(ver, "route_distance_m") >= 0.0 and _metric(ver, "energy_conservative_wh") >= 0.0
    if strategy == "EXPOSURE_COVERAGE":
        assert ver.payload.outcome == "PASS"
        assert _metric(ver, "unique_exposure_m:R-EXPOSURE") >= minimum - 1e-9


@FAST
@given(spec=random_graphs())
def test_search_is_deterministic(spec) -> None:  # noqa: ANN001
    design = support.graph_design_with(spec, "EXPOSURE_COVERAGE")
    first = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    second = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    a, b = first.payload.model_dump(mode="json"), second.payload.model_dump(mode="json")
    a["counters"].pop("elapsed_ms")
    b["counters"].pop("elapsed_ms")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert first.route_sha256 == second.route_sha256


@FAST
@given(seed=st.integers(0, 10_000), length=st.integers(2, 14))
def test_random_walks_never_earn_duplicate_exposure(seed: int, length: int) -> None:
    """Unique exposure == 50 m * (distinct 15 deg edges walked) <= 150 m, however often edges repeat."""
    import random

    rng = random.Random(seed)  # noqa: S311 - seeded test data, not cryptography
    design = support.graph_design("EXPOSURE_COVERAGE")
    neighbours: dict[str, list[str]] = {}
    for e in design.constraints.graph.edges:  # type: ignore[union-attr]
        neighbours.setdefault(e.a, []).append(e.b)
        neighbours.setdefault(e.b, []).append(e.a)
    walk = ["S"]
    for _ in range(length):
        walk.append(rng.choice(sorted(neighbours[walk[-1]])))
    route = support.make_route(design.constraints_sha256, walk)
    out = verify_route(
        design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
    )
    steep = {frozenset(p) for p in (("S", "B"), ("B", "C"), ("C", "W1"))}
    distinct = {frozenset(p) for p in zip(walk, walk[1:], strict=False)} & steep
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == 50.0 * len(distinct) <= 150.0
    assert _metric(out, "traversed_exposure_m:R-EXPOSURE") >= _metric(out, "unique_exposure_m:R-EXPOSURE")
    assert _metric(out, "route_distance_m") >= 0.0


@FAST
@given(extra=st.integers(1, 5))
def test_reserve_decreases_monotonically_with_added_work(extra: int) -> None:
    design = support.graph_design("EXPOSURE_COVERAGE")
    base_route = list(catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    last = None
    for k in range(extra + 1):
        walk = [*base_route, *(["A", "S"] * k)]
        route = support.make_route(design.constraints_sha256, walk)
        out = verify_route(
            design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
        )
        reserve = _metric(out, "reserve_pct")
        if last is not None:
            assert reserve < last  # extra distance/energy strictly lowers the reserve, never clamped
        last = reserve
    assert last is not None and last <= 100.0


# ------------------------------------------------------------------------------------------------ geometry
@FAST
@given(
    u0=st.floats(1.0, 38.0),
    v0=st.floats(1.0, 38.0),
    du=st.floats(-6.0, 6.0),
    dv=st.floats(-6.0, 6.0),
)
def test_dda_and_slab_agree_everywhere(u0: float, v0: float, du: float, dv: float) -> None:
    grid = support.make_grid(np.zeros((40, 40)))
    x0, y0 = grid.origin_x_m + u0 * 60.0, grid.origin_y_m - v0 * 60.0
    x1, y1 = x0 + du * 60.0, y0 - dv * 60.0
    if not (0.5 < u0 + du < 39.5 and 0.5 < v0 + dv < 39.5):
        return
    # a segment lying exactly ON a grid line belongs to both neighbouring closed cells (slab) but to one (DDA);
    # route edges join cell centres and never do this, so that measure-zero degenerate case is excluded here
    assume(abs(du) > 1e-6 or abs(u0 - round(u0)) > 1e-6)
    assume(abs(dv) > 1e-6 or abs(v0 - round(v0)) > 1e-6)
    dda: dict[tuple[int, int], float] = {}
    for h in supercover(x0, y0, x1, y1, cell_size_m=60.0, origin_x_m=grid.origin_x_m, origin_y_m=grid.origin_y_m):
        dda[(h.row, h.col)] = dda.get((h.row, h.col), 0.0) + h.length_m
    slab = {(r, c): length for r, c, length in slab_cells(x0, y0, x1, y1, grid)}
    pos_a = {k: v for k, v in dda.items() if v > 1e-7}
    pos_b = {k: v for k, v in slab.items() if v > 1e-7}
    assert pos_a.keys() == pos_b.keys()
    for key in pos_a:
        assert math.isclose(pos_a[key], pos_b[key], abs_tol=1e-6)
    assert math.isclose(sum(pos_a.values()), math.hypot(x1 - x0, y1 - y0), abs_tol=1e-6)


# ------------------------------------------------------------------------------------------------ random rasters
def _reachable_cells(good: np.ndarray, passable: np.ndarray, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Independent oracle: 8-neighbour flood fill over good cells; a diagonal also needs both corner cells passable."""
    height, width = good.shape
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (
                    (dr, dc) == (0, 0)
                    or not (0 <= nr < height and 0 <= nc < width)
                    or not good[nr, nc]
                    or (nr, nc) in seen
                ):
                    continue
                if dr != 0 and dc != 0 and not (passable[r, nc] and passable[nr, c]):
                    continue
                seen.add((nr, nc))
                stack.append((nr, nc))
    return seen


@st.composite
def random_rasters(draw):  # noqa: ANN001, ANN202
    size = draw(st.integers(6, 9))
    seed = draw(st.integers(0, 2**31 - 1))
    rng = np.random.default_rng(seed)
    valid = rng.random((size, size)) > draw(st.sampled_from([0.0, 0.1, 0.25]))
    land = rng.random((size, size)) > 0.05
    slope = rng.choice([2.0, 6.0, 15.0, 21.0], size=(size, size))
    return size, valid, land, slope, seed


@FAST
@given(case=random_rasters())
def test_found_routes_never_touch_invalid_cells_and_feasibility_matches_flood_fill(case) -> None:  # noqa: ANN001
    size, valid, land, slope, _seed = case
    grid = support.make_grid(slope, valid=valid, land=land)
    good = valid & land & (np.where(valid, slope, np.inf) <= 18.0)
    cells = [(r, c) for r in range(size) for c in range(size) if good[r, c]]
    if len(cells) < 3:
        return
    start, w1 = cells[0], cells[len(cells) // 2]
    art, digest = support.raster_constraints(
        grid,
        start=start,
        tasks=[("W1", w1)],
        strategy="WAYPOINT_RETURN",
        energy_model=None,
        max_distance_m=None,
        task_tolerance_m=0.0,
    )
    out = search_route(art, digest, grid=grid, mode="synthetic")
    reach = _reachable_cells(good, valid & land, start)
    if w1 in reach:
        assert out.payload.search_status == "FOUND" and out.route is not None
        for node in out.route.node_sequence:
            r, c = int(node[1 : node.index("c")]), int(node[node.index("c") + 1 :])
            assert valid[r, c] and land[r, c] and slope[r, c] <= 18.0
        ver = verify_route(art, digest, out.route, out.route_sha256 or "", "FOUND", grid=grid, mode="synthetic")
        assert ver.payload.violations == [] and ver.payload.outcome == "INCONCLUSIVE"  # only energy is unknown
        assert math.isclose(_metric(ver, "route_distance_m"), out.route.solver_claimed.distance_m, abs_tol=1e-6)
        assert out.route.node_sequence[0] == out.route.node_sequence[-1] == raster_node_id(*start)
    else:
        assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and out.route is None


@FAST
@given(case=random_rasters())
def test_nodata_anywhere_on_a_verified_route_is_always_caught(case) -> None:  # noqa: ANN001
    size, valid, land, slope, _seed = case
    grid = support.make_grid(np.full((size, size), 3.0))
    start, w1 = (size // 2, 1), (size // 2, size - 2)
    art, digest = support.raster_constraints(
        grid, start=start, tasks=[("W1", w1)], strategy="WAYPOINT_RETURN", task_tolerance_m=0.0
    )
    out = search_route(art, digest, grid=grid, mode="synthetic")
    assert out.route is not None
    ok = verify_route(art, digest, out.route, out.route_sha256 or "", "FOUND", grid=grid, mode="synthetic")
    assert ok.payload.outcome == "PASS"
    for node in set(out.route.node_sequence):
        r, c = int(node[1 : node.index("c")]), int(node[node.index("c") + 1 :])
        bad_valid = np.ones((size, size), dtype=bool)
        bad_valid[r, c] = False
        broken = support.make_grid(np.full((size, size), 3.0), valid=bad_valid)
        out2 = verify_route(art, digest, out.route, out.route_sha256 or "", "FOUND", grid=broken, mode="synthetic")
        assert out2.payload.outcome == "FAIL" and "UNKNOWN_TERRAIN" in {v.code for v in out2.payload.violations}


def test_ndimage_is_the_independent_component_oracle_for_the_island_geometry() -> None:
    """Sanity of the oracle machinery itself: scipy components of a moat grid separate the island."""
    land = np.ones((12, 12), dtype=bool)
    land[3:9, 3:9] = False
    land[5:7, 5:7] = True
    labels, count = ndimage.label(land, structure=np.ones((3, 3)))
    assert count == 2 and labels[0, 0] != labels[5, 5]


# ------------------------------------------------------------------------------------------------ corner touches
@given(
    cell=st.one_of(
        st.sampled_from([27.8, 1 / 3, 7.3, 0.1, 30.0, 60.0, 12.5, 0.7]), st.floats(0.05, 120.0, allow_nan=False)
    ),
    origin_x=st.one_of(st.just(0.0), st.floats(-2.0e7, 2.0e7), st.sampled_from([494240.0, 500000.123, 1234567.891])),
    origin_y=st.one_of(st.just(0.0), st.floats(-1.0e7, 1.0e7), st.sampled_from([3900000.0, 4123456.789])),
    row=st.integers(1, 3),
    col=st.integers(1, 3),
    d_row=st.sampled_from([-1, 1]),
    d_col=st.sampled_from([-1, 1]),
    which=st.sampled_from([0, 1]),
)
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
def test_one_pixel_nodata_channel_is_never_a_diagonal_bridge(cell, origin_x, origin_y, row, col, d_row, d_col, which):  # noqa: ANN001, ANN201
    """For ANY cell size / origin a diagonal step passing exactly through a cell corner touches both corner cells, so
    nodata at either of them blocks the step in BOTH algorithms (solver DDA and verifier slab clipping)."""
    assume(0 <= row + d_row <= 4 and 0 <= col + d_col <= 4)
    corner = (row, col + d_col) if which == 0 else (row + d_row, col)
    valid = np.ones((5, 5), dtype=bool)
    valid[corner] = False
    grid = support.make_grid(
        np.full((5, 5), 3.0), valid=valid, cell_size_m=cell, origin_x_m=origin_x, origin_y_m=origin_y
    )
    x0, y0 = grid.center_xy(row, col)
    x1, y1 = grid.center_xy(row + d_row, col + d_col)
    dda = {
        (h.row, h.col) for h in supercover(x0, y0, x1, y1, cell_size_m=cell, origin_x_m=origin_x, origin_y_m=origin_y)
    }
    slab = {(r, c) for r, c, _ in slab_cells(x0, y0, x1, y1, grid)}
    assert corner in dda and corner in slab
    assert dda == slab
    constraints, digest = support.raster_constraints(
        grid, start=(row, col), tasks=[("W1", (row + d_row, col + d_col))], max_distance_m=1e9, task_tolerance_m=0.0
    )
    route = support.make_route(digest, [raster_node_id(row, col), raster_node_id(row + d_row, col + d_col)])
    verdict = verify_route(constraints, digest, route, canonical_sha256(route), "NOT_RUN", grid=grid, mode="synthetic")
    assert verdict.payload.outcome == "FAIL"
    assert "UNKNOWN_TERRAIN" in {v.code for v in verdict.payload.violations}
    found = search_route(constraints, digest, grid=grid, mode="synthetic")
    if found.route is not None:
        seq = found.route.node_sequence
        assert {raster_node_id(row, col), raster_node_id(row + d_row, col + d_col)} not in [
            {a, b} for a, b in zip(seq, seq[1:], strict=False)
        ]
