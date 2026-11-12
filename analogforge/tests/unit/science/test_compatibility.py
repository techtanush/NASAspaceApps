"""ASSESS_COMPATIBILITY logic (guide 08 s4.8) against the practice rovers and the Mars mission contract."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import MeasuredMetric, Requirement, RoverProfile
from analogforge.ports.science_payloads import (
    AssessCompatibilityPayload,
    CompatibilityDimension,
    ConstraintsArtifact,
    EnergySpec,
    GraphEdge,
    GraphSpec,
    TaskSpec,
    VerificationSummary,
    Waypoint,
)
from analogforge.science.compatibility import (
    assess_compatibility,
    required_capabilities,
    verified_route_supplied,
)

KIT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "kit"
IDENTITY = {
    "schema_version": "1.0",
    "id": "00000000-0000-4000-8000-000000000001",
    "rover_id": "00000000-0000-4000-8000-000000000002",
    "workspace_id": "00000000-0000-4000-8000-000000000003",
    "revision": 1,
    "created_at": "2026-11-05T00:00:00Z",
    "content_sha256": "0" * 64,
}


def rover(name: str, **changes: object) -> RoverProfile:
    raw = json.loads((KIT / "rovers" / catalog.PRACTICE_ROVER_FILES[name].split("/")[1]).read_text())
    return RoverProfile.model_validate({**raw, **IDENTITY, **changes})


def _requirements(mission: str) -> list[Requirement]:
    raw = json.loads((KIT / "missions" / mission).read_text())["requirements"]
    return [Requirement.model_validate(r) for r in raw]


MARS = _requirements("mission-mars-mobility.json")
MOON = _requirements("mission-moon-gap.json")


def metric(metric_id: str, value: float | None, unit: str = "m") -> MeasuredMetric:
    return MeasuredMetric(
        metric_id=metric_id,
        value=value,
        unit=unit,
        support_scale_m=60.0,
        quantity_kind="DERIVED",
        method_id="t",
        valid_fraction=1.0,
        uncertainty_note="nominal",
    )


def verification(distance: float | None = 230.0, reserve: float | None = 98.3) -> VerificationSummary:
    metrics = [metric("route_distance_m", distance), metric("reserve_pct", reserve, "percent")]
    return VerificationSummary(outcome="PASS", failure_category=None, metrics=metrics)


def by_id(dims: tuple[CompatibilityDimension, ...]) -> dict[str, CompatibilityDimension]:
    assert len({d.metric_id for d in dims}) == len(dims)
    return {d.metric_id: d for d in dims}


# ----------------------------------------------------------------------------- preliminary table of architecture 40 s5
def test_ares_1_preliminary_compatibility_matches_architecture_40() -> None:
    result = assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, candidate_support_scale_m=60.0)
    assert result.preliminary
    dims = by_id(result.dimensions)
    assert [d.metric_id for d in result.dimensions] == [
        "max_surface_slope_deg",
        "energy_reserve_pct",
        "ground_clearance_m",
        "max_obstacle_height_m",
        "required_capability:geological_sampling",
    ]
    slope = dims["max_surface_slope_deg"]
    assert (slope.status, slope.rover_value, slope.required_value, slope.unit) == ("PASS", 18.0, 18.0, "deg")
    assert "declared" in slope.explanation
    assert dims["energy_reserve_pct"].status == "UNKNOWN" and dims["energy_reserve_pct"].rover_value is None
    assert dims["ground_clearance_m"].status == "UNKNOWN" and "coarser" in dims["ground_clearance_m"].explanation
    assert dims["max_obstacle_height_m"].status == "UNKNOWN" and dims["max_obstacle_height_m"].rover_value is None
    cap = dims["required_capability:geological_sampling"]
    assert cap.status == "PASS" and "declared, not observed" in cap.explanation
    assert "route_length_m" not in dims  # ARES-1 states no max_route_m


def test_slope_capability_is_computed_from_the_rover_not_the_scenario() -> None:
    lite = assess_compatibility(rover(catalog.ROVER_PRACTICE_LITE), MARS)
    assert by_id(lite.dimensions)["max_surface_slope_deg"].status == "FAIL"
    for limit, expected in ((17.9, "FAIL"), (18.0, "PASS"), (30.0, "PASS"), (14.0, "FAIL")):
        dims = by_id(assess_compatibility(rover(catalog.ROVER_ARES_1, max_slope_deg=limit), MARS).dimensions)
        assert dims["max_surface_slope_deg"].status == expected, limit
    # the requirement drives it: no slope band -> unknown; a steeper band than the rover climbs -> FAIL
    no_band = [r for r in MARS if r.parameters.slope_band_deg is None]
    unknown = by_id(assess_compatibility(rover(catalog.ROVER_ARES_1), no_band).dimensions)
    assert unknown["max_surface_slope_deg"].status == "UNKNOWN"
    steeper_params = MARS[0].parameters.model_copy(update={"slope_band_deg": [20.0, 25.0]})
    steeper = MARS[0].model_copy(update={"parameters": steeper_params})
    dims = by_id(assess_compatibility(rover(catalog.ROVER_ARES_1), [steeper]).dimensions)
    assert dims["max_surface_slope_deg"].status == "FAIL" and dims["max_surface_slope_deg"].required_value == 25.0


def test_moon_site_only_mission_has_no_capability_dimension() -> None:
    dims = by_id(assess_compatibility(rover(catalog.ROVER_ARES_1), MOON).dimensions)
    assert "required_capability:geological_sampling" not in dims  # no science task requirement exists
    assert dims["ground_clearance_m"].status == "UNKNOWN"
    assert "No obstacle-height requirement" in dims["ground_clearance_m"].explanation


# ----------------------------------------------------------------------------- after a verified route
def test_energy_reserve_comes_only_from_the_verifier() -> None:
    ares = rover(catalog.ROVER_ARES_1)
    ok = assess_compatibility(ares, MARS, verification=verification(reserve=98.33))
    assert not ok.preliminary
    energy = by_id(ok.dimensions)["energy_reserve_pct"]
    assert (energy.status, energy.rover_value, energy.required_value) == ("PASS", 98.33, 20.0)
    assert "assumed" in energy.explanation
    for reserve, expected in ((20.0, "PASS"), (19.99, "FAIL")):
        dims = by_id(assess_compatibility(ares, MARS, verification=verification(reserve=reserve)).dimensions)
        assert dims["energy_reserve_pct"].status == expected
    small = rover(catalog.ROVER_PRACTICE_SMALL_BATTERY)
    negative = by_id(assess_compatibility(small, MARS, verification=verification(reserve=-12.5)).dimensions)
    assert negative["energy_reserve_pct"].status == "FAIL" and negative["energy_reserve_pct"].rover_value == -12.5
    unevaluated = assess_compatibility(ares, MARS, verification=verification(reserve=None))
    assert not unevaluated.preliminary and by_id(unevaluated.dimensions)["energy_reserve_pct"].status == "UNKNOWN"


def test_missing_energy_model_is_unknown_even_with_a_verified_route() -> None:
    no_model = rover(catalog.ROVER_PRACTICE_NO_ENERGY)
    assert no_model.energy_model is None
    for v in (None, verification(reserve=95.0), verification(reserve=None)):
        dim = by_id(assess_compatibility(no_model, MARS, verification=v).dimensions)["energy_reserve_pct"]
        assert dim.status == "UNKNOWN" and "no energy model" in dim.explanation and dim.rover_value is None


def test_preliminary_until_a_route_distance_is_reported() -> None:
    assert not verified_route_supplied(None)
    assert not verified_route_supplied(VerificationSummary(outcome="INCONCLUSIVE", failure_category="SEARCH_LIMIT"))
    assert not verified_route_supplied(verification(distance=None))
    assert verified_route_supplied(verification(distance=1.0))
    assert assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, verification=verification(distance=None)).preliminary


def test_route_length_limit_is_checked_only_when_declared() -> None:
    limited = rover(catalog.ROVER_ARES_1, max_route_m=250.0)
    assert by_id(assess_compatibility(limited, MARS).dimensions)["route_length_m"].status == "UNKNOWN"
    for distance, expected in ((230.0, "PASS"), (250.0, "PASS"), (250.5, "FAIL")):
        result = assess_compatibility(limited, MARS, verification=verification(distance=distance))
        dim = by_id(result.dimensions)["route_length_m"]
        assert dim.status == expected and dim.rover_value == 250.0 and dim.required_value == distance


# ----------------------------------------------------------------------------- clearance and obstacle height
def test_clearance_is_unknown_for_coarse_support_and_never_inferred_from_wheels() -> None:
    ares = rover(catalog.ROVER_ARES_1)
    for support in (60.0, 480.0, None):
        dims = by_id(assess_compatibility(ares, MARS, candidate_support_scale_m=support).dimensions)
        assert dims["ground_clearance_m"].status == "UNKNOWN"
        assert dims["max_obstacle_height_m"].status == "UNKNOWN" and dims["max_obstacle_height_m"].rover_value is None
    # wheel diameter 0.3 m exceeds the 0.2 m requirement, but it must not become an obstacle capability
    fine = by_id(assess_compatibility(ares, MARS, candidate_support_scale_m=0.01).dimensions)
    assert ares.wheel_diameter_m == 0.3 and fine["max_obstacle_height_m"].status == "UNKNOWN"


def test_declared_clearance_is_compared_only_when_support_is_fine_enough() -> None:
    def dims_for(support: float, **changes: object) -> dict[str, CompatibilityDimension]:
        result = assess_compatibility(rover(catalog.ROVER_ARES_1, **changes), MARS, candidate_support_scale_m=support)
        return by_id(result.dimensions)

    ok = dims_for(0.01)["ground_clearance_m"]
    assert (ok.status, ok.rover_value, ok.required_value) == ("PASS", 0.2, 0.2)
    assert "declared, not observed" in ok.explanation
    assert dims_for(0.01, ground_clearance_m=0.19)["ground_clearance_m"].status == "FAIL"
    assert dims_for(0.02)["ground_clearance_m"].status == "PASS"  # the window upper bound is inclusive
    for obstacle, expected in ((0.3, "PASS"), (0.2, "PASS"), (0.1, "FAIL")):
        assert dims_for(0.01, max_obstacle_height_m=obstacle)["max_obstacle_height_m"].status == expected, obstacle
    coarse = dims_for(60.0, max_obstacle_height_m=0.3)["max_obstacle_height_m"]
    assert coarse.status == "UNKNOWN" and coarse.rover_value == 0.3


# ----------------------------------------------------------------------------- capabilities
def test_capability_pass_fail_unknown() -> None:
    sampling = "required_capability:geological_sampling"
    assert by_id(assess_compatibility(rover(catalog.ROVER_ARES_1), MARS).dimensions)[sampling].status == "PASS"
    nav_only = rover(catalog.ROVER_ARES_1, capabilities=["autonomous_navigation"])
    missing = by_id(assess_compatibility(nav_only, MARS).dimensions)[sampling]
    assert missing.status == "FAIL" and "not among the declared" in missing.explanation
    empty = rover(catalog.ROVER_ARES_1, capabilities=[])
    none_listed = by_id(assess_compatibility(empty, MARS).dimensions)[sampling]
    assert none_listed.status == "UNKNOWN" and "no capabilities" in none_listed.explanation  # unknown, not absence


def _constraints(capability: str | None) -> ConstraintsArtifact:
    def task(task_id: str, cap: str | None) -> TaskSpec:
        return TaskSpec(
            task_id=task_id,
            requirement_ids=["R-TASKS"],
            kind="SAMPLING",
            location=Waypoint(node_id=task_id),
            tolerance_m=0.0,
            dwell_s=0.0,
            required_capability=cap,
            evidence_origin="SYNTHETIC_FIXTURE",
        )

    return ConstraintsArtifact(
        artifact_kind="SYNTHETIC_GRAPH_REGRESSION",
        mode="synthetic",
        resource_provider="TEST_ONLY_MOCK_GRAPH",
        mission_revision_id=uuid4(),
        mission_content_sha256="a" * 64,
        rover_revision_id=uuid4(),
        rover_content_sha256="b" * 64,
        candidate_window_id="graph-zone-1",
        test_revision=1,
        strategy="WAYPOINT_RETURN",
        graph=GraphSpec(nodes=["S", "W1"], edges=[GraphEdge(a="S", b="W1", length_m=10.0, surface_slope_deg=5.0)]),
        start=Waypoint(node_id="S"),
        return_required=True,
        tasks=[task("W1", capability), task("W2", "autonomous_navigation")],
        surface_slope_cap_deg=18.0,
        exposures=[],
        energy=EnergySpec(
            model=None, battery_wh=100.0, min_reserve_pct=20.0, rover_mass_kg=10.0, nominal_speed_mps=0.5
        ),
        solver={"max_expansions": 10, "max_seconds": 1, "max_labels_per_node": 4, "seed": 0},  # type: ignore[arg-type]
    )


def test_frozen_constraints_decide_the_required_capabilities() -> None:
    assert required_capabilities(MARS, None) == ["geological_sampling"]
    assert required_capabilities(MOON, None) == []
    assert required_capabilities(MARS, _constraints("drilling")) == ["autonomous_navigation", "drilling"]
    assert required_capabilities(MARS, _constraints(None)) == ["autonomous_navigation"]
    constraints = _constraints("drilling")
    dims = by_id(assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, constraints=constraints).dimensions)
    assert dims["required_capability:drilling"].status == "FAIL"
    assert dims["required_capability:autonomous_navigation"].status == "PASS"
    assert "required_capability:geological_sampling" not in dims  # frozen constraints replace the default inference


# ----------------------------------------------------------------------------- payload and determinism
def test_dimensions_carry_evidence_and_build_a_valid_payload() -> None:
    refs = [EvidenceRef(evidence_id=uuid4()), EvidenceRef(local_key="analysis")]
    result = assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, evidence=refs)
    assert all(d.evidence == refs for d in result.dimensions)
    payload = AssessCompatibilityPayload(
        preliminary=result.preliminary,
        dimensions=list(result.dimensions),
        compatibility_evidence=EvidenceRef(local_key="compat"),
    )
    assert AssessCompatibilityPayload.model_validate_json(payload.model_dump_json()) == payload


def test_assessment_is_deterministic() -> None:
    a = assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, verification=verification())
    b = assess_compatibility(rover(catalog.ROVER_ARES_1), MARS, verification=verification())
    assert a == b


# ----------------------------------------------------------------------------- review defects 4 and 9
def test_a_route_distance_metric_alone_is_not_a_verified_route() -> None:
    metrics = [metric("route_distance_m", 9999.0), metric("reserve_pct", 90.0, "percent")]
    ares = rover(catalog.ROVER_ARES_1, max_route_m=250.0)
    for outcome, category, codes in (
        ("INCONCLUSIVE", "DATA", []),
        ("INCONCLUSIVE", "SYSTEM", []),
        ("INCONCLUSIVE", "SEARCH_LIMIT", []),
        ("FAIL", "ROUTE", ["UNKNOWN_TERRAIN"]),
        ("PASS", None, ["UNKNOWN_TERRAIN"]),
    ):
        v = VerificationSummary(outcome=outcome, failure_category=category, violation_codes=codes, metrics=metrics)  # type: ignore[arg-type]
        assert not verified_route_supplied(v), (outcome, category, codes)
        result = assess_compatibility(ares, MARS, verification=v)
        dims = by_id(result.dimensions)
        assert result.preliminary
        assert dims["energy_reserve_pct"].status == "UNKNOWN" and dims["route_length_m"].status == "UNKNOWN"
    # a conclusive PASS/FAIL outcome with a distance is a verified route
    for outcome, category in (("PASS", None), ("FAIL", "ROUTE")):
        v = VerificationSummary(outcome=outcome, failure_category=category, violation_codes=[], metrics=metrics)  # type: ignore[arg-type]
        assert verified_route_supplied(v)
        assert by_id(assess_compatibility(ares, MARS, verification=v).dimensions)["route_length_m"].status == "FAIL"


def test_clearance_requirement_without_a_lower_bound_is_unknown_not_a_crash() -> None:
    clearance = next(r for r in MARS if r.observable == "ground_clearance_m")
    no_lower = clearance.model_copy(update={"lower": None})
    ares = rover(catalog.ROVER_ARES_1, ground_clearance_m=0.3, max_obstacle_height_m=0.3)
    dims = by_id(assess_compatibility(ares, [no_lower], candidate_support_scale_m=0.01).dimensions)
    for metric_id in ("ground_clearance_m", "max_obstacle_height_m"):
        assert dims[metric_id].status == "UNKNOWN" and dims[metric_id].required_value is None
        assert "no numeric lower bound" in dims[metric_id].explanation
