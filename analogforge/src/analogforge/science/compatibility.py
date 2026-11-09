"""``ASSESS_COMPATIBILITY`` logic (guide 08 section 4.8; architecture 11 section 7).

Rover compatibility compares *declared* capabilities with explicit task needs.  A declared capability is not an
observed performance, a missing field is ``UNKNOWN`` (never absence), and clearance/obstacle capability is never
inferred from wheel diameter.  ``preliminary`` stays true until a verified route (a verification carrying a route
distance) is supplied.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from analogforge.ports.common import EvidenceRef, QualificationStatus
from analogforge.ports.domain_models import Requirement, RoverProfile
from analogforge.ports.science_payloads import (
    CompatibilityDimension,
    ConstraintsArtifact,
    VerificationSummary,
)

DEFAULT_TASK_CAPABILITY = "geological_sampling"
_TOLERANCE = 1e-9


@dataclass(frozen=True)
class CompatibilityResult:
    preliminary: bool
    dimensions: tuple[CompatibilityDimension, ...]


def verified_route_supplied(verification: VerificationSummary | None) -> bool:
    """A verified route exists only if the verification reports a route distance."""
    if verification is None:
        return False
    return any(m.metric_id == "route_distance_m" and m.value is not None for m in verification.metrics)


def _metric(verification: VerificationSummary | None, metric_id: str) -> float | None:
    if verification is None:
        return None
    for m in verification.metrics:
        if m.metric_id == metric_id:
            return m.value
    return None


def required_capabilities(
    requirements: Sequence[Requirement],
    constraints: ConstraintsArtifact | None,
    task_capability: str = DEFAULT_TASK_CAPABILITY,
) -> list[str]:
    """Capabilities the mission needs: task capabilities of frozen constraints, else sampling for science tasks."""
    if constraints is not None:
        return sorted({t.required_capability for t in constraints.tasks if t.required_capability})
    needs_sampling = any(r.observable == "completed_task_count" and r.dimension == "SCIENCE" for r in requirements)
    return [task_capability] if needs_sampling else []


def assess_compatibility(
    rover: RoverProfile,
    requirements: Sequence[Requirement],
    *,
    verification: VerificationSummary | None = None,
    constraints: ConstraintsArtifact | None = None,
    candidate_support_scale_m: float | None = None,
    task_capability: str = DEFAULT_TASK_CAPABILITY,
    evidence: Sequence[EvidenceRef] = (),
) -> CompatibilityResult:
    """Compatibility dimensions of ``rover`` for ``requirements`` (optionally with a verified route)."""
    refs = list(evidence)
    verified = verified_route_supplied(verification)
    dims: list[CompatibilityDimension] = []

    def dim(
        metric_id: str,
        status: QualificationStatus,
        rover_value: float | None,
        required: float | None,
        unit: str | None,
        why: str,
    ) -> None:
        dims.append(
            CompatibilityDimension(
                metric_id=metric_id,
                status=status,
                rover_value=rover_value,
                required_value=required,
                unit=unit,
                explanation=why,
                evidence=refs,
            )
        )

    # --- surface slope: declared capability vs the highest required band upper
    uppers = [
        float(r.parameters.slope_band_deg[1])
        for r in requirements
        if r.parameters.slope_band_deg is not None and len(r.parameters.slope_band_deg) == 2
    ]
    if not uppers:
        dim("max_surface_slope_deg", "UNKNOWN", rover.max_slope_deg, None, "deg", "No requirement names a slope band.")
    else:
        need = max(uppers)
        ok = rover.max_slope_deg >= need - _TOLERANCE
        dim(
            "max_surface_slope_deg",
            "PASS" if ok else "FAIL",
            rover.max_slope_deg,
            need,
            "deg",
            f"Declared maximum slope {rover.max_slope_deg:g} deg {'covers' if ok else 'is below'} the highest "
            f"required band upper {need:g} deg (declared capability, not observed).",
        )

    # --- energy reserve
    if rover.energy_model is None:
        dim(
            "energy_reserve_pct",
            "UNKNOWN",
            None,
            rover.min_reserve_pct,
            "percent",
            "The rover profile has no energy model, so reserve cannot be evaluated (never assumed zero).",
        )
    elif not verified:
        dim(
            "energy_reserve_pct",
            "UNKNOWN",
            None,
            rover.min_reserve_pct,
            "percent",
            "Preliminary: energy reserve is known only after a route is independently verified.",
        )
    else:
        reserve = _metric(verification, "reserve_pct")
        if reserve is None:
            dim(
                "energy_reserve_pct",
                "UNKNOWN",
                None,
                rover.min_reserve_pct,
                "percent",
                "The verification did not evaluate the energy reserve.",
            )
        else:
            ok = reserve >= rover.min_reserve_pct - _TOLERANCE
            note = (
                " Energy parameters are assumed, not calibrated."
                if rover.energy_model.calibration_status == "ASSUMED"
                else ""
            )
            dim(
                "energy_reserve_pct",
                "PASS" if ok else "FAIL",
                reserve,
                rover.min_reserve_pct,
                "percent",
                f"Verified modeled reserve {reserve:.4g}% {'meets' if ok else 'is below'} the required "
                f"{rover.min_reserve_pct:g}%.{note}",
            )

    # --- clearance and obstacle height (declared values; field-scale evidence required)
    clearance_reqs = [r for r in requirements if r.observable == "ground_clearance_m"]
    required_clearance = max((r.lower for r in clearance_reqs if r.lower is not None), default=None)
    coarse = [
        r
        for r in clearance_reqs
        if r.maximum_support_scale_m is not None
        and (candidate_support_scale_m is None or candidate_support_scale_m > r.maximum_support_scale_m)
    ]
    if not clearance_reqs:
        gate_why = "No obstacle-height requirement exists in the mission."
    elif coarse:
        support_text = "unknown" if candidate_support_scale_m is None else f"{candidate_support_scale_m:g} m"
        gate_why = (
            f"Terrain support ({support_text}) is coarser than the requirement window, "
            "so obstacle height is not observable."
        )
    else:
        gate_why = ""
    for metric_id, declared, label in (
        ("ground_clearance_m", rover.ground_clearance_m, "ground clearance"),
        ("max_obstacle_height_m", rover.max_obstacle_height_m, "maximum obstacle height"),
    ):
        if declared is None:
            dim(
                metric_id,
                "UNKNOWN",
                None,
                required_clearance,
                "m",
                f"The rover profile does not state {label} (unknown).",
            )
        elif gate_why:
            dim(
                metric_id,
                "UNKNOWN",
                declared,
                required_clearance,
                "m",
                f"{gate_why} Declared {label} {declared:g} m is not tested.",
            )
        else:
            assert required_clearance is not None
            ok = declared >= required_clearance - _TOLERANCE
            dim(
                metric_id,
                "PASS" if ok else "FAIL",
                declared,
                required_clearance,
                "m",
                f"Declared {label} {declared:g} m {'meets' if ok else 'is below'} "
                f"the required {required_clearance:g} m (declared, not observed).",
            )

    # --- required capabilities
    for capability in required_capabilities(requirements, constraints, task_capability):
        metric_id = f"required_capability:{capability}"
        if not rover.capabilities:
            dim(metric_id, "UNKNOWN", None, None, None, "The rover profile lists no capabilities, so this is unknown.")
        elif capability in rover.capabilities:
            dim(
                metric_id,
                "PASS",
                None,
                None,
                None,
                f"'{capability}' is declared by the profile (declared, not observed).",
            )
        else:
            dim(metric_id, "FAIL", None, None, None, f"'{capability}' is not among the declared capabilities.")

    # --- route length
    if rover.max_route_m is not None:
        distance = _metric(verification, "route_distance_m")
        if distance is None:
            dim("route_length_m", "UNKNOWN", rover.max_route_m, None, "m", "No verified route length yet.")
        else:
            ok = distance <= rover.max_route_m + _TOLERANCE
            dim(
                "route_length_m",
                "PASS" if ok else "FAIL",
                rover.max_route_m,
                distance,
                "m",
                f"Verified route length {distance:.6g} m {'is within' if ok else 'exceeds'} the declared "
                f"maximum {rover.max_route_m:g} m.",
            )
    return CompatibilityResult(preliminary=not verified, dimensions=tuple(dims))
