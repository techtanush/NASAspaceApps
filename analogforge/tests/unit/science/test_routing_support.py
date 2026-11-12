"""Shared builders for the routing tests (helpers only; one self-test at the bottom).

Everything is derived from the frozen kit fixtures (rovers, missions, canonical graph) so no expected value is
re-typed here except where an independent oracle is computed on purpose.
"""

from __future__ import annotations

import datetime
import itertools
import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from analogforge.ports import catalog
from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import EnergyModel, MissionTestContract, RoverProfile, SolverConfig
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    CandidateRef,
    ConstraintsArtifact,
    DesignBenchmarkInput,
    DesignBenchmarkPayload,
    EnergySpec,
    ExposureSpec,
    GraphSpec,
    GridSpec,
    RouteArtifact,
    RouteStrategy,
    SolverClaimedTotals,
    TaskSpec,
    Waypoint,
)
from analogforge.science.routing import GridArrays, raster_node_id
from analogforge.science.routing.fixture_graph import canonical_graph_spec
from analogforge.science.routing.waypoints import design_benchmark

FIX = Path(__file__).resolve().parents[3] / "tests/fixtures/kit"
NOW = datetime.datetime(2026, 11, 5, tzinfo=datetime.UTC).isoformat()


def load_json(rel: str) -> dict:
    return json.loads((FIX / rel).read_text())


def _base() -> dict:
    return {
        "schema_version": "1.0",
        "id": str(uuid.UUID(int=1)),
        "workspace_id": str(uuid.UUID(int=2)),
        "revision": 1,
        "created_at": NOW,
        "content_sha256": "a" * 64,
    }


def mission(name: str = "mission-graph-regression") -> MissionTestContract:
    return MissionTestContract(
        **load_json(f"missions/{name}.json"), **_base(), mission_id=str(uuid.UUID(int=3)), accepted_at=NOW
    )


def rover(name: str = "ares-1", **overrides: object) -> RoverProfile:
    data = load_json(f"rovers/{name}.json")
    data.update(overrides)
    return RoverProfile(**data, **_base(), rover_id=str(uuid.UUID(int=4)))


def candidate(window_id: str = catalog.GRAPH_WINDOW_ID) -> CandidateRef:
    msn = mission()
    return CandidateRef(
        window_id=window_id,
        name=catalog.PRACTICE_CANDIDATE_NAME_PREFIX + window_id,
        aoi=msn.target.model_copy(update={"body": "EARTH"}),
        origin="SYNTHETIC_CONTROL",
        novelty_status="NOT_ASSESSED",
        discovery_method="test",
    )


def design_input(
    strategy: RouteStrategy = "EXPOSURE_COVERAGE",
    *,
    rover_obj: RoverProfile | None = None,
    mission_obj: MissionTestContract | None = None,
    graph: bool = True,
    blocked: Sequence[str] = (),
    window_id: str = catalog.GRAPH_WINDOW_ID,
) -> DesignBenchmarkInput:
    return DesignBenchmarkInput(
        mission=mission_obj or mission(),
        rover=rover_obj or rover(),
        candidate=candidate(window_id),
        analysis_evidence_id=None if graph else uuid.UUID(int=9),
        graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH if graph else None,
        strategy=strategy,
        test_revision=1,
        blocked_edge_ids=list(blocked),
    )


def graph_design(strategy: RouteStrategy = "EXPOSURE_COVERAGE", **kw: object) -> DesignBenchmarkPayload:
    return design_benchmark(design_input(strategy, **kw), mode="synthetic")  # type: ignore[arg-type]


def graph_design_with(
    spec: GraphSpec, strategy: RouteStrategy = "EXPOSURE_COVERAGE", **kw: object
) -> DesignBenchmarkPayload:
    from analogforge.science.routing.constraints import RouteDesignDefaults
    from analogforge.science.routing.fixture_graph import design_graph_benchmark

    return design_graph_benchmark(
        design_input(strategy, **kw),
        mode="synthetic",
        defaults=RouteDesignDefaults(),
        graph=spec,  # type: ignore[arg-type]
    )


def rebuild(constraints: ConstraintsArtifact, **updates: object) -> tuple[ConstraintsArtifact, str]:
    """Re-validate an artifact with changes and return it with its canonical hash."""
    data = constraints.model_dump(mode="json")
    data.update(updates)
    new = ConstraintsArtifact.model_validate(data)
    return new, canonical_sha256(new)


def make_route(
    constraints_sha256: str,
    sequence: Sequence[str],
    *,
    strategy: RouteStrategy = "EXPOSURE_COVERAGE",
    claimed: SolverClaimedTotals | None = None,
    mode: RuntimeMode = "synthetic",
) -> RouteArtifact:
    return RouteArtifact(
        route_key="supplied",
        mode=mode,
        constraints_sha256=constraints_sha256,
        strategy=strategy,
        graph_revision="supplied",
        node_sequence=list(sequence),
        task_events=[],
        display_geometry=None,
        solver_claimed=claimed or SolverClaimedTotals(distance_m=0.0, energy_conservative_wh=0.0, unique_exposure_m={}),
    )


# ----------------------------------------------------------------------------------------------- brute force oracle
def brute_force(spec: ConstraintsArtifact) -> tuple[float, float, tuple[str, ...], float] | None:
    """Independent exhaustive search on an abstract graph: min (distance, energy, node_sequence) closed walk.

    Written separately from the solver: plain recursion over walks with <= max traversals per undirected edge.
    Returns ``(distance, energy, sequence, unique_exposure)`` or ``None``.
    """
    assert spec.graph is not None
    edges = {}
    for e in spec.graph.edges:
        if e.surface_slope_deg <= spec.surface_slope_cap_deg:
            edges[frozenset((e.a, e.b))] = e
    adj: dict[str, list[str]] = {n: [] for n in spec.graph.nodes}
    for e in edges.values():
        adj[e.a].append(e.b)
        adj[e.b].append(e.a)
    tasks = {t.task_id: spec.tasks[i] for i, t in enumerate(spec.tasks)}
    need_exposure = spec.strategy != "WAYPOINT_RETURN"
    start = spec.start.node_id
    assert start is not None
    max_trav = spec.max_undirected_edge_traversals
    max_dist = spec.max_distance_m
    best: list[tuple[float, float, tuple[str, ...], float]] = []

    def exposure_of(used: dict[frozenset[str], int], expo: ExposureSpec) -> float:
        total = 0.0
        for key, count in used.items():
            e = edges[key]
            lo, hi = expo.band_deg
            inside = lo <= e.surface_slope_deg < hi or (expo.upper_inclusive and e.surface_slope_deg == hi)
            if inside:
                total += e.length_m * (1 if expo.counting == "UNIQUE_UNDIRECTED_EDGE_DISTANCE" else count)
        return total

    def rec(
        node: str, path: list[str], used: dict[frozenset[str], int], dist: float, energy: float, done: frozenset[str]
    ) -> None:
        if max_dist is not None and dist > max_dist + 1e-9:
            return
        if node == start and len(path) > 1 and len(done) == len(tasks):
            ok = (
                all(exposure_of(used, x) >= x.minimum_distance_m - 1e-9 for x in spec.exposures)
                if need_exposure
                else True
            )
            if ok:
                first = exposure_of(used, spec.exposures[0]) if spec.exposures else 0.0
                best.append((round(dist, 9), round(energy, 9), tuple(path), first))
        for nbr in sorted(adj[node]):
            key = frozenset((node, nbr))
            if used.get(key, 0) >= max_trav:
                continue
            newly = {t for t, ts in tasks.items() if ts.location.node_id == nbr and t not in done}
            extra = sum(tasks[t].incremental_energy_wh or 0.0 for t in newly)
            used[key] = used.get(key, 0) + 1
            rec(
                nbr,
                [*path, nbr],
                used,
                dist + edges[key].length_m,
                energy + (edges[key].mock_energy_wh or 0.0) + extra,
                done | newly,
            )
            used[key] -= 1
            if used[key] == 0:
                del used[key]

    init_done = frozenset(t for t, ts in tasks.items() if ts.location.node_id == start)
    init_energy = sum(tasks[t].incremental_energy_wh or 0.0 for t in init_done)
    rec(start, [start], {}, 0.0, init_energy, init_done)
    if not best:
        return None
    return min(best, key=lambda b: (b[0], b[1], b[2]))


def brute_force_full(spec: ConstraintsArtifact) -> tuple[float, float, tuple[str, ...]] | None:
    """Exhaustive oracle that honours EVERYTHING the search honours on an abstract graph: traversal limit (1 or more),
    max distance, the usable-energy bound, unique AND total exposure counting and the strategy's objective order
    (MINIMUM_FEASIBLE_ROUTE: energy first; otherwise distance first).  Returns ``(distance, energy, sequence)``."""
    assert spec.graph is not None and spec.start.node_id is not None
    edges = {frozenset((e.a, e.b)): e for e in spec.graph.edges if e.surface_slope_deg <= spec.surface_slope_cap_deg}
    adj: dict[str, list[str]] = {n: [] for n in spec.graph.nodes}
    for e in edges.values():
        adj[e.a].append(e.b)
        adj[e.b].append(e.a)
    tasks = {t.task_id: t for t in spec.tasks}
    start = spec.start.node_id
    need_exposure = spec.strategy != "WAYPOINT_RETURN"
    model_battery = spec.energy.battery_wh
    usable = model_battery * (1.0 - spec.energy.min_reserve_pct / 100.0)
    best: list[tuple[float, float, tuple[str, ...]]] = []

    def exposure_of(used: dict[frozenset[str], int], expo: ExposureSpec) -> float:
        total = 0.0
        for key, count in used.items():
            e = edges[key]
            lo, hi = expo.band_deg
            if lo <= e.surface_slope_deg < hi or (expo.upper_inclusive and e.surface_slope_deg == hi):
                total += e.length_m * (1 if expo.counting == "UNIQUE_UNDIRECTED_EDGE_DISTANCE" else count)
        return total

    def rec(
        node: str, path: list[str], used: dict[frozenset[str], int], dist: float, energy: float, done: frozenset[str]
    ) -> None:
        if spec.max_distance_m is not None and dist > spec.max_distance_m + 1e-9:
            return
        if energy > usable + 1e-9:
            return
        if node == start and len(path) > 1 and len(done) == len(tasks):
            if not need_exposure or all(exposure_of(used, x) >= x.minimum_distance_m - 1e-9 for x in spec.exposures):
                best.append((round(dist, 9), round(energy, 9), tuple(path)))
        for nbr in sorted(adj[node]):
            key = frozenset((node, nbr))
            if used.get(key, 0) >= spec.max_undirected_edge_traversals:
                continue
            newly = {t for t, ts in tasks.items() if ts.location.node_id == nbr and t not in done}
            used[key] = used.get(key, 0) + 1
            rec(
                nbr,
                [*path, nbr],
                used,
                dist + edges[key].length_m,
                energy + (edges[key].mock_energy_wh or 0.0) + sum(tasks[t].incremental_energy_wh or 0.0 for t in newly),
                done | newly,
            )
            used[key] -= 1
            if used[key] == 0:
                del used[key]

    init_done = frozenset(t for t, ts in tasks.items() if ts.location.node_id == start)
    rec(start, [start], {}, 0.0, sum(tasks[t].incremental_energy_wh or 0.0 for t in init_done), init_done)
    if not best:
        return None
    if spec.strategy == "MINIMUM_FEASIBLE_ROUTE":
        return min(best, key=lambda b: (b[1], b[0], b[2]))
    return min(best, key=lambda b: (b[0], b[1], b[2]))


# ----------------------------------------------------------------------------------------------- raster builders
def make_grid(
    slope: np.ndarray,
    *,
    valid: np.ndarray | None = None,
    land: np.ndarray | None = None,
    elevation: np.ndarray | None = None,
    cell_size_m: float = 60.0,
    origin_x_m: float = 494240.0,
    origin_y_m: float = 3900000.0,
) -> GridArrays:
    shape = slope.shape
    ok = np.ones(shape, dtype=bool) if valid is None else valid
    return GridArrays(
        elevation_m=np.zeros(shape) if elevation is None else elevation.astype(np.float64),
        valid=ok,
        land=np.ones(shape, dtype=bool) if land is None else land,
        slope_deg=np.where(ok, slope, 0.0).astype(np.float64),
        cell_size_m=cell_size_m,
        origin_x_m=origin_x_m,
        origin_y_m=origin_y_m,
    )


def grid_spec_of(grid: GridArrays) -> GridSpec:
    return GridSpec(
        analysis_grid_sha256="0" * 64,
        crs_wkt="TEST",
        cell_size_m=grid.cell_size_m,
        width=grid.width,
        height=grid.height,
    )


def wp(grid: GridArrays, row: int, col: int) -> Waypoint:
    x, y = grid.center_xy(row, col)
    return Waypoint(node_id=raster_node_id(row, col), x_m=x, y_m=y)


def raster_constraints(
    grid: GridArrays,
    *,
    start: tuple[int, int],
    tasks: Sequence[tuple[str, tuple[int, int]]],
    exposures: Sequence[ExposureSpec] = (),
    strategy: RouteStrategy = "EXPOSURE_COVERAGE",
    cap: float = 18.0,
    rover_obj: RoverProfile | None = None,
    max_distance_m: float | None = 8000.0,
    dilation_m: float = 0.0,
    blocked: Sequence[str] = (),
    energy_model: EnergyModel | None | str = "rover",
    battery_wh: float | None = None,
    task_tolerance_m: float | None = None,
    solver: SolverConfig | None = None,
) -> tuple[ConstraintsArtifact, str]:
    rv = rover_obj or rover()
    model = rv.energy_model if energy_model == "rover" else energy_model
    assert model is None or isinstance(model, EnergyModel)
    art = ConstraintsArtifact(
        artifact_kind="RASTER_ROUTE_TEST",
        mode="synthetic",
        resource_provider="PHYSICAL_EARTH_MODEL",
        mission_revision_id=uuid.UUID(int=3),
        mission_content_sha256="a" * 64,
        rover_revision_id=uuid.UUID(int=4),
        rover_content_sha256="b" * 64,
        candidate_window_id="grid-test",
        test_revision=1,
        strategy=strategy,
        grid=grid_spec_of(grid),
        graph=None,
        start=wp(grid, *start),
        return_required=True,
        tasks=[
            TaskSpec(
                task_id=tid,
                requirement_ids=["R-TASKS"],
                kind="SAMPLING",
                location=wp(grid, *rc),
                tolerance_m=grid.cell_size_m if task_tolerance_m is None else task_tolerance_m,
                dwell_s=60.0,
                incremental_energy_wh=None if model is None else model.science_task_wh,
                required_capability=None,
                evidence_origin="SYNTHETIC_FIXTURE",
            )
            for tid, rc in tasks
        ],
        surface_slope_cap_deg=cap,
        exposures=list(exposures),
        max_distance_m=max_distance_m,
        footprint_dilation_m=dilation_m,
        blocked_edge_ids=list(blocked),
        energy=EnergySpec(
            model=model,
            battery_wh=rv.battery_wh if battery_wh is None else battery_wh,
            min_reserve_pct=rv.min_reserve_pct,
            rover_mass_kg=rv.mass_kg,
            nominal_speed_mps=rv.nominal_speed_mps,
        ),
        solver=solver or SolverConfig(max_expansions=200_000, max_seconds=30, max_labels_per_node=32, seed=0),
    )
    return art, canonical_sha256(art)


def band_spec(
    lo: float = 12.0,
    hi: float = 18.0,
    minimum: float = 100.0,
    *,
    inclusive: bool = True,
    rid: str = "R-EXPOSURE",
    counting: str = "UNIQUE_UNDIRECTED_EDGE_DISTANCE",
) -> ExposureSpec:
    return ExposureSpec(
        requirement_id=rid,
        metric_id="surface_slope_deg",
        band_deg=(lo, hi),
        upper_inclusive=inclusive,
        minimum_distance_m=minimum,
        counting=counting,  # type: ignore[arg-type]
    )


def ramp_grid(height: int = 24, width: int = 24) -> GridArrays:
    """Flat 3 deg terrain with a 15 deg ramp band (columns 14..17) running full height: a feasible exposure target."""
    slope = np.full((height, width), 3.0)
    slope[:, 14:18] = 15.0
    return make_grid(slope)


def test_support_builds_canonical_artifacts() -> None:
    payload = graph_design()
    assert payload.constraints.graph == canonical_graph_spec()
    assert list(itertools.islice(payload.constraints.exposures, 1))[0].requirement_id == "R-EXPOSURE"
