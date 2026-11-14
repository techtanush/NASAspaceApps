"""Discovery consumes the science shortlist order independently of collection ordering."""

from copy import deepcopy
from uuid import uuid4

from analogforge.application.registrar import RegisteredResult
from analogforge.application.scheduler import WorkflowEngine
from analogforge.ports.science_payloads import AnalyzeCandidateInput, ScreenCandidatesInput
from tests.unit.platform.test_registrar import StoreDouble


class RowMajorStore(StoreDouble):
    def require(self, kind, identifier):
        return self.data[kind][identifier]

    def replace(self, kind, identifier, value, *_args):
        self.data[kind][identifier] = deepcopy(value)

    def list(self, kind, filters=None):
        rows = super().list(kind, filters)
        return sorted(rows, key=lambda row: row["window_id"]) if kind == "candidates" else rows


def test_discovery_pins_and_analyzes_science_order_before_selecting_rank_one(monkeypatch):
    workspace, run_id = str(uuid4()), str(uuid4())
    store = RowMajorStore(workspace, run_id)
    run = store.require("runs", run_id)
    run.update(state="DISCOVERING", scenario_config_id="test-scenario", candidate_ids=[], runtime={})
    mission = {"requirements": []}
    store.create("target_profiles", {
        "id": str(uuid4()), "run_id": run_id, "metrics": [], "payload": {"slope_histogram": None},
    })
    windows = [{
        "window_id": window, "name": window, "rank": rank,
        "origin": "DISCOVERED", "novelty_status": "NOT_IN_REFERENCE_LIST",
        "aoi": {"body": "EARTH", "bbox": [10, 20, 11, 21], "longitude_convention": "NEG180_180",
                "latitude_type": "GEODETIC", "crs_wkt": None, "vertical_datum": "Unknown"},
    } for window, rank in [("r0c0", 3), ("r0c1", 4), ("r1c0", 1), ("r1c1", 2)]]
    # Science has already applied its stable tie break. The orchestration layer must preserve this exact list.
    shortlist = ["r1c0", "r1c1", "r0c0", "r0c1"]
    analyzed = []
    engine = object.__new__(WorkflowEngine)
    engine.store = store
    monkeypatch.setattr(engine, "_scenario", lambda _: {
        "earth_source": {"kind": "LOCAL_DATASET", "dataset_id": "test-dem"},
        "search_region_set_id": "test-regions", "reference_set_id": "test-references", "operator_limits": {},
    })
    monkeypatch.setattr(engine, "_load", lambda *_: (store.require("runs", run_id), mission, None))
    monkeypatch.setattr(engine, "_display", lambda *_: None)
    monkeypatch.setattr(engine, "_role", lambda *_: None)

    def save(_run_id, _workspace, changes, **_kwargs):
        current = store.require("runs", run_id)
        current.update(changes)
        return current

    def compute(inputs, *_args, publish, **_kwargs):
        if isinstance(inputs, ScreenCandidatesInput):
            payload = {"windows": windows, "shortlist_window_ids": shortlist}
        else:
            assert isinstance(inputs, AnalyzeCandidateInput)
            analyzed.append(inputs.candidate.window_id)
            payload = {"metrics": [], "limitations": []}
        result = RegisteredResult(
            payload=payload, evidence_ids=(), artifact_hashes={}, local_evidence_ids={},
            receipt={"id": str(uuid4())}, status="SUCCEEDED", issues=(),
        )
        with store.transaction(workspace) as tx:
            publish(tx, result)
        return result

    monkeypatch.setattr(engine, "_save_run", save)
    monkeypatch.setattr(engine, "_compute", compute)
    result = engine._advance_step(run, mission, None, workspace, None, None)

    pinned = [store.require("candidates", identifier) for identifier in result["candidate_ids"]]
    assert [row["window_id"] for row in pinned] == shortlist
    assert [row["screening_rank"] for row in pinned] == [1, 2, 3, 4]
    assert analyzed == shortlist
    assert store.require("candidates", result["selected_candidate_id"])["window_id"] == "r1c0"
    assert result["state"] == "QUALIFYING"
