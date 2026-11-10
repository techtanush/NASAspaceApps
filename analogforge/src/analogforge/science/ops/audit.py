"""``AUDIT_EVIDENCE`` (guide 08 section 4.15): wraps :mod:`analogforge.science.audit`.

The kit's ``AuditEvidenceInput`` carries no requirement records, so requirement-window checks that need the window
(SC-04 against ``minimum_support_scale_m``) are reported by the audit as not assessable rather than guessed.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from uuid import UUID

from analogforge.ports import catalog
from analogforge.ports.domain_models import Requirement
from analogforge.ports.science import ComputationStatus, EvidenceHandle
from analogforge.ports.science_payloads import AuditEvidenceInput, ScreenCandidatesPayload
from analogforge.science.audit import DiscoveryEvidence, audit_evidence, discovery_evidence_from_screening
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact

_REF = re.compile(r"reference_set=([A-Za-z0-9._-]+)")


def _mission_sensitivity_ids(evidence: Sequence[EvidenceHandle]) -> list[UUID]:
    """Comparison evidence that shows the screening was judged under more than one mission contract.

    One comparison is a single verdict, not a sensitivity analysis.  Sensitivity evidence needs at least two
    ``COMPARISON`` records computed with different parameters (different requirements or thresholds); otherwise the
    list is empty and SC-13 reports the gap.
    """
    comparisons = [
        h for h in evidence if h.kind == "COMPARISON" and h.algorithm_id == catalog.ALGORITHM_IDS["COMPARE_REQUIREMENT"]
    ]
    if len({h.parameters_sha256 for h in comparisons}) < 2:
        return []
    return [h.evidence_id for h in comparisons]


def run_audit(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, AuditEvidenceInput)
    algo = catalog.ALGORITHM_IDS["AUDIT_EVIDENCE"]
    discovery: dict[UUID, DiscoveryEvidence] = {}
    screening = [h for h in env.request.input_evidence if h.algorithm_id == catalog.ALGORITHM_ID_SCREENING]
    for h in screening:
        if h.artifact_sha256 is None:
            continue
        try:
            table = env.read_model(h, ScreenCandidatesPayload)
        except OpBlocked:  # a foreign artifact is not a screening table
            continue
        ref = next((m.group(1) for lim in h.limitations if (m := _REF.search(lim))), None)
        discovery[h.evidence_id] = discovery_evidence_from_screening(
            table,
            reference_set_id=ref,
            mission_sensitivity_evidence_ids=_mission_sensitivity_ids(env.request.input_evidence),
        )
    requirements: dict[str, Requirement] = {}
    for h in env.request.input_evidence:
        if h.kind == "ASSUMPTION" and h.algorithm_id == catalog.ALGORITHM_IDS["COMPARE_REQUIREMENT"]:
            try:
                req = env.read_model(h, Requirement)
            except OpBlocked:
                continue
            requirements[req.id] = req
    payload = audit_evidence(
        inp,
        requirements=requirements or None,
        mode=env.request.mode,
        evidence=list(env.request.input_evidence),
        config=env.cfg,
        discovery=discovery,
    )
    params = env.params_hash(algo, env.operation_params())
    art = json_artifact(env, params_sha=params, key="audit-json", name="audit.json", payload=payload)
    ev = derived_evidence(
        env,
        key="audit",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        parent_evidence_ids=[h.evidence_id for h in env.request.input_evidence],
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], [ev])
