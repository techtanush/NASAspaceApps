"""Actual independent verifier rows keep exposure identities through the comparison operation."""

import pickle
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import fields
from uuid import uuid4

import pytest
from support.builders import make_context, make_request, run
from support.registrar_stub import register

from analogforge.jobs import cpu
from analogforge.jobs.context import WorkerScienceContext
from analogforge.ports import catalog
from analogforge.ports.hashing import (
    MISSION_CONTENT_EXCLUDE,
    bytes_sha256,
    canonical_json_bytes,
    canonical_sha256,
    model_sha256,
)
from analogforge.ports.science import LocalScienceContext, ScienceRequest
from analogforge.ports.science_payloads import CompareRequirementInput, VerificationSummary, VerifyRouteInput
from analogforge.science.facade import create_science_service
from tests.unit.science.test_routing_support import candidate, graph_design, make_route, mission


def case(tmp_path):
    accepted = mission()
    original = next(r for r in accepted.requirements if r.id == "R-EXPOSURE")
    other = original.model_copy(update={"id": "R-OTHER-EXPOSURE", "lower": 300.0})
    accepted = accepted.model_copy(update={"requirements": [*accepted.requirements, other]})
    accepted = accepted.model_copy(update={"content_sha256": model_sha256(accepted, MISSION_CONTENT_EXCLUDE)})
    designed = graph_design(mission_obj=accepted)
    route = make_route(designed.constraints_sha256, catalog.GRAPH_SUPPLIED_ROUTE_PASS)
    service = create_science_service()
    context = make_context(tmp_path, run_id=uuid4())
    context.test_candidate = candidate().model_copy(update={"candidate_id": uuid4()})
    request = make_request(VerifyRouteInput(
        constraints=designed.constraints, constraints_sha256=designed.constraints_sha256,
        route=route, route_sha256=canonical_sha256(route), search_status="NOT_RUN",
    ))
    result = service.execute(request, context)
    registered = register(request, result, context)
    assert registered is not None
    report = result.payload
    assert report.outcome == "FAIL" and report.verified_route_sha256 is None
    assert [(v.code, v.requirement_id) for v in report.violations] == [("EXPOSURE_SHORTFALL", other.id)]
    summary = VerificationSummary(
        outcome=report.outcome, failure_category=report.failure_category,
        violation_codes=[v.code for v in report.violations], metrics=report.metrics, test_result_id=uuid4(),
    )
    verifier = next(handle for handle in registered.handles.values() if handle.kind == "VERIFICATION")
    context.verification_requests = {str(verifier.evidence_id): {
        "workspace_id": str(context.workspace_id), "run_id": str(context.run_id), "mode": context.mode,
        "candidate_id": str(context.test_candidate.candidate_id),
        "candidate_window_id": context.test_candidate.window_id, "test_result_id": str(summary.test_result_id),
        "constraints_sha256": designed.constraints_sha256, "route_sha256": canonical_sha256(route),
        "evidence_id": str(verifier.evidence_id), "artifact_sha256": verifier.artifact_sha256,
        "receipt_input_sha256": canonical_sha256(request), "request": request.model_dump(mode="json"),
    }}
    return service, context, registered, report, summary, original, other


def compare(service, context, handles, summary, requirement):
    result, _ = run(service, CompareRequirementInput(
        requirement=requirement, candidate=context.test_candidate, target_evidence_ids=[],
        candidate_evidence_ids=[h.evidence_id for h in handles], verification=summary,
        observable_policy_id="route-exposure-v1",
    ), context, evidence=handles)
    assert result.payload is not None, result.issues
    return result.payload


def test_actual_verifier_scopes_150m_pass_and_300m_shortfall_without_promoting_failed_route(tmp_path):
    service, context, registered, report, summary, original, other = case(tmp_path)
    rows = {row.requirement_id: row for row in report.benchmark_rows if row.requirement_id is not None}
    assert (rows[original.id].measured, rows[original.id].threshold, rows[original.id].status) == (150, 100, "PASS")
    assert (rows[other.id].measured, rows[other.id].threshold, rows[other.id].status) == (150, 300, "FAIL")
    handles = list(registered.handles.values())
    supported = compare(service, context, handles, summary, original)
    short = compare(service, context, handles, summary, other)
    assert (supported.proposed_status, supported.measured_value) == ("PASS", 150)
    assert (short.proposed_status, short.measured_value) == ("FAIL", 150)
    assert report.outcome == "FAIL" and report.verified_route_sha256 is None


@pytest.mark.parametrize("defect", ["checksum", "missing", "codes", "metrics", "duplicate", "requirement", "constraint",
                                     "threshold", "unit", "unscoped_violation", "stale_report", "outcome",
                                     "missing_binding", "parameters"])
def test_ambiguous_or_mismatched_verifier_detail_cannot_authorize_exposure_support(tmp_path, defect):
    service, context, registered, report, summary, original, _ = case(tmp_path)
    handles = list(registered.handles.values())
    verifier = next(h for h in handles if h.kind == "VERIFICATION")
    if defect == "checksum":
        context.read_artifact(verifier.artifact_sha256).write_bytes(b"{}")
    elif defect == "missing":
        context.read_artifact(verifier.artifact_sha256).unlink()
    elif defect == "codes":
        summary = summary.model_copy(update={"violation_codes": ["EXPOSURE_SHORTFALL", "EXPOSURE_SHORTFALL"]})
    elif defect == "metrics":
        summary = summary.model_copy(update={"metrics": [m.model_copy(update={"value": 151})
            if m.metric_id == f"unique_exposure_m:{original.id}" else m for m in summary.metrics]})
    elif defect == "duplicate":
        duplicate = verifier.model_copy(update={"evidence_id": uuid4()})
        handles.append(duplicate)
        context.verification_requests[str(duplicate.evidence_id)] = {
            **context.verification_requests[str(verifier.evidence_id)], "evidence_id": str(duplicate.evidence_id),
        }
    elif defect == "missing_binding":
        context.verification_requests = {}
    elif defect == "parameters":
        handles = [h.model_copy(update={"parameters_sha256": "0" * 64}) if h == verifier else h for h in handles]
    else:
        # Rehash changed test bytes so this exercises semantic identity checks, not just checksum rejection.
        data = report.model_dump(mode="json")
        row = next(r for r in data["benchmark_rows"] if r["requirement_id"] == original.id)
        if defect == "unscoped_violation":
            data["violations"][0]["requirement_id"] = None
        elif defect == "stale_report":
            next(m for m in data["metrics"] if m["metric_id"] == f"unique_exposure_m:{original.id}")["value"] = 149
        elif defect == "outcome":
            data.update(outcome="INCONCLUSIVE", failure_category="DATA")
        else:
            key, value = {"requirement": ("requirement_id", "unrelated"),
                "constraint": ("constraint_id", "C-EXPOSURE-unrelated"), "threshold": ("threshold", 99),
                "unit": ("unit", "km")}[defect]
            row[key] = value
        raw = canonical_json_bytes(data)
        replacement = verifier.model_copy(update={"artifact_sha256": bytes_sha256(raw)})
        # Authorize the deliberately changed bytes only in this local science fixture.
        path = context.read_artifact(verifier.artifact_sha256)
        path.write_bytes(raw)
        context.artifact_paths[replacement.artifact_sha256] = path
        context.verification_requests[str(replacement.evidence_id)]["artifact_sha256"] = replacement.artifact_sha256
        handles = [replacement if h.evidence_id == verifier.evidence_id else h for h in handles]
    result = compare(service, context, handles, summary, original)
    assert result.proposed_status == "UNKNOWN"


@pytest.mark.parametrize("foreign", ["candidate", "route"])
def test_equally_valued_foreign_verifier_cannot_qualify_the_current_candidate_or_route(tmp_path, foreign):
    service, context, registered, original_report, summary, original, _ = case(tmp_path)
    current = next(iter(context.verification_requests.values()))
    source = ScienceRequest.model_validate(current["request"]).inputs
    constraints, route = source.constraints, source.route
    if foreign == "candidate":
        constraints = constraints.model_copy(update={"candidate_window_id": "other-candidate"})
        route = route.model_copy(update={"constraints_sha256": canonical_sha256(constraints)})
    else:
        route = route.model_copy(update={"route_key": "equally-valued-other-route"})
    request = make_request(VerifyRouteInput(
        constraints=constraints, constraints_sha256=canonical_sha256(constraints),
        route=route, route_sha256=canonical_sha256(route), search_status=source.search_status,
    ))
    checked = service.execute(request, context)
    foreign_registered = register(request, checked, context)
    assert checked.payload.metrics == original_report.metrics and checked.payload.outcome == "FAIL"
    verifier = next(h for h in foreign_registered.handles.values() if h.kind == "VERIFICATION")
    # The expected current binding remains frozen; the actual source request belongs elsewhere.
    context.verification_requests = {str(verifier.evidence_id): {
        **current, "evidence_id": str(verifier.evidence_id), "artifact_sha256": verifier.artifact_sha256,
        "receipt_input_sha256": canonical_sha256(request), "request": request.model_dump(mode="json"),
    }}
    result = compare(service, context, list(foreign_registered.handles.values()), summary, original)
    assert result.proposed_status == "UNKNOWN"


def test_pickled_cpu_context_does_not_reuse_a_previous_requests_verification_authority(tmp_path):
    service, context, registered, _, summary, original, _ = case(tmp_path)
    handles = list(registered.handles.values())
    inputs = CompareRequirementInput(
        requirement=original, candidate=context.test_candidate, target_evidence_ids=[],
        candidate_evidence_ids=[h.evidence_id for h in handles], verification=summary,
        observable_policy_id="route-exposure-v1",
    )
    worker = WorkerScienceContext(**{field.name: getattr(context, field.name) for field in fields(LocalScienceContext)},
                                  verification_requests=deepcopy(context.verification_requests))
    worker = pickle.loads(pickle.dumps(worker))  # noqa: S301 - only locally constructed fixture bytes
    # The baseline CPU-session wrapper reuses one spawned process when merged; the same two-call seam also runs
    # against integration's current per-call executor without claiming that it already has process reuse.
    with getattr(cpu, "science_session", nullcontext)():
        first = cpu.run_science(service, make_request(inputs, evidence=handles), worker, timeout_seconds=15)
        empty = deepcopy(worker)
        empty.verification_requests = {}
        second = cpu.run_science(service, make_request(inputs, evidence=handles), empty, timeout_seconds=15)
    assert first.payload.proposed_status == "PASS"
    assert second.payload.proposed_status == "UNKNOWN"
