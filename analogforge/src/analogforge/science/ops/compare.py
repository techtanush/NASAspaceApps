"""``COMPARE_REQUIREMENT`` and ``ASSESS_COMPATIBILITY`` (guide 08 sections 4.7 and 4.8).

The facade only reads evidence artifacts (target/candidate slope histograms), calls the pure comparison and
compatibility functions and packages the result as evidence plus a canonical-JSON payload artifact.
"""

from __future__ import annotations

import numpy as np

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.science import ComputationStatus, EvidenceHandle
from analogforge.ports.science_payloads import (
    AnalyzeCandidatePayload,
    AssessCompatibilityInput,
    AssessCompatibilityPayload,
    CharacterizeTargetPayload,
    CompareRequirementInput,
    Histogram,
)
from analogforge.science.comparison.compare import CompareInputs, compare_requirement
from analogforge.science.comparison.policies import SideEvidence
from analogforge.science.compatibility import assess_compatibility
from analogforge.science.features.coverage import QUALITY_NO_FULL_SUPPORT, QUALITY_OK
from analogforge.science.features.histogram import area_weighted_histogram, to_port_histogram
from analogforge.science.features.slope import analyze_surface
from analogforge.science.geometry import PixelGeometry
from analogforge.science.ops.base import (
    OpBlocked,
    OpEnv,
    OpOutcome,
    derived_evidence,
    json_artifact,
)
from analogforge.science.raster.normalize import aggregate_blocks
from analogforge.science.raster.store import decode_analysis_grid

NPZ = "application/x-npz"
TARGET_POLICIES = frozenset({"slope-w1-common-support-v1", "mineral-presence-v1", "thermal-min-v1"})


def _handles(env: OpEnv, ids: list[object]) -> tuple[EvidenceHandle, ...]:
    return tuple(env.handle(i) for i in ids)


def _target_histogram(env: OpEnv, handles: tuple[EvidenceHandle, ...]) -> Histogram | None:
    for h in handles:
        if h.algorithm_id == catalog.ALGORITHM_IDS["CHARACTERIZE_TARGET"] and h.artifact_sha256 is not None:
            hist = env.read_model(h, CharacterizeTargetPayload).slope_histogram
            if hist is not None:
                return hist
    return None


def histogram_at_support(env: OpEnv, handle: EvidenceHandle, support_m: float) -> Histogram | None:
    """Slope histogram of an ANALYSIS_GRID re-derived at ``support_m`` (area-averaged elevation, never upsampled)."""
    grid = decode_analysis_grid(env.artifact_path(handle).read_bytes())
    cell = grid.meta.cell_size_m
    ratio = support_m / cell
    factor = round(ratio)
    if factor < 1 or abs(ratio - factor) > 1e-6:
        return None
    edges = tuple(float(e) for e in env.cfg.measurement_spec(catalog.MEASUREMENT_SPEC_EARTH).slope_hist_edges_deg)
    if factor == 1:
        data = area_weighted_histogram(grid.slope_deg, grid.valid, cell * cell, edges)
        return to_port_histogram(data, support_scale_m=support_m) if data.valid_area_m2 > 0 else None
    usable = grid.land & ((grid.quality == QUALITY_OK) | (grid.quality == QUALITY_NO_FULL_SUPPORT))
    mean, ok = aggregate_blocks(grid.elevation_m, usable, factor)
    surf = analyze_surface(mean, PixelGeometry.north_up(support_m), nodata=~ok)
    valid = np.asarray(surf.valid, dtype=bool)
    slope = np.where(valid, surf.slope_deg, 0.0)
    data = area_weighted_histogram(slope, valid, support_m * support_m, edges)
    if data.valid_area_m2 <= 0:
        # no coarse cell has full support: an explicit empty histogram (the policy reports INSUFFICIENT_VALID_DATA)
        return Histogram(
            metric_id="surface_slope_deg", unit="deg", edges=list(edges),
            area_fraction=[0.0] * (len(edges) - 1), valid_area_m2=0.0, support_scale_m=support_m,
        )  # fmt: skip
    return to_port_histogram(data, support_scale_m=support_m)


def _candidate_histogram(env: OpEnv, handles: tuple[EvidenceHandle, ...], target: Histogram | None) -> Histogram | None:
    grids = [h for h in handles if h.algorithm_id == catalog.ALGORITHM_IDS["ANALYZE_CANDIDATE"] and h.artifact_sha256]
    summaries = [
        h for h in handles if h.algorithm_id == catalog.ALGORITHM_IDS["ANALYSIS_SUMMARY"] and h.artifact_sha256
    ]
    if target is not None and grids:
        hist = histogram_at_support(env, grids[0], target.support_scale_m)
        if hist is not None:
            return hist
    for h in summaries:
        hist = env.read_model(h, AnalyzeCandidatePayload).slope_histogram
        if hist is not None:
            return hist
    return None


def run_compare(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, CompareRequirementInput)
    algo = catalog.ALGORITHM_IDS["COMPARE_REQUIREMENT"]
    target_handles = _handles(env, list(inp.target_evidence_ids))
    cand_handles = _handles(env, list(inp.candidate_evidence_ids))
    if inp.observable_policy_id not in TARGET_POLICIES:
        # Policies that never read the planetary side must not be judged on its body (valid_bodies lists EARTH only).
        target_handles = ()
    target_hist = _target_histogram(env, target_handles)
    cand_hist = _candidate_histogram(env, cand_handles, target_hist)
    outcome = compare_requirement(
        CompareInputs(
            requirement=inp.requirement,
            policy_id=inp.observable_policy_id,
            mode=env.request.mode,
            candidate=SideEvidence(handles=cand_handles, histogram=cand_hist),
            target=SideEvidence(handles=target_handles, histogram=target_hist),
            verification=inp.verification,
        ),
        env.cfg,
    )
    params = env.params_hash(algo, env.operation_params())
    payload = outcome.to_payload(EvidenceRef(local_key="comparison"))
    art = json_artifact(env, params_sha=params, key="comparison-json", name="comparison.json", payload=payload)
    parents = sorted({h.evidence_id for h in (*_handles(env, list(inp.target_evidence_ids)), *cand_handles)}, key=str)
    req_art = json_artifact(
        env, params_sha=params, key="requirement-json", name="requirement.json", payload=inp.requirement
    )
    req_ev = derived_evidence(
        env,
        key="requirement",
        kind="ASSUMPTION",
        body="EARTH",
        algorithm_id=algo,
        params_sha=env.params_hash(algo, {"requirement": inp.requirement.model_dump(mode="json")}),
        artifact=req_art,
        limitations=[
            "Requirement record as accepted in the mission contract; carried so the audit can read its window."
        ],
    )
    ev = derived_evidence(
        env,
        key="comparison",
        parent_keys=["requirement"],
        kind="COMPARISON",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        parent_evidence_ids=parents,
        metrics=outcome.metrics,
        limitations=outcome.limitations,
        comparison_scale_m=outcome.comparison_scale_m,
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art, req_art], [req_ev, ev])


def run_compat(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, AssessCompatibilityInput)
    algo = catalog.ALGORITHM_IDS["ASSESS_COMPATIBILITY"]
    handles = _handles(env, list(inp.candidate_evidence_ids))
    scales = [h.comparison_scale_m for h in handles if h.comparison_scale_m is not None]
    scales += [h.native_resolution_m for h in handles if h.native_resolution_m is not None]
    support = max(scales) if scales else None
    refs = [EvidenceRef(local_key="compatibility")]
    try:
        result = assess_compatibility(
            inp.rover,
            inp.requirements,
            verification=inp.verification,
            constraints=inp.constraints,
            candidate_support_scale_m=support,
            evidence=refs,
        )
    except ValueError as exc:
        raise OpBlocked(f"compatibility cannot be assessed: {exc}", detail_code="COMPATIBILITY_INPUT") from exc
    params = env.params_hash(algo, env.operation_params())
    payload = AssessCompatibilityPayload(
        preliminary=result.preliminary,
        dimensions=list(result.dimensions),
        compatibility_evidence=EvidenceRef(local_key="compatibility"),
    )
    art = json_artifact(env, params_sha=params, key="compatibility-json", name="compatibility.json", payload=payload)
    ev = derived_evidence(
        env,
        key="compatibility",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        parent_evidence_ids=[h.evidence_id for h in handles],
        limitations=["Capabilities are declared by the rover profile, not observed."],
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], [ev])
