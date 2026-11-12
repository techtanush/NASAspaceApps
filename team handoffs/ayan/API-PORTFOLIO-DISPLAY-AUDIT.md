# API-PORTFOLIO-DISPLAY-AUDIT: portfolio, display layers, audit evidence

Pure functions under `analogforge.science` (no environment, network, DB, clock). They return kit payload models; the
facade wraps them in `ScienceComputationResult` and builds evidence drafts (algorithm ids `optimize-portfolio`,
`build-display-layers`, `audit-evidence`). Errors derive from `science.errors.ScienceError` (`.code`, `.detail_code`).
Tests: `tests/integration/science/{test_portfolio,test_display_layers}.py`, `tests/unit/science/test_audit.py`.

## portfolio (`science/portfolio.py`)
* `optimize_portfolio(inputs: OptimizePortfolioInput, *, portfolio_evidence: EvidenceRef, mode=None, evidence_modes=(), mission_revisions=(), check_cancelled=None) -> OptimizePortfolioPayload`.
  Pass `mode` (request mode) with the modes of the input evidence and the mission revisions seen in the inputs to get
  fixture-7 rejection (`INPUT_INVALID`, detail `MODE_MISMATCH` / `REVISION_MISMATCH`); also exposed as `check_single_scope`.
* More than `MAX_ELIGIBLE` (12) eligible windows (windows covering at least one item) raises `ScienceError(code="RESOURCE_LIMIT")`
  -> facade returns BLOCKED. Other input errors (unknown/duplicate window or requirement, verification for an unknown window) are `INPUT_INVALID`.
* Coverage rules: row `PASS`, no open blocking critic issue; route-dependent observables (`catalog.ROUTE_DEPENDENT_OBSERVABLES`) also need
  `FINAL` and, when `verification_by_window_id` has the window, outcome `PASS`. Coupled groups (`parameters.co_location_group`) are one joint
  item per window: all member rows PASS+FINAL and that window's verification PASS. `NOT_NATURALLY_REPRODUCIBLE` -> `GAP`, never optimised.
* `lexicographic_objective = [mandatory_weight, optional_weight, -site_count, evidence_rank]` (all maximised); `objective_value = mandatory + optional`.
  Evidence rank per covered item: 3 verified, 2 FINAL PASS, 1 PRELIMINARY PASS. Final tie: smallest sorted `window_id` tuple.
* Assignments are sorted by requirement id and `residual_requirement_ids` lists every non-FULL requirement (sorted), so output is
  independent of input order. Non-FULL states: PARTIAL (selected site has a PARTIAL/PASS-but-uncovered row), GAP, NONE (every row in the
  selected sites - or all candidates when the selection is empty - is an unblocked FAIL), else UNKNOWN.

## display (`science/display/`, helpers in `rendering/tiles/`)
* `LayerRaster(kind, grid: AnalysisGridSpec, values (NaN = invalid), unit, support_scale_m, source_evidence, synthetic, attribution, categorical, class_labels, limitations)`;
  `layer_from_analysis_grid(grid, "ELEVATION"|"SLOPE", source_evidence=, synthetic=, attribution=)` masks invalid cells.
  ROUGHNESS/THERMAL/MINERAL layers are built by the facade from the evidence it reads (categorical ids: `categorical=True`, never blended).
* `render_layer(layer) -> RenderedLayer(draft, png, rgba)` (no I/O); `build_display_layers(layers, scratch_dir) -> BuiltLayers(payload: BuildDisplayLayersPayload, artifacts: tuple[ArtifactDraft])`
  writes `display/display-<kind>.png` (role `DISPLAY_IMAGE`, `image/png`, `body`, `crs_wkt`, `support_scale_m`). Layer `local_key = display-<kind>`,
  `image_artifact_key = display-<kind>-png`. The facade supplies the evidence draft(s) that `source_evidence` refs point to.
* EARTH: Web-Mercator image (EPSG:3857 affine, GDAL order), `earth_corners` NW,NE,SE,SW lon/lat of the image rectangle; pixels sample the
  nearest containing analysis cell (outside the footprint = transparent). MOON/MARS: planar image on the grid's own CRS (`assert_crs_matches_body` rejects Earth CRS),
  affine = grid geotransform at the display pixel size, `earth_corners=None`. Small grids are upscaled by an integer nearest factor (target 256 px); grids above 2048 px are decimated by stride.
* Invalid cells have alpha 0 and RGB 0. Legend = the classes that colour the image (SLOPE fixed classes 0-6-12-18-24-30-90 deg, lower-inclusive; ELEVATION 8 / ROUGHNESS 5 / THERMAL 6 equal-interval classes; MINERAL one class per id present).
* Attribution: synthetic -> `"SYNTHETIC PRACTICE DATA — not terrain of this location"` first; real layers must pass the manifest citation/license note (`ScienceError` otherwise).
  Limitations always include "Display smoothing adds no resolution." Geometry helpers: `apply_affine`, `mercator_to_lonlat`, `lonlat_to_mercator`, `earth_corners_from_affine`.
* PNG bytes are deterministic (`rendering.tiles.png.encode_png_rgba`: fixed compression, no metadata chunks); `decode_png_rgba` for tests.

## audit (`science/audit.py`)
* `audit_evidence(inputs: AuditEvidenceInput, *, mode, evidence: Sequence[EvidenceHandle], config: ScienceConfig, requirements: Mapping[str, Requirement] | None, source_families: Mapping[UUID, frozenset[str]] | None, discovery: Mapping[UUID, DiscoveryEvidence] | None) -> AuditEvidencePayload`.
  One `ClaimGateEvidence` per claim with gates `AUDIT_GATES` = SC-02..SC-11, SC-13 (in that order), findings sorted by id. It never decides publication.
* The facade must supply `requirements` (the request carries only `requirement_id`; SC-04 needs the window) - see DECISIONS A-02. Without it SC-04 is `NOT_ASSESSED`.
* `check_set` mapping: provenance -> SC-02/SC-09, units|crs -> SC-03, scale -> SC-04, coverage -> SC-05, proxies -> SC-07, uncertainty -> SC-08, independence -> SC-10/SC-11;
  unrequested gates are `NOT_ASSESSED`. SC-06 and SC-13 are always evaluated.
* `SCALE_MISMATCH` (BLOCKING): the claim's evidence scale is finer or coarser than the requirement window (COMPARISON evidence defines the claim scale when cited, otherwise all scaled evidence).
* SC-11: VERIFICATION claims need VERIFICATION evidence whose `algorithm_id` differs from the cited `search-route` evidence (equal id, or search cited alone = `UNSATISFIED` + `ROUTE_NOT_VERIFIED`).
* SC-10: needs >=2 distinct source products among the cited evidence; products of one ancestry family (`ANCESTRY_FAMILY_BY_PRODUCT`, NASADEM+SRTM) = `UNSATISFIED` + `SHARED_ANCESTRY`.
  Product tokens come from `source_families[evidence_id]` when the facade knows them (preferred) else from handle limitations / `local_key_origin` / algorithm id text.
* SC-13: `discovery_evidence_from_screening(payload, reference_set_id=, mission_sensitivity_evidence_ids=)` builds the `DiscoveryEvidence` the facade passes per screening evidence id.
