"""Portfolio coverage must use the current experiment for each independent site."""

from copy import deepcopy
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from analogforge.application import portfolios
from analogforge.application.scheduler import WorkflowEngine
from analogforge.ports.common import EvidenceRef
from analogforge.ports.hashing import canonical_sha256
from analogforge.science.portfolio import optimize_portfolio
from tests.integration.science.test_portfolio import cand, req


def case():
    workspace_id, run_id, mission_id, rover_id = [str(uuid4()) for _ in range(4)]
    run = {"id": run_id, "workspace_id": workspace_id, "mode": "synthetic"}
    child_scope = {"run_id": run_id, "workspace_id": workspace_id, "mode": "synthetic"}
    requirements = [req("R-A", "unique_slope_exposure_m"), req("R-B", "completed_task_count")]
    mission = {"id": mission_id, "content_sha256": "1" * 64,
               "requirements": [r.model_dump(mode="json") for r in requirements]}
    rover = {"id": rover_id, "content_sha256": "2" * 64}
    candidates, tests, results, evidence, qualifications = [], [], [], [], []
    for number, window in enumerate(["A", "B"], 1):
        candidate = {**cand(window).model_dump(mode="json"), "id": str(uuid4())}
        candidates.append(candidate)
        test_id, result_id, verifier_id = [str(uuid4()) for _ in range(3)]
        constraints = {"mode": "synthetic", "mission_revision_id": mission_id,
                       "mission_content_sha256": mission["content_sha256"], "rover_revision_id": rover_id,
                       "rover_content_sha256": rover["content_sha256"], "candidate_window_id": window,
                       "test_revision": number}
        tests.append({**child_scope, "id": test_id, "candidate_id": candidate["id"], "attempt_number": number,
                      "mission_revision_id": mission_id, "rover_revision_id": rover_id,
                      "test_revision": number, "constraints": constraints,
                      "constraints_sha256": canonical_sha256(constraints), "route_artifact_sha256": str(number) * 64})
        results.append({**child_scope, "id": result_id, "test_id": test_id, "outcome": "PASS", "failure_category": None,
                        "verified_route_sha256": str(number) * 64, "evidence_ids": [verifier_id], "metrics": [],
                        "violations": []})
        evidence.append({**child_scope, "id": verifier_id, "kind": "VERIFICATION", "algorithm_id": "verify-route",
                         "artifact_sha256": "3" * 64, "input_evidence_ids": []})
        for requirement in mission["requirements"]:
            comparison_id = str(uuid4())
            evidence.append({**child_scope, "id": comparison_id, "kind": "COMPARISON",
                             "algorithm_id": "compare-requirement",
                             "artifact_sha256": "4" * 64, "input_evidence_ids": [verifier_id]})
            qualifications.append({"candidate_id": candidate["id"], "requirement_id": requirement["id"],
                                   "status": "PASS" if requirement["id"] == "R-" + window else "FAIL",
                                   "evaluation_stage": "FINAL", "critic_status": "ACCEPTED",
                                   "evidence_ids": [comparison_id]})
    return dict(run=run, mission=mission, rover=rover, candidates=candidates, qualifications=qualifications,
                tests=tests, results=results, evidence=evidence, max_sites=3)


def optimize(data):
    return optimize_portfolio(
        portfolios.optimizer_inputs(**data), portfolio_evidence=EvidenceRef(local_key="portfolio"),
    )


def test_separate_verified_benchmarks_select_two_sites_and_preserve_each_result():
    data = case()
    inputs = portfolios.optimizer_inputs(**data)
    assert {window: str(summary.test_result_id) for window, summary in inputs.verification_by_window_id.items()} == {
        window: result["id"] for window, result in zip(["A", "B"], data["results"], strict=True)}
    output = optimize(data)
    assert output.selected_window_ids == ["A", "B"] and output.objective_value == 2
    assert {row.requirement_id: row.window_ids for row in output.assignments} == {"R-A": ["A"], "R-B": ["B"]}
    # The same requirements cannot be combined across sites when the experiment requires co-location.
    for requirement in data["mission"]["requirements"]:
        requirement["parameters"]["co_location_group"] = "same-route"
    assert optimize(data).selected_window_ids == []
    # Both rows at A, proved by A's one current verifier, can form the coupled campaign.
    data["qualifications"][1]["status"] = "PASS"
    assert optimize(data).selected_window_ids == ["A"]


def test_scheduler_forwards_current_site_proofs_and_conservative_missing_stage():
    data = case()
    data["qualifications"][0].pop("evaluation_stage")
    engine = object.__new__(WorkflowEngine)
    engine._load = MagicMock(return_value=(data["run"], data["mission"], data["rover"]))
    tables = {key: data[key] for key in ["candidates", "tests", "evidence"]}
    tables["test_results"] = data["results"]
    engine._rows = MagicMock(side_effect=lambda workspace, table, run: tables[table])
    engine._latest_qualifications = MagicMock(return_value=data["qualifications"])
    engine._compute = MagicMock()
    assert "run_id" not in data["run"]
    engine._perform_pending_action(data["run"]["id"], data["run"]["workspace_id"], {
        "type": "BUILD_PORTFOLIO", "payload": {"candidate_ids": [c["id"] for c in data["candidates"]], "max_sites": 3},
    }, data["mission"], data["rover"], None, None)
    inputs = engine._compute.call_args.args[0]
    assert set(inputs.verification_by_window_id) == {"A", "B"}
    assert inputs.qualification_rows[0].evaluation_stage == "PRELIMINARY"


@pytest.mark.parametrize("defect", ["result_run", "result_mode", "test_mission", "test_rover", "constraint_inputs",
                                     "constraint_hash", "route_hash"])
def test_foreign_or_changed_verification_cannot_enter_optimizer(defect):
    data = case()
    if defect == "result_run":
        data["results"][0]["run_id"] = str(uuid4())
    elif defect == "result_mode":
        data["results"][0]["mode"] = "live"
    elif defect == "test_mission":
        data["tests"][0]["mission_revision_id"] = str(uuid4())
    elif defect == "test_rover":
        data["tests"][0]["rover_revision_id"] = str(uuid4())
    elif defect == "constraint_inputs":
        data["tests"][0]["constraints"]["rover_content_sha256"] = "0" * 64
        data["tests"][0]["constraints_sha256"] = canonical_sha256(data["tests"][0]["constraints"])
    elif defect == "constraint_hash":
        data["tests"][0]["constraints_sha256"] = "0" * 64
    else:
        data["results"][0]["verified_route_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Portfolio verification"):
        portfolios.optimizer_inputs(**data)


@pytest.mark.parametrize("defect", ["missing_result", "non_verifier", "new_route_old_rows", "inconclusive"])
def test_missing_stale_or_inconclusive_proof_stays_unknown_without_partial_credit(defect):
    data = case()
    if defect == "missing_result":
        data["results"] = data["results"][1:]
    elif defect == "non_verifier":
        data["evidence"][0]["kind"] = "DERIVED"
        data["evidence"][0]["algorithm_id"] = "search-route"
    elif defect == "inconclusive":
        data["results"][0].update(outcome="INCONCLUSIVE", failure_category="SEARCH_LIMIT")
    else:
        # A newer verifier exists, but A's comparison still cites its previous route proof.
        old_id = data["results"][0]["evidence_ids"][0]
        new_id = str(uuid4())
        data["evidence"].append({**data["evidence"][0], "id": new_id})
        data["results"][0]["evidence_ids"] = [new_id]
        assert old_id != new_id
    inputs = portfolios.optimizer_inputs(**data)
    assert inputs.qualification_rows[0].status == "UNKNOWN"
    output = optimize(data)
    assert output.selected_window_ids == ["B"]
    assert next(a for a in output.assignments if a.requirement_id == "R-A").coverage == "UNKNOWN"


def test_new_incomplete_attempt_does_not_reuse_earlier_pass():
    data = case()
    newer = deepcopy(data["tests"][0])
    newer.update(id=str(uuid4()), attempt_number=3, test_revision=3)
    data["tests"].append(newer)
    assert portfolios.optimizer_inputs(**data).qualification_rows[0].status == "UNKNOWN"
