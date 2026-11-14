from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.application.assurance import (
    AuditSnapshot,
    ClaimInput,
    ScientificClaimRejected,
    assurance_policy_digest,
    audit,
    compile_conclusions,
)
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import CritiqueIssue, EvidenceRecord, ToolReceipt
from analogforge.ports.science_payloads import GateEvidence

FIXTURES = Path(__file__).parents[2] / "fixtures" / "kit"


def audit_case(status="PASS"):
    workspace_id, run_id, eid = uuid4(), uuid4(), uuid4()
    evidence = EvidenceRecord(
        schema_version="1.0",
        id=eid,
        workspace_id=workspace_id,
        run_id=run_id,
        mode="synthetic",
        created_at=datetime.now(UTC),
        kind="DERIVED",
        artifact_sha256=None,
        artifact_media_type=None,
        source_uri=None,
        dataset_product_id="SYNTHETIC_TEST",
        dataset_version="1",
        granule_id="test",
        license_note="Synthetic fixture",
        body="EARTH",
        aoi=None,
        input_evidence_ids=[],
        parameters_sha256="1" * 64,
        algorithm_id="compare-requirement",
        algorithm_version="1.0",
        native_resolution_m=60,
        comparison_scale_m=60,
        metrics=[],
        limitations=[],
    )
    receipt = ToolReceipt(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=workspace_id,
        run_id=run_id,
        mode="synthetic",
        created_at=datetime.now(UTC),
        invocation_id=uuid4(),
        tool_name="compare_requirement",
        tool_version="1",
        input_sha256="1" * 64,
        output_sha256="2" * 64,
        evidence_ids=[eid],
        status="SUCCEEDED",
        error_code=None,
        elapsed_ms=0,
        cache_hit=False,
    )
    snapshot = AuditSnapshot(
        workspace_id=workspace_id,
        run_id=run_id,
        mode="synthetic",
        mission_content_sha256="1" * 64,
        rover_content_sha256=None,
        dataset_policy_sha256="2" * 64,
        acquired_manifest_sha256="3" * 64,
        algorithm_lock_sha256="4" * 64,
        assurance_policy_sha256="5" * 64,
        snapshot_content={"evidence": [str(eid)], "revision": 1},
        evidence={eid: evidence},
    )
    gates = tuple(
        GateEvidence(
            gate_id=f"SC-{n:02}",
            outcome="SATISFIED",
            reason="Executed synthetic adequacy receipt",
            evidence=[EvidenceRef(evidence_id=eid)],
        )
        for n in range(2, 14)
        if n != 12
    )
    claim = ClaimInput(
        claim_id="q:one",
        claim_type="QUALIFICATION",
        requirement_id="R-ONE",
        candidate_ids=(),
        scope="regional terrain comparison",
        evidence_ids=(eid,),
        qualification_status=status,
        validation_level="S1",
        science_gates=gates,
    )
    return snapshot, claim, [receipt]


def test_supported_negative_is_allowed_and_does_not_become_success():
    snapshot, claim, receipts = audit_case("FAIL")
    report = audit(snapshot, [claim], receipts)
    assert report.publication == "ALLOWED"
    assert report.claims[0].disposition == "SUPPORTED"
    assert report.claims[0].qualification_status == "FAIL"
    assert "outcome FAIL" in report.claims[0].permitted_statement
    conclusions = compile_conclusions(report)
    assert conclusions["qualified_uses"] == []
    assert len(conclusions["unsupported_uses"]) == 1


def test_negative_findings_cannot_invent_evidence_or_relabel_missing_data_as_failure():
    snapshot, claim, receipts = audit_case("FAIL")
    report = audit(snapshot, [replace(claim, evidence_ids=())], receipts)
    assert report.publication == "BLOCKED"
    assert report.claims[0].disposition == "REJECTED"


@pytest.mark.parametrize("status,disposition", [("UNKNOWN", "UNKNOWN"), ("GAP", "GAP"), ("PARTIAL", "LIMITED")])
def test_honest_limited_findings_publish(status, disposition):
    snapshot, claim, receipts = audit_case(status)
    report = audit(snapshot, [claim], receipts)
    assert report.publication == "LIMITED"
    assert report.claims[0].disposition == disposition
    assert len(report.claims[0].gates) == 15
    # The published report must satisfy the frozen JSON schema, which requires a limitation on every
    # non-supported claim (found when the real science engine produced UNKNOWN rows with no limitation text).
    import jsonschema

    schema = json.loads((Path(__file__).parents[3] / "contracts" / "scientific-assurance.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(json.loads(report.model_dump_json()))
    assert report.claims[0].limitations


@pytest.mark.parametrize("gate_id", [f"SC-{n:02}" for n in (*range(2, 12), 13)])
def test_every_scientific_gate_blocks_an_unearned_positive(gate_id):
    snapshot, claim, receipts = audit_case()
    changed = tuple(
        g.model_copy(update={"outcome": "UNSATISFIED"}) if g.gate_id == gate_id else g for g in claim.science_gates
    )
    report = audit(snapshot, [replace(claim, science_gates=changed)], receipts)
    assert report.publication == "BLOCKED"
    assert report.claims[0].disposition == "REJECTED"


@pytest.mark.parametrize(
    "case", ["stale", "hash", "policy", "mode", "level", "row", "dangling", "failed_receipt", "duplicate"]
)
def test_mechanical_integrity_cannot_be_waived(case):
    snapshot, claim, receipts = audit_case()
    if case == "stale":
        snapshot = replace(snapshot, snapshot_is_current=False)
    elif case == "hash":
        snapshot = replace(snapshot, frozen_inputs_match=False)
    elif case == "policy":
        claim = replace(claim, policy_is_pinned=False)
    elif case == "mode":
        evidence = next(iter(snapshot.evidence.values())).model_copy(update={"mode": "live"})
        snapshot = replace(snapshot, evidence={evidence.id: evidence})
    elif case == "level":
        claim = replace(claim, validation_level="S4")
    elif case == "row":
        claim = replace(claim, current_row_matches=False)
    elif case == "dangling":
        claim = replace(claim, evidence_ids=(uuid4(),))
    elif case == "failed_receipt":
        receipts = [receipts[0].model_copy(update={"status": "FAILED"})]
    elif case == "duplicate":
        claim = replace(claim, science_gates=claim.science_gates + (claim.science_gates[0],))
    assert audit(snapshot, [claim], receipts).publication == "BLOCKED"


def test_missing_gate_is_not_assessed_not_success():
    snapshot, claim, receipts = audit_case()
    report = audit(snapshot, [replace(claim, science_gates=claim.science_gates[:-1])], receipts)
    assert report.publication == "BLOCKED"
    assert report.claims[0].gates[12].outcome == "NOT_ASSESSED"


def test_required_gate_cannot_be_marked_not_applicable():
    snapshot, claim, receipts = audit_case()
    changed = tuple(
        g.model_copy(update={"outcome": "NOT_APPLICABLE"}) if g.gate_id == "SC-02" else g for g in claim.science_gates
    )
    assert audit(snapshot, [replace(claim, science_gates=changed)], receipts).publication == "BLOCKED"


def test_unresolved_critic_rejects_positive_but_preserves_negative():
    snapshot, claim, receipts = audit_case()
    issue = CritiqueIssue(
        issue_id=uuid4(),
        run_id=snapshot.run_id,
        candidate_id=None,
        requirement_id="R-ONE",
        target_evidence_ids=list(claim.evidence_ids),
        reason_code="SCALE_MISMATCH",
        severity="BLOCKING",
        status="OPEN",
        summary="Coarse data cannot resolve clearance",
        repair_request="Recompute or downgrade",
        resolution_evidence_ids=[],
    )
    snapshot = replace(snapshot, critiques=(issue,))
    assert audit(snapshot, [claim], receipts).publication == "BLOCKED"
    assert audit(snapshot, [replace(claim, qualification_status="FAIL")], receipts).publication == "ALLOWED"
    bad_resolution = issue.model_copy(update={"status": "RESOLVED"})
    assert audit(replace(snapshot, critiques=(bad_resolution,)), [claim], receipts).publication == "BLOCKED"
    resolved = issue.model_copy(update={"status": "RESOLVED", "resolution_evidence_ids": list(claim.evidence_ids)})
    assert audit(replace(snapshot, critiques=(resolved,)), [claim], receipts).publication == "ALLOWED"


def test_nominal_models_are_limited_and_do_not_claim_observed_performance():
    snapshot, claim, receipts = audit_case()
    report = audit(snapshot, [replace(claim, nominal_model=True, limitations=("Unquantified model error",))], receipts)
    assert report.publication == "LIMITED"
    assert "accepted nominal model" in report.claims[0].permitted_statement
    assert compile_conclusions(report)["qualified_uses"] == []


def test_validation_level_requires_the_correct_executed_receipt_kind_and_algorithm():
    snapshot, claim, receipts = audit_case()
    record = next(iter(snapshot.evidence.values())).model_copy(
        update={"mode": "live", "dataset_product_id": "REAL_TEST_SOURCE"}
    )
    snapshot = replace(
        snapshot,
        mode="live",
        evidence={record.id: record},
        validation_receipts={"independent_verification": (record.id,)},
    )
    receipts = [receipts[0].model_copy(update={"mode": "live"})]
    claim = replace(claim, validation_level="S4")
    assert audit(snapshot, [claim], receipts).publication == "BLOCKED"
    record = record.model_copy(update={"kind": "VERIFICATION", "algorithm_id": "verify-route"})
    snapshot = replace(snapshot, evidence={record.id: record})
    assert audit(snapshot, [claim], receipts).publication == "ALLOWED"


def test_verification_requires_independent_gate_and_final_route_rows():
    snapshot, claim, receipts = audit_case()
    verifier = replace(claim, claim_type="VERIFICATION", qualification_status=None, verification_status="PASS")
    report = audit(snapshot, [verifier], receipts)
    assert report.publication == "ALLOWED"
    assert compile_conclusions(report)["qualified_uses"] == []
    assert len(compile_conclusions(report, route_rows_final_pass=True)["qualified_uses"]) == 1
    weakened = tuple(
        g.model_copy(update={"outcome": "NOT_APPLICABLE"}) if g.gate_id == "SC-11" else g
        for g in verifier.science_gates
    )
    assert audit(snapshot, [replace(verifier, science_gates=weakened)], receipts).publication == "BLOCKED"


def test_blueprint_reports_remain_strict_compatible():
    from analogforge.ports.assurance_models import ScientificAssuranceArtifact

    for path in FIXTURES.glob("blueprint-assurance-*.json"):
        report = ScientificAssuranceArtifact.model_validate(json.loads(path.read_text()))
        assert len(report.claims[0].gates) == 15


def test_policy_digest_pins_observable_rules_together_with_gate_registry(tmp_path):
    from analogforge.ports.hashing import canonical_sha256

    registry = json.loads((Path(__file__).parents[3] / "contracts" / "scientific-gates.json").read_text())
    path = tmp_path / "algorithms.yaml"
    path.write_text("observable_policies:\n  terrain-v1:\n    minimum_valid_fraction: 0.8\n")
    first = assurance_policy_digest(tmp_path)
    assert first == canonical_sha256(
        {"observable_policies": {"terrain-v1": {"minimum_valid_fraction": 0.8}}, "gate_registry": registry}
    )
    path.write_text("observable_policies:\n  terrain-v1:\n    minimum_valid_fraction: 0.9\n")
    assert assurance_policy_digest(tmp_path) != first
    path.write_text("observable_policies: []\n")
    with pytest.raises(ScientificClaimRejected, match="POLICY_CONFIGURATION_INVALID"):
        assurance_policy_digest(tmp_path)
