
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

## Portfolio / display / audit worker (A-xx)
* A-01 Portfolio ties and tiers: objective tiers are (mandatory weight, optional weight, -site count, evidence rank) with final tie on the smallest sorted `window_id` tuple; evidence rank 3/2/1 = verified / FINAL PASS / PRELIMINARY PASS (documented in API-PORTFOLIO-DISPLAY-AUDIT.md). Coupled-group weights are the member weights, counted once. A coupled group needs the window's `verification_by_window_id` outcome PASS; an uncoupled route-dependent row needs FINAL and, if a verification is supplied for the window, PASS (a missing verification entry is not treated as failure, per 08 4.13 wording).
* A-02 CONTRADICTION/GAP: `AuditEvidenceInput.ClaimScope` carries `requirement_id` but no `Requirement`, so SC-04 (requirement window) and the observable policy lookup cannot be derived from the kit request alone. `audit_evidence` takes `requirements` as an extra argument; the facade must resolve them (e.g. from the frozen mission via the platform). Without it SC-04 is `NOT_ASSESSED`, never SATISFIED. A kit change request is NOT filed; a compatible local workaround is used.
* A-03 `EvidenceHandle` has no product id, so SC-10 ancestry uses explicit `source_families` from the facade when available and otherwise product tokens in limitations/local_key_origin/algorithm_id. SC-13 inputs (search extent, reference set, negative controls, mission-sensitivity evidence) are likewise passed as `DiscoveryEvidence` derived from the screening payload.
* A-04 Spelling: attribution uses the em dash string of guide 08 4.14 (`SYNTHETIC PRACTICE DATA — not terrain of this location`), which differs from `provenance.SYNTHETIC_LICENSE_NOTE` (ASCII hyphen, evidence license note). Both are kept; they serve different fields.
* A-05 Display: Earth images are resampled to Web Mercator by nearest containing analysis cell; small grids get an integer nearest upscale (target 256 px) with `pixel_to_world` scaled accordingly; the Earth image rectangle (not the rotated UTM footprint) defines `earth_corners`, with outside-footprint pixels transparent. QUALIFICATION layers are not produced (not requestable in `BuildDisplayLayersInput`).
* A-06 Mutation-check note: PYTHONDONTWRITEBYTECODE is required when mutating sources in place (same-size edits within one second reuse stale .pyc); the 14 mutants listed in the final report were all killed after clearing caches.
* A-07 Environment defect (not mine): `src/analogforge/science/datasets/inspect.py` line 116 (E501) and line 153 (mypy `format` literal) fail ruff/mypy; reported to the owner of that file.

## Facade (science/facade.py, science/ops/*)

* F-01 Dispatch is a table of (module, function, algorithm id); ops are plain `(OpEnv) -> OpOutcome` functions. Expected problems raise
  `OpBlocked`/`ScienceError` -> `BLOCKED` with one `ScienceIssue`; pydantic validation errors -> `BLOCKED INPUT_INVALID/MODEL_VALIDATION`;
  any other exception -> `FAILED` with code `SYSTEM` (no such code exists in error-codes.json; the closest class is "SYSTEM-class" of
  architecture 35 3.4) and `detail_code` = exception type. `ScienceCancelled`/`ScienceDeadlineExceeded` always propagate (never a result).
* F-02 `parameters_sha256` of the result and of evidence = `hashing_utils.parameters_sha256` over {operation, algorithm id/version, request
  inputs minus request_id, sorted input-evidence parameter+artifact hashes, extra source hashes, seed, algorithm_config_sha256}. request_id is
  excluded so the platform cache key semantics hold. Scratch paths are `<op>/<params[:16]>/<name>` so two requests never collide.
* F-03 `create_science_service(config_dir=None)` takes an optional config directory (default `analogforge/config`) so tests can prove thresholds are read
  from yaml. `ScienceOptions.algorithm_config_sha256` is a pin: a hash that is neither the loaded config nor a loaded config -> BLOCKED.
* F-04 SYNTHETIC_FIXTURE sources are generated by `fixtures.practice.generate_all` into `scratch/_fixtures` and then read through the SAME
  ingest path as LOCAL_DATASET (parity by construction). ADAPTER_EVIDENCE sources are BLOCKED `UNSUPPORTED_PRODUCT` in this build.
* F-05 COMPARE_REQUIREMENT W1: the candidate histogram at the target's support is re-derived from the candidate ANALYSIS_GRID (area-averaged
  elevation, slope recomputed on the coarse grid, outermost coarse ring invalid; never upsampled). A candidate whose only histogram is the 60 m
  analysis-summary therefore yields `SCALE_UNSUPPORTED`. The COMPARISON evidence carries `comparison_scale_m` (480/960).
* F-06 COMPARE_REQUIREMENT also emits an `ASSUMPTION` evidence ("requirement") whose artifact is the Requirement JSON, parent of the COMPARISON.
  AUDIT_EVIDENCE reads Requirement records from any input evidence of that shape to resolve SC-04 (kit `ClaimScope` carries no window; see A-02).
  Without them SC-04 is NOT_ASSESSED.
* F-07 ANALYZE_CANDIDATE metrics: `valid_fraction`, `slope_area_fraction:<lo>-<hi>` for EVERY pair of histogram edges (so any requirement band aligned to
  the edges is answerable), `surface_slope_deg:*`, roughness/relief at 3/5/9 cells. Connected zones: safe = valid, land, slope <= cap 18, 8-connected,
  min 4 cells, `contains_start` for the largest component (the component auto-waypoints-v1 will use); band areas for all edge pairs.
* F-08 SCREEN_CANDIDATES: deficit = max over `slope_band_area_fraction` requirements of max(0, lower - f_band); rank key (deficit, W1 (None last), window_id);
  shortlist = best `max_detailed - n_controls` non-control windows plus ranked negative controls; the rest of the ranked windows carry
  `exclusion_reason="BELOW_SHORTLIST_CUTOFF"` with `excluded=False`. W1 is computed with whole-source derivatives at the target support and cropped.
  Each non-excluded window has a DERIVED evidence (no artifact) with `comparison_scale_m` = common support; the screening evidence limitations contain
  `reference_set=<id>` for the audit (SC-13).
* F-09 CHARACTERIZE_TARGET emits profile (JSON) + `target-grid` (ANALYSIS_GRID of the AOI crop at comparison support) evidences, both algorithm
  `characterize-target`; BUILD_DISPLAY_LAYERS for TARGET reads the npz one. THERMAL/MINERAL display layers need rasters no evidence artifact carries -> issue
  `NO_COVERAGE/LAYER_DATA_MISSING` (LIMITED if another layer was built, else BLOCKED).
* F-10 FETCH_SOURCE / network RESOLVE_COVERAGE are BLOCKED `UNSUPPORTED_PRODUCT` outside live mode with an injected client; live paths call the adapters' `discover/fetch`
  and are exercised only against mocked adapters elsewhere (SCN-18).

## Dataset slot (science/datasets)
* D-01 Dependent checks that cannot run (invalid manifest, unreadable/HTML file) report `WARN` `NOT_EVALUATED: ...` rather
  than FAIL (root cause already reported once; mock-drop "exactly the named check") or PASS (unknown is not success).
  These WARNs are blocking for `usable_for_quantitative_claims`. Arch 36 section 4 does not specify this case.
* D-02 HTML-by-content detection owns the failure: `format_readable` is `NOT_EVALUATED` when a file is an HTML page, so
  `mock-nasa-bad-html` fails exactly `html_login_page` (arch 39 section 5).
* D-03 CRS: file CRS must be present for GEOTIFF/COG/HGT/HGT_ZIP (missing => `crs_resolved` FAIL, arch 39 `bad-no-crs`);
  other formats may rely on the manifest CRS. Earth-vs-planet ellipsoid contradiction => `crs_resolved`; planet-vs-planet or
  >1 % radius error => `body_consistent`. An Earth CRS on a planet therefore fails both (unavoidable overlap). The file CRS
  georeferences when present (GDAL's PDS3 driver reports a projected sphere even when the manifest says geographic).
* D-04 `scale_offset_once` table: reader scale present + manifest scale present => FAIL in both flag states unless
  `scale_already_applied` is true and the two agree; file scale present but manifest silent and not `scale_already_applied`
  => FAIL (GDAL scales are never silently applied); `scale_already_applied` true with no file scale and a manifest scale => FAIL.
* D-05 `longitude_convention`: geographic rasters must start inside the declared range; may spill past the upper bound when
  they straddle it (359.9..360.1 is valid ZERO_360, invalid NEG180_180). PROJECTED requires a projected CRS.
* D-06 `units_and_quantity` also rejects role/quantity pairs the role cannot consume (e.g. mineral role with ELEVATION),
  `reference_radius_m` more than 1 % from the body mean radius, relative height p99 > 50 km, non-integer class ids, scaled
  class ids. SLOPE_DEG => blocking WARN ("allowed but flagged"). CONTEXT_ONLY is never usable.
* D-07 `lineage_fields` also fails on the `TODO_FILL_IN` placeholder in provider/license_note/citation/vertical_reference/title
  and on signed/token-bearing `product_identity.source_url`. `draft_manifest` writes `vertical_reference: not applicable`
  for non-height quantities.
* D-08 Resolution cross-check compares the declared posting with the larger cell side (geographic cells shrink east-west
  with latitude: SRTM3 is "90 m" north-south); `native_resolution_m` in the payload is the geometric-mean cell size.
* D-09 `nodata_value` in the manifest that differs from the file's nodata => `nodata_declared` FAIL.
* D-10 NetCDF: GDAL first, h5netcdf (EMIT convention) when GDAL leaves the variable ungeoreferenced; h5py remains an
  undeclared dependency (see CHANGE-REQUEST-adapters-h5py.json).
* D-11 INCIDENT: a stray `ruff format src` (a whole-tree format run instead of only my paths) reformatted
  `src/analogforge/adapters/**` (19 tracked files, whitespace/line-wrapping only, behaviour unchanged; 575 science tests still
  pass). Reverting with `git checkout` was blocked, so the coordinator should either keep or `git checkout -- src/analogforge/adapters`.

## Fixtures (science/fixtures, tests/fixtures/science/window_checker.py)

* F-01 The practice 60 m grid is one continuous surface: features are compactly supported (cones, slabs, ramps that return to the base level)
  so no window border creates a cliff. Consequence of C-01: the 0.80 `valid_fraction` policy counts water and the halo of water/nodata as
  invalid, so windows A and KNOWN (moats) sit at 0.82 / 0.81, close to the floor. `moat_cells` is the number of water cells between the island
  land and the mainland land measured by the checker (the generator widens the water ring by half a cell on each side so diagonals also reach it).
* F-02 Window B (`grid-r0c0`): the architecture asks for a 15 deg corridor with a 5-6 deg surround and a first-attempt property ("minimum-distance
  WAYPOINT_RETURN loop earns < 100 m"). A 15 deg ramp cannot end inside a 64-cell window without a taper of <= 6 deg that needs >= 28 cells, so B's
  ramp runs the full window height and its narrowing wedge (where the 5.5 deg roof meets it) lies in `grid-r1c0`, which supplies r1c0's band
  fraction (0.029). The wedge is deliberately outside B's waypoint annulus; with a wedge inside B the rule picks W1/W2 on the slanted edge and the
  shortest W1-W2 path is tied between band and non-band cells. "Width >= 8 cells" and "runs >= 40 cells" are checked as: inscribed disc diameter of
  the largest 15 +- 0.5 deg interior component >= 8 cells and its extent >= 40 cells; "everything else <= 6 deg" means outside a 2-cell dilation of the band.
* F-03 Window A is a tilted 15 deg slab (not a cone): with `moat_cells=0` its straight south foot joins the mainland smoothly, S/W1/W2 stay on the
  mainland and the minimum-distance loop earns 0 m while an exposure route exists (PERT-01 behaves as written). A round island would put the
  start cell inside the band when the moat is removed (W1/W2 on the rim, loop chord crossing the island). Cone islands are used only for KNOWN and fillers.
* F-04 PERT-02 as specified (ramp 15 -> 10 deg) removes all band cells of B (f_band 0); `R-SLOPE-AVAILABILITY` FAIL is therefore guaranteed.
* F-05 `generate_all` returns dataset ids (not paths). `target_fractions` is an alias of `mars_fractions`; Moon fractions use `moon_fractions`.
  The Moon height field is centred on the reference sphere so int16 at scale 0.5 spans +-16 km; an overflow raises `ValueError`.
* F-06 Mock-drop quirks chosen so the parallel ingest accepts the good five and flags exactly one check per bad one: lunar PDS3 radius in km
  with GDAL-readable scale/offset (`scale_already_applied: true`), NetCDF georeference through a root `crs` grid-mapping variable (GDAL does not
  read per-group coordinate variables), `mock-nasa-bad-no-crs` declares `epsg: 32612` in its manifest while the file has no CRS (the ingest FAILs
  `crs_resolved` for the missing file CRS), pixel registration CORNER for area-referenced GeoTIFF/ASCII fixtures and UNKNOWN where ambiguous.
* F-07 Mars strips have 4 kink columns that mix neighbouring slopes; measured fractions (0.42/0.30/0.19/0.087) are within the +-0.03 allowance.

## Ownership / test layout (closing pass)
* O-01 Contradiction: guide 08 calls `registrar_stub` and the other helpers "under `tests/support/` yours", but `team coordination/contracts/ownership.json`
  assigns `analogforge/tests/conftest.py` and `analogforge/tests/support/` to Tanush, so `check_branch_ownership.py --person ayan` failed. The registry
  was NOT edited. The helpers moved to the Ayan-owned `tests/fixtures/science/support/` (package `support`; `builders.KIT` now resolves to
  `tests/fixtures/kit`), the shared `tests/conftest.py` was deleted and replaced by one `conftest.py` per `tests/{unit,integration,contracts,property,replay}/science/`
  that puts `tests/fixtures/science` on `sys.path`. `forbidden_scan.py` scans `tests/fixtures/science` instead of `tests/support`.
* O-02 `analogforge/out/` (generated oracle/forbidden/mutation JSON and junit XML) is never committed. `analogforge/.gitignore` is a frozen kit file so it
  cannot list `out/`; the clone-local `.git/info/exclude` carries `analogforge/out/` so `git ls-files --others --exclude-standard` (used by the
  ownership check) does not see it. Scripts keep writing to `analogforge/out/`.
* O-03 D-01 (aspect == 360.0) fixed in `features/slope.py`; the facade workaround `clean_aspect` was removed.
* O-04 New: `tests/property/science/test_properties.py` (cross-cutting properties) and `scripts/science/validate_sources.py` (+ `tests/integration/science/test_validate_sources.py`).
