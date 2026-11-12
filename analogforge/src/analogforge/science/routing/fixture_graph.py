"""Abstract (non-raster) graphs: the canonical regression graph, its mock resource provider and the graph designer.

``canonical-graph-v1`` (architecture 12 section 9, ``catalog.FIXTURE_CANONICAL_GRAPH``) is an explicitly SYNTHETIC
graph whose edges carry a fixed surface slope and a mock energy per traversal.  It exists to regression-test search
and verification accounting; it is not a raster surface and is only usable in ``synthetic`` mode.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Final

from analogforge.ports import catalog
from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import SolverConfig
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    ConstraintsArtifact,
    DesignBenchmarkInput,
    DesignBenchmarkPayload,
    EnergySpec,
    ExposureSpec,
    GraphEdge,
    GraphSpec,
    TaskSpec,
    Waypoint,
)
from analogforge.science.routing import RouteInputError, undirected_edge_id
from analogforge.science.routing.constraints import (
    ROUTE_TASK_OBSERVABLE,
    RouteDesignDefaults,
    exposure_specs_from_requirements,
    finish_design_payload,
)
from analogforge.science.routing.exposure import slope_in_band
from analogforge.science.routing.grid_graph import EdgeRec, RouteGraph, finalize_graph

CANONICAL_GRAPH_NODES: Final = ("S", "A", "B", "C", "W1", "W2")
# (a, b, length_m, surface_slope_deg, mock_energy_wh) - architecture 12 section 9
CANONICAL_GRAPH_EDGES: Final = (
    ("S", "A", 20.0, 10.0, 1.0),
    ("A", "W1", 20.0, 10.0, 1.0),
    ("W1", "W2", 20.0, 10.0, 1.0),
    ("S", "B", 50.0, 15.0, 2.0),
    ("B", "C", 50.0, 15.0, 2.0),
    ("C", "W1", 50.0, 15.0, 2.0),
)
CANONICAL_TASK_WH: Final = (("W1", 10.0), ("W2", 10.0))
CANONICAL_START: Final = "S"
CANONICAL_BAND_DEG: Final = (12.0, 18.0)
CANONICAL_MIN_EXPOSURE_M: Final = 100.0
CANONICAL_EXPOSURE_REQUIREMENT_ID: Final = "R-EXPOSURE"
CANONICAL_LIMITATIONS: Final = (
    "SYNTHETIC GRAPH REGRESSION: mock per-edge energies test solver accounting only and bypass "
    "the production energy model.",
    "This graph is not asserted to describe a realizable raster surface.",
)


def canonical_graph_spec(drop_edges: Iterable[tuple[str, str]] = ()) -> GraphSpec:
    """The canonical graph; ``drop_edges`` removes undirected edges (used by the 'steep edges removed' regression)."""
    dropped = {undirected_edge_id(a, b) for a, b in drop_edges}
    edges = [
        GraphEdge(a=a, b=b, length_m=length, surface_slope_deg=slope, mock_energy_wh=wh)
        for a, b, length, slope, wh in CANONICAL_GRAPH_EDGES
        if undirected_edge_id(a, b) not in dropped
    ]
    return GraphSpec(nodes=list(CANONICAL_GRAPH_NODES), edges=edges)


def build_abstract_graph(
    constraints: ConstraintsArtifact,
    *,
    slope_cap_deg: float | None = None,
    blocked_edge_ids: Sequence[str] | None = None,
) -> RouteGraph:
    """Search graph of a ``SYNTHETIC_GRAPH_REGRESSION`` artifact.

    Edges whose surface slope exceeds the cap (or that are blocked) are not traversable.  ``slope_cap_deg`` overrides
    the artifact's cap (used by the ANALOG-vs-ROVER certificate re-run).
    """
    spec = constraints.graph
    if spec is None:
        raise RouteInputError("constraints carry no abstract graph", detail_code="GRAPH_MISSING")
    cap = constraints.surface_slope_cap_deg if slope_cap_deg is None else slope_cap_deg
    blocked = frozenset(constraints.blocked_edge_ids if blocked_edge_ids is None else blocked_edge_ids)
    index = {node: i for i, node in enumerate(spec.nodes)}
    seen: set[str] = set()
    edges: list[EdgeRec] = []
    for edge in spec.edges:
        eid = undirected_edge_id(edge.a, edge.b)
        if eid in seen:
            raise RouteInputError(f"duplicate graph edge {eid}", detail_code="DUPLICATE_EDGE")
        seen.add(eid)
        if eid in blocked or edge.surface_slope_deg > cap + 1e-9:
            continue
        edges.append(
            EdgeRec(
                edge_id=eid,
                u=index[edge.a],
                v=index[edge.b],
                d_xy_m=edge.length_m,
                dz_m=0.0,
                hazard_slope_deg=edge.surface_slope_deg,
                band_len_m=tuple(
                    edge.length_m if slope_in_band(edge.surface_slope_deg, e.band_deg, e.upper_inclusive) else 0.0
                    for e in constraints.exposures
                ),
                mock_energy_wh=edge.mock_energy_wh,
            )
        )
    revision = (
        "graph-"
        + canonical_sha256(
            {"kind": "ABSTRACT", "graph": spec.model_dump(mode="json"), "cap": cap, "blocked": sorted(blocked)}
        )[:16]
    )
    return finalize_graph(spec.nodes, None, [0.0] * len(spec.nodes), edges, revision=revision, kind="ABSTRACT")


def design_graph_benchmark(
    inp: DesignBenchmarkInput,
    *,
    mode: RuntimeMode,
    defaults: RouteDesignDefaults,
    constraints_artifact_key: str = "constraints",
    graph: GraphSpec | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> DesignBenchmarkPayload:
    """``DESIGN_BENCHMARK`` for ``graph_fixture_id == 'canonical-graph-v1'`` (synthetic mode only)."""
    if check_cancelled is not None:
        check_cancelled()
    if mode != "synthetic":
        raise RouteInputError(
            "the canonical graph scenario uses the TEST_ONLY_MOCK_GRAPH provider and is synthetic-only",
            detail_code="MOCK_PROVIDER_FORBIDDEN",
        )
    if inp.graph_fixture_id != catalog.FIXTURE_CANONICAL_GRAPH:
        raise RouteInputError(f"unknown graph fixture {inp.graph_fixture_id!r}", detail_code="UNKNOWN_FIXTURE")
    rover = inp.rover
    exposures = exposure_specs_from_requirements(inp.mission.requirements, rover.max_slope_deg)
    if not exposures:
        exposures = [
            ExposureSpec(
                requirement_id=CANONICAL_EXPOSURE_REQUIREMENT_ID,
                metric_id="surface_slope_deg",
                band_deg=CANONICAL_BAND_DEG,
                upper_inclusive=abs(CANONICAL_BAND_DEG[1] - rover.max_slope_deg) < 1e-9,
                minimum_distance_m=CANONICAL_MIN_EXPOSURE_M,
                counting="UNIQUE_UNDIRECTED_EDGE_DISTANCE",
            )
        ]
    task_req_ids = [r.id for r in inp.mission.requirements if r.observable == ROUTE_TASK_OBSERVABLE]
    tasks = [
        TaskSpec(
            task_id=task_id,
            requirement_ids=task_req_ids,
            kind="SAMPLING",
            location=Waypoint(node_id=task_id),
            tolerance_m=0.0,
            dwell_s=0.0,
            incremental_energy_wh=wh,
            required_capability=None,
            evidence_origin="SYNTHETIC_FIXTURE",
        )
        for task_id, wh in CANONICAL_TASK_WH
    ]
    artifact = ConstraintsArtifact(
        artifact_kind="SYNTHETIC_GRAPH_REGRESSION",
        mode="synthetic",
        resource_provider="TEST_ONLY_MOCK_GRAPH",
        mission_revision_id=inp.mission.id,
        mission_content_sha256=inp.mission.content_sha256,
        rover_revision_id=rover.id,
        rover_content_sha256=rover.content_sha256,
        candidate_window_id=inp.candidate.window_id,
        test_revision=inp.test_revision,
        strategy=inp.strategy,
        grid=None,
        graph=graph if graph is not None else canonical_graph_spec(),
        start=Waypoint(node_id=CANONICAL_START),
        return_required=True,
        tasks=tasks,
        surface_slope_cap_deg=rover.max_slope_deg,
        exposures=exposures,
        max_distance_m=rover.max_route_m if rover.max_route_m is not None else defaults.graph_max_distance_m,
        max_duration_s=None,
        max_undirected_edge_traversals=defaults.max_edge_traversals,
        footprint_dilation_m=0.0,
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
        limitations=list(CANONICAL_LIMITATIONS),
    )
    return finish_design_payload(
        artifact, constraints_artifact_key=constraints_artifact_key, requirements=inp.mission.requirements
    )
