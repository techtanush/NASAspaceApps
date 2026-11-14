"""Mechanical evidence checks; metadata is never executed as instructions."""

from typing import Any


def compare_evidence(left: dict[str, Any], right: dict[str, Any], kind: str) -> dict[str, Any]:
    reasons = []
    if left["mode"] != right["mode"]:
        reasons.append("MODE_MISMATCH")
    if kind == "geometry" and left["body"] != right["body"]:
        reasons.append("BODY_MISMATCH")
    if kind == "scale" and (
        left.get("comparison_scale_m") is None or left.get("comparison_scale_m") != right.get("comparison_scale_m")
    ):
        reasons.append("SCALE_MISMATCH")
    if kind == "metric":
        leftunits = {m["metric_id"]: m["unit"] for m in left.get("metrics", [])}
        rightunits = {m["metric_id"]: m["unit"] for m in right.get("metrics", [])}
        if not leftunits or leftunits != rightunits:
            reasons.append("UNIT_OR_QUANTITY_MISMATCH")
    if kind == "uncertainty":
        reasons.append("INDEPENDENT_ERROR_MODEL_REQUIRES_SCIENCE_AUDIT")
    return {"comparable": not reasons, "reasons": reasons, "harmonization_spec_id": None}
