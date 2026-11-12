"""Exercise every frozen operation through the switchable science seam.

The assertions concern result typing, hashing and artifact bytes. Scientific numeric
oracles belong to Ayan's independent science tests, not this platform seam suite.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.ports import science_payloads as p
from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.domain_models import MissionTestContract, RoverProfile
from analogforge.ports.hashing import bytes_sha256, canonical_sha256
from analogforge.ports.science import (
    LocalScienceContext,
    ScienceComputationResult,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from tests.support.factories import science_factory

FIXTURES = Path(__file__).parents[2] / "fixtures" / "kit"


def test_all_fifteen_operation_results_and_scratch_artifacts_are_typed_and_hashed(tmp_path):
    service = science_factory()
    assert service.supported_operations() == frozenset(ScienceOperation)
    mission = MissionTestContract.model_validate_json((FIXTURES / "blueprint-mission-contract.json").read_bytes())
    rover = RoverProfile.model_validate_json((FIXTURES / "blueprint-rover-profile.json").read_bytes())
    source = p.SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id="canonical-graph-v1")
    earth = p.SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id="practice-earth-grid-v1")
    candidate = p.CandidateRef(
        window_id="graph-zone-1",
        name="Practice graph-zone-1",
        aoi={
            "body": "EARTH",
            "bbox": [-111, 35, -110, 36],
            "longitude_convention": "NEG180_180",
            "latitude_type": "GEODETIC",
            "crs_wkt": "EPSG:4326",
            "vertical_datum": "SYNTHETIC_REFERENCE",
        },
        origin="SYNTHETIC_CONTROL",
        novelty_status="NOT_ASSESSED",
        discovery_method="Synthetic graph regression",
    )
    context = LocalScienceContext(tmp_path / "scratch", uuid4(), uuid4())
    seen = set()

    def execute(inputs):
        request = ScienceRequest(
            request_id=uuid4(),
            operation=inputs.operation,
            mode="synthetic",
            inputs=inputs,
            source_policy=SourcePolicy(policy_id="synthetic-policy-v1", policy_sha256="1" * 64),
        )
        result = service.execute(request, context)
        ScienceComputationResult.model_validate_json(result.model_dump_json())
        assert result.request_id == request.request_id
        assert result.operation == request.operation
        assert result.mode == request.mode
        assert result.input_sha256 == canonical_sha256(request)
        for draft in result.artifacts:
            content = (context.scratch_dir() / draft.scratch_relpath).read_bytes()
            assert bytes_sha256(content) == draft.sha256
            assert len(content) == draft.size_bytes
        seen.add(result.operation)
        return result

    coverage = execute(
        p.ResolveCoverageInput(
            subject_kind="TARGET", aoi=mission.target, adapter_id="synthetic_practice", measurement_kinds=["TERRAIN"]
        )
    )
    assert coverage.payload.operation == "RESOLVE_COVERAGE"
    execute(p.FetchSourceInput(selection=coverage.payload.selections[0], aoi=mission.target))
    manifest = DatasetManifest(
        dataset_id="synthetic-earth-test",
        title="Test synthetic terrain",
        provider="SYNTHETIC_TEST",
        is_synthetic=True,
        body="EARTH",
        role="EARTH_TERRAIN",
        format="GEOTIFF",
        files=[{"path": "terrain.tif"}],
        primary_file="terrain.tif",
        quantity="ELEVATION",
        units="m",
        vertical_reference="SYNTHETIC_REFERENCE",
        crs={"epsg": 32612},
        longitude_convention="PROJECTED",
        latitude_type="GEODETIC",
        license_note="Test",
        citation="Test",
    )
    execute(p.IngestLocalDatasetInput(manifest=manifest))
    target = execute(
        p.CharacterizeTargetInput(
            target=mission.target,
            source=p.SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id="practice-mars-target-v1"),
            measurement_spec_id="terrain-target-v1",
            requested_dimensions=["TERRAIN"],
        )
    )
    execute(
        p.ScreenCandidatesInput(
            search_region_set_id="practice-earth-grid-v1",
            source=source,
            target_metrics=target.payload.metrics,
            target_histogram=target.payload.slope_histogram,
            requirements=mission.requirements,
            max_detailed=6,
            reference_set_id="practice-reference-set-v1",
        )
    )
    execute(p.AnalyzeCandidateInput(candidate=candidate, source=earth, measurement_spec_id="terrain-earth-v1"))
    execute(
        p.CompareRequirementInput(
            requirement=mission.requirements[0],
            candidate=candidate,
            target_evidence_ids=[],
            candidate_evidence_ids=[],
            observable_policy_id="route-exposure-v1",
        )
    )
    execute(
        p.AssessCompatibilityInput(
            rover=rover, requirements=mission.requirements, candidate=candidate, candidate_evidence_ids=[]
        )
    )
    designed = execute(
        p.DesignBenchmarkInput(
            mission=mission,
            rover=rover,
            candidate=candidate,
            analysis_evidence_id=None,
            graph_fixture_id="canonical-graph-v1",
            strategy="WAYPOINT_RETURN",
            test_revision=1,
        )
    )
    constraints = designed.payload.constraints
    searched = execute(
        p.SearchRouteInput(constraints=constraints, constraints_sha256=designed.payload.constraints_sha256)
    )
    verified = execute(
        p.VerifyRouteInput(
            constraints=constraints,
            constraints_sha256=designed.payload.constraints_sha256,
            route=searched.payload.route,
            route_sha256=searched.payload.route_sha256,
            search_status="FOUND",
        )
    )
    execute(
        p.DiagnoseResultInput(
            constraints=constraints,
            search_status="FOUND",
            verification=p.VerificationSummary(
                outcome=verified.payload.outcome,
                failure_category=verified.payload.failure_category,
                violation_codes=[v.code for v in verified.payload.violations],
                metrics=verified.payload.metrics,
            ),
            violations=verified.payload.violations,
            attempt_history=[],
            remaining_route_repairs=2,
            remaining_candidate_switches=1,
        )
    )
    execute(
        p.OptimizePortfolioInput(
            requirements=mission.requirements, candidates=[candidate], qualification_rows=[], max_sites=3
        )
    )
    execute(p.BuildDisplayLayersInput(subject="CANDIDATE", evidence_ids=[uuid4()], layer_kinds=["SLOPE"]))
    execute(
        p.AuditEvidenceInput(
            claims=[
                p.ClaimScope(
                    claim_id="test",
                    claim_type="CONTEXT",
                    requirement_id=None,
                    candidate_window_ids=[candidate.window_id],
                    evidence_ids=[],
                )
            ],
            check_set=["provenance"],
        )
    )
    assert seen == frozenset(ScienceOperation)


def test_explicit_real_science_factory_never_substitutes_a_double(monkeypatch):
    monkeypatch.setenv("AF_SCIENCE_IMPL", "real")

    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("tests.support.factories.importlib.import_module", missing)
    with pytest.raises(RuntimeError, match="SCIENCE_FACADE_MISSING"):
        science_factory()


def test_unknown_switch_value_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv("AF_SCIENCE_IMPL", "faker")
    with pytest.raises(ValueError, match="fake or real"):
        science_factory()
