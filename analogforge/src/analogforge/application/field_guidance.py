"""Procedural reading aids, never measurements, new acceptance rules, or field authorization."""

from typing import Any


def field_guidance(requirement: dict[str, Any]) -> dict[str, str]:
    observable = requirement.get("observable")
    parameters = requirement.get("parameters") or {}
    band = parameters.get("slope_band_deg")
    band_text = (
        f"{band[0]} to {band[1]} deg" if isinstance(band, list) and len(band) == 2 else "the accepted slope band"
    )
    task_ids = parameters.get("task_ids") or []
    tasks = ", ".join(str(value) for value in task_ids) or "the accepted science tasks"
    methods = {
        "slope_band_area_fraction": (
            "Terrain availability for mobility rehearsal",
            "Survey the assessed region at the stated comparison support. "
            f"Classify valid terrain cells in {band_text}; "
            "report their area divided by the valid surveyed area. "
            "This checks site suitability, not wheel performance.",
            "Survey bounds, valid-area mask, cell support, slope measurements and area fraction.",
        ),
        "slope_distribution_w1_deg": (
            "Target-to-Earth terrain similarity",
            "Build Earth and target slope distributions at the same registered support and units. Compare their "
            "Wasserstein-1 distance with the accepted limit. A drive alone cannot establish this regional comparison.",
            "Both histograms, valid-area coverage, common support and distribution distance.",
        ),
        "unique_slope_exposure_m": (
            "Mobility and slope-exposure rehearsal",
            f"After survey and route approval, follow this site’s recorded start, checkpoints and finish. "
            f"Log position and ground slope; count each traversed segment in {band_text} only once, "
            "then compare the unique distance with the accepted benchmark.",
            "Georeferenced track, unique segment lengths, slope samples, wheel-slip and recovery observations.",
        ),
        "completed_task_count": (
            "Assigned science-task capability",
            f"At the recorded checkpoints, perform {tasks} using the capability named for each task. "
            "Record completion and dwell time on the same route. "
            "Procedural waypoints do not establish mineral presence.",
            "Checkpoint positions, assigned task IDs, instrument outputs, dwell times and completion records.",
        ),
        "final_battery_reserve_pct": (
            "Energy reserve and return capability",
            "Record usable battery capacity and starting charge, drive the approved route with its assigned tasks, "
            "and measure remaining charge at the recorded finish or required return point. Compare reserve with the "
            "accepted percentage; keep the model’s assumed calibration separate from physical observations.",
            "Start/end charge, usable capacity, power over time, task loads, elapsed time and calibration uncertainty.",
        ),
        "surface_temperature_min_k": (
            "Thermal environment and hardware follow-up",
            "Measure the accepted surface-temperature quantity with calibrated sensors over the mission’s specified "
            "time window and support. Compare in the accepted units. Earth air-weather readings cannot substitute "
            "for planetary surface temperature; unmatched extremes need a separate thermal facility.",
            "Sensor type, surface versus air quantity, observation window, units, calibration and minimum temperature.",
        ),
        "mineral_class_present": (
            "Geological sampling and instrument context",
            "Check the accepted mineral class against qualified geological observations or calibrated field assays "
            "inside this region. Record sample provenance and uncertainty. Terrain imagery or a completed sampling "
            "waypoint cannot establish composition.",
            "Sample coordinates, assay or instrument evidence, class identification and detection limits.",
        ),
        "ground_clearance_m": (
            "Clearance and obstacle negotiation",
            "Survey obstacles at rover scale along the approved corridor. Compare measured heights and underbody "
            "clearance with the accepted criterion and declared rover geometry before any controlled traversal. "
            "Regional elevation cells cannot establish wheel-scale clearance.",
            "Obstacle dimensions, rover geometry, measured clearances, track and contact/recovery observations.",
        ),
    }
    if requirement.get("operator") == "NOT_NATURALLY_REPRODUCIBLE":
        focus, method, record = (
            "Planetary transfer gap",
            "This condition cannot be reproduced naturally by choosing an Earth location. Plan a separately "
            "specified facility test or transfer analysis; no terrestrial drive can pass this planetary criterion.",
            "The declared transfer gap and the separate validation method; no invented Earth measurement.",
        )
    else:
        focus, method, record = methods.get(
            observable,
            (
                str(requirement.get("dimension") or "Mission-specific capability").replace("_", " "),
                "Define an operator-reviewed measurement protocol for this accepted observable before field execution. "
                "Use the stated units, support and acceptance rule; no task or measured performance is inferred.",
                "The approved measurement protocol, source observations, calibration and uncertainty.",
            ),
        )
    return {"focus": focus, "method": method, "record": record}
