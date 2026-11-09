"""INDEPENDENT route verifier (08 section 4.11, architecture 12 section 7).

Independence rules enforced by ``tests/unit/science/test_verifier_independence.py``:

* this module imports no solver object: not ``search``, ``grid_graph``, ``fixture_graph``, ``supercover``,
  ``certificate`` or ``waypoints``;
* the only input is the immutable ``ConstraintsArtifact``, the raw analysis-grid arrays and the ROUTE's
  ``node_sequence`` - ``solver_claimed`` and ``task_events`` are ignored;
* cell intersections are computed by **slab clipping** of the segment against every candidate cell (a different
  algorithm than the solver's DDA), masks (including the footprint dilation) are rebuilt locally;
* distance, duration, energy, unique/traversed exposure, task completion, closure and traversal counts are all
  recomputed from the node sequence.

Only low-level, stateless primitives are shared with the solver: the band predicate and exposure accumulator
(``exposure``), the energy formula (``constraints``), the tolerance constants and id conventions (package root).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef, RuntimeMode, ScienceIssue, SearchStatus
from analogforge.ports.domain_models import MeasuredMetric
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    BenchmarkRow,
    ConstraintsArtifact,
    RouteArtifact,
    RouteViolation,
    TaskSpec,
    TelemetryArtifact,
    VerifyRoutePayload,
)
from analogforge.science.routing import (
    CONSTRAINT_INPUT_HASH,
    CONSTRAINT_TERRAIN_MASK,
    EPS_LEN_M,
    EPS_VALUE,
    GridArrays,
    RouteInputError,
    parse_raster_node_id,
    undirected_edge_id,
)
from analogforge.science.routing.constraints import (
    make_energy_provider,
    usable_wh,
    validate_constraints,
    waypoint_xy,
)
from analogforge.science.routing.exposure import accumulate_exposure, slope_in_band
from analogforge.science.routing.telemetry import TelemetryRow, build_telemetry

CONSTRAINT_START: Final = "C-START"
_METHOD: Final = "route-verifier-v1"
_SLOPE_TOL: Final = 1e-9


@dataclass(frozen=True)
class VerifyOutput:
    payload: VerifyRoutePayload
    telemetry: TelemetryArtifact | None
    issues: list[ScienceIssue]
    route_sha256: str


# ----------------------------------------------------------------------------------------------- slab clipping
def slab_cells(x0_m: float, y0_m: float, x1_m: float, y1_m: float, grid: GridArrays) -> list[tuple[int, int, float]]:
    """Cells whose CLOSED square intersects the segment, with the intersection length in metres.

    Different algorithm than the solver's DDA: for every cell of the segment's bounding box the segment parameter
    interval inside the cell is obtained by clipping against the two slabs (x and y).  Cells touched only at a corner
    or edge are returned with length 0, i.e. the same "supercover" set as the DDA.
    """
    cs = grid.cell_size_m
    u0 = (x0_m - grid.origin_x_m) / cs
    v0 = (grid.origin_y_m - y0_m) / cs
    u1 = (x1_m - grid.origin_x_m) / cs
    v1 = (grid.origin_y_m - y1_m) / cs
    du, dv = u1 - u0, v1 - v0
    length_m = math.hypot(du, dv) * cs
    col_lo, col_hi = math.floor(min(u0, u1)) - 1, math.floor(max(u0, u1)) + 1
    row_lo, row_hi = math.floor(min(v0, v1)) - 1, math.floor(max(v0, v1)) + 1
    eps = 1e-12
    hits: list[tuple[int, int, float]] = []
    for row in range(row_lo, row_hi + 1):
        for col in range(col_lo, col_hi + 1):
            t_in, t_out = 0.0, 1.0
            empty = False
            for p0, d, lo in ((u0, du, float(col)), (v0, dv, float(row))):
                hi = lo + 1.0
                if d == 0.0:
                    if p0 < lo - eps or p0 > hi + eps:
                        empty = True
                        break
                else:
                    ta, tb = (lo - p0) / d, (hi - p0) / d
                    if ta > tb:
                        ta, tb = tb, ta
                    t_in, t_out = max(t_in, ta), min(t_out, tb)
            if empty or t_in > t_out + eps:
                continue
            hits.append((row, col, max(0.0, t_out - t_in) * length_m))
    return hits


def unsafe_cells(grid: GridArrays, dilation_m: float) -> np.ndarray:
    """Cells a route may not intersect: invalid/water cells plus their dilation by the rover footprint radius.

    Rebuilt here with explicit offset shifts (the solver uses a distance transform) so the two implementations
    cross-check each other.
    """
    bad = ~(grid.valid & grid.land)
    unsafe = bad.copy()
    if dilation_m > 0.0:
        reach = int(math.ceil(dilation_m / grid.cell_size_m))
        height, width = bad.shape
        for d_row in range(-reach, reach + 1):
            for d_col in range(-reach, reach + 1):
                if (d_row or d_col) and math.hypot(d_row, d_col) * grid.cell_size_m <= dilation_m + _SLOPE_TOL:
                    src_rows = slice(max(0, -d_row), min(height, height - d_row))
                    src_cols = slice(max(0, -d_col), min(width, width - d_col))
                    dst_rows = slice(max(0, d_row), min(height, height + d_row))
                    dst_cols = slice(max(0, d_col), min(width, width + d_col))
                    unsafe[dst_rows, dst_cols] |= bad[src_rows, src_cols]
    return np.asarray(unsafe, dtype=np.bool_)


# ----------------------------------------------------------------------------------------------- recomputation
@dataclass
class _Step:
    index: int  # route index of the arrival node
    edge_id: str
    d_xy_m: float
    dz_m: float
    hazard_slope_deg: float | None
    band_len_m: list[float]
    mock_wh: float | None


@dataclass
class _Findings:
    violations: list[RouteViolation] = field(default_factory=list)
    discontinuities: int = 0
    terrain_hits: int = 0
    max_slope_deg: float | None = None


def _violation(
    code: str,
    constraint_id: str,
    message: str,
    *,
    requirement_id: str | None = None,
    observed: float | None = None,
    threshold: float | None = None,
    unit: str | None = None,
    segment: int | None = None,
) -> RouteViolation:
    return RouteViolation.model_validate(
        {
            "code": code,
            "requirement_id": requirement_id,
            "constraint_id": constraint_id,
            "observed": observed,
            "threshold": threshold,
            "unit": unit,
            "segment_from_index": None if segment is None else segment - 1,
            "segment_to_index": segment,
            "message": message,
        }
    )


def _metric(
    metric_id: str, value: float | None, unit: str, kind: str, method: str, note: str, support: float | None
) -> MeasuredMetric:
    return MeasuredMetric.model_validate(
        {
            "metric_id": metric_id,
            "value": value,
            "unit": unit,
            "support_scale_m": support,
            "quantity_kind": kind,
            "method_id": method,
            "valid_fraction": 1.0,
            "uncertainty_note": note,
        }
    )


def _row(
    constraint_id: str,
    rule: str,
    measured: float | None,
    threshold: float | None,
    unit: str | None,
    kind: str,
    requirement_id: str | None = None,
    *,
    force_status: str | None = None,
) -> BenchmarkRow:
    """``kind`` is GTE (measured >= threshold passes) or LTE (measured <= threshold passes)."""
    if measured is None or threshold is None:
        margin = None
        status = force_status or "INCONCLUSIVE"
    else:
        margin = measured - threshold if kind == "GTE" else threshold - measured
        status = force_status or ("PASS" if margin >= -EPS_VALUE else "FAIL")
    return BenchmarkRow.model_validate(
        {
            "constraint_id": constraint_id,
            "requirement_id": requirement_id,
            "rule": rule,
            "measured": measured,
            "threshold": threshold,
            "unit": unit,
            "margin": margin,
            "status": status,
        }
    )


def verify_route(
    constraints: ConstraintsArtifact,
    constraints_sha256_claimed: str,
    route: RouteArtifact,
    route_sha256_claimed: str,
    search_status: SearchStatus,
    *,
    grid: GridArrays | None = None,
    mode: RuntimeMode,
    verification_evidence_key: str = "verification",
    telemetry_artifact_key: str | None = "telemetry",
    rover_capabilities: Collection[str] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    to_lonlat: Callable[[float, float], tuple[float, float]] | None = None,
) -> VerifyOutput:
    """Recompute everything from ``route.node_sequence`` and decide PASS / FAIL / INCONCLUSIVE."""
    cancel = check_cancelled if check_cancelled is not None else (lambda: None)
    validate_constraints(constraints, mode=mode)
    evidence = EvidenceRef(local_key=verification_evidence_key)
    actual_constraints_hash = canonical_sha256(constraints)
    actual_route_hash = canonical_sha256(route)

    stale: list[str] = []
    if actual_constraints_hash != constraints_sha256_claimed:
        stale.append("constraints_sha256 does not match the canonical hash of the constraints artifact")
    if route.constraints_sha256 != actual_constraints_hash:
        stale.append("the route was produced for a different constraints artifact")
    if actual_route_hash != route_sha256_claimed:
        stale.append("route_sha256 does not match the canonical hash of the route artifact")
    if stale:
        message = "; ".join(stale)
        violation = _violation("STALE_INPUT_HASH", CONSTRAINT_INPUT_HASH, message)
        payload = VerifyRoutePayload(
            outcome="INCONCLUSIVE",
            failure_category="SYSTEM",
            search_status=search_status,
            verified_route_sha256=None,
            metrics=[],
            violations=[violation],
            benchmark_rows=[
                _row(CONSTRAINT_INPUT_HASH, "inputs must match their frozen hashes", None, None, None, "LTE")
            ],
            telemetry_artifact_key=None,
            verification_evidence=evidence,
            limitations=[message],
        )
        issue = ScienceIssue(code="STALE_INPUT_HASH", message=message, scope="VERIFY_ROUTE")
        return VerifyOutput(payload, None, [issue], actual_route_hash)

    provider = make_energy_provider(constraints)
    is_graph = constraints.artifact_kind == "SYNTHETIC_GRAPH_REGRESSION"
    cap = constraints.surface_slope_cap_deg
    sequence = route.node_sequence
    blocked = frozenset(constraints.blocked_edge_ids)

    # ---- world lookup (independent of the solver's graph objects)
    graph_edges: dict[str, tuple[float, float, float | None]] = {}
    unsafe: np.ndarray | None = None
    if is_graph:
        assert constraints.graph is not None
        for edge in constraints.graph.edges:
            graph_edges[undirected_edge_id(edge.a, edge.b)] = (
                edge.length_m,
                edge.surface_slope_deg,
                edge.mock_energy_wh,
            )
        known_nodes = set(constraints.graph.nodes)
    else:
        if grid is None or constraints.grid is None:
            raise RouteInputError(
                "raster verification needs the analysis grid arrays", detail_code="ANALYSIS_GRID_MISSING"
            )
        grid_spec = constraints.grid
        if (grid.width, grid.height) != (grid_spec.width, grid_spec.height) or abs(
            grid.cell_size_m - grid_spec.cell_size_m
        ) > 1e-9:
            raise RouteInputError("analysis grid arrays do not match the GridSpec", detail_code="GRID_SPEC_MISMATCH")
        unsafe = unsafe_cells(grid, constraints.footprint_dilation_m)
        known_nodes = set()

    findings = _Findings()
    steps: list[_Step] = []
    cell_slope = np.where(grid.valid, grid.slope_deg, np.nan) if grid is not None else None

    def node_xy(node_id: str) -> tuple[float, float] | None:
        if grid is None:
            return None
        parsed = parse_raster_node_id(node_id)
        if parsed is None or not grid.contains(*parsed):
            return None
        return grid.center_xy(*parsed)

    for index in range(1, len(sequence)):
        if index % 64 == 0:
            cancel()
        a, b = sequence[index - 1], sequence[index]
        eid = undirected_edge_id(a, b)
        if is_graph:
            if a not in known_nodes or b not in known_nodes or eid not in graph_edges:
                findings.discontinuities += 1
                findings.violations.append(
                    _violation(
                        "DISCONTINUOUS_ROUTE",
                        catalog.CONSTRAINT_CONTINUITY,
                        f"{a} -> {b} is not an edge of the graph",
                        segment=index,
                    )
                )
                continue
            length_m, slope_deg, mock_wh = graph_edges[eid]
            if eid in blocked:
                findings.terrain_hits += 1
                findings.violations.append(
                    _violation(
                        "FORBIDDEN_INTERSECTION", CONSTRAINT_TERRAIN_MASK, f"edge {eid} is blocked", segment=index
                    )
                )
            if slope_deg > cap + _SLOPE_TOL:
                findings.violations.append(
                    _violation(
                        "MAX_SLOPE_EXCEEDED",
                        catalog.CONSTRAINT_SLOPE_CAP,
                        f"edge {eid} slope {slope_deg:g} deg exceeds cap {cap:g} deg",
                        observed=slope_deg,
                        threshold=cap,
                        unit="deg",
                        segment=index,
                    )
                )
            findings.max_slope_deg = (
                slope_deg if findings.max_slope_deg is None else max(findings.max_slope_deg, slope_deg)
            )
            band = [
                length_m if slope_in_band(slope_deg, s.band_deg, s.upper_inclusive) else 0.0
                for s in constraints.exposures
            ]
            steps.append(_Step(index, eid, length_m, 0.0, slope_deg, band, mock_wh))
            continue

        assert grid is not None and unsafe is not None and cell_slope is not None
        pa, pb = parse_raster_node_id(a), parse_raster_node_id(b)
        if (
            pa is None
            or pb is None
            or not grid.contains(*pa)
            or not grid.contains(*pb)
            or max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1])) != 1
        ):
            findings.discontinuities += 1
            findings.violations.append(
                _violation(
                    "DISCONTINUOUS_ROUTE",
                    catalog.CONSTRAINT_CONTINUITY,
                    f"{a} -> {b} is not an 8-neighbour step inside the grid",
                    segment=index,
                )
            )
            continue
        (x0, y0), (x1, y1) = grid.center_xy(*pa), grid.center_xy(*pb)
        cells = slab_cells(x0, y0, x1, y1, grid)
        unknown_cell = False
        forbidden_cell = eid in blocked
        hazard: float | None = None
        positive: list[tuple[float, float]] = []
        steep: tuple[float, int, int] | None = None
        for row, col, length in cells:
            if not grid.contains(row, col) or not grid.valid[row, col]:
                unknown_cell = True
                continue
            if unsafe[row, col]:
                forbidden_cell = True
                continue
            if length > EPS_LEN_M:
                s = float(cell_slope[row, col])
                positive.append((s, length))
                hazard = s if hazard is None else max(hazard, s)
                if s > cap + _SLOPE_TOL and (steep is None or s > steep[0]):
                    steep = (s, row, col)
        if unknown_cell:
            findings.terrain_hits += 1
            findings.violations.append(
                _violation(
                    "UNKNOWN_TERRAIN",
                    CONSTRAINT_TERRAIN_MASK,
                    f"step {a} -> {b} intersects an invalid/unknown cell",
                    segment=index,
                )
            )
        if forbidden_cell:
            findings.terrain_hits += 1
            findings.violations.append(
                _violation(
                    "FORBIDDEN_INTERSECTION",
                    CONSTRAINT_TERRAIN_MASK,
                    f"step {a} -> {b} intersects a water/forbidden/dilated or blocked cell",
                    segment=index,
                )
            )
        if steep is not None:
            findings.violations.append(
                _violation(
                    "MAX_SLOPE_EXCEEDED",
                    catalog.CONSTRAINT_SLOPE_CAP,
                    f"step {a} -> {b} crosses a {steep[0]:.3f} deg cell > cap {cap:g} deg",
                    observed=steep[0],
                    threshold=cap,
                    unit="deg",
                    segment=index,
                )
            )
        if hazard is not None:
            findings.max_slope_deg = hazard if findings.max_slope_deg is None else max(findings.max_slope_deg, hazard)
        band = [
            sum(length for s, length in positive if slope_in_band(s, e.band_deg, e.upper_inclusive))
            for e in constraints.exposures
        ]
        d_xy = math.hypot(x1 - x0, y1 - y0)
        dz = float(grid.elevation_m[pb]) - float(grid.elevation_m[pa])
        steps.append(_Step(index, eid, d_xy, dz, hazard, band, None))

    # ---- tasks, start and closure
    def at_location(node_id: str, wp_node: str | None, wp_xy: tuple[float, float] | None, tol: float) -> float | None:
        """Distance (m) from ``node_id`` to a waypoint if within tolerance, else None."""
        if is_graph:
            return 0.0 if wp_node is not None and node_id == wp_node else None
        xy = node_xy(node_id)
        target = wp_xy
        if target is None and wp_node is not None:
            parsed = parse_raster_node_id(wp_node)
            if parsed is not None and grid is not None:
                target = grid.center_xy(*parsed)
        if xy is None or target is None:
            return None
        d = math.hypot(xy[0] - target[0], xy[1] - target[1])
        return d if d <= tol + EPS_VALUE else None

    start_xy = waypoint_xy(constraints.start)
    closure_tol = 0.0 if is_graph else (0.5 * grid.cell_size_m if grid is not None else 0.0)
    if is_graph and constraints.start.node_id is None:
        raise RouteInputError("graph constraints need a start node id", detail_code="WAYPOINT_UNRESOLVED")
    if not is_graph and start_xy is None and constraints.start.node_id is None:
        raise RouteInputError("raster constraints need a start location", detail_code="WAYPOINT_UNRESOLVED")

    if at_location(sequence[0], constraints.start.node_id, start_xy, closure_tol) is None:
        findings.violations.append(
            _violation(
                "WAYPOINT_MISSED",
                CONSTRAINT_START,
                f"route starts at {sequence[0]}, not at the declared start",
                unit=None,
                segment=None,
            )
        )
    closure_distance: float | None = None
    if constraints.return_required:
        last = sequence[-1]
        if is_graph:
            closure_distance = 0.0 if last == constraints.start.node_id else math.inf
        else:
            xy_last = node_xy(last)
            tgt = start_xy
            if tgt is None and constraints.start.node_id is not None and grid is not None:
                parsed_start = parse_raster_node_id(constraints.start.node_id)
                tgt = grid.center_xy(*parsed_start) if parsed_start is not None else None
            closure_distance = (
                math.inf if xy_last is None or tgt is None else math.hypot(xy_last[0] - tgt[0], xy_last[1] - tgt[1])
            )
        if closure_distance > closure_tol + EPS_VALUE:
            findings.violations.append(
                _violation(
                    "RETURN_NOT_COMPLETED",
                    catalog.CONSTRAINT_RETURN,
                    f"route ends at {sequence[-1]}, not back at the start",
                    observed=None if math.isinf(closure_distance) else closure_distance,
                    threshold=closure_tol,
                    unit="m",
                )
            )

    first_arrival: dict[str, int] = {}
    for task in constraints.tasks:
        if not is_graph and waypoint_xy(task.location) is None and task.location.node_id is None:
            raise RouteInputError(f"task {task.task_id} has no projected location", detail_code="WAYPOINT_UNRESOLVED")
        txy = waypoint_xy(task.location)
        for i, node in enumerate(sequence):
            if at_location(node, task.location.node_id, txy, task.tolerance_m) is not None:
                first_arrival[task.task_id] = i
                break
        if task.task_id not in first_arrival:
            findings.violations.append(
                _violation(
                    "WAYPOINT_MISSED",
                    catalog.constraint_task(task.task_id),
                    f"task {task.task_id} was never reached within {task.tolerance_m:g} m",
                    observed=0.0,
                    threshold=1.0,
                    unit="tasks",
                )
            )
        elif (
            rover_capabilities is not None
            and task.required_capability is not None
            and task.required_capability not in rover_capabilities
        ):
            findings.violations.append(
                _violation(
                    "TASK_CAPABILITY_MISSING",
                    catalog.constraint_task(task.task_id),
                    f"rover lacks capability {task.required_capability}",
                    observed=0.0,
                    threshold=1.0,
                    unit="tasks",
                )
            )

    # ---- cumulative resources along the route
    cancel()
    n = len(sequence)
    cum_dist = [0.0] * n
    cum_time = [0.0] * n
    cum_nom = [0.0] * n
    cum_cons = [0.0] * n
    step_by_index = {s.index: s for s in steps}
    tasks_by_index: dict[int, list[TaskSpec]] = {}
    for task in constraints.tasks:
        if task.task_id in first_arrival:
            tasks_by_index.setdefault(first_arrival[task.task_id], []).append(task)
    energy_ok = provider.evaluable
    for i in range(n):
        if i > 0:
            cum_dist[i], cum_time[i], cum_nom[i], cum_cons[i] = (
                cum_dist[i - 1],
                cum_time[i - 1],
                cum_nom[i - 1],
                cum_cons[i - 1],
            )
            step = step_by_index.get(i)
            if step is not None:
                res = provider.edge(step.d_xy_m, step.dz_m, step.mock_wh)
                cum_dist[i] += step.d_xy_m
                cum_time[i] += res.duration_s
                cum_nom[i] += res.nominal_wh
                cum_cons[i] += res.conservative_wh
        for task in tasks_by_index.get(i, ()):
            tres = provider.task(task)
            cum_time[i] += tres.duration_s
            cum_nom[i] += tres.nominal_wh
            cum_cons[i] += tres.conservative_wh
    total_dist, total_time = cum_dist[-1], cum_time[-1]
    total_nom, total_cons = cum_nom[-1], cum_cons[-1]

    # ---- traversal counts and exposure
    counts: dict[str, int] = {}
    for step in steps:
        counts[step.edge_id] = counts.get(step.edge_id, 0) + 1
    max_count = max(counts.values(), default=0)
    if max_count > constraints.max_undirected_edge_traversals:
        worst = sorted(e for e, c in counts.items() if c == max_count)[0]
        findings.violations.append(
            _violation(
                "EDGE_TRAVERSAL_LIMIT_EXCEEDED",
                catalog.CONSTRAINT_EDGE_TRAVERSALS,
                f"edge {worst} traversed {max_count} times",
                observed=float(max_count),
                threshold=float(constraints.max_undirected_edge_traversals),
                unit="traversals",
            )
        )
    totals = accumulate_exposure([(s.edge_id, s.band_len_m) for s in steps], constraints.exposures)
    for spec, tot in zip(constraints.exposures, totals, strict=True):
        counted = tot.counted_m(spec)
        if counted < spec.minimum_distance_m - EPS_VALUE:
            findings.violations.append(
                _violation(
                    "EXPOSURE_SHORTFALL",
                    catalog.constraint_exposure(spec.requirement_id),
                    f"{counted:g} m {'unique' if spec.counting.startswith('UNIQUE') else 'traversed'} exposure in "
                    f"{spec.band_deg} deg < required {spec.minimum_distance_m:g} m",
                    requirement_id=spec.requirement_id,
                    observed=counted,
                    threshold=spec.minimum_distance_m,
                    unit="m",
                )
            )

    # ---- distance / duration / energy
    if constraints.max_distance_m is not None and total_dist > constraints.max_distance_m + EPS_VALUE:
        findings.violations.append(
            _violation(
                "MAX_DISTANCE_EXCEEDED",
                catalog.CONSTRAINT_MAX_DISTANCE,
                f"route distance {total_dist:g} m > {constraints.max_distance_m:g} m",
                observed=total_dist,
                threshold=constraints.max_distance_m,
                unit="m",
            )
        )
    if constraints.max_duration_s is not None and total_time > constraints.max_duration_s + EPS_VALUE:
        findings.violations.append(
            _violation(
                "MAX_DURATION_EXCEEDED",
                catalog.CONSTRAINT_MAX_DURATION,
                f"route duration {total_time:g} s > {constraints.max_duration_s:g} s",
                observed=total_time,
                threshold=constraints.max_duration_s,
                unit="s",
            )
        )
    reserve: float | None = None
    usable = usable_wh(provider)
    if energy_ok:
        reserve = 100.0 * (provider.battery_wh - total_cons) / provider.battery_wh
        if total_cons > usable + EPS_VALUE:
            findings.violations.append(
                _violation(
                    "ENERGY_RESERVE_SHORTFALL",
                    catalog.CONSTRAINT_ENERGY_RESERVE,
                    f"reserve {reserve:.6f}% < required {provider.min_reserve_pct:g}%",
                    observed=reserve,
                    threshold=provider.min_reserve_pct,
                    unit="percent",
                )
            )

    # ---- benchmark rows
    rows: list[BenchmarkRow] = [
        _row(
            catalog.CONSTRAINT_CONTINUITY,
            "every step is an allowed adjacency",
            float(findings.discontinuities),
            0.0,
            "steps",
            "LTE",
        ),
        _row(
            catalog.CONSTRAINT_SLOPE_CAP,
            f"max hazard surface slope <= {cap:g} deg",
            findings.max_slope_deg,
            cap,
            "deg",
            "LTE",
        ),
        _row(
            CONSTRAINT_TERRAIN_MASK,
            "no unknown, water, forbidden or dilated cell is intersected",
            float(findings.terrain_hits),
            0.0,
            "steps",
            "LTE",
        ),
        _row(
            catalog.CONSTRAINT_EDGE_TRAVERSALS,
            f"each undirected edge traversed <= {constraints.max_undirected_edge_traversals} times",
            float(max_count),
            float(constraints.max_undirected_edge_traversals),
            "traversals",
            "LTE",
        ),
    ]
    if constraints.return_required:
        rows.append(
            _row(
                catalog.CONSTRAINT_RETURN,
                "route returns to the start",
                closure_distance if closure_distance is not None and not math.isinf(closure_distance) else None,
                closure_tol,
                "m",
                "LTE",
                force_status=None if closure_distance is not None and not math.isinf(closure_distance) else "FAIL",
            )
        )
    for task in constraints.tasks:
        done = 1.0 if task.task_id in first_arrival else 0.0
        rows.append(
            _row(
                catalog.constraint_task(task.task_id),
                f"task {task.task_id} reached and completed",
                done,
                1.0,
                "tasks",
                "GTE",
                force_status=None if done else "FAIL",
            )
        )
    for spec, tot in zip(constraints.exposures, totals, strict=True):
        counted = tot.counted_m(spec)
        word = "unique" if spec.counting.startswith("UNIQUE") else "traversed"
        rows.append(
            _row(
                catalog.constraint_exposure(spec.requirement_id),
                f">= {spec.minimum_distance_m:g} m {word} in "
                f"[{spec.band_deg[0]:g},{spec.band_deg[1]:g}{']' if spec.upper_inclusive else ')'} deg",
                counted,
                spec.minimum_distance_m,
                "m",
                "GTE",
                spec.requirement_id,
            )
        )
    if constraints.max_distance_m is not None:
        rows.append(
            _row(
                catalog.CONSTRAINT_MAX_DISTANCE,
                f"route distance <= {constraints.max_distance_m:g} m",
                total_dist,
                constraints.max_distance_m,
                "m",
                "LTE",
            )
        )
    if constraints.max_duration_s is not None:
        rows.append(
            _row(
                catalog.CONSTRAINT_MAX_DURATION,
                f"route duration <= {constraints.max_duration_s:g} s",
                total_time,
                constraints.max_duration_s,
                "s",
                "LTE",
            )
        )
    rows.append(
        _row(
            catalog.CONSTRAINT_ENERGY_RESERVE,
            f"reserve >= {provider.min_reserve_pct:g}% (conservative energy)",
            reserve,
            provider.min_reserve_pct,
            "percent",
            "GTE",
        )
    )
    rows.append(_start_row(findings))

    # ---- metrics
    support = None if grid is None else grid.cell_size_m
    energy_kind = provider.quantity_kind
    energy_method = provider.method_id
    metrics = [
        _metric(
            "route_distance_m",
            total_dist,
            "m",
            "DERIVED",
            _METHOD,
            "horizontal planimetric distance recomputed from node_sequence",
            support,
        ),
        _metric(
            "route_duration_s",
            total_time,
            "s",
            "DERIVED",
            _METHOD,
            "surface length / nominal speed plus task dwell",
            support,
        ),
        _metric(
            "max_surface_slope_deg",
            findings.max_slope_deg,
            "deg",
            "DERIVED",
            _METHOD,
            "max cell slope over positive-length intersections",
            support,
        ),
        _metric(
            "tasks_completed",
            float(len(first_arrival)),
            "count",
            "DERIVED",
            _METHOD,
            "tasks reached within tolerance",
            support,
        ),
    ]
    for spec, tot in zip(constraints.exposures, totals, strict=True):
        metrics.append(
            _metric(
                f"unique_exposure_m:{spec.requirement_id}",
                tot.unique_m,
                "m",
                "DERIVED",
                _METHOD,
                "unique undirected edge subsegment length in band",
                support,
            )
        )
        metrics.append(
            _metric(
                f"traversed_exposure_m:{spec.requirement_id}",
                tot.traversed_m,
                "m",
                "DERIVED",
                _METHOD,
                "every traversal counted",
                support,
            )
        )
    if energy_ok:
        note = (
            "ASSUMED energy model parameters; not calibrated" if energy_kind == "ASSUMED" else "calibrated energy model"
        )
        metrics.append(_metric("energy_nominal_wh", total_nom, "Wh", energy_kind, energy_method, note, support))
        metrics.append(_metric("energy_conservative_wh", total_cons, "Wh", energy_kind, energy_method, note, support))
        metrics.append(_metric("reserve_pct", reserve, "percent", energy_kind, energy_method, note, support))
    else:
        for metric_id, unit in (
            ("energy_nominal_wh", "Wh"),
            ("energy_conservative_wh", "Wh"),
            ("reserve_pct", "percent"),
        ):
            metrics.append(
                _metric(
                    metric_id,
                    None,
                    unit,
                    "ASSUMED",
                    energy_method,
                    "no energy model: energy is unknown, not zero",
                    support,
                )
            )

    # ---- telemetry
    tele_rows: list[TelemetryRow] = []
    for i, node in enumerate(sequence):
        step = step_by_index.get(i)
        xy = node_xy(node)
        lon = lat = None
        if to_lonlat is not None and xy is not None:
            lon, lat = to_lonlat(*xy)
        elevation = None
        parsed_node = parse_raster_node_id(node) if grid is not None else None
        if grid is not None and parsed_node is not None and grid.contains(*parsed_node):
            elevation = float(grid.elevation_m[parsed_node])
        tele_rows.append(
            TelemetryRow(
                node_id=node,
                cumulative_distance_m=cum_dist[i],
                elapsed_s=cum_time[i],
                lon=lon,
                lat=lat,
                elevation_m=elevation,
                segment_surface_slope_deg=None if step is None else step.hazard_slope_deg,
                cumulative_energy_conservative_wh=cum_cons[i] if energy_ok else None,
                in_band_requirement_ids=[]
                if step is None
                else [e.requirement_id for k, e in enumerate(constraints.exposures) if step.band_len_m[k] > EPS_LEN_M],
            )
        )
    telemetry = build_telemetry(
        tele_rows,
        route_sha256=actual_route_hash,
        constraints_sha256=actual_constraints_hash,
        battery_wh=provider.battery_wh,
    )

    # ---- outcome rule
    issues: list[ScienceIssue] = []
    limitations: list[str] = [
        "Modeled terrain-test verification on the stated discrete graph and source support; "
        "not a dynamics simulation or hardware certification."
    ]
    if findings.discontinuities:
        limitations.append("Route is discontinuous: totals cover only the continuous steps.")
    if not energy_ok:
        limitations.append("No energy model: energy reserve is unknown (ENERGY_UNCALIBRATED), not zero consumption.")
    if energy_ok and energy_kind == "ASSUMED":
        limitations.append("Energy model parameters are ASSUMED design defaults, not calibrated.")
    if constraints.resource_provider == "TEST_ONLY_MOCK_GRAPH":
        limitations.append("SYNTHETIC GRAPH REGRESSION: mock per-edge energies; not a realizable surface.")
    if findings.violations:
        outcome, category = "FAIL", "ROUTE"
        verified = None
    elif not energy_ok:
        outcome, category = "INCONCLUSIVE", "DATA"
        verified = None
        issues.append(
            ScienceIssue(
                code="ENERGY_UNCALIBRATED",
                message="Rover has no energy model; the energy reserve requirement cannot be evaluated.",
                affected_requirement_ids=[],
                scope="VERIFY_ROUTE",
            )
        )
    else:
        outcome, category = "PASS", None
        verified = actual_route_hash
    payload = VerifyRoutePayload.model_validate(
        {
            "outcome": outcome,
            "failure_category": category,
            "search_status": search_status,
            "verified_route_sha256": verified,
            "metrics": metrics,
            "violations": findings.violations,
            "benchmark_rows": rows,
            "telemetry_artifact_key": telemetry_artifact_key,
            "verification_evidence": evidence,
            "limitations": limitations,
        }
    )
    return VerifyOutput(payload, telemetry, issues, actual_route_hash)


def _start_row(findings: _Findings) -> BenchmarkRow:
    missed = any(v.constraint_id == CONSTRAINT_START for v in findings.violations)
    return _row(
        CONSTRAINT_START,
        "route starts at the declared start",
        0.0 if missed else 1.0,
        1.0,
        "starts",
        "GTE",
        force_status="FAIL" if missed else "PASS",
    )
