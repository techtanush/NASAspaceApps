"""Persist deterministic comparisons; preserve revisions and unresolved route scope."""

from typing import Any

from analogforge.domain.ids import envelope
from analogforge.domain.policy import PolicyViolation
from analogforge.ports.domain_models import QualificationDimension


def evaluate_candidate(
    workspace_id: str, run_id: str, mode: str, candidate_id: str, payload: dict[str, Any], evidence_ids: list[str]
) -> dict[str, Any]:
    if payload["proposed_status"] in {"PASS", "PARTIAL", "FAIL"} and not evidence_ids:
        raise PolicyViolation("COMPARISON_EVIDENCE_MISSING")
    if payload["confidence"] == "HIGH" and any("unquantified" in x.lower() for x in payload["limitations"]):
        raise PolicyViolation("CONFIDENCE_INFLATION")
    return {
        **QualificationDimension.model_validate(
            {
                **envelope(workspace_id, run_id, mode),
                "candidate_id": candidate_id,
                "requirement_id": payload["requirement_id"],
                "status": payload["proposed_status"],
                "evidence_ids": evidence_ids,
                "rule_id": payload["adequacy"]["observable_policy_id"],
                "rule_version": "1.0",
                "confidence": payload["confidence"],
                "comparison_scale_m": payload["comparison_scale_m"],
                "explanation": payload["explanation"],
                "limitations": payload["limitations"],
                "critic_status": "UNREVIEWED",
                "critique_evidence_ids": [],
            }
        ).model_dump(mode="json"),
        "payload": payload,
        "evaluation_stage": payload["evaluation_stage"],
        "reason_code": payload["reason_code"],
    }


def validate_payload_against_requirement(payload: dict[str, Any], requirement: dict[str, Any]) -> None:
    """Enforce receipt scope/threshold identity without recomputing its science metric."""
    if payload["threshold_lower"] != requirement["lower"] or payload["threshold_upper"] != requirement["upper"]:
        raise PolicyViolation("FROZEN_THRESHOLD_CHANGED", "SCIENTIFIC_CLAIM_REJECTED")
    if payload["measured_unit"] is not None and payload["measured_unit"] != requirement["unit"]:
        raise PolicyViolation("MEASUREMENT_UNIT_CHANGED", "SCIENTIFIC_CLAIM_REJECTED")
    if payload["proposed_status"] not in {"PASS", "PARTIAL"}:
        return
    gates = payload["adequacy"]["gates"]
    by_id = {gate["gate_id"]: gate for gate in gates}
    if len(by_id) != len(gates):
        raise PolicyViolation("DUPLICATE_ADEQUACY_GATE", "SCIENTIFIC_CLAIM_REJECTED")
    for gate_id in [*(f"SC-{i:02}" for i in range(2, 12)), "SC-13"]:
        gate = by_id.get(gate_id)
        if gate is None or gate["outcome"] in {"NOT_ASSESSED", "UNSATISFIED"}:
            raise PolicyViolation("POSITIVE_CLAIM_ADEQUACY_MISSING", "SCIENTIFIC_CLAIM_REJECTED")
    scale = payload["comparison_scale_m"]
    minimum, maximum = requirement["minimum_support_scale_m"], requirement["maximum_support_scale_m"]
    if (minimum is not None and (scale is None or scale < minimum)) or (
        maximum is not None and (scale is None or scale > maximum)
    ):
        raise PolicyViolation("POSITIVE_CLAIM_SCALE_UNSUPPORTED", "SCIENTIFIC_CLAIM_REJECTED")
