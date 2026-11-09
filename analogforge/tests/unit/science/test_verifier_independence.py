"""SCN-04: the verifier recomputes everything from ``node_sequence`` and rejects what a sloppy checker would accept.

Falsified solver totals, diagonal-corner / nodata traversal, stale hashes, repeated-edge exposure gaming, missing
return, non-adjacent steps, unreachable / too-far waypoints, energy-margin sign errors, mutated routes, and a
structural test that the verifier does not import the solver.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import (  # noqa: E402
    graph_design,
    make_grid,
    make_route,
    raster_constraints,
    rebuild,
)

from analogforge.ports import catalog  # noqa: E402
from analogforge.ports.hashing import canonical_sha256  # noqa: E402
from analogforge.ports.science_payloads import SolverClaimedTotals, TaskEvent  # noqa: E402
from analogforge.science.routing import raster_node_id  # noqa: E402
from analogforge.science.routing.search import search_route  # noqa: E402
from analogforge.science.routing.verify import verify_route  # noqa: E402

SRC = Path(__file__).resolve().parents[3] / "src/analogforge/science/routing"


def _verify(design, sequence, *, constraints=None, digest=None, claimed=None, status="NOT_RUN"):  # noqa: ANN001, ANN202
    constraints = constraints or design.constraints
    digest = digest or design.constraints_sha256
    route = make_route(digest, sequence, claimed=claimed)
    return verify_route(constraints, digest, route, canonical_sha256(route), status, mode="synthetic")


def _codes(out) -> list[str]:  # noqa: ANN001
    return [v.code for v in out.payload.violations]


def _metric(out, metric_id):  # noqa: ANN001, ANN202
    return next(m.value for m in out.payload.metrics if m.metric_id == metric_id)


def _ids(*cells: tuple[int, int]) -> list[str]:
    return [raster_node_id(r, c) for r, c in cells]


# ------------------------------------------------------------------------------------------------ falsified totals
def test_falsified_solver_totals_are_ignored() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    honest = _verify(design, catalog.GRAPH_SUPPLIED_ROUTE_FAIL)
    lie = SolverClaimedTotals(distance_m=340.0, energy_conservative_wh=34.0, unique_exposure_m={"R-EXPOSURE": 150.0})
    lying = _verify(design, catalog.GRAPH_SUPPLIED_ROUTE_FAIL, claimed=lie)
    assert lying.payload.outcome == "FAIL" and _codes(lying) == ["EXPOSURE_SHORTFALL"]
    assert lying.payload.metrics == honest.payload.metrics  # claims never enter the verified numbers
    assert _metric(lying, "route_distance_m") == 120.0 != lie.distance_m
    assert _metric(lying, "unique_exposure_m:R-EXPOSURE") == 0.0 != lie.unique_exposure_m["R-EXPOSURE"]
    assert _metric(lying, "energy_conservative_wh") == 26.0 != lie.energy_conservative_wh


def test_searched_route_with_tampered_claims_verifies_identically() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    found = search_route(design.constraints, design.constraints_sha256, mode="synthetic")
    assert found.route is not None
    honest = verify_route(
        design.constraints, design.constraints_sha256, found.route, found.route_sha256 or "", "FOUND", mode="synthetic"
    )
    tampered = found.route.model_copy(
        update={"solver_claimed": SolverClaimedTotals(distance_m=1.0, energy_conservative_wh=0.0, unique_exposure_m={})}
    )
    out = verify_route(
        design.constraints, design.constraints_sha256, tampered, canonical_sha256(tampered), "FOUND", mode="synthetic"
    )
    assert out.payload.outcome == honest.payload.outcome == "PASS"
    assert out.payload.metrics == honest.payload.metrics


def test_lying_task_events_do_not_complete_tasks() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    route = make_route(design.constraints_sha256, ["S", "A", "S"]).model_copy(
        update={
            "task_events": [
                TaskEvent(task_id="W1", node_id="W1", arrival_distance_m=20.0, dwell_s=0.0),
                TaskEvent(task_id="W2", node_id="W2", arrival_distance_m=40.0, dwell_s=0.0),
            ]
        }
    )
    out = verify_route(
        design.constraints, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic"
    )
    assert out.payload.outcome == "FAIL"
    assert _codes(out).count("WAYPOINT_MISSED") == 2 and _metric(out, "tasks_completed") == 0.0


# ------------------------------------------------------------------------------------------------ stale hashes
def test_stale_constraints_hash_is_inconclusive_system() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    route = make_route(design.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    out = verify_route(design.constraints, "f" * 64, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
    assert (out.payload.outcome, out.payload.failure_category) == ("INCONCLUSIVE", "SYSTEM")
    assert _codes(out) == ["STALE_INPUT_HASH"] and out.payload.verified_route_sha256 is None
    assert out.telemetry is None and out.issues[0].code == "STALE_INPUT_HASH"


def test_route_built_for_other_constraints_and_edited_route_are_stale() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    other = make_route("e" * 64, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    out = verify_route(
        design.constraints, design.constraints_sha256, other, canonical_sha256(other), "NOT_RUN", mode="synthetic"
    )
    assert _codes(out) == ["STALE_INPUT_HASH"]
    route = make_route(design.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    edited = route.model_copy(update={"node_sequence": ["S", "A", "W1", "W2", "W1", "A", "S"]})
    out2 = verify_route(
        design.constraints, design.constraints_sha256, edited, canonical_sha256(route), "NOT_RUN", mode="synthetic"
    )
    assert _codes(out2) == ["STALE_INPUT_HASH"]  # claimed route hash no longer matches the bytes
    changed, _ = rebuild(design.constraints, max_distance_m=399.0)
    out3 = verify_route(changed, design.constraints_sha256, route, canonical_sha256(route), "NOT_RUN", mode="synthetic")
    assert _codes(out3) == ["STALE_INPUT_HASH"]  # constraints edited after hashing


# ------------------------------------------------------------------------------------------------ gaming
def test_repeated_edge_oscillation_cannot_manufacture_unique_exposure() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    needs_200, digest = rebuild(
        design.constraints,
        exposures=[{**design.constraints.exposures[0].model_dump(mode="json"), "minimum_distance_m": 200.0}],
    )
    route = ["S", "B", "C", "B", "S", "A", "W1", "W2", "W1", "A", "S"]  # S-B and B-C each walked twice
    out = _verify(design, route, constraints=needs_200, digest=digest)
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == 100.0
    assert _metric(out, "traversed_exposure_m:R-EXPOSURE") == 200.0
    assert out.payload.outcome == "FAIL" and _codes(out) == ["EXPOSURE_SHORTFALL"]
    assert out.payload.violations[0].observed == 100.0
    # the same walk under *total traversed* counting is legitimately credited
    total = needs_200.model_dump(mode="json")
    total["exposures"][0]["counting"] = "TOTAL_TRAVERSED_DISTANCE"
    total_art, total_digest = rebuild(needs_200, exposures=total["exposures"])
    assert _verify(design, route, constraints=total_art, digest=total_digest).payload.outcome == "PASS"


def test_edge_traversal_limit_is_enforced_and_energy_time_are_still_paid() -> None:
    design = graph_design("WAYPOINT_RETURN")
    route = ["S", "A", "W1", "W2", "W1", "W2", "W1", "W2", "W1", "A", "S"]  # W1-W2 six times
    out = _verify(design, route)
    assert "EDGE_TRAVERSAL_LIMIT_EXCEEDED" in _codes(out)
    assert _metric(out, "route_distance_m") == 200.0  # 10 steps of 20 m: the oscillation is paid for in distance
    assert _metric(out, "unique_exposure_m:R-EXPOSURE") == 0.0
    assert _metric(out, "energy_conservative_wh") == 10 * 1.0 + 20.0  # ten traversals of 1 Wh + two tasks, tasks once


# ------------------------------------------------------------------------------------------------ route shape
def test_missing_return_non_adjacent_step_and_missing_task() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    no_return = _verify(design, ["S", "A", "W1", "W2"])
    assert "RETURN_NOT_COMPLETED" in _codes(no_return) and no_return.payload.outcome == "FAIL"
    teleport = _verify(design, ["S", "W1", "W2", "W1", "A", "S"])  # S-W1 is not an edge
    codes = _codes(teleport)
    assert "DISCONTINUOUS_ROUTE" in codes
    bad = next(v for v in teleport.payload.violations if v.code == "DISCONTINUOUS_ROUTE")
    assert (bad.segment_from_index, bad.segment_to_index) == (0, 1)
    unknown_node = _verify(design, ["S", "Z", "S"])
    assert "DISCONTINUOUS_ROUTE" in _codes(unknown_node)
    missing_task = _verify(design, ["S", "A", "W1", "A", "S"])
    assert _codes(missing_task).count("WAYPOINT_MISSED") == 1
    assert next(v for v in missing_task.payload.violations if v.code == "WAYPOINT_MISSED").constraint_id == "C-TASK-W2"
    wrong_start = _verify(design, ["A", "W1", "W2", "W1", "A"])
    assert "WAYPOINT_MISSED" in _codes(wrong_start)
    assert any(v.constraint_id == "C-START" for v in wrong_start.payload.violations)


def test_mutated_route_is_rejected() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    good = list(catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE)
    assert _verify(design, good).payload.outcome == "PASS"
    for position in range(1, len(good) - 1):
        mutated = list(good)
        mutated[position] = "W2" if mutated[position] != "W2" else "B"
        out = _verify(design, mutated)
        assert out.payload.outcome == "FAIL", (position, mutated)


# ------------------------------------------------------------------------------------------------ energy
def test_energy_threshold_equality_passes_and_shortfall_fails_without_clamping() -> None:
    design = graph_design("EXPOSURE_COVERAGE")
    route = catalog.GRAPH_SUPPLIED_ROUTE_PASS  # 34 Wh
    for battery, expected, reserve in ((42.5, "PASS", 20.0), (42.4, "FAIL", None), (20.0, "FAIL", -70.0)):
        energy = design.constraints.energy.model_dump(mode="json") | {"battery_wh": battery}
        art, digest = rebuild(design.constraints, energy=energy)
        out = _verify(design, route, constraints=art, digest=digest)
        assert out.payload.outcome == expected, battery
        if reserve is not None:
            assert _metric(out, "reserve_pct") == pytest.approx(reserve, abs=1e-9)
        if expected == "FAIL":
            assert _codes(out) == ["ENERGY_RESERVE_SHORTFALL"]
            row = next(r for r in out.payload.benchmark_rows if r.constraint_id == catalog.CONSTRAINT_ENERGY_RESERVE)
            assert row.status == "FAIL" and row.margin is not None and row.margin < 0
    sample = _verify(design, route)
    row = next(r for r in sample.payload.benchmark_rows if r.constraint_id == catalog.CONSTRAINT_ENERGY_RESERVE)
    assert row.margin == pytest.approx(row.measured - row.threshold)  # type: ignore[operator]
    last = sample.telemetry.samples[-1]  # type: ignore[union-attr]
    assert last.cumulative_energy_conservative_wh == 34.0 and last.reserve_pct == _metric(sample, "reserve_pct")


def test_missing_energy_model_is_inconclusive_data_never_zero() -> None:
    grid = make_grid(np.full((6, 6), 3.0))
    art, digest = raster_constraints(grid, start=(3, 1), tasks=[("W1", (3, 4))], energy_model=None)
    route = make_route(digest, _ids((3, 1), (3, 2), (3, 3), (3, 4), (3, 3), (3, 2), (3, 1)))
    out = verify_route(art, digest, route, canonical_sha256(route), "NOT_RUN", mode="synthetic", grid=grid)
    assert (out.payload.outcome, out.payload.failure_category) == ("INCONCLUSIVE", "DATA")
    assert out.issues[0].code == "ENERGY_UNCALIBRATED"
    assert _metric(out, "reserve_pct") is None and _metric(out, "energy_conservative_wh") is None
    row = next(r for r in out.payload.benchmark_rows if r.constraint_id == catalog.CONSTRAINT_ENERGY_RESERVE)
    assert row.status == "INCONCLUSIVE" and row.measured is None
    assert all(s.reserve_pct is None for s in out.telemetry.samples)  # type: ignore[union-attr]
    # a definite violation still wins over the unevaluable item
    short = make_route(digest, _ids((3, 1), (3, 2)))
    out2 = verify_route(art, digest, short, canonical_sha256(short), "NOT_RUN", mode="synthetic", grid=grid)
    assert out2.payload.outcome == "FAIL"


# ------------------------------------------------------------------------------------------------ raster geometry
def _line(row: int, c0: int, c1: int) -> list[tuple[int, int]]:
    step = 1 if c1 >= c0 else -1
    return [(row, c) for c in range(c0, c1 + step, step)]


def _raster(slope=None, valid=None, land=None, **kw):  # noqa: ANN001, ANN002, ANN003, ANN202
    slope = np.full((7, 7), 3.0) if slope is None else slope
    grid = make_grid(slope, valid=valid, land=land)
    art, digest = raster_constraints(grid, start=(3, 1), tasks=[("W1", (3, 5))], **kw)
    return grid, art, digest


def _verify_cells(grid, art, digest, cells):  # noqa: ANN001, ANN202
    route = make_route(digest, _ids(*cells))
    return verify_route(art, digest, route, canonical_sha256(route), "NOT_RUN", mode="synthetic", grid=grid)


def test_clean_raster_route_passes_and_matches_hand_computation() -> None:
    grid, art, digest = _raster()
    cells = [*_line(3, 1, 5), *_line(3, 4, 1)]
    out = _verify_cells(grid, art, digest, cells)
    assert out.payload.outcome == "PASS", out.payload.violations
    assert _metric(out, "route_distance_m") == 8 * 60.0
    assert _metric(out, "route_duration_s") == pytest.approx(8 * 60.0 / 0.5 + 60.0)  # drive + one dwell
    assert [s.node_id for s in out.telemetry.samples] == _ids(*cells)  # type: ignore[union-attr]
    dist = [s.cumulative_distance_m for s in out.telemetry.samples]  # type: ignore[union-attr]
    assert dist == sorted(dist) and dist[-1] == 480.0


def test_diagonal_cutting_a_nodata_corner_is_rejected() -> None:
    valid = np.ones((7, 7), dtype=bool)
    valid[2, 3] = False  # touched only at the shared corner by the diagonal (2,2)->(3,3)
    grid, art, digest = _raster(valid=valid)
    out = _verify_cells(
        grid, art, digest, [(3, 1), (3, 2), (2, 2), (3, 3), (3, 4), (3, 5), (3, 4), (3, 3), (3, 2), (3, 1)]
    )
    assert "UNKNOWN_TERRAIN" in _codes(out) and out.payload.outcome == "FAIL"
    # the identical route is fine once the corner cell is valid again (the rule, not the geometry, rejects it)
    grid2, art2, digest2 = _raster()
    ok = _verify_cells(
        grid2, art2, digest2, [(3, 1), (3, 2), (2, 2), (3, 3), (3, 4), (3, 5), (3, 4), (3, 3), (3, 2), (3, 1)]
    )
    assert ok.payload.outcome == "PASS"


def test_one_pixel_nodata_channel_is_not_a_diagonal_bridge() -> None:
    valid = np.ones((7, 7), dtype=bool)
    valid[:, 3] = False  # a one-cell wide channel
    grid, art, digest = _raster(valid=valid)
    jump = _verify_cells(grid, art, digest, [(3, 1), (3, 2), (3, 4), (3, 5), (3, 4), (3, 2), (3, 1)])
    assert "DISCONTINUOUS_ROUTE" in _codes(jump)
    diagonal = _verify_cells(
        grid, art, digest, [(3, 1), (3, 2), (2, 3), (3, 4), (3, 5), (3, 4), (2, 3), (3, 2), (3, 1)]
    )
    assert "UNKNOWN_TERRAIN" in _codes(diagonal)


def test_water_slope_cap_blocked_edge_and_dilation_rules() -> None:
    land = np.ones((7, 7), dtype=bool)
    land[3, 3] = False
    grid, art, digest = _raster(land=land)
    water = _verify_cells(grid, art, digest, [*_line(3, 1, 5), *_line(3, 4, 1)])
    assert "FORBIDDEN_INTERSECTION" in _codes(water)

    slope = np.full((7, 7), 3.0)
    slope[3, 3] = 20.0
    grid, art, digest = _raster(slope=slope)
    steep = _verify_cells(grid, art, digest, [*_line(3, 1, 5), *_line(3, 4, 1)])
    violation = next(v for v in steep.payload.violations if v.code == "MAX_SLOPE_EXCEEDED")
    assert violation.observed == 20.0 and violation.threshold == 18.0
    assert _metric(steep, "max_surface_slope_deg") == 20.0

    slope = np.full((7, 7), 3.0)
    slope[2, 3] = 25.0  # corner-touched only by the diagonal: not a positive-length cell
    grid, art, digest = _raster(slope=slope)
    corner = _verify_cells(
        grid, art, digest, [(3, 1), (3, 2), (2, 2), (3, 3), (3, 4), (3, 5), (3, 4), (3, 3), (3, 2), (3, 1)]
    )
    assert "MAX_SLOPE_EXCEEDED" not in _codes(corner)

    grid, art, digest = _raster(blocked=["r3c2--r3c3"])
    blocked = _verify_cells(grid, art, digest, [*_line(3, 1, 5), *_line(3, 4, 1)])
    assert "FORBIDDEN_INTERSECTION" in _codes(blocked)

    valid = np.ones((7, 7), dtype=bool)
    valid[0, 6] = False
    grid, art, digest = _raster(valid=valid, dilation_m=60.0)
    near = _verify_cells(grid, art, digest, [(3, 1), (2, 2), (1, 5), (2, 5), (3, 5), (2, 5), (1, 5), (2, 2), (3, 1)])
    assert near.payload.outcome == "FAIL"  # (1,5) and (0,5)/(1,6) neighbours of the invalid cell are dilated away


def test_waypoint_snapping_tolerance_is_enforced_by_the_verifier() -> None:
    grid = make_grid(np.full((7, 7), 3.0))
    art, digest = raster_constraints(grid, start=(3, 1), tasks=[("W1", (3, 5))], task_tolerance_m=60.0)

    def run(cells):  # noqa: ANN001, ANN202
        return _verify_cells(grid, art, digest, cells)

    reached = run([(3, 1), (3, 2), (3, 3), (3, 4), (3, 3), (3, 2), (3, 1)])  # one cell short: 60 m <= tolerance
    assert reached.payload.outcome == "PASS"
    short = run([(3, 1), (3, 2), (3, 3), (3, 2), (3, 1)])  # two cells short: 120 m > tolerance
    assert short.payload.outcome == "FAIL" and "WAYPOINT_MISSED" in _codes(short)
    diagonal_miss = run([(3, 1), (4, 2), (4, 3), (4, 4), (4, 3), (4, 2), (3, 1)])  # diagonal neighbour is 84.9 m away
    assert "WAYPOINT_MISSED" in _codes(diagonal_miss)


def test_return_closure_requires_ending_at_the_start() -> None:
    grid, art, digest = _raster()
    out = _verify_cells(grid, art, digest, [*_line(3, 1, 5), *_line(3, 4, 2)])  # stops one cell short of the start
    violation = next(v for v in out.payload.violations if v.code == "RETURN_NOT_COMPLETED")
    assert violation.observed == 60.0 and out.payload.outcome == "FAIL"


# ------------------------------------------------------------------------------------------------ structure
def test_verifier_imports_no_solver_module() -> None:
    forbidden = {"search", "grid_graph", "fixture_graph", "supercover", "certificate", "waypoints", "diagnose"}
    tree = ast.parse((SRC / "verify.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    leaked = {m for m in imported if m.rsplit(".", 1)[-1] in forbidden and m.startswith("analogforge")}
    assert leaked == set()


def test_importing_the_verifier_does_not_load_solver_modules() -> None:
    code = (
        "import sys, analogforge.science.routing.verify;"
        "bad=[m for m in sys.modules if m.startswith('analogforge.science.routing.') and m.rsplit('.',1)[-1] in "
        "('search','grid_graph','fixture_graph','supercover','certificate','waypoints','diagnose')];"
        "print(','.join(bad))"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert result.stdout.strip() == ""
