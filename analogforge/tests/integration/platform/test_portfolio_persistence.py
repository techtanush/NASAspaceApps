"""Exercise the scheduler portfolio seam from actual PostgreSQL documents."""

from unittest.mock import MagicMock

import pytest

from analogforge.ports.hashing import canonical_sha256
from tests.integration.platform import test_runtime_journey
from tests.unit.platform.test_portfolio_verification import case

runtime = test_runtime_journey.runtime


@pytest.mark.db
def test_persisted_run_primary_id_binds_child_verification_without_redundant_run_id(runtime):
    engine, store, workspace_id, make = runtime
    created = make()
    with store.transaction(workspace_id) as tx:
        persisted = tx.require("runs", created["id"])
        persisted.pop("run_id", None)
        tx.replace("runs", persisted["id"], persisted, persisted["revision"])
    run, mission, rover = engine._load(created["id"], workspace_id)
    assert "run_id" not in run
    data = case()
    candidate, test, result = data["candidates"][0], data["tests"][0], data["results"][0]
    scope = {"workspace_id": workspace_id, "run_id": run["id"], "mode": run["mode"]}
    candidate.update(scope)
    test.update(scope, mission_revision_id=mission["id"], rover_revision_id=rover["id"])
    test["constraints"].update(mission_revision_id=mission["id"], mission_content_sha256=mission["content_sha256"],
                               rover_revision_id=rover["id"], rover_content_sha256=rover["content_sha256"])
    test["constraints_sha256"] = canonical_sha256(test["constraints"])
    result.update(scope)
    evidence = data["evidence"][:3]
    qualifications = data["qualifications"][:2]
    for record in evidence:
        record.update(scope)
    for requirement, row in zip(mission["requirements"], qualifications, strict=False):
        row.update(scope, requirement_id=requirement["id"])
    with store.transaction(workspace_id) as tx:
        tx.create("candidates", candidate)
        tx.create("tests", test)
        for record in evidence:
            tx.create("evidence", record)
        tx.create("test_results", result)
        for row in qualifications:
            tx.create("qualifications", row)
    engine._compute = MagicMock()
    engine._perform_pending_action(run["id"], workspace_id, {
        "type": "BUILD_PORTFOLIO", "payload": {"candidate_ids": [candidate["id"]], "max_sites": 3},
    }, mission, rover, None, None)
    inputs = engine._compute.call_args.args[0]
    assert str(inputs.verification_by_window_id["A"].test_result_id) == result["id"]
    assert inputs.qualification_rows[0].status == "PASS"
