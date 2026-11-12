"""Mode gates exercise real runtime selection without a silent live fallback."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from analogforge.agents.runtime.provider import ProviderError, ReplayProvider
from analogforge.agents.runtime.scripted_provider import ScriptedProvider
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import LocalScienceContext, ScienceOperation, ScienceRequest, SourcePolicy
from analogforge.ports.science_payloads import ResolveCoverageInput
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.support.factories import science_factory


def test_synthetic_and_replay_contexts_never_construct_network_client(tmp_path, monkeypatch):
    import socket

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("Network construction forbidden in offline runtime")

    monkeypatch.setattr(socket, "socket", forbidden)
    service = science_factory()
    assert service.supported_operations() == frozenset(ScienceOperation)
    target = {
        "body": "MARS",
        "bbox": [137, -5, 138, -4],
        "longitude_convention": "NEG180_180",
        "latitude_type": "PLANETOCENTRIC",
        "crs_wkt": None,
        "vertical_datum": "TEST_REFERENCE",
    }
    for mode in ("synthetic", "replay"):
        context = LocalScienceContext(tmp_path / mode, uuid4(), uuid4(), mode=mode)
        assert context.http_client() is None
        request = ScienceRequest(
            request_id=uuid4(),
            operation=ScienceOperation.RESOLVE_COVERAGE,
            mode=mode,
            inputs=ResolveCoverageInput(
                subject_kind="TARGET", aoi=target, adapter_id="synthetic_practice", measurement_kinds=["TERRAIN"]
            ),
            source_policy=SourcePolicy(policy_id="p", policy_sha256=canonical_sha256({}), allow_network=False),
        )
        result = service.execute(request, context)
        assert result.mode == mode
        assert result.input_sha256 == canonical_sha256(request)
        with pytest.raises(ValidationError):
            ScienceRequest.model_validate(
                {
                    **request.model_dump(mode="json"),
                    "source_policy": {**request.source_policy.model_dump(mode="json"), "allow_network": True},
                }
            )
    assert calls == []


def test_scripted_provider_refuses_live_and_replay_requires_recording():
    task, context, registry, _, _ = task_and_context()
    with pytest.raises(ProviderError, match="cannot run in live"):
        ScriptedProvider().run(task, registry, context)
    with pytest.raises(ProviderError) as failure:
        ReplayProvider({}).run(task, registry, context)
    assert failure.value.code == "REPLAY_INTEGRITY_ERROR"


def test_all_fifteen_science_operations_deny_sockets_in_offline_modes(tmp_path, monkeypatch):
    import json
    import socket
    from pathlib import Path

    from analogforge.ports import catalog
    from analogforge.ports import science_payloads as p
    from analogforge.ports.domain_models import MissionTestContract, RoverProfile, SolverConfig
    from analogforge.ports.science import ScienceComputationResult

    root = Path(__file__).resolve().parents[3]
    mission = MissionTestContract.model_validate(
        json.loads((root / "tests/fixtures/kit/blueprint-mission-contract.json").read_text())
    )
    rover = RoverProfile.model_validate(
        json.loads((root / "tests/fixtures/kit/blueprint-rover-profile.json").read_text())
    )
    graph = json.loads((root / "tests/fixtures/kit/canonical-graph-v1.json").read_text())
    aoi = {
        "body": "EARTH",
        "bbox": [-111, 35, -110.9, 35.1],
        "longitude_convention": "NEG180_180",
        "latitude_type": "GEODETIC",
        "crs_wkt": "EPSG:4326",
        "vertical_datum": "SYNTHETIC_ELLIPSOID",
    }
    candidate = p.CandidateRef(
        window_id=catalog.GRAPH_WINDOW_ID,
        name="Practice graph-zone-1",
        aoi=aoi,
        origin="SYNTHETIC_CONTROL",
        novelty_status="NOT_ASSESSED",
        discovery_method="synthetic-graph",
    )
    source = p.SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id=catalog.FIXTURE_CANONICAL_GRAPH)
    constraints = p.ConstraintsArtifact(
        artifact_kind="SYNTHETIC_GRAPH_REGRESSION",
        mode="synthetic",
        resource_provider="TEST_ONLY_MOCK_GRAPH",
        mission_revision_id=mission.id,
        mission_content_sha256=mission.content_sha256,
        rover_revision_id=rover.id,
        rover_content_sha256=rover.content_sha256,
        candidate_window_id=candidate.window_id,
        test_revision=1,
        strategy="WAYPOINT_RETURN",
        graph=p.GraphSpec(nodes=graph["nodes"], edges=graph["edges"]),
        start=p.Waypoint(node_id="S"),
        return_required=True,
        tasks=[],
        surface_slope_cap_deg=18,
        exposures=[],
        max_distance_m=400,
        energy=p.EnergySpec(
            model=rover.energy_model,
            battery_wh=rover.battery_wh,
            min_reserve_pct=rover.min_reserve_pct,
            rover_mass_kg=rover.mass_kg,
            nominal_speed_mps=rover.nominal_speed_mps,
        ),
        solver=SolverConfig(max_expansions=1000, max_seconds=10, max_labels_per_node=32, seed=0),
    )
    route = p.RouteArtifact(
        route_key="provided-fixture",
        mode="synthetic",
        constraints_sha256=canonical_sha256(constraints),
        strategy="WAYPOINT_RETURN",
        graph_revision="canonical-graph-v1",
        node_sequence=list(catalog.GRAPH_SUPPLIED_ROUTE_FAIL),
        solver_claimed=p.SolverClaimedTotals(distance_m=120, energy_conservative_wh=26, unique_exposure_m={}),
    )
    dataset = {
        "dataset_id": "socket-test-terrain",
        "title": "Socket test source",
        "provider": "SYNTHETIC_TEST",
        "is_synthetic": True,
        "body": "EARTH",
        "role": "EARTH_TERRAIN",
        "format": "ASCII_GRID",
        "files": [{"path": "terrain.asc"}],
        "primary_file": "terrain.asc",
        "quantity": "ELEVATION",
        "units": "m",
        "nodata_value": -9999,
        "vertical_reference": "SYNTHETIC_ELLIPSOID",
        "crs": {"epsg": 4326},
        "longitude_convention": "NEG180_180",
        "latitude_type": "GEODETIC",
        "license_note": "Synthetic fixture",
        "citation": "Synthetic fixture",
    }
    dataset_dir = tmp_path / "socket-test-terrain"
    dataset_dir.mkdir()
    (dataset_dir / "terrain.asc").write_text(
        "ncols 3\nnrows 3\nxllcorner -111\nyllcorner 35\ncellsize 0.01\nNODATA_value -9999\n0 0 0\n0 0 0\n0 0 0\n"
    )
    inputs = [
        p.ResolveCoverageInput(
            subject_kind="TARGET", aoi=mission.target, adapter_id="synthetic_practice", measurement_kinds=["TERRAIN"]
        ),
        p.FetchSourceInput(
            selection=p.CoverageSelection(
                selection_key="fixture",
                adapter_id="synthetic_practice",
                product_id="SYNTHETIC_TEST",
                version="1",
                access_state="AVAILABLE",
            ),
            aoi=mission.target,
        ),
        p.IngestLocalDatasetInput(manifest=dataset),
        p.CharacterizeTargetInput(
            target=mission.target,
            source=p.SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id=catalog.FIXTURE_MARS_TARGET),
            measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET,
            requested_dimensions=["TERRAIN"],
        ),
        p.ScreenCandidatesInput(
            search_region_set_id=catalog.SEARCH_REGION_PRACTICE,
            source=source,
            target_metrics=[],
            target_histogram=None,
            requirements=mission.requirements,
            max_detailed=1,
            reference_set_id=catalog.REFERENCE_SET_PRACTICE,
        ),
        p.AnalyzeCandidateInput(candidate=candidate, source=source, measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH),
        p.CompareRequirementInput(
            requirement=mission.requirements[0],
            candidate=candidate,
            target_evidence_ids=[],
            candidate_evidence_ids=[],
            observable_policy_id=catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(
                mission.requirements[0].observable, "unsupported"
            ),
        ),
        p.AssessCompatibilityInput(
            rover=rover, requirements=mission.requirements, candidate=candidate, candidate_evidence_ids=[]
        ),
        p.DesignBenchmarkInput(
            mission=mission,
            rover=rover,
            candidate=candidate,
            analysis_evidence_id=None,
            graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH,
            strategy="WAYPOINT_RETURN",
            test_revision=1,
        ),
        p.SearchRouteInput(constraints=constraints, constraints_sha256=canonical_sha256(constraints)),
        p.VerifyRouteInput(
            constraints=constraints,
            constraints_sha256=canonical_sha256(constraints),
            route=route,
            route_sha256=canonical_sha256(route),
            search_status="FOUND",
        ),
        p.DiagnoseResultInput(
            constraints=constraints,
            search_status="FOUND",
            verification=p.VerificationSummary(outcome="FAIL", failure_category="ROUTE"),
            violations=[],
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        ),
        p.OptimizePortfolioInput(
            requirements=mission.requirements, candidates=[candidate], qualification_rows=[], max_sites=1
        ),
        p.BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[uuid4()], layer_kinds=["SLOPE"]),
        p.AuditEvidenceInput(
            claims=[
                p.ClaimScope(
                    claim_id="context",
                    claim_type="CONTEXT",
                    requirement_id=None,
                    candidate_window_ids=[],
                    evidence_ids=[],
                )
            ],
            check_set=["provenance"],
        ),
    ]
    assert {i.operation for i in inputs} == set(ScienceOperation)

    def denied(*args, **kwargs):
        raise AssertionError("Offline science attempted to open a socket")

    monkeypatch.setattr(socket, "socket", denied)
    service = science_factory()
    executed = []
    for mode in ("synthetic", "replay"):
        for value in inputs:
            context = LocalScienceContext(
                tmp_path / f"{mode}-{value.operation}",
                uuid4(),
                uuid4(),
                mode=mode,
                dataset_roots={"socket-test-terrain": dataset_dir},
            )
            request = ScienceRequest(
                request_id=uuid4(),
                operation=ScienceOperation(value.operation),
                mode=mode,
                inputs=value,
                source_policy=SourcePolicy(
                    policy_id="offline",
                    policy_sha256=canonical_sha256({}),
                    allow_network=False,
                    local_dataset_ids=["socket-test-terrain"],
                    synthetic_fixture_ids=[catalog.FIXTURE_CANONICAL_GRAPH, catalog.FIXTURE_MARS_TARGET],
                ),
            )
            result = service.execute(request, context)
            ScienceComputationResult.model_validate(result.model_dump(mode="json"))
            assert result.request_id == request.request_id and result.input_sha256 == canonical_sha256(request)
            assert context.http_client() is None
            executed.append((mode, value.operation))
    assert len(executed) == 30
