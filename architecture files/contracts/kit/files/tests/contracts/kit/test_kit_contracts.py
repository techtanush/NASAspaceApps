"""FROZEN CONTRACT KIT FILE - kit self-tests. Every branch runs these unchanged:

    uv run pytest tests/contracts/kit -q

They prove the shared contracts import cleanly, the blueprint fixtures validate, the canonical
hashes reproduce, and the exact regression oracles (graph routes, energy) are internally true.
DO NOT EDIT, SKIP OR XFAIL in any branch.
"""

from __future__ import annotations

import importlib
import json
import math
import sys
import uuid
from collections import Counter
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from analogforge.ports import catalog
from analogforge.ports.assurance_models import ScientificAssuranceArtifact
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.domain_models import (
    MissionTestContract,
    QualificationDimension,
    RoverProfile,
    RunEvent,
)
from analogforge.ports.hashing import MISSION_CONTENT_EXCLUDE, ROVER_CONTENT_EXCLUDE, canonical_sha256, model_sha256
from analogforge.ports.science import (
    ArtifactDraft,
    ComputationStatus,
    EvidenceDraft,
    LocalScienceContext,
    ScienceCancelled,
    ScienceComputationResult,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import ConstraintsArtifact, Histogram, SearchCounters, SearchRoutePayload

APP = Path(__file__).resolve().parents[3]
FIX = APP / "tests/fixtures/kit"
CONTRACTS = APP / "contracts"
ZERO = "0" * 64


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_ports_import_without_platform_or_model_stacks() -> None:
    for module in ["science", "science_payloads", "passport_renderer", "domain_models", "assurance_models",
                   "datasets", "hashing", "catalog", "common"]:
        importlib.import_module(f"analogforge.ports.{module}")
    for forbidden in ["fastapi", "sqlalchemy", "openai", "anthropic", "psycopg"]:
        assert forbidden not in sys.modules, f"ports must not import {forbidden}"


def test_blueprint_examples_validate_as_domain_models() -> None:
    MissionTestContract.model_validate(load("blueprint-mission-contract.json"))
    RoverProfile.model_validate(load("blueprint-rover-profile.json"))
    QualificationDimension.model_validate(load("blueprint-qualification-unknown.json"))
    RunEvent.model_validate(load("blueprint-run-event.json"))
    for name in ["supported-negative", "supported-positive", "limited-unknown", "blocked-claim"]:
        ScientificAssuranceArtifact.model_validate(load(f"blueprint-assurance-{name}.json"))


def test_content_hashes_reproduce_with_kit_hashing() -> None:
    mission = MissionTestContract.model_validate(load("blueprint-mission-contract.json"))
    rover = RoverProfile.model_validate(load("blueprint-rover-profile.json"))
    assert model_sha256(mission, MISSION_CONTENT_EXCLUDE) == mission.content_sha256
    assert model_sha256(rover, ROVER_CONTENT_EXCLUDE) == rover.content_sha256


def test_canonical_hash_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        canonical_sha256({"x": math.nan})
    assert canonical_sha256({"b": 1, "a": 2.0}) == canonical_sha256({"a": 2, "b": 1})


def _openapi_validator(component: str) -> jsonschema.Draft202012Validator:
    api = json.loads((CONTRACTS / "openapi.bundled.json").read_text())
    schema = {"$ref": f"#/components/schemas/{component}", "components": api["components"]}
    return jsonschema.Draft202012Validator(schema)


def test_practice_rovers_and_missions_match_wire_contract() -> None:
    rover_validator = _openapi_validator("RoverInput")
    for name, rel in catalog.PRACTICE_ROVER_FILES.items():
        rover = load(rel)
        assert rover["name"] == name
        assert not list(rover_validator.iter_errors(rover)), rel
    assert load("rovers/practice-lite.json")["max_slope_deg"] == 12
    assert load("rovers/practice-no-energy-model.json")["energy_model"] is None
    assert load("rovers/practice-small-battery.json")["battery_wh"] == 30
    mission_validator = _openapi_validator("MissionContent")
    for rel in ["missions/mission-mars-mobility.json", "missions/mission-moon-gap.json",
                "missions/mission-graph-regression.json"]:
        assert not list(mission_validator.iter_errors(load(rel))), rel


def test_bundled_openapi_is_self_contained() -> None:
    api = json.loads((CONTRACTS / "openapi.bundled.json").read_text())
    text = json.dumps(api)
    assert "domain.schema.json" not in text
    ops = [(p, m) for p, item in api["paths"].items() for m in item if m in {"get", "post", "put", "patch", "delete"}]
    assert len(ops) == 43
    for path, method in ops:
        if method == "post":
            params = api["paths"][path][method].get("parameters", [])
            assert any(p.get("$ref", "").endswith("/IdempotencyKey") for p in params), path


def test_dataset_manifest_semantics() -> None:
    base = {
        "dataset_id": "practice-mars-dem", "title": "t", "provider": "SYNTHETIC_PRACTICE", "is_synthetic": True,
        "body": "MARS", "role": "TARGET_TERRAIN", "format": "GEOTIFF", "files": [{"path": "dem.tif"}],
        "primary_file": "dem.tif", "quantity": "ELEVATION", "units": "m", "vertical_reference": "sphere",
        "crs": {"wkt": "GEOGCS[\"Mars 2000\"]"}, "longitude_convention": "NEG180_180",
        "latitude_type": "PLANETOCENTRIC", "license_note": "synthetic", "citation": "synthetic",
    }
    DatasetManifest.model_validate(base)
    for change in [{"provider": "NASA PDS"}, {"crs": {"epsg": 4326}}, {"role": "EARTH_TERRAIN"},
                   {"files": [{"path": "../x.tif"}], "primary_file": "../x.tif"}, {"quantity": "RADIUS"}]:
        with pytest.raises(ValidationError):
            DatasetManifest.model_validate({**base, **change})


def _policy(network: bool = False) -> dict:
    return {"policy_id": "p", "policy_sha256": ZERO, "allow_network": network}


def test_science_request_consistency() -> None:
    req = {
        "request_id": str(uuid.uuid4()), "operation": "SEARCH_ROUTE", "mode": "synthetic",
        "inputs": {"operation": "VERIFY_ROUTE"}, "source_policy": _policy(),
    }
    with pytest.raises(ValidationError):
        ScienceRequest.model_validate(req)
    with pytest.raises(ValidationError):
        ScienceRequest.model_validate({**req, "inputs": {"operation": "AUDIT_EVIDENCE", "claims": [], "check_set": []},
                                       "operation": "AUDIT_EVIDENCE", "source_policy": _policy(True)})


def test_result_closure_rules() -> None:
    common = dict(request_id=uuid.uuid4(), operation=ScienceOperation.SEARCH_ROUTE, mode="synthetic",
                  algorithm_id="a", algorithm_version="1", parameters_sha256=ZERO, input_sha256=ZERO)
    with pytest.raises(ValidationError):
        ScienceComputationResult(status=ComputationStatus.SUCCEEDED, **common)  # payload missing
    with pytest.raises(ValidationError):
        ScienceComputationResult(status=ComputationStatus.BLOCKED, **common)  # issues missing
    art = ArtifactDraft(local_key="a1", scratch_relpath="x.json", sha256=ZERO, size_bytes=1,
                        media_type="application/json", role="ROUTE")
    ev = EvidenceDraft(local_key="e1", kind="DERIVED", body="EARTH", artifact_key="missing", license_note="x",
                       algorithm_id="a", algorithm_version="1", parameters_sha256=ZERO)
    with pytest.raises(ValidationError):
        ScienceComputationResult(status=ComputationStatus.FAILED, artifacts=[art], evidence_drafts=[ev],
                                 issues=[{"code": "SYSTEM", "message": "x"}], **common)
    with pytest.raises(ValidationError):
        ArtifactDraft(local_key="a", scratch_relpath="../escape", sha256=ZERO, size_bytes=0,
                      media_type="x", role="ROUTE")
    with pytest.raises(ValidationError):
        SearchRoutePayload(search_status="EXHAUSTIVE_INFEASIBLE", route=None, route_artifact_key=None,
                           counters=SearchCounters(expansions=1, labels_created=1, labels_pruned_dominated=0,
                                                   labels_pruned_lossy=3, elapsed_ms=1),
                           termination_reason="x")


def test_constraints_forbid_mock_provider_in_live_mode() -> None:
    raw = {
        "artifact_kind": "SYNTHETIC_GRAPH_REGRESSION", "mode": "live", "resource_provider": "TEST_ONLY_MOCK_GRAPH",
        "mission_revision_id": str(uuid.uuid4()), "mission_content_sha256": ZERO,
        "rover_revision_id": str(uuid.uuid4()), "rover_content_sha256": ZERO, "candidate_window_id": "g",
        "test_revision": 1, "strategy": "WAYPOINT_RETURN",
        "graph": {"nodes": ["S"], "edges": [{"a": "S", "b": "A", "length_m": 1, "surface_slope_deg": 1}]},
        "start": {"node_id": "S"}, "return_required": True, "tasks": [], "surface_slope_cap_deg": 18,
        "exposures": [], "energy": {"model": None, "battery_wh": 1, "min_reserve_pct": 20, "rover_mass_kg": 1,
                                    "nominal_speed_mps": 1},
        "solver": {"max_expansions": 1, "max_seconds": 1, "max_labels_per_node": 1, "seed": 0},
    }
    with pytest.raises(ValidationError):
        ConstraintsArtifact.model_validate(raw)
    ConstraintsArtifact.model_validate({**raw, "mode": "synthetic"})


def test_histogram_shape_rules() -> None:
    Histogram(metric_id="surface_slope_deg", unit="deg", edges=[0, 12, 18, 90], area_fraction=[0.5, 0.25, 0.25],
              valid_area_m2=10, support_scale_m=60)
    with pytest.raises(ValidationError):
        Histogram(metric_id="s", unit="deg", edges=[0, 12], area_fraction=[0.5], valid_area_m2=10, support_scale_m=60)


def _route_totals(graph: dict, route: tuple[str, ...]) -> tuple[float, float, float, bool]:
    edges = {frozenset((e["a"], e["b"])): e for e in graph["edges"]}
    c = graph["constraints"]
    used = Counter(frozenset(p) for p in zip(route, route[1:], strict=False))
    dist = sum(edges[k]["length_m"] * n for k, n in used.items())
    energy = sum(edges[k]["mock_energy_wh"] * n for k, n in used.items())
    energy += sum(cost for task, cost in graph["tasks"].items() if task in route)
    lo, hi = c["slope_band_deg"]
    exposure = sum(edges[k]["length_m"] for k in used if lo <= edges[k]["surface_slope_deg"] <= hi)
    hard = (route[0] == route[-1] == c["start"] and set(c["required_task_ids"]) <= set(route)
            and all(n <= c["max_undirected_edge_traversals"] for n in used.values()) and dist <= c["max_distance_m"])
    return dist, energy, exposure, hard


def test_graph_oracle_is_internally_true() -> None:
    graph = load("canonical-graph-v1.json")
    exp = catalog.GRAPH_EXPECTED
    for key, route in [("supplied_fail", catalog.GRAPH_SUPPLIED_ROUTE_FAIL),
                       ("supplied_pass", catalog.GRAPH_SUPPLIED_ROUTE_PASS),
                       ("search_waypoint_return", catalog.GRAPH_SEARCH_WAYPOINT_RETURN),
                       ("search_exposure_coverage", catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE)]:
        dist, energy, exposure, hard = _route_totals(graph, route)
        assert hard
        assert (dist, energy, exposure) == (exp[key]["distance_m"], exp[key]["energy_wh"], exp[key]["unique_exposure_m"])
    # Brute-force: the declared search results are the minimum-distance routes with the
    # lexicographic tie-break (independent oracle for Ayan's solver tests).
    adj: dict[str, list[str]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["a"], []).append(e["b"])
        adj.setdefault(e["b"], []).append(e["a"])
    found: list[tuple[float, float, tuple[str, ...], float]] = []

    def walk(path: list[str]) -> None:
        if len(path) > 13:
            return
        if len(path) > 1 and path[-1] == "S":
            dist, energy, exposure, hard = _route_totals(graph, tuple(path))
            if hard:
                found.append((dist, energy, tuple(path), exposure))
        for nxt in sorted(adj[path[-1]]):
            walk(path + [nxt])

    walk(["S"])
    hard_only = min(found)
    with_exposure = min(f for f in found if f[3] >= graph["constraints"]["minimum_unique_exposure_m"])
    assert hard_only[2] == catalog.GRAPH_SEARCH_WAYPOINT_RETURN
    assert with_exposure[2] == catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE
    assert 100 * (1800 - 34) / 1800 == pytest.approx(exp["supplied_pass"]["reserve_pct"], abs=1e-12)


def test_energy_oracle_matches_formula() -> None:
    m, g, crr, eta, d, v, idle = 42.0, 9.80665, 0.06, 0.65, 1000.0, 0.5, 35.0
    rolling = 1.0 * crr * m * g * math.cos(0.0) * d / eta / 3600
    idle_wh = idle * (d / v) / 3600
    nominal = rolling + idle_wh
    conservative = nominal * 1.25
    oracle = catalog.ENERGY_ORACLE_FLAT_1000M
    assert rolling == pytest.approx(oracle["rolling_wh"], abs=1e-8)
    assert idle_wh == pytest.approx(oracle["idle_wh"], abs=1e-8)
    assert conservative == pytest.approx(oracle["conservative_wh"], abs=1e-8)
    assert 100 * (1800 - conservative) / 1800 == pytest.approx(oracle["reserve_pct"], abs=1e-8)


def test_local_context_cancellation(tmp_path: Path) -> None:
    ctx = LocalScienceContext(scratch=tmp_path, workspace_id=uuid.uuid4(), job_id=uuid.uuid4())
    ctx.check_cancelled()
    ctx.cancelled = True
    with pytest.raises(ScienceCancelled):
        ctx.check_cancelled()


def test_generated_schema_files_have_not_drifted() -> None:
    from analogforge.ports.science_payloads import RouteArtifact, TelemetryArtifact

    for name, model in [("route-artifact.schema.json", RouteArtifact),
                        ("telemetry-artifact.schema.json", TelemetryArtifact),
                        ("constraints-artifact.schema.json", ConstraintsArtifact),
                        ("dataset-manifest.schema.json", DatasetManifest)]:
        on_disk = json.loads((CONTRACTS / name).read_text())
        on_disk.pop("$comment", None)
        assert on_disk == model.model_json_schema(), name


def test_source_policy_defaults_deny_network() -> None:
    assert SourcePolicy(policy_id="x", policy_sha256=ZERO).allow_network is False
    assert len(catalog.ROLE_KEYS) == 10 and len(set(catalog.ROLE_KEYS)) == 10
    assert len(catalog.TOOL_NAMES) == 21


def test_observable_policy_map_covers_all_practice_requirements() -> None:
    for rel in ["missions/mission-mars-mobility.json", "missions/mission-moon-gap.json",
                "missions/mission-graph-regression.json"]:
        for req in load(rel)["requirements"]:
            assert req["observable"] in catalog.OBSERVABLE_POLICY_BY_OBSERVABLE, (rel, req["observable"])


def test_ui_testid_contract_is_well_formed() -> None:
    doc = json.loads((CONTRACTS / "ui-testids.json").read_text())
    ids = [t["id"] for t in doc["testids"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 60
    for entry in doc["testids"]:
        assert entry["id"] == entry["id"].lower() and " " not in entry["id"]
        assert all(a.startswith("data-") for a in entry["required_attributes"])
    for must in ["mode-badge", "qual-cell", "btn-prove-it", "attempt-row", "export-btn", "assurance-badge",
                 "candidate-list", "unknown-value", "manifest-digest", "file-digest"]:
        assert must in ids


def test_practice_missions_contain_required_gap_and_unknown_rows() -> None:
    mars = {r["id"]: r for r in load("missions/mission-mars-mobility.json")["requirements"]}
    assert mars["R-GRAVITY"]["operator"] == "NOT_NATURALLY_REPRODUCIBLE"
    assert mars["R-CLEARANCE"]["evidence_scope"] == "field_validation"
    assert mars["R-EXPOSURE"]["parameters"]["co_location_group"] == "campaign-A"
    assert mars["R-TARGET-SLOPE-CONTEXT"]["minimum_support_scale_m"] == 480
    moon = {r["id"] for r in load("missions/mission-moon-gap.json")["requirements"]}
    assert {"R-THERMAL", "R-GRAVITY", "R-VACUUM"} <= moon


def test_algorithm_ids_cover_payload_bearing_operations() -> None:
    ops = {op.value for op in ScienceOperation}
    for needed in ["CHARACTERIZE_TARGET", "SCREEN_CANDIDATES", "ANALYZE_CANDIDATE", "COMPARE_REQUIREMENT",
                   "ASSESS_COMPATIBILITY", "DESIGN_BENCHMARK", "SEARCH_ROUTE", "VERIFY_ROUTE", "DIAGNOSE_RESULT",
                   "OPTIMIZE_PORTFOLIO", "AUDIT_EVIDENCE"]:
        assert needed in ops and needed in catalog.ALGORITHM_IDS
    assert len(set(catalog.ALGORITHM_IDS.values())) == len(catalog.ALGORITHM_IDS)
    assert catalog.ALGORITHM_ID_SCREENING == "screen-candidates"
