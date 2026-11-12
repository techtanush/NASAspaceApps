"""The qualification seam must not borrow a different run or candidate's verifier."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from analogforge.application.scheduler import WorkflowEngine, WorkflowError
from analogforge.ports.science_payloads import VerificationSummary


@pytest.mark.parametrize("foreign_field", ["result_run", "test_run", "candidate"])
def test_foreign_verification_is_rejected_before_qualification(foreign_field):
    run_id, workspace_id, candidate_id, result_id = [str(uuid4()) for _ in range(4)]
    engine = object.__new__(WorkflowEngine)
    engine.store = MagicMock()
    engine._rows = MagicMock(return_value=[{"evidence_ids": []}])
    engine._compute = MagicMock()
    result = {"run_id": run_id, "test_id": str(uuid4()), "evidence_ids": [str(uuid4())]}
    test = {"run_id": run_id, "candidate_id": candidate_id}
    if foreign_field == "result_run":
        result["run_id"] = str(uuid4())
    elif foreign_field == "test_run":
        test["run_id"] = str(uuid4())
    else:
        test["candidate_id"] = str(uuid4())
    engine.store.transaction.return_value.__enter__.return_value.require.side_effect = [result, test]
    summary = VerificationSummary(outcome="PASS", failure_category=None, test_result_id=result_id)
    with pytest.raises(WorkflowError, match="another candidate or run"):
        engine._qualify(
            run_id, workspace_id, [{"id": candidate_id, "evidence_ids": []}], {"requirements": []}, None,
            verification_by_candidate={candidate_id: summary},
        )
    engine._compute.assert_not_called()
