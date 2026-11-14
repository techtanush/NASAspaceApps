"""An actual scientific passport draft stays unpublished until role review accepts it."""

import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.agents.runtime.openai_provider import _expand_wire_task
from analogforge.agents.runtime.provider import ProviderError
from analogforge.application.assurance import ScientificClaimRejected, audit_registered_claim
from analogforge.application.passports import publish_passport
from analogforge.application.qualification import evaluate_candidate
from analogforge.application.registrar import Registrar
from analogforge.application.scheduler import WorkflowEngine, WorkflowRolePaused
from analogforge.db.store import PersistenceError
from analogforge.settings import Settings
from tests.unit.platform.test_registered_validation_levels import comparison_publication

__all__ = ["comparison_publication"]


@pytest.fixture
def publication_ready(comparison_publication, monkeypatch, tmp_path):
    store, blobs, mission, request, result, kwargs, candidate = comparison_publication
    workspace, run_id = kwargs["workspace_id"], kwargs["run_id"]

    def qualify(unit, registered):
        row = evaluate_candidate(workspace, run_id, "live", str(candidate.id), registered.required_payload,
                                 list(registered.evidence_ids))
        audit_registered_claim(unit, unit.require("runs", run_id), mission, None, row,
                               registered.required_payload, blobs)
        unit.create("qualifications", row)
        unit.require("runs", run_id)["qualification_ids"] = [row["id"]]

    Registrar(store, blobs).register(request, result, apply_payload=qualify, **kwargs)
    run = store.require("runs", run_id)
    run.update(state="BUILDING_PASSPORT", scenario_config_id="live-hackathon-v1")
    store.require("candidates", str(candidate.id))["window_id"] = "offline-window"
    acceptance = store.list("mission_acceptances")[0]
    acceptance["created_at"] = acceptance["accepted_at"]
    # Model the real store's revision/event behavior, including _role's ordinary diagnostic changes.
    original_replace, original_transaction = store.replace, store.transaction
    depth = [0]

    def replace(kind, identifier, value, expected_revision=None):
        value = deepcopy(value)
        current = store.require(kind, identifier)
        if expected_revision is not None:
            assert current["revision"] == expected_revision
        if kind == "runs":
            value["revision"] = current["revision"] + 1
        return original_replace(kind, identifier, value, expected_revision)

    @contextmanager
    def transaction(scope):
        depth[0] += 1
        try:
            with original_transaction(scope) as unit:
                yield unit
        finally:
            depth[0] -= 1

    def event(identifier, event_type, payload, mode):
        current = deepcopy(store.require("runs", identifier))
        current["last_event_seq"] = current.get("last_event_seq", 0) + 1
        store.replace("runs", identifier, current, current["revision"])
        return store.create("run_events", {"run_id": identifier, "event_type": event_type, "payload": payload})

    monkeypatch.setattr(store, "replace", replace)
    monkeypatch.setattr(store, "transaction", transaction)
    monkeypatch.setattr(store, "append_event", event)
    settings = Settings(_env_file=None, data_root=tmp_path,
                        config_dir=Path(__file__).resolve().parents[3] / "config")
    engine = WorkflowEngine(store, settings)
    engine.blobs = blobs
    monkeypatch.setattr(engine, "_audit", lambda *_: {"claim_gates": [], "findings": []})
    return engine, store, blobs, workspace, run_id, depth


def exports(store):
    return [job for job in store.list("jobs") if job["kind"] == "EXPORT_PASSPORT"]


def passport_events(store):
    return [event for event in store.list("run_events") if event["event_type"] == "passport.created"]


@pytest.mark.parametrize("response", ["review", "not_ready", "blocking", "provider_failure", "warning", "accept"])
def test_real_draft_review_precedes_publication_and_runs_outside_transactions(publication_ready, monkeypatch, response):
    engine, store, _blobs, workspace, run_id, depth = publication_ready
    before_revision = store.require("runs", run_id)["revision"]
    calls = []

    class Client:
        def create(self, **kwargs):
            assert depth[0] == 0
            assert store.list("passports") == exports(store) == passport_events(store) == []
            task = _expand_wire_task(json.loads(kwargs["input"][0]["content"])["task"])
            calls.append(task)
            if response == "provider_failure":
                raise ProviderError("MODEL_OUTPUT_INVALID", "Controlled test failure")
            proposal = deepcopy(task["payload"]["prepared_submission"])
            if response == "review":
                proposal.update(disposition="NEEDS_USER_REVIEW", next_action="request_review")
            if response == "not_ready":
                proposal["payload"]["ready_to_publish"] = False
            if response in {"blocking", "warning"}:
                proposal["issues"] = [{"code": "EVIDENCE_LIMITATION", "severity": "BLOCKING" if response == "blocking"
                                       else "WARNING", "requirement_id": None, "evidence_ids": [],
                                       "message": "A retained role concern.", "recommended_action": "review"}]
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "review-draft", "arguments": json.dumps(proposal)}]}

    monkeypatch.setattr(engine, "_provider_client", lambda: Client())
    run, mission, rover = engine._load(run_id, workspace)
    if response in {"review", "not_ready", "blocking", "provider_failure"}:
        with pytest.raises(ProviderError if response == "provider_failure" else WorkflowRolePaused):
            engine._advance_step(run, mission, rover, workspace, None, None)
        assert store.list("passports") == exports(store) == passport_events(store) == []
        assert not store.require("runs", run_id).get("passport_id")
    else:
        completed = engine._advance_step(run, mission, rover, workspace, None, None)
        assert completed["state"] == "COMPLETED"
        assert len(store.list("passports")) == len(exports(store)) == len(passport_events(store)) == 1
        assert store.require("runs", run_id)["revision"] > before_revision
    assert len(calls) == 1
    invocation = next(row for row in store.list("invocations") if row["task_kind"] == "assemble_passport")
    assert invocation["status"] == ("FAILED" if response == "provider_failure" else "SUCCEEDED")
    if response in {"blocking", "not_ready"}:
        assert store.list("role_results")[0]["status"] == store.list("agent_actions")[0]["status"] == "BLOCKED"


def test_review_copy_mutation_cannot_change_published_scientific_bundle(publication_ready):
    _engine, store, blobs, workspace, run_id, depth = publication_ready
    reviewed = []

    def review(draft):
        assert depth[0] == 0 and store.list("passports") == []
        reviewed.append(str(draft.passport.id))
        draft.passport.qualified_uses.append("Invented qualification")
        draft.assurance.publication = "BLOCKED"

    bundle = publish_passport(store, workspace, run_id, blobs, before_publish=review)
    assert str(bundle.passport.id) == reviewed[0]
    assert bundle.passport.qualified_uses == [] and bundle.assurance.publication != "BLOCKED"
    saved = store.list("passports")[0]["bundle"]
    assert saved == bundle.model_dump(mode="json")


@pytest.mark.parametrize("change", ["qualification", "selection", "scientific_receipt"])
def test_scientific_change_during_review_rejects_publication(publication_ready, change):
    _engine, store, blobs, workspace, run_id, _depth = publication_ready

    def review(_draft):
        if change == "qualification":
            row = deepcopy(store.list("qualifications")[0])
            row.update(id=str(uuid4()), evaluation_version=2, status="UNKNOWN")
            store.create("qualifications", row)
        elif change == "selection":
            run = deepcopy(store.require("runs", run_id))
            run["selected_candidate_id"] = str(uuid4())
            store.replace("runs", run_id, run, run["revision"])
        else:
            store.create("tool_receipts", {"id": str(uuid4()), "run_id": run_id,
                                           "tool_name": "compare_requirement", "evidence_ids": [], "status": "FAILED"})

    with pytest.raises(ScientificClaimRejected, match="STALE_OR_CANCELLED_PUBLICATION"):
        publish_passport(store, workspace, run_id, blobs, before_publish=review)
    assert store.list("passports") == exports(store) == passport_events(store) == []


def test_prepublication_review_preserves_lease_fence(publication_ready, monkeypatch):
    _engine, store, blobs, workspace, run_id, _depth = publication_ready
    reviewed = []

    @contextmanager
    def lost_lease(*_args):
        raise PersistenceError("LEASE_LOST", "Lease was replaced during review")
        yield

    monkeypatch.setattr(store, "publication", lost_lease)
    with pytest.raises(PersistenceError, match="Lease was replaced"):
        publish_passport(store, workspace, run_id, blobs, before_publish=lambda draft: reviewed.append(draft),
                         job_id=str(uuid4()), lease_token=str(uuid4()))
    assert len(reviewed) == 1 and store.list("passports") == exports(store) == passport_events(store) == []


def test_successful_publication_remains_idempotent_and_does_not_review_again(publication_ready):
    _engine, store, blobs, workspace, run_id, _depth = publication_ready
    reviewed = []
    first = publish_passport(store, workspace, run_id, blobs, before_publish=lambda draft: reviewed.append(draft))
    second = publish_passport(store, workspace, run_id, blobs, before_publish=lambda draft: reviewed.append(draft))
    assert first.model_dump(mode="json") == second.model_dump(mode="json") and len(reviewed) == 1
    assert len(exports(store)) == len(passport_events(store)) == 1
