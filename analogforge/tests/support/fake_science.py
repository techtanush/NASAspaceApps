"""Typed, deterministic TEST DOUBLE for the platform/science seam.

These canned practice measurements are not a scientific implementation. No production
module imports this file. All fifteen operations use the frozen request/result models,
write actual scratch bytes, and carry synthetic provenance. The real facade replaces
this object unchanged through AF_SCIENCE_IMPL=real during merge validation.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import numpy as np

from analogforge.ports import catalog
from analogforge.ports import science_payloads as p
from analogforge.ports.common import EvidenceRef, ScienceIssue
from analogforge.ports.domain_models import AreaOfInterest, MeasuredMetric, RequiredExposure, SolverConfig
from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes, canonical_sha256
from analogforge.ports.science import (
    ArtifactDraft,
    ComputationStatus,
    EvidenceDraft,
    ScienceComputationResult,
    ScienceContext,
    ScienceOperation,
    ScienceRequest,
)

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "kit"
_SCIENCE_GATES = tuple(f"SC-{n:02}" for n in range(2, 12)) + ("SC-13",)
_FRACTIONS = {
    catalog.WINDOW_B_CORRIDOR: 0.10,
    catalog.WINDOW_A_MESA: 0.35,
    catalog.WINDOW_C_FLAT: 0.0,
    catalog.WINDOW_ROLLING_1: 0.03,
    catalog.WINDOW_ROLLING_2: 0.02,
    catalog.WINDOW_GENTLE: 0.005,
    catalog.WINDOW_KNOWN_REFERENCE: 0.08,
    catalog.GRAPH_WINDOW_ID: 0.5,
}
_ORDER = [
    catalog.WINDOW_A_MESA,
    catalog.WINDOW_B_CORRIDOR,
    catalog.WINDOW_KNOWN_REFERENCE,
    catalog.WINDOW_ROLLING_1,
    catalog.WINDOW_ROLLING_2,
    catalog.WINDOW_GENTLE,
    catalog.WINDOW_C_FLAT,
]


def metric(name: str, value: float | None, unit: str, scale: float = 60.0) -> MeasuredMetric:
    return MeasuredMetric(
        metric_id=name,
        value=value,
        unit=unit,
        support_scale_m=scale,
        quantity_kind="DERIVED",
        method_id="TEST_DOUBLE",
        valid_fraction=1,
        uncertainty_note="Unquantified synthetic test-double uncertainty; not NASA data",
    )


def gates(evidence_id: Any = None) -> list[p.GateEvidence]:
    refs = [EvidenceRef(evidence_id=evidence_id)] if evidence_id else []
    return [
        p.GateEvidence(gate_id=gate_id, outcome="SATISFIED", reason="Synthetic seam fixture check", evidence=refs)
        for gate_id in _SCIENCE_GATES
    ]


def _aoi(index: int = 0) -> AreaOfInterest:
    return AreaOfInterest(
        body="EARTH",
        bbox=[-111 + index * 0.01, 35, -110.99 + index * 0.01, 35.01],
        longitude_convention="NEG180_180",
        latitude_type="GEODETIC",
        crs_wkt="EPSG:4326",
        vertical_datum="SYNTHETIC_ELLIPSOID",
    )


def _hist(support: float = 480.0) -> p.Histogram:
    return p.Histogram(
        metric_id="surface_slope_deg",
        unit="deg",
        edges=[0, 2, 5, 8, 12, 15, 18, 25, 35, 90],
        area_fraction=[0, 0.4, 0.3, 0, 0.2, 0, 0.1, 0, 0],
        valid_area_m2=1_000_000,
        support_scale_m=support,
    )


class FakeScienceService:
    def supported_operations(self) -> frozenset[ScienceOperation]:
        return frozenset(ScienceOperation)

    def execute(self, request: ScienceRequest, context: ScienceContext) -> ScienceComputationResult:
        context.check_cancelled()
        if request.mode != "synthetic":
            return ScienceComputationResult(
                request_id=request.request_id,
                operation=request.operation,
                mode=request.mode,
                status="BLOCKED",
                algorithm_id="test-double",
                algorithm_version="1.0",
                parameters_sha256=canonical_sha256({}),
                input_sha256=canonical_sha256(request),
                issues=[ScienceIssue(code="MODE_MISMATCH", message="Test-double sources are synthetic only")],
            )
        artifacts: list[ArtifactDraft] = []
        evidence: list[EvidenceDraft] = []
        source_body = "EARTH"
        if request.operation == "CHARACTERIZE_TARGET":
            source_body = request.inputs.target.body
        elif request.operation == "RESOLVE_COVERAGE":
            source_body = request.inputs.aoi.body
        elif request.operation == "INGEST_LOCAL_DATASET":
            source_body = request.inputs.manifest.body
        elif request.operation == "FETCH_SOURCE":
            source_body = request.inputs.aoi.body

        def artifact(key: str, data: bytes, role: str = "DERIVED_JSON", media: str = "application/json") -> str:
            path = context.scratch_dir() / f"{key}-{request.request_id}.bin"
            path.write_bytes(data)
            artifacts.append(
                ArtifactDraft(
                    local_key=key,
                    scratch_relpath=path.name,
                    sha256=bytes_sha256(data),
                    size_bytes=len(data),
                    media_type=media,
                    role=role,
                    body=source_body,
                )
            )
            return key

        def ev(
            key: str = "main",
            algorithm: str | None = None,
            artifact_key: str | None = None,
            kind: str = "DERIVED",
            scale: float | None = 60.0,
            parents: list[str] | None = None,
        ) -> EvidenceRef:
            evidence.append(
                EvidenceDraft(
                    local_key=key,
                    kind=kind,
                    body=source_body,
                    artifact_key=artifact_key,
                    artifact_media_type=next((a.media_type for a in artifacts if a.local_key == artifact_key), None),
                    parent_local_keys=parents or [],
                    parent_evidence_ids=[e.evidence_id for e in request.input_evidence],
                    source_uri=None,
                    dataset_product_id="SYNTHETIC_TEST_DOUBLE",
                    dataset_version="1.0",
                    granule_id=key,
                    license_note="Tests-only generated synthetic values",
                    algorithm_id=algorithm or request.operation.lower().replace("_", "-"),
                    algorithm_version="1.0",
                    parameters_sha256=canonical_sha256(request.inputs),
                    native_resolution_m=60.0,
                    comparison_scale_m=scale,
                    metrics=[],
                    limitations=["TEST DOUBLE: canned seam data; not a scientific or NASA-source validation"],
                )
            )
            return EvidenceRef(local_key=key)

        payload = self._payload(request, context, artifact, ev)
        if not evidence:
            ev()
        algorithm = catalog.ALGORITHM_IDS.get(request.operation, request.operation.lower().replace("_", "-"))
        # Every operation's UI summary is backed by genuine canonical payload bytes.
        if request.operation not in {"ANALYZE_CANDIDATE", "DESIGN_BENCHMARK", "SEARCH_ROUTE"}:
            key = artifact("payload", canonical_json_bytes(payload))
            first = evidence[0]
            evidence[0] = first.model_copy(
                update={"artifact_key": key, "artifact_media_type": "application/json", "algorithm_id": algorithm}
            )
        return ScienceComputationResult(
            request_id=request.request_id,
            operation=request.operation,
            mode=request.mode,
            status=ComputationStatus.SUCCEEDED,
            algorithm_id=algorithm,
            algorithm_version="1.0",
            parameters_sha256=canonical_sha256(request.inputs),
            input_sha256=canonical_sha256(request),
            counters={"test_double": 1},
            artifacts=artifacts,
            evidence_drafts=evidence,
            payload=payload,
        )

    def _payload(self, request: ScienceRequest, context: ScienceContext, artifact: Any, ev: Any) -> Any:
        inputs = request.inputs
        op = request.operation
        if op == "RESOLVE_COVERAGE":
            return p.ResolveCoveragePayload(
                selections=[
                    p.CoverageSelection(
                        selection_key="fixture",
                        adapter_id=inputs.adapter_id,
                        product_id="SYNTHETIC_TEST_DOUBLE",
                        version="1",
                        access_state="AVAILABLE",
                        coverage_fraction=1,
                        native_resolution_m=60,
                        granule_ids=["test-fixture"],
                    )
                ]
            )
        if op == "FETCH_SOURCE":
            key = artifact("source", b"SYNTHETIC TEST SOURCE", "SOURCE_BYTES", "application/octet-stream")
            return p.FetchSourcePayload(source_evidence=[ev(artifact_key=key, kind="SOURCE")], acquired_assets=[])
        if op == "INGEST_LOCAL_DATASET":
            return p.IngestLocalDatasetPayload(
                dataset_id=inputs.manifest.dataset_id,
                body=inputs.manifest.body,
                role=inputs.manifest.role,
                usable_for_quantitative_claims=True,
                normalized_evidence=ev(kind="SOURCE"),
                checks=[
                    p.ValidationCheck(check_id="synthetic_fixture", status="PASS", message="Synthetic seam fixture")
                ],
                native_resolution_m=60,
                valid_fraction=1,
                bbox_lonlat=None,
            )
        if op == "CHARACTERIZE_TARGET":
            support = 960.0 if inputs.target.body == "MOON" else 480.0
            return p.CharacterizeTargetPayload(
                profile_evidence=ev(scale=support),
                metrics=[metric("slope_mean_deg", 8.0, "deg", support)],
                slope_histogram=_hist(support),
                comparison_support_m=support,
                unavailable_dimensions=[
                    p.UnavailableDimension(
                        dimension="THERMAL", reason_code="NO_COVERAGE", message="No paired thermal fixture"
                    )
                ],
            )
        if op == "SCREEN_CANDIDATES":
            graph = inputs.source.fixture_id == catalog.FIXTURE_CANONICAL_GRAPH
            order = [catalog.GRAPH_WINDOW_ID] if graph else _ORDER
            shortlist = order[: min(inputs.max_detailed, len(order))]
            if not graph and len(shortlist) >= 6:
                shortlist[-1] = catalog.WINDOW_C_FLAT
            ref = ev(scale=480)
            windows = [
                p.ScreenedWindow(
                    window_id=window,
                    name="Practice " + window,
                    aoi=_aoi(index),
                    origin="KNOWN_CONTROL"
                    if window == catalog.WINDOW_KNOWN_REFERENCE
                    else ("SYNTHETIC_CONTROL" if window == catalog.WINDOW_C_FLAT else "DISCOVERED"),
                    novelty_status="KNOWN_ANALOG"
                    if window == catalog.WINDOW_KNOWN_REFERENCE
                    else "NOT_IN_REFERENCE_LIST",
                    rank=index + 1,
                    excluded=False,
                    feature_scores={"availability_deficit": max(0.0, 0.05 - _FRACTIONS[window])},
                    is_negative_control=window == catalog.WINDOW_C_FLAT,
                    evidence=ref,
                )
                for index, window in enumerate(order)
            ]
            if not graph:
                windows += [
                    p.ScreenedWindow(
                        window_id=window,
                        name="Practice " + window,
                        aoi=_aoi(8),
                        origin="DISCOVERED",
                        novelty_status="NOT_IN_REFERENCE_LIST",
                        excluded=True,
                        feature_scores={},
                        exclusion_reason=reason,
                    )
                    for window, reason in [
                        (catalog.WINDOW_WATER, "WATER_ONLY"),
                        (catalog.WINDOW_NODATA_STRIPE, "INSUFFICIENT_VALID_DATA"),
                    ]
                ]
            return p.ScreenCandidatesPayload(
                screened_count=len(windows),
                windows=windows,
                shortlist_window_ids=shortlist,
                stop_reason="GRID_EXHAUSTED",
                search_extent=_aoi(),
                limitations=["Synthetic bounded practice grid"],
            )
        if op == "ANALYZE_CANDIDATE":
            buffer = io.BytesIO()
            np.savez(buffer, elevation=np.zeros((4, 4)), slope=np.zeros((4, 4)), valid=np.ones((4, 4), dtype=bool))
            grid_key = artifact("grid", buffer.getvalue(), "ANALYSIS_GRID", "application/x-npz")
            ref = ev(artifact_key=grid_key, algorithm="analyze-candidate")
            window = inputs.candidate.window_id
            payload = p.AnalyzeCandidatePayload(
                analysis_evidence=ref,
                analysis_grid_artifact_key=grid_key,
                metrics=[metric("slope_band_area_fraction", _FRACTIONS.get(window, 0.1), "fraction")],
                slope_histogram=_hist(60),
                connected_zones=[
                    p.ConnectedZone(
                        zone_id="start",
                        area_m2=1e6,
                        band_area_m2={"12-18": 1e5 if window == catalog.WINDOW_B_CORRIDOR else 0},
                        contains_start=True,
                    )
                ],
                coverage_fraction=1,
                limitations=["Canned synthetic candidate analysis"],
            )
            ev(
                key="summary",
                algorithm="analysis-summary",
                artifact_key=artifact("summary-json", canonical_json_bytes(payload)),
                parents=["main"],
            )
            return payload
        if op == "COMPARE_REQUIREMENT":
            req = inputs.requirement
            status, reason, value, stage = "UNKNOWN", "REQUIREMENT_UNDERSPECIFIED", None, "FINAL"
            if req.observable == "slope_band_area_fraction":
                value = _FRACTIONS.get(inputs.candidate.window_id, 0.1)
                status = "PASS" if value >= (req.lower or 0) else "FAIL"
                reason = "MEETS_CRITERION" if status == "PASS" else "INSUFFICIENT_EXPOSURE"
            elif req.observable == "slope_distribution_w1_deg":
                value, status, reason = 2.0, "PASS" if (req.upper or 0) >= 2 else "FAIL", "MEETS_CRITERION"
            elif req.observable in catalog.ROUTE_DEPENDENT_OBSERVABLES:
                if inputs.verification is None:
                    reason, stage = "ROUTE_NOT_VERIFIED", "PRELIMINARY"
                else:
                    names = {
                        "unique_slope_exposure_m": f"unique_exposure_m:{req.id}",
                        "completed_task_count": "completed_task_count",
                        "final_battery_reserve_pct": "reserve_pct",
                    }
                    value = next(
                        (m.value for m in inputs.verification.metrics if m.metric_id == names[req.observable]), None
                    )
                    if value is not None:
                        status = "PASS" if value >= (req.lower or 0) else "FAIL"
                        reason = "ROUTE_VERIFIED" if status == "PASS" else "ROUTE_FAILED"
                    else:
                        reason = (
                            "ENERGY_MODEL_MISSING" if req.observable == "final_battery_reserve_pct" else "ROUTE_FAILED"
                        )
            elif req.observable in {"planetary_gravity", "planetary_atmosphere"}:
                status, reason = "GAP", "PHYSICAL_GAP"
            elif req.observable == "ground_clearance_m":
                reason = "SCALE_UNSUPPORTED"
            elif req.observable in {"mineral_class_present", "surface_temperature_min_k"}:
                reason = "EARTH_EVIDENCE_MISSING"
                if (
                    req.observable == "mineral_class_present"
                    and "practice-earth-minerals-v1" in request.source_policy.local_dataset_ids
                ):
                    reason = "TARGET_EVIDENCE_MISSING"
            ref = ev(scale=480 if req.observable == "slope_distribution_w1_deg" else 60)
            return p.CompareRequirementPayload(
                requirement_id=req.id,
                proposed_status=status,
                reason_code=reason,
                evaluation_stage=stage,
                confidence="MEDIUM" if status in {"PASS", "FAIL"} else "UNASSESSED",
                comparison_scale_m=480 if req.observable == "slope_distribution_w1_deg" else 60,
                measured_value=value,
                measured_unit=req.unit,
                threshold_lower=req.lower,
                threshold_upper=req.upper,
                explanation=f"Synthetic seam fixture: {reason}",
                limitations=["Unquantified nominal-model uncertainty"],
                comparison_evidence=ref,
                adequacy=p.AdequacyReceipt(
                    observable_policy_id=inputs.observable_policy_id,
                    policy_sha256=canonical_sha256({"policy": inputs.observable_policy_id}),
                    gates=gates(),
                    validation_level="S1",
                ),
            )
        if op == "ASSESS_COMPATIBILITY":
            reserve = (
                next((value.value for value in inputs.verification.metrics if value.metric_id == "reserve_pct"), None)
                if inputs.verification
                else None
            )
            return p.AssessCompatibilityPayload(
                preliminary=inputs.verification is None,
                dimensions=[
                    p.CompatibilityDimension(
                        metric_id="max_surface_slope_deg",
                        status="PASS" if inputs.rover.max_slope_deg >= 18 else "FAIL",
                        rover_value=inputs.rover.max_slope_deg,
                        required_value=18,
                        unit="deg",
                        explanation="Declared capability, not observed performance",
                    ),
                    p.CompatibilityDimension(
                        metric_id="ground_clearance_m",
                        status="UNKNOWN",
                        rover_value=inputs.rover.ground_clearance_m,
                        required_value=None,
                        unit="m",
                        explanation="60 m practice terrain does not resolve physical obstacle clearance",
                    ),
                    p.CompatibilityDimension(
                        metric_id="energy_reserve_pct",
                        status="UNKNOWN"
                        if reserve is None
                        else ("PASS" if reserve >= inputs.rover.min_reserve_pct else "FAIL"),
                        rover_value=reserve,
                        required_value=inputs.rover.min_reserve_pct,
                        unit="percent",
                        explanation="Route-specific nominal modeled reserve; no value before independent verification",
                    ),
                    p.CompatibilityDimension(
                        metric_id="obstacle_height",
                        status="UNKNOWN",
                        rover_value=inputs.rover.max_obstacle_height_m,
                        required_value=None,
                        unit="m",
                        explanation="No resolved physical obstacle survey",
                    ),
                    p.CompatibilityDimension(
                        metric_id="required_capability",
                        status="PASS" if "geological_sampling" in inputs.rover.capabilities else "FAIL",
                        rover_value=None,
                        required_value=None,
                        unit=None,
                        explanation="Geological sampling capability is declared, not observed",
                    ),
                ],
                compatibility_evidence=ev(),
            )
        if op == "DESIGN_BENCHMARK":
            graph = json.loads((_FIXTURES / "canonical-graph-v1.json").read_text())
            is_graph = inputs.graph_fixture_id is not None
            exposures = [
                p.ExposureSpec(
                    requirement_id=r.id,
                    metric_id="surface_slope_deg",
                    band_deg=r.parameters.slope_band_deg or (12, 18),
                    upper_inclusive=False,
                    minimum_distance_m=r.lower or 0,
                    counting="UNIQUE_UNDIRECTED_EDGE_DISTANCE",
                )
                for r in inputs.mission.requirements
                if r.observable == "unique_slope_exposure_m"
            ]
            constraints = p.ConstraintsArtifact(
                artifact_kind="SYNTHETIC_GRAPH_REGRESSION" if is_graph else "RASTER_ROUTE_TEST",
                mode=request.mode,
                resource_provider="TEST_ONLY_MOCK_GRAPH" if is_graph else "PHYSICAL_EARTH_MODEL",
                mission_revision_id=inputs.mission.id,
                mission_content_sha256=inputs.mission.content_sha256,
                rover_revision_id=inputs.rover.id,
                rover_content_sha256=inputs.rover.content_sha256,
                candidate_window_id=inputs.candidate.window_id,
                test_revision=inputs.test_revision,
                strategy=inputs.strategy,
                graph=p.GraphSpec(nodes=graph["nodes"], edges=graph["edges"]) if is_graph else None,
                grid=None
                if is_graph
                else p.GridSpec(
                    analysis_evidence_id=inputs.analysis_evidence_id,
                    analysis_grid_sha256="0" * 64,
                    crs_wkt="EPSG:32612",
                    cell_size_m=60,
                    width=64,
                    height=64,
                ),
                start=p.Waypoint(node_id="S"),
                return_required=True,
                tasks=[
                    p.TaskSpec(
                        task_id=name,
                        requirement_ids=[
                            r.id for r in inputs.mission.requirements if r.observable == "completed_task_count"
                        ],
                        kind="SAMPLING",
                        location=p.Waypoint(node_id=name),
                        tolerance_m=0,
                        dwell_s=60,
                        incremental_energy_wh=10,
                        required_capability="geological_sampling",
                        evidence_origin="SYNTHETIC_FIXTURE",
                    )
                    for name in ["W1", "W2"]
                ],
                surface_slope_cap_deg=inputs.rover.max_slope_deg,
                exposures=exposures,
                max_distance_m=inputs.rover.max_route_m or 8000,
                energy=p.EnergySpec(
                    model=inputs.rover.energy_model,
                    battery_wh=inputs.rover.battery_wh,
                    min_reserve_pct=inputs.rover.min_reserve_pct,
                    rover_mass_kg=inputs.rover.mass_kg,
                    nominal_speed_mps=inputs.rover.nominal_speed_mps,
                ),
                solver=SolverConfig(
                    max_expansions=request.options.max_expansions or 200000,
                    max_seconds=30,
                    max_labels_per_node=32,
                    seed=0,
                ),
                limitations=["Synthetic seam fixture; unquantified model uncertainty"],
            )
            key = artifact("constraints", canonical_json_bytes(constraints), "CONSTRAINTS")
            ev(artifact_key=key)
            return p.DesignBenchmarkPayload(
                constraints=constraints,
                constraints_artifact_key=key,
                constraints_sha256=canonical_sha256(constraints),
                required_exposures=[
                    RequiredExposure(
                        requirement_id=e.requirement_id,
                        metric_id=e.metric_id,
                        lower=e.band_deg[0],
                        upper=e.band_deg[1],
                        minimum_distance_m=e.minimum_distance_m,
                    )
                    for e in exposures
                ],
                requirement_mapping=[
                    p.ConstraintMapping(
                        requirement_id=r.id,
                        constraint_ids=[catalog.constraint_exposure(r.id)],
                        treatment="VERIFIED_BY_TOOL",
                    )
                    for r in inputs.mission.requirements
                ],
            )
        if op == "SEARCH_ROUTE":
            c = inputs.constraints
            graph = c.artifact_kind == "SYNTHETIC_GRAPH_REGRESSION"
            status = "FOUND"
            if (request.options.max_expansions or c.solver.max_expansions) == 1:
                status = "BUDGET_EXHAUSTED"
            elif c.energy.battery_wh < 100 or any(
                e.minimum_distance_m > (c.max_distance_m or 8000) for e in c.exposures
            ):
                status = "EXHAUSTIVE_INFEASIBLE"
            elif (
                c.strategy != "WAYPOINT_RETURN"
                and not graph
                and (
                    c.candidate_window_id in {catalog.WINDOW_A_MESA, catalog.WINDOW_KNOWN_REFERENCE}
                    or c.surface_slope_cap_deg < 15
                )
            ):
                status = "EXHAUSTIVE_INFEASIBLE"
            counters = p.SearchCounters(
                expansions=1 if status == "BUDGET_EXHAUSTED" else 20,
                labels_created=20,
                labels_pruned_dominated=0,
                labels_pruned_lossy=0,
                elapsed_ms=0,
            )
            if status != "FOUND":
                ev()
                return p.SearchRoutePayload(
                    search_status=status,
                    route=None,
                    route_artifact_key=None,
                    counters=counters,
                    optimistic_exposure_bound_m={e.requirement_id: 0 for e in c.exposures},
                    termination_reason="Synthetic fixture bound",
                )
            sequence = list(
                catalog.GRAPH_SEARCH_WAYPOINT_RETURN
                if c.strategy == "WAYPOINT_RETURN"
                else catalog.GRAPH_SEARCH_EXPOSURE_COVERAGE
            )
            route = p.RouteArtifact(
                route_key="test-route",
                mode=request.mode,
                constraints_sha256=inputs.constraints_sha256,
                strategy=c.strategy,
                graph_revision="TEST_DOUBLE",
                node_sequence=sequence,
                task_events=[
                    p.TaskEvent(task_id=name, node_id=name, arrival_distance_m=0, dwell_s=60) for name in ["W1", "W2"]
                ],
                solver_claimed=p.SolverClaimedTotals(
                    distance_m=120 if c.strategy == "WAYPOINT_RETURN" else 230,
                    energy_conservative_wh=26 if c.strategy == "WAYPOINT_RETURN" else 30,
                    unique_exposure_m={
                        e.requirement_id: 0 if c.strategy == "WAYPOINT_RETURN" else 150 for e in c.exposures
                    },
                ),
            )
            key = artifact("route", canonical_json_bytes(route), "ROUTE")
            ev(artifact_key=key)
            return p.SearchRoutePayload(
                search_status="FOUND",
                route=route,
                route_artifact_key=key,
                route_sha256=canonical_sha256(route),
                counters=counters,
                termination_reason="Synthetic fixture route",
            )
        if op == "VERIFY_ROUTE":
            c, route = inputs.constraints, inputs.route
            initial = route.strategy == "WAYPOINT_RETURN"
            distance, energy, exposure = (120.0, 26.0, 0.0) if initial else (230.0, 30.0, 150.0)
            if tuple(route.node_sequence) == catalog.GRAPH_SUPPLIED_ROUTE_PASS:
                distance, energy = 340.0, 34.0
            missing_energy = c.energy.model is None
            violations = [
                p.RouteViolation(
                    code="EXPOSURE_SHORTFALL",
                    requirement_id=e.requirement_id,
                    constraint_id=catalog.constraint_exposure(e.requirement_id),
                    observed=exposure,
                    threshold=e.minimum_distance_m,
                    unit="m",
                    message="Synthetic route does not meet unique exposure",
                )
                for e in c.exposures
                if exposure < e.minimum_distance_m
            ]
            outcome = "FAIL" if violations else ("INCONCLUSIVE" if missing_energy else "PASS")
            category = "ROUTE" if violations else ("DATA" if missing_energy else None)
            values = [
                metric("route_distance_m", distance, "m"),
                metric("energy_conservative_wh", None if missing_energy else energy, "Wh"),
                metric("reserve_pct", None if missing_energy else 100 * (1 - energy / c.energy.battery_wh), "%"),
                metric("completed_task_count", 2.0, "count"),
            ] + [metric(f"unique_exposure_m:{e.requirement_id}", exposure, "m") for e in c.exposures]
            telemetry = p.TelemetryArtifact(
                route_sha256=inputs.route_sha256,
                constraints_sha256=inputs.constraints_sha256,
                samples=[p.TelemetrySample(index=0, node_id="S", cumulative_distance_m=0, elapsed_s=0)],
            )
            telemetry_key = artifact("telemetry", canonical_json_bytes(telemetry), "TELEMETRY")
            ref = ev(kind="VERIFICATION")
            ev(key="telemetry-evidence", algorithm="route-telemetry", artifact_key=telemetry_key, parents=["main"])
            rows = [
                p.BenchmarkRow(
                    constraint_id=catalog.constraint_exposure(e.requirement_id),
                    requirement_id=e.requirement_id,
                    rule="unique exposure meets accepted minimum",
                    measured=exposure,
                    threshold=e.minimum_distance_m,
                    unit="m",
                    margin=exposure - e.minimum_distance_m,
                    status="PASS" if exposure >= e.minimum_distance_m else "FAIL",
                )
                for e in c.exposures
            ]
            return p.VerifyRoutePayload(
                outcome=outcome,
                failure_category=category,
                search_status=inputs.search_status,
                verified_route_sha256=inputs.route_sha256,
                metrics=values,
                violations=violations,
                benchmark_rows=rows
                or [
                    p.BenchmarkRow(
                        constraint_id="C-RETURN",
                        requirement_id=None,
                        rule="Return to start",
                        measured=1,
                        threshold=1,
                        unit="bool",
                        margin=0,
                        status="PASS",
                    )
                ],
                telemetry_artifact_key=telemetry_key,
                verification_evidence=ref,
                limitations=["ENERGY_UNCALIBRATED"]
                if missing_energy
                else ["Synthetic nominal model; unquantified uncertainty"],
            )
        if op == "DIAGNOSE_RESULT":
            c = inputs.constraints
            if inputs.search_status == "BUDGET_EXHAUSTED":
                category, repair = "SEARCH_LIMIT", None
            elif inputs.search_status == "EXHAUSTIVE_INFEASIBLE":
                category = "ROVER" if c.surface_slope_cap_deg < 15 or c.energy.battery_wh < 100 else "ANALOG"
                repair = "NEW_CONTRACT_REQUIRED" if category == "ROVER" else "NEW_CANDIDATE"
            elif inputs.verification.failure_category == "DATA":
                category, repair = "DATA", "DATA_REPAIR"
            else:
                category, repair = inputs.verification.failure_category, "NEW_ROUTE"
            return p.DiagnoseResultPayload(
                primary_category=category,
                violated_constraint_ids=[v.constraint_id for v in inputs.violations],
                permitted_repairs=[repair] if repair else [],
                recommended_repair=repair,
                recommended_strategy="EXPOSURE_COVERAGE" if repair in {"NEW_ROUTE", "NEW_CANDIDATE"} else None,
                proof_scope="Synthetic bounded fixture model",
                explanation=f"Synthetic diagnosis: {category}",
                diagnosis_evidence=ev(),
            )
        if op == "OPTIMIZE_PORTFOLIO":
            # Deliberately simple seam fixture, not the production optimizer.
            selected = sorted({r.candidate_window_id for r in inputs.qualification_rows if r.status == "PASS"})[
                : inputs.max_sites
            ]
            assignments = [
                p.PortfolioAssignment(
                    requirement_id=req.id,
                    window_ids=[
                        r.candidate_window_id
                        for r in inputs.qualification_rows
                        if r.requirement_id == req.id and r.candidate_window_id in selected and r.status == "PASS"
                    ],
                    coverage="GAP" if req.operator == "NOT_NATURALLY_REPRODUCIBLE" else "UNKNOWN",
                )
                for req in inputs.requirements
            ]
            return p.OptimizePortfolioPayload(
                selected_window_ids=selected,
                assignments=assignments,
                objective_value=0,
                lexicographic_objective=[0],
                residual_requirement_ids=[r.id for r in inputs.requirements],
                limitations=["TEST DOUBLE: not optimizer validation"],
                portfolio_evidence=ev(),
            )
        if op == "BUILD_DISPLAY_LAYERS":
            # Valid 1x1 transparent PNG, no fabricated geographic image.
            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
            key = artifact("display", png, "DISPLAY_IMAGE", "image/png")
            body = next((e.body for e in request.input_evidence if e.evidence_id in inputs.evidence_ids), "EARTH")
            return p.BuildDisplayLayersPayload(
                layers=[
                    p.DisplayLayerDraft(
                        local_key="slope",
                        body=body,
                        layer_kind="SLOPE",
                        rendering="EARTH_WEBMERCATOR_IMAGE" if body == "EARTH" else "PLANETARY_PLANAR_IMAGE",
                        image_artifact_key=key,
                        display_crs_wkt="EPSG:3857" if body == "EARTH" else "SYNTHETIC_PLANAR",
                        pixel_to_world=(0, 1, 0, 0, 0, -1),
                        width_px=1,
                        height_px=1,
                        earth_corners=[(-111, 35), (-110, 35), (-110, 34), (-111, 34)] if body == "EARTH" else None,
                        legend=[],
                        unit="deg",
                        support_scale_m=60,
                        source_evidence=[EvidenceRef(evidence_id=e) for e in inputs.evidence_ids],
                        attribution=["Synthetic test double"],
                        limitations=["Transparent test image; not scientific visualization"],
                    )
                ]
            )
        if op == "AUDIT_EVIDENCE":
            ev()
            return p.AuditEvidencePayload(
                claim_gates=[
                    p.ClaimGateEvidence(claim_id=c.claim_id, gates=gates(c.evidence_ids[0] if c.evidence_ids else None))
                    for c in inputs.claims
                ]
            )
        raise AssertionError(f"Unhandled operation: {op}")
