"""An operator's requested portfolio candidate set is an authorization and selection boundary."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from analogforge.application.scheduler import WorkflowEngine, WorkflowError


def candidate():
    return {"id": str(uuid4()), "window_id": str(uuid4()), "name": "Scoped candidate", "origin": "DISCOVERED",
            "novelty_status": "NOT_IN_REFERENCE_LIST", "discovery_method": "bounded-test",
            "aoi": {"body": "EARTH", "bbox": [0, 0, 1, 1], "longitude_convention": "NEG180_180",
                    "latitude_type": "GEODETIC", "crs_wkt": None, "vertical_datum": "EGM96"}}


def test_optimizer_receives_only_the_requested_candidates_and_their_rows():
    a, b = candidate(), candidate()
    engine = object.__new__(WorkflowEngine)
    engine._load = MagicMock(return_value=({"mode": "synthetic"}, {}, None))
    engine._rows = MagicMock(return_value=[a, b])
    engine._latest_qualifications = MagicMock(return_value=[{
        "candidate_id": c["id"], "requirement_id": "R-SLOPE-AVAILABILITY", "status": "PASS",
        "evaluation_stage": "FINAL", "critic_status": "UNREVIEWED",
    } for c in [a, b]])
    engine._compute = MagicMock()
    mission = json.loads((Path("tests/fixtures/kit/missions/mission-mars-mobility.json")).read_text())
    engine._perform_pending_action(str(uuid4()), str(uuid4()), {
        "type": "BUILD_PORTFOLIO", "payload": {"candidate_ids": [a["id"]], "max_sites": 3},
    }, mission, None, None, None)
    inputs = engine._compute.call_args.args[0]
    assert [str(c.candidate_id) for c in inputs.candidates] == [a["id"]]
    assert {row.candidate_window_id for row in inputs.qualification_rows} == {a["window_id"]}


def test_foreign_portfolio_candidate_is_rejected_before_enqueuing():
    engine = object.__new__(WorkflowEngine)
    tx = MagicMock()
    run_id, workspace_id, allowed = str(uuid4()), str(uuid4()), str(uuid4())
    tx.require.return_value = {
        "id": run_id, "run_id": run_id, "workspace_id": workspace_id, "revision": 1,
        "state": "AWAITING_REVIEW", "candidate_ids": [allowed], "pending_review": None, "mode": "synthetic",
    }
    with pytest.raises(WorkflowError, match="Candidate"):
        engine.apply_action(run_id, workspace_id, "BUILD_PORTFOLIO",
                            {"candidate_ids": [str(uuid4())], "max_sites": 3}, 1, uow=tx)
    tx.enqueue.assert_not_called()
    tx.replace.assert_not_called()
