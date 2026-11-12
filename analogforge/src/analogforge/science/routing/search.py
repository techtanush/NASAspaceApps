"""Bounded resource-constrained best-first label search (architecture 12 section 6, 08 section 4.10).

Pipeline: validate -> stale-hash check -> build graph -> resolve waypoints -> lossless certificate -> label search.

Label = (node, completed-task bitmask, per-requirement exposure saturated at its minimum, the set of covered in-band
edges while a UNIQUE requirement is unsaturated, edge traversal counts, conservative/nominal energy, time, distance,
predecessor).  Traversal counts are reconstructed from the predecessor chain on expansion (the limit is enforced
exactly per label); they are NOT part of dominance, see below.

Ordering is A* with a consistent admissible heuristic (shortest horizontal distance to finish tasks/return and the
remaining exposure deficit), key ``(f, g, secondary, node_sequence)``; with strictly positive edge lengths the first
popped solution is therefore the minimum-distance route, then minimum conservative energy, then lexicographically
smallest ``node_sequence`` (ranks are computed from plain string order of the node ids).  ``MINIMUM_FEASIBLE_ROUTE``
orders by conservative energy first instead.

Task semantics (shared with the verifier): a task is completed on arrival at ANY traversable node whose centre lies
within the task tolerance of the task location (``Problem.task_sets``); it is reachable iff one of them is in the start
component, the heuristics use the nearest such node, and the route reports the first arrival.

Pruning that is *lossless*: hard-constraint violations (traversal limit, max distance/duration/energy by admissible
bounds) and Pareto dominance between labels with the same (node, task set, saturation pattern): ``A`` dominates ``B``
if ``A`` has no more distance/energy/time, covers a superset of ``B``'s in-band edges (and at least ``B``'s TOTAL
traversed exposure).  Equal labels keep the lexicographically smaller ``node_sequence``.

Two dominance modes (``strict_dominance``):

* RELAXED (``max_undirected_edge_traversals >= 2`` and no TOTAL_TRAVERSED_DISTANCE requirement): dominance ignores the
  per-edge traversal counts: if ``A``'s continuation of ``B``'s suffix would traverse an edge a third time, the closed
  walk can be shortened by removing two copies of that edge (at least one copy remains because the count exceeded
  ``max >= 2``; the remaining multigraph keeps its Euler circuit, task visits and unique exposure), contradicting
  minimality of the distance; this argument is exact for distance/time bounds and for symmetric energies.  When the
  energy bound is active on a surface with elevation changes (asymmetric energies) dominance prunes are therefore
  counted as *lossy*.
* STRICT (``max_undirected_edge_traversals == 1`` or any TOTAL requirement): removing two copies is impossible
  (with a limit of 1 the second copy leaves zero edges, so the walk disconnects) or changes the counted exposure
  (TOTAL counting).  ``A`` then dominates ``B`` only if, in addition, ``A`` has used every edge no more often than
  ``B`` (pointwise), which makes every continuation of ``B`` valid from ``A``; labels that tie on all costs but
  differ in usage are both kept so the lexicographic tie-break stays exact.  No prune in this mode is lossy.

*Lossy*: the per-(node, task-set, exposure-level) label cap
``max_labels_per_node``; any lossy pruning is counted, flagged in ``approximation_flags`` and forbids
``EXHAUSTIVE_INFEASIBLE`` (an empty queue then maps to ``BUDGET_EXHAUSTED``).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Final

from analogforge.ports.common import RuntimeMode, ScienceIssue, SearchStatus
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    ConstraintsArtifact,
    GeoJSONLineString,
    RouteArtifact,
    SearchCounters,
    SearchRoutePayload,
    SolverClaimedTotals,
    TaskEvent,
    Waypoint,
)
from analogforge.science.routing import (
    EPS_VALUE,
    GridArrays,
    RouteInputError,
    parse_raster_node_id,
    raster_node_id,
)
from analogforge.science.routing.certificate import (
    Certificate,
    EdgeCosts,
    compute_certificate,
    evaluate_costs,
    remaining_bound_tables,
)
from analogforge.science.routing.constraints import (
    EnergyProvider,
    make_energy_provider,
    require_fresh_hash,
    usable_wh,
    validate_constraints,
    waypoint_xy,
)
from analogforge.science.routing.fixture_graph import build_abstract_graph
from analogforge.science.routing.grid_graph import RouteGraph, build_raster_graph

MAX_TASKS: Final = 16
_MICRO: Final = 1_000_000
_NANO: Final = 1_000_000_000
LABEL_CAP_FLAG: Final = (
    "LABEL_CAP_TRUNCATION: lossy pruning occurred; minimality and exhaustive-infeasibility claims are void."
)


# ----------------------------------------------------------------------------------------------- problem preparation
@dataclass(frozen=True, eq=False)
class Problem:
    """A constraints artifact lowered onto a graph: everything the certificate and the search need."""

    constraints: ConstraintsArtifact
    graph: RouteGraph
    provider: EnergyProvider
    costs: EdgeCosts
    start: int | None
    task_nodes: dict[str, int | None]  # nearest in-tolerance node (representative; ties by node id)
    task_sets: dict[str, frozenset[int]]  # ALL traversable nodes within the task tolerance (empty: unresolved)


def resolve_waypoint_set(
    graph: RouteGraph, grid: GridArrays | None, waypoint: Waypoint, tolerance_m: float
) -> list[tuple[float, str, int]]:
    """Every traversable node within ``tolerance_m`` of the waypoint, as ``(distance, id, index)``, nearest first."""
    if graph.kind == "ABSTRACT":
        idx = graph.index_of.get(waypoint.node_id) if waypoint.node_id is not None else None
        return [] if idx is None else [(0.0, graph.node_ids[idx], idx)]
    if grid is None:
        raise RouteInputError("raster waypoint resolution needs the analysis grid", detail_code="ANALYSIS_GRID_MISSING")
    xy = waypoint_xy(waypoint)
    if xy is None and waypoint.node_id is not None:
        parsed = parse_raster_node_id(waypoint.node_id)
        if parsed is not None:
            xy = grid.center_xy(*parsed)
    if xy is None:
        raise RouteInputError(
            "raster waypoints need projected x_m/y_m (or an r{row}c{col} node id)", detail_code="WAYPOINT_UNRESOLVED"
        )
    row, col = grid.cell_of(*xy)
    reach = int(math.ceil(max(tolerance_m, 0.0) / grid.cell_size_m)) + 1
    found: list[tuple[float, str, int]] = []
    for r in range(row - reach, row + reach + 1):
        for c in range(col - reach, col + reach + 1):
            idx = graph.index_of.get(raster_node_id(r, c))
            if idx is None:
                continue
            nx, ny = graph.xy(idx)
            d = math.hypot(nx - xy[0], ny - xy[1])
            if d <= tolerance_m + EPS_VALUE:
                found.append((d, graph.node_ids[idx], idx))
    found.sort()
    return found


def resolve_waypoint(graph: RouteGraph, grid: GridArrays | None, waypoint: Waypoint, tolerance_m: float) -> int | None:
    """Graph node for a waypoint: the nearest traversable node within ``tolerance_m`` (ties by node id)."""
    nodes = resolve_waypoint_set(graph, grid, waypoint, tolerance_m)
    return nodes[0][2] if nodes else None


def build_graph_for(
    constraints: ConstraintsArtifact,
    grid: GridArrays | None,
    *,
    slope_cap_deg: float | None = None,
    check_cancelled: Callable[[], None] | None = None,
    hazard_min_intersection_m: float | None = None,
) -> RouteGraph:
    if constraints.artifact_kind == "SYNTHETIC_GRAPH_REGRESSION":
        return build_abstract_graph(constraints, slope_cap_deg=slope_cap_deg)
    if grid is None or constraints.grid is None:
        raise RouteInputError("raster route test needs the analysis grid arrays", detail_code="ANALYSIS_GRID_MISSING")
    spec = constraints.grid
    if (grid.width, grid.height) != (spec.width, spec.height) or abs(grid.cell_size_m - spec.cell_size_m) > 1e-9:
        raise RouteInputError(
            "analysis grid arrays do not match the GridSpec in the constraints", detail_code="GRID_SPEC_MISMATCH"
        )
    return build_raster_graph(
        grid,
        slope_cap_deg=constraints.surface_slope_cap_deg if slope_cap_deg is None else slope_cap_deg,
        exposures=constraints.exposures,
        dilation_m=constraints.footprint_dilation_m,
        blocked_edge_ids=constraints.blocked_edge_ids,
        check_cancelled=check_cancelled,
        hazard_min_intersection_m=hazard_min_intersection_m,
    )


def prepare_problem(
    constraints: ConstraintsArtifact,
    grid: GridArrays | None,
    *,
    mode: RuntimeMode,
    slope_cap_deg: float | None = None,
    check_cancelled: Callable[[], None] | None = None,
    hazard_min_intersection_m: float | None = None,
) -> Problem:
    validate_constraints(constraints, mode=mode)
    provider = make_energy_provider(constraints)
    graph = build_graph_for(
        constraints,
        grid,
        slope_cap_deg=slope_cap_deg,
        check_cancelled=check_cancelled,
        hazard_min_intersection_m=hazard_min_intersection_m,
    )
    costs = evaluate_costs(graph, constraints, provider)
    start = resolve_waypoint(graph, grid, constraints.start, 0.0)
    sets = {t.task_id: resolve_waypoint_set(graph, grid, t.location, t.tolerance_m) for t in constraints.tasks}
    tasks = {tid: (found[0][2] if found else None) for tid, found in sets.items()}
    task_sets = {tid: frozenset(n for _d, _id, n in found) for tid, found in sets.items()}
    return Problem(constraints, graph, provider, costs, start, tasks, task_sets)


# ----------------------------------------------------------------------------------------------- label search
class _Label:
    __slots__ = (
        "node", "mask", "dist", "cons", "nom", "time", "expo", "cov", "sat", "rd", "rc", "rt",
        "parent", "edge", "seq", "dead", "usage",
    )  # fmt: skip

    def __init__(
        self,
        node: int,
        mask: int,
        dist: float,
        cons: float,
        nom: float,
        time_s: float,
        expo: tuple[float, ...],
        cov: frozenset[int],
        sat: int,
        parent: _Label | None,
        edge: int,
        seq: bytes,
        usage: dict[int, int] | None = None,
    ) -> None:
        self.node = node
        self.mask = mask
        self.dist = dist
        self.cons = cons
        self.nom = nom
        self.time = time_s
        self.expo = expo
        self.cov = cov
        self.sat = sat
        self.rd = round(dist * _MICRO)
        self.rc = round(cons * _NANO)
        self.rt = round(time_s * _MICRO)
        self.parent = parent
        self.edge = edge
        self.seq = seq
        self.dead = False
        self.usage = usage  # per-edge traversal counts; only kept in STRICT dominance mode


@dataclass(frozen=True)
class SearchOutput:
    payload: SearchRoutePayload
    route: RouteArtifact | None
    route_sha256: str | None
    issues: list[ScienceIssue]
    certificate: Certificate | None
    problem: Problem | None


def _usage(label: _Label) -> dict[int, int]:
    counts: dict[int, int] = {}
    node: _Label | None = label
    while node is not None and node.parent is not None:
        counts[node.edge] = counts.get(node.edge, 0) + 1
        node = node.parent
    return counts


def _path(label: _Label) -> list[_Label]:
    chain: list[_Label] = []
    node: _Label | None = label
    while node is not None:
        chain.append(node)
        node = node.parent
    chain.reverse()
    return chain


def search_route(
    constraints: ConstraintsArtifact,
    constraints_sha256_claimed: str,
    *,
    grid: GridArrays | None = None,
    mode: RuntimeMode,
    check_cancelled: Callable[[], None] | None = None,
    max_expansions: int | None = None,
    max_seconds: float | None = None,
    max_labels_per_node: int | None = None,
    route_key: str = "route",
    route_artifact_key: str = "route",
    to_lonlat: Callable[[float, float], tuple[float, float]] | None = None,
    clock: Callable[[], float] = time.monotonic,
    hazard_min_intersection_m: float | None = None,
) -> SearchOutput:
    """Run ``SEARCH_ROUTE``.  Raises ``RouteInputError`` for BLOCKED conditions (stale hash, missing grid, ...)."""
    started = clock()
    cancel = check_cancelled if check_cancelled is not None else (lambda: None)
    claimed_hash = require_fresh_hash(constraints, constraints_sha256_claimed)
    cancel()
    problem = prepare_problem(
        constraints, grid, mode=mode, check_cancelled=cancel, hazard_min_intersection_m=hazard_min_intersection_m
    )
    graph, provider, costs = problem.graph, problem.provider, problem.costs
    solver = constraints.solver
    budget_expansions = solver.max_expansions if max_expansions is None else min(solver.max_expansions, max_expansions)
    budget_seconds = float(solver.max_seconds if max_seconds is None else min(solver.max_seconds, max_seconds))
    label_cap = (
        solver.max_labels_per_node
        if max_labels_per_node is None
        else min(solver.max_labels_per_node, max_labels_per_node)
    )

    if len(constraints.tasks) > MAX_TASKS:
        raise RouteInputError(f"at most {MAX_TASKS} tasks are supported", detail_code="TOO_MANY_TASKS")
    needs_exposure = constraints.strategy != "WAYPOINT_RETURN" and bool(constraints.exposures)
    if not constraints.tasks and not needs_exposure:
        raise RouteInputError("nothing to route: no tasks and no exposure requirement", detail_code="NOTHING_TO_ROUTE")

    def finish(
        status: SearchStatus,
        counters: tuple[int, int, int, int],
        reason: str,
        *,
        route: RouteArtifact | None = None,
        cert: Certificate | None = None,
        flags: list[str] | None = None,
        issues: list[ScienceIssue] | None = None,
    ) -> SearchOutput:
        route_sha = canonical_sha256(route) if route is not None else None
        payload = SearchRoutePayload(
            search_status=status,
            route=route,
            route_artifact_key=route_artifact_key if route is not None else None,
            route_sha256=route_sha,
            counters=SearchCounters(
                expansions=counters[0],
                labels_created=counters[1],
                labels_pruned_dominated=counters[2],
                labels_pruned_lossy=counters[3],
                elapsed_ms=int(max(0.0, clock() - started) * 1000),
            ),
            approximation_flags=flags or [],
            optimistic_exposure_bound_m=dict(cert.exposure_bound_m) if cert is not None else {},
            termination_reason=reason,
        )
        return SearchOutput(payload, route, route_sha, issues or [], cert, problem)

    # ---- certificate step (lossless)
    certificate = compute_certificate(graph, constraints, provider, costs, problem.start, problem.task_sets)
    if certificate.infeasible:
        text = "; ".join(r.message for r in certificate.reasons)
        return finish("EXHAUSTIVE_INFEASIBLE", (0, 0, 0, 0), f"CERTIFICATE: {text}", cert=certificate)
    start = problem.start
    assert start is not None  # certificate guarantees a resolved start

    # ---- search tables
    task_list = list(constraints.tasks)
    tset: list[frozenset[int]] = []
    for t in task_list:
        nodes_of_task = problem.task_sets[t.task_id]
        assert nodes_of_task  # certificate guarantees resolved tasks
        tset.append(nodes_of_task)
    n_tasks = len(task_list)
    full_mask = (1 << n_tasks) - 1
    tasks_at: dict[int, list[int]] = {}
    for k, nodes_of_task in enumerate(tset):
        for node in sorted(nodes_of_task):
            tasks_at.setdefault(node, []).append(k)
    ret = constraints.return_required
    use_energy_objective = constraints.strategy == "MINIMUM_FEASIBLE_ROUTE" and provider.evaluable
    objective_note = "distance"
    if constraints.strategy == "MINIMUM_FEASIBLE_ROUTE":
        objective_note = "energy" if use_energy_objective else "distance (energy model missing)"

    to_start_d, to_task_d = remaining_bound_tables(graph, start, tset, costs, use_energy=False)
    energy_bounded = provider.evaluable
    usable = usable_wh(provider) if energy_bounded else math.inf
    if energy_bounded:
        to_start_e, to_task_e = remaining_bound_tables(graph, start, tset, costs, use_energy=True)
    else:
        to_start_e, to_task_e = [], []
    asymmetric_energy = energy_bounded and any(abs(rec.dz_m) > 1e-12 for rec in graph.edges)
    # cheapest way back to the start once task k is done (it may be completed at any node of its set)
    back_d = [min(to_start_d[n] for n in nodes) for nodes in tset]
    back_e = [min(to_start_e[n] for n in nodes) for nodes in tset] if energy_bounded else []
    task_cons = [costs.per_task[t.task_id].conservative_wh for t in task_list]
    task_nom = [costs.per_task[t.task_id].nominal_wh for t in task_list]
    task_dur = [costs.per_task[t.task_id].duration_s for t in task_list]

    exp_specs = list(constraints.exposures) if needs_exposure else []
    exp_idx = list(range(len(constraints.exposures))) if needs_exposure else []
    exp_min = [s.minimum_distance_m for s in exp_specs]
    exp_total_mode = [s.counting == "TOTAL_TRAVERSED_DISTANCE" for s in exp_specs]
    unique_reqs = [i for i, total_mode in enumerate(exp_total_mode) if not total_mode]
    total_reqs = [i for i, total_mode in enumerate(exp_total_mode) if total_mode]

    remaining_cache: dict[int, tuple[int, ...]] = {}

    def remaining(mask: int) -> tuple[int, ...]:
        cached = remaining_cache.get(mask)
        if cached is None:
            cached = tuple(k for k in range(n_tasks) if not mask >> k & 1)
            remaining_cache[mask] = cached
        return cached

    def h_dist(node: int, mask: int, expo: tuple[float, ...]) -> float:
        base = to_start_d[node] if ret else 0.0
        for k in remaining(mask):
            v = to_task_d[k][node] + (back_d[k] if ret else 0.0)
            if v > base:
                base = v
        for i, e in enumerate(expo):
            deficit = exp_min[i] - e
            if deficit > base:
                base = deficit
        return base

    def energy_lb(node: int, mask: int) -> float:
        base = to_start_e[node] if ret else 0.0
        extra = 0.0
        for k in remaining(mask):
            v = to_task_e[k][node] + (back_e[k] if ret else 0.0)
            if v > base:
                base = v
            extra += task_cons[k]
        return base + extra

    node_rank = {i: r for r, i in enumerate(sorted(range(len(graph.node_ids)), key=lambda i: graph.node_ids[i]))}
    rank_bytes = [node_rank[i].to_bytes(4, "big") for i in range(len(graph.node_ids))]

    def sat_mask(expo: tuple[float, ...]) -> int:
        bits = 0
        for i, e in enumerate(expo):
            if e >= exp_min[i] - EPS_VALUE:
                bits |= 1 << i
        return bits

    # ---- initial label
    init_mask = 0
    cons0 = nom0 = time0 = 0.0
    for k in tasks_at.get(start, []):
        init_mask |= 1 << k
        cons0 += task_cons[k]
        nom0 += task_nom[k]
        time0 += task_dur[k]
    expo0 = tuple(0.0 for _ in exp_specs)
    max_trav = constraints.max_undirected_edge_traversals
    total_reqs_present = bool(total_reqs)
    strict = max_trav == 1 or total_reqs_present  # see the module docstring: STRICT vs RELAXED dominance
    root = _Label(
        start, init_mask, 0.0, cons0, nom0, time0, expo0, frozenset(), sat_mask(expo0), None, -1, rank_bytes[start],
        {} if strict else None,
    )  # fmt: skip
    # A root that already satisfies everything is NOT a solution (a route has at least one edge), so it must not
    # dominate (and thereby discard) the labels that leave and return to the start.
    root_done = init_mask == full_mask and all(e >= exp_min[i] - EPS_VALUE for i, e in enumerate(expo0))

    def priority(label: _Label, counter: int) -> tuple[int, int, int, bytes, int]:
        if use_energy_objective:
            f = label.cons + energy_lb(label.node, label.mask)
            return (round(f * _NANO), label.rc, label.rd, label.seq, counter)
        f = label.dist + h_dist(label.node, label.mask, label.expo)
        return (round(f * _MICRO), label.rd, label.rc, label.seq, counter)

    def usage_le(a: _Label, b: _Label) -> bool:
        """STRICT mode: ``a`` used no edge more often than ``b`` (every continuation of ``b`` is legal for ``a``)."""
        if not strict:
            return True
        assert a.usage is not None and b.usage is not None
        other = b.usage
        return all(other.get(e, 0) >= c for e, c in a.usage.items())

    def covers(a: _Label, b: _Label) -> bool:
        """``a`` is at least as good as ``b`` in every dimension that can matter for the future."""
        if a.rd > b.rd or a.rc > b.rc or a.rt > b.rt or not a.cov >= b.cov:
            return False
        return all(a.expo[i] >= b.expo[i] - EPS_VALUE for i in total_reqs) and usage_le(a, b)

    def identical(a: _Label, b: _Label) -> bool:
        """Equal in every COST dimension (the traversal usage may still differ in STRICT mode)."""
        return (
            a.rd == b.rd
            and a.rc == b.rc
            and a.rt == b.rt
            and a.cov == b.cov
            and all(abs(a.expo[i] - b.expo[i]) <= EPS_VALUE for i in total_reqs)
        )

    def same_usage(a: _Label, b: _Label) -> bool:
        return (not strict) or a.usage == b.usage

    heap: list[tuple[tuple[int, int, int, bytes, int], _Label]] = []
    counter = 0
    heappush(heap, (priority(root, counter), root))
    labels_created = 1
    class_counts: dict[tuple[int, int, tuple[int, ...]], int] = {}
    pareto: dict[tuple[int, int, int], list[_Label]] = {} if root_done else {(root.node, root.mask, root.sat): [root]}
    expansions = 0
    pruned_dominated = 0
    pruned_lossy = 0
    bound_pruned = 0
    max_dist = constraints.max_distance_m if constraints.max_distance_m is not None else math.inf
    max_dur = constraints.max_duration_s if constraints.max_duration_s is not None else math.inf
    pops = 0

    def bucket(expo: tuple[float, ...]) -> tuple[int, ...]:
        return tuple(4 if exp_min[i] <= 0.0 else min(4, int(4.0 * e / exp_min[i])) for i, e in enumerate(expo))

    def counters() -> tuple[int, int, int, int]:
        return (expansions, labels_created, pruned_dominated, pruned_lossy)

    def reason_suffix() -> str:
        return f" [objective={objective_note}; bound_pruned={bound_pruned}]"

    def lossy_flags() -> list[str]:
        return [LABEL_CAP_FLAG] if pruned_lossy > 0 else []

    if not root_done:
        class_counts[(root.node, root.mask, bucket(root.expo))] = 1

    while heap:
        pops += 1
        if pops & 7 == 0:
            cancel()
        if (pops == 1 or pops & 7 == 0) and clock() - started > budget_seconds:
            return finish(
                "BUDGET_EXHAUSTED",
                counters(),
                f"max_seconds {budget_seconds:g} reached" + reason_suffix(),
                cert=certificate,
                flags=lossy_flags(),
            )
        _prio, label = heappop(heap)
        if label.dead:
            continue
        done = label.mask == full_mask and all(e >= exp_min[i] - EPS_VALUE for i, e in enumerate(label.expo))
        if done and label.parent is not None and ((not ret) or label.node == start):
            route = _make_route(label, graph, problem, claimed_hash, mode, route_key, to_lonlat, tset)
            return finish(
                "FOUND",
                counters(),
                "solution popped first by the best-first order" + reason_suffix(),
                route=route,
                cert=certificate,
                flags=lossy_flags(),
            )
        if expansions >= budget_expansions:
            return finish(
                "BUDGET_EXHAUSTED",
                counters(),
                f"max_expansions {budget_expansions} reached" + reason_suffix(),
                cert=certificate,
                flags=lossy_flags(),
            )
        expansions += 1
        usage = label.usage if label.usage is not None else _usage(label)
        for nbr, ei, sign in graph.adj[label.node]:
            count = usage.get(ei, 0)
            if count >= max_trav:
                continue
            res = costs.edge(ei, sign)
            rec = graph.edges[ei]
            new_dist = label.dist + rec.d_xy_m
            new_cons = label.cons + res.conservative_wh
            new_nom = label.nom + res.nominal_wh
            new_time = label.time + res.duration_s
            new_mask = label.mask
            for k in tasks_at.get(nbr, ()):
                if not new_mask >> k & 1:
                    new_mask |= 1 << k
                    new_cons += task_cons[k]
                    new_nom += task_nom[k]
                    new_time += task_dur[k]
            if new_time > max_dur + EPS_VALUE:
                bound_pruned += 1
                continue
            new_cov = label.cov
            if exp_specs:
                new_expo_list = []
                for i, e in enumerate(label.expo):
                    band = rec.band_len_m[exp_idx[i]]
                    gain = band if (count == 0 or exp_total_mode[i]) else 0.0
                    new_expo_list.append(min(exp_min[i], e + gain))
                    if count == 0 and band > 0.0 and not exp_total_mode[i] and e < exp_min[i] - EPS_VALUE:
                        new_cov = new_cov | {ei}
                new_expo = tuple(new_expo_list)
            else:
                new_expo = ()
            new_sat = sat_mask(new_expo)
            if all(new_sat >> i & 1 for i in unique_reqs):
                new_cov = frozenset()
            if new_dist + h_dist(nbr, new_mask, new_expo) > max_dist + EPS_VALUE:
                bound_pruned += 1
                continue
            if energy_bounded and new_cons + energy_lb(nbr, new_mask) > usable + EPS_VALUE:
                bound_pruned += 1
                continue
            child_usage = {**usage, ei: count + 1} if strict else None
            child = _Label(
                nbr, new_mask, new_dist, new_cons, new_nom, new_time, new_expo, new_cov, new_sat, label, ei,
                label.seq + rank_bytes[nbr], child_usage,
            )  # fmt: skip
            # Pareto dominance among labels with the same (node, task set, saturation pattern)
            peers = pareto.setdefault((nbr, new_mask, new_sat), [])
            dropped = False
            survivors: list[_Label] = []
            for other in peers:
                if covers(other, child):
                    if identical(other, child) and child.seq < other.seq:
                        if same_usage(other, child):
                            other.dead = True  # same state, lexicographically smaller sequence wins
                            pruned_dominated += 1
                        else:
                            survivors.append(
                                other
                            )  # STRICT: ``other`` is freer, ``child`` is lexicographically smaller
                        continue
                    dropped = True
                    break
                if covers(child, other):
                    if identical(other, child) and other.seq < child.seq:
                        survivors.append(other)  # STRICT: ``child`` is freer but ``other`` is lexicographically smaller
                        continue
                    other.dead = True
                    pruned_dominated += 1
                    continue
                survivors.append(other)
            if dropped:
                pruned_dominated += 1
                continue
            cls = (nbr, new_mask, bucket(new_expo))
            seen = class_counts.get(cls, 0)
            if seen >= label_cap:
                pruned_lossy += 1
                continue
            class_counts[cls] = seen + 1
            survivors.append(child)
            pareto[(nbr, new_mask, new_sat)] = survivors
            counter += 1
            labels_created += 1
            heappush(heap, (priority(child, counter), child))

    if pruned_lossy > 0:
        return finish(
            "BUDGET_EXHAUSTED",
            counters(),
            "queue exhausted after lossy label-cap pruning: infeasibility not proven" + reason_suffix(),
            cert=certificate,
            flags=lossy_flags(),
        )
    if asymmetric_energy and pruned_dominated > 0 and not strict:
        return finish(
            "BUDGET_EXHAUSTED",
            counters(),
            "queue exhausted, but dominance ignores traversal counts and the active energy bound is asymmetric "
            "(uphill/downhill): infeasibility not proven" + reason_suffix(),
            cert=certificate,
            flags=["TRAVERSAL_COUNT_DOMINANCE: exhaustive-infeasibility claim withheld under asymmetric energy."],
        )
    return finish(
        "EXHAUSTIVE_INFEASIBLE",
        counters(),
        "queue exhausted with no lossy pruning: no feasible route in the bounded discrete domain" + reason_suffix(),
        cert=certificate,
    )


def _make_route(
    last: _Label,
    graph: RouteGraph,
    problem: Problem,
    constraints_sha256: str,
    mode: RuntimeMode,
    route_key: str,
    to_lonlat: Callable[[float, float], tuple[float, float]] | None,
    tset: Sequence[frozenset[int]],
) -> RouteArtifact:
    constraints = problem.constraints
    chain = _path(last)
    node_ids = [graph.node_ids[lab.node] for lab in chain]
    events: list[TaskEvent] = []
    done: set[str] = set()
    for lab in chain:
        for k, nodes_of_task in enumerate(tset):
            task = constraints.tasks[k]
            if lab.node in nodes_of_task and task.task_id not in done:
                done.add(task.task_id)
                events.append(
                    TaskEvent(
                        task_id=task.task_id,
                        node_id=graph.node_ids[lab.node],
                        arrival_distance_m=lab.dist,
                        dwell_s=task.dwell_s,
                    )
                )
    # the searcher's own belief (informational; the verifier recomputes everything independently)
    seen: set[int] = set()
    claimed_expo = {s.requirement_id: 0.0 for s in constraints.exposures}
    for lab in chain[1:]:
        rec = graph.edges[lab.edge]
        for i, spec in enumerate(constraints.exposures):
            if lab.edge not in seen or spec.counting == "TOTAL_TRAVERSED_DISTANCE":
                claimed_expo[spec.requirement_id] += rec.band_len_m[i]
        seen.add(lab.edge)
    geometry = None
    if to_lonlat is not None and graph.node_xy is not None:
        geometry = GeoJSONLineString(coordinates=[to_lonlat(*graph.xy(lab.node)) for lab in chain])
    return RouteArtifact(
        route_key=route_key,
        mode=mode,
        constraints_sha256=constraints_sha256,
        strategy=constraints.strategy,
        graph_revision=graph.revision,
        node_sequence=node_ids,
        task_events=events,
        display_geometry=geometry,
        solver_claimed=SolverClaimedTotals(
            distance_m=last.dist,
            energy_conservative_wh=last.cons if problem.provider.evaluable else None,
            unique_exposure_m=claimed_expo,
        ),
    )


def task_nodes_summary(problem: Problem) -> Mapping[str, int | None]:
    return problem.task_nodes


__all__ = [
    "LABEL_CAP_FLAG",
    "MAX_TASKS",
    "Problem",
    "SearchOutput",
    "build_graph_for",
    "prepare_problem",
    "resolve_waypoint",
    "resolve_waypoint_set",
    "search_route",
]
