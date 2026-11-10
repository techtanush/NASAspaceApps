# ruff: noqa: E501, E402, S603, S607, S101
"""SCN-21: cancellation and deadline are honoured within 1 s and never swallowed."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from support.builders import load_mission, load_rover, make_context, make_request

from analogforge.ports import catalog
from analogforge.ports.science import ScienceCancelled, ScienceDeadlineExceeded
from analogforge.ports.science_payloads import CandidateRef, DesignBenchmarkInput
from analogforge.science.facade import create_science_service


def _design() -> DesignBenchmarkInput:
    mission = load_mission("mission-graph-regression")
    return DesignBenchmarkInput(
        mission=mission, rover=load_rover("ares-1"),
        candidate=CandidateRef(
            window_id=catalog.GRAPH_WINDOW_ID, name="g", aoi=mission.target.model_copy(update={"body": "EARTH"}),
            origin="SYNTHETIC_CONTROL", novelty_status="NOT_ASSESSED", discovery_method="fixture",
        ),
        analysis_evidence_id=None, graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH,
        strategy="WAYPOINT_RETURN", test_revision=1,
    )  # fmt: skip


def test_cancelled_context_raises_within_one_second(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    ctx.cancelled = True
    start = time.monotonic()
    with pytest.raises(ScienceCancelled):
        create_science_service().execute(make_request(_design()), ctx)
    assert time.monotonic() - start < 1.0


def test_expired_deadline_raises_within_one_second(tmp_path: Path) -> None:
    ctx = make_context(tmp_path, deadline_monotonic=time.monotonic() - 1.0)
    start = time.monotonic()
    with pytest.raises(ScienceDeadlineExceeded):
        create_science_service().execute(make_request(_design()), ctx)
    assert time.monotonic() - start < 1.0


def test_cancellation_is_not_converted_to_a_result(tmp_path: Path) -> None:
    """A BLOCKED/FAILED envelope for a cancelled run would be a swallowed cancellation."""
    ctx = make_context(tmp_path)
    ctx.cancelled = True
    with pytest.raises(ScienceCancelled):
        create_science_service().execute(make_request(_design()), ctx)


# --------------------------------------------------------------------------- raster operations
from dataclasses import dataclass  # noqa: E402

from support.practice import (  # noqa: E402
    Flow,
    candidate_ref,
    characterize_mars,
    local,
    make_practice_context,
    screen,
    service,
)

from analogforge.ports.science import LocalScienceContext  # noqa: E402
from analogforge.ports.science import ScienceDeadlineExceeded as _Deadline
from analogforge.ports.science_payloads import ScreenCandidatesInput, SearchRouteInput  # noqa: E402


@dataclass
class CancelAfter(LocalScienceContext):
    """Raises ScienceCancelled on the n-th checkpoint (counts every ``check_cancelled`` call)."""

    after: int = 3
    calls: int = 0

    def check_cancelled(self) -> None:
        self.calls += 1
        if self.calls >= self.after:
            raise ScienceCancelled()


def _clone(ctx: LocalScienceContext, cls: type, **kw: object) -> LocalScienceContext:
    return cls(scratch=ctx.scratch, workspace_id=ctx.workspace_id, job_id=ctx.job_id, mode=ctx.mode, dataset_roots=ctx.dataset_roots, artifact_paths=ctx.artifact_paths, **kw)


@pytest.fixture(scope="module")
def prac(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    ctx = make_practice_context(tmp_path_factory.mktemp("cancel"))
    flow = Flow(service(), ctx)
    target, _ = characterize_mars(flow)
    sc = screen(flow, target)
    return flow, target, sc


def test_screening_honours_cancel_and_deadline(prac) -> None:  # type: ignore[no-untyped-def]
    flow, target, _ = prac
    mission = load_mission("mission-mars-mobility")
    inp = ScreenCandidatesInput(search_region_set_id=catalog.SEARCH_REGION_PRACTICE, source=local("practice-earth-grid-v1"), target_metrics=target.metrics, target_histogram=target.slope_histogram, requirements=mission.requirements, max_detailed=6, reference_set_id=catalog.REFERENCE_SET_PRACTICE)
    req = make_request(inp, datasets=["practice-earth-grid-v1"])
    for ctx, exc in ((_clone(flow.ctx, CancelAfter, after=4), ScienceCancelled), (_clone(flow.ctx, LocalScienceContext, deadline_monotonic=time.monotonic() - 1.0), _Deadline)):
        start = time.monotonic()
        with pytest.raises(exc):
            flow.svc.execute(req, ctx)
        assert time.monotonic() - start < 1.0


def test_analysis_honours_cancel(prac) -> None:  # type: ignore[no-untyped-def]
    flow, _, sc = prac
    from analogforge.ports.science_payloads import AnalyzeCandidateInput

    inp = AnalyzeCandidateInput(candidate=candidate_ref(sc, catalog.WINDOW_B_CORRIDOR), source=local("practice-earth-grid-v1"), measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH)
    ctx = _clone(flow.ctx, CancelAfter, after=2)
    start = time.monotonic()
    with pytest.raises(ScienceCancelled):
        flow.svc.execute(make_request(inp, datasets=["practice-earth-grid-v1"]), ctx)
    assert time.monotonic() - start < 1.0


def test_search_honours_cancel_mid_run(prac) -> None:  # type: ignore[no-untyped-def]
    flow, _, sc = prac
    from support.practice import prove

    att, _ = prove(flow, sc, catalog.WINDOW_B_CORRIDOR, load_rover("ares-1"), "EXPOSURE_COVERAGE", 1)
    inp = SearchRouteInput(constraints=att.constraints, constraints_sha256=att.constraints_sha)
    # the grid blob must be authorized: flow.ctx.artifact_paths already knows it
    for after in (1, 3, 10):
        ctx = _clone(flow.ctx, CancelAfter, after=after)
        start = time.monotonic()
        with pytest.raises(ScienceCancelled):
            flow.svc.execute(make_request(inp), ctx)
        assert time.monotonic() - start < 1.0
    ok = _clone(flow.ctx, CancelAfter, after=10**9)
    assert flow.svc.execute(make_request(inp), ok).status.value == "SUCCEEDED"
