# ruff: noqa: E501, E402, S603, S607, S101
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


# --------------------------------------------------------------------------- the practice flow
from support.practice import (  # noqa: E402
    Flow,  # noqa: E402
    candidate_ref,
    characterize_mars,
    make_practice_context,
    prove,
    screen,
    service,
)


def _flow(tmp: Path) -> tuple[Flow, object, list[ScienceComputationResult]]:
    from support import builders

    builders._counter["n"] = 0  # same request ids => same registrar-allocated evidence UUIDs in both runs
    ctx = make_practice_context(tmp)
    flow = Flow(service(), ctx)
    target, _ = characterize_mars(flow)
    sc = screen(flow, target)
    att, _ = prove(flow, sc, catalog.WINDOW_B_CORRIDOR, load_rover("ares-1"), "EXPOSURE_COVERAGE", 1)
    return flow, sc, [*flow.results, *att.results.values()]


def test_practice_flow_is_identical_across_runs_and_directories(tmp_path: Path) -> None:
    _, _, one = _flow(tmp_path / "one")
    _, _, two = _flow(tmp_path / "two" / "deeper")
    assert len(one) == len(two) >= 6
    for a, b in zip(one, two, strict=True):
        assert a.operation == b.operation
        pa = _no_elapsed(json.loads(canonical_json_bytes(a.payload))) if a.payload is not None else None
        pb = _no_elapsed(json.loads(canonical_json_bytes(b.payload))) if b.payload is not None else None
        assert pa == pb, a.operation
        assert [(x.local_key, x.sha256, x.size_bytes) for x in a.artifacts] == [(x.local_key, x.sha256, x.size_bytes) for x in b.artifacts], a.operation
        assert a.parameters_sha256 == b.parameters_sha256 and a.input_sha256 != "" and a.status == b.status
        assert [e.parameters_sha256 for e in a.evidence_drafts] == [e.parameters_sha256 for e in b.evidence_drafts]
    # the analysis grid in particular is byte-identical
    grids = [x.sha256 for r in one for x in r.artifacts if x.role.value == "ANALYSIS_GRID"]
    assert grids and grids == [x.sha256 for r in two for x in r.artifacts if x.role.value == "ANALYSIS_GRID"]


def test_seed_changes_the_hashes_but_not_the_science(tmp_path: Path) -> None:
    from support.builders import make_request

    from analogforge.ports.science import ScienceOptions

    flow, sc, _ = _flow(tmp_path)
    from support.practice import local

    from analogforge.ports.science_payloads import AnalyzeCandidateInput

    inp = AnalyzeCandidateInput(candidate=candidate_ref(sc, catalog.WINDOW_B_CORRIDOR), source=local("practice-earth-grid-v1"), measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH)  # type: ignore[arg-type]
    r0 = flow.svc.execute(make_request(inp, datasets=["practice-earth-grid-v1"]), flow.ctx)
    r1 = flow.svc.execute(make_request(inp, datasets=["practice-earth-grid-v1"], options=ScienceOptions(seed=7)), flow.ctx)
    assert r0.parameters_sha256 != r1.parameters_sha256
    assert _no_elapsed(json.loads(canonical_json_bytes(r0.payload))) == _no_elapsed(json.loads(canonical_json_bytes(r1.payload)))
