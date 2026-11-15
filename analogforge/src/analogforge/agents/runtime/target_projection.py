"""Project registered target facts for review without calculating or qualifying terrain."""

from typing import Any


def target_evidence_context(facts: dict[str, Any]) -> dict[str, Any]:
    target = facts.get("target") or {}
    records = {row["id"]: row for row in facts.get("evidence_records", [])}
    target_ids = [identifier for identifier in target.get("evidence_ids", []) if identifier in records]
    lineage = set(target_ids)
    pending = target_ids[:]
    while pending:
        for parent in records[pending.pop()].get("input_evidence_ids", []):
            if parent in records and parent not in lineage:
                lineage.add(parent)
                pending.append(parent)
    body = target.get("target", {}).get("body")
    sources = sorted(identifier for identifier in lineage
                     if records[identifier]["kind"] == "SOURCE" and records[identifier].get("body") == body)
    measurements = [identifier for identifier in target_ids if records[identifier]["kind"] == "DERIVED"]
    payload = target.get("payload", {})
    unavailable = {row["dimension"]: row for row in payload.get("unavailable_dimensions", [])}
    # This is the committed terrain profile's availability, not satisfaction of any criterion.
    histogram = payload.get("slope_histogram") or {}
    terrain_available = bool(measurements and sources and histogram.get("valid_area_m2", 0) > 0)
    dimensions = []
    for requirement in facts["mission"]["requirements"]:
        missing = unavailable.get(requirement["dimension"])
        availability, limitation = "UNRESOLVED", "No dimension-specific target measurement is established here."
        if missing:
            reason = missing.get("reason_code")
            availability = reason if reason in {"NO_COVERAGE", "UNSUPPORTED"} else "UNRESOLVED"
            limitation = missing["message"]
        elif requirement["dimension"] == "TERRAIN" and terrain_available:
            availability = "AVAILABLE"
            limitation = "Registered terrain profile only; exact criterion and common-support checks remain downstream."
        dimensions.append({"requirement_id": requirement["id"], "availability": availability,
                           "evidence_ids": measurements if availability == "AVAILABLE" else [],
                           "measurement_spec_id": facts.get("target_measurement_spec_id")
                           if availability == "AVAILABLE" else None,
                           "limitation": limitation})
    return {"source_evidence_ids": sources, "measurement_evidence_ids": measurements,
            "dimension_evidence": dimensions}
