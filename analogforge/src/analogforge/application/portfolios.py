"""Project the science optimizer's assignments without aggregating joint rows."""

from typing import Any

from analogforge.domain.ids import envelope
from analogforge.ports import catalog
from analogforge.ports.domain_models import CompositePortfolio
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import OptimizePortfolioInput, QualificationRowInput, VerificationSummary


def evidence_ancestors(ids: list[str], evidence: dict[str, dict[str, Any]]) -> set[str]:
    """Registered ancestors only; absent references cannot establish route proof."""
    found: set[str] = set()
    pending = list(ids)
    while pending:
        identifier = pending.pop()
        if identifier in found or identifier not in evidence:
            continue
        found.add(identifier)
        pending.extend(evidence[identifier].get("input_evidence_ids", []))
    return found


def optimizer_inputs(
    *, run: dict[str, Any], mission: dict[str, Any], rover: dict[str, Any] | None,
    candidates: list[dict[str, Any]], qualifications: list[dict[str, Any]],
    tests: list[dict[str, Any]], results: list[dict[str, Any]], evidence: list[dict[str, Any]], max_sites: int,
) -> OptimizePortfolioInput:
    """Bind coverage to each site's latest experiment and current comparison lineage.

    A newer incomplete/failed experiment cannot borrow an earlier PASS. Route or
    coupled rows without the current verifier in their lineage remain UNKNOWN.
    No frozen wire fields or scientific thresholds are introduced.
    """
    from analogforge.application.discovery import reference

    selected = {candidate["id"]: candidate for candidate in candidates}
    # A run's primary identity is id; child records carry the foreign key run_id.
    # Persisted runs are allowed to omit the redundant run_id wire field.
    record_scope = {"workspace_id": run["workspace_id"], "run_id": run["id"], "mode": run["mode"]}
    by_id = {record["id"]: record for record in evidence}
    current: dict[str, dict[str, Any]] = {}
    for test in sorted(tests, key=lambda t: (t.get("attempt_number", t.get("test_revision", 1)),
                                            t.get("created_at", ""), t["id"])):
        if test.get("candidate_id") in selected:
            current[test["candidate_id"]] = test
    verifications: dict[str, VerificationSummary] = {}
    proof_ids: dict[str, set[str]] = {}
    for candidate_id, test in current.items():
        matched = [result for result in results if result.get("test_id") == test["id"]]
        if not matched:
            continue
        if len(matched) != 1:
            raise ValueError("Portfolio experiment has multiple verification results")
        result = matched[0]
        for record in (test, result):
            if any(record.get(key) != value for key, value in record_scope.items()):
                raise ValueError("Portfolio verification belongs to another run or mode")
        constraints = test.get("constraints")
        if (rover is None or test.get("mission_revision_id") != mission["id"]
                or test.get("rover_revision_id") != rover["id"] or not isinstance(constraints, dict)):
            raise ValueError("Portfolio verification uses another mission or rover revision")
        expected = {"mode": run["mode"], "mission_revision_id": mission["id"],
                    "mission_content_sha256": mission["content_sha256"], "rover_revision_id": rover["id"],
                    "rover_content_sha256": rover["content_sha256"],
                    "candidate_window_id": selected[candidate_id]["window_id"], "test_revision": test["test_revision"]}
        if any(constraints.get(key) != value for key, value in expected.items()):
            raise ValueError("Portfolio verification constraints belong to other frozen inputs")
        if canonical_sha256(constraints) != test.get("constraints_sha256"):
            raise ValueError("Portfolio verification constraints checksum differs")
        if result["outcome"] == "PASS" and (
            not result.get("verified_route_sha256")
            or result["verified_route_sha256"] != test.get("route_artifact_sha256")
        ):
            raise ValueError("Portfolio verification does not prove the frozen route")
        verified = {identifier for identifier in result.get("evidence_ids", []) if identifier in by_id
                    and by_id[identifier].get("kind") == "VERIFICATION"
                    and by_id[identifier].get("algorithm_id") == "verify-route"
                    and by_id[identifier].get("artifact_sha256")
                    and all(by_id[identifier].get(key) == value for key, value in record_scope.items())}
        if not verified:
            # A numeric summary or search result alone is not an independent verifier.
            continue
        proof_ids[candidate_id] = verified
        verifications[selected[candidate_id]["window_id"]] = VerificationSummary(
            outcome=result["outcome"], failure_category=result.get("failure_category"),
            test_result_id=result["id"], violation_codes=[v["code"] for v in result.get("violations", [])],
            metrics=result.get("metrics", []),
        )
    requirements = {req["id"]: req for req in mission["requirements"]}
    rows = []
    for row in qualifications:
        candidate = selected[row["candidate_id"]]
        requirement = requirements[row["requirement_id"]]
        stage = row.get("payload", {}).get("evaluation_stage", row.get("evaluation_stage", "PRELIMINARY"))
        status = row["status"]
        needs_route = (requirement["observable"] in catalog.ROUTE_DEPENDENT_OBSERVABLES
                       or requirement["parameters"].get("co_location_group") is not None)
        if needs_route and status in {"PASS", "PARTIAL"}:
            summary = verifications.get(candidate["window_id"])
            ancestors = evidence_ancestors(row.get("evidence_ids", []), by_id)
            if summary is None or summary.outcome != "PASS" or not (proof_ids.get(candidate["id"], set()) & ancestors):
                status = "UNKNOWN"
        rows.append(QualificationRowInput(
            candidate_window_id=candidate["window_id"], requirement_id=row["requirement_id"], status=status,
            evaluation_stage=stage, critic_blocking_open=row["critic_status"] == "CHALLENGED",
        ))
    return OptimizePortfolioInput(
        requirements=mission["requirements"], candidates=[reference(candidate) for candidate in candidates],
        qualification_rows=rows, verification_by_window_id=verifications, max_sites=max_sites,
    )


def assemble(
    workspace_id: str, run_id: str, mode: str, payload: dict[str, Any], window_ids: dict[str, str]
) -> dict[str, Any]:
    return CompositePortfolio.model_validate(
        {
            **envelope(workspace_id, run_id, mode),
            "candidate_ids": [window_ids[w] for w in payload["selected_window_ids"]],
            "requirement_assignments": [
                {
                    "requirement_id": a["requirement_id"],
                    "candidate_ids": [window_ids[w] for w in a["window_ids"]],
                    "coverage": a["coverage"],
                }
                for a in payload["assignments"]
            ],
            "objective_value": payload["objective_value"],
            "algorithm_id": payload["algorithm_id"],
            "residual_requirement_ids": payload["residual_requirement_ids"],
            "limitations": payload["limitations"],
        }
    ).model_dump(mode="json")
