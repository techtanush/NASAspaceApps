"""Lossless infeasibility certificates (08 section 4.10 step 2) and shortest-path helpers.

A certificate may only use OPTIMISTIC bounds, so that "infeasible" is a statement about the whole discrete problem
(graph, route-domain bounds, model) and never about a heuristic:

* start/task connectivity in the start component.  A task is satisfied at ANY traversable node within its tolerance
  (the verifier accepts any route node in tolerance), so it is reachable iff at least one of those nodes lies in the
  start component; distance/energy bounds use the cheapest such node;
* optimistic exposure bound per requirement =
  ``min(sum of in-band subsegment length over the component's undirected edges, max_distance_m,
  energy distance bound)``;
* distance lower bound of any closed route visiting all tasks (``2 * farthest task``) versus ``max_distance_m``;
* energy lower bound of any closed route visiting all tasks (shortest directed conservative energy there and back
  plus all task energies) versus the usable energy.

``labels_pruned_lossy`` is therefore always 0 for a certificate proof.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass

from analogforge.ports import catalog
from analogforge.ports.science_payloads import ConstraintsArtifact
from analogforge.science.routing import EPS_VALUE
from analogforge.science.routing.constraints import EdgeResources, EnergyProvider, TaskResources, usable_wh
from analogforge.science.routing.grid_graph import RouteGraph, reachable_from

CostFn = Callable[[int, int], float]  # (edge_index, sign) -> non-negative cost of travelling in that direction


@dataclass(frozen=True)
class CertificateReason:
    code: str
    constraint_id: str
    requirement_id: str | None
    message: str
    observed: float | None
    threshold: float | None
    domain_bound: bool = False


@dataclass(frozen=True)
class Certificate:
    infeasible: bool
    reasons: tuple[CertificateReason, ...]
    exposure_bound_m: dict[str, float]
    component_size: int
    distance_lower_bound_m: float | None
    energy_lower_bound_wh: float | None
    usable_wh: float | None

    @property
    def violated_constraint_ids(self) -> list[str]:
        return sorted({r.constraint_id for r in self.reasons})


def dijkstra(graph: RouteGraph, source: int | Collection[int], cost: CostFn) -> list[float]:
    """Shortest path from one node or (multi-source) a set of nodes; unreachable nodes get ``inf``.  Deterministic."""
    sources = [source] if isinstance(source, int) else sorted(source)
    dist = [math.inf] * len(graph.node_ids)
    heap: list[tuple[float, int]] = []
    for src in sources:
        dist[src] = 0.0
        heap.append((0.0, src))
    heapq.heapify(heap)
    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
        for nbr, ei, sign in graph.adj[node]:
            nd = d + cost(ei, sign)
            if nd < dist[nbr]:
                dist[nbr] = nd
                heapq.heappush(heap, (nd, nbr))
    return dist


@dataclass(frozen=True)
class EdgeCosts:
    """Pre-evaluated resources per edge and direction (index 0: travelling u->v, index 1: v->u) and per task."""

    per_edge: tuple[tuple[EdgeResources, EdgeResources], ...]
    per_task: dict[str, TaskResources]

    def edge(self, edge_index: int, sign: int) -> EdgeResources:
        return self.per_edge[edge_index][0 if sign > 0 else 1]


def evaluate_costs(graph: RouteGraph, constraints: ConstraintsArtifact, provider: EnergyProvider) -> EdgeCosts:
    per_edge = []
    for rec in graph.edges:
        fwd = provider.edge(rec.d_xy_m, rec.dz_m, rec.mock_energy_wh)
        bwd = provider.edge(rec.d_xy_m, -rec.dz_m, rec.mock_energy_wh)
        per_edge.append((fwd, bwd))
    return EdgeCosts(tuple(per_edge), {t.task_id: provider.task(t) for t in constraints.tasks})


def compute_certificate(
    graph: RouteGraph,
    constraints: ConstraintsArtifact,
    provider: EnergyProvider,
    costs: EdgeCosts,
    start: int | None,
    task_nodes: Mapping[str, Collection[int]],
    *,
    unbounded_battery: bool = False,
) -> Certificate:
    """Optimistic-bound certificate for ``constraints`` on ``graph``.

    ``unbounded_battery=True`` implements the ROVER half of the ANALOG-vs-ROVER rule (battery treated unbounded);
    the caller rebuilds the graph with a raised slope cap for the other half.
    """
    reasons: list[CertificateReason] = []
    max_trav = constraints.max_undirected_edge_traversals
    if start is None:
        reasons.append(
            CertificateReason(
                "START_UNRESOLVED", catalog.CONSTRAINT_RETURN, None, "Start is not a traversable node.", None, None
            )
        )
        return Certificate(True, tuple(reasons), {}, 0, None, None, None)

    component = reachable_from(graph, start)
    reachable_sets: dict[str, list[int]] = {}
    for task in constraints.tasks:
        reachable_sets[task.task_id] = sorted(n for n in task_nodes.get(task.task_id, ()) if n in component)
        if not reachable_sets[task.task_id]:
            reasons.append(
                CertificateReason(
                    "TASK_UNREACHABLE",
                    catalog.constraint_task(task.task_id),
                    None,
                    f"Task {task.task_id} is not reachable from the start inside the traversable graph "
                    "(task unreachable).",
                    None,
                    None,
                )
            )
    if reasons:
        return Certificate(True, tuple(reasons), {}, len(component), None, None, None)

    dist = dijkstra(graph, start, lambda ei, _s: graph.edges[ei].d_xy_m)
    far = max((min(dist[n] for n in reachable_sets[t.task_id]) for t in constraints.tasks), default=0.0)
    distance_lb = 2.0 * far if constraints.return_required else far
    if constraints.max_distance_m is not None and distance_lb > constraints.max_distance_m + EPS_VALUE:
        reasons.append(
            CertificateReason(
                "MAX_DISTANCE",
                catalog.CONSTRAINT_MAX_DISTANCE,
                None,
                f"Any closed route visiting all tasks needs at least {distance_lb:.3f} m "
                f"> {constraints.max_distance_m:.3f} m.",
                distance_lb,
                constraints.max_distance_m,
            )
        )

    # energy bounds (only when the model exists and the battery is bounded)
    energy_lb: float | None = None
    usable: float | None = None
    distance_from_energy = math.inf
    if provider.evaluable and not unbounded_battery:
        usable = usable_wh(provider)
        fwd = dijkstra(graph, start, lambda ei, s: costs.edge(ei, s).conservative_wh)
        back = dijkstra(graph, start, lambda ei, s: costs.edge(ei, -s).conservative_wh)  # cost of travelling TO start
        task_wh = sum(c.conservative_wh for c in costs.per_task.values())
        trips = [
            min(fwd[n] + (back[n] if constraints.return_required else 0.0) for n in reachable_sets[t.task_id])
            for t in constraints.tasks
        ]
        energy_lb = (max(trips) if trips else 0.0) + task_wh
        if energy_lb > usable + EPS_VALUE:
            reasons.append(
                CertificateReason(
                    "ENERGY_LOWER_BOUND",
                    catalog.CONSTRAINT_ENERGY_RESERVE,
                    None,
                    f"Any closed route visiting all tasks needs at least {energy_lb:.3f} Wh "
                    f"conservative > {usable:.3f} Wh usable.",
                    energy_lb,
                    usable,
                )
            )
        ratios = [
            costs.edge(ei, s).conservative_wh / rec.d_xy_m
            for ei, rec in enumerate(graph.edges)
            for s in (1, -1)
            if rec.u in component
        ]
        ratio_min = min(ratios) if ratios else 0.0
        drive_budget = usable - task_wh
        if drive_budget < 0.0:
            distance_from_energy = 0.0
        elif ratio_min > 0.0:
            distance_from_energy = drive_budget / ratio_min

    bounds: dict[str, float] = {}
    if constraints.strategy != "WAYPOINT_RETURN":
        for index, spec in enumerate(constraints.exposures):
            total = sum(rec.band_len_m[index] for rec in graph.edges if rec.u in component)
            if spec.counting == "TOTAL_TRAVERSED_DISTANCE":
                total *= max_trav
            domain_limit = min(
                constraints.max_distance_m if constraints.max_distance_m is not None else math.inf, distance_from_energy
            )
            bound = min(total, domain_limit)
            bounds[spec.requirement_id] = bound
            if bound < spec.minimum_distance_m - EPS_VALUE:
                limit_kind = "route-domain bound" if total >= spec.minimum_distance_m else "reachable in-band"
                reasons.append(
                    CertificateReason(
                        "EXPOSURE_BOUND",
                        catalog.constraint_exposure(spec.requirement_id),
                        spec.requirement_id,
                        (
                            f"Optimistic exposure bound {bound:.3f} m < required {spec.minimum_distance_m:.3f} m "
                            f"({limit_kind} limit)."
                        ),
                        bound,
                        spec.minimum_distance_m,
                        domain_bound=total >= spec.minimum_distance_m,
                    )
                )
    reasons.sort(key=lambda r: (r.constraint_id, r.code))
    return Certificate(bool(reasons), tuple(reasons), bounds, len(component), distance_lb, energy_lb, usable)


def remaining_bound_tables(
    graph: RouteGraph,
    start: int,
    task_nodes: Sequence[Collection[int]],
    costs: EdgeCosts,
    *,
    use_energy: bool,
) -> tuple[list[float], list[list[float]]]:
    """Distance tables for the A* heuristic: ``to_start[n]`` and ``to_task[k][n]`` (shortest horizontal metres to the
    NEAREST node of task k's in-tolerance node set) or, with ``use_energy``, the shortest conservative-energy tables for
    travelling n -> start / n -> that set."""
    if use_energy:
        # cost of travelling n -> target equals reverse Dijkstra from target with reversed direction costs
        def cost(ei: int, sign: int) -> float:
            return costs.edge(ei, -sign).conservative_wh
    else:

        def cost(ei: int, sign: int) -> float:
            return graph.edges[ei].d_xy_m

    to_start = dijkstra(graph, start, cost)
    to_task = [dijkstra(graph, nodes, cost) for nodes in task_nodes]
    return to_start, to_task
