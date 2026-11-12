# ruff: noqa: S101
"""Route-level VERIFICATION claims are audited on their own evidence (found in the Tanush+Ayan trial merge).

The platform proposes one VERIFICATION claim per test (``requirement_id=None``); per-requirement statements are
separate QUALIFICATION claims (E-09). Before this fix the audit left SC-03/04/06/07 NOT_ASSESSED for every such
claim, so the platform refused every verified PASS. These tests pin the corrected behavior and keep the gates
honest (the assumption gate still bites when the accepted-assumption record is absent).
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from support.builders import make_context, run
from support.graph_flow import attempt, attempt_summary

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    AuditEvidenceInput,
    AuditEvidencePayload,
    ClaimScope,
    SearchRouteInput,
    VerifyRouteInput,
)
from analogforge.science.facade import create_science_service

ALL_CHECKS = ["provenance", "units", "crs", "scale", "coverage", "uncertainty", "proxies", "independence"]
PLATFORM_REQUIRED = {"SC-02", "SC-07", "SC-09", "SC-11"}  # may never be NOT_APPLICABLE on a positive VERIFICATION


def _graph_pass(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Attempt 2 of S-GRAPH-1 (EXPOSURE_COVERAGE, PASS), re-run search and verify through the registrar stub."""
    from tests.integration.science.test_storylines import _graph_candidate, _graph_design

    svc = create_science_service()
    ctx = make_context(tmp_path)
    a1 = attempt(svc, ctx, _graph_design("WAYPOINT_RETURN", 1))
    a2 = attempt(svc, ctx, _graph_design("EXPOSURE_COVERAGE", 2), history=[attempt_summary(1, _graph_candidate(), a1)])
    assert a2.verify is not None and a2.verify.outcome == "PASS"
    search_input = SearchRouteInput(constraints=a2.constraints, constraints_sha256=a2.constraints_sha)
    search, search_reg = run(svc, search_input, ctx)
    route = search.payload.route  # type: ignore[union-attr]
    assert route is not None and search_reg is not None
    verify, verify_reg = run(
        svc,
        VerifyRouteInput(
            constraints=a2.constraints,
            constraints_sha256=a2.constraints_sha,
            route=route,
            route_sha256=search.payload.route_sha256 or canonical_sha256(route),  # type: ignore[union-attr]
            search_status=search.payload.search_status,  # type: ignore[union-attr]
        ),
        ctx,
    )
    assert verify_reg is not None
    return svc, ctx, verify, list(verify_reg.handles.values()), list(search_reg.handles.values())


def _audit(svc, ctx, handles) -> dict[str, tuple[str, str]]:  # type: ignore[no-untyped-def]
    claim = ClaimScope(
        claim_id=f"v:{uuid4()}",
        claim_type="VERIFICATION",
        requirement_id=None,
        candidate_window_ids=[catalog.GRAPH_WINDOW_ID],
        evidence_ids=[h.evidence_id for h in handles],
    )
    res, _ = run(svc, AuditEvidenceInput(claims=[claim], check_set=ALL_CHECKS), ctx, evidence=handles)  # type: ignore[arg-type]
    assert isinstance(res.payload, AuditEvidencePayload), res.issues
    (gates,) = res.payload.claim_gates
    return {g.gate_id: (g.outcome, g.reason) for g in gates.gates}


def test_verified_graph_route_emits_accepted_assumption_record(tmp_path: Path) -> None:
    _, _, result, handles, _ = _graph_pass(tmp_path)
    kinds = {h.kind for h in handles}
    assert {"VERIFICATION", "ASSUMPTION"} <= kinds
    assumption = next(d for d in result.evidence_drafts if d.kind == "ASSUMPTION")
    assert assumption.artifact_key in {a.local_key for a in result.artifacts}


def test_route_verification_claim_is_fully_assessed(tmp_path: Path) -> None:
    svc, ctx, _, handles, search_handles = _graph_pass(tmp_path)
    gates = _audit(svc, ctx, [*handles, *search_handles])
    assert gates["SC-03"][0] == "SATISFIED", gates["SC-03"]
    assert gates["SC-04"][0] == "NOT_APPLICABLE" and "abstract synthetic graph" in gates["SC-04"][1]
    assert gates["SC-06"][0] == "NOT_APPLICABLE", gates["SC-06"]
    assert gates["SC-07"][0] == "SATISFIED", gates["SC-07"]
    bad = {g: v for g, v in gates.items() if v[0] in {"NOT_ASSESSED", "UNSATISFIED"}}
    assert not bad, bad
    assert all(gates[g][0] != "NOT_APPLICABLE" for g in PLATFORM_REQUIRED if g in gates)


def test_assumption_gate_still_bites_without_the_accepted_record(tmp_path: Path) -> None:
    svc, ctx, _, handles, search_handles = _graph_pass(tmp_path)
    without = [h for h in [*handles, *search_handles] if h.kind != "ASSUMPTION"]
    gates = _audit(svc, ctx, without)
    assert gates["SC-07"][0] == "NOT_ASSESSED", gates["SC-07"]
