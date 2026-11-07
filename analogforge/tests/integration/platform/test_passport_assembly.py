from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.application.assurance import ScientificClaimRejected, audit
from analogforge.application.passports import PassportSnapshot, assemble_bundle
from analogforge.ports.domain_models import EarthAnalogCandidate, MissionTestContract, QualificationDimension
from analogforge.ports.hashing import MISSION_CONTENT_EXCLUDE, bytes_sha256, canonical_json_bytes, model_sha256
from analogforge.ports.passport_renderer import SourceLocks
from tests.integration.platform.test_assurance import audit_case


def passport_case():
    snapshot, claim, receipts = audit_case("FAIL")
    mission_path = Path(__file__).parents[2] / "fixtures" / "kit" / "blueprint-mission-contract.json"
    raw = json.loads(mission_path.read_text())
    raw.update(
        workspace_id=str(snapshot.workspace_id),
        requirements=[raw["requirements"][0]],
        accepted_at="2026-11-06T00:00:00Z",
    )
    mission = MissionTestContract.model_validate(raw)
    mission.content_sha256 = model_sha256(mission, MISSION_CONTENT_EXCLUDE)
    candidate = EarthAnalogCandidate(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=snapshot.workspace_id,
        run_id=snapshot.run_id,
        mode="synthetic",
        created_at=datetime.now(UTC),
        name="Synthetic negative control",
        aoi={
            "body": "EARTH",
            "bbox": [-111, 35, -110, 36],
            "longitude_convention": "NEG180_180",
            "latitude_type": "GEODETIC",
            "crs_wkt": "EPSG:4326",
            "vertical_datum": "SYNTHETIC_TEST",
        },
        origin="SYNTHETIC_CONTROL",
        discovery_method="Bounded synthetic test",
        novelty_status="NOT_ASSESSED",
        evidence_ids=list(claim.evidence_ids),
        metrics=[],
        accessibility_status="NOT_ASSESSED",
        limitations=[],
    )
    row = QualificationDimension(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=snapshot.workspace_id,
        run_id=snapshot.run_id,
        mode="synthetic",
        created_at=datetime.now(UTC),
        candidate_id=candidate.id,
        requirement_id=mission.requirements[0].id,
        status="FAIL",
        evidence_ids=list(claim.evidence_ids),
        rule_id="test-rule",
        rule_version="1",
        confidence="MEDIUM",
        comparison_scale_m=60,
        explanation="Synthetic measured shortfall",
        limitations=[],
        critic_status="ACCEPTED",
        critique_evidence_ids=[],
    )
    snapshot = replace(snapshot, mission_content_sha256=mission.content_sha256)
    claim = replace(claim, requirement_id=row.requirement_id, candidate_ids=(candidate.id,))
    report = audit(snapshot, [claim], receipts)
    first_evidence = next(iter(snapshot.evidence.values()))
    assurance_evidence = first_evidence.model_copy(
        update={
            "id": uuid4(),
            "algorithm_id": "scientific-assurance",
            "algorithm_version": "1.0",
            "artifact_sha256": bytes_sha256(canonical_json_bytes(report)),
            "artifact_media_type": "application/json",
            "input_evidence_ids": list(claim.evidence_ids),
        }
    )
    return PassportSnapshot(
        audit=report,
        assurance_evidence=assurance_evidence,
        mission=mission,
        rover=None,
        candidates=(candidate,),
        qualifications=(row,),
        source_locks=SourceLocks(
            dataset_policy_sha256=report.dataset_policy_sha256,
            acquired_manifest_sha256=report.acquired_manifest_sha256,
            config_sha256="6" * 64,
            algorithm_lock_sha256=report.algorithm_lock_sha256,
        ),
        evidence=tuple(snapshot.evidence.values()),
        generated_at=datetime(2026, 11, 6, tzinfo=UTC),
        passport_id=uuid4(),
    )


def test_manifest_is_independently_reproducible_and_acyclic():
    snapshot = passport_case()
    bundle = assemble_bundle(snapshot)
    parsed = json.loads(bundle.canonical_manifest_json)
    assert bytes_sha256(canonical_json_bytes(parsed)) == bundle.manifest_sha256
    assert bundle.manifest_sha256 == bundle.passport.manifest_sha256
    assert "manifest_sha256" not in parsed
    assert str(snapshot.assurance_evidence.id) == parsed["decisions"]["assurance_evidence_id"]
    assert snapshot.assurance_evidence.id in bundle.passport.evidence_ids
    assert bundle.assurance.publication == "ALLOWED"
    assert bundle.passport.qualified_uses == []
    assert "site qualification only" in bundle.not_run_reason
    assert assemble_bundle(snapshot).model_dump(mode="json") == bundle.model_dump(mode="json")


@pytest.mark.parametrize(
    "defect",
    [
        "hash",
        "audit_hash",
        "assurance_bytes",
        "mode",
        "missing_row",
        "missing_evidence",
        "self_parent",
        "blocked",
        "lock",
    ],
)
def test_inconsistent_frozen_snapshot_is_rejected(defect):
    snapshot = passport_case()
    if defect == "hash":
        snapshot = replace(
            snapshot, mission=snapshot.mission.model_copy(update={"objective": "Changed after acceptance"})
        )
    elif defect == "audit_hash":
        snapshot = replace(snapshot, audit=snapshot.audit.model_copy(update={"mission_content_sha256": "0" * 64}))
    elif defect == "assurance_bytes":
        snapshot = replace(
            snapshot, assurance_evidence=snapshot.assurance_evidence.model_copy(update={"artifact_sha256": "0" * 64})
        )
    elif defect == "mode":
        snapshot = replace(snapshot, candidates=(snapshot.candidates[0].model_copy(update={"mode": "live"}),))
    elif defect == "missing_row":
        snapshot = replace(snapshot, qualifications=())
    elif defect == "missing_evidence":
        snapshot = replace(snapshot, evidence=())
    elif defect == "self_parent":
        record = snapshot.evidence[0]
        snapshot = replace(snapshot, evidence=(record.model_copy(update={"input_evidence_ids": [record.id]}),))
    elif defect == "blocked":
        snapshot = replace(snapshot, audit=snapshot.audit.model_copy(update={"publication": "BLOCKED"}))
    elif defect == "lock":
        snapshot = replace(
            snapshot, source_locks=snapshot.source_locks.model_copy(update={"algorithm_lock_sha256": "0" * 64})
        )
    with pytest.raises(ScientificClaimRejected):
        assemble_bundle(snapshot)


def test_changing_scientific_limitation_changes_manifest():
    snapshot = passport_case()
    first = assemble_bundle(snapshot)
    second = assemble_bundle(replace(snapshot, search_limitations=("Bounded model; not a field validation",)))
    assert first.manifest_sha256 != second.manifest_sha256
    assert "Bounded model" in second.canonical_manifest_json


def test_multinode_evidence_cycle_is_rejected():
    snapshot = passport_case()
    a = snapshot.evidence[0]
    b = a.model_copy(update={"id": uuid4(), "input_evidence_ids": [a.id]})
    a = a.model_copy(update={"input_evidence_ids": [b.id]})
    with pytest.raises(ScientificClaimRejected, match="EVIDENCE_CYCLE"):
        assemble_bundle(replace(snapshot, evidence=(a, b)))
