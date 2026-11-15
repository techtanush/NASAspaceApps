"""Instructions adapt to accepted requirements without creating scientific evidence."""

from copy import deepcopy

from analogforge.application.field_guidance import field_guidance


def test_route_instructions_retain_the_missions_own_band_and_task_identifiers():
    requirement = {"observable": "unique_slope_exposure_m", "parameters": {"slope_band_deg": [7, 11]}}
    original = deepcopy(requirement)
    result = field_guidance(requirement)
    assert "7 to 11 deg" in result["method"] and "12 to 18" not in result["method"]
    assert "only once" in result["method"] and requirement == original
    tasks = field_guidance({"observable": "completed_task_count", "parameters": {"task_ids": ["CORE-A", "IMAGE-B"]}})
    assert "CORE-A, IMAGE-B" in tasks["method"] and "W1" not in tasks["method"]


def test_distinct_capabilities_get_distinct_observation_protocols():
    methods = {
        key: field_guidance({"observable": key})
        for key in [
            "slope_band_area_fraction",
            "slope_distribution_w1_deg",
            "final_battery_reserve_pct",
            "mineral_class_present",
            "surface_temperature_min_k",
            "ground_clearance_m",
        ]
    }
    assert len({value["method"] for value in methods.values()}) == len(methods)
    assert "air-weather" in methods["surface_temperature_min_k"]["method"]
    assert "Regional elevation cells cannot establish" in methods["ground_clearance_m"]["method"]
    assert "assumed calibration" in methods["final_battery_reserve_pct"]["method"]


def test_physical_gaps_and_unrecognized_observables_do_not_get_invented_field_tests():
    gap = field_guidance({"observable": "planetary_gravity", "operator": "NOT_NATURALLY_REPRODUCIBLE"})
    assert "no terrestrial drive can pass" in gap["method"]
    custom = field_guidance({"observable": "custom_rover_sensor", "dimension": "sensor_validation"})
    assert "operator-reviewed measurement protocol" in custom["method"]
    assert "no task or measured performance is inferred" in custom["method"]
