"""Project registered target facts for review without calculating or qualifying terrain."""

from copy import deepcopy
from typing import Any

from analogforge.ports.hashing import canonical_sha256


def target_coordinate_context(facts: dict[str, Any]) -> dict[str, Any]:
    """Bind source-frame metadata to committed ingestion and target-preparation receipts."""
    target = facts.get("target") or {}
    result: dict[str, Any] = {"operator_aoi_scope": "HORIZONTAL_FOOTPRINT",
                              "geometry_validation_receipt_id": None, "source_frames": []}
    if not target.get("evidence_ids"):
        return result
    scope = {key: target.get(key) for key in ("workspace_id", "run_id", "mode")}
    if any(not isinstance(value, str) or not value for value in scope.values()):
        return result
    receipts: dict[str, dict[str, Any]] = {r["id"]: r for r in facts.get("registered_receipts", [])}

    def receipt_for(operation: dict[str, Any]) -> dict[str, Any] | None:
        receipt_id = operation.get("receipt_id")
        if not isinstance(receipt_id, str):
            return None
        receipt = receipts.get(receipt_id, {})
        tool = {"CHARACTERIZE_TARGET": "characterize_target", "INGEST_LOCAL_DATASET": "fetch_dataset"}.get(
            operation.get("operation", "")
        )
        if (operation.get("status") != "SUCCEEDED" or receipt.get("status") != "SUCCEEDED"
                or tool is None or receipt.get("tool_name") != tool
                or any(operation.get(k) != v or receipt.get(k) != v for k, v in scope.items())
                or not operation.get("evidence_ids")
                or set(receipt.get("evidence_ids", [])) != set(operation["evidence_ids"])):
            return None
        return receipt

    for operation in reversed(facts.get("target_operations", [])):
        receipt = receipt_for(operation)
        inputs = operation.get("request", {}).get("inputs", {})
        if (not receipt or operation.get("operation") != "CHARACTERIZE_TARGET"
                or inputs.get("target") != target.get("target")
                or not set(target["evidence_ids"]) <= set(operation["evidence_ids"])):
            continue
        result["geometry_validation_receipt_id"] = receipt["id"]
        result["geometry_validation_operation"] = "CHARACTERIZE_TARGET"
        source = inputs.get("source", {})
        if source.get("kind") != "LOCAL_DATASET":
            return result
        for ingestion in reversed(facts.get("source_ingest_operations", [])):
            source_receipt = receipt_for(ingestion)
            manifest = ingestion.get("request", {}).get("inputs", {}).get("manifest", {})
            if (not source_receipt or ingestion.get("operation") != "INGEST_LOCAL_DATASET"
                    or manifest.get("dataset_id") != source.get("dataset_id")
                    or manifest.get("body") != target.get("target", {}).get("body")):
                continue
            fields = ("dataset_id", "body", "role", "quantity", "units", "crs", "vertical_reference",
                      "reference_radius_m", "longitude_convention", "longitude_direction", "latitude_type",
                      "pixel_registration", "declared_native_resolution_m")
            result["source_frames"] = [{**{key: deepcopy(manifest.get(key)) for key in fields},
                                         "ingestion_receipt_id": source_receipt["id"],
                                         "manifest_sha256": canonical_sha256(manifest)}]
            break
        return result
    return result


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
