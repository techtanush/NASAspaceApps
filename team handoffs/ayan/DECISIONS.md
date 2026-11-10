
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

## Route-engine adversarial-review fixes (routing)
* R-01 Task satisfaction is the SET of traversable nodes within the task tolerance (`Problem.task_sets`; `task_nodes` stays as the nearest
  representative). Solver, certificate (reachable iff any member is in the start component; distance/energy bounds use the cheapest member)
  and heuristics (multi-source Dijkstra, `min` over members for the return leg) use the same rule as the verifier, which accepts any in-tolerance
  route node. The first in-tolerance arrival completes the task, so FOUND routes stay minimal under the shared semantics.
* R-02 Corner-touch geometry uses `routing.tie_slack_cells` (1e-12 + 8 eps_mach * max|coordinate| / cell_size, in cells) instead of a fixed 1e-12 in
  BOTH algorithms; the algorithms stay different (DDA tie test scaled by the larger direction component; slab clipping tests inclusion against
  squares expanded by the slack and measures lengths on the exact square, lengths <= slack are 0). Over-detecting a touch is the conservative direction.
* R-03 Node-id aliasing: REJECT, not canonicalise. `parse_raster_node_id` accepts only `r<0|[1-9][0-9]*>c<...>` (ASCII, full match), so `r05c13`,
  `r5c013`, fullwidth/Arabic digits and trailing newlines are not node ids; the verifier reports them as `DISCONTINUOUS_ROUTE` with a "non-canonical node
  id" message (the closed `RouteViolation.code` set has no dedicated code). Waypoints with such ids raise `WAYPOINT_UNRESOLVED`.
* R-04/R-05 Pareto dominance has two modes. RELAXED (limit >= 2 and no TOTAL requirement) keeps the "remove two copies of a third traversal" argument.
  STRICT (limit == 1, or any TOTAL_TRAVERSED_DISTANCE requirement, where removing copies lowers counted exposure) additionally requires pointwise
  usage `A <= B`; ties on all costs with different usage keep both labels so the lexicographic tie-break stays exact. No STRICT prune is lossy, so the
  asymmetric-energy "withhold EXHAUSTIVE_INFEASIBLE" rule applies to RELAXED mode only. Cost: weaker pruning for those two cases (budgets still bound it).
* R-06 A root label that already satisfies everything is not a solution (a route has >= 1 edge) and is therefore kept out of the Pareto table and the
  label-cap counters, so it cannot dominate the labels that leave and return (`S,A,S` is found when every task is at the start).
* R-07 The wall-clock budget is read on the first pop and every 8 pops (was every 256).
* R-08 Non-finite terrain: a VALID cell with NaN/inf slope or elevation is impassable for the solver (never a node, never crossed) and, if a route
  touches one, the verifier emits `UNKNOWN_TERRAIN` ("not finite") and returns `INCONCLUSIVE / DATA` (terrain-mask row INCONCLUSIVE, issue
  `INPUT_INVALID/NONFINITE_TERRAIN`) unless a genuine violation also exists (then FAIL). It never PASSes and never raises `ModelError`.

## Review wave: datasets / adapters / coverage hardening (D1-D16)
* DH-01 Nodata (D2): a declared nodata no longer exempts the data from the sentinel scan. Known void sentinels (-32768, -9999) present in the raw
  values but not named by the manifest or file declaration FAIL `nodata_declared`; the all-zero-border heuristic still runs only when nothing is declared.
* DH-02 Source URL (D5): `lineage_fields` also inspects the fragment and a wider credential-key list (pass/pwd/secret/session/bearer/jwt/x-goog,
  exact SAS keys sv/se/sp/sr/st/sas). Evidence `source_uri` is now scheme+host[:port]+path only (`checks.sanitized_source_url`): userinfo, query and fragment
  are dropped, because the registrar already refuses a query and a token may sit in any of them.
* DH-03 Latitude (D6): `check_transform_sane(gt, registration, bbox)` FAILs when the extent (cell edges included) leaves +-90 (1e-6 tolerance) or is non-finite.
  `ingest` publishes a non-finite/<=0 native resolution as `None` and an off-globe bbox as `None` (never NaN into the payload model).
* DH-04 Longitude (cheap items): a raster start must lie in the half-open domain [lo, hi) (360 / 180 rejected); `longitude_direction` must match the
  longitude axis of the geographic CRS (POSITIVE_WEST declared over a positive-east raster FAILs; the pipeline never mirrors longitudes).
* DH-05 `reference_radius_m` (D7): separate `REFERENCE_RADIUS_TOLERANCE = 0.1 %` of the body mean radius (Moon 1737 m, Mars 3396 m). CRS ellipsoid checks keep
  the 1 % `BODY_RADIUS_TOLERANCE` (WGS84 a is 0.11 % above the Earth mean radius, so a 0.1 % rule there would reject Earth). Consequence: an Earth RADIUS product with a
  WGS84 semi-major reference (6378137) fails; use the mean radius.
* DH-06 HTML sniff (D8): one helper `adapters/source_http/sniff.looks_like_html` (BOM, whitespace/NUL, any number of comments and `<? ?>` prologs, UTF-16/32,
  first 4096 bytes). `datasets.checks` delegates to it (datasets -> adapters already exists via the archive helper; adapters never import datasets). `download`
  buffers the first 4096 bytes before sniffing. PDS4 `.xml` label downloads pass `expected_magic=("<?xml", BOM+"<?xml")`; PDS3 labels, raw images and Diviner
  tables have no single signature, so none is passed for them (documented gap). `expected_magic` may be a tuple.
* DH-07 Transport (D9/D10/D16): credential-like request headers (policy `sensitive_headers` + names containing auth/token/secret/key/cookie/credential/password/signature)
  are stripped on every hop to a non-credential host. Allow-list is port-aware: `HttpPolicy.allowed_ports` (default {443}; 80 added with `allow_insecure`),
  `PORT_NOT_ALLOWED`. Unparseable URL / invalid port -> `INVALID_URL`; `redact_url` never raises; `Retry-After` accepts ASCII digits only.
* DH-08 Coverage policy (D3/D4): `coverage.enforce_source_policy` runs before any request for RESOLVE_COVERAGE and FETCH_SOURCE. Network adapters need
  `allow_network` AND an explicit `allowed_adapter_ids` entry; a non-empty `allowed_adapter_ids` also restricts local adapters (empty = no restriction for local sources,
  which are authorized by `local_dataset_ids`/`synthetic_fixture_ids`). `allowed_extents` (same body, planar union, ExtentBox convention inferred: any lon > 180 = ZERO_360)
  must contain the whole AOI. `synthetic_practice` outside synthetic mode -> BLOCKED `MODE_MISMATCH`. Zero-width / off-globe AOI -> BLOCKED `AOI_INVALID`.
  Network adapters outside live mode keep their previous block (`NETWORK_UNAVAILABLE`/`FETCH_NOT_AVAILABLE`), evaluated first.
* DH-09 Geometry (D13): `coverage_fraction` splits product boxes with west > east at the seam of their domain (0/360 when any longitude > 180, else -180/180).
  `validate_bbox` rejects west == east (a full circle is west+360).
* DH-10 Locks (D14): `verify_lock_integrity` also re-validates `manifest.yaml` and compares its canonical hash with `manifest_sha256` (MISSING / SOURCE_CHECKSUM_MISMATCH) and
  reports `SYMLINK` for a symlinked dataset directory, manifest or file. The existing lock test now writes `manifest.yaml` next to the data (a locked dataset always has one).
* DH-11 XML (D15): `xml_safe` decodes UTF-16/32 (BOM or NUL-pattern) before scanning for DOCTYPE/ENTITY and parses the decoded text; ASCII-incompatible declared
  encodings (anything other than UTF-8/ASCII/Latin-1/cp1252) are rejected.
* DH-12 NASADEM (D11/D12/D16): tile corner must be in lat -90..89, lon -180..179. `mosaic(max_cells=DEFAULT_MOSAIC_MAX_CELLS=64e6)` refuses before allocation
  (`MOSAIC_TOO_LARGE`). `decode` of a zip extracts to a temp dir (or `work_dir`) and never writes next to the source. Expansion rule: the 20x ratio cap is waived only for members
  whose declared size is exactly N*N or 2*N*N (N in {1201, 3601} or `expected_samples`); a constant ocean/flat tile compresses ~1000:1. Such a member still counts toward
  `max_total_bytes` and cannot grow past its declared size while copying.
* DH-13 Archives (D16): a name used both as a file and as a directory prefix (`x.hgt` + `x.hgt/y.hgt`) -> `ARCHIVE_DUPLICATE_MEMBER`; any failure while extracting removes the files (or the
  whole destination if it was created) written so far; OS write errors map to `ARCHIVE_WRITE_FAILED`. `asset_directory` rejects dot-only or >200 character granule names and requires
  the result to sit directly under `source_bytes/<adapter>`. `pds.index.validate_relative` uses `fullmatch` and rejects '.', empty segments and a trailing '/'.
* DH-14 User survey (D1): GDAL scale/offset from the file are applied once (`raw*scale+offset`, before unit conversion; nodata matched on raw values); `scale_applied`,
  `source_scale`, `source_offset` report it; a zero/non-finite scale is `METADATA_INCOMPLETE`.

## Review fixes (science worker, adversarial-review round)

* RV-01 Compare W1 (HIGH): the stored ANALYSIS_GRID zeroed `elevation_m` on every cell with `valid=false`, including land cells that merely lack a full
  3x3 neighbourhood (quality NO_FULL_SUPPORT, e.g. the raster border), and `histogram_at_support` area-averaged those zeros as data (flat control `grid-r0c2`
  W1 3.595 PASS vs the true 6.806). Fix at the source: `raster.store.build_analysis_grid` now keeps the real elevation for quality OK **and** NO_FULL_SUPPORT land
  cells and zeroes only cells without usable elevation (nodata, water, outside); the invariant check and docstring say so (guide 08 section 3 wording "invalid cells
  hold 0" is narrowed to "cells without usable elevation hold 0"; the member set and bytes layout are unchanged). The aggregation uses only `land & quality in (OK, NO_FULL_SUPPORT)`.
  Coverage of the re-derived histogram is the share of *eligible* coarse cells (the window's outer coarse ring cannot have a 3x3 neighbourhood in a window-only grid)
  that obtained a slope; the W1 policy gates on that (`SideEvidence.coverage`), not on the 60 m `valid_fraction` metric (0.969 passed while 0.56 of coarse cells were used).
  The target histogram's `valid_fraction` metric is gated as well (DECISION RV-05).
  Independent re-derivation (truth table `independent_w1`, now from the RAW GeoTIFF + water mask, only the window origin/size come from `meta.json`): W1 at 480 m
  A = coverage < 0.8 (UNKNOWN `INSUFFICIENT_VALID_DATA`), B (`grid-r0c0`) 4.3898 PASS, C (`grid-r0c2`) 6.8065 **FAIL `DISTRIBUTION_MISMATCH`** (was PASS 3.595), `grid-r1c0` 4.8065 PASS.
  Expected-row changes: (1) C's context row is FAIL (arch 40 section 5 says "per oracle", so the oracle decides; flat slope is all in bin [0,2) -> W1 = 6.806 > 6);
  (2) A's context row is UNKNOWN: the island window's moat leaves too few full-support 480 m cells (the old PASS used 0 m water cells as terrain). `test_pert_05` now asserts
  B PASS->FAIL under the shifted target and A UNKNOWN in both runs, each checked against the raw-raster oracle. Screening (halo-based, 6.8065 for C) agrees with the
  compare value for C; B/rolling differ slightly because screening has real halo data outside the window (4.454 vs 4.390) - the window-only value is what compare reports.
* RV-02 `CHARACTERIZE_TARGET` `valid_fraction` has the whole AOI as denominator (cells whose centre is in the AOI, counted over the unclipped range, in row chunks), so an AOI
  mostly outside the dataset is no longer "fully valid"; `< hard_block_valid_fraction` (0.05) blocks `INSUFFICIENT_VALID_DATA`.
* RV-03 Route rows (`route_dependent`): INCONCLUSIVE (any category) credits nothing (reserve + DATA + no value -> `ENERGY_MODEL_MISSING`); PASS/ROUTE_VERIFIED needs a
  `kind == VERIFICATION` handle (otherwise UNKNOWN `ROUTE_NOT_VERIFIED`, SC-11 NOT_ASSESSED); an `UNKNOWN_TERRAIN` violation -> UNKNOWN; any violation outside the row-scoped set
  {EXPOSURE_SHORTFALL, WAYPOINT_MISSED, TASK_CAPABILITY_MISSING, RETURN_NOT_COMPLETED, ENERGY_RESERVE_SHORTFALL, CLASS_DIVERSITY_SHORTFALL} (slope, forbidden terrain,
  discontinuity, stale hash, distance/duration/traversal budget) invalidates the route -> FAIL `ROUTE_FAILED` for every route row. Credit after an overall FAIL therefore survives only
  when all violations are row-scoped (arch 40 section 5: A after PROVE IT keeps R-TASKS/R-RESERVE PASS when only EXPOSURE_SHORTFALL fired). Tension recorded: arch 40 S-NO-ENERGY says
  "exposure/tasks PASS" for an INCONCLUSIVE/DATA verification; the review requirement (no PASS on INCONCLUSIVE) wins - those rows are UNKNOWN until the energy model exists. The existing
  test that expected a search-only (non-VERIFICATION) handle to PASS at S3 now expects UNKNOWN at S2.
* RV-04 `verified_route_supplied` needs outcome PASS/FAIL and no `UNKNOWN_TERRAIN`; energy/route-length dimensions read verifier metrics only from such a verification.
  A clearance requirement without `lower` is UNKNOWN (previously an `assert`).
* RV-05 W1 gates the target's `valid_fraction` metric (or `SideEvidence.coverage`) against `min_valid_fraction` when stated (missing -> not assessed, as before; the histogram's
  `valid_area_m2 > 0` check stays). Equality passes, below -> `INSUFFICIENT_VALID_DATA` ("Target valid coverage ...").
* RV-06 `COMPARE_REQUIREMENT` blocks (`INPUT_INVALID`, detail `EVIDENCE_WINDOW_MISMATCH`) when an `analyze-candidate` grid among the candidate evidence does not contain the candidate AOI
  (grid centre vs lon/lat box), including mixed evidence. Limit: summary/route handles carry no geometry, so only grid evidence is bound.
* RV-07 Compare gates SC-07/08/09 are evaluated: SC-07 from the quantity kinds of consulted + decisive verifier metrics (PROXY -> UNSATISFIED; ASSUMED without ASSUMPTION evidence -> NOT_ASSESSED);
  SC-08 needs a non-empty uncertainty note on every decisive metric; SC-09 checks version presence and the algorithm lock. Audit: `search_extent_recorded` is derived from the screening payload
  (screened_count > 0, finite non-degenerate box); mission sensitivity needs >= 2 COMPARISON evidences with distinct parameter hashes (one verdict is not a sensitivity analysis); an accepted
  ASSUMED metric still needs an uncertainty statement for SC-07 SATISFIED.
* RV-08 SC-10 matches source products as whole words (`[A-Z0-9]+` tokens) against the family table (added SRTMGL1/3, ASTGTM, MEGDR aliases); "raster" no longer matches ASTER.
* RV-09 Portfolio `NONE`/`GAP` coverage needs a matching row in every candidate window; any window without a row keeps the requirement `UNKNOWN`.
* RV-10 Config wiring: `thresholds.numeric_tolerance` (support-window bounds, W1 sum and support equality, compatibility comparisons), `energy_tolerance_wh` (`meets_reserve` default) and
  `grid.target_support_m.earth_default_m` (validated equal to the Earth measurement spec default, so the two copies cannot drift) are read from `algorithms.yaml` via the cached
  `config.default_thresholds()`. Routing-owned keys are listed in DEFECTS-FOUND.md (R-CFG-01).
* RV-11 `assert_crs_matches_body` also compares the semi-minor axis: an oblate Mars CRS (a=3396190, b=3376200) is rejected `BODY_MISMATCH` instead of being silently treated as the Mars sphere.
* RV-12 Connected zones of `ANALYZE_CANDIDATE` keep the default 18 deg cap: the kit input carries no rover, so honouring the rover cap (PRACTICE-LITE 12 deg) is impossible without a kit change
  (`CHANGE-REQUEST-analyze-rover-cap.json`). The payload now states the cap used and that reachability for a rover comes from route search.
