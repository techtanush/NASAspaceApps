import json
from pathlib import Path

from analogforge.ports.science_payloads import (
    ConstraintsArtifact,
    RouteArtifact,
)

root = Path.cwd()
seed = json.loads((root / "apps/web/src/mock/fixtures/seed.json").read_text())
graph = json.loads((root / "tests/fixtures/kit/canonical-graph-v1.json").read_text())
h = seed["hash"]
u = "70000000-0000-4000-8000-000000000001"
r = seed["roverPresets"]["ARES-1"]
ref = {"evidence_id": u}
constraints = ConstraintsArtifact.model_validate(
    dict(
        schema_version="1.0",
        artifact_kind="RASTER_ROUTE_TEST",
        mode="synthetic",
        resource_provider="PHYSICAL_EARTH_MODEL",
        mission_revision_id=u,
        mission_content_sha256=h,
        rover_revision_id=u,
        rover_content_sha256=h,
        candidate_window_id="grid-r0c1",
        test_revision=1,
        strategy="WAYPOINT_RETURN",
        grid={
            "analysis_evidence_id": u,
            "analysis_grid_sha256": h,
            "crs_wkt": "EPSG:32612",
            "cell_size_m": 60,
            "width": 64,
            "height": 64,
        },
        graph=None,
        start={"node_id": None, "lon": -111, "lat": 35, "x_m": 494240, "y_m": 3900000},
        return_required=True,
        tasks=[
            {
                "task_id": name,
                "requirement_ids": ["R-TASKS"],
                "kind": "SAMPLING",
                "location": {
                    "node_id": None,
                    "lon": -110.99 if name == "W1" else -110.98,
                    "lat": 35.01,
                    "x_m": 494840 if name == "W1" else 495440,
                    "y_m": 3899400,
                },
                "tolerance_m": 60,
                "dwell_s": 60,
                "incremental_energy_wh": 10,
                "required_capability": "geological_sampling",
                "evidence_origin": "SYNTHETIC_FIXTURE",
            }
            for name in ["W1", "W2"]
        ],
        surface_slope_cap_deg=18,
        exposures=[
            {
                "requirement_id": "R-EXPOSURE",
                "metric_id": "surface_slope_deg",
                "band_deg": [12, 18],
                "upper_inclusive": True,
                "minimum_distance_m": 100,
                "counting": "UNIQUE_UNDIRECTED_EDGE_DISTANCE",
            }
        ],
        max_distance_m=8000,
        max_duration_s=None,
        max_undirected_edge_traversals=2,
        unknown_is_forbidden=True,
        footprint_dilation_m=0,
        blocked_edge_ids=[],
        energy={
            "model": r["energy_model"],
            "battery_wh": 1800,
            "min_reserve_pct": 20,
            "rover_mass_kg": 42,
            "nominal_speed_mps": 0.5,
            "gravity_mps2": 9.80665,
        },
        solver={"max_expansions": 100000, "max_seconds": 60, "max_labels_per_node": 100, "seed": 20261105},
        limitations=[
            "Authored mock practice constraints; not a scientific computation",
            "An unspecified rover maximum route uses the recorded 8000 m design default",
        ],
    )
)
graph_data = constraints.model_dump(mode="json")
graph_data.update(
    artifact_kind="SYNTHETIC_GRAPH_REGRESSION",
    resource_provider="TEST_ONLY_MOCK_GRAPH",
    grid=None,
    graph={"nodes": graph["nodes"], "edges": graph["edges"]},
    start={"node_id": "S", "lon": None, "lat": None, "x_m": None, "y_m": None},
    max_distance_m=400,
)
graph_constraints = ConstraintsArtifact.model_validate(graph_data)
route = RouteArtifact.model_validate(
    dict(
        schema_version="1.0",
        route_key="practice-waypoint-return",
        mode="synthetic",
        constraints_sha256=h,
        strategy="WAYPOINT_RETURN",
        graph_revision="synthetic-practice-grid-v1",
        node_sequence=["S", "A", "W1", "W2", "W1", "A", "S"],
        task_events=[
            {"task_id": "W1", "node_id": "W1", "arrival_distance_m": 40, "dwell_s": 60},
            {"task_id": "W2", "node_id": "W2", "arrival_distance_m": 60, "dwell_s": 60},
        ],
        display_geometry={"type": "LineString", "coordinates": [[-111, 35], [-110.995, 35.005], [-111, 35]]},
        solver_claimed={"distance_m": 120, "energy_conservative_wh": 26, "unique_exposure_m": {"R-EXPOSURE": 0}},
    )
)
(root / "apps/web/src/mock/fixtures/artifact-templates.json").write_text(
    json.dumps(
        {
            "constraints": constraints.model_dump(mode="json"),
            "graphConstraints": graph_constraints.model_dump(mode="json"),
            "route": route.model_dump(mode="json"),
        },
        indent=2,
    )
    + "\n"
)
