"""Regression tests for the adversarial route-engine review: solver/verifier agreement on task satisfaction,
robust corner-touch geometry, node-id aliasing, root-label dominance, time budgets and non-finite terrain."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import (  # noqa: E402
    band_spec,
    brute_force_full,
    graph_design,
    graph_design_with,
    make_grid,
    make_route,
    ramp_grid,
    raster_constraints,
)

from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.ports.science_payloads import ConstraintsArtifact, GraphEdge, GraphSpec, Waypoint  # noqa: E402
from analogforge.science.routing import parse_raster_node_id, raster_node_id  # noqa: E402
from analogforge.science.routing.search import prepare_problem, search_route  # noqa: E402
from analogforge.science.routing.supercover import supercover  # noqa: E402
from analogforge.science.routing.verify import slab_cells, verify_route  # noqa: E402


def _verify(constraints, digest, sequence, grid=None, *, strategy="EXPOSURE_COVERAGE"):  # noqa: ANN001, ANN202
    route = make_route(digest, sequence, strategy=strategy)
    return verify_route(constraints, digest, route, canonical_sha256(route), "NOT_RUN", grid=grid, mode="synthetic")


def _retask(
    constraints: ConstraintsArtifact, location: Waypoint, tolerance_m: float
) -> tuple[ConstraintsArtifact, str]:
    task = constraints.tasks[0].model_copy(update={"location": location, "tolerance_m": tolerance_m})
    art = ConstraintsArtifact.model_validate(constraints.model_copy(update={"tasks": [task]}).model_dump(mode="json"))
    return art, canonical_sha256(art)


# ------------------------------------------------------------------------------- 1. task satisfaction semantics
def _walled_grid(cell: float = 60.0):  # noqa: ANN202
    valid = np.ones((5, 11), dtype=bool)
    valid[:, 5] = False  # full-height wall: the start side and the far side are disconnected
    return make_grid(np.full((5, 11), 3.0), valid=valid, cell_size_m=cell)


def test_task_is_satisfied_by_any_in_tolerance_node_not_just_the_nearest_one() -> None:
    """The node nearest to the task location sits behind the wall; a farther in-tolerance node is reachable.  The
    verifier accepts any in-tolerance route node, so the solver must too (previously: false EXHAUSTIVE_INFEASIBLE)."""
    grid = _walled_grid()
    base, _ = raster_constraints(grid, start=(2, 0), tasks=[("W1", (2, 6))])
    x, y = grid.center_xy(2, 5)
    art, digest = _retask(base, Waypoint(x_m=x + 0.2 * grid.cell_size_m, y_m=y), 2.5 * grid.cell_size_m)

    problem = prepare_problem(art, grid, mode="synthetic")
    nearest = problem.task_nodes["W1"]
    assert nearest is not None and problem.graph.cell(nearest) == (2, 6)  # nearest is across the wall
    cells = {problem.graph.cell(n) for n in problem.task_sets["W1"]}
    assert {(2, 3), (2, 4), (2, 6), (2, 7)} <= cells and all(c[1] != 5 for c in cells)

    out = search_route(art, digest, grid=grid, mode="synthetic")
    assert out.payload.search_status == "FOUND" and out.route is not None
    # the cheapest satisfying node is (2, 3): three steps out and three back
    assert out.route.solver_claimed.distance_m == pytest.approx(6 * grid.cell_size_m)
    assert [e.task_id for e in out.route.task_events] == ["W1"]
    assert problem.graph.cell(problem.graph.index_of[out.route.task_events[0].node_id]) == (2, 3)
    ver = verify_route(art, digest, out.route, out.route_sha256 or "", "FOUND", grid=grid, mode="synthetic")
    assert ver.payload.outcome == "PASS", [v.message for v in ver.payload.violations]


def test_task_is_infeasible_only_when_every_in_tolerance_node_is_cut_off() -> None:
    grid = _walled_grid()
    base, _ = raster_constraints(grid, start=(2, 0), tasks=[("W1", (2, 6))])
    x, y = grid.center_xy(2, 6)
    art, digest = _retask(base, Waypoint(x_m=x, y_m=y), 1.5 * grid.cell_size_m)  # nodes (cols 6, 7) only
    out = search_route(art, digest, grid=grid, mode="synthetic")
    assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
    assert out.payload.termination_reason.startswith("CERTIFICATE:")
    # the verifier agrees on a route that tries to cheat by stopping at the wall
    ver = _verify(art, digest, [raster_node_id(2, c) for c in (0, 1, 2, 3, 4, 3, 2, 1, 0)], grid)
    assert ver.payload.outcome == "FAIL" and "WAYPOINT_MISSED" in {v.code for v in ver.payload.violations}


# ------------------------------------------------------------------------------- 6. root label must not dominate
def _task_at_start_graph(traversals: int, strategy="WAYPOINT_RETURN"):  # noqa: ANN001, ANN202
    spec = GraphSpec(
        nodes=["S", "A"], edges=[GraphEdge(a="S", b="A", length_m=20.0, surface_slope_deg=10.0, mock_energy_wh=1.0)]
    )
    base = graph_design_with(spec, strategy).constraints
    task = base.tasks[0].model_copy(update={"task_id": "T0", "location": Waypoint(node_id="S")})
    art = ConstraintsArtifact.model_validate(
        base.model_copy(
            update={"tasks": [task], "max_undirected_edge_traversals": traversals, "exposures": []}
        ).model_dump(mode="json")
    )
    return art, canonical_sha256(art)


def test_task_at_start_still_finds_the_out_and_back_route() -> None:
    art, digest = _task_at_start_graph(2)
    out = search_route(art, digest, mode="synthetic")
    assert out.payload.search_status == "FOUND" and out.route is not None
    assert out.route.node_sequence == ["S", "A", "S"]
    oracle = brute_force_full(art)
    assert oracle is not None and oracle[2] == ("S", "A", "S")
    assert _verify(art, digest, out.route.node_sequence, strategy="WAYPOINT_RETURN").payload.outcome == "PASS"


def test_task_at_start_with_one_traversal_is_infeasible_and_the_oracle_agrees() -> None:
    art, digest = _task_at_start_graph(1)
    out = search_route(art, digest, mode="synthetic")
    assert out.payload.search_status == "EXHAUSTIVE_INFEASIBLE" and brute_force_full(art) is None


# ------------------------------------------------------------------------------- 7. time budget
def test_wall_clock_budget_is_checked_on_the_first_pop() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    t = [0.0]

    def clock() -> float:
        t[0] += 1000.0
        return t[0]

    out = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_seconds=1, clock=clock)
    assert out.payload.search_status == "BUDGET_EXHAUSTED" and "max_seconds" in out.payload.termination_reason
    assert out.payload.counters.expansions == 0


def test_wall_clock_budget_is_noticed_within_a_few_pops() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    readings = [0]

    def clock() -> float:  # the first readings look fast, then time jumps: must be noticed well before 256 pops
        readings[0] += 1
        return 0.0 if readings[0] <= 3 else 100.0

    out = search_route(design.constraints, design.constraints_sha256, mode="synthetic", max_seconds=1, clock=clock)
    assert out.payload.search_status == "BUDGET_EXHAUSTED"
    assert 0 < out.payload.counters.expansions <= 16


# ------------------------------------------------------------------------------- 3. node-id aliasing
@pytest.mark.parametrize(
    "alias", ["r05c13", "r5c013", "r005c13", "r5c00", "r５c13", "r٥c13", "r5c13\n", " r5c13", "R5c13", "r-1c3"]
)
def test_only_canonical_raster_ids_parse(alias: str) -> None:
    assert parse_raster_node_id(alias) is None
    assert parse_raster_node_id("r5c13") == (5, 13) and parse_raster_node_id("r0c0") == (0, 0)


def test_leading_zero_ids_are_flagged_as_noncanonical() -> None:
    from analogforge.science.routing import is_noncanonical_raster_node_id

    assert is_noncanonical_raster_node_id("r05c13") and is_noncanonical_raster_node_id("r5c013")
    assert not is_noncanonical_raster_node_id("r5c13") and not is_noncanonical_raster_node_id("abc")


def test_aliased_node_ids_cannot_launder_traversal_limit_or_unique_exposure() -> None:
    grid = ramp_grid(10, 24)
    expo = band_spec(12, 18, minimum=200.0)
    art, digest = raster_constraints(grid, start=(5, 13), tasks=[("W1", (5, 13))], exposures=[expo], max_distance_m=1e5)
    honest = ["r5c13", "r5c14"] * 5 + ["r5c13"]
    assert "EDGE_TRAVERSAL_LIMIT_EXCEEDED" in {v.code for v in _verify(art, digest, honest, grid).payload.violations}
    alias = ["r5c13", "r5c14", "r05c13", "r05c14", "r005c13", "r005c14", "r5c013", "r5c014", "r5c13"]
    ver = _verify(art, digest, alias, grid)
    assert ver.payload.outcome == "FAIL"
    codes = {v.code for v in ver.payload.violations}
    assert "DISCONTINUOUS_ROUTE" in codes
    assert any("non-canonical" in v.message for v in ver.payload.violations)
    assert ver.payload.verified_route_sha256 is None


# ------------------------------------------------------------------------------- 8. non-finite terrain
@pytest.mark.parametrize("field", ["slope_deg", "elevation_m"])
def test_nan_terrain_on_a_valid_cell_is_never_a_pass_and_never_raises(field: str) -> None:
    grid = make_grid(np.full((4, 6), 3.0))
    getattr(grid, field)[1, 3] = np.nan
    art, digest = raster_constraints(grid, start=(1, 1), tasks=[("W1", (1, 2))], max_distance_m=1e5)
    seq = [raster_node_id(1, c) for c in (1, 2, 3, 2, 1)]
    ver = _verify(art, digest, seq, grid)
    assert ver.payload.outcome == "INCONCLUSIVE" and ver.payload.failure_category == "DATA"
    assert ver.payload.verified_route_sha256 is None
    assert any(v.code == "UNKNOWN_TERRAIN" and "not finite" in v.message for v in ver.payload.violations)
    assert any(i.detail_code == "NONFINITE_TERRAIN" for i in ver.issues)
    # a route that avoids the corrupt cell is unaffected
    clean = _verify(art, digest, [raster_node_id(1, c) for c in (1, 2, 1)], grid)
    assert clean.payload.outcome == "PASS"
    # the solver treats the corrupt cell as untraversable (never as flat terrain) and does not raise
    far, far_digest = raster_constraints(grid, start=(1, 1), tasks=[("W1", (1, 5))], max_distance_m=1e5)
    found = search_route(far, far_digest, grid=grid, mode="synthetic")
    assert found.payload.search_status == "FOUND" and found.route is not None
    assert "r1c3" not in found.route.node_sequence
    assert _verify(far, far_digest, found.route.node_sequence, grid).payload.outcome == "PASS"


def test_nan_terrain_with_a_real_violation_is_still_a_fail() -> None:
    grid = make_grid(np.full((4, 6), 3.0))
    grid.slope_deg[1, 3] = np.nan
    art, digest = raster_constraints(grid, start=(1, 1), tasks=[("W1", (1, 2))], max_distance_m=10.0)
    ver = _verify(art, digest, [raster_node_id(1, c) for c in (1, 2, 3, 2, 1)], grid)
    assert ver.payload.outcome == "FAIL"


# ------------------------------------------------------------------------------- 2. corner touches, many cell sizes
CELL_SIZES = [27.8, 1 / 3, 7.3, 0.1, 30.0, 60.0, 12.5, 90.0, 0.5, 3.0]
ORIGINS = [
    (494240.0, 3900000.0),
    (500000.123, 4123456.789),
    (1234567.891, 9876543.21),
    (-17000000.3, 5000000.7),
    (0.0, 0.0),
]


@pytest.mark.parametrize("cell", CELL_SIZES)
@pytest.mark.parametrize("origin", ORIGINS)
def test_single_nodata_pixel_is_never_a_diagonal_bridge(cell: float, origin: tuple[float, float]) -> None:
    for corner in ((1, 2), (2, 1)):  # the two cells that touch the (1,1)->(2,2) diagonal only at its midpoint
        valid = np.ones((4, 4), dtype=bool)
        valid[corner] = False
        grid = make_grid(
            np.full((4, 4), 3.0), valid=valid, cell_size_m=cell, origin_x_m=origin[0], origin_y_m=origin[1]
        )
        # both algorithms report the corner cell (zero length)
        x0, y0 = grid.center_xy(1, 1)
        x1, y1 = grid.center_xy(2, 2)
        dda = {
            (h.row, h.col): h.length_m
            for h in supercover(x0, y0, x1, y1, cell_size_m=cell, origin_x_m=origin[0], origin_y_m=origin[1])
        }
        slab = {(r, c): length for r, c, length in slab_cells(x0, y0, x1, y1, grid)}
        assert corner in dda and corner in slab, (cell, origin, corner)
        assert dda[corner] <= 1e-9 and slab[corner] <= 1e-9
        assert set(dda) == set(slab) == {(1, 1), (2, 2), (1, 2), (2, 1)}
        # verifier rejects the bridge; the solver never builds it
        art, digest = raster_constraints(
            grid, start=(1, 1), tasks=[("W1", (2, 2))], max_distance_m=1e6, task_tolerance_m=0.0
        )
        ver = _verify(art, digest, [raster_node_id(*rc) for rc in ((1, 1), (2, 2), (1, 1))], grid)
        assert ver.payload.outcome == "FAIL", (cell, origin, corner)
        assert "UNKNOWN_TERRAIN" in {v.code for v in ver.payload.violations}
        out = search_route(art, digest, grid=grid, mode="synthetic")
        if out.route is not None:
            assert (
                "r1c1" not in out.route.node_sequence
                or "r2c2" not in out.route.node_sequence
                or not any(
                    {a, b} == {"r1c1", "r2c2"}
                    for a, b in zip(out.route.node_sequence, out.route.node_sequence[1:], strict=False)
                )
            )
            assert _verify(art, digest, out.route.node_sequence, grid).payload.outcome == "PASS"


def test_diagonal_through_a_corner_keeps_zero_length_corner_cells_at_non_dyadic_sizes() -> None:
    for cell in CELL_SIZES:
        for origin in ORIGINS:
            grid = make_grid(np.zeros((6, 6)), cell_size_m=cell, origin_x_m=origin[0], origin_y_m=origin[1])
            for (r0, c0), (r1, c1) in (((2, 2), (3, 3)), ((2, 3), (3, 2)), ((3, 3), (2, 2)), ((3, 2), (2, 3))):
                x0, y0 = grid.center_xy(r0, c0)
                x1, y1 = grid.center_xy(r1, c1)
                dda = {
                    (h.row, h.col)
                    for h in supercover(x0, y0, x1, y1, cell_size_m=cell, origin_x_m=origin[0], origin_y_m=origin[1])
                }
                slab = {(r, c) for r, c, _ in slab_cells(x0, y0, x1, y1, grid)}
                assert dda == slab == {(r0, c0), (r1, c1), (r0, c1), (r1, c0)}, (cell, origin, (r0, c0), (r1, c1))
                for h in supercover(x0, y0, x1, y1, cell_size_m=cell, origin_x_m=origin[0], origin_y_m=origin[1]):
                    assert math.isfinite(h.length_m)


# ------------------------------------------------------------------------------- traversal limit 1 on rasters
def test_raster_with_one_traversal_needs_a_loop() -> None:
    open_grid = make_grid(np.full((3, 3), 3.0))
    art, digest = raster_constraints(open_grid, start=(2, 2), tasks=[("W1", (0, 0))], max_distance_m=1e5)
    one = ConstraintsArtifact.model_validate(
        art.model_copy(update={"max_undirected_edge_traversals": 1}).model_dump(mode="json")
    )
    one_digest = canonical_sha256(one)
    out = search_route(one, one_digest, grid=open_grid, mode="synthetic")
    assert out.payload.search_status == "FOUND" and out.route is not None
    seq = out.route.node_sequence
    edges = [frozenset(p) for p in zip(seq, seq[1:], strict=False)]
    assert len(edges) == len(set(edges))  # a genuine loop, no edge twice
    assert _verify(one, one_digest, seq, open_grid).payload.outcome == "PASS"
    corridor = make_grid(np.full((1, 5), 3.0))
    c_art, _ = raster_constraints(corridor, start=(0, 0), tasks=[("W1", (0, 4))], max_distance_m=1e5)
    c_one = ConstraintsArtifact.model_validate(
        c_art.model_copy(update={"max_undirected_edge_traversals": 1}).model_dump(mode="json")
    )
    dead = search_route(c_one, canonical_sha256(c_one), grid=corridor, mode="synthetic")
    assert dead.payload.search_status == "EXHAUSTIVE_INFEASIBLE"
