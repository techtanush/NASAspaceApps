"""Offline role proposals copied from registered facts, never scientific calculators."""

from typing import Any

from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask
from analogforge.tools.registry import ToolContext, ToolRegistry


class ScriptedProvider:
    def run(self, task: AgentTask, registry: ToolRegistry, context: ToolContext) -> RoleSubmission:
        if task.runtime_mode not in {"synthetic", "replay"}:
            raise ProviderError("MODE_MISMATCH", "Scripted roles cannot run in live mode")
        proposal = RoleSubmission.model_validate(task.payload["prepared_submission"])
        proposal.validate_payload()
        if not {str(e) for e in proposal.evidence_ids} <= {str(e) for e in task.input_evidence_ids}:
            raise ProviderError("MODEL_OUTPUT_INVALID", "Script references evidence absent from task")
        return proposal


def project_payload(role: str, facts: dict[str, Any]) -> dict[str, Any]:
    mission = facts["mission"]
    requirements = [r["id"] for r in mission["requirements"]]
    receipt = facts["validation_receipt_id"]
    candidate = facts.get("candidate") or {}
    test = facts.get("test") or {}
    result = facts.get("result") or {}
    evidence = facts.get("evidence_ids", [])
    if role == "mission_director":
        return {
            "dispatch_role": None,
            "dispatch_task_kind": None,
            "dispatch_input_ids": [],
            "requirement_ids": requirements,
            "expected_evidence_kinds": [],
            "priority": "REQUIRED",
            "stop_reason": facts.get("stop_reason"),
            "portfolio_revision_id": None,
        }
    if role == "requirements":
        return {
            "contract_revision_id": mission["id"],
            "contract_hash": mission["content_sha256"],
            "requirement_ids": requirements,
            "validation_receipt_id": receipt,
            "unchanged": True,
            "consistency_issues": [],
            "new_contract_required": False,
        }
    if role == "rover_systems":
        rover = facts["rover"]
        return {
            "rover_revision_id": rover["id"],
            "validation_receipt_id": receipt,
            "hard_limit_summary": [
                {"field_path": key, "value": rover[key], "unit": unit, "source_ref": "saved_profile." + key}
                for key, unit in [("max_slope_deg", "deg"), ("battery_wh", "Wh"), ("min_reserve_pct", "pct")]
            ],
            "capability_mapping": [],
            "compatibility_revision_id": None,
            "energy_model_revision_id": None,
            "missing_engineering_inputs": []
            if rover["energy_model"]
            else [
                {
                    "field_path": "energy_model",
                    "affects_requirement_ids": requirements,
                    "consequence": "Predicted reserve remains unknown",
                }
            ],
            "benchmark_constraint_refs": [],
        }
    if role == "planetary_target":
        target = facts.get("target")
        return {
            "target_revision_id": mission["id"],
            "target_profile_revision_id": target["id"] if target else None,
            "coverage_receipt_ids": facts.get("coverage_receipt_ids", []),
            "source_evidence_ids": [],
            "measurement_evidence_ids": evidence,
            "dimension_evidence": [],
            "geometry_validation_receipt_id": receipt,
            "comparison_ready": target is not None,
        }
    if role == "earth_scout":
        screening = facts.get("screening", {})
        return {
            "search_region_set_id": facts["scenario"]["search_region_set_id"],
            "screening_receipt_id": facts.get("screening_receipt_id"),
            "screened_region_count": screening.get("screened_count", 0),
            "shortlist": [
                {
                    "candidate_revision_id": c["id"],
                    "analysis_revision_id": None,
                    "screen_rank": c.get("screening_rank") or i + 1,
                    "evidence_ids": c["evidence_ids"],
                    "supported_requirement_ids": [],
                    "unknown_requirement_ids": requirements,
                    "known_analog_reference": c["novelty_status"] == "KNOWN_ANALOG",
                    "selection_reason_code": "FEATURE_MATCH",
                }
                for i, c in enumerate(facts.get("candidates", []))
            ],
            "excluded_candidate_refs": [],
            "search_limitations": screening.get("limitations", []),
            "portfolio_revision_id": None,
            "discovery_exhausted": screening.get("stop_reason") == "GRID_EXHAUSTED",
        }
    if role == "qualification":
        rows = facts["qualifications"]
        return {
            "candidate_revision_id": candidate["id"],
            "qualification_draft_revision_id": rows[-1]["id"],
            "rows": [
                {
                    "requirement_id": r["requirement_id"],
                    "comparison_receipt_id": r.get("receipt_id"),
                    "proposed_status": r["status"],
                    "evidence_ids": r["evidence_ids"],
                    "measurement_evidence_ids": r["evidence_ids"],
                    "basis": "PHYSICAL_LIMITATION"
                    if r["status"] == "GAP"
                    else "MISSING_EVIDENCE"
                    if r["status"] == "UNKNOWN"
                    else "DERIVED",
                    "confidence": r["confidence"],
                    "covered_subcriterion_ids": r["payload"]["covered_subcriteria"],
                    "uncovered_subcriterion_ids": r["payload"]["uncovered_subcriteria"],
                    "limitations": r["limitations"],
                }
                for r in rows
            ],
            "qualified_use_requirement_ids": [r["requirement_id"] for r in rows if r["status"] == "PASS"],
            "partial_use_requirement_ids": [r["requirement_id"] for r in rows if r["status"] == "PARTIAL"],
            "unsupported_use_requirement_ids": [
                r["requirement_id"] for r in rows if r["status"] in {"FAIL", "GAP", "UNKNOWN"}
            ],
            "portfolio_revision_id": None,
            "critic_review_required": True,
        }
    if role == "scientific_critic":
        return {
            "review_revision_id": facts["review_revision_id"],
            "objections": facts.get("objections", []),
            "accepted_claim_ids": [],
            "gate_recommendation": "REPAIR_REQUIRED" if facts.get("objections") else "CLEAR_WITH_LIMITATIONS",
        }
    if role == "test_designer":
        search = test.get("search_payload") or {}
        return {
            "candidate_revision_id": candidate["id"],
            "test_revision_id": test["id"],
            "strategy": test["strategy"],
            "constraint_mapping": [
                {
                    "requirement_id": m["requirement_id"],
                    "benchmark_constraint_ids": m["constraint_ids"],
                    "treatment": m["treatment"],
                    "limitation": m.get("limitation"),
                }
                for m in test.get("requirement_mapping", [])
            ],
            "compatibility_revision_id": None,
            "search_attempt_id": facts.get("search_operation_id"),
            "proposed_route_revision_id": None,
            "search_termination": {
                "FOUND": "ROUTE_FOUND",
                "EXHAUSTIVE_INFEASIBLE": "EXHAUSTIVE_NO_ROUTE",
                "BUDGET_EXHAUSTED": "LIMIT_REACHED",
            }.get(str(search.get("search_status")), "DATA_BLOCKED"),
            "unverified_requirement_ids": test.get("unverified_requirement_ids", []),
        }
    if role == "verification_replanning":
        diagnosis = facts.get("diagnosis") or {}
        repair = diagnosis.get("recommended_repair")
        return {
            "test_revision_id": test["id"],
            "result_revision_id": result["id"],
            "search_attempt_id": facts.get("search_operation_id"),
            "outcome": result["outcome"],
            "primary_failure_category": result["failure_category"],
            "secondary_failure_categories": diagnosis.get("secondary_categories", []),
            "violated_constraint_ids": diagnosis.get("violated_constraint_ids", []),
            "diagnosis_receipt_id": facts.get("diagnosis_receipt_id"),
            "repair": None
            if repair is None
            else {
                "kind": repair,
                "target_revision_ids": [test["id"]],
                "addresses_constraint_ids": diagnosis.get("violated_constraint_ids", []),
                "preserved_contract_sha256": mission["content_sha256"],
                "strategy": diagnosis.get("recommended_strategy"),
                "expected_check": diagnosis.get("explanation", "Independent verification"),
                "requires_new_run": repair == "NEW_CONTRACT_REQUIRED",
            },
            "stop_reason": "VERIFIED" if result["outcome"] == "PASS" else None,
        }
    if role == "evidence_passport":
        passport = facts["passport"]
        return {
            "passport_draft_revision_id": passport["id"],
            "source_run_revision": facts["run"]["revision"],
            "selected_candidate_revision_ids": passport["candidate_ids"],
            "portfolio_revision_id": passport["portfolio_id"],
            "claim_annotations": [],
            "unresolved_issue_ids": [],
            "not_verified_requirement_ids": [
                r["requirement_id"] for r in facts.get("qualifications", []) if r["status"] != "PASS"
            ],
            "export_artifact_ids": [],
            "ready_to_publish": True,
        }
    raise ValueError("Unknown role")
