# ruff: noqa: E501, S603, S607, S101
"""Facade-level helpers for the design -> search -> verify -> diagnose flow (graph and raster)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import EvidenceHandle, LocalScienceContext, ScienceComputationResult, ScienceService
from analogforge.ports.science_payloads import (
    AttemptSummary,
    CandidateRef,
    ConstraintsArtifact,
    DesignBenchmarkInput,
    DesignBenchmarkPayload,
    DiagnoseResultInput,
    DiagnoseResultPayload,
    SearchRouteInput,
    SearchRoutePayload,
    VerificationSummary,
    VerifyRouteInput,
    VerifyRoutePayload,
)
from support.builders import run


@dataclass
class Attempt:
    constraints: ConstraintsArtifact
    constraints_sha: str
    search: SearchRoutePayload
    verify: VerifyRoutePayload | None
    diagnosis: DiagnoseResultPayload | None
    results: dict[str, ScienceComputationResult]
    elapsed: dict[str, float] = field(default_factory=dict)


def summary_of(v: VerifyRoutePayload) -> VerificationSummary:
    return VerificationSummary(
        outcome=v.outcome,
        failure_category=v.failure_category,
        violation_codes=sorted({x.code for x in v.violations}),
        metrics=list(v.metrics),
    )


def attempt(
    service: ScienceService,
    ctx: LocalScienceContext,
    design: DesignBenchmarkInput,
    *,
    evidence: list[EvidenceHandle] | None = None,
    history: list[AttemptSummary] | None = None,
    repairs: int = 2,
    switches: int = 1,
    do_verify: bool = True,
    **run_kw: Any,
) -> Attempt:
    """One PROVE-IT attempt exactly as the platform would drive it: design, search, verify, diagnose."""
    results: dict[str, ScienceComputationResult] = {}
    elapsed: dict[str, float] = {}
    t0 = time.monotonic()
    r, _ = run(service, design, ctx, evidence=evidence, **run_kw)
    elapsed["design"] = time.monotonic() - t0
    results["design"] = r
    assert isinstance(r.payload, DesignBenchmarkPayload), r.issues
    constraints, sha = r.payload.constraints, r.payload.constraints_sha256
    assert canonical_sha256(constraints) == sha
    t0 = time.monotonic()
    s, _ = run(service, SearchRouteInput(constraints=constraints, constraints_sha256=sha), ctx, evidence=evidence)
    elapsed["search"] = time.monotonic() - t0
    results["search"] = s
    assert isinstance(s.payload, SearchRoutePayload), s.issues
    verify: VerifyRoutePayload | None = None
    status = s.payload.search_status
    if s.payload.route is not None and do_verify:
        t0 = time.monotonic()
        v, _ = run(
            service,
            VerifyRouteInput(
                constraints=constraints, constraints_sha256=sha, route=s.payload.route,
                route_sha256=s.payload.route_sha256 or canonical_sha256(s.payload.route), search_status=status,
            ),
            ctx, evidence=evidence,
        )  # fmt: skip
        elapsed["verify"] = time.monotonic() - t0
        results["verify"] = v
        assert isinstance(v.payload, VerifyRoutePayload), v.issues
        verify = v.payload
    elif s.payload.route is None:
        verify = None
    diagnosis: DiagnoseResultPayload | None = None
    if verify is not None or status != "FOUND":
        summary = summary_of(verify) if verify is not None else VerificationSummary(
            outcome="INCONCLUSIVE" if status == "BUDGET_EXHAUSTED" else "FAIL",
            failure_category="SEARCH_LIMIT" if status == "BUDGET_EXHAUSTED" else None,
        )
        if verify is None and status == "EXHAUSTIVE_INFEASIBLE":
            summary = VerificationSummary(outcome="FAIL", failure_category="ANALOG", violation_codes=[])
        outcome_ok = verify is not None and verify.outcome == "PASS"
        if not outcome_ok:
            d, _ = run(
                service,
                DiagnoseResultInput(
                    constraints=constraints, search_status=status, verification=summary,
                    violations=list(verify.violations) if verify is not None else [],
                    attempt_history=history or [], remaining_route_repairs=repairs, remaining_candidate_switches=switches,
                ),
                ctx, evidence=evidence,
            )  # fmt: skip
            results["diagnose"] = d
            assert isinstance(d.payload, DiagnoseResultPayload), d.issues
            diagnosis = d.payload
    return Attempt(constraints, sha, s.payload, verify, diagnosis, results, elapsed)


def attempt_summary(n: int, candidate: CandidateRef, a: Attempt) -> AttemptSummary:
    return AttemptSummary(
        attempt_number=n, test_revision=a.constraints.test_revision, candidate_window_id=candidate.window_id,
        strategy=a.constraints.strategy,
        outcome=a.verify.outcome if a.verify is not None else "INCONCLUSIVE",
        failure_category=a.verify.failure_category if a.verify is not None else None,
        search_status=a.search.search_status,
        route_sha256=a.search.route_sha256,
        violation_codes=sorted({v.code for v in a.verify.violations}) if a.verify is not None else [],
    )  # fmt: skip
