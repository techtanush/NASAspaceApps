"""Constraints design (``DESIGN_BENCHMARK`` assembly), hashing, validation and resource (energy) providers.

Nothing here builds a graph or runs a search; the module is imported by both the solver side and the independent
verifier.  Energy follows architecture 12 section 5 exactly:

    E_roll  = k_r * Crr * m * g * cos(theta_s) * d_s / eta        [J]  (core ``science.energy.edge_energy``)
    E_climb = m * g * max(dz, 0) / eta                            [J]
    E_idle  = P_idle * (t_drive + t_tasks)                        [J]
    E_nom   = (E_roll + E_climb + E_idle) / 3600 + sum(task Wh)   [Wh]
    E_cons  = E_nom * (1 + uncertainty_fraction)
    reserve = 100 * (battery - E_cons) / battery

``theta_s`` is the modeled surface slope of the edge, ``atan2(|dz|, d_xy)`` (so ``cos(theta_s) * d_s = d_xy``);
no downhill credit and no regeneration.  A missing energy model is *not evaluable* (never zero consumption).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NamedTuple, Protocol

from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import RequiredExposure, Requirement
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    ConstraintMapping,
    ConstraintsArtifact,
    DesignBenchmarkPayload,
    ExposureSpec,
    TaskSpec,
    Waypoint,
)
from analogforge.science.energy import JOULES_PER_WH, EnergyParams, edge_energy
from analogforge.science.routing import RouteInputError

MOCK_METHOD_ID: Final = "mock-graph-energy-v1"
PHYSICAL_METHOD_ID: Final = "earth-simple-v1"


# ----------------------------------------------------------------------------------------------- resource providers
class EdgeResources(NamedTuple):
    nominal_wh: float
    conservative_wh: float
    duration_s: float
    surface_m: float


class TaskResources(NamedTuple):
    nominal_wh: float
    conservative_wh: float
    duration_s: float


class EnergyProvider(Protocol):
    """Per-edge/per-task resource model.  ``evaluable`` is False when no energy model exists (energy unknown)."""

    @property
    def evaluable(self) -> bool: ...

    @property
    def method_id(self) -> str: ...

    @property
    def quantity_kind(self) -> str: ...

    @property
    def battery_wh(self) -> float: ...

    @property
    def min_reserve_pct(self) -> float: ...

    def edge(self, d_xy_m: float, dz_m: float, mock_wh: float | None) -> EdgeResources: ...

    def task(self, task: TaskSpec) -> TaskResources: ...


def usable_wh(provider: EnergyProvider) -> float:
    """Conservative energy allowed by the reserve rule: ``battery * (1 - min_reserve_pct / 100)``."""
    return provider.battery_wh * (1.0 - provider.min_reserve_pct / 100.0)


@dataclass(frozen=True)
class MockGraphEnergy:
    """TEST-ONLY provider: edge energy is the fixture's ``mock_energy_wh`` per traversal, task energy is the task's
    ``incremental_energy_wh``; no uncertainty margin, no idle power.  Forbidden in ``live`` mode."""

    battery_wh: float
    min_reserve_pct: float
    speed_mps: float
    evaluable: bool = True
    method_id: str = MOCK_METHOD_ID
    quantity_kind: str = "ASSUMED"

    def edge(self, d_xy_m: float, dz_m: float, mock_wh: float | None) -> EdgeResources:
        if mock_wh is None:
            raise RouteInputError("graph edge has no mock_energy_wh", detail_code="MOCK_ENERGY_MISSING")
        return EdgeResources(mock_wh, mock_wh, d_xy_m / self.speed_mps, d_xy_m)

    def task(self, task: TaskSpec) -> TaskResources:
        if task.incremental_energy_wh is None:
            raise RouteInputError(
                f"task {task.task_id} has no incremental_energy_wh", detail_code="MOCK_ENERGY_MISSING"
            )
        return TaskResources(task.incremental_energy_wh, task.incremental_energy_wh, task.dwell_s)


@dataclass(frozen=True)
class PhysicalEarthEnergy:
    """Adapter over the core ``science.energy`` model ``earth-simple-v1`` (architecture 12 section 5)."""

    params: EnergyParams
    evaluable: bool = True
    method_id: str = PHYSICAL_METHOD_ID

    @property
    def battery_wh(self) -> float:
        return self.params.battery_wh

    @property
    def min_reserve_pct(self) -> float:
        return self.params.min_reserve_pct

    @property
    def quantity_kind(self) -> str:
        return "DERIVED" if self.params.calibration_status == "CALIBRATED" else "ASSUMED"

    def edge(self, d_xy_m: float, dz_m: float, mock_wh: float | None) -> EdgeResources:
        p = self.params
        e = edge_energy(p, d_xy_m, dz_m)
        nominal = e.drive_wh + p.idle_power_w * e.drive_time_s / JOULES_PER_WH
        return EdgeResources(nominal, nominal * (1.0 + p.uncertainty_fraction), e.drive_time_s, e.d_s_m)

    def task(self, task: TaskSpec) -> TaskResources:
        p = self.params
        task_wh = task.incremental_energy_wh if task.incremental_energy_wh is not None else p.science_task_wh
        nominal = task_wh + p.idle_power_w * task.dwell_s / JOULES_PER_WH
        return TaskResources(nominal, nominal * (1.0 + p.uncertainty_fraction), task.dwell_s)


@dataclass(frozen=True)
class NullEnergy:
    """No energy model: energy is *unknown*.  Durations are still computable from the speed; all Wh values are 0.0
    placeholders that callers must never report (``evaluable`` is False)."""

    battery_wh: float
    min_reserve_pct: float
    speed_mps: float
    evaluable: bool = False
    method_id: str = "energy-model-missing"
    quantity_kind: str = "ASSUMED"

    def edge(self, d_xy_m: float, dz_m: float, mock_wh: float | None) -> EdgeResources:
        surface_m = math.hypot(d_xy_m, dz_m)
        return EdgeResources(0.0, 0.0, surface_m / self.speed_mps, surface_m)

    def task(self, task: TaskSpec) -> TaskResources:
        return TaskResources(0.0, 0.0, task.dwell_s)


def make_energy_provider(constraints: ConstraintsArtifact) -> EnergyProvider:
    """Select the provider from the artifact; the mock provider is only honoured for synthetic graph regressions."""
    spec = constraints.energy
    if constraints.resource_provider == "TEST_ONLY_MOCK_GRAPH":
        if constraints.mode != "synthetic":
            raise RouteInputError(
                "the TEST_ONLY_MOCK_GRAPH resource provider is only allowed in synthetic mode",
                detail_code="MOCK_PROVIDER_FORBIDDEN",
            )
        return MockGraphEnergy(spec.battery_wh, spec.min_reserve_pct, spec.nominal_speed_mps)
    params = EnergyParams.from_spec(spec)
    if params is None:
        return NullEnergy(spec.battery_wh, spec.min_reserve_pct, spec.nominal_speed_mps)
    return PhysicalEarthEnergy(params)


# ----------------------------------------------------------------------------------------------- hashing/validation
def constraints_sha256(constraints: ConstraintsArtifact) -> str:
    """``VerificationTest.constraints_sha256``: RFC 8785 canonical hash of the whole artifact."""
    return canonical_sha256(constraints)


def require_fresh_hash(constraints: ConstraintsArtifact, claimed_sha256: str) -> str:
    """Return the recomputed hash or raise ``STALE_INPUT_HASH`` when the claimed hash does not match."""
    actual = constraints_sha256(constraints)
    if actual != claimed_sha256:
        raise RouteInputError(
            "constraints_sha256 does not match the canonical hash of the constraints artifact",
            code="STALE_INPUT_HASH",
            detail_code="CONSTRAINTS_HASH_MISMATCH",
        )
    return actual


def validate_constraints(constraints: ConstraintsArtifact, *, mode: RuntimeMode) -> None:
    """Structural validation beyond the pydantic model; raises ``RouteInputError`` (-> BLOCKED)."""
    if constraints.resource_provider == "TEST_ONLY_MOCK_GRAPH" and (
        mode != "synthetic" or constraints.mode != "synthetic"
    ):
        raise RouteInputError(
            "the mock graph resource provider is forbidden outside synthetic mode",
            detail_code="MOCK_PROVIDER_FORBIDDEN",
        )
    if constraints.mode != mode:
        raise RouteInputError(
            f"constraints were designed in mode {constraints.mode} but the request runs in {mode}",
            detail_code="MODE_MISMATCH",
        )
    seen: set[str] = set()
    for task in constraints.tasks:
        if task.task_id in seen:
            raise RouteInputError(f"duplicate task id {task.task_id}", detail_code="DUPLICATE_TASK_ID")
        seen.add(task.task_id)
    for spec in constraints.exposures:
        low, high = spec.band_deg
        if not 0.0 <= low < high <= 90.0:
            raise RouteInputError(f"exposure band {spec.band_deg} of {spec.requirement_id} is not 0 <= lo < hi <= 90")
    if len({spec.requirement_id for spec in constraints.exposures}) != len(constraints.exposures):
        raise RouteInputError("duplicate exposure requirement id", detail_code="DUPLICATE_REQUIREMENT_ID")
    if constraints.graph is not None:
        nodes = set(constraints.graph.nodes)
        if len(nodes) != len(constraints.graph.nodes):
            raise RouteInputError("duplicate graph node", detail_code="DUPLICATE_NODE")
        for edge in constraints.graph.edges:
            if edge.a not in nodes or edge.b not in nodes or edge.a == edge.b:
                raise RouteInputError(f"graph edge {edge.a}-{edge.b} references unknown/identical nodes")
        for task in constraints.tasks:
            if task.location.node_id not in nodes:
                raise RouteInputError(f"task {task.task_id} is not a graph node", detail_code="WAYPOINT_UNRESOLVED")
        if constraints.start.node_id not in nodes:
            raise RouteInputError("start is not a graph node", detail_code="WAYPOINT_UNRESOLVED")


# ----------------------------------------------------------------------------------------------- design assembly
@dataclass(frozen=True)
class RouteDesignDefaults:
    """Values normally read from ``config/algorithms.yaml`` (``design_defaults`` / ``route_search``)."""

    max_route_m: float = 8000.0
    task_dwell_s: float = 60.0
    max_expansions: int = 200_000
    max_seconds: int = 30
    max_labels_per_node: int = 32
    seed: int = 0
    footprint_dilation_m: float = 0.0
    graph_max_distance_m: float = 400.0


ROUTE_EXPOSURE_OBSERVABLE: Final = "unique_slope_exposure_m"
ROUTE_TASK_OBSERVABLE: Final = "completed_task_count"
ROUTE_RESERVE_OBSERVABLE: Final = "final_battery_reserve_pct"
GAP_OBSERVABLES: Final = frozenset({"planetary_gravity", "planetary_atmosphere"})
ROUTE_CONTEXT_OBSERVABLES: Final = frozenset({"slope_band_area_fraction", "slope_distribution_w1_deg"})


def exposure_specs_from_requirements(requirements: Sequence[Requirement], rover_cap_deg: float) -> list[ExposureSpec]:
    """One ``ExposureSpec`` per ``unique_slope_exposure_m`` requirement; ``upper_inclusive`` iff band upper == cap."""
    specs: list[ExposureSpec] = []
    for req in requirements:
        if req.observable != ROUTE_EXPOSURE_OBSERVABLE:
            continue
        band = req.parameters.slope_band_deg
        if band is None or len(band) != 2:
            raise RouteInputError(f"requirement {req.id} has no 2-element slope_band_deg", detail_code="BAND_MISSING")
        if req.lower is None:
            raise RouteInputError(
                f"requirement {req.id} has no minimum distance (lower)", detail_code="THRESHOLD_MISSING"
            )
        counting = req.parameters.exposure_counting or "UNIQUE_UNDIRECTED_EDGE_DISTANCE"
        specs.append(
            ExposureSpec(
                requirement_id=req.id,
                metric_id="surface_slope_deg",
                band_deg=(float(band[0]), float(band[1])),
                upper_inclusive=abs(float(band[1]) - rover_cap_deg) < 1e-9,
                minimum_distance_m=float(req.lower),
                counting=counting,
            )
        )
    return specs


def build_requirement_mapping(
    requirements: Sequence[Requirement], tasks: Sequence[TaskSpec], *, energy_evaluable: bool
) -> list[ConstraintMapping]:
    """How each accepted requirement is treated by the route test (08 section 4.9)."""
    from analogforge.ports.catalog import constraint_exposure, constraint_task

    mapping: list[ConstraintMapping] = []
    task_constraints = [constraint_task(t.task_id) for t in tasks]
    for req in requirements:
        obs = req.observable
        if obs == ROUTE_EXPOSURE_OBSERVABLE:
            mapping.append(
                ConstraintMapping(
                    requirement_id=req.id, constraint_ids=[constraint_exposure(req.id)], treatment="VERIFIED_BY_TOOL"
                )
            )
        elif obs == ROUTE_TASK_OBSERVABLE:
            mapping.append(
                ConstraintMapping(requirement_id=req.id, constraint_ids=task_constraints, treatment="VERIFIED_BY_TOOL")
            )
        elif obs == ROUTE_RESERVE_OBSERVABLE:
            if energy_evaluable:
                mapping.append(
                    ConstraintMapping(
                        requirement_id=req.id, constraint_ids=["C-ENERGY-RESERVE"], treatment="VERIFIED_BY_TOOL"
                    )
                )
            else:
                mapping.append(
                    ConstraintMapping(
                        requirement_id=req.id,
                        constraint_ids=["C-ENERGY-RESERVE"],
                        treatment="UNKNOWN",
                        limitation="Rover has no energy model; reserve cannot be evaluated (ENERGY_UNCALIBRATED).",
                    )
                )
        elif obs in GAP_OBSERVABLES or req.operator == "NOT_NATURALLY_REPRODUCIBLE":
            mapping.append(
                ConstraintMapping(
                    requirement_id=req.id,
                    constraint_ids=[],
                    treatment="GAP",
                    limitation="Physical condition that an Earth analog cannot reproduce; not tested by the route.",
                )
            )
        elif obs in ROUTE_CONTEXT_OBSERVABLES:
            mapping.append(
                ConstraintMapping(
                    requirement_id=req.id,
                    constraint_ids=[],
                    treatment="UNKNOWN",
                    limitation="Evaluated from candidate analysis evidence (COMPARE_REQUIREMENT); not a route test.",
                )
            )
        else:
            mapping.append(
                ConstraintMapping(
                    requirement_id=req.id,
                    constraint_ids=[],
                    treatment="UNKNOWN",
                    limitation=f"Observable {obs} cannot be verified by modeled route geometry.",
                )
            )
    return mapping


def required_exposures_of(specs: Sequence[ExposureSpec]) -> list[RequiredExposure]:
    return [
        RequiredExposure(
            requirement_id=s.requirement_id,
            metric_id=s.metric_id,
            lower=s.band_deg[0],
            upper=s.band_deg[1],
            minimum_distance_m=s.minimum_distance_m,
        )
        for s in specs
    ]


def finish_design_payload(
    constraints: ConstraintsArtifact,
    *,
    constraints_artifact_key: str,
    requirements: Sequence[Requirement],
) -> DesignBenchmarkPayload:
    """Wrap a finished artifact into the payload (hash, mapping, required exposures, unverified ids)."""
    provider = make_energy_provider(constraints)
    mapping = build_requirement_mapping(requirements, constraints.tasks, energy_evaluable=provider.evaluable)
    unverified = [m.requirement_id for m in mapping if m.treatment != "VERIFIED_BY_TOOL"]
    return DesignBenchmarkPayload(
        constraints=constraints,
        constraints_artifact_key=constraints_artifact_key,
        constraints_sha256=constraints_sha256(constraints),
        required_exposures=required_exposures_of(constraints.exposures),
        requirement_mapping=mapping,
        unverified_requirement_ids=unverified,
        blockers=[],
    )


def waypoint_xy(waypoint: Waypoint) -> tuple[float, float] | None:
    """Projected (x, y) of a waypoint if it carries them."""
    if waypoint.x_m is not None and waypoint.y_m is not None:
        return waypoint.x_m, waypoint.y_m
    return None
