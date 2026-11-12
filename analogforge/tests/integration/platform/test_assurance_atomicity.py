"""Real PostgreSQL assertion that a claim audit precedes public result commit."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.application.assurance import ScientificClaimRejected, audit_registered_claim
from tests.integration.platform.test_journey_api import journey_store, platform_store
from tests.integration.platform.test_passport_assembly import passport_case

__all__ = ["journey_store", "platform_store"]


def seed_scope(store, snapshot):
    workspace = str(snapshot.audit.workspace_id)
    run_id = str(snapshot.audit.run_id)
    store.ensure_workspace(workspace, "Assurance transaction test")
    mission = snapshot.mission.model_dump(mode="json")
    with store.transaction(workspace) as unit:
        unit.create("missions", {"id": str(snapshot.mission.mission_id), "name": snapshot.mission.name})
        unit.create("mission_revisions", mission)
        run = unit.create(
            "runs",
            {
                "id": run_id,
                "run_id": run_id,
                "mission_revision_id": mission["id"],
                "rover_revision_id": None,
                "mode": "synthetic",
                "state": "QUALIFYING",
                "config_sha256": "1" * 64,
                "runtime": {
                    "mission_content_sha256": mission["content_sha256"],
                    "rover_content_sha256": None,
                    "dataset_policy_sha256": snapshot.source_locks.dataset_policy_sha256,
                    "acquired_manifest_sha256": snapshot.source_locks.acquired_manifest_sha256,
                    "algorithm_lock_sha256": snapshot.source_locks.algorithm_lock_sha256,
                },
            },
        )
    return workspace, run, mission


def register_pending_comparison(unit, snapshot):
    record = snapshot.qualifications[0].model_dump(mode="json")
    evidence = snapshot.evidence[0].model_dump(mode="json")
    unit.create("candidates", snapshot.candidates[0])
    unit.create("evidence", evidence)
    invocation_id = str(uuid4())
    unit.create(
        "agent_invocations",
        {
            "id": invocation_id,
            "run_id": str(snapshot.audit.run_id),
            "preparation_id": None,
            "role": "qualification",
            "status": "SUCCEEDED",
            "input_hash": "1" * 64,
        },
    )
    unit.create(
        "tool_receipts",
        {
            "schema_version": "1.0",
            "id": str(uuid4()),
            "run_id": str(snapshot.audit.run_id),
            "mode": "synthetic",
            "created_at": datetime.now(UTC).isoformat(),
            "invocation_id": invocation_id,
            "tool_name": "compare_requirement",
            "tool_version": "1.0",
            "input_sha256": "1" * 64,
            "output_sha256": "2" * 64,
            "evidence_ids": [evidence["id"]],
            "status": "SUCCEEDED",
            "error_code": None,
            "elapsed_ms": 0,
            "cache_hit": False,
        },
    )
    payload = {
        "proposed_status": record["status"],
        "adequacy": {
            "validation_level": "S1",
            "gates": [
                {
                    "gate_id": gate.gate_id,
                    "outcome": gate.outcome,
                    "reason": gate.reason,
                    "evidence": [{"evidence_id": evidence["id"]}],
                }
                for gate in snapshot.audit.claims[0].gates
            ],
        },
    }
    return record, payload


@pytest.mark.db
def test_invalid_positive_rolls_back_evidence_receipt_and_public_qualification(journey_store, tmp_path):
    snapshot = passport_case()
    workspace, run, mission = seed_scope(journey_store, snapshot)
    with pytest.raises(ScientificClaimRejected):
        with journey_store.transaction(workspace) as unit:
            record, payload = register_pending_comparison(unit, snapshot)
            record["status"] = payload["proposed_status"] = "PASS"
            next(gate for gate in payload["adequacy"]["gates"] if gate["gate_id"] == "SC-04")["outcome"] = "UNSATISFIED"
            audit_registered_claim(unit, run, mission, None, record, payload, ContentAddressedStore(tmp_path))
            unit.create("qualifications", record)
    with journey_store.transaction(workspace) as unit:
        assert unit.list("qualifications", {"run_id": run["id"]}) == []
        assert unit.list("tool_receipts", {"run_id": run["id"]}) == []
        assert unit.list("evidence", {"run_id": run["id"]}) == []


@pytest.mark.db
def test_supported_negative_has_persisted_audit_before_public_row(journey_store, tmp_path):
    snapshot = passport_case()
    workspace, run, mission = seed_scope(journey_store, snapshot)
    with journey_store.transaction(workspace) as unit:
        record, payload = register_pending_comparison(unit, snapshot)
        original = deepcopy(record)
        report = audit_registered_claim(unit, run, mission, None, record, payload, ContentAddressedStore(tmp_path))
        assert report.publication == "ALLOWED"
        assert record["status"] == original["status"] == "FAIL"
        audit_evidence = unit.require("evidence", record["audit_evidence_id"])
        assert audit_evidence["algorithm_id"] == "scientific-assurance"
        assert unit.list("tool_receipts", {"tool_name": "review_evidence_bundle"})
        unit.create("qualifications", record)
    with journey_store.transaction(workspace) as unit:
        assert len(unit.list("qualifications", {"run_id": run["id"]})) == 1
        assert len(unit.list("evidence", {"run_id": run["id"]})) == 2
