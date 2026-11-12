"""SCN-02: the physical Earth energy model ``earth-simple-v1`` against the analytic oracle of architecture 29 s4."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from analogforge.ports import catalog
from analogforge.ports.domain_models import EnergyModel, RoverProfile
from analogforge.ports.science_payloads import EnergySpec
from analogforge.science.energy import (
    EARTH_GRAVITY_MPS2,
    EnergyAccumulator,
    EnergyParams,
    edge_energy,
    evaluate_route_energy,
    flat_lower_bound_wh,
    meets_reserve,
    reserve_pct,
    route_energy,
)
from analogforge.science.errors import ModelError

KIT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "kit"
G = 9.80665


def make(**overrides: float) -> EnergyParams:
    base: dict[str, float] = {
        "mass_kg": 42.0,
        "nominal_speed_mps": 0.5,
        "battery_wh": 1800.0,
        "min_reserve_pct": 20.0,
        "rolling_coefficient": 0.06,
        "drive_efficiency": 0.65,
        "idle_power_w": 35.0,
        "science_task_wh": 10.0,
        "roughness_multiplier": 1.0,
        "uncertainty_fraction": 0.25,
    }
    base.update(overrides)
    return EnergyParams(**base)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- the analytic oracle
def test_flat_1000m_oracle_matches_catalog_within_1e8_wh() -> None:
    result = route_energy(make(), [(1000.0, 0.0)])
    oracle = catalog.ENERGY_ORACLE_FLAT_1000M
    assert result.rolling_wh == pytest.approx(oracle["rolling_wh"], abs=1e-8)
    assert result.idle_wh == pytest.approx(oracle["idle_wh"], abs=1e-8)
    assert result.nominal_wh == pytest.approx(oracle["nominal_wh"], abs=1e-8)
    assert result.conservative_wh == pytest.approx(oracle["conservative_wh"], abs=1e-8)
    assert result.reserve_pct == pytest.approx(oracle["reserve_pct"], abs=1e-9)
    assert result.climb_wh == 0.0 and result.tasks_wh == 0.0
    assert result.duration_s == 2000.0 and result.distance_surface_m == 1000.0


def test_oracle_is_independent_hand_arithmetic_not_the_function_under_test() -> None:
    rolling = 1.0 * 0.06 * 42.0 * G * 1000.0 / 0.65 / 3600.0
    idle = 35.0 * (1000.0 / 0.5) / 3600.0
    assert rolling == pytest.approx(10.5610076923, abs=1e-9) and idle == pytest.approx(19.4444444444, abs=1e-9)
    nominal = rolling + idle
    assert nominal * 1.25 == pytest.approx(37.5068151710, abs=1e-9)
    assert 100 * (1800 - nominal * 1.25) / 1800 == pytest.approx(97.9162880461, abs=1e-9)


def test_oracle_from_the_kit_rover_profile() -> None:
    rover = RoverProfile.model_validate(json.loads((KIT / "rovers" / "ares-1.json").read_text()) | _identity())
    params = EnergyParams.from_model(
        rover.energy_model,
        mass_kg=rover.mass_kg,
        nominal_speed_mps=rover.nominal_speed_mps,
        battery_wh=rover.battery_wh,
        min_reserve_pct=rover.min_reserve_pct,
    )
    assert params is not None
    assert params.calibration_status == "ASSUMED" and params.model_id == "earth-simple-v1"
    assert route_energy(params, [(1000.0, 0.0)]).conservative_wh == pytest.approx(
        catalog.ENERGY_ORACLE_FLAT_1000M["conservative_wh"], abs=1e-8
    )
    assert params.usable_energy_wh == pytest.approx(1440.0)


def _identity() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "id": "00000000-0000-4000-8000-000000000001",
        "rover_id": "00000000-0000-4000-8000-000000000002",
        "workspace_id": "00000000-0000-4000-8000-000000000003",
        "revision": 1,
        "created_at": "2026-11-05T00:00:00Z",
        "content_sha256": "0" * 64,
    }


# ----------------------------------------------------------------------------- scaling relations
def test_doubling_mass_doubles_rolling_and_climb_but_not_idle() -> None:
    a = route_energy(make(), [(500.0, 20.0)])
    b = route_energy(make(mass_kg=84.0), [(500.0, 20.0)])
    assert b.rolling_wh == pytest.approx(2 * a.rolling_wh, rel=1e-12)
    assert b.climb_wh == pytest.approx(2 * a.climb_wh, rel=1e-12) and a.climb_wh > 0
    assert b.idle_wh == pytest.approx(a.idle_wh, rel=1e-12)


def test_doubling_flat_distance_doubles_a_no_task_route() -> None:
    a = route_energy(make(), [(700.0, 0.0)])
    b = route_energy(make(), [(1400.0, 0.0)])
    assert b.nominal_wh == pytest.approx(2 * a.nominal_wh, rel=1e-12)
    assert b.conservative_wh == pytest.approx(2 * a.conservative_wh, rel=1e-12)
    split = route_energy(make(), [(700.0, 0.0), (700.0, 0.0)])
    assert split.nominal_wh == pytest.approx(b.nominal_wh, rel=1e-12)


def test_doubling_speed_halves_idle_but_not_rolling() -> None:
    slow = route_energy(make(), [(1000.0, 0.0)])
    fast = route_energy(make(nominal_speed_mps=1.0), [(1000.0, 0.0)])
    assert fast.idle_wh == pytest.approx(slow.idle_wh / 2, rel=1e-12)
    assert fast.rolling_wh == pytest.approx(slow.rolling_wh, rel=1e-12)
    assert fast.drive_time_s == pytest.approx(slow.drive_time_s / 2)


def test_rolling_resistance_coefficient_and_roughness_scale_rolling_linearly() -> None:
    base = route_energy(make(), [(1000.0, 0.0)]).rolling_wh
    assert route_energy(make(rolling_coefficient=0.12), [(1000.0, 0.0)]).rolling_wh == pytest.approx(2 * base)
    assert route_energy(make(roughness_multiplier=1.5), [(1000.0, 0.0)]).rolling_wh == pytest.approx(1.5 * base)
    assert route_energy(make(drive_efficiency=0.325), [(1000.0, 0.0)]).rolling_wh == pytest.approx(2 * base)


# ----------------------------------------------------------------------------- climbing, no regeneration
def test_downhill_earns_no_credit_and_uphill_pays_climb_work() -> None:
    p = make()
    flat = edge_energy(p, 100.0, 0.0)
    down = edge_energy(p, 100.0, -25.0)
    up = edge_energy(p, 100.0, 25.0)
    assert down.climb_wh == 0.0 and down.drive_wh == pytest.approx(flat.drive_wh, rel=1e-12)  # same rolling, no credit
    assert down.drive_time_s > flat.drive_time_s  # the surface path is longer
    assert up.climb_wh == pytest.approx(42.0 * G * 25.0 / 0.65 / 3600.0, rel=1e-12)
    assert up.d_s_m == pytest.approx(math.hypot(100.0, 25.0)) and up.drive_wh > down.drive_wh
    assert (
        down.drive_wh >= 0
        and route_energy(p, [(100.0, -25.0)]).nominal_wh >= route_energy(p, [(100.0, 0.0)]).nominal_wh
    )


def test_out_and_back_includes_the_climbing_work_exactly_once() -> None:
    p = make()
    out_and_back = route_energy(p, [(200.0, 40.0), (200.0, -40.0)])
    assert out_and_back.climb_wh == pytest.approx(42.0 * G * 40.0 / 0.65 / 3600.0, rel=1e-12)
    two_up_two_down = route_energy(p, [(100.0, 10.0), (100.0, 10.0), (100.0, -10.0), (100.0, -10.0)])
    assert two_up_two_down.climb_wh == pytest.approx(42.0 * G * 20.0 / 0.65 / 3600.0, rel=1e-12)
    assert out_and_back.rolling_wh == pytest.approx(route_energy(p, [(400.0, 0.0)]).rolling_wh, rel=1e-12)


def test_edge_geometry_uses_surface_length() -> None:
    e = edge_energy(make(), 30.0, 40.0)
    assert e.d_s_m == 50.0 and e.drive_time_s == 100.0
    default = edge_energy(make(), 30.0, 40.0)
    slope = math.degrees(math.atan2(40.0, 30.0))
    explicit = edge_energy(make(), 30.0, 40.0, surface_slope_deg=slope)
    assert explicit.rolling_wh == pytest.approx(default.rolling_wh, rel=1e-12)
    steeper = edge_energy(make(), 30.0, 40.0, surface_slope_deg=80.0)
    assert steeper.rolling_wh < default.rolling_wh
    with pytest.raises(ModelError):
        edge_energy(make(), 30.0, 40.0, surface_slope_deg=90.0)
    with pytest.raises(ModelError):
        edge_energy(make(), -1.0, 0.0)
    with pytest.raises(ModelError):
        edge_energy(make(), 1.0, float("nan"))


# ----------------------------------------------------------------------------- tasks, dwell, margin, reserve
def test_task_dwell_and_energy_are_charged_once_per_completed_task() -> None:
    p = make()
    none = route_energy(p, [(1000.0, 0.0)])
    two = route_energy(p, [(1000.0, 0.0)], tasks_completed=2, dwell_s_total=120.0)
    assert two.tasks_wh == 20.0  # science_task_wh is the increment ABOVE idle
    assert two.idle_wh - none.idle_wh == pytest.approx(35.0 * 120.0 / 3600.0)  # idle power is paid during dwell
    assert two.nominal_wh - none.nominal_wh == pytest.approx(20.0 + 35.0 * 120.0 / 3600.0)
    assert two.duration_s == 2120.0
    four = route_energy(p, [(1000.0, 0.0)], tasks_completed=4, dwell_s_total=240.0)
    assert four.tasks_wh == 40.0 and four.nominal_wh - none.nominal_wh == pytest.approx(
        2 * (two.nominal_wh - none.nominal_wh)
    )
    with pytest.raises(ModelError):
        route_energy(p, [], tasks_completed=-1)
    with pytest.raises(ModelError):
        route_energy(p, [], dwell_s_total=-1.0)


def test_conservative_margin_changes_reserve_and_zero_margin_equals_nominal() -> None:
    edges = [(1000.0, 0.0)]
    margin = route_energy(make(), edges)
    no_margin = route_energy(make(uncertainty_fraction=0.0), edges)
    assert no_margin.conservative_wh == pytest.approx(no_margin.nominal_wh, rel=1e-15)
    assert margin.conservative_wh == pytest.approx(1.25 * margin.nominal_wh, rel=1e-15)
    assert margin.reserve_pct < no_margin.reserve_pct


def test_exact_reserve_equality_passes_and_one_part_in_a_million_over_fails() -> None:
    # nominal 64 Wh (one 64 Wh task, no drive, no idle) * 1.25 = 80 Wh = the usable energy of 100 Wh at 20 % reserve
    p = make(battery_wh=100.0, min_reserve_pct=20.0, science_task_wh=64.0, idle_power_w=0.0, rolling_coefficient=0.0)
    r = route_energy(p, [], tasks_completed=1)
    assert r.conservative_wh == 80.0 and p.usable_energy_wh == 80.0 and r.reserve_pct == 20.0
    assert meets_reserve(p, r.conservative_wh)
    over = route_energy(
        make(battery_wh=100.0, science_task_wh=64.000064, idle_power_w=0.0, rolling_coefficient=0.0),
        [],
        tasks_completed=1,
    )
    assert not meets_reserve(p, over.conservative_wh) and over.reserve_pct < 20.0


def test_negative_reserve_is_reported_never_clamped() -> None:
    r = route_energy(make(battery_wh=30.0), [(2000.0, 0.0)])
    assert r.reserve_pct < 0 and r.reserve_pct == pytest.approx(100 * (30.0 - r.conservative_wh) / 30.0)
    assert reserve_pct(100.0, 130.0) == -30.0
    assert not meets_reserve(make(battery_wh=30.0), r.conservative_wh)
    with pytest.raises(ModelError):
        reserve_pct(0.0, 1.0)


# ----------------------------------------------------------------------------- validation and unknowns
@pytest.mark.parametrize(
    "bad",
    [
        {"drive_efficiency": 0.0},
        {"drive_efficiency": 1.5},
        {"drive_efficiency": -0.2},
        {"drive_efficiency": float("nan")},
        {"drive_efficiency": float("inf")},
        {"mass_kg": 0.0},
        {"mass_kg": -1.0},
        {"nominal_speed_mps": 0.0},
        {"battery_wh": 0.0},
        {"min_reserve_pct": 101.0},
        {"min_reserve_pct": -1.0},
        {"rolling_coefficient": 1.2},
        {"rolling_coefficient": -0.01},
        {"idle_power_w": -1.0},
        {"science_task_wh": -1.0},
        {"roughness_multiplier": 0.99},
        {"uncertainty_fraction": 1.01},
        {"gravity_mps2": 3.71},
        {"gravity_mps2": 1.62},
    ],
)
def test_invalid_model_parameters_are_rejected(bad: dict[str, float]) -> None:
    with pytest.raises(ModelError):
        make(**bad)


def test_earth_gravity_is_the_only_gravity() -> None:
    assert EARTH_GRAVITY_MPS2 == 9.80665 == make().gravity_mps2
    # Mars gravity would change rolling energy by 3.71/9.80665: prove the Earth constant is what is used
    assert route_energy(make(), [(1000.0, 0.0)]).rolling_wh == pytest.approx(
        0.06 * 42.0 * 9.80665 * 1000.0 / 0.65 / 3600.0, abs=1e-12
    )


def test_missing_energy_model_is_unknown_not_zero() -> None:
    assert (
        EnergyParams.from_model(None, mass_kg=42.0, nominal_speed_mps=0.5, battery_wh=1800.0, min_reserve_pct=20.0)
        is None
    )
    assert evaluate_route_energy(None, [(1000.0, 0.0)]) is None
    spec = EnergySpec(model=None, battery_wh=1800.0, min_reserve_pct=20.0, rover_mass_kg=42.0, nominal_speed_mps=0.5)
    assert EnergyParams.from_spec(spec) is None
    model = EnergyModel(
        model_id="earth-simple-v1",
        rolling_coefficient=0.06,
        drive_efficiency=0.65,
        idle_power_w=35.0,
        science_task_wh=10.0,
        roughness_multiplier=1.0,
        uncertainty_fraction=0.25,
        calibration_status="ASSUMED",
        calibration_evidence_id=None,
    )
    spec2 = EnergySpec(model=model, battery_wh=1800.0, min_reserve_pct=20.0, rover_mass_kg=42.0, nominal_speed_mps=0.5)
    params = EnergyParams.from_spec(spec2)
    assert params == make()
    direct = evaluate_route_energy(params, [(1000.0, 0.0)])
    assert direct is not None and direct.reserve_pct == pytest.approx(
        catalog.ENERGY_ORACLE_FLAT_1000M["reserve_pct"], abs=1e-9
    )


# ----------------------------------------------------------------------------- accumulator and bounds
def test_accumulator_is_monotone_and_ends_at_the_route_total() -> None:
    p = make()
    acc = EnergyAccumulator(p)
    seen = [acc.total().conservative_wh]
    edges = [(100.0, 5.0), (120.0, -3.0), (80.0, 0.0)]
    for d, dz in edges:
        acc.add_edge(d, dz)
        seen.append(acc.total().conservative_wh)
    acc.add_tasks(1, 60.0)
    seen.append(acc.total().conservative_wh)
    assert seen[0] == 0.0 and all(b > a for a, b in zip(seen, seen[1:], strict=False))
    assert acc.total() == route_energy(p, edges, tasks_completed=1, dwell_s_total=60.0)


def test_flat_lower_bound_is_admissible_and_tight_on_flat_terrain() -> None:
    p = make()
    assert flat_lower_bound_wh(p, 0.0) == 0.0
    flat = route_energy(p, [(900.0, 0.0)], tasks_completed=2, dwell_s_total=120.0)
    assert flat_lower_bound_wh(p, 900.0, tasks=2, dwell_s_total=120.0) == pytest.approx(flat.conservative_wh, rel=1e-12)
    for edges in ([(300.0, 50.0), (600.0, -50.0)], [(450.0, -10.0), (450.0, 10.0)], [(900.0, 120.0)]):
        real = route_energy(p, edges, tasks_completed=2, dwell_s_total=120.0)
        assert flat_lower_bound_wh(p, 900.0, tasks=2, dwell_s_total=120.0) <= real.conservative_wh + 1e-12
