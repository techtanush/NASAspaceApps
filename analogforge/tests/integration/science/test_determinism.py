# ruff: noqa: E501, S603, S607, S101
"""SCN-20: identical requests give identical payload JSON and artifact SHA-256 (elapsed fields excluded)."""

from __future__ import annotations

import json
from pathlib import Path

from support.builders import load_mission, load_rover, make_context, make_request
from support.graph_flow import attempt

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_json_bytes
from analogforge.ports.science import ScienceComputationResult
from analogforge.ports.science_payloads import CandidateRef, DesignBenchmarkInput
from analogforge.science.facade import create_science_service


def _design(strategy: str = "EXPOSURE_COVERAGE") -> DesignBenchmarkInput:
    mission = load_mission("mission-graph-regression")
    return DesignBenchmarkInput(
        mission=mission, rover=load_rover("ares-1"),
        candidate=CandidateRef(
            window_id=catalog.GRAPH_WINDOW_ID, name="g", aoi=mission.target.model_copy(update={"body": "EARTH"}),
            origin="SYNTHETIC_CONTROL", novelty_status="NOT_ASSESSED", discovery_method="fixture",
        ),
        analysis_evidence_id=None, graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH,
        strategy=strategy, test_revision=1,
    )  # type: ignore[arg-type]  # fmt: skip


def stable(result: ScienceComputationResult) -> tuple[bytes, list[str], list[str]]:
    dump = json.loads(canonical_json_bytes(result))
    dump.pop("counters", None)

    def scrub(node: object) -> object:
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items() if k != "elapsed_ms"}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    clean = scrub(dump)
    return (
        json.dumps(clean, sort_keys=True).encode(),
        [a.sha256 for a in result.artifacts if a.role.value != "ROUTE" or True],
        [e.parameters_sha256 for e in result.evidence_drafts],
    )


def test_graph_flow_is_byte_identical_across_runs(tmp_path: Path) -> None:
    svc = create_science_service()
    a = attempt(svc, make_context(tmp_path / "one"), _design())
    b = attempt(svc, make_context(tmp_path / "two"), _design())
    assert a.constraints_sha == b.constraints_sha
    for key in a.results:
        ra, rb = a.results[key], b.results[key]
        pa = canonical_json_bytes(ra.payload) if ra.payload is not None else b""
        pb = canonical_json_bytes(rb.payload) if rb.payload is not None else b""
        # elapsed_ms is a wall-clock field and is excluded from the comparison
        assert json.loads(pa.decode() or "null") is None or _no_elapsed(json.loads(pa)) == _no_elapsed(json.loads(pb))
        assert [x.sha256 for x in ra.artifacts] == [x.sha256 for x in rb.artifacts]
        assert [e.parameters_sha256 for e in ra.evidence_drafts] == [e.parameters_sha256 for e in rb.evidence_drafts]


def _no_elapsed(node: object) -> object:
    if isinstance(node, dict):
        return {k: _no_elapsed(v) for k, v in node.items() if k != "elapsed_ms"}
    if isinstance(node, list):
        return [_no_elapsed(v) for v in node]
    return node


def test_different_inputs_change_hashes(tmp_path: Path) -> None:
    svc = create_science_service()
    a = svc.execute(make_request(_design("WAYPOINT_RETURN")), make_context(tmp_path / "a"))
    b = svc.execute(make_request(_design("EXPOSURE_COVERAGE")), make_context(tmp_path / "b"))
    assert a.parameters_sha256 != b.parameters_sha256
    assert a.artifacts[0].sha256 != b.artifacts[0].sha256
