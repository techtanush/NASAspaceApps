# ruff: noqa: S101
"""SC-02 consistency at the platform seam (found in the Tanush+Ayan trial merge, 2026-11-11).

The platform hands COMPARE_REQUIREMENT the candidate's evidence exactly as architecture 35 section 5b lists it:
the screening evidence (per-window and run-level) plus the analysis evidences. Two invariants must hold:

1. Every derived evidence draft any operation emits references an artifact in the same result (real bytes, SC-02).
2. A positive proposal (PASS/PARTIAL) never carries an adequacy gate the platform rejects
   (SC-02..SC-11 and SC-13 must not be NOT_ASSESSED or UNSATISFIED; application/qualification.py).
"""

from __future__ import annotations

import pytest
from support.builders import load_mission
from support.practice import Flow, analyze, candidate_ref, characterize_mars, make_practice_context, screen, service

from analogforge.ports import catalog
from analogforge.ports.science_payloads import CompareRequirementInput

PLATFORM_REQUIRED_GATES = [*(f"SC-{i:02}" for i in range(2, 12)), "SC-13"]


@pytest.fixture(scope="module")
def flow_after_analysis(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    flow = Flow(service(), make_practice_context(tmp_path_factory.mktemp("sc02")))
    target, target_handle = characterize_mars(flow)
    screened = screen(flow, target)
    analyses = {}
    for window_id in (catalog.WINDOW_A_MESA, catalog.WINDOW_B_CORRIDOR):
        cand = candidate_ref(screened, window_id)
        _, handles = analyze(flow, cand)
        analyses[window_id] = (cand, handles)
    return flow, target_handle, analyses


def test_every_derived_draft_has_artifact_bytes(flow_after_analysis) -> None:  # type: ignore[no-untyped-def]
    flow, _, _ = flow_after_analysis
    checked = 0
    for result in flow.results:
        artifact_keys = {a.local_key for a in result.artifacts}
        for draft in result.evidence_drafts:
            if draft.kind == "SOURCE":
                continue
            checked += 1
            assert draft.artifact_key is not None, (result.operation, draft.local_key)
            assert draft.artifact_key in artifact_keys, (result.operation, draft.local_key, draft.artifact_key)
    assert checked > 0


def test_positive_proposals_satisfy_platform_gates_with_platform_evidence(flow_after_analysis) -> None:  # type: ignore[no-untyped-def]
    flow, target_handle, analyses = flow_after_analysis
    mission = load_mission("mission-mars-mobility")
    positives = 0
    for window_id, (cand, analysis_handles) in analyses.items():
        screening = [flow.handles["SCREEN_CANDIDATES:screening"], flow.handles[f"SCREEN_CANDIDATES:window-{window_id}"]]
        cand_handles = [*screening, *analysis_handles]
        for req in mission.requirements:
            policy = catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(req.observable, "unknown-policy-v1")
            inp = CompareRequirementInput(
                requirement=req,
                candidate=cand,
                target_evidence_ids=[target_handle.evidence_id],
                candidate_evidence_ids=[h.evidence_id for h in cand_handles],
                verification=None,
                observable_policy_id=policy,
            )
            result, _ = flow.call(inp, evidence=[target_handle, *cand_handles])
            payload = result.payload
            if payload is None or payload.proposed_status not in {"PASS", "PARTIAL"}:
                continue
            positives += 1
            outcomes = {g.gate_id: g.outcome for g in payload.adequacy.gates}
            rejected = {None, "NOT_ASSESSED", "UNSATISFIED"}
            bad = {g: outcomes.get(g) for g in PLATFORM_REQUIRED_GATES if outcomes.get(g) in rejected}
            assert not bad, (window_id, req.id, payload.proposed_status, bad)
    assert positives > 0, "the practice storyline must produce at least one positive terrain row"


def test_positive_qualification_claims_are_fully_assessable_by_the_audit(flow_after_analysis) -> None:  # type: ignore[no-untyped-def]
    """The audited claim cites the COMPARISON + requirement records (35 s5b); they must carry the decisive values."""
    from analogforge.ports.science_payloads import AuditEvidenceInput, AuditEvidencePayload, ClaimScope

    flow, target_handle, analyses = flow_after_analysis
    mission = load_mission("mission-mars-mobility")
    audited = 0
    for window_id, (cand, analysis_handles) in analyses.items():
        screening = [flow.handles["SCREEN_CANDIDATES:screening"], flow.handles[f"SCREEN_CANDIDATES:window-{window_id}"]]
        cand_handles = [*screening, *analysis_handles]
        for req in mission.requirements:
            policy = catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(req.observable, "unknown-policy-v1")
            inp = CompareRequirementInput(
                requirement=req,
                candidate=cand,
                target_evidence_ids=[target_handle.evidence_id],
                candidate_evidence_ids=[h.evidence_id for h in cand_handles],
                verification=None,
                observable_policy_id=policy,
            )
            result, reg = flow.call(inp, evidence=[target_handle, *cand_handles])
            payload = result.payload
            if payload is None or payload.proposed_status not in {"PASS", "PARTIAL"} or reg is None:
                continue
            row_handles = [reg.handles["comparison"], reg.handles["requirement"]]
            assert any(m.value is not None for m in reg.handles["comparison"].metrics), req.id
            claim = ClaimScope(
                claim_id=f"q:{window_id}:{req.id}",
                claim_type="QUALIFICATION",
                requirement_id=req.id,
                candidate_window_ids=[window_id],
                evidence_ids=[h.evidence_id for h in row_handles],
            )
            audit, _ = flow.call(
                AuditEvidenceInput(claims=[claim], check_set=[
                    "provenance", "units", "crs", "scale", "coverage", "uncertainty", "proxies", "independence",
                ]),
                evidence=[*row_handles],
            )
            assert isinstance(audit.payload, AuditEvidencePayload), audit.issues
            outcomes = {g.gate_id: g.outcome for g in audit.payload.claim_gates[0].gates}
            assert outcomes["SC-05"] != "NOT_ASSESSED" and outcomes["SC-08"] != "NOT_ASSESSED", (req.id, outcomes)
            audited += 1
    assert audited > 0
