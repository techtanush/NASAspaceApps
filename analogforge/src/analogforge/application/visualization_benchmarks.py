"""Accepted criteria and scoped committed comparisons, without recomputing science."""

from __future__ import annotations

import json
import math
from typing import Any

from pydantic import ValidationError

from analogforge.application.visualization_detail import authorized_subject, registered_json, scoped_record
from analogforge.db.store import NotFound, PersistenceError
from analogforge.ports.catalog import ROUTE_DEPENDENT_OBSERVABLES
from analogforge.ports.domain_models import QualificationDimension, Requirement
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import CompareRequirementPayload


def _measurement(reason: str) -> dict[str, Any]:
    return {
        "value": None,
        "unit": None,
        "support_scale_m": None,
        "comparison_evidence_id": None,
        "receipt_id": None,
        "reason": reason,
    }


def _candidate_results(uow: Any, run: dict[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    """Only pinned tests/results from this candidate and immutable mission revision."""
    results = []
    tests = {}
    for identifier in run.get("test_ids", []):
        test = scoped_record(uow, "tests", identifier, run)
        if test.get("candidate_id") == candidate_id and test.get("mission_revision_id") == run["mission_revision_id"]:
            tests[identifier] = test
    for identifier in run.get("test_result_ids", []):
        result = scoped_record(uow, "test_results", identifier, run)
        if result.get("test_id") in tests:
            results.append(result)
    return results


def _lineage(uow: Any, identifiers: list[str], run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting or len(records) >= 4096 or len(visiting) >= 128:
            raise ValueError("Invalid or oversized evidence graph")
        if identifier in records:
            return
        visiting.add(identifier)
        row = scoped_record(uow, "evidence", identifier, run)
        for parent in row.get("input_evidence_ids", []):
            visit(parent)
        visiting.remove(identifier)
        records[identifier] = row

    for identifier in identifiers:
        visit(identifier)
    return records


def _numeric_measurement(
    uow: Any,
    blobs: Any,
    run: dict[str, Any],
    candidate: dict[str, Any],
    requirement: dict[str, Any],
    qualification: dict[str, Any],
    results: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    receipt = scoped_record(uow, "tool_receipts", qualification["receipt_id"], run)
    if receipt.get("status") != "SUCCEEDED" or receipt.get("tool_name") != "compare_requirement":
        raise ValueError("No successful comparison receipt")
    payload = CompareRequirementPayload.model_validate(qualification["payload"])
    if (
        payload.requirement_id != requirement["id"]
        or payload.proposed_status != qualification["status"]
        or payload.threshold_lower != requirement["lower"]
        or payload.threshold_upper != requirement["upper"]
        or payload.comparison_scale_m != qualification.get("comparison_scale_m")
        or payload.adequacy.observable_policy_id != qualification.get("rule_id")
    ):
        raise ValueError("Comparison differs from committed criteria or qualification")
    comparison_id = str(payload.comparison_evidence.evidence_id)
    if comparison_id not in qualification.get("evidence_ids", []) or comparison_id not in receipt.get(
        "evidence_ids", []
    ):
        raise ValueError("Comparison is not registered by the committed receipt")
    graph = _lineage(uow, [comparison_id], run)
    comparison = graph[comparison_id]
    if (
        comparison.get("kind") != "COMPARISON"
        or comparison.get("algorithm_id") != "compare-requirement"
        or comparison.get("body") != "EARTH"
        or comparison.get("comparison_scale_m") != payload.comparison_scale_m
    ):
        raise ValueError("Incompatible registered comparison")
    raw = CompareRequirementPayload.model_validate(registered_json(uow, blobs, comparison, run))
    # The raw artifact has a local comparison ref, while registration resolves it
    # to a canonical UUID. All factual fields must remain byte-canonical equal.
    if canonical_sha256(raw.model_dump(mode="json", exclude={"comparison_evidence"})) != canonical_sha256(
        payload.model_dump(mode="json", exclude={"comparison_evidence"})
    ):
        raise ValueError("Committed payload differs from immutable comparison artifact")
    accepted = False
    for row in graph.values():
        if row.get("algorithm_id") == "accepted-requirement-record" and row.get("kind") == "ASSUMPTION":
            if row["id"] not in receipt.get("evidence_ids", []):
                continue
            if registered_json(uow, blobs, row, run) == requirement:
                accepted = True
    if not accepted:
        raise ValueError("Comparison lacks the exact accepted requirement artifact")
    # Candidate analysis is the authority. Shared screening evidence cannot bind
    # a different candidate's numerical comparison to this site's benchmark.
    analysis = (candidate.get("analysis_payload") or {}).get("analysis_evidence", {}).get("evidence_id")
    if analysis is None or analysis not in candidate.get("evidence_ids", []) or analysis not in graph:
        raise ValueError("Comparison lacks this exact candidate's analysis lineage")
    if graph[analysis].get("body") != "EARTH":
        raise ValueError("Candidate analysis belongs to the wrong body")
    own_result_ids = []
    for result in results:
        if result.get("evidence_ids") and set(result["evidence_ids"]).intersection(graph):
            own_result_ids.append(result["id"])
    # Any verifier ancestry must resolve to one of the selected candidate's
    # committed attempts. Never borrow a different candidate's route result.
    verification_ids = {identifier for identifier, row in graph.items() if row.get("kind") == "VERIFICATION"}
    own_verification_ids = {identifier for result in results for identifier in result.get("evidence_ids", [])}
    if not verification_ids.issubset(own_verification_ids):
        raise ValueError("Comparison contains unrelated verification ancestry")
    if (
        requirement["observable"] in ROUTE_DEPENDENT_OBSERVABLES
        and payload.measured_value is not None
        and not own_result_ids
    ):
        raise ValueError("Route-dependent comparison lacks a scoped committed attempt")
    value, unit, support = payload.measured_value, payload.measured_unit, payload.comparison_scale_m
    if value is None:
        return _measurement("The registered comparison records no numeric measurement."), own_result_ids
    if (
        isinstance(value, bool)
        or not math.isfinite(value)
        or unit != requirement["unit"]
        or support is None
        or not math.isfinite(support)
        or support <= 0
    ):
        raise ValueError("Measurement units or support are incompatible")
    minimum, maximum = requirement["minimum_support_scale_m"], requirement["maximum_support_scale_m"]
    if (minimum is not None and support < minimum) or (maximum is not None and support > maximum):
        raise ValueError("Measurement support is outside accepted criteria")
    if requirement["operator"] in {"PRESENT", "NOT_NATURALLY_REPRODUCIBLE"} or qualification["status"] in {
        "GAP",
        "UNKNOWN",
    }:
        return _measurement("This committed criterion has no comparable numeric benchmark."), own_result_ids
    return {
        "value": value,
        "unit": unit,
        "support_scale_m": support,
        "comparison_evidence_id": comparison_id,
        "receipt_id": receipt["id"],
        "reason": "Exact registered comparison value; no margin, score or new measurement was calculated.",
    }, own_result_ids


def site_benchmarks(uow: Any, blob_store: Any, run_id: str, candidate_id: str) -> dict[str, Any]:
    """Use accepted requirement order and only the run's pinned current qualifications."""
    run, mission, candidate, _aoi = authorized_subject(uow, run_id, candidate_id)
    if candidate is None:
        raise NotFound()
    results = _candidate_results(uow, run, candidate_id)
    committed: dict[str, dict[str, Any]] = {}
    for identifier in run.get("qualification_ids", []):
        row = scoped_record(uow, "qualifications", identifier, run)
        if row.get("candidate_id") != candidate_id:
            continue
        parsed = QualificationDimension.model_validate(
            {key: row[key] for key in QualificationDimension.model_fields if key in row}
        )
        if parsed.requirement_id in committed:
            raise PersistenceError("SOURCE_CONTENT_INVALID", "Run pins conflicting current qualification rows.")
        committed[parsed.requirement_id] = row
    rows = []
    for raw_requirement in mission["requirements"]:
        requirement = Requirement.model_validate(raw_requirement).model_dump(mode="json")
        qualification = committed.get(requirement["id"])
        measurement = _measurement("No committed, compatible registered comparison is available.")
        result_ids: list[str] = []
        if qualification is not None:
            try:
                measurement, result_ids = _numeric_measurement(
                    uow,
                    blob_store,
                    run,
                    candidate,
                    requirement,
                    qualification,
                    results,
                )
            except (ValueError, KeyError, TypeError, PersistenceError, json.JSONDecodeError, ValidationError):
                measurement = _measurement(
                    "The committed comparison cannot supply a verified compatible numeric value."
                )
        rows.append(
            {
                "requirement": requirement,
                "qualification_id": qualification["id"] if qualification else None,
                "status": qualification["status"] if qualification else "UNKNOWN",
                "explanation": qualification["explanation"]
                if qualification
                else "No qualification has been committed.",
                "measurement": measurement,
                "test_result_ids": result_ids,
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "mission_revision_id": mission["id"],
        "dataset_lock_id": run.get("dataset_lock_id"),
        "requirements": rows,
        "test_result_ids": [row["id"] for row in results],
    }
