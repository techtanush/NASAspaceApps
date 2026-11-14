"""Configuration values must actually drive the science code that reads them (no dead YAML keys)."""

from __future__ import annotations

import pytest
from test_compatibility import MARS, by_id, rover

from analogforge.ports import catalog
from analogforge.science import compatibility, energy
from analogforge.science.comparison import scale, w1
from analogforge.science.config import default_thresholds, load_config

THRESHOLDS = load_config().algorithms.thresholds


def _patched(monkeypatch: pytest.MonkeyPatch, modules: list[object], **changes: float) -> None:
    patched = THRESHOLDS.model_copy(update=changes)
    for module in modules:
        monkeypatch.setattr(module, "default_thresholds", lambda: patched)


def test_default_thresholds_are_the_repository_yaml() -> None:
    assert default_thresholds() == THRESHOLDS


def test_energy_tolerance_wh_comes_from_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    params = energy.EnergyParams(
        mass_kg=42.0, nominal_speed_mps=0.5, battery_wh=1000.0, min_reserve_pct=20.0, rolling_coefficient=0.06,
        drive_efficiency=0.65, idle_power_w=35.0, science_task_wh=10.0, roughness_multiplier=1.0,
        uncertainty_fraction=0.25,
    )  # fmt: skip
    over = params.usable_energy_wh + 0.5  # half a watt-hour above the usable energy
    assert not energy.meets_reserve(params, over)  # config tolerance is 1e-9 Wh
    _patched(monkeypatch, [energy], energy_tolerance_wh=1.0)
    assert energy.meets_reserve(params, over)  # a looser configured tolerance changes the verdict
    assert not energy.meets_reserve(params, params.usable_energy_wh + 2.0)
    assert not energy.meets_reserve(params, over, tolerance_wh=0.0)  # an explicit argument still wins


def test_numeric_tolerance_comes_from_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    # support window bound: 480.4 m vs maximum 480 m
    assert not scale.check_support_window(480.4, None, 480.0).supported
    # sum-to-one check of the W1 distributions
    with pytest.raises(Exception, match="sum to 1"):
        w1.binned_w1([0.5, 0.4999], [0.5, 0.5], [1.0, 2.0])
    # compatibility: declared slope 17.9 vs required 18
    ares = rover(catalog.ROVER_ARES_1, max_slope_deg=17.9)
    status = lambda: by_id(compatibility.assess_compatibility(ares, MARS).dimensions)["max_surface_slope_deg"].status  # noqa: E731
    assert status() == "FAIL"
    _patched(monkeypatch, [scale, w1, compatibility], numeric_tolerance=0.5)
    assert scale.check_support_window(480.4, None, 480.0).supported
    assert w1.binned_w1([0.5, 0.4999], [0.5, 0.5], [1.0, 2.0]) >= 0.0
    assert status() == "PASS"


def test_earth_default_support_is_consistent_between_grid_and_measurement_spec() -> None:
    cfg = load_config().algorithms
    spec = cfg.measurement_specs[catalog.MEASUREMENT_SPEC_EARTH].comparison_support
    assert cfg.grid.target_support_m.earth_default_m == spec.default_requested_m
    broken = cfg.model_dump(mode="json")
    broken["grid"]["target_support_m"]["earth_default_m"] = 120
    with pytest.raises(ValueError, match="earth_default_m"):
        type(cfg).model_validate(broken)
