"""Actual PostgreSQL workflow with switchable science/renderer seams."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from analogforge.application.scheduler import WorkflowEngine
from analogforge.db.store import Store
from analogforge.domain.ids import utc_now
from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes, canonical_sha256
from analogforge.ports.science import ScienceOperation
from tests.support.factories import renderer_factory, science_factory

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def runtime(tmp_path):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required for executed PostgreSQL gates")
    store = Store(database_url)
    store.migrate()
    ws = str(uuid4())
    store.ensure_workspace(ws)
    settings = SimpleNamespace(data_root=tmp_path, config_dir=ROOT / "config", openai_api_key=None, openai_model=None)
    from analogforge.application.seed import _write_synthetic_lock

    _write_synthetic_lock(settings)
    engine = WorkflowEngine(store, settings, science_factory(), renderer_factory())

    def make(scenario="synthetic-mars-mobility-v1", no_rover=False):
        names = {
            "synthetic-mars-mobility-v1": "mission-mars-mobility.json",
            "synthetic-graph-regression-v1": "mission-graph-regression.json",
            "synthetic-moon-gap-v1": "mission-moon-gap.json",
        }
        mission = json.loads((ROOT / "tests/fixtures/kit/missions" / names[scenario]).read_text())
        rover = json.loads((ROOT / "tests/fixtures/kit/rovers/ares-1.json").read_text())
        mid, rid, runid = str(uuid4()), str(uuid4()), str(uuid4())
        mission.update(
            schema_version="1.0",
            created_at=utc_now(),
            id=mid,
            mission_id=str(uuid4()),
            workspace_id=ws,
            accepted_at=utc_now(),
        )
        # Rover imports have no DB envelope; turn the kit profile into its immutable saved revision.
        if "profile" in rover:
            rover = rover["profile"]
        rover = {
            **rover,
            "schema_version": "1.0",
            "id": rid,
            "rover_id": str(uuid4()),
            "workspace_id": ws,
            "revision": 1,
            "created_at": utc_now(),
        }
        from analogforge.domain.hashing_utils import content_hash

        mission["content_sha256"] = content_hash(mission, "mission")
        rover["content_sha256"] = content_hash(rover, "rover")
        run = {
            "schema_version": "1.0",
            "id": runid,
            "run_id": runid,
            "workspace_id": ws,
            "mode": "synthetic",
            "created_at": utc_now(),
            "state": "DRAFT",
            "revision": 1,
            "last_event_seq": 0,
            "mission_revision_id": mid,
            "rover_revision_id": None if no_rover else rid,
            "target_profile_id": None,
            "candidate_ids": [],
            "qualification_ids": [],
            "test_ids": [],
            "test_result_ids": [],
            "portfolio_ids": [],
            "passport_id": None,
            "pending_review": None,
            "blocked_dependencies": [],
            "config_sha256": canonical_sha256({"test": "runtime"}),
            "selected_candidate_id": None,
            "selected_portfolio_id": None,
            "scenario_config_id": scenario,
            "dataset_lock_id": "synthetic-policy-v1",
            "runtime": {},
        }
        with store.transaction(ws) as tx:
            tx.create("missions", {"id": mission["mission_id"], "name": mission["name"]})
            tx.create("mission_revisions", mission)
            tx.create("mission_acceptances", {"mission_revision_id": mid, "accepted_at": mission["accepted_at"]})
            if not no_rover:
                tx.create("rovers", {"id": rover["rover_id"], "name": rover["name"]})
                tx.create("rover_revisions", rover)
            tx.create("runs", run)
        return run

    yield engine, store, ws, make
    with store.transaction(ws) as tx:
        for job in tx.list("jobs"):
            if job["state"] in {"QUEUED", "RUNNING"}:
                tx.replace(
                    "jobs", job["id"], {**job, "state": "CANCELLED", "lease_token": None, "lease_expires_at": None}
                )
    store.close()


def advance_until(engine, run, ws, target):
    for _ in range(30):
        if run["state"] in target:
            return run
        run = engine.advance(run["id"], ws)
    pytest.fail("Workflow failed to reach a bounded checkpoint")


def test_runtime_graph_end_to_end(runtime):
    engine, store, ws, make = runtime
    run = advance_until(engine, make("synthetic-graph-regression-v1"), ws, {"AWAITING_REVIEW"})
    run = engine.apply_action(run["id"], ws, "PROVE_IT", {}, run["revision"])
    run = advance_until(engine, run, ws, {"COMPLETED", "BLOCKED", "FAILED"})
    assert run["state"] == "COMPLETED"
    with store.transaction(ws) as tx:
        results = tx.list("test_results", {"run_id": run["id"]})
        assert [r["outcome"] for r in results] == ["FAIL", "PASS"]
        tests = tx.list("tests", {"run_id": run["id"]})
        assert [t["strategy"] for t in tests] == ["WAYPOINT_RETURN", "EXPOSURE_COVERAGE"]
        assert len({t["constraints"]["mission_content_sha256"] for t in tests}) == 1
        assert tx.require("passports", run["passport_id"])["assurance_evidence_id"]
        roles = {r["role"] for r in tx.list("role_results", {"run_id": run["id"]})}
        assert len(roles) == 10


def test_runtime_transition_and_successor_are_atomic(runtime, monkeypatch):
    engine, store, ws, make = runtime
    run = make("synthetic-graph-regression-v1")
    from analogforge.db.store import UnitOfWork

    original = UnitOfWork.enqueue

    def fail_enqueue(self, *args, **kwargs):
        if args[0] == "ADVANCE_RUN":
            raise RuntimeError("Injected crash before successor enqueue")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(UnitOfWork, "enqueue", fail_enqueue)
    with pytest.raises(RuntimeError, match="Injected crash"):
        engine.advance(run["id"], ws)
    with store.transaction(ws) as tx:
        assert tx.require("runs", run["id"])["state"] == "DRAFT"
        assert tx.list("run_events", {"run_id": run["id"]}) == []
        assert tx.list("jobs", {"run_id": run["id"]}) == []


class PerturbedScience:
    def __init__(self, underlying):
        self.underlying = underlying

    def supported_operations(self):
        return self.underlying.supported_operations()

    def execute(self, request, context):
        result = self.underlying.execute(request, context)
        payload = result.payload
        if request.operation == ScienceOperation.VERIFY_ROUTE and payload.outcome == "PASS":
            raw = payload.model_dump(mode="json")
            raw.update(
                outcome="FAIL",
                failure_category="ROUTE",
                violations=[
                    {
                        "code": "EXPOSURE_SHORTFALL",
                        "requirement_id": "R-EXPOSURE",
                        "constraint_id": "C-EXPOSURE-R-EXPOSURE",
                        "observed": 0.0,
                        "threshold": 100.0,
                        "unit": "m",
                        "segment_from_index": None,
                        "segment_to_index": None,
                        "message": "Perturbed independent verifier test receipt",
                    }
                ],
            )
            for metric in raw["metrics"]:
                if metric["metric_id"].startswith("unique_exposure_m"):
                    metric["value"] = 0.0
            for row in raw["benchmark_rows"]:
                if row["constraint_id"] == "C-EXPOSURE-R-EXPOSURE":
                    row.update(status="FAIL", measured=0.0, margin=-100.0)
            payload = type(payload).model_validate(raw)
        elif (
            request.operation == ScienceOperation.DIAGNOSE_RESULT
            and request.inputs.constraints.strategy == "EXPOSURE_COVERAGE"
        ):
            payload = payload.model_copy(
                update={
                    "recommended_repair": None,
                    "permitted_repairs": [],
                    "recommended_strategy": None,
                    "explanation": "Perturbed diagnosis reports no permitted repair",
                }
            )
        if payload is not result.payload:
            artifacts = []
            for draft in result.artifacts:
                if draft.media_type == "application/json":
                    content = canonical_json_bytes(payload)
                    (context.scratch_dir() / draft.scratch_relpath).write_bytes(content)
                    draft = draft.model_copy(update={"sha256": bytes_sha256(content), "size_bytes": len(content)})
                artifacts.append(draft)
            result = result.model_copy(update={"payload": payload, "artifacts": artifacts})
        return result


def test_runtime_changed_verifier_and_diagnosis_change_storyline(runtime):
    engine, store, ws, make = runtime
    engine.science = PerturbedScience(engine.science)
    run = advance_until(engine, make("synthetic-graph-regression-v1"), ws, {"AWAITING_REVIEW"})
    run = engine.apply_action(run["id"], ws, "PROVE_IT", {}, run["revision"])
    run = advance_until(engine, run, ws, {"COMPLETED", "BLOCKED", "FAILED"})
    assert run["state"] == "COMPLETED"
    with store.transaction(ws) as tx:
        results = tx.list("test_results", {"run_id": run["id"]})
        assert [r["outcome"] for r in results] == ["FAIL", "FAIL"]
        assert len(tx.list("tests", {"run_id": run["id"]})) == 2
        passport = tx.require("passports", run["passport_id"])
        assert not any("verified route" in use.lower() for use in passport["qualified_uses"])
    assert run["runtime"]["stop_reason"] == "NO_PERMITTED_REPAIR"


def test_runtime_critic_opens_then_repairs_durable_proposal(runtime):
    engine, store, ws, make = runtime
    run = advance_until(engine, make(), ws, {"CRITIQUING"})
    run = engine.advance(run["id"], ws)
    assert run["state"] == "CRITIQUING"
    with store.transaction(ws) as tx:
        issues = tx.list("critiques", {"run_id": run["id"]})
        assert any(i["status"] == "OPEN" and i["reason_code"] == "SCALE_MISMATCH" for i in issues)
        rejected = [
            r for r in tx.list("role_results", {"run_id": run["id"]}) if r.get("error_code") == "SCALE_INCOMPATIBLE"
        ]
        assert rejected and rejected[0]["status"] == "BLOCKED"
        assert any(q["critic_status"] == "CHALLENGED" for q in tx.list("qualifications", {"run_id": run["id"]}))
    run = engine.advance(run["id"], ws)
    assert run["state"] == "AWAITING_REVIEW"
    with store.transaction(ws) as tx:
        assert all(
            i["status"] == "RESOLVED" for i in tx.list("critiques", {"run_id": run["id"]}) if i.get("seeded_citation")
        )
        events = tx.list("run_events", {"run_id": run["id"]})
        opened = next(e["seq"] for e in events if e["event_type"] == "critic.issue_opened")
        resolved = next(e["seq"] for e in events if e["event_type"] == "critic.issue_resolved")
        assert resolved > opened


def test_runtime_rejected_claim_blocks_run_without_passport(runtime, monkeypatch):
    """Architecture 33 s2.7/s6: a refused positive claim stops the run in a defined state; no passport is published."""
    engine, store, ws, make = runtime
    run = advance_until(engine, make("synthetic-graph-regression-v1"), ws, {"AWAITING_REVIEW"})
    run = engine.apply_action(run["id"], ws, "PROVE_IT", {}, run["revision"])
    from analogforge.application import passports
    from analogforge.application.assurance import ScientificClaimRejected

    def reject(*_args, **_kwargs):
        raise ScientificClaimRejected(["v:injected:POSITIVE_CLAIM_UNSUPPORTED"])

    monkeypatch.setattr(passports, "audit", reject)
    run = advance_until(engine, run, ws, {"COMPLETED", "BLOCKED", "FAILED"})
    assert run["state"] == "BLOCKED"
    assert run["blocked_dependencies"] == ["SCIENTIFIC_CLAIM_REJECTED"]
    assert run["runtime"]["stop_reason"] == "SCIENTIFIC_CLAIM_REJECTED"
    assert run["runtime"]["claim_rejection_issues"] == ["v:injected:POSITIVE_CLAIM_UNSUPPORTED"]
    assert run["passport_id"] is None
    with store.transaction(ws) as tx:
        assert tx.list("passports", {"run_id": run["id"]}) == []
        assert [e["event_type"] for e in tx.list("run_events", {"run_id": run["id"]})][-1] == "run.blocked"
