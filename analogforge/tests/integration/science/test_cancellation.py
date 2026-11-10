# ruff: noqa: E501, S603, S607, S101
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
