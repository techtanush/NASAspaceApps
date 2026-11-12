"""Deterministic claim auditing. Scientific measurements stay behind ScienceService.

This module accepts only registered evidence and science adequacy receipts. It never
computes a terrain metric or allows a language-model statement to choose a verdict.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import yaml

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.db.store import PersistenceError, UnitOfWork
from analogforge.ports.assurance_models import Claim, Gate, ScientificAssuranceArtifact
from analogforge.ports.common import RuntimeMode
from analogforge.ports.domain_models import CritiqueIssue, EvidenceRecord, ToolReceipt
from analogforge.ports.hashing import canonical_json_bytes, canonical_sha256
from analogforge.ports.science_payloads import GateEvidence

GATE_IDS = tuple(f"SC-{number:02}" for number in range(1, 16))
PLATFORM_GATES = frozenset({"SC-01", "SC-12", "SC-14", "SC-15"})
INTEGRITY_GATES = frozenset({"SC-01", "SC-02", "SC-09", "SC-14", "SC-15"})


def assurance_policy_digest(config_dir: Path | None = None) -> str:
    """Pin observable policy definitions together with the executable gate registry."""
    import json

    project = Path(__file__).resolve().parents[3]
    registry = json.loads((project / "contracts" / "scientific-gates.json").read_text())
    path = (config_dir or project / "config") / "algorithms.yaml"
    configuration = yaml.safe_load(path.read_text()) if path.is_file() else {}
    if not isinstance(configuration, dict):
        raise ScientificClaimRejected(["SC-01:ALGORITHM_POLICY_CONFIGURATION_INVALID"])
    policies = configuration.get("observable_policies", {})
    if not isinstance(policies, dict):
        raise ScientificClaimRejected(["SC-01:OBSERVABLE_POLICY_CONFIGURATION_INVALID"])
    return canonical_sha256({"observable_policies": policies, "gate_registry": registry})


class ScientificClaimRejected(PersistenceError):
    code = "SCIENTIFIC_CLAIM_REJECTED"

    def __init__(self, issues: Sequence[str]) -> None:
        self.issue_codes = sorted(set(issues))
        super().__init__(self.code, f"{self.code}: {', '.join(self.issue_codes)}")


@dataclass(frozen=True)
class ClaimInput:
    claim_id: str
    claim_type: Literal["QUALIFICATION", "VERIFICATION", "DISCOVERY", "CONTEXT"]
    requirement_id: str | None
    candidate_ids: tuple[UUID, ...]
    scope: str
    evidence_ids: tuple[UUID, ...]
    qualification_status: Literal["PASS", "PARTIAL", "FAIL", "GAP", "UNKNOWN"] | None = None
    verification_status: Literal["PASS", "FAIL", "INCONCLUSIVE"] | None = None
    validation_level: Literal["S0", "S1", "S2", "S3", "S4"] = "S0"
    science_gates: tuple[GateEvidence, ...] = ()
    assumption_evidence_ids: tuple[UUID, ...] = ()
    limitations: tuple[str, ...] = ()
    nominal_model: bool = False
    current_row_matches: bool = True
    policy_is_pinned: bool = True


@dataclass(frozen=True)
class AuditSnapshot:
    workspace_id: UUID
    run_id: UUID
    mode: RuntimeMode
    mission_content_sha256: str
    rover_content_sha256: str | None
    dataset_policy_sha256: str
    acquired_manifest_sha256: str
    algorithm_lock_sha256: str
    assurance_policy_sha256: str
    snapshot_content: Mapping[str, Any]
    evidence: Mapping[UUID, EvidenceRecord]
    critiques: tuple[CritiqueIssue, ...] = ()
    frozen_inputs_match: bool = True
    snapshot_is_current: bool = True
    # Populated only by executed decoder/comparison/verifier receipts, never a role.
    validation_receipts: Mapping[str, tuple[UUID, ...]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _gate(gate_id: str, valid: bool, reason: str, ids: Sequence[UUID] = ()) -> Gate:
    return Gate(gate_id=gate_id, outcome="SATISFIED" if valid else "UNSATISFIED", reason=reason, evidence_ids=list(ids))


def _statement(proposal: ClaimInput, disposition: str) -> str:
    subject = proposal.requirement_id or proposal.claim_id
    scope = proposal.scope
    if disposition == "REJECTED":
        return f"No publishable conclusion for {subject}: claim integrity checks failed."
    if proposal.qualification_status == "GAP":
        return f"{subject} is a physical gap in natural Earth analog selection ({scope})."
    if proposal.qualification_status == "UNKNOWN" or proposal.verification_status == "INCONCLUSIVE":
        return f"No supported decision for {subject}; evidence or search is incomplete ({scope})."
    if proposal.claim_type == "DISCOVERY":
        return f"Candidate identified within the declared search and reference-list scope ({scope})."
    result = proposal.verification_status or proposal.qualification_status or "context recorded"
    prefix = "Under the accepted nominal model" if disposition == "LIMITED" else "Under the accepted assumptions"
    return f"{prefix}, {subject} has outcome {result} within {scope}."


def _mode_and_level(snapshot: AuditSnapshot, proposal: ClaimInput) -> tuple[bool, str]:
    records = [
        snapshot.evidence[eid]
        for eid in proposal.evidence_ids + proposal.assumption_evidence_ids
        if eid in snapshot.evidence
    ]
    if any(
        e.mode != snapshot.mode or e.workspace_id != snapshot.workspace_id or e.run_id != snapshot.run_id
        for e in records
    ):
        return False, "Evidence is from a different mode, workspace or run."
    if snapshot.mode == "synthetic" and proposal.validation_level not in {"S0", "S1"}:
        return False, "Synthetic evidence cannot establish real-source S2, S3 or S4."
    required = {"S2": "decoded_source", "S3": "common_scale_comparison", "S4": "independent_verification"}
    receipt_kind = required.get(proposal.validation_level)
    if receipt_kind is not None:
        confirmed = snapshot.validation_receipts.get(receipt_kind, ())
        if not confirmed or not all(eid in snapshot.evidence for eid in confirmed):
            return False, f"No executed {receipt_kind} evidence supports {proposal.validation_level}."
        expected = {
            "decoded_source": ({"SOURCE"}, {"ingest-local-dataset", "fetch-source", "decode-source"}),
            "common_scale_comparison": ({"COMPARISON"}, {"compare-requirement"}),
            "independent_verification": ({"VERIFICATION"}, {"verify-route"}),
        }
        kinds, algorithms = expected[receipt_kind]
        for evidence_id in confirmed:
            record = snapshot.evidence[evidence_id]
            if (
                record.kind not in kinds
                or record.algorithm_id not in algorithms
                or record.workspace_id != snapshot.workspace_id
                or record.run_id != snapshot.run_id
                or record.mode != snapshot.mode
                or (record.dataset_product_id or "").startswith("SYNTHETIC_")
            ):
                return False, f"The registered evidence is not an executed real-source {receipt_kind} receipt."
    if snapshot.mode == "live" and any((e.dataset_product_id or "").startswith("SYNTHETIC_") for e in records):
        return False, "Synthetic product identity is forbidden in live scientific claims."
    return True, "Immutable runtime mode and executed validation level agree."


def _claim_limitations(proposal: ClaimInput, disposition: str, gates: Mapping[str, Gate]) -> list[str]:
    """Limitations for a compiled claim; never empty for a non-supported disposition (assurance schema).

    The proposal's own limitations come first; if a LIMITED/UNSUPPORTED/UNKNOWN/GAP/REJECTED claim states none, the
    reasons of its unmet gates are recorded instead of publishing an unexplained restriction.
    """
    limitations = list(dict.fromkeys(text for text in proposal.limitations if text.strip()))
    if limitations or disposition == "SUPPORTED":
        return limitations
    unmet = [f"{g.gate_id}: {g.reason}" for g in gates.values() if g.outcome in {"UNSATISFIED", "NOT_ASSESSED"}]
    status = proposal.qualification_status or proposal.verification_status or "no status"
    fallback = f"{proposal.claim_type.lower()} claim is {disposition.lower()} ({status}) under the accepted scope"
    return unmet or [fallback]


def audit(
    snapshot: AuditSnapshot, claims: Sequence[ClaimInput], receipts: Sequence[ToolReceipt]
) -> ScientificAssuranceArtifact:
    """Audit every included claim against one immutable registered snapshot.

    Missing scientific gates are explicit NOT_ASSESSED, never filled with success.
    A supported negative is publishable; a contradictory positive is rejected.
    """
    if not claims:
        raise ScientificClaimRejected(["CLAIM_SET_EMPTY"])
    if len({c.claim_id for c in claims}) != len(claims):
        raise ScientificClaimRejected(["CLAIM_ID_DUPLICATE"])
    successful = {
        eid
        for receipt in receipts
        if receipt.status == "SUCCEEDED"
        and receipt.workspace_id == snapshot.workspace_id
        and receipt.run_id == snapshot.run_id
        and receipt.mode == snapshot.mode
        for eid in receipt.evidence_ids
    }
    compiled: list[Claim] = []
    blocking: list[str] = []
    for proposal in claims:
        positive = proposal.qualification_status in {"PASS", "PARTIAL"} or proposal.verification_status == "PASS"
        supplied: dict[str, GateEvidence] = {g.gate_id: g for g in proposal.science_gates}
        duplicate = len(supplied) != len(proposal.science_gates)
        gates: dict[str, Gate] = {}
        for gate_id in GATE_IDS:
            scientific = supplied.get(gate_id)
            if scientific is None:
                gates[gate_id] = Gate(
                    gate_id=gate_id,
                    outcome="NOT_ASSESSED",
                    reason="No registered scientific adequacy receipt for this gate.",
                    evidence_ids=[],
                )
            else:
                ids = [r.evidence_id for r in scientific.evidence if r.evidence_id is not None]
                unresolved = any(r.local_key is not None for r in scientific.evidence)
                unauthorized = any(
                    eid not in snapshot.evidence
                    or snapshot.evidence[eid].workspace_id != snapshot.workspace_id
                    or snapshot.evidence[eid].run_id != snapshot.run_id
                    or snapshot.evidence[eid].mode != snapshot.mode
                    for eid in ids
                )
                gates[gate_id] = Gate(
                    gate_id=scientific.gate_id,
                    outcome="UNSATISFIED" if unresolved or unauthorized else scientific.outcome,
                    reason="Unregistered scientific gate reference."
                    if unresolved or unauthorized
                    else scientific.reason,
                    evidence_ids=ids,
                )
        # Always-applicable gates cannot be waived by a provider's N/A label.
        required_scientific = {"SC-07"}
        if positive:
            required_scientific |= {"SC-02", "SC-09"}
        if proposal.claim_type == "VERIFICATION" and positive:
            required_scientific.add("SC-11")
        if proposal.claim_type == "DISCOVERY":
            required_scientific.add("SC-13")
        for gate_id in required_scientific:
            if gates[gate_id].outcome == "NOT_APPLICABLE":
                gates[gate_id] = _gate(gate_id, False, "Required applicable gate cannot be marked NOT_APPLICABLE.")
        frozen = snapshot.frozen_inputs_match and snapshot.snapshot_is_current and proposal.policy_is_pinned
        gates["SC-01"] = _gate(
            "SC-01",
            frozen,
            "Accepted inputs and pinned policies match current snapshot."
            if frozen
            else "Stale snapshot, changed accepted input or missing policy lock.",
        )
        references = proposal.evidence_ids + proposal.assumption_evidence_ids
        source_valid = all(eid in snapshot.evidence for eid in references)
        data_dependent = (
            proposal.qualification_status in {"PASS", "PARTIAL", "FAIL"}
            or proposal.verification_status in {"PASS", "FAIL"}
            or proposal.claim_type == "DISCOVERY"
        )
        if data_dependent and not proposal.evidence_ids:
            gates["SC-02"] = _gate(
                "SC-02", False, "A measured positive or negative finding requires registered evidence."
            )
        if references and not source_valid:
            gates["SC-02"] = _gate("SC-02", False, "Claim references absent or unauthorized evidence.")
        if references and any(eid not in successful for eid in proposal.evidence_ids):
            gates["SC-02"] = _gate("SC-02", False, "Claim evidence has no successful registered tool receipt.")
        for eid in proposal.assumption_evidence_ids:
            if eid in snapshot.evidence and snapshot.evidence[eid].kind != "ASSUMPTION":
                gates["SC-07"] = _gate("SC-07", False, "Assumption reference is not an ASSUMPTION record.")
        challenges = [
            c
            for c in snapshot.critiques
            if c.severity == "BLOCKING"
            and c.status == "OPEN"
            and (c.requirement_id is None or c.requirement_id == proposal.requirement_id)
            and (c.candidate_id is None or c.candidate_id in proposal.candidate_ids)
        ]
        broken_resolution = any(
            c.status == "RESOLVED"
            and (
                not c.resolution_evidence_ids or any(eid not in snapshot.evidence for eid in c.resolution_evidence_ids)
            )
            for c in snapshot.critiques
        )
        gates["SC-12"] = _gate(
            "SC-12",
            (not challenges or not positive) and not broken_resolution,
            "No unresolved material challenge supports a positive claim."
            if not challenges
            else "Material challenge restricts dependent claims.",
        )
        valid_mode, reason = _mode_and_level(snapshot, proposal)
        gates["SC-14"] = _gate("SC-14", valid_mode, reason, proposal.evidence_ids)
        consistent = proposal.current_row_matches and not duplicate
        gates["SC-15"] = _gate(
            "SC-15",
            consistent,
            "Audited status, complete history and authoritative row agree."
            if consistent
            else "Proposal contradicts the authoritative row or repeats a gate.",
        )
        invalid_integrity = [
            g.gate_id for g in gates.values() if g.gate_id in INTEGRITY_GATES and g.outcome == "UNSATISFIED"
        ]
        unearned_positive = positive and (
            not proposal.evidence_ids or any(g.outcome in {"UNSATISFIED", "NOT_ASSESSED"} for g in gates.values())
        )
        invalid_verifier = proposal.claim_type == "VERIFICATION" and positive and gates["SC-11"].outcome != "SATISFIED"
        if invalid_integrity or unearned_positive or invalid_verifier or broken_resolution:
            disposition = "REJECTED"
            blocking.extend(f"{proposal.claim_id}:{gate_id}" for gate_id in invalid_integrity)
            if unearned_positive or invalid_verifier:
                blocking.append(f"{proposal.claim_id}:POSITIVE_CLAIM_UNSUPPORTED")
        elif proposal.qualification_status == "UNKNOWN" or proposal.verification_status == "INCONCLUSIVE":
            disposition = "UNKNOWN"
        elif proposal.qualification_status == "GAP":
            disposition = "GAP"
        elif proposal.qualification_status == "PARTIAL" or proposal.nominal_model:
            disposition = "LIMITED"
        elif any(g.outcome in {"UNSATISFIED", "NOT_ASSESSED"} for g in gates.values()):
            disposition = "UNSUPPORTED"
        else:
            disposition = "SUPPORTED"
        compiled.append(
            Claim(
                claim_id=proposal.claim_id,
                claim_type=proposal.claim_type,
                requirement_id=proposal.requirement_id,
                candidate_ids=list(proposal.candidate_ids),
                scope=proposal.scope,
                disposition=cast(Any, disposition),
                qualification_status=proposal.qualification_status,
                verification_status=proposal.verification_status,
                validation_level=proposal.validation_level,
                evidence_ids=list(proposal.evidence_ids),
                assumption_evidence_ids=list(proposal.assumption_evidence_ids),
                gates=[gates[gate_id] for gate_id in GATE_IDS],
                permitted_statement=_statement(proposal, disposition),
                limitations=_claim_limitations(proposal, disposition, gates),
            )
        )
    rejected = any(c.disposition == "REJECTED" for c in compiled)
    publication = (
        "BLOCKED"
        if rejected or blocking
        else (
            "LIMITED"
            if any(c.disposition in {"LIMITED", "UNKNOWN", "GAP", "UNSUPPORTED"} for c in compiled)
            else "ALLOWED"
        )
    )
    return ScientificAssuranceArtifact(
        schema_version="1.0",
        audit_id=uuid4(),
        workspace_id=snapshot.workspace_id,
        run_id=snapshot.run_id,
        mode=snapshot.mode,
        created_at=snapshot.created_at,
        snapshot_sha256=canonical_sha256(dict(snapshot.snapshot_content)),
        mission_content_sha256=snapshot.mission_content_sha256,
        rover_content_sha256=snapshot.rover_content_sha256,
        dataset_policy_sha256=snapshot.dataset_policy_sha256,
        acquired_manifest_sha256=snapshot.acquired_manifest_sha256,
        algorithm_lock_sha256=snapshot.algorithm_lock_sha256,
        assurance_policy_sha256=snapshot.assurance_policy_sha256,
        critique_evidence_ids=sorted({eid for c in snapshot.critiques for eid in c.target_evidence_ids}, key=str),
        claims=compiled,
        publication=publication,
        blocking_issue_codes=sorted(set(blocking)),
        limitations=sorted({text for c in compiled for text in c.limitations}),
    )


def compile_conclusions(
    report: ScientificAssuranceArtifact, *, route_rows_final_pass: bool = False
) -> dict[str, list[str]]:
    """Only audited text can enter the published summary; no role-written summary."""
    if report.publication == "BLOCKED":
        raise ScientificClaimRejected(report.blocking_issue_codes or ["ASSURANCE_BLOCKED"])
    result: dict[str, list[str]] = {"qualified_uses": [], "partial_uses": [], "unsupported_uses": [], "unknowns": []}
    for claim in report.claims:
        if claim.disposition in {"UNKNOWN", "GAP"}:
            result["unknowns"].append(claim.permitted_statement)
        elif (
            claim.qualification_status == "FAIL"
            or claim.verification_status == "FAIL"
            or claim.disposition == "UNSUPPORTED"
        ):
            result["unsupported_uses"].append(claim.permitted_statement)
        elif (
            claim.claim_type == "VERIFICATION"
            and claim.disposition == "SUPPORTED"
            and claim.verification_status == "PASS"
            and route_rows_final_pass
        ):
            result["qualified_uses"].append(claim.permitted_statement)
        else:
            result["partial_uses"].append(claim.permitted_statement)
    return result


def audit_registered_claim(
    unit: UnitOfWork,
    run: Mapping[str, Any],
    mission: Mapping[str, Any],
    rover: Mapping[str, Any] | None,
    record: dict[str, Any],
    payload: Mapping[str, Any],
    blob_store: ContentAddressedStore,
    *,
    config_dir: Path | None = None,
) -> ScientificAssuranceArtifact:
    """Audit one comparison inside its registrar's fenced publication transaction.

    The comparison's receipt and evidence already exist in this transaction, while its
    public qualification row does not. An invalid positive rolls the whole transaction
    back. The final passport still performs a separate whole-snapshot audit.
    """
    authoritative = unit.require("runs", run["id"])
    runtime = authoritative.get("runtime", {})
    evidence = {
        UUID(raw["id"]): EvidenceRecord.model_validate(
            {key: value for key, value in raw.items() if key in EvidenceRecord.model_fields}
        )
        for raw in unit.list("evidence", {"run_id": run["id"]})
    }
    receipts = [
        ToolReceipt.model_validate({key: value for key, value in raw.items() if key in ToolReceipt.model_fields})
        for raw in unit.list("tool_receipts", {"run_id": run["id"]})
    ]
    policy_hash = assurance_policy_digest(config_dir)
    if runtime.get("assurance_policy_sha256", policy_hash) != policy_hash:
        raise ScientificClaimRejected(["SC-01:ASSURANCE_POLICY_CHANGED"])
    locks = ("dataset_policy_sha256", "acquired_manifest_sha256", "algorithm_lock_sha256")
    if any(not runtime.get(key) for key in locks):
        raise ScientificClaimRejected(["SC-01:SOURCE_OR_ALGORITHM_LOCK_MISSING"])
    scope = next(
        requirement["evidence_scope"]
        for requirement in mission["requirements"]
        if requirement["id"] == record["requirement_id"]
    )
    snapshot = AuditSnapshot(
        workspace_id=UUID(run["workspace_id"]),
        run_id=UUID(run["id"]),
        mode=cast(Any, run["mode"]),
        mission_content_sha256=mission["content_sha256"],
        rover_content_sha256=rover["content_sha256"] if rover else None,
        dataset_policy_sha256=runtime["dataset_policy_sha256"],
        acquired_manifest_sha256=runtime["acquired_manifest_sha256"],
        algorithm_lock_sha256=runtime["algorithm_lock_sha256"],
        assurance_policy_sha256=runtime.get("assurance_policy_sha256", policy_hash),
        snapshot_content={"run_id": run["id"], "revision": authoritative["revision"], "qualification": record},
        evidence=evidence,
        frozen_inputs_match=runtime.get("mission_content_sha256") == mission["content_sha256"]
        and runtime.get("rover_content_sha256") == (rover["content_sha256"] if rover else None),
        validation_receipts={
            key: tuple(UUID(value) for value in values)
            for key, values in runtime.get("validation_receipts", {}).items()
        },
    )
    claim = ClaimInput(
        claim_id=f"q:{record['id']}",
        claim_type="QUALIFICATION",
        requirement_id=record["requirement_id"],
        candidate_ids=(UUID(record["candidate_id"]),),
        scope=scope,
        evidence_ids=tuple(UUID(value) for value in record["evidence_ids"]),
        qualification_status=record["status"],
        validation_level=payload["adequacy"]["validation_level"],
        science_gates=tuple(GateEvidence.model_validate(gate) for gate in payload["adequacy"]["gates"]),
        limitations=tuple(record["limitations"]),
        nominal_model=scope == "terrain_model" and record["status"] in {"PASS", "PARTIAL"},
        current_row_matches=record["status"] == payload["proposed_status"],
    )
    report = audit(snapshot, [claim], receipts)
    if report.publication == "BLOCKED":
        raise ScientificClaimRejected(report.blocking_issue_codes or ["ASSURANCE_BLOCKED"])
    blob = blob_store.put_bytes(canonical_json_bytes(report), "application/json")
    if not unit.list("artifacts", {"sha256": blob.sha256}):
        unit.create(
            "artifacts",
            {
                "sha256": blob.sha256,
                "bytes": blob.size_bytes,
                "media_type": blob.media_type,
                "relative_path": blob.relative_path,
            },
        )
    evidence_id = uuid4()
    assurance = EvidenceRecord(
        schema_version="1.0",
        id=evidence_id,
        workspace_id=snapshot.workspace_id,
        run_id=snapshot.run_id,
        mode=snapshot.mode,
        created_at=report.created_at,
        kind="DERIVED",
        artifact_sha256=blob.sha256,
        artifact_media_type="application/json",
        source_uri=None,
        dataset_product_id=None,
        dataset_version=None,
        granule_id=None,
        license_note="AnalogForge pre-publication scientific claim audit",
        body=cast(Any, mission["target"]["body"]),
        aoi=None,
        input_evidence_ids=list(claim.evidence_ids),
        parameters_sha256=report.snapshot_sha256,
        algorithm_id="scientific-assurance",
        algorithm_version="1.0",
        native_resolution_m=None,
        comparison_scale_m=None,
        metrics=[],
        limitations=report.limitations,
    )
    unit.create("evidence", assurance)
    invocation_id = next(
        receipt.invocation_id
        for receipt in reversed(receipts)
        if receipt.status == "SUCCEEDED" and set(claim.evidence_ids).intersection(receipt.evidence_ids)
    )
    receipt = ToolReceipt(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=snapshot.workspace_id,
        run_id=snapshot.run_id,
        mode=snapshot.mode,
        created_at=report.created_at,
        invocation_id=invocation_id,
        tool_name="review_evidence_bundle",
        tool_version="1.0",
        input_sha256=report.snapshot_sha256,
        output_sha256=blob.sha256,
        evidence_ids=[evidence_id],
        status="SUCCEEDED",
        error_code=None,
        elapsed_ms=0,
        cache_hit=False,
    )
    unit.create(
        "tool_receipts", {**receipt.model_dump(mode="json"), "tool_call_id": "assurance-" + str(report.audit_id)}
    )
    for parent in claim.evidence_ids:
        unit.create(
            "evidence_edges",
            {
                "run_id": run["id"],
                "mode": run["mode"],
                "parent_evidence_id": str(parent),
                "child_evidence_id": str(evidence_id),
                "relation": "DERIVED_FROM",
            },
        )
    record["audit_evidence_id"] = str(evidence_id)
    return report
