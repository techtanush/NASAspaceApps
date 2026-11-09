
## Adapters worker (earthdata, pds, emit, diviner, user_survey, source_http)

* A-01 AOI `bbox` is read as `[west, south, east, north]` (kit docs do not state the order). `west > east` means the box
  crosses the seam of its own longitude convention; boxes are split per target convention before any comparison.
* A-02 `coverage_fraction` is planar-degree footprint overlap against the union of selected granule/product boxes; it is
  documented as such in every selection note. Valid-pixel coverage (EMIT masks) is computed after decode
  (`emit.retrieval_in_bbox`) and returns `None` (unknown) for an empty intersection, never 0.
* A-03 `CoverageSelection` has no URL field, so selections carry ids only (CMR concept ids; PDS index-relative product
  paths) and `fetch` re-resolves download URLs through CMR / the PDS base URL. An agent-supplied URL can therefore never
  be fetched. Product paths are validated (`[A-Za-z0-9._/-]`, no `..`, no `//`).
* A-04 Credentials: `AUTH_REQUIRED` is reported at discovery when the injected client has neither an Authorization header
  nor an `auth` handler (CMR search itself is public, so the coverage is still returned); `fetch` raises
  `PROVIDER_AUTH_FAILED/AUTH_REQUIRED` without any download request. HTTP 401/403 -> same.
* A-05 Authorization/Cookie/Proxy-Authorization are removed (and client `auth=None` forced) for every hop whose host is not
  the initial host or in `HttpPolicy.auth_hosts`; redirects are followed manually and each hop is allow-list checked.
* A-06 Retry policy: at most 3 attempts; sleeps 2 s then 4 s; a `Retry-After` value replaces the back-off value and a value
  above `max_retry_after_s` (60) is not waited for. Truncated transfers are retried; checksum mismatch, HTML login pages,
  auth failures and 404 are never retried. 429 exhaustion -> `PROVIDER_RATE_LIMITED`, 5xx -> `SOURCE_UNAVAILABLE`,
  timeouts -> `TOOL_TIMEOUT`.
* A-07 Provider checksum absent => `AcquiredAsset.validation_status="PENDING"` (local SHA-256 still recorded); matched =>
  `"VERIFIED"`. PDS archives are always `"PENDING"` (no per-file provider checksum is compared).
* A-08 Archive expansion cap (20x) is applied to declared sizes before extraction and again to bytes actually copied.
* A-09 PDS3 labels via `pvl`; PDS4 via stdlib ElementTree after refusing any `<!DOCTYPE`/`<!ENTITY` (stricter than
  disabling external entities; real PDS4 labels do not need a DTD). `defusedxml`/`lxml` are not installed.
* A-10 MOLA/LOLA/Diviner scale and offset are applied with raw numpy reads, never via GDAL, so they can only be applied once.
  The caller must state `quantity` (`height`/`radius`/`count`); nothing is inferred from a file name. Pixel geometry comes
  from the label's bounding coordinates and is cross-checked against `MAP_RESOLUTION` when present; positive-west
  longitude products are refused (`UNSUPPORTED_PRODUCT`).
* A-11 NASADEM `SWB` is interpreted as non-zero = water (exact coding unverified, noted in `metadata.notes`); `NUM` is kept
  as a separate coded array. Mosaic precedence is the lexicographic tile name, first valid sample wins, and disagreeing
  shared samples are counted and disclosed (`seam_mismatch_cells`).
* A-12 Diviner supported variables are a small registry (`bolometric_brightness_temperature_{min,max,mean}`) whose index/base
  URLs are unverified proposals; any other variable is `UNSUPPORTED` at discovery and `UNSUPPORTED_PRODUCT` at decode.
  Celsius labels are converted by +273.15; any other unit is unsupported; samples <= 0 K are masked invalid.
* A-13 EMIT categorical ids use `-1` in `data` where the retrieval is invalid (`valid` authoritative); "no identification"
  ids (default `{0}`) count as valid retrievals but are reported separately (`identified_fraction`) and are never
  treated as proof of absence.
* A-14 `user_survey` never touches the network; missing declared metadata yields a decodable preview with
  `quantitative_use_allowed=False` and an `issues` list (missing fields, undeclared nodata, cell-support mismatch).
* A-15 Default hosts/URLs (`cmr.earthdata.nasa.gov`, `data.lpdaac.earthdatacloud.nasa.gov`, `urs.earthdata.nasa.gov`,
  `pds-geosciences.wustl.edu` paths) are configuration proposals for the future live gate; they are not validated.
* A-16 `h5py` is required by `h5netcdf` for EMIT and is absent from `pyproject.toml` -> CHANGE-REQUEST-adapters-h5py.json.

## Routing (science/routing) decisions

* R-01 Traversal limit vs dominance: the per-undirected-edge traversal limit (2) is enforced exactly on every label
  (counts rebuilt from the predecessor chain), but Pareto dominance between labels with the same (node, task set,
  saturation pattern) ignores the counts; `A` dominates `B` if A has <= distance/conservative energy/time, covers a
  superset of B's in-band edges and at least B's TOTAL traversed exposure; identical labels keep the lexicographically
  smaller `node_sequence`. Justification: if A's continuation of B's suffix would exceed the limit, removing two copies
  of the offending edge keeps tasks, unique exposure and the Euler circuit and strictly shortens the walk, contradicting
  distance-minimality (exact for distance/time bounds and symmetric energies). With an active energy bound on a surface
  with elevation changes (asymmetric energies) an empty queue after any dominance prune is reported `BUDGET_EXHAUSTED`
  with an approximation flag instead of `EXHAUSTIVE_INFEASIBLE`. Raster infeasibility is normally decided losslessly by the
  certificate, so this does not affect the practice storylines.
* R-02 Label cap: `max_labels_per_node` is applied per (node, task set, exposure level bucket) at label creation; any
  discarded label counts as `labels_pruned_lossy`, sets the `LABEL_CAP_TRUNCATION` flag and forbids EXHAUSTIVE_INFEASIBLE.
* R-03 Search order is A* (consistent admissible heuristic: horizontal shortest path to remaining tasks + return, and the
  remaining exposure deficit), key `(f, g, secondary, node_sequence)`; ranks of node ids come from plain string order so
  the tie-break is the lexicographically smallest `node_sequence` of node-id strings. `MINIMUM_FEASIBLE_ROUTE` orders by
  conservative energy first (admissible energy bound from reverse Dijkstra tables).
* R-04 Cell legality: a segment may only intersect valid, land, un-dilated, un-blocked cells in its SUPERCOVER (corner
  touches included, so a diagonal cannot cut an invalid corner or bridge a 1-pixel nodata channel). The slope cap and the
  hazard slope use only cells with intersection length > 1e-9 m (08 section 1), so a steep cell touched only at a corner does
  not block a diagonal.
* R-05 `auto-waypoints-v1` (40 section 6) is evaluated on the largest connected component of the traversal GRAPH (so the
  rule and the router agree on connectivity). W1/W2 candidates exclude cells that are themselves in the exposure band
  (40 section 4 states W1/W2 sit on non-band cells; the literal "greatest band count in 5x5" would otherwise pick ramp cells and
  let attempt 1 earn the exposure). W2 additionally stays in the same 0.15-0.30 window-edge annulus around S ("same rule").
  If a rule step has no candidate the design is BLOCKED (`WAYPOINT_UNRESOLVED`); there is no silent relaxation.
  `window_edge = max(width, height) * cell_size`.
* R-06 Closure tolerance in the verifier: raster 0.5 cell (same cell as the start, stricter than the one-cell snapping
  tolerance so "ends next to the start" is not a completed loop); graph exact node. Task completion: any route node within
  `tolerance_m` of the task location (first arrival counts; dwell and task energy are charged once at first arrival).
* R-07 Energy of an edge uses core `science.energy.edge_energy` (theta_s from endpoint dz, cos(theta_s)*d_s = d_xy); task
  energy = `TaskSpec.incremental_energy_wh` (falls back to `science_task_wh`) plus idle power during dwell; conservative =
  nominal * (1 + uncertainty). The TEST_ONLY mock provider ignores the model margin/idle (GRAPH_EXPECTED has no margin).
* R-08 Verifier outcome precedence: any definite violation -> FAIL/ROUTE (even if energy is also unevaluable); else missing
  energy model -> INCONCLUSIVE/DATA + `ENERGY_UNCALIBRATED`; stale constraints/route hash -> INCONCLUSIVE/SYSTEM. Extra
  constraint ids: `C-TERRAIN-MASK`, `C-START`, `C-INPUT-HASH`. Task capability (`TASK_CAPABILITY_MISSING`) is only checked
  if the facade passes `rover_capabilities` (the kit's VerifyRouteInput carries no rover).
* R-09 Diagnosis: `ROVER` yields `permitted_repairs=["NEW_CONTRACT_REQUIRED"]` and `recommended_repair=None` (never an
  automatic action). When the original infeasibility came from enumeration rather than the certificate, ANALOG/ROVER is
  decided by a relaxed search (slope cap 89.999999, battery 1e12, same budgets); an undecidable relaxed search yields
  `SEARCH_LIMIT`.
* R-10 A segment lying exactly on a grid line is "touched" by both neighbouring cells under slab clipping (closed squares)
  but by one cell under DDA; route edges join cell centres and never do this. The property test excludes that degenerate case.

## Core library (geometry, raster, features, energy, comparison, qualification, compatibility, config)

* C-01 `valid` of the ANALYSIS_GRID = usable (finite, not nodata, not water) with a full 3x3 usable neighbourhood, so a land
  cell next to water or nodata is NOT valid (guide 08 4.6 "adjacent to nodata/water are invalid"); `land` = not water. The
  practice-window `valid_fraction` oracles (40 section 4, e.g. r1c2 0.50-0.60) are therefore halo-inclusive: the fixture generator
  and its independent checker must use the same definition (`features.coverage.coverage_summary`, `land_data_fraction` gives the
  halo-free variant).
* C-02 Slope/aspect use the pseudo-inverse of the 3x3 design matrix built from the true metric offsets of the raster
  (`PixelGeometry`), differences taken to the centre sample for exactness; invalid slope is NaN in memory and 0 inside the npz
  (aspect is the only NaN-bearing member, as specified).
* C-03 Planetary CRS WKT is built from a PROJ string and then renamed (datum `D_<Body>_2000`, ellipsoid `<Body>_2000_IAU_IAG`) so no
  planetary frame says "unknown" or looks Earth-like; `assert_crs_matches_body` compares the ellipsoid semi-major axis (Earth CRS
  on Moon/Mars -> `BODY_MISMATCH`). Polar frames (|lat| >= 80) are polar stereographic with `lat_ts = +-90`; others
  equirectangular with `lat_ts` = AOI mid-latitude. Distortion is sampled on an 11x11 lattice; limit from `thresholds.max_linear_distortion`.
* C-04 `observable_policies` are keyed by policy id (the id the request carries) and carry one extra field `observable`; the physical-gap policy
  uses `units: "*"` because gravity (m/s2) and atmosphere (Pa) share it. `thermal-min-v1` lists `valid_bodies [EARTH, MOON]` because Earth
  thermal evidence is looked up (and found missing) on the Earth side. `valid_bodies` applies to every consulted evidence handle; candidate
  handles must additionally be EARTH.
* C-05 Gate order inside `compare_requirement`: physical gap (operator based, independent of policy id) -> dispatch (unknown
  observable / unknown policy / policy id != catalog mapping -> `REQUIREMENT_UNDERSPECIFIED`) -> units/body/mode (`METADATA_INCOMPLETE`)
  -> required evidence present (`*_EVIDENCE_MISSING`) -> support window (`SCALE_UNSUPPORTED`) -> coverage (`INSUFFICIENT_VALID_DATA`) -> numeric
  rule. Mineral rows skip the coverage gate (both sources present -> `THRESHOLD_UNRESOLVED` per spec; low retrieval coverage never becomes absence).
* C-06 Confidence: `MEDIUM` only for direct, adequately covered (>= 0.90), nominal-uncertainty evidence without assumed model parameters; `LOW`
  otherwise (all UNKNOWN/GAP rows, coverage 0.80-0.90, and route-reserve rows whose metric is `ASSUMED`). `HIGH` is reachable only with
  `uncertainty="quantified"` which v1 never supplies. Never `UNASSESSED`.
* C-07 Route rows: a `verification` is accepted only if a candidate evidence handle with algorithm `verify-route`, `search-route` or
  `diagnose-result` is present (otherwise `METADATA_INCOMPLETE`, FINAL); a definite row-level violation code (`EXPOSURE_SHORTFALL`,
  `WAYPOINT_MISSED|TASK_CAPABILITY_MISSING|RETURN_NOT_COMPLETED`, `ENERGY_RESERVE_SHORTFALL`) forces FAIL even if a metric looks passing;
  `FAIL` with category ANALOG/ROVER and no route metric on the exposure row yields `INSUFFICIENT_EXPOSURE`; INCONCLUSIVE with
  SYSTEM/SEARCH_LIMIT/REQUIREMENT credits nothing (`ROUTE_NOT_VERIFIED`). A coarse analysis support (> `maximum_support_scale_m`) -> `SCALE_UNSUPPORTED`.
* C-08 `validation_level`: GAP/no evidence S0; synthetic S1; live/replay: numeric terrain decision S3, route verified by an independent
  `verify-route` evidence S4, otherwise S2.
* C-09 Compatibility: `preliminary` = no verification carrying `route_distance_m`. `required_value`/`rover_value` semantics: slope (rover limit vs highest
  band upper), energy (verified reserve vs `rover.min_reserve_pct`), clearance/obstacle (declared vs the requirement lower bound; UNKNOWN unless the
  candidate support is within every clearance requirement's window), capability (listed -> PASS "declared, not observed"; non-empty list without
  it -> FAIL; empty list -> UNKNOWN), `route_length_m` (only when `max_route_m` is declared). With no frozen constraints a SCIENCE
  `completed_task_count` requirement implies `design_defaults.science_task_required_capability` (geological_sampling).
* C-10 Energy: `theta_s` defaults to the edge-aligned slope (`cos(theta_s) * d_s = d_xy`, 08 section 1); an optional `surface_slope_deg` override exists.
  Idle power is charged for drive time AND dwell; `science_task_wh` is the increment above idle; no regeneration. Missing model -> `None`.
* C-11 ANALYSIS_GRID `meta.json` contains exactly the keys of 08 section 3; `valid` implies `land`; the encoder refuses grids violating the invariants, and the
  decoder re-checks them (single parser).
* C-12 Spec ambiguity recorded, no contradiction found requiring a kit change: 08 section 4.7 lists `comparison_rule_id: emit-mineral-presence-v1`
  in the Mars mission fixture while the policy id is `mineral-presence-v1`; dispatch uses the catalog mapping (observable -> policy id), not `comparison_rule_id`.
