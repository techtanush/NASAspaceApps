"""Immutable assurance → manifest → passport assembly, without hash cycles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import BaseModel

from analogforge.adapters.storage.cas import Blob, ContentAddressedStore
from analogforge.application.assurance import (
    AuditSnapshot,
    ClaimInput,
    ScientificClaimRejected,
    assurance_policy_digest,
    audit,
    compile_conclusions,
)
from analogforge.application.missions import accepted_contract
from analogforge.db.store import Store, UnitOfWork
from analogforge.ports.assurance_models import ScientificAssuranceArtifact
from analogforge.ports.domain_models import (
    AnalogPassport,
    CompositePortfolio,
    CritiqueIssue,
    EarthAnalogCandidate,
    EvidenceRecord,
    MissionTestContract,
    PlanetaryTargetProfile,
    QualificationDimension,
    RoverProfile,
    TestResult,
    ToolReceipt,
    VerificationTest,
)
from analogforge.ports.hashing import (
    MISSION_CONTENT_EXCLUDE,
    ROVER_CONTENT_EXCLUDE,
    bytes_sha256,
    canonical_json_bytes,
    canonical_sha256,
    model_sha256,
)
from analogforge.ports.passport_renderer import (
    AttemptRecord,
    CompatibilityBlock,
    PassportExportBundle,
    PassportRenderer,
    SourceLocks,
)
from analogforge.ports.science_payloads import GateEvidence


def public_model[ModelT: BaseModel](model: type[ModelT], document: Mapping[str, Any]) -> ModelT:
    """Internal bookkeeping is never leaked into a strict frozen wire model."""
    return model.model_validate({key: value for key, value in document.items() if key in model.model_fields})


@dataclass(frozen=True)
class PassportSnapshot:
    audit: ScientificAssuranceArtifact
    assurance_evidence: EvidenceRecord
    mission: MissionTestContract
    rover: RoverProfile | None
    candidates: tuple[EarthAnalogCandidate, ...]
    qualifications: tuple[QualificationDimension, ...]
    source_locks: SourceLocks
    target_profile: PlanetaryTargetProfile | None = None
    attempts: tuple[AttemptRecord, ...] = ()
    compatibility: tuple[CompatibilityBlock, ...] = ()
    critiques: tuple[CritiqueIssue, ...] = ()
    portfolio: CompositePortfolio | None = None
    evidence: tuple[EvidenceRecord, ...] = ()
    search_limitations: tuple[str, ...] = ()
    not_run_reason: str | None = None
    replay_source_run_id: UUID | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    passport_id: UUID = field(default_factory=uuid4)
    # Public QualificationDimension omits stage; preserve its authoritative context.
    final_route_requirement_ids: frozenset[str] = frozenset()


def _validate_snapshot(snapshot: PassportSnapshot) -> None:
    report, mission = snapshot.audit, snapshot.mission
    if report.publication == "BLOCKED":
        raise ScientificClaimRejected(report.blocking_issue_codes or ["ASSURANCE_BLOCKED"])
    if mission.accepted_at is None or model_sha256(mission, MISSION_CONTENT_EXCLUDE) != mission.content_sha256:
        raise ScientificClaimRejected(["SC-01:MISSION_HASH_MISMATCH"])
    if report.mission_content_sha256 != mission.content_sha256:
        raise ScientificClaimRejected(["SC-01:MISSION_AUDIT_MISMATCH"])
    if snapshot.rover is not None:
        if model_sha256(snapshot.rover, ROVER_CONTENT_EXCLUDE) != snapshot.rover.content_sha256:
            raise ScientificClaimRejected(["SC-01:ROVER_HASH_MISMATCH"])
        if report.rover_content_sha256 != snapshot.rover.content_sha256:
            raise ScientificClaimRejected(["SC-01:ROVER_AUDIT_MISMATCH"])
    elif report.rover_content_sha256 is not None or snapshot.attempts:
        raise ScientificClaimRejected(["SC-01:SITE_ONLY_ROVER_INVENTED"])
    assurance = snapshot.assurance_evidence
    if (assurance.kind, assurance.algorithm_id, assurance.algorithm_version) != (
        "DERIVED",
        "scientific-assurance",
        "1.0",
    ):
        raise ScientificClaimRejected(["SC-02:ASSURANCE_REFERENCE_INVALID"])
    if assurance.artifact_sha256 != canonical_sha256(report):
        raise ScientificClaimRejected(["SC-02:ASSURANCE_BYTES_MISMATCH"])
    if report.workspace_id != mission.workspace_id:
        raise ScientificClaimRejected(["SC-02:WORKSPACE_MISMATCH"])
    additional: list[Any] = []
    if snapshot.target_profile is not None:
        additional.append(snapshot.target_profile)
    if snapshot.portfolio is not None:
        additional.append(snapshot.portfolio)
    for attempt in snapshot.attempts:
        additional.extend([attempt.test, attempt.result])
    records: Sequence[Any] = (
        assurance,
        *snapshot.candidates,
        *snapshot.qualifications,
        *snapshot.evidence,
        *additional,
    )
    for record in records:
        if record.workspace_id != report.workspace_id or record.run_id != report.run_id or record.mode != report.mode:
            raise ScientificClaimRejected(["SC-14:RECORD_SCOPE_MISMATCH"])
    evidence = {e.id: e for e in (*snapshot.evidence, assurance)}
    candidate_ids = {candidate.id for candidate in snapshot.candidates}
    for claim in report.claims:
        if any(candidate_id not in candidate_ids for candidate_id in claim.candidate_ids):
            raise ScientificClaimRejected(["SC-15:CLAIM_CANDIDATE_MISMATCH"])
        if any(eid not in evidence for eid in (*claim.evidence_ids, *claim.assumption_evidence_ids)):
            raise ScientificClaimRejected(["SC-02:DANGLING_CLAIM_EVIDENCE"])
    for record in evidence.values():
        if (
            any(parent not in evidence for parent in record.input_evidence_ids)
            or record.id in record.input_evidence_ids
        ):
            raise ScientificClaimRejected(["SC-02:DANGLING_OR_SELF_LINEAGE"])
    visited: set[UUID] = set()
    active: set[UUID] = set()

    def visit(evidence_id: UUID) -> None:
        if evidence_id in active:
            raise ScientificClaimRejected(["SC-02:EVIDENCE_CYCLE"])
        if evidence_id in visited:
            return
        active.add(evidence_id)
        for parent in evidence[evidence_id].input_evidence_ids:
            visit(parent)
        active.remove(evidence_id)
        visited.add(evidence_id)

    for evidence_id in evidence:
        visit(evidence_id)
    required_pairs = {(candidate.id, req.id) for candidate in snapshot.candidates for req in mission.requirements}
    actual_pairs = {(row.candidate_id, row.requirement_id) for row in snapshot.qualifications}
    if required_pairs != actual_pairs:
        raise ScientificClaimRejected(["SC-15:REQUIREMENT_MATRIX_INCOMPLETE"])
    if len(snapshot.qualifications) != len(actual_pairs):
        raise ScientificClaimRejected(["SC-15:DUPLICATE_CURRENT_QUALIFICATION"])
    for row in snapshot.qualifications:
        matching = [
            claim
            for claim in report.claims
            if claim.claim_type == "QUALIFICATION"
            and claim.requirement_id == row.requirement_id
            and row.candidate_id in claim.candidate_ids
        ]
        if len(matching) != 1 or matching[0].qualification_status != row.status:
            raise ScientificClaimRejected(["SC-15:AUDIT_QUALIFICATION_MISMATCH"])
        if any(eid not in evidence for eid in row.evidence_ids):
            raise ScientificClaimRejected(["SC-02:QUALIFICATION_EVIDENCE_MISSING"])
    for candidate in snapshot.candidates:
        if any(eid not in evidence for eid in candidate.evidence_ids):
            raise ScientificClaimRejected(["SC-02:CANDIDATE_EVIDENCE_MISSING"])
    if [attempt.attempt_number for attempt in snapshot.attempts] != list(range(1, len(snapshot.attempts) + 1)):
        raise ScientificClaimRejected(["SC-15:ATTEMPT_HISTORY_INCOMPLETE"])
    for attempt in snapshot.attempts:
        if (
            attempt.test.mission_revision_id != mission.id
            or snapshot.rover is None
            or attempt.test.rover_revision_id != snapshot.rover.id
        ):
            raise ScientificClaimRejected(["SC-01:ATTEMPT_INPUT_MISMATCH"])
        if attempt.result.test_id != attempt.test.id:
            raise ScientificClaimRejected(["SC-15:ATTEMPT_RESULT_MISMATCH"])
        matching = [claim for claim in report.claims if claim.claim_id == f"v:{attempt.test.id}"]
        if len(matching) != 1 or matching[0].verification_status != attempt.result.outcome:
            raise ScientificClaimRejected(["SC-15:AUDIT_VERIFICATION_MISMATCH"])
    locks = snapshot.source_locks
    for key in ("dataset_policy_sha256", "acquired_manifest_sha256", "algorithm_lock_sha256"):
        if getattr(report, key) != getattr(locks, key):
            raise ScientificClaimRejected([f"SC-01:{key.upper()}_MISMATCH"])


def assemble_bundle(snapshot: PassportSnapshot) -> PassportExportBundle:
    _validate_snapshot(snapshot)
    report = snapshot.audit
    latest_pass = snapshot.attempts[-1] if snapshot.attempts else None
    route_ids = {
        r.id
        for r in snapshot.mission.requirements
        if r.mandatory
        and r.observable in {"unique_slope_exposure_m", "completed_task_count", "final_battery_reserve_pct"}
    }
    selected_rows = [r for r in snapshot.qualifications if latest_pass and r.candidate_id == latest_pass.candidate_id]
    rows_final_pass = (
        latest_pass is not None
        and latest_pass.result.outcome == "PASS"
        and route_ids.issubset(snapshot.final_route_requirement_ids)
        and all(
            any(row.requirement_id == req_id and row.status == "PASS" for row in selected_rows) for req_id in route_ids
        )
    )
    conclusions = compile_conclusions(report, route_rows_final_pass=rows_final_pass)
    if (
        rows_final_pass
        and latest_pass is not None
        and any(
            claim.claim_type == "VERIFICATION"
            and claim.disposition == "SUPPORTED"
            and claim.verification_status == "PASS"
            and latest_pass.candidate_id in claim.candidate_ids
            for claim in report.claims
        )
    ):
        labels = [requirement.label for requirement in snapshot.mission.requirements if requirement.id in route_ids]
        conclusions["qualified_uses"] = [
            "modeled terrain-feasibility test of "
            + ", ".join(labels)
            + " on "
            + latest_pass.candidate_name
            + " under the accepted assumptions"
        ]
    evidence = sorted(
        {e.id: e for e in (*snapshot.evidence, snapshot.assurance_evidence)}.values(), key=lambda e: str(e.id)
    )
    not_run = snapshot.not_run_reason or (
        "No rover supplied — site qualification only"
        if snapshot.rover is None
        else ("No modeled experiment executed" if not snapshot.attempts else None)
    )
    # The manifest excludes itself, passport's manifest field and rendition bytes.
    manifest = {
        "schema_version": "1.0",
        "identity": {
            "passport_id": str(snapshot.passport_id),
            "run_id": str(report.run_id),
            "workspace_id": str(report.workspace_id),
            "mode": report.mode,
            "generated_at": snapshot.generated_at.isoformat(),
        },
        "accepted_inputs": {
            "mission": snapshot.mission.model_dump(mode="json"),
            "rover": snapshot.rover.model_dump(mode="json") if snapshot.rover else None,
        },
        "sources": snapshot.source_locks.model_dump(mode="json"),
        "derived_artifacts": [e.model_dump(mode="json") for e in evidence],
        "decisions": {
            "qualifications": [r.model_dump(mode="json") for r in snapshot.qualifications],
            "critiques": [c.model_dump(mode="json") for c in snapshot.critiques],
            "conclusions": conclusions,
            "assurance_evidence_id": str(snapshot.assurance_evidence.id),
            "assurance_sha256": canonical_sha256(report),
        },
        "tests": [a.model_dump(mode="json") for a in snapshot.attempts],
        "portfolio": snapshot.portfolio.model_dump(mode="json") if snapshot.portfolio else None,
        "limitations": sorted(set(report.limitations) | set(snapshot.search_limitations)),
        "not_run_reason": not_run,
        "runtime": {
            "validation_levels": sorted({c.validation_level for c in report.claims}),
            "replay_source_run_id": str(snapshot.replay_source_run_id) if snapshot.replay_source_run_id else None,
        },
    }
    canonical = canonical_json_bytes(manifest)
    digest = bytes_sha256(canonical)
    passport = AnalogPassport(
        schema_version="1.0",
        id=snapshot.passport_id,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        mode=report.mode,
        created_at=snapshot.generated_at,
        mission_revision_id=snapshot.mission.id,
        rover_revision_id=snapshot.rover.id if snapshot.rover else None,
        candidate_ids=[c.id for c in snapshot.candidates],
        portfolio_id=snapshot.portfolio.id if snapshot.portfolio else None,
        qualification_ids=[q.id for q in snapshot.qualifications],
        test_result_ids=[a.result.id for a in snapshot.attempts],
        evidence_ids=[e.id for e in evidence],
        manifest_sha256=digest,
        limitations=manifest["limitations"],
        next_steps=["Acquire specific evidence for unresolved requirements before a physical campaign."],
        assurance_evidence_id=snapshot.assurance_evidence.id,
        **conclusions,
    )
    return PassportExportBundle(
        is_draft=False,
        generated_at=snapshot.generated_at.isoformat(),
        mode=report.mode,
        replay_source_run_id=snapshot.replay_source_run_id,
        passport=passport,
        manifest_sha256=digest,
        canonical_manifest_json=canonical.decode(),
        mission=snapshot.mission,
        rover=snapshot.rover,
        target_profile=snapshot.target_profile,
        candidates=list(snapshot.candidates),
        qualifications=list(snapshot.qualifications),
        compatibility=list(snapshot.compatibility),
        critiques=list(snapshot.critiques),
        attempts=list(snapshot.attempts),
        portfolio=snapshot.portfolio,
        evidence_appendix=evidence,
        assurance=report,
        source_locks=snapshot.source_locks,
        search_limitations=list(snapshot.search_limitations),
        not_run_reason=not_run,
    )


def register_blob(unit: UnitOfWork, blob: Blob) -> None:
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


def _science_gates(raw: Mapping[str, Any], audit_payload: Mapping[str, Any], claim_id: str) -> tuple[GateEvidence, ...]:
    # A final audit supplies claim-specific evidence; qualification adequacy is fallback.
    registered = next(
        (row.get("gates", []) for row in audit_payload.get("claim_gates", []) if row.get("claim_id") == claim_id), None
    )
    if registered is None:
        registered = raw.get("payload", {}).get("adequacy", {}).get("gates", [])
    return tuple(GateEvidence.model_validate(gate) for gate in registered)


def _claim_validation_level(run: Mapping[str, Any], claim_id: str, real_level: str) -> Any:
    if run["mode"] == "synthetic":
        return "S1"
    if run["mode"] == "replay":
        # A replay must pin the original executed level. Absence is unassessed S0,
        # never an automatic promotion of synthetic history into real-source S4.
        return run.get("replay_validation_levels", {}).get(claim_id, "S0")
    return real_level


def publish_passport(
    store: Store,
    workspace_id: str | UUID,
    run_id: str | UUID,
    blob_store: ContentAddressedStore,
    renderer: PassportRenderer | None = None,
    *,
    job_id: str | UUID | None = None,
    lease_token: str | UUID | None = None,
    config_dir: Path | None = None,
) -> PassportExportBundle:
    """Freeze and publish under revision/lease fencing; renderer runs in a separate job.

    Passing a renderer never performs rendering inside this transaction. It only allows
    the caller to retain the same explicit seam when enqueueing export work.
    """
    del renderer
    with store.transaction(workspace_id) as unit:
        run = unit.require("runs", run_id)
        # The scheduler keeps operational bookkeeping under runtime; wire fields remain
        # the frozen RunSnapshot. Both layouts are accepted during the initial build.
        run = {**run, **run.get("runtime", {})}
        if run.get("passport_id"):
            saved = unit.require("passports", run["passport_id"])
            return PassportExportBundle.model_validate(saved["bundle"])
        revision = run["revision"]
        mission = public_model(MissionTestContract, accepted_contract(unit, run["mission_revision_id"]))
        rover = (
            public_model(RoverProfile, unit.require("rover_revisions", run["rover_revision_id"]))
            if run.get("rover_revision_id")
            else None
        )
        candidates = [
            public_model(EarthAnalogCandidate, raw) for raw in unit.list("candidates", {"run_id": str(run_id)})
        ]
        raw_quals = unit.list("qualifications", {"run_id": str(run_id)})
        current: dict[tuple[str, str], dict[str, Any]] = {}
        for raw in raw_quals:
            key = (raw["candidate_id"], raw["requirement_id"])
            if key not in current or raw.get("evaluation_version", 1) >= current[key].get("evaluation_version", 1):
                current[key] = raw
        qualifications = tuple(public_model(QualificationDimension, raw) for raw in current.values())
        evidence = [public_model(EvidenceRecord, raw) for raw in unit.list("evidence", {"run_id": str(run_id)})]
        for record in evidence:
            if record.artifact_sha256 is not None:
                if not unit.list("artifacts", {"sha256": record.artifact_sha256}):
                    raise ScientificClaimRejected(["SC-02:ARTIFACT_AUTHORIZATION_MISSING"])
                blob_store.read(record.artifact_sha256)
        receipts = [public_model(ToolReceipt, raw) for raw in unit.list("tool_receipts", {"run_id": str(run_id)})]
        critiques = tuple(public_model(CritiqueIssue, raw) for raw in unit.list("critiques", {"run_id": str(run_id)}))
        tests = sorted(
            unit.list("tests", {"run_id": str(run_id)}),
            key=lambda row: row.get("attempt_number", row.get("test_revision", 1)),
        )
        results = unit.list("test_results", {"run_id": str(run_id)})
        attempts = []
        for number, raw in enumerate(tests, 1):
            result_raw = next((r for r in results if r["test_id"] == raw["id"]), None)
            if result_raw is None:
                raise ScientificClaimRejected(["SC-15:ATTEMPT_RESULT_MISSING"])
            candidate = next(c for c in candidates if str(c.id) == raw["candidate_id"])
            attempts.append(
                AttemptRecord(
                    attempt_number=number,
                    parent_attempt_number=number - 1 if number > 1 else None,
                    candidate_id=candidate.id,
                    candidate_name=candidate.name,
                    strategy=raw.get("strategy", "WAYPOINT_RETURN"),
                    test=public_model(VerificationTest, raw),
                    result=public_model(TestResult, result_raw),
                    benchmark_rows=result_raw.get("payload", {}).get("benchmark_rows", []),
                    violations=result_raw.get("payload", {}).get("violations", []),
                    diagnosis_category=(raw.get("diagnosis_json") or {}).get("primary_category"),
                    diagnosis_explanation=(raw.get("diagnosis_json") or {}).get("explanation"),
                    changed_elements=raw.get("changed_elements", []),
                )
            )
        target_raw = unit.get("target_profiles", run["target_profile_id"]) if run.get("target_profile_id") else None
        portfolio_raw = (
            unit.get("portfolios", run["selected_portfolio_id"]) if run.get("selected_portfolio_id") else None
        )
        compatibility = [
            CompatibilityBlock(
                candidate_id=raw["candidate_id"],
                rover_revision_id=raw["rover_revision_id"],
                preliminary=raw.get("payload", raw).get("preliminary", True),
                dimensions=raw.get("payload", raw).get("dimensions", []),
            )
            for raw in unit.list("compatibility", {"run_id": str(run_id)})
        ]
    created_at = datetime.now(UTC)
    acquired = canonical_sha256(
        sorted([e.model_dump(mode="json") for e in evidence if e.kind == "SOURCE"], key=lambda e: e["id"])
    )
    policy_sha = assurance_policy_digest(config_dir)
    if run.get("assurance_policy_sha256", policy_sha) != policy_sha:
        raise ScientificClaimRejected(["SC-01:ASSURANCE_POLICY_CHANGED"])
    required_locks = ("dataset_policy_sha256", "algorithm_lock_sha256", "config_sha256")
    if any(not run.get(key) for key in required_locks):
        raise ScientificClaimRejected(["SC-01:SOURCE_OR_ALGORITHM_LOCK_MISSING"])
    locks = SourceLocks(
        dataset_policy_sha256=run["dataset_policy_sha256"],
        acquired_manifest_sha256=run.get("acquired_manifest_sha256", acquired),
        config_sha256=run["config_sha256"],
        algorithm_lock_sha256=run["algorithm_lock_sha256"],
        build_lock_sha256=run.get("build_lock_sha256"),
    )
    frozen_snapshot = {
        "run": {key: value for key, value in run.items() if key not in {"passport_id", "audit_payload"}},
        "qualifications": [q.model_dump(mode="json") for q in qualifications],
        "attempts": [a.model_dump(mode="json") for a in attempts],
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "critiques": [c.model_dump(mode="json") for c in critiques],
    }
    audit_snapshot = AuditSnapshot(
        workspace_id=UUID(str(workspace_id)),
        run_id=UUID(str(run_id)),
        mode=cast(Any, run["mode"]),
        mission_content_sha256=mission.content_sha256,
        rover_content_sha256=rover.content_sha256 if rover else None,
        dataset_policy_sha256=locks.dataset_policy_sha256,
        acquired_manifest_sha256=locks.acquired_manifest_sha256,
        algorithm_lock_sha256=locks.algorithm_lock_sha256,
        assurance_policy_sha256=run.get("assurance_policy_sha256", policy_sha),
        snapshot_content=frozen_snapshot,
        evidence={e.id: e for e in evidence},
        critiques=critiques,
        frozen_inputs_match=(
            run.get("mission_content_sha256", mission.content_sha256) == mission.content_sha256
            and run.get("rover_content_sha256", rover.content_sha256 if rover else None)
            == (rover.content_sha256 if rover else None)
        ),
        validation_receipts={
            key: tuple(UUID(value) for value in values) for key, values in run.get("validation_receipts", {}).items()
        },
        created_at=created_at,
    )
    claims = []
    for row in qualifications:
        raw = current[(str(row.candidate_id), row.requirement_id)]
        payload = raw.get("payload", {})
        requirement = next(r for r in mission.requirements if r.id == row.requirement_id)
        claim_id = f"q:{row.id}"
        claims.append(
            ClaimInput(
                claim_id=claim_id,
                claim_type="QUALIFICATION",
                requirement_id=row.requirement_id,
                candidate_ids=(row.candidate_id,),
                scope=requirement.evidence_scope,
                evidence_ids=tuple(row.evidence_ids),
                qualification_status=row.status,
                validation_level=payload.get("adequacy", {}).get("validation_level", "S0"),
                science_gates=_science_gates(raw, run.get("audit_payload", {}), claim_id),
                # An UNKNOWN/GAP row may carry its reason only in the science explanation; a non-supported claim
                # must state at least one limitation (scientific-assurance schema).
                limitations=tuple(row.limitations) or ((row.explanation,) if row.explanation.strip() else ()),
                nominal_model=row.status in {"PASS", "PARTIAL"} and requirement.evidence_scope == "terrain_model",
            )
        )
    for attempt in attempts:
        claim_id = f"v:{attempt.test.id}"
        claims.append(
            ClaimInput(
                claim_id=claim_id,
                claim_type="VERIFICATION",
                requirement_id=None,
                candidate_ids=(attempt.candidate_id,),
                scope="modeled terrain-feasibility verification",
                evidence_ids=tuple(attempt.result.evidence_ids),
                verification_status=attempt.result.outcome,
                validation_level=_claim_validation_level(run, claim_id, "S4"),
                science_gates=_science_gates({}, run.get("audit_payload", {}), claim_id),
                limitations=tuple(attempt.result.limitations),
                nominal_model=False,
            )
        )
    for candidate in candidates:
        nominated = candidate.origin == "USER_SUPPLIED"
        claim_id = f"{'nomination' if nominated else 'discovery'}:{candidate.id}"
        claims.append(
            ClaimInput(
                claim_id=claim_id,
                claim_type="CONTEXT" if nominated else "DISCOVERY",
                requirement_id=None,
                candidate_ids=(candidate.id,),
                scope="User-nominated region; automatic discovery and reference-list novelty are not claimed"
                if nominated else f"{candidate.discovery_method}; reference status {candidate.novelty_status}",
                evidence_ids=tuple(candidate.evidence_ids),
                validation_level=_claim_validation_level(run, claim_id, "S2"),
                science_gates=_science_gates({}, run.get("audit_payload", {}), claim_id),
                limitations=tuple(candidate.limitations),
            )
        )
    if not claims:
        # Preserve an empty search as explicit unsupported context, with no invented candidate or positive claim.
        for requirement in mission.requirements:
            claim_id = "uncovered:" + requirement.id
            claims.append(ClaimInput(
                claim_id=claim_id, claim_type="CONTEXT", requirement_id=requirement.id, candidate_ids=(),
                scope="source availability; no Earth candidate was qualified", qualification_status="UNKNOWN",
                evidence_ids=tuple(UUID(identifier) for identifier in target_raw["evidence_ids"]) if target_raw else (),
                validation_level="S0",
                science_gates=_science_gates({}, run.get("audit_payload", {}), claim_id),
                limitations=(
                    "NO_COVERAGE: no Earth candidate was available; no qualification or verification occurred.",
                ),
            ))
    from analogforge.application.assurance import restrict_rehearsal_claim

    report = audit(audit_snapshot, [restrict_rehearsal_claim(audit_snapshot, claim) for claim in claims], receipts)
    assurance_blob = blob_store.put_bytes(canonical_json_bytes(report), "application/json")
    assurance_evidence = EvidenceRecord(
        schema_version="1.0",
        id=uuid4(),
        workspace_id=UUID(str(workspace_id)),
        run_id=UUID(str(run_id)),
        mode=cast(Any, run["mode"]),
        created_at=created_at,
        kind="DERIVED",
        artifact_sha256=assurance_blob.sha256,
        artifact_media_type="application/json",
        source_uri=None,
        dataset_product_id=None,
        dataset_version=None,
        granule_id=None,
        license_note="AnalogForge scientific claim audit",
        body=mission.target.body,
        aoi=mission.target,
        input_evidence_ids=[e.id for e in evidence],
        parameters_sha256=report.snapshot_sha256,
        algorithm_id="scientific-assurance",
        algorithm_version="1.0",
        native_resolution_m=None,
        comparison_scale_m=None,
        metrics=[],
        limitations=report.limitations,
    )
    if report.publication == "BLOCKED":
        # Preserve a diagnostic audit, but never create a passport/event.
        with store.transaction(workspace_id) as unit:
            register_blob(unit, assurance_blob)
            unit.create("evidence", assurance_evidence)
        raise ScientificClaimRejected(report.blocking_issue_codes or ["ASSURANCE_BLOCKED"])
    final_ids = frozenset(
        raw["requirement_id"]
        for raw in current.values()
        if attempts
        and raw["candidate_id"] == str(attempts[-1].candidate_id)
        and raw.get("payload", {}).get("evaluation_stage", raw.get("evaluation_stage")) == "FINAL"
    )
    snapshot = PassportSnapshot(
        audit=report,
        assurance_evidence=assurance_evidence,
        mission=mission,
        rover=rover,
        candidates=tuple(candidates),
        qualifications=qualifications,
        source_locks=locks,
        target_profile=public_model(PlanetaryTargetProfile, target_raw) if target_raw else None,
        attempts=tuple(attempts),
        compatibility=tuple(compatibility),
        critiques=critiques,
        portfolio=public_model(CompositePortfolio, portfolio_raw) if portfolio_raw else None,
        evidence=tuple(evidence),
        search_limitations=tuple(run.get("search_limitations", [])),
        not_run_reason=run.get("not_run_reason"),
        generated_at=created_at,
        final_route_requirement_ids=final_ids,
    )
    bundle = assemble_bundle(snapshot)
    manifest_blob = blob_store.put_bytes(bundle.canonical_manifest_json.encode(), "application/json")
    if (job_id is None) != (lease_token is None):
        raise ValueError("job_id and lease_token must be supplied together")
    context = (
        store.publication(workspace_id, job_id, lease_token)
        if job_id is not None and lease_token is not None
        else store.transaction(workspace_id)
    )
    with context as unit:
        latest = unit.require("runs", run_id, lock=True)
        if latest["revision"] != revision or latest["state"] in {"CANCELLED", "FAILED"}:
            raise ScientificClaimRejected(["SC-01:STALE_OR_CANCELLED_PUBLICATION"])
        register_blob(unit, assurance_blob)
        register_blob(unit, manifest_blob)
        unit.create("evidence", assurance_evidence)
        if not receipts:
            raise ScientificClaimRejected(["SC-02:ASSURANCE_INVOCATION_MISSING"])
        assurance_receipt = ToolReceipt(
            schema_version="1.0",
            id=uuid4(),
            workspace_id=UUID(str(workspace_id)),
            run_id=UUID(str(run_id)),
            mode=cast(Any, run["mode"]),
            created_at=created_at,
            invocation_id=receipts[-1].invocation_id,
            tool_name="build_passport_manifest",
            tool_version="1.0",
            input_sha256=report.snapshot_sha256,
            output_sha256=assurance_blob.sha256,
            evidence_ids=[assurance_evidence.id],
            status="SUCCEEDED",
            error_code=None,
            elapsed_ms=0,
            cache_hit=False,
        )
        unit.create(
            "tool_receipts",
            {**assurance_receipt.model_dump(mode="json"), "tool_call_id": "assurance-" + str(report.audit_id)},
        )
        for parent in assurance_evidence.input_evidence_ids:
            unit.create(
                "evidence_edges",
                {
                    "run_id": str(run_id),
                    "mode": run["mode"],
                    "parent_evidence_id": str(parent),
                    "child_evidence_id": str(assurance_evidence.id),
                    "relation": "DERIVED_FROM",
                },
            )
        unit.create("passports", {**bundle.passport.model_dump(mode="json"), "bundle": bundle.model_dump(mode="json")})
        latest["passport_id"] = str(bundle.passport.id)
        unit.replace("runs", run_id, latest, revision)
        unit.append_event(
            run_id,
            "passport.created",
            {
                "passport_id": str(bundle.passport.id),
                "manifest_sha256": bundle.manifest_sha256,
                "assurance_evidence_id": str(assurance_evidence.id),
            },
            run["mode"],
        )
        unit.enqueue("EXPORT_PASSPORT", {"passport_id": str(bundle.passport.id)}, run_id=run_id)
    return bundle
