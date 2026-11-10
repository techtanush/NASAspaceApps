# ruff: noqa: E501, S101
"""Helpers that regenerate the practice datasets (optionally perturbed) and drive the facade over them."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from analogforge.ports import catalog
from analogforge.ports.science import EvidenceHandle, LocalScienceContext, ScienceComputationResult, ScienceService
from analogforge.ports.science_payloads import (
    AnalyzeCandidateInput,
    CandidateRef,
    CharacterizeTargetInput,
    CharacterizeTargetPayload,
    ScreenCandidatesInput,
    ScreenCandidatesPayload,
    SourceSelector,
)
from analogforge.science.fixtures.practice import generate_all
from support.builders import load_mission, make_context, run
from support.registrar_stub import Registered

ALL = (
    "practice-mars-target-v1",
    "practice-moon-target-v1",
    "practice-moon-thermal-v1",
    "practice-earth-grid-v1",
    "practice-earth-minerals-v1",
)


def make_practice_context(root: Path, **gen: Any) -> LocalScienceContext:
    """Generate all practice datasets below ``root/data`` and return a context that knows their roots."""
    data = root / "data"
    generate_all(data, **gen)
    return make_context(root / "scratch", dataset_roots={d: data / d for d in ALL})


@dataclass
class Flow:
    """Accumulates registered evidence handles like the platform would hand them back to later calls."""

    svc: ScienceService
    ctx: LocalScienceContext
    handles: dict[str, EvidenceHandle] = field(default_factory=dict)
    results: list[ScienceComputationResult] = field(default_factory=list)
    elapsed: dict[str, float] = field(default_factory=dict)

    def call(self, inputs: Any, *, evidence: list[EvidenceHandle] | None = None, name: str | None = None, **kw: Any) -> tuple[ScienceComputationResult, Registered | None]:
        t0 = time.monotonic()
        result, reg = run(self.svc, inputs, self.ctx, evidence=evidence, **kw)
        self.elapsed[name or inputs.operation] = time.monotonic() - t0
        self.results.append(result)
        if reg is not None:
            for key, h in reg.handles.items():
                self.handles[f"{inputs.operation}:{key}"] = h
        return result, reg


def local(dataset_id: str) -> SourceSelector:
    return SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset_id)


def mars_target_aoi() -> Any:
    return load_mission("mission-mars-mobility").target


def characterize_mars(flow: Flow) -> tuple[CharacterizeTargetPayload, EvidenceHandle]:
    inp = CharacterizeTargetInput(
        target=mars_target_aoi(), source=local("practice-mars-target-v1"),
        measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET, requested_dimensions=["TERRAIN", "SCIENCE", "THERMAL"],
    )  # fmt: skip
    res, _ = flow.call(inp, datasets=["practice-mars-target-v1"])
    assert isinstance(res.payload, CharacterizeTargetPayload), res.issues
    return res.payload, flow.handles["CHARACTERIZE_TARGET:profile"]


def screen(flow: Flow, target: CharacterizeTargetPayload, mission_name: str = "mission-mars-mobility", max_detailed: int = 6) -> ScreenCandidatesPayload:
    mission = load_mission(mission_name)
    inp = ScreenCandidatesInput(
        search_region_set_id=catalog.SEARCH_REGION_PRACTICE, source=local("practice-earth-grid-v1"),
        target_metrics=target.metrics, target_histogram=target.slope_histogram,
        requirements=mission.requirements, max_detailed=max_detailed, reference_set_id=catalog.REFERENCE_SET_PRACTICE,
    )  # fmt: skip
    res, _ = flow.call(inp, datasets=["practice-earth-grid-v1"])
    assert isinstance(res.payload, ScreenCandidatesPayload), res.issues
    return res.payload


def candidate_ref(screened: ScreenCandidatesPayload, window_id: str) -> CandidateRef:
    w = next(x for x in screened.windows if x.window_id == window_id)
    return CandidateRef(window_id=w.window_id, name=w.name, aoi=w.aoi, origin=w.origin, novelty_status=w.novelty_status, discovery_method="practice grid screening")


def analyze(flow: Flow, cand: CandidateRef, datasets: list[str] | None = None) -> tuple[ScienceComputationResult, list[EvidenceHandle]]:
    """ANALYZE_CANDIDATE; returns the result and [analysis-grid handle, analysis-summary handle]."""
    inp = AnalyzeCandidateInput(candidate=cand, source=local("practice-earth-grid-v1"), measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH)
    res, reg = flow.call(inp, datasets=datasets or ["practice-earth-grid-v1"], name=f"analyze:{cand.window_id}")
    assert reg is not None
    return res, [reg.handles["analysis"], reg.handles["analysis-summary"]]


def compare(flow: Flow, req: Any, cand: CandidateRef, target: list[EvidenceHandle], cands: list[EvidenceHandle], verification: Any = None) -> Any:
    """COMPARE_REQUIREMENT through the facade with the policy id from the catalog map."""
    from analogforge.ports.science_payloads import CompareRequirementInput

    pid = catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(req.observable, "unknown-policy-v1")
    inp = CompareRequirementInput(
        requirement=req, candidate=cand, target_evidence_ids=[h.evidence_id for h in target],
        candidate_evidence_ids=[h.evidence_id for h in cands], verification=verification, observable_policy_id=pid,
    )  # fmt: skip
    res, _ = flow.call(inp, evidence=[*target, *cands])
    return res


def service() -> ScienceService:
    from analogforge.science.facade import create_science_service

    return create_science_service()



def prove(
    flow: Flow,
    screened: ScreenCandidatesPayload,
    window: str,
    rover: Any,
    strategy: str,
    rev: int,
    *,
    mission: Any = None,
    history: list[Any] | None = None,
    repairs: int = 2,
    switches: int = 1,
    datasets: list[str] | None = None,
) -> tuple[Any, CandidateRef]:
    """Analyze ``window`` then run design/search/verify/diagnose for it (one PROVE IT attempt) via the facade."""
    from analogforge.ports.science_payloads import DesignBenchmarkInput
    from support.graph_flow import attempt

    mission = mission or load_mission("mission-mars-mobility")
    cand = candidate_ref(screened, window)
    res, handles = analyze(flow, cand, datasets)
    assert res.status.value in ("SUCCEEDED", "LIMITED"), res.issues
    inp = DesignBenchmarkInput(
        mission=mission, rover=rover, candidate=cand, analysis_evidence_id=handles[0].evidence_id,
        strategy=strategy, test_revision=rev,
    )  # type: ignore[arg-type]  # fmt: skip
    att = attempt(flow.svc, flow.ctx, inp, evidence=[handles[0]], history=history, repairs=repairs, switches=switches, datasets=datasets or ["practice-earth-grid-v1"])
    return att, cand
