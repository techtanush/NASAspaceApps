"""FROZEN CONTRACT KIT FILE - analogforge.ports.catalog

Shared identifiers every branch must use verbatim: scenario ids, synthetic fixture ids,
practice-grid window ids, practice rover names, role keys, tool names, operational budgets
and exact expected values for deterministic regressions. DO NOT EDIT in any branch.
See architecture 40 for the meaning of each entry.
"""

from __future__ import annotations

from typing import Final

# ----------------------------------------------------------------------------- dataset locks
DATASET_LOCK_SYNTHETIC: Final = "synthetic-policy-v1"
DATASET_LOCK_LOCAL_PRACTICE: Final = "local-practice-policy-v1"
DATASET_LOCK_LIVE_HACKATHON: Final = "live-hackathon-policy-v1"

# ----------------------------------------------------------------------------- scenarios
SCENARIO_MARS_MOBILITY: Final = "synthetic-mars-mobility-v1"  # full raster workflow, A fails -> B passes
SCENARIO_GRAPH_REGRESSION: Final = "synthetic-graph-regression-v1"  # canonical graph through the whole app
SCENARIO_MOON_GAP: Final = "synthetic-moon-gap-v1"  # Moon target, thermal UNKNOWN, gravity/vacuum GAP
SCENARIO_LOCAL_PRACTICE: Final = "local-dataset-practice-v1"  # drop-in practice GeoTIFFs via INGEST_LOCAL_DATASET
SCENARIO_LIVE_HACKATHON: Final = "live-hackathon-v1"  # the NASA-data slot; unavailable until datasets registered
ALL_SCENARIOS: Final = (
    SCENARIO_MARS_MOBILITY,
    SCENARIO_GRAPH_REGRESSION,
    SCENARIO_MOON_GAP,
    SCENARIO_LOCAL_PRACTICE,
    SCENARIO_LIVE_HACKATHON,
)
DEFAULT_SCENARIO: Final = SCENARIO_MARS_MOBILITY

# ----------------------------------------------------------------------------- synthetic fixtures
FIXTURE_MARS_TARGET: Final = "practice-mars-target-v1"
FIXTURE_MOON_TARGET: Final = "practice-moon-target-v1"
FIXTURE_EARTH_GRID: Final = "practice-earth-grid-v1"
FIXTURE_CANONICAL_GRAPH: Final = "canonical-graph-v1"
SEARCH_REGION_PRACTICE: Final = "practice-earth-grid-v1"  # search_region_set_id for the 3x3 grid
REFERENCE_SET_PRACTICE: Final = "practice-reference-set-v1"

# Window ids of the 3x3 practice Earth grid (architecture 40 section 3). Row 0 is north.
WINDOW_B_CORRIDOR: Final = "grid-r0c0"  # connected 15 deg ramp: route-feasible (PASS expected)
WINDOW_A_MESA: Final = "grid-r0c1"  # large 15 deg area on an unreachable mesa (FAIL expected)
WINDOW_C_FLAT: Final = "grid-r0c2"  # low-relief negative control (exposure FAIL expected)
WINDOW_ROLLING_1: Final = "grid-r1c0"
WINDOW_WATER: Final = "grid-r1c1"  # excluded: WATER_ONLY
WINDOW_NODATA_STRIPE: Final = "grid-r1c2"  # nodata stripe: limited coverage
WINDOW_ROLLING_2: Final = "grid-r2c0"
WINDOW_GENTLE: Final = "grid-r2c1"
WINDOW_KNOWN_REFERENCE: Final = "grid-r2c2"  # in the practice reference set => KNOWN_ANALOG
GRAPH_WINDOW_ID: Final = "graph-zone-1"  # candidate window for the graph scenario

# ----------------------------------------------------------------------------- practice rovers
ROVER_ARES_1: Final = "ARES-1"
ROVER_PRACTICE_LITE: Final = "PRACTICE-LITE"  # 12 deg max slope: conflicts with a [12,18] band
ROVER_PRACTICE_NO_ENERGY: Final = "PRACTICE-NO-ENERGY-MODEL"  # energy_model null: energy INCONCLUSIVE
ROVER_PRACTICE_SMALL_BATTERY: Final = "PRACTICE-SMALL-BATTERY"  # 30 Wh: ENERGY_RESERVE_SHORTFALL
PRACTICE_ROVER_FILES: Final = {
    ROVER_ARES_1: "rovers/ares-1.json",
    ROVER_PRACTICE_LITE: "rovers/practice-lite.json",
    ROVER_PRACTICE_NO_ENERGY: "rovers/practice-no-energy-model.json",
    ROVER_PRACTICE_SMALL_BATTERY: "rovers/practice-small-battery.json",
}

# ----------------------------------------------------------------------------- agent council
ROLE_KEYS: Final = (
    "mission_director",
    "requirements",
    "rover_systems",
    "planetary_target",
    "earth_scout",
    "qualification",
    "scientific_critic",
    "test_designer",
    "verification_replanning",
    "evidence_passport",
)
ROLE_DISPLAY_NAMES: Final = {
    "mission_director": "Mission Director",
    "requirements": "Requirements",
    "rover_systems": "Rover Systems",
    "planetary_target": "Planetary Target",
    "earth_scout": "Earth Analog Scout",
    "qualification": "Qualification",
    "scientific_critic": "Scientific Critic",
    "test_designer": "Test Designer",
    "verification_replanning": "Verification & Replanning",
    "evidence_passport": "Evidence/Passport",
}
TOOL_NAMES: Final = (
    "get_run_snapshot",
    "inspect_contract",
    "validate_mission_draft",
    "validate_rover_profile",
    "resolve_dataset_coverage",
    "fetch_dataset",
    "characterize_target",
    "screen_earth_candidates",
    "analyze_earth_candidate",
    "compare_requirement",
    "assess_rover_compatibility",
    "review_evidence_bundle",
    "design_test",
    "search_route",
    "verify_route",
    "diagnose_verification",
    "optimize_portfolio",
    "get_evidence",
    "compare_evidence",
    "build_passport_manifest",
    "submit_role_result",
)

# ----------------------------------------------------------------------------- canonical budgets
# Single source of truth for operational budgets (architecture 34, erratum E-03).
BUDGETS: Final = {
    "model_requests_per_invocation": 6,
    "tool_calls_per_invocation": 8,
    "model_requests_per_run": 40,
    "preparation_model_requests": 4,
    "tool_calls_per_run": 160,
    "director_dispatches_per_run": 30,
    "coarse_windows_max": 30,
    "detailed_candidates_default": 6,
    "detailed_candidates_operator_cap": 25,
    "critic_repair_rounds": 2,
    "replans_total": 3,
    "route_repairs_same_candidate": 2,
    "candidate_switches": 1,
    "route_attempts_per_candidate": 3,
    "portfolio_sites_default": 3,
    "portfolio_sites_max": 5,
    "active_run_seconds": 900,
    "search_max_expansions": 200_000,
    "search_max_seconds": 30,
    "search_max_labels_per_node": 32,
    "max_undirected_edge_traversals": 2,
    "job_lease_seconds": 120,
    "job_heartbeat_seconds": 20,
}

# ----------------------------------------------------------------------------- exact regressions
# Canonical graph (examples/synthetic-route-graph.json), mock energies, no uncertainty margin.
GRAPH_SUPPLIED_ROUTE_FAIL: Final = ("S", "A", "W1", "W2", "W1", "A", "S")  # 120 m, 26 Wh, 0 m -> FAIL
GRAPH_SUPPLIED_ROUTE_PASS: Final = ("S", "B", "C", "W1", "W2", "W1", "C", "B", "S")  # 340 m, 34 Wh, 150 m -> PASS
GRAPH_SEARCH_WAYPOINT_RETURN: Final = ("S", "A", "W1", "W2", "W1", "A", "S")  # 120 m, 26 Wh, 0 m -> verify FAIL
GRAPH_SEARCH_EXPOSURE_COVERAGE: Final = ("S", "A", "W1", "W2", "W1", "C", "B", "S")  # 230 m, 30 Wh, 150 m -> PASS
GRAPH_EXPECTED: Final = {
    "supplied_fail": {"distance_m": 120.0, "energy_wh": 26.0, "unique_exposure_m": 0.0, "outcome": "FAIL",
                      "violation": "EXPOSURE_SHORTFALL", "category": "ROUTE"},
    "supplied_pass": {"distance_m": 340.0, "energy_wh": 34.0, "unique_exposure_m": 150.0, "outcome": "PASS",
                      "reserve_pct": 98.11111111111111},
    "search_waypoint_return": {"distance_m": 120.0, "energy_wh": 26.0, "unique_exposure_m": 0.0, "outcome": "FAIL",
                               "search_status": "FOUND", "category": "ROUTE"},
    "search_exposure_coverage": {"distance_m": 230.0, "energy_wh": 30.0, "unique_exposure_m": 150.0, "outcome": "PASS",
                                 "search_status": "FOUND", "reserve_pct": 98.33333333333333},
    "one_expansion_budget": {"search_status": "BUDGET_EXHAUSTED", "outcome": "INCONCLUSIVE", "category": "SEARCH_LIMIT"},
    "steep_edges_removed": {"search_status": "EXHAUSTIVE_INFEASIBLE", "outcome": "FAIL"},
}
# Tie-break for equal (distance, conservative energy): lexicographically smallest node_sequence.

# Analytic energy oracle (architecture 29 section 4): flat 1000 m, 42 kg, Crr 0.06, eta 0.65,
# k_r 1, 0.5 m/s, idle 35 W, no tasks, margin 0.25, battery 1800 Wh. Tolerance 1e-8 Wh.
ENERGY_ORACLE_FLAT_1000M: Final = {
    "rolling_wh": 10.56100769230769,
    "idle_wh": 19.444444444444443,
    "nominal_wh": 30.005452136752133,
    "conservative_wh": 37.506815170940165,
    "reserve_pct": 97.91628804605888,
}

# ----------------------------------------------------------------------------- naming + policy maps
PRACTICE_CANDIDATE_NAME_PREFIX: Final = "Practice "  # candidate name == prefix + window_id
MEASUREMENT_SPEC_TARGET: Final = "terrain-target-v1"
MEASUREMENT_SPEC_EARTH: Final = "terrain-earth-v1"
# Requirement.observable -> observable policy id (config/algorithms.yaml observable_policies).
# An observable absent from this map yields UNKNOWN / REQUIREMENT_UNDERSPECIFIED, never a guess.
OBSERVABLE_POLICY_BY_OBSERVABLE: Final = {
    "slope_band_area_fraction": "slope-band-area-fraction-v1",
    "slope_distribution_w1_deg": "slope-w1-common-support-v1",
    "unique_slope_exposure_m": "route-exposure-v1",
    "completed_task_count": "route-tasks-v1",
    "final_battery_reserve_pct": "route-reserve-v1",
    "mineral_class_present": "mineral-presence-v1",
    "surface_temperature_min_k": "thermal-min-v1",
    "ground_clearance_m": "clearance-scale-v1",
    "planetary_gravity": "physical-gap-v1",
    "planetary_atmosphere": "physical-gap-v1",
}


# ----------------------------------------------------------------------------- constraint ids
# Stable ids of benchmark constraints inside a ConstraintsArtifact / BenchmarkRow / RouteViolation.
CONSTRAINT_SLOPE_CAP: Final = "C-SLOPE-CAP"
CONSTRAINT_RETURN: Final = "C-RETURN"
CONSTRAINT_CONTINUITY: Final = "C-CONTINUITY"
CONSTRAINT_ENERGY_RESERVE: Final = "C-ENERGY-RESERVE"
CONSTRAINT_MAX_DISTANCE: Final = "C-MAX-DISTANCE"
CONSTRAINT_MAX_DURATION: Final = "C-MAX-DURATION"
CONSTRAINT_EDGE_TRAVERSALS: Final = "C-EDGE-TRAVERSALS"


def constraint_task(task_id: str) -> str:
    return f"C-TASK-{task_id}"


def constraint_exposure(requirement_id: str) -> str:
    return f"C-EXPOSURE-{requirement_id}"


# Route-dependent requirement observables (their rows are UNKNOWN/ROUTE_NOT_VERIFIED/PRELIMINARY until a
# route is verified; architecture 34 erratum E-09).
ROUTE_DEPENDENT_OBSERVABLES: Final = frozenset(
    {"unique_slope_exposure_m", "completed_task_count", "final_battery_reserve_pct"}
)
OBSERVABLE_CONSTRAINT: Final = {
    "unique_slope_exposure_m": "exposure",
    "completed_task_count": "tasks",
    "final_battery_reserve_pct": CONSTRAINT_ENERGY_RESERVE,
}

# Practice analysis grid (architecture 40 section 2).
PRACTICE_GRID_CELL_M: Final = 60.0
PRACTICE_WINDOW_CELLS: Final = 64
PRACTICE_GRID_CRS_EPSG: Final = 32612
PRACTICE_GRID_SW_EASTING_M: Final = 494240.0
PRACTICE_GRID_NORTH_NORTHING_M: Final = 3900000.0


# ----------------------------------------------------------------------------- UI-readable artifacts
# Every payload-bearing science operation emits an evidence draft whose algorithm_id is the value below and whose
# artifact is the operation payload serialized with ports.hashing.canonical_json_bytes (media type application/json).
# The frontend discovers them by GET /evidence/{id} -> algorithm_id -> GET /artifacts/{sha256}. (architecture 35 section 5b)
ALGORITHM_IDS: Final = {
    "INGEST_LOCAL_DATASET": "ingest-local-dataset",  # SOURCE evidence, no artifact bytes
    "CHARACTERIZE_TARGET": "characterize-target",  # artifact: CharacterizeTargetPayload JSON
    "SCREEN_CANDIDATES": "screen-candidates",  # artifact: ScreenCandidatesPayload JSON
    "ANALYZE_CANDIDATE": "analyze-candidate",  # artifact: ANALYSIS_GRID npz (role ANALYSIS_GRID)
    "ANALYSIS_SUMMARY": "analysis-summary",  # artifact: AnalyzeCandidatePayload JSON (child of analyze-candidate)
    "COMPARE_REQUIREMENT": "compare-requirement",  # artifact: CompareRequirementPayload JSON
    "ASSESS_COMPATIBILITY": "assess-compatibility",  # artifact: AssessCompatibilityPayload JSON
    "DESIGN_BENCHMARK": "design-benchmark",  # artifact: ConstraintsArtifact JSON (role CONSTRAINTS)
    "SEARCH_ROUTE": "search-route",  # artifact: RouteArtifact JSON (role ROUTE); none when no route
    "VERIFY_ROUTE": "verify-route",  # VERIFICATION evidence; artifact: VerifyRoutePayload JSON
    "ROUTE_TELEMETRY": "route-telemetry",  # artifact: TelemetryArtifact JSON (role TELEMETRY)
    "DIAGNOSE_RESULT": "diagnose-result",  # artifact: DiagnoseResultPayload JSON
    "OPTIMIZE_PORTFOLIO": "optimize-portfolio",  # artifact: OptimizePortfolioPayload JSON
    "AUDIT_EVIDENCE": "audit-evidence",  # artifact: AuditEvidencePayload JSON
    "SCIENTIFIC_ASSURANCE": "scientific-assurance",  # platform; artifact validates against scientific-assurance schema
}
ALGORITHM_ID_SCREENING: Final = ALGORITHM_IDS["SCREEN_CANDIDATES"]
