# API-ROUTING: route engine (`analogforge.science.routing`)

Pure functions returning kit payload models. No facade/evidence/artifact packaging here: the facade worker wraps these.
All functions are deterministic (same inputs -> same bytes, excluding `SearchCounters.elapsed_ms`); budgets use only
`time.monotonic` (injectable `clock`). Expected data problems raise `RouteInputError` (a `science.errors.ScienceError`
with `.code` / `.detail_code`) which the facade must translate to a `BLOCKED` result with a `ScienceIssue`.
`ScienceCancelled` / `ScienceDeadlineExceeded` raised by the `check_cancelled` callable are never swallowed.

Grid data enters as `routing.GridArrays` (elevation_m, valid, land, slope_deg, cell_size_m, origin_x_m = WEST edge of
column 0, origin_y_m = NORTH edge of row 0). Wire it from the ANALYSIS_GRID blob with
`routing.load_grid_arrays(path, expected_sha256=GridSpec.analysis_grid_sha256)` (uses `raster.store.decode_analysis_grid`;
a hash mismatch raises `RouteInputError(code="STALE_INPUT_HASH")`). Abstract graph scenarios pass `grid=None`.

Identifier conventions: raster node `r{row}c{col}` (row 0 = north; canonical decimal only, `r05c13` is rejected, see DECISIONS R-03); undirected edge `"{lo}--{hi}"` (string order);
`ConstraintsArtifact.blocked_edge_ids` use the edge ids.

## DESIGN_BENCHMARK -> `routing.waypoints.design_benchmark`

```python
design_benchmark(inp: DesignBenchmarkInput, *, mode, grid: GridArrays | None = None, grid_spec: GridSpec | None = None,
                 defaults: RouteDesignDefaults | None = None, constraints_artifact_key="constraints",
                 check_cancelled=None) -> DesignBenchmarkPayload
```

* `inp.graph_fixture_id == "canonical-graph-v1"` -> synthetic graph scenario (`mode` must be `synthetic`, else
  `RouteInputError(detail_code="MOCK_PROVIDER_FORBIDDEN")`): artifact kind `SYNTHETIC_GRAPH_REGRESSION`, mock provider.
* otherwise a raster candidate: needs `grid` (decoded candidate ANALYSIS_GRID) and `grid_spec` (`GridSpec` carrying the
  blob sha256 / crs_wkt / dims; the facade builds it from the analysis evidence). Start and tasks come from
  `auto-waypoints-v1`; exposures from every `unique_slope_exposure_m` requirement (`upper_inclusive` iff band upper ==
  rover cap); `max_distance_m = rover.max_route_m or defaults.max_route_m`.
* `RouteDesignDefaults(max_route_m, task_dwell_s, max_expansions, max_seconds, max_labels_per_node, seed,
  footprint_dilation_m, graph_max_distance_m)` is meant to be filled from `config/algorithms.yaml`
  (`design_defaults`, `route_search`).
* Returned `DesignBenchmarkPayload.constraints_sha256 = canonical_sha256(constraints)` (`constraints.constraints_sha256`
  helper). The facade writes the `ConstraintsArtifact` JSON (`canonical_json_bytes`) as the CONSTRAINTS artifact.
* Raises `RouteInputError(detail_code=ANALYSIS_GRID_MISSING | WAYPOINT_UNRESOLVED | BAND_MISSING | THRESHOLD_MISSING)`.

## SEARCH_ROUTE -> `routing.search.search_route`

```python
search_route(constraints, constraints_sha256_claimed, *, grid=None, mode, check_cancelled=None, max_expansions=None,
             max_seconds=None, max_labels_per_node=None, route_key="route", route_artifact_key="route",
             to_lonlat=None, clock=time.monotonic) -> SearchOutput
SearchOutput(payload: SearchRoutePayload, route: RouteArtifact | None, route_sha256: str | None,
             issues: list[ScienceIssue], certificate, problem)
```

* Stale hash -> `RouteInputError(code="STALE_INPUT_HASH")`; mock provider with `mode != "synthetic"` ->
  `detail_code="MOCK_PROVIDER_FORBIDDEN"`; grid missing/mismatching the `GridSpec` -> `ANALYSIS_GRID_MISSING` /
  `GRID_SPEC_MISMATCH`.
* Caller budgets can only LOWER the frozen `constraints.solver` budgets (pass `ScienceOptions.max_*`).
* `to_lonlat(x_m, y_m) -> (lon, lat)` (from core geometry) fills `RouteArtifact.display_geometry`; otherwise `None`.
* Serialise `output.route` with `canonical_json_bytes` as the ROUTE artifact; `payload.route_artifact_key` is whatever
  `route_artifact_key` you passed.
* Task semantics: a task is done at ANY traversable node within its tolerance (`Problem.task_sets`), identical in solver, certificate and verifier. Statuses: `FOUND`; `EXHAUSTIVE_INFEASIBLE` (certificate or complete enumeration, `labels_pruned_lossy == 0` always);
  `BUDGET_EXHAUSTED` (expansions/seconds, or lossy label-cap pruning); `ERROR` is not produced by this function (the
  facade maps unexpected exceptions to `FAILED`). `termination_reason` starts with `CERTIFICATE:` when no label search ran.
* Strategies: `WAYPOINT_RETURN` ignores exposures; `EXPOSURE_COVERAGE` / `RECOVERY_ALTERNATIVE` minimise distance, then
  conservative energy, then lexicographic `node_sequence`; `MINIMUM_FEASIBLE_ROUTE` minimises conservative energy first.

## VERIFY_ROUTE -> `routing.verify.verify_route`

```python
verify_route(constraints, constraints_sha256_claimed, route, route_sha256_claimed, search_status, *, grid=None, mode,
             verification_evidence_key="verification", telemetry_artifact_key="telemetry",
             rover_capabilities=None, check_cancelled=None, to_lonlat=None) -> VerifyOutput
VerifyOutput(payload: VerifyRoutePayload, telemetry: TelemetryArtifact | None, issues, route_sha256)
```

Independent of the solver (no import of search/graph builders; slab clipping; own dilation). Stale constraints/route
hash -> `INCONCLUSIVE / SYSTEM` with a `STALE_INPUT_HASH` violation (no telemetry). Missing energy model ->
`INCONCLUSIVE / DATA` and `issues=[ScienceIssue("ENERGY_UNCALIBRATED")]` (energy metrics are `None`, never 0).
`payload.telemetry_artifact_key` is the key you pass; `payload.verification_evidence` is
`EvidenceRef(local_key=verification_evidence_key)`. Serialise `telemetry` as the TELEMETRY artifact. Extra constraint
ids beyond the catalog: `C-TERRAIN-MASK`, `C-START`, `C-INPUT-HASH`.

## DIAGNOSE_RESULT -> `routing.diagnose.diagnose_result`

```python
diagnose_result(inp: DiagnoseResultInput, *, grid=None, mode, diagnosis_evidence_key="diagnosis",
                check_cancelled=None) -> DiagnoseOutput(payload: DiagnoseResultPayload, issues)
```

`grid` is required for raster constraints on `EXHAUSTIVE_INFEASIBLE` (ANALOG vs ROVER re-run of the certificate with the
slope cap lifted and the battery unbounded; terrain masks kept; if the original infeasibility came from enumeration a
relaxed search under the same budgets decides). `ROVER -> permitted_repairs == ["NEW_CONTRACT_REQUIRED"]`,
`recommended_repair=None`.

## Other public pieces

* `routing.constraints`: `constraints_sha256`, `require_fresh_hash`, `validate_constraints`, `make_energy_provider`
  (`PhysicalEarthEnergy` wraps `science.energy`, `MockGraphEnergy` test-only, `NullEnergy`), `RouteDesignDefaults`.
* `routing.fixture_graph`: `canonical_graph_spec(drop_edges=())`, `build_abstract_graph`, `design_graph_benchmark`.
* `routing.grid_graph`: `build_raster_graph`, `RouteGraph`, `components`.
* `routing.certificate.compute_certificate`, `routing.exposure` (band rule, unique/total accumulation),
  `routing.telemetry.build_telemetry`, `routing.supercover.supercover` (DDA).

Facade checklist: evidence ids per operation are the facade's job (algorithm ids `catalog.ALGORITHM_IDS`);
`validate_constraints` is already called inside search/verify; pass `context.check_cancelled` as `check_cancelled`.
