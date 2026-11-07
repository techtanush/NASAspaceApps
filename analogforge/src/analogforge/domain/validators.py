"""Semantic validations augment immutable kit wire models without changing them."""

from dataclasses import asdict, dataclass
from typing import Any

from pydantic import ValidationError

from analogforge.ports.domain_models import MissionTestContract, RoverProfile


@dataclass(frozen=True)
class Violation:
    code: str
    field_path: str
    message: str
    severity: str = "ERROR"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_rover_input(profile: dict[str, Any] | RoverProfile) -> list[Violation]:
    value = profile.model_dump(mode="json") if isinstance(profile, RoverProfile) else profile
    issues: list[Violation] = []
    for field in ("mass_kg", "battery_wh", "nominal_speed_mps", "wheel_diameter_m"):
        v = value.get(field)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            issues.append(Violation("INPUT_INVALID", field, "Must be a positive SI quantity"))
    if not 0 < value.get("max_slope_deg", 0) < 90:
        issues.append(Violation("INPUT_INVALID", "max_slope_deg", "Must lie strictly between 0 and 90 degrees"))
    if not 0 <= value.get("min_reserve_pct", -1) <= 100:
        issues.append(Violation("INPUT_INVALID", "min_reserve_pct", "Must lie between 0 and 100"))
    sensors = value.get("sensors", [])
    if len(sensors) != len(set(sensors)):
        issues.append(Violation("INPUT_INVALID", "sensors", "Duplicate sensors"))
    return issues


def validate_mission_content(
    contract: dict[str, Any] | MissionTestContract, rover: dict[str, Any] | None = None
) -> list[Violation]:
    value = contract.model_dump(mode="json") if isinstance(contract, MissionTestContract) else contract
    issues: list[Violation] = []
    requirements = value.get("requirements", [])
    if not requirements:
        issues.append(Violation("INPUT_INVALID", "requirements", "At least one measurable requirement is required"))
    ids = [r["id"] for r in requirements]
    if len(ids) != len(set(ids)):
        issues.append(Violation("INPUT_INVALID", "requirements", "Duplicate requirement ids"))
    for i, row in enumerate(requirements):
        prefix = f"requirements[{i}]"
        lower, upper = row.get("lower"), row.get("upper")
        op = row.get("operator")
        if op == "BETWEEN" and (lower is None or upper is None or lower > upper):
            issues.append(Violation("INPUT_INVALID", prefix, "BETWEEN requires ordered lower and upper bounds"))
        if op == "GTE" and lower is None or op == "LTE" and upper is None:
            issues.append(Violation("INPUT_INVALID", prefix, "Numeric operator requires its bound"))
        if op == "NOT_NATURALLY_REPRODUCIBLE" and row.get("observable") not in {
            "planetary_gravity",
            "planetary_atmosphere",
            "planetary_radiation",
        }:
            issues.append(
                Violation("INPUT_INVALID", prefix, "Physical GAP operator is restricted to physical observables")
            )
        minimum, maximum = row.get("minimum_support_scale_m"), row.get("maximum_support_scale_m")
        if minimum is not None and maximum is not None and minimum > maximum:
            issues.append(Violation("INPUT_INVALID", prefix, "Minimum support exceeds maximum support"))
        band = row.get("parameters", {}).get("slope_band_deg")
        if band is not None:
            if len(band) != 2 or not 0 <= band[0] < band[1] <= 90:
                issues.append(
                    Violation(
                        "INPUT_INVALID",
                        prefix + ".parameters.slope_band_deg",
                        "Slope band requires two ordered angles within 0–90 degrees",
                    )
                )
            elif rover is not None and band[1] > rover["max_slope_deg"]:
                issues.append(
                    Violation(
                        "ROVER_LIMIT_CONFLICT",
                        prefix,
                        "Requested band extends above the selected rover slope limit",
                        "WARNING",
                    )
                )
        if row.get("observable") == "unique_slope_exposure_m" and row.get("unit") != "m":
            issues.append(Violation("INPUT_INVALID", prefix + ".unit", "Exposure threshold is distance in meters"))
    return issues


def validate_run_inputs(
    mission: dict[str, Any],
    rover: dict[str, Any] | None,
    *,
    workspace_id: str,
    mode: str,
    scenario: dict[str, Any],
    dataset_lock: dict[str, Any] | None,
    api_key: str | None = None,
    model: str | None = None,
) -> list[Violation]:
    issues = validate_mission_content(mission, rover)
    if not mission.get("accepted_at"):
        issues.append(Violation("INPUT_INVALID", "mission_revision_id", "Mission revision must be accepted"))
    for label, record in (("mission", mission), ("rover", rover)):
        if record is not None and str(record.get("workspace_id")) != workspace_id:
            issues.append(Violation("INPUT_INVALID", label, "Workspace mismatch"))
    if mode not in scenario.get("allowed_modes", []):
        issues.append(Violation("MODE_MISMATCH", "mode", "Scenario does not allow selected mode"))
    if mission.get("target", {}).get("body") != scenario.get("body"):
        issues.append(Violation("INPUT_INVALID", "target.body", "Target body differs from scenario"))
    if dataset_lock is None:
        issues.append(Violation("SOURCE_UNAVAILABLE", "dataset_lock_id", "Source-policy lock is unavailable"))
    if mode == "live" and (not api_key or not model):
        issues.append(
            Violation(
                "PROVIDER_AUTH_FAILED",
                "OPENAI_API_KEY" if not api_key else "OPENAI_MODEL",
                "Live provider configuration is incomplete",
            )
        )
    return issues


def model_violations(model: type[MissionTestContract] | type[RoverProfile], value: dict[str, Any]) -> list[Violation]:
    try:
        model.model_validate(value)
    except ValidationError as exc:
        return [Violation("INPUT_INVALID", ".".join(str(p) for p in e["loc"]), e["msg"]) for e in exc.errors()]
    return []
