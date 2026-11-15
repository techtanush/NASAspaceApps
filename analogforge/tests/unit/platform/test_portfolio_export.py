"""Export must preserve current evidence limits rather than repeat stale portfolio claims."""

from dataclasses import replace
from uuid import uuid4

import pytest

from analogforge.application.assurance import ScientificClaimRejected
from analogforge.application.passports import _validate_portfolio, assemble_bundle
from analogforge.ports.domain_models import CompositePortfolio, VerificationTest
from analogforge.ports.domain_models import TestResult as VerifiedResult
from analogforge.ports.passport_renderer import AttemptRecord
from tests.integration.platform.test_passport_assembly import passport_case


def portfolio(snapshot, coverage, *, candidate_ids=None):
    candidate = snapshot.candidates[0]
    selected = candidate_ids if candidate_ids is not None else [candidate.id]
    rid = snapshot.mission.requirements[0].id
    return CompositePortfolio(
        schema_version="1.0", id=uuid4(), workspace_id=candidate.workspace_id, run_id=candidate.run_id,
        mode=candidate.mode, created_at=candidate.created_at, candidate_ids=selected,
        requirement_assignments=[{"requirement_id": rid, "candidate_ids": selected, "coverage": coverage}],
        objective_value=snapshot.mission.requirements[0].weight if coverage == "FULL" else 0,
        algorithm_id="exhaustive-subset-v1", residual_requirement_ids=[] if coverage == "FULL" else [rid],
        limitations=["Synthetic portfolio consistency test"],
    )


def route_snapshot():
    snapshot = passport_case()
    candidate = snapshot.candidates[0]
    envelope = {key: getattr(candidate, key)
                for key in ["schema_version", "workspace_id", "run_id", "mode", "created_at"]}
    verifier = snapshot.evidence[0].model_copy(update={
        "id": uuid4(), "kind": "VERIFICATION", "algorithm_id": "verify-route", "artifact_sha256": "3" * 64,
        "input_evidence_ids": [],
    })
    comparison = snapshot.evidence[0].model_copy(update={"input_evidence_ids": [verifier.id]})
    row = snapshot.qualifications[0].model_copy(update={"status": "PASS"})
    test = VerificationTest(
        **envelope, id=uuid4(), candidate_id=candidate.id, mission_revision_id=snapshot.mission.id,
        rover_revision_id=uuid4(), test_revision=1, requirement_ids=[row.requirement_id],
        route_artifact_sha256="4" * 64, waypoints_artifact_sha256=None, constraints_sha256="5" * 64,
        required_exposures=[],
        solver_config={"max_expansions": 10, "max_seconds": 1, "max_labels_per_node": 1, "seed": 0},
        assumptions=[],
    )
    result = VerifiedResult(
        **envelope, id=uuid4(), test_id=test.id, outcome="PASS", failure_category=None, search_status="FOUND",
        verified_route_sha256="4" * 64, metrics=[], violations=[], evidence_ids=[verifier.id],
        verifier_version="1.0", limitations=[],
    )
    attempt = AttemptRecord(
        attempt_number=1, parent_attempt_number=None, candidate_id=candidate.id, candidate_name=candidate.name,
        strategy="EXPOSURE_COVERAGE", test=test, result=result, benchmark_rows=[], violations=[],
        diagnosis_category=None, diagnosis_explanation=None, changed_elements=[],
    )
    return replace(snapshot, qualifications=(row,), evidence=(comparison, verifier), attempts=(attempt,),
                   qualification_stages={row.id: "FINAL"}, portfolio=portfolio(snapshot, "FULL"))


def test_final_export_rejects_full_assignment_when_current_qualification_failed():
    snapshot = passport_case()
    with pytest.raises(ScientificClaimRejected, match="PORTFOLIO_QUALIFICATION_MISMATCH"):
        assemble_bundle(replace(snapshot, portfolio=portfolio(snapshot, "FULL")))
    # The supported negative remains publishable with an honest empty portfolio and residual.
    honest = replace(snapshot, portfolio=portfolio(snapshot, "NONE", candidate_ids=[]))
    assert assemble_bundle(honest).portfolio.requirement_assignments[0].coverage == "NONE"


def test_portfolio_route_with_current_final_evidence_is_consistent():
    _validate_portfolio(route_snapshot())


@pytest.mark.parametrize("defect", ["missing_stage", "inconclusive", "stale_proof", "different_route",
                                     "invented_partial", "wrong_objective", "missing_residual", "foreign_candidate"])
def test_portfolio_route_export_rejects_stale_or_unsupported_assignments(defect):
    snapshot = route_snapshot()
    if defect == "missing_stage":
        snapshot = replace(snapshot, qualification_stages={})
    elif defect == "inconclusive":
        attempt = snapshot.attempts[0]
        result = attempt.result.model_copy(update={"outcome": "INCONCLUSIVE", "failure_category": "SEARCH_LIMIT"})
        snapshot = replace(snapshot, attempts=(attempt.model_copy(update={"result": result}),))
    elif defect == "stale_proof":
        comparison = snapshot.evidence[0].model_copy(update={"input_evidence_ids": []})
        snapshot = replace(snapshot, evidence=(comparison, snapshot.evidence[1]))
    elif defect == "different_route":
        attempt = snapshot.attempts[0]
        result = attempt.result.model_copy(update={"verified_route_sha256": "0" * 64})
        snapshot = replace(snapshot, attempts=(attempt.model_copy(update={"result": result}),))
    elif defect == "invented_partial":
        snapshot = replace(snapshot, portfolio=portfolio(snapshot, "PARTIAL"))
    elif defect == "wrong_objective":
        snapshot = replace(snapshot, portfolio=snapshot.portfolio.model_copy(update={"objective_value": 999}))
    elif defect == "missing_residual":
        record = portfolio(snapshot, "UNKNOWN", candidate_ids=[]).model_copy(update={"residual_requirement_ids": []})
        snapshot = replace(snapshot, portfolio=record)
    else:
        snapshot = replace(snapshot, portfolio=portfolio(snapshot, "FULL", candidate_ids=[uuid4()]))
    with pytest.raises(ScientificClaimRejected):
        _validate_portfolio(snapshot)


def test_same_site_group_cannot_combine_rows_from_different_route_proofs():
    snapshot = route_snapshot()
    original = snapshot.qualifications[0]
    requirement = snapshot.mission.requirements[0].model_copy(update={"id": "R-OTHER"})
    other = original.model_copy(update={"id": uuid4(), "requirement_id": requirement.id, "evidence_ids": [uuid4()]})
    mission = snapshot.mission.model_copy(update={"requirements": [*snapshot.mission.requirements, requirement]})
    assignments = [*snapshot.portfolio.requirement_assignments,
                   snapshot.portfolio.requirement_assignments[0].model_copy(update={"requirement_id": requirement.id})]
    record = snapshot.portfolio.model_copy(update={
        "requirement_assignments": assignments,
        "objective_value": snapshot.portfolio.objective_value + requirement.weight,
    })
    snapshot = replace(snapshot, mission=mission, qualifications=(original, other), portfolio=record,
                       qualification_stages={original.id: "FINAL", other.id: "FINAL"})
    with pytest.raises(ScientificClaimRejected, match="PORTFOLIO_ROUTE_LINEAGE_MISMATCH"):
        _validate_portfolio(snapshot)
