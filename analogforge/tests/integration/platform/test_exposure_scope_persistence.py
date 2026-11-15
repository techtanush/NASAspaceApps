"""Actual scheduler publication precedes and supplies scoped comparison authority."""

from uuid import UUID, uuid4

import pytest

from analogforge.domain.hashing_utils import content_hash
from analogforge.domain.ids import envelope
from analogforge.ports import catalog
from analogforge.ports.domain_models import MissionTestContract, RoverProfile
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import CompareRequirementInput, VerificationSummary, VerifyRouteInput
from analogforge.science.facade import create_science_service
from tests.integration.platform import test_runtime_journey
from tests.unit.science.test_routing_support import candidate, graph_design, make_route

runtime = test_runtime_journey.runtime


@pytest.mark.db
def test_scheduler_persists_verifier_and_result_before_first_scoped_comparison_and_drops_stale_authority(runtime):
    engine, store, workspace, make = runtime
    created = make("synthetic-graph-regression-v1")
    run, mission, rover = engine._load(created["id"], workspace)
    extra = dict(next(req for req in mission["requirements"] if req["id"] == "R-EXPOSURE"))
    extra.update(id="R-OTHER-EXPOSURE", lower=300.0)
    updated = {**mission, "id": str(uuid4()), "revision": 2, "requirements": [*mission["requirements"], extra]}
    updated["content_sha256"] = content_hash(updated, "mission")
    reference = candidate().model_copy(update={"candidate_id": uuid4()})
    candidate_record = reference.model_dump(mode="json", exclude={"candidate_id"})
    run = {**run, "id": str(uuid4()), "mission_revision_id": updated["id"], "state": "VERIFYING",
           "candidate_ids": [str(reference.candidate_id)]}
    run.pop("run_id", None)  # The persisted primary identity is id.
    with store.transaction(workspace) as tx:
        tx.create("mission_revisions", updated)
        tx.create("mission_acceptances", {"mission_revision_id": updated["id"], "accepted_at": updated["accepted_at"]})
        tx.create("runs", run)
        tx.create("candidates", {**envelope(workspace, run["id"], run["mode"]),
            **candidate_record, "id": str(reference.candidate_id)})
    designed = graph_design(mission_obj=MissionTestContract.model_validate(updated),
                            rover_obj=RoverProfile.model_validate(rover))
    # Use the independent oracle's exact supplied pass walk; it meets the 100 m row but not the added 300 m row.
    route = make_route(designed.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    test_id, result_id = str(uuid4()), str(uuid4())
    with store.transaction(workspace) as tx:
        tx.create("tests", {**envelope(workspace, run["id"], run["mode"]), "id": test_id,
            "candidate_id": str(reference.candidate_id), "mission_revision_id": updated["id"],
            "rover_revision_id": rover["id"], "attempt_number": 1, "test_revision": 1,
            "constraints": designed.constraints.model_dump(mode="json"),
            "constraints_sha256": designed.constraints_sha256, "route_artifact_sha256": canonical_sha256(route)})
    engine.science = create_science_service(engine.settings.config_dir)
    def publish(tx, registered):
        assert tx.list("scientific_operations", {"run_id": run["id"], "operation": "VERIFY_ROUTE"})
        tx.create("test_results", {**envelope(workspace, run["id"], run["mode"]), "id": result_id,
            "test_id": test_id, **registered.required_payload, "evidence_ids": list(registered.evidence_ids)})
    checked = engine._compute(VerifyRouteInput(
        constraints=designed.constraints, constraints_sha256=designed.constraints_sha256,
        route=route, route_sha256=canonical_sha256(route), search_status="NOT_RUN",
    ), run["id"], workspace, publish=publish)
    assert checked.required_payload["outcome"] == "FAIL"
    with store.transaction(workspace) as tx:
        result = tx.require("test_results", result_id)
    summary = VerificationSummary(test_result_id=UUID(result_id), outcome=result["outcome"],
        failure_category=result["failure_category"], metrics=result["metrics"],
        violation_codes=[v["code"] for v in result["violations"]])
    inputs = CompareRequirementInput(
        requirement=next(req for req in updated["requirements"] if req["id"] == "R-EXPOSURE"),
        candidate=reference, candidate_evidence_ids=result["evidence_ids"], target_evidence_ids=[],
        verification=summary, observable_policy_id="route-exposure-v1",
    )
    from analogforge.application.verification_scope import current_verification_requests
    with store.transaction(workspace) as tx:
        current, accepted, saved_rover = engine._load(run["id"], workspace)
        binding = current_verification_requests(tx, inputs, current, accepted, saved_rover)
    assert binding, "The persisted current verifier must bind before its first comparison"
    supported = engine._compute(inputs, run["id"], workspace)
    assert supported.required_payload["proposed_status"] == "PASS", supported.required_payload
    # A new incomplete experiment must invalidate authority even for an otherwise identical cached comparison.
    with store.transaction(workspace) as tx:
        previous = tx.require("tests", test_id)
        tx.create("tests", {**previous, "id": str(uuid4()), "attempt_number": 2, "test_revision": 2})
    stale = engine._compute(inputs, run["id"], workspace)
    assert stale.required_payload["proposed_status"] == "UNKNOWN" and not stale.receipt["cache_hit"]
