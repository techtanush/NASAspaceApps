"""Rejected science publication finalizes its invocation and reaches normal worker failure handling."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.application.registrar import RegistrationRejected
from analogforge.application.scheduler import WorkflowEngine
from analogforge.application.seed import seed_synthetic
from analogforge.jobs import cpu
from analogforge.jobs.worker import Worker
from analogforge.ports.hashing import bytes_sha256, canonical_sha256
from analogforge.ports.science import ArtifactDraft, ScienceComputationResult, ScienceIssue, ScienceOperation
from analogforge.ports.science_payloads import ResolveCoverageInput, ResolveCoveragePayload
from analogforge.settings import Settings
from tests.unit.platform.test_registrar import StoreDouble


class WorkerStoreDouble(StoreDouble):
    def require(self, kind, identifier, **_kwargs):
        return self.data[kind][identifier]

    def replace(self, kind, identifier, value, *_args):
        self.data[kind][identifier] = deepcopy(value)

    @contextmanager
    def publication(self, workspace, _job, _lease):
        with self.transaction(workspace) as tx:
            self.in_publication = True
            try:
                yield tx
            finally:
                self.in_publication = False

    def record_worker_heartbeat(self, _worker_id):
        pass

    def reap_expired_jobs(self):
        return 0

    def claim_job(self, **_kwargs):
        job = next(iter(self.data["jobs"].values()))
        if job["state"] != "QUEUED":
            return None
        job["state"] = "RUNNING"
        return deepcopy(job)


class UnpublishableScience:
    def supported_operations(self):
        return frozenset(ScienceOperation)

    def execute(self, request, context):
        content = b"<html>Unpermitted derived artifact</html>"
        path = context.scratch_dir() / "invalid.html"
        path.write_bytes(content)
        return ScienceComputationResult(
            request_id=request.request_id, operation=request.operation, mode=request.mode, status="SUCCEEDED",
            algorithm_id="test-double", algorithm_version="1.0", parameters_sha256="0" * 64,
            input_sha256=canonical_sha256(request), payload=ResolveCoveragePayload(selections=[]),
            artifacts=[ArtifactDraft(
                local_key="invalid", scratch_relpath=path.name, sha256=bytes_sha256(content),
                size_bytes=len(content), media_type="text/html", role="DERIVED_JSON", body="MARS",
            )],
        )


class ReturnedScience(UnpublishableScience):
    def __init__(self, status):
        self.status = status

    def execute(self, request, context):
        return ScienceComputationResult(
            request_id=request.request_id, operation=request.operation, mode=request.mode, status=self.status,
            algorithm_id="test-double", algorithm_version="1.0", parameters_sha256="0" * 64,
            input_sha256=canonical_sha256(request),
            payload=ResolveCoveragePayload(selections=[]) if self.status in {"SUCCEEDED", "LIMITED"} else None,
            issues=[] if self.status == "SUCCEEDED" else [ScienceIssue(code="NO_COVERAGE", message="Test outcome")],
        )


@pytest.fixture
def rejected_computation(tmp_path, monkeypatch):
    workspace, run_id, job_id = (str(uuid4()) for _ in range(3))
    store = WorkerStoreDouble(workspace, run_id)
    run = store.require("runs", run_id)
    run.update(scenario_config_id="synthetic-mars-mobility-v1", config_sha256="0" * 64,
               dataset_lock_id="synthetic-policy-v1", runtime={})
    job = {"id": job_id, "workspace_id": workspace, "run_id": run_id,
           "lease_token": str(uuid4()), "state": "QUEUED"}
    store.create("jobs", job)
    settings = Settings(_env_file=None, data_root=tmp_path, config_dir=Path(__file__).resolve().parents[3] / "config")
    seed_synthetic(None, settings)
    engine = WorkflowEngine(store, settings, science=UnpublishableScience())
    monkeypatch.setattr(engine, "_load", lambda *_: (store.require("runs", run_id), {}, None))
    monkeypatch.setattr(engine, "_charge", lambda *_: None)
    monkeypatch.setattr(cpu, "run_science", lambda service, request, context, **_: service.execute(request, context))
    inputs = ResolveCoverageInput(
        subject_kind="TARGET", adapter_id="synthetic_practice", measurement_kinds=["terrain"],
        aoi={"body": "MARS", "bbox": [137, -5, 138, -4], "longitude_convention": "NEG180_180",
             "latitude_type": "PLANETOCENTRIC", "crs_wkt": None, "vertical_datum": "Unknown"},
    )
    return engine, store, inputs, workspace, run_id, job


def test_rejected_registration_finalizes_invocation_and_worker_run_job(rejected_computation, monkeypatch):
    engine, store, inputs, workspace, run_id, job = rejected_computation

    def handle(claimed):
        engine._compute(inputs, run_id, workspace, job_id=claimed["id"], lease_token=claimed["lease_token"])

    worker = Worker(store, handle)
    monkeypatch.setattr(worker, "_heartbeats", lambda *_: None)
    assert worker.run_once()
    assert store.require("jobs", job["id"])["state"] == "FAILED"
    assert store.require("jobs", job["id"])["error"]["code"] == "SOURCE_CONTENT_INVALID"
    assert store.require("runs", run_id)["state"] == "FAILED"
    invocations = store.list("invocations")
    assert len(invocations) == 1 and invocations[0]["status"] == "FAILED"
    assert store.list("evidence") == []
    assert store.list("artifacts") == []
    assert store.list("scientific_operations") == []
    assert store.list("tool_receipts")[-1]["status"] == "FAILED"
    assert list((engine.settings.data_root / "scratch/quarantine").glob("*/invalid.html"))


def test_invocation_cleanup_preserves_the_original_registration_exception(rejected_computation, monkeypatch):
    engine, store, inputs, workspace, run_id, _ = rejected_computation
    failure = RegistrationRejected("Original registration failure")

    def reject(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(engine.registrar, "register", reject)
    with pytest.raises(RegistrationRejected) as caught:
        engine._compute(inputs, run_id, workspace)
    assert caught.value is failure
    assert store.list("invocations")[0]["status"] == "FAILED"


def test_cleanup_storage_failure_does_not_replace_registration_error(rejected_computation, monkeypatch, caplog):
    engine, store, inputs, workspace, run_id, _ = rejected_computation
    failure = RegistrationRejected("Original registration failure")

    def reject(*_args, **_kwargs):
        raise failure

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private database connection details")

    monkeypatch.setattr(engine.registrar, "register", reject)
    monkeypatch.setattr(store, "replace", unavailable)
    with pytest.raises(RegistrationRejected) as caught:
        engine._compute(inputs, run_id, workspace)
    assert caught.value is failure
    assert "science.invocation_finalize_failed" in caplog.text
    assert "private database" not in caplog.text


@pytest.mark.parametrize("outcome,invocation_status,receipt_status", [
    ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED"),
    ("LIMITED", "SUCCEEDED", "SUCCEEDED"),
    ("BLOCKED", "SUCCEEDED", "BLOCKED"),
    ("FAILED", "FAILED", "FAILED"),
])
def test_published_science_invocation_finishes_in_publication_transaction(
    rejected_computation, monkeypatch, outcome, invocation_status, receipt_status,
):
    engine, store, inputs, workspace, run_id, job = rejected_computation
    engine.science = ReturnedScience(outcome)
    updates = []
    replace = store.replace

    def record_replace(kind, identifier, value, *args):
        if kind == "invocations":
            updates.append((value["status"], getattr(store, "in_publication", False)))
        return replace(kind, identifier, value, *args)

    monkeypatch.setattr(store, "replace", record_replace)
    registered = engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"])
    assert registered.status == outcome
    assert store.list("invocations")[0]["status"] == invocation_status
    assert updates == [(invocation_status, True)]
    assert store.list("scientific_operations")[0]["status"] == outcome
    assert store.list("tool_receipts")[0]["status"] == receipt_status


def test_late_publication_rejection_rolls_back_successful_invocation_and_operation(rejected_computation):
    engine, store, inputs, workspace, run_id, job = rejected_computation
    engine.science = ReturnedScience("SUCCEEDED")
    staged_invocations = []

    def reject_publication(tx, _registered):
        staged_invocations.extend(row["status"] for row in tx.list("invocations"))
        tx.create("target_profiles", {"id": str(uuid4()), "run_id": run_id})
        raise RegistrationRejected("Rejected late domain publication")

    with pytest.raises(RegistrationRejected, match="Rejected late domain publication"):
        engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"],
                        publish=reject_publication)
    assert staged_invocations == ["SUCCEEDED"]
    assert store.list("invocations")[0]["status"] == "FAILED"
    assert store.list("scientific_operations") == []
    assert store.list("target_profiles") == []
    assert store.list("tool_receipts")[-1]["status"] == "FAILED"


def test_science_start_is_committed_before_cpu_execution(rejected_computation, monkeypatch):
    engine, store, inputs, workspace, run_id, job = rejected_computation
    engine.science = ReturnedScience("LIMITED")
    events = []

    def record(_run_id, event_type, payload, _mode):
        assert store.in_publication
        events.append((event_type, deepcopy(payload)))

    def compute(service, request, context, **_kwargs):
        assert events[0][0] == "tool.started"
        assert events[0][1]["operation"] == inputs.operation
        assert store.list("invocations")[0]["status"] == "RUNNING"
        assert not store.in_publication
        return service.execute(request, context)

    monkeypatch.setattr(store, "append_event", record)
    monkeypatch.setattr(cpu, "run_science", compute)
    engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"])
    assert [event[0] for event in events] == ["tool.started", "tool.completed"]
    assert events[-1][1]["status"] == "LIMITED"


def test_science_cpu_failure_records_failed_transition_without_fabricating_receipt(rejected_computation, monkeypatch):
    engine, store, inputs, workspace, run_id, job = rejected_computation
    events = []
    monkeypatch.setattr(store, "append_event", lambda _run, kind, payload, _mode: events.append((kind, payload)))

    def fail(*_args, **_kwargs):
        raise RuntimeError("private provider/token detail")

    monkeypatch.setattr(cpu, "run_science", fail)
    with pytest.raises(RuntimeError):
        engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"])
    assert [e[0] for e in events] == ["tool.started", "tool.completed"]
    assert events[-1][1]["status"] == "FAILED" and "private" not in str(events)
    assert store.list("tool_receipts") == [] and store.list("scientific_operations") == []


def test_science_start_cannot_run_after_lease_loss(rejected_computation, monkeypatch):
    from analogforge.db.store import LeaseLost

    engine, store, inputs, workspace, run_id, job = rejected_computation

    @contextmanager
    def lost(*_args):
        raise LeaseLost()
        yield

    monkeypatch.setattr(store, "publication", lost)
    monkeypatch.setattr(cpu, "run_science", lambda *_a, **_k: pytest.fail("Lost lease executed work"))
    with pytest.raises(LeaseLost):
        engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"])
    assert store.list("invocations") == []


def test_science_start_cannot_run_after_cancellation_at_the_execution_boundary(rejected_computation, monkeypatch):
    from analogforge.ports.science import ScienceCancelled

    engine, store, inputs, workspace, run_id, _job = rejected_computation
    events = []
    monkeypatch.setattr(engine, "_charge", lambda *_args: store.require("runs", run_id).update(state="CANCELLED"))
    monkeypatch.setattr(store, "append_event", lambda *_args: events.append(_args))
    monkeypatch.setattr(cpu, "run_science", lambda *_a, **_k: pytest.fail("Cancelled work executed"))
    with pytest.raises(ScienceCancelled):
        engine._compute(inputs, run_id, workspace)
    assert store.list("invocations") == [] and events == []


def test_science_deadline_is_a_blocked_attempt_not_a_scientific_failure(rejected_computation, monkeypatch):
    from analogforge.ports.science import ScienceDeadlineExceeded

    engine, store, inputs, workspace, run_id, job = rejected_computation
    events = []
    monkeypatch.setattr(store, "append_event", lambda _run, kind, payload, _mode: events.append((kind, payload)))

    def timeout(*_args, **_kwargs):
        raise ScienceDeadlineExceeded()

    monkeypatch.setattr(cpu, "run_science", timeout)
    with pytest.raises(ScienceDeadlineExceeded):
        engine._compute(inputs, run_id, workspace, job_id=job["id"], lease_token=job["lease_token"])
    assert events[-1][1]["status"] == "BLOCKED"
    assert store.list("tool_receipts") == [] and store.list("scientific_operations") == []
