"""Freeze test design and project independent verifier/termination results."""

from typing import Any

from analogforge.domain.ids import envelope
from analogforge.ports.domain_models import TestResult, VerificationTest


def design(
    workspace_id: str,
    run_id: str,
    mode: str,
    candidate_id: str,
    payload: dict[str, Any],
    *,
    parent_test_id: str | None,
    attempt_number: int,
    changed_elements: list[str],
) -> dict[str, Any]:
    c = payload["constraints"]
    return {
        **VerificationTest.model_validate(
            {
                **envelope(workspace_id, run_id, mode),
                "candidate_id": candidate_id,
                "mission_revision_id": c["mission_revision_id"],
                "rover_revision_id": c["rover_revision_id"],
                "test_revision": c["test_revision"],
                "requirement_ids": [x["requirement_id"] for x in payload["requirement_mapping"]],
                "route_artifact_sha256": None,
                "waypoints_artifact_sha256": None,
                "constraints_sha256": payload["constraints_sha256"],
                "required_exposures": payload["required_exposures"],
                "solver_config": c["solver"],
                # The frozen wire model has no changed-elements field; the public record carries the attempt's
                # changes as one "Changed elements:" line (the convention the workbench parses), "none" for attempt 1.
                "assumptions": [
                    *c["limitations"],
                    "Changed elements: " + ("; ".join(changed_elements) if changed_elements else "none"),
                ],
            }
        ).model_dump(mode="json"),
        "attempt_number": attempt_number,
        "parent_test_id": parent_test_id,
        "strategy": c["strategy"],
        "search_status": "NOT_RUN",
        "diagnosis_json": None,
        "changed_elements": changed_elements,
        "constraints": c,
        "search_payload": None,
    }


def independently_verify(
    workspace_id: str, run_id: str, mode: str, test_id: str, payload: dict[str, Any], evidence_ids: list[str]
) -> dict[str, Any]:
    record = TestResult.model_validate(
        {
            **envelope(workspace_id, run_id, mode),
            "test_id": test_id,
            "outcome": payload["outcome"],
            "failure_category": payload["failure_category"],
            "search_status": payload["search_status"],
            "verified_route_sha256": payload["verified_route_sha256"],
            "metrics": payload["metrics"],
            "violations": [
                {
                    "requirement_id": v["requirement_id"] or v["constraint_id"],
                    "code": v["code"],
                    "message": v["message"],
                    "evidence_ids": evidence_ids,
                }
                for v in payload["violations"]
            ],
            "evidence_ids": evidence_ids,
            "verifier_version": "1.0",
            "limitations": payload["limitations"],
        }
    ).model_dump(mode="json")
    return {**record, "payload": payload}


def no_route_result(
    workspace_id: str,
    run_id: str,
    mode: str,
    test_id: str,
    search: dict[str, Any],
    evidence_ids: list[str],
    diagnosis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = search["search_status"]
    outcome = "FAIL" if status == "EXHAUSTIVE_INFEASIBLE" else "INCONCLUSIVE"
    category = (
        (diagnosis or {}).get("primary_category")
        if outcome == "FAIL"
        else ("SEARCH_LIMIT" if status == "BUDGET_EXHAUSTED" else "DATA")
    )
    # A provisional no-route summary is never persisted before science supplies its diagnosis.
    if category is None:
        raise ValueError("Exhaustive no-route result requires an independent diagnosis category")
    return TestResult.model_validate(
        {
            **envelope(workspace_id, run_id, mode),
            "test_id": test_id,
            "outcome": outcome,
            "failure_category": category,
            "search_status": status,
            "verified_route_sha256": None,
            "metrics": [],
            "violations": [],
            "evidence_ids": evidence_ids,
            "verifier_version": "search-termination/1.0",
            "limitations": [
                search["termination_reason"],
                (diagnosis or {}).get("proof_scope", "Bounded search; not proof that no route exists"),
            ],
        }
    ).model_dump(mode="json")


def diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_category": payload["primary_category"],
        "permitted_repairs": payload["permitted_repairs"],
        "recommended_repair": payload["recommended_repair"],
        "recommended_strategy": payload["recommended_strategy"],
        "proof_scope": payload["proof_scope"],
        "explanation": payload["explanation"],
    }
