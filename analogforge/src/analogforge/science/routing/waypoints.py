"""``auto-waypoints-v1`` (architecture 40 section 6) and the ``DESIGN_BENCHMARK`` designer for raster candidates.

Normative rule, evaluated on the largest connected safe component of the traversal graph (valid, land, slope <= cap;
ties between equal-size components go to the smallest row-major first cell):

* ``S``  = component cell nearest the component's cell centroid (ties -> row-major);
* ``W1`` = among component cells at Euclidean distance in ``[0.15, 0.30] * window_edge`` from ``S`` the one with the
  greatest number of band-slope cells in its 5x5 neighbourhood (ties -> row-major);
* ``W2`` = same rule among cells at least ``0.10 * window_edge`` from ``W1`` (same annulus around ``S``).

Task tolerance is one cell, dwell ``design_defaults.task_dwell_s``, incremental energy ``energy_model.science_task_wh``.
Candidates that are themselves band-slope cells are excluded (see DECISIONS: a task placed inside the band would let
the minimum-distance ``WAYPOINT_RETURN`` loop earn exposure, contradicting the binding first-attempt property of 40 s4).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from scipy import ndimage

from analogforge.ports import catalog
from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import SolverConfig
from analogforge.ports.science_payloads import (
    ConstraintsArtifact,
    DesignBenchmarkInput,
    DesignBenchmarkPayload,
    EnergySpec,
    ExposureSpec,
    GridSpec,
    TaskSpec,
    Waypoint,
)
from analogforge.science.routing import GridArrays, RouteInputError
from analogforge.science.routing.constraints import (
    ROUTE_TASK_OBSERVABLE,
    RouteDesignDefaults,
    exposure_specs_from_requirements,
    finish_design_payload,
)
from analogforge.science.routing.exposure import slope_in_band
from analogforge.science.routing.fixture_graph import design_graph_benchmark
from analogforge.science.routing.grid_graph import RouteGraph, build_raster_graph, components

AUTO_WAYPOINTS_ID: Final = "auto-waypoints-v1"
SAMPLING_CAPABILITY: Final = "geological_sampling"
S_MIN_FRACTION: Final = 0.15
S_MAX_FRACTION: Final = 0.30
W2_MIN_FRACTION: Final = 0.10


@dataclass(frozen=True)
class AutoWaypoints:
    start: int
    w1: int
    w2: int
    component_size: int


def _band_count_5x5(grid: GridArrays, spec: ExposureSpec | None) -> np.ndarray:
    if spec is None:
        return np.zeros(grid.elevation_m.shape, dtype=np.int64)
    in_band = np.zeros(grid.elevation_m.shape, dtype=np.int64)
    rows, cols = np.nonzero(grid.valid)
    for r, c in zip(rows.tolist(), cols.tolist(), strict=True):
        if slope_in_band(float(grid.slope_deg[r, c]), spec.band_deg, spec.upper_inclusive):
            in_band[r, c] = 1
    return np.asarray(
        ndimage.convolve(in_band, np.ones((5, 5), dtype=np.int64), mode="constant", cval=0), dtype=np.int64
    )


def auto_waypoints_v1(
    graph: RouteGraph, grid: GridArrays, exposure: ExposureSpec | None, *, window_edge_m: float | None = None
) -> AutoWaypoints:
    """Choose ``S``, ``W1``, ``W2`` as graph node indices.  Raises ``WAYPOINT_UNRESOLVED`` if the rule has no answer."""
    comps = components(graph)
    if not comps:
        raise RouteInputError("no traversable cells: cannot place waypoints", detail_code="WAYPOINT_UNRESOLVED")
    comp = comps[0]
    edge_m = window_edge_m if window_edge_m is not None else max(grid.width, grid.height) * grid.cell_size_m
    cs = grid.cell_size_m
    cells = np.array([graph.cell(i) for i in comp], dtype=np.float64)
    centroid = cells.mean(axis=0)
    d_centroid = np.hypot(cells[:, 0] - centroid[0], cells[:, 1] - centroid[1])
    start_pos = min(range(len(comp)), key=lambda k: (float(d_centroid[k]), comp[k]))
    start = comp[start_pos]
    counts = _band_count_5x5(grid, exposure)

    def is_band(idx: int) -> bool:
        if exposure is None:
            return False
        r, c = graph.cell(idx)
        return slope_in_band(float(grid.slope_deg[r, c]), exposure.band_deg, exposure.upper_inclusive)

    def dist_m(a: int, b: int) -> float:
        ar, ac = graph.cell(a)
        br, bc = graph.cell(b)
        return math.hypot(ar - br, ac - bc) * cs

    def pick(candidates: Sequence[int]) -> int | None:
        best: tuple[int, int] | None = None
        for idx in candidates:
            r, c = graph.cell(idx)
            key = (-int(counts[r, c]), idx)
            if best is None or key < best:
                best = key
        return None if best is None else best[1]

    annulus = [
        i
        for i in comp
        if i != start
        and S_MIN_FRACTION * edge_m - 1e-9 <= dist_m(start, i) <= S_MAX_FRACTION * edge_m + 1e-9
        and not is_band(i)
    ]
    w1 = pick(annulus)
    if w1 is None:
        raise RouteInputError(
            "auto-waypoints-v1: no W1 candidate in the 0.15-0.30 window-edge annulus", detail_code="WAYPOINT_UNRESOLVED"
        )
    far_enough = [i for i in annulus if i != w1 and dist_m(w1, i) >= W2_MIN_FRACTION * edge_m - 1e-9]
    w2 = pick(far_enough)
    if w2 is None:
        raise RouteInputError(
            "auto-waypoints-v1: no W2 candidate at least 0.10 window-edge from W1", detail_code="WAYPOINT_UNRESOLVED"
        )
    return AutoWaypoints(start, w1, w2, len(comp))


def _waypoint(graph: RouteGraph, index: int) -> Waypoint:
    assert graph.node_xy is not None
    x, y = graph.node_xy[index]
    return Waypoint(node_id=graph.node_ids[index], x_m=x, y_m=y)


def design_raster_benchmark(
    inp: DesignBenchmarkInput,
    *,
    mode: RuntimeMode,
    grid: GridArrays | None,
    grid_spec: GridSpec | None,
    defaults: RouteDesignDefaults,
    constraints_artifact_key: str = "constraints",
    check_cancelled: Callable[[], None] | None = None,
) -> DesignBenchmarkPayload:
    """``DESIGN_BENCHMARK`` for a raster candidate: exposures, ``auto-waypoints-v1`` tasks, budgets and energy."""
    if grid is None or grid_spec is None:
        raise RouteInputError("DESIGN_BENCHMARK needs the candidate analysis grid", detail_code="ANALYSIS_GRID_MISSING")
    rover = inp.rover
    cap = rover.max_slope_deg
    exposures = exposure_specs_from_requirements(inp.mission.requirements, cap)
    graph = build_raster_graph(
        grid,
        slope_cap_deg=cap,
        exposures=exposures,
        dilation_m=defaults.footprint_dilation_m,
        blocked_edge_ids=inp.blocked_edge_ids,
        check_cancelled=check_cancelled,
    )
    picked = auto_waypoints_v1(graph, grid, exposures[0] if exposures else None)
    task_req_ids = [r.id for r in inp.mission.requirements if r.observable == ROUTE_TASK_OBSERVABLE]
    science_wh = rover.energy_model.science_task_wh if rover.energy_model is not None else None
    tasks = [
        TaskSpec(
            task_id=task_id,
            requirement_ids=task_req_ids,
            kind="SAMPLING",
            location=_waypoint(graph, node),
            tolerance_m=grid.cell_size_m,
            dwell_s=defaults.task_dwell_s,
            incremental_energy_wh=science_wh,
            required_capability=SAMPLING_CAPABILITY,
            evidence_origin="SYNTHETIC_FIXTURE" if mode == "synthetic" else "USER_DESIGNATED",
        )
        for task_id, node in (("W1", picked.w1), ("W2", picked.w2))
    ]
    limitations = [
        f"Waypoints placed by {AUTO_WAYPOINTS_ID} on the largest safe component ({picked.component_size} cells); "
        "sampling locations are designated, not evidence of material availability.",
        f"Terrain model at {grid.cell_size_m:g} m support; the route is a raster-feasibility result, "
        "not a proven physical corridor.",
        "Rover footprint, soil traction and obstacle clearance are not resolved by this model.",
    ]
    if rover.max_route_m is None:
        limitations.append(
            f"max_distance_m defaults to design_defaults.max_route_m = {defaults.max_route_m:g} m "
            "(rover declares none)."
        )
    if rover.energy_model is None:
        limitations.append("Rover has no energy model: energy-dependent checks are INCONCLUSIVE (ENERGY_UNCALIBRATED).")
    artifact = ConstraintsArtifact(
        artifact_kind="RASTER_ROUTE_TEST",
        mode=mode,
        resource_provider="PHYSICAL_EARTH_MODEL",
        mission_revision_id=inp.mission.id,
        mission_content_sha256=inp.mission.content_sha256,
        rover_revision_id=rover.id,
        rover_content_sha256=rover.content_sha256,
        candidate_window_id=inp.candidate.window_id,
        test_revision=inp.test_revision,
        strategy=inp.strategy,
        grid=grid_spec,
        graph=None,
        start=_waypoint(graph, picked.start),
        return_required=True,
        tasks=tasks,
        surface_slope_cap_deg=cap,
        exposures=exposures,
        max_distance_m=rover.max_route_m if rover.max_route_m is not None else defaults.max_route_m,
        max_duration_s=None,
        max_undirected_edge_traversals=catalog.BUDGETS["max_undirected_edge_traversals"],
        footprint_dilation_m=defaults.footprint_dilation_m,
        blocked_edge_ids=sorted(inp.blocked_edge_ids),
        energy=EnergySpec(
            model=rover.energy_model,
            battery_wh=rover.battery_wh,
            min_reserve_pct=rover.min_reserve_pct,
            rover_mass_kg=rover.mass_kg,
            nominal_speed_mps=rover.nominal_speed_mps,
        ),
        solver=SolverConfig(
            max_expansions=defaults.max_expansions,
            max_seconds=defaults.max_seconds,
            max_labels_per_node=defaults.max_labels_per_node,
            seed=defaults.seed,
        ),
        limitations=limitations,
    )
    return finish_design_payload(
        artifact, constraints_artifact_key=constraints_artifact_key, requirements=inp.mission.requirements
    )


def design_benchmark(
    inp: DesignBenchmarkInput,
    *,
    mode: RuntimeMode,
    grid: GridArrays | None = None,
    grid_spec: GridSpec | None = None,
    defaults: RouteDesignDefaults | None = None,
    constraints_artifact_key: str = "constraints",
    check_cancelled: Callable[[], None] | None = None,
) -> DesignBenchmarkPayload:
    """Dispatch ``DESIGN_BENCHMARK``: abstract graph scenario (synthetic only) or raster candidate."""
    used = defaults if defaults is not None else RouteDesignDefaults()
    if inp.graph_fixture_id is not None:
        return design_graph_benchmark(
            inp,
            mode=mode,
            defaults=used,
            constraints_artifact_key=constraints_artifact_key,
            check_cancelled=check_cancelled,
        )
    return design_raster_benchmark(
        inp,
        mode=mode,
        grid=grid,
        grid_spec=grid_spec,
        defaults=used,
        constraints_artifact_key=constraints_artifact_key,
        check_cancelled=check_cancelled,
    )
