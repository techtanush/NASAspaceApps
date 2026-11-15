"""Deterministic validation of declarations; never a physical rover verification."""

from typing import Any

from analogforge.domain.validators import model_violations, validate_rover_input
from analogforge.ports.domain_models import RoverProfile


def profile_validation_report(profile: dict[str, Any]) -> dict[str, Any]:
    violations = model_violations(RoverProfile, profile)
    if not violations:
        violations = validate_rover_input(profile)
    return {
        "profile_revision_id": profile["id"],
        "profile_content_sha256": profile["content_sha256"],
        "validation_scope": "SAVED_PROFILE_SCHEMA_AND_DECLARED_FIELD_CONSISTENCY",
        "valid": not violations,
        "violations": [issue.as_dict() for issue in violations],
        "physical_performance_validated": False,
        "energy_calibration_status": (profile.get("energy_model") or {}).get("calibration_status", "NOT_SUPPLIED"),
        "unknown_optional_limits": [
            key for key in ("max_obstacle_height_m", "max_route_m") if profile.get(key) is None
        ],
        "limitations": [
            "Validates the saved declaration only, not terrain suitability, route feasibility or observed performance.",
            "Null optional limits remain unknown; energy calibration and route verification are separate assessments.",
        ],
    }
