"""Physical Earth energy model ``earth-simple-v1`` (architecture 12 section 5).

For every directed edge with horizontal length ``d_xy`` and endpoint height change ``dz`` (difference of the two node
cell-centre elevations, no interpolation)::

    d_s       = sqrt(d_xy^2 + dz^2)            modeled surface length
    t_drive   = d_s / nominal_speed
    E_roll_J  = k_r * Crr * m * g * cos(theta_s) * d_s / eta        (cos(theta_s) * d_s = d_xy for a planar edge)
    E_climb_J = m * g * max(dz, 0) / eta                            (no regeneration: downhill earns nothing)
    E_drive_Wh = (E_roll_J + E_climb_J) / 3600

and for a route ``E_idle_Wh = P_idle * (sum t_drive + sum dwell) / 3600``, ``E_tasks_Wh = science_task_wh * tasks``
(the incremental per-task energy *above* idle), ``E_nominal = drive + idle + tasks``,
``E_conservative = E_nominal * (1 + uncertainty_fraction)`` and
``reserve_pct = 100 * (battery - E_conservative) / battery`` (negative values are reported, never clamped).

Gravity is the Earth field-test value ``9.80665 m/s^2``: a Mars or Moon gravity can never enter this model.  A
missing energy model yields ``None`` (unknown), never zero consumption.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from analogforge.ports.domain_models import EnergyModel
from analogforge.ports.science_payloads import EnergySpec
from analogforge.science.config import default_thresholds
from analogforge.science.errors import ModelError

EARTH_GRAVITY_MPS2: Final = 9.80665
JOULES_PER_WH: Final = 3600.0


def _finite(name: str, value: float) -> float:
    if not isinstance(value, numbers.Real) or isinstance(value, bool) or not math.isfinite(value):
        raise ModelError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class EnergyParams:
    """Validated parameters of ``earth-simple-v1`` plus the rover quantities the model needs."""

    mass_kg: float
    nominal_speed_mps: float
    battery_wh: float
    min_reserve_pct: float
    rolling_coefficient: float
    drive_efficiency: float
    idle_power_w: float
    science_task_wh: float
    roughness_multiplier: float
    uncertainty_fraction: float
    calibration_status: Literal["ASSUMED", "CALIBRATED"] = "ASSUMED"
    gravity_mps2: float = EARTH_GRAVITY_MPS2
    model_id: str = "earth-simple-v1"

    def __post_init__(self) -> None:
        for name in (
            "mass_kg",
            "nominal_speed_mps",
            "battery_wh",
            "min_reserve_pct",
            "rolling_coefficient",
            "drive_efficiency",
            "idle_power_w",
            "science_task_wh",
            "roughness_multiplier",
            "uncertainty_fraction",
            "gravity_mps2",
        ):
            _finite(name, getattr(self, name))
        if self.gravity_mps2 != EARTH_GRAVITY_MPS2:
            raise ModelError("the Earth field-test energy model uses g = 9.80665 m/s^2 only")
        if not self.mass_kg > 0:
            raise ModelError("mass_kg must be positive")
        if not self.nominal_speed_mps > 0:
            raise ModelError("nominal_speed_mps must be positive")
        if not self.battery_wh > 0:
            raise ModelError("battery_wh must be positive")
        if not 0.0 <= self.min_reserve_pct <= 100.0:
            raise ModelError("min_reserve_pct must lie in [0, 100]")
        if not 0.0 <= self.rolling_coefficient <= 1.0:
            raise ModelError("rolling_coefficient must lie in [0, 1]")
        if not 0.0 < self.drive_efficiency <= 1.0:
            raise ModelError("drive_efficiency must lie in (0, 1]")
        if self.idle_power_w < 0 or self.science_task_wh < 0:
            raise ModelError("idle_power_w and science_task_wh must be >= 0")
        if self.roughness_multiplier < 1.0:
            raise ModelError("roughness_multiplier must be >= 1")
        if not 0.0 <= self.uncertainty_fraction <= 1.0:
            raise ModelError("uncertainty_fraction must lie in [0, 1]")

    @property
    def usable_energy_wh(self) -> float:
        """Energy that may be consumed while keeping ``min_reserve_pct``."""
        return self.battery_wh * (1.0 - self.min_reserve_pct / 100.0)

    @classmethod
    def from_model(
        cls,
        model: EnergyModel | None,
        *,
        mass_kg: float,
        nominal_speed_mps: float,
        battery_wh: float,
        min_reserve_pct: float,
    ) -> EnergyParams | None:
        """Parameters from a rover's :class:`EnergyModel`; ``None`` when the rover has no model (unknown)."""
        if model is None:
            return None
        return cls(
            mass_kg=mass_kg,
            nominal_speed_mps=nominal_speed_mps,
            battery_wh=battery_wh,
            min_reserve_pct=min_reserve_pct,
            rolling_coefficient=model.rolling_coefficient,
            drive_efficiency=model.drive_efficiency,
            idle_power_w=model.idle_power_w,
            science_task_wh=model.science_task_wh,
            roughness_multiplier=model.roughness_multiplier,
            uncertainty_fraction=model.uncertainty_fraction,
            calibration_status=model.calibration_status,
            model_id=model.model_id,
        )

    @classmethod
    def from_spec(cls, spec: EnergySpec) -> EnergyParams | None:
        """Parameters from a frozen constraints :class:`EnergySpec` (``None`` when ``spec.model`` is null)."""
        return cls.from_model(
            spec.model,
            mass_kg=spec.rover_mass_kg,
            nominal_speed_mps=spec.nominal_speed_mps,
            battery_wh=spec.battery_wh,
            min_reserve_pct=spec.min_reserve_pct,
        )


@dataclass(frozen=True)
class EdgeEnergy:
    """Energy of one directed edge (drive terms only; idle and tasks are route-level)."""

    d_xy_m: float
    dz_m: float
    d_s_m: float
    rolling_wh: float
    climb_wh: float
    drive_time_s: float

    @property
    def drive_wh(self) -> float:
        return self.rolling_wh + self.climb_wh


def edge_energy(
    params: EnergyParams, d_xy_m: float, dz_m: float, *, surface_slope_deg: float | None = None
) -> EdgeEnergy:
    """Drive energy of a directed edge.

    ``surface_slope_deg`` optionally overrides the edge-aligned slope used in the ``cos(theta_s)`` rolling term;
    by default ``theta_s = atan(|dz| / d_xy)`` so that ``cos(theta_s) * d_s = d_xy``.
    """
    d_xy = _finite("d_xy_m", d_xy_m)
    dz = _finite("dz_m", dz_m)
    if d_xy < 0:
        raise ModelError("d_xy_m must be >= 0")
    d_s = math.hypot(d_xy, dz)
    if surface_slope_deg is None:
        rolling_length = d_xy
    else:
        slope = _finite("surface_slope_deg", surface_slope_deg)
        if not 0.0 <= slope < 90.0:
            raise ModelError("surface_slope_deg must lie in [0, 90)")
        rolling_length = math.cos(math.radians(slope)) * d_s
    mg = params.mass_kg * params.gravity_mps2
    rolling_j = params.roughness_multiplier * params.rolling_coefficient * mg * rolling_length / params.drive_efficiency
    climb_j = mg * max(dz, 0.0) / params.drive_efficiency
    return EdgeEnergy(
        d_xy_m=d_xy,
        dz_m=dz,
        d_s_m=d_s,
        rolling_wh=rolling_j / JOULES_PER_WH,
        climb_wh=climb_j / JOULES_PER_WH,
        drive_time_s=d_s / params.nominal_speed_mps,
    )


@dataclass(frozen=True)
class RouteEnergy:
    """Energy of a whole route."""

    distance_xy_m: float
    distance_surface_m: float
    rolling_wh: float
    climb_wh: float
    idle_wh: float
    tasks_wh: float
    drive_time_s: float
    dwell_s: float
    nominal_wh: float
    conservative_wh: float
    reserve_pct: float

    @property
    def duration_s(self) -> float:
        return self.drive_time_s + self.dwell_s


def reserve_pct(battery_wh: float, conservative_wh: float) -> float:
    """``100 * (battery - conservative) / battery``; negative when the battery is overdrawn (never clamped)."""
    if not _finite("battery_wh", battery_wh) > 0:
        raise ModelError("battery_wh must be positive")
    return 100.0 * (battery_wh - _finite("conservative_wh", conservative_wh)) / battery_wh


def route_energy(
    params: EnergyParams,
    edges: Sequence[tuple[float, float]],
    *,
    tasks_completed: int = 0,
    dwell_s_total: float = 0.0,
) -> RouteEnergy:
    """Energy of the directed edges ``[(d_xy_m, dz_m), ...]`` plus ``tasks_completed`` tasks and their dwell."""
    if tasks_completed < 0:
        raise ModelError("tasks_completed must be >= 0")
    dwell = _finite("dwell_s_total", dwell_s_total)
    if dwell < 0:
        raise ModelError("dwell_s_total must be >= 0")
    acc = EnergyAccumulator(params)
    for d_xy, dz in edges:
        acc.add_edge(d_xy, dz)
    acc.add_tasks(tasks_completed, dwell)
    return acc.total()


class EnergyAccumulator:
    """Running route energy, so telemetry can read the cumulative value at every node."""

    def __init__(self, params: EnergyParams) -> None:
        self._p = params
        self._xy = 0.0
        self._surface = 0.0
        self._rolling_wh = 0.0
        self._climb_wh = 0.0
        self._drive_s = 0.0
        self._dwell_s = 0.0
        self._tasks = 0

    def add_edge(self, d_xy_m: float, dz_m: float, *, surface_slope_deg: float | None = None) -> EdgeEnergy:
        edge = edge_energy(self._p, d_xy_m, dz_m, surface_slope_deg=surface_slope_deg)
        self._xy += edge.d_xy_m
        self._surface += edge.d_s_m
        self._rolling_wh += edge.rolling_wh
        self._climb_wh += edge.climb_wh
        self._drive_s += edge.drive_time_s
        return edge

    def add_tasks(self, count: int, dwell_s: float) -> None:
        """Charge ``count`` completed tasks (once each) and their total dwell time (idle power is paid in dwell)."""
        if count < 0 or _finite("dwell_s", dwell_s) < 0:
            raise ModelError("task count and dwell must be >= 0")
        self._tasks += count
        self._dwell_s += dwell_s

    def total(self) -> RouteEnergy:
        p = self._p
        idle_wh = p.idle_power_w * (self._drive_s + self._dwell_s) / JOULES_PER_WH
        tasks_wh = p.science_task_wh * self._tasks
        nominal = self._rolling_wh + self._climb_wh + idle_wh + tasks_wh
        conservative = nominal * (1.0 + p.uncertainty_fraction)
        return RouteEnergy(
            distance_xy_m=self._xy,
            distance_surface_m=self._surface,
            rolling_wh=self._rolling_wh,
            climb_wh=self._climb_wh,
            idle_wh=idle_wh,
            tasks_wh=tasks_wh,
            drive_time_s=self._drive_s,
            dwell_s=self._dwell_s,
            nominal_wh=nominal,
            conservative_wh=conservative,
            reserve_pct=reserve_pct(p.battery_wh, conservative),
        )


def evaluate_route_energy(
    params: EnergyParams | None,
    edges: Sequence[tuple[float, float]],
    *,
    tasks_completed: int = 0,
    dwell_s_total: float = 0.0,
) -> RouteEnergy | None:
    """Like :func:`route_energy` but ``None`` (unknown, ``ENERGY_UNCALIBRATED``) when there is no energy model."""
    if params is None:
        return None
    return route_energy(params, edges, tasks_completed=tasks_completed, dwell_s_total=dwell_s_total)


def meets_reserve(params: EnergyParams, conservative_wh: float, tolerance_wh: float | None = None) -> bool:
    """Hard constraint ``E_conservative <= battery * (1 - min_reserve/100)`` (equality passes).

    ``tolerance_wh`` defaults to ``thresholds.energy_tolerance_wh`` of ``config/algorithms.yaml``.
    """
    if tolerance_wh is None:
        tolerance_wh = default_thresholds().energy_tolerance_wh
    return _finite("conservative_wh", conservative_wh) <= params.usable_energy_wh + tolerance_wh


def flat_lower_bound_wh(
    params: EnergyParams, distance_xy_m: float, *, tasks: int = 0, dwell_s_total: float = 0.0
) -> float:
    """Admissible lower bound on the *conservative* energy of any route with this horizontal length.

    Elevation changes only add climb work and drive time, so the flat-terrain cost with the same horizontal
    distance, tasks and dwell is a lower bound (used by lossless energy certificates).
    """
    return route_energy(
        params, [(distance_xy_m, 0.0)] if distance_xy_m > 0 else [], tasks_completed=tasks, dwell_s_total=dwell_s_total
    ).conservative_wh
