"""The job CPU boundary preserves request-scoped verification authority."""

import pickle
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import fields

from analogforge.jobs import cpu
from analogforge.jobs.context import WorkerScienceContext
from analogforge.ports.science import LocalScienceContext
from analogforge.ports.science_payloads import CompareRequirementInput
from tests.fixtures.science.support.builders import make_request
from tests.integration.science.test_exposure_identity import case


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
    # The same two-call seam runs against the candidate-scoped spawned CPU session.
    with getattr(cpu, "science_session", nullcontext)():
        first = cpu.run_science(service, make_request(inputs, evidence=handles), worker, timeout_seconds=15)
        empty = deepcopy(worker)
        empty.verification_requests = {}
        second = cpu.run_science(service, make_request(inputs, evidence=handles), empty, timeout_seconds=15)
    assert first.payload.proposed_status == "PASS"
    assert second.payload.proposed_status == "UNKNOWN"
