# API-CORE: geometry, raster, features, energy, comparison, qualification, compatibility, config

All modules are under `analogforge.science` and are pure (no environment, network, database, wall clock). Arrays are
`numpy` float64/bool/uint8; "NaN = invalid" inside features, the ANALYSIS_GRID stores `0` for invalid slope/elevation.
Errors derive from `science.errors.ScienceError` (`.code` canonical, `.detail_code` fine-grained): `GeometryError`
(`UNSUPPORTED_CRS`; detail `BODY_MISMATCH|FRAME_UNRESOLVED|DISTORTION_EXCEEDED`), `RasterError`, `ScaleError`
(`SCALE_INCOMPATIBLE`), `ModelError`, `ConfigError`. Run commands from `analogforge/`; tests live in
`tests/unit/science/test_{geometry,features,energy,comparison,qualification,compatibility}.py`.

## config (`science/config.py`, files `config/{algorithms,candidates,datasets}.yaml`)
* `load_config(config_dir=None) -> ScienceConfig` parses the three YAML files strictly (unknown keys rejected), caches by
  content hashes, returns an immutable object. `ScienceConfig.algorithm_config_sha256 == canonical_sha256(parsed algorithms.yaml)`.
* `config_for_hash(sha) -> ScienceConfig | None`; `cfg.verify_pin(sha | None) -> bool` (compare to `ScienceOptions.algorithm_config_sha256`).
* `cfg.policy(policy_id) -> ObservablePolicy | None`, `cfg.policy_sha256(policy_id) -> str | None`,
  `cfg.algorithm_version(algorithm_id) -> str`, `cfg.measurement_spec(spec_id)`.
* Sections: `cfg.algorithms.{algorithm_lock, measurement_specs, observable_policies, grid, route_search, energy_defaults,
  design_defaults (incl. auto_waypoints, science_task_required_capability), thresholds, fixtures}`,
  `cfg.candidates.{search_region_sets, reference_sets}`, `cfg.datasets.adapters`.
  `thresholds`: `default_cap_deg 18, min_valid_fraction .8, hard_block_valid_fraction .05, water_only_fraction .98,
  medium_confidence_min_coverage .9, flat_gradient_tolerance, hazard_min_intersection_m, numeric_tolerance,
  energy_tolerance_wh, max_linear_distortion .01`.
* `candidates.yaml` `practice-earth-grid-v1` is a `FIXED_GRID` (EPSG:32612, `sw_easting_m`, `north_northing_m`, 3x3 windows with
  `negative_control` flags); `local-dataset-grid-v1` is a `GENERATED_GRID` recipe (NW row-major, `coarse_windows_max`).

## provenance / hashing (`provenance.py`, `hashing_utils.py`)
* `hashing_utils.parameters_sha256(*, operation, algorithm_id, algorithm_version, parameters, input_hashes, seed, algorithm_config_sha256) -> str`
  (canonical hash of the 08 section 1 recipe; input hashes sorted); `array_sha256(arr)`; `payload_bytes_sha256(bytes)`.
* `provenance.write_scratch_artifact(scratch_dir, *, local_key, relpath, data, media_type, role, body=, crs_wkt=, support_scale_m=, metadata=) -> ArtifactDraft`;
  `write_payload_artifact(scratch_dir, *, local_key, relpath, payload, role=DERIVED_JSON, body=)` (canonical JSON bytes);
  `evidence_draft(*, mode, local_key, kind, body, algorithm_id, algorithm_version, parameters_sha256, license_note, artifact=, parent_local_keys=, dataset_product_id=, dataset_version=, source_uri=, native_resolution_m=, comparison_scale_m=, aoi_bbox=, metrics=, limitations=) -> EvidenceDraft`
  (enforces `SYNTHETIC_*`/`source_uri=None` naming; parents sorted+deduped); `synthetic_product_id(dataset_id)`;
  `check_source_naming(mode, product_id, source_uri)`; `safe_relpath(relpath)`; constants `SYNTHETIC_LICENSE_NOTE`.

## geometry (`geometry.py`)
* `body_geometry(body) -> BodyGeometry` (Earth WGS84, Moon 1737.4 km, Mars 3396.19 km spheres); `body_distance_m(body, lon1, lat1, lon2, lat2)`;
  `convert_latitude(lat, src, dst, geometry)`.
* Longitude: `normalize_longitude(lon, convention)`, `unwrap_bbox(bbox, convention)` (continuous interval, may exceed 360),
  `split_bbox_at_antimeridian(bbox, convention) -> list[bbox]`, `bbox_longitude_centre`, `to_positive_east`.
* Frames: `projected_frame_for_aoi(body, bbox, convention="NEG180_180", *, max_linear_distortion=0.01) -> ProjectedFrame`
  (Earth UTM/UPS/LOCAL_TM; Moon/Mars equirectangular or polar stereographic on the body sphere, named WKT, distortion-checked);
  `frame_from_crs_wkt(body, wkt)`; `assert_crs_matches_body(body, wkt)` (rejects Earth CRS for planets: `BODY_MISMATCH`).
* Transforms: `lonlat_to_xy(frame, lon, lat)`, `xy_to_lonlat(frame, x, y, convention)`, `densified_boundary_lonlat`,
  `bbox_to_projected_bounds(frame, bbox, convention)` (densified boundary: polar wedges/wrap), `projected_bounds_to_bbox(frame, bounds, convention)`.
* `AnalysisGridSpec(body, crs_wkt, origin_x_m(west edge), origin_y_m(north edge), cell_size_m, width, height)`: `.bounds`, `.geotransform` (GDAL order),
  `.cell_centre(r,c)`, `.centre_coordinates()`, `.index_of(x,y) -> (row,col)|None`, `.window(r0,c0,h,w)`, `.aggregated(factor)`, `.pixel_geometry()`, `.cell_area_m2`.
  `grid_from_bounds(frame, bounds, cell, snap=True)`, `grid_for_bbox(frame, bbox, cell, convention, snap=True)`, `pixel_to_world_gdal(grid)`, `world_to_pixel_continuous`.
* `PixelGeometry(dx_dcol, dy_dcol, dx_drow, dy_drow)` (+ `.north_up(cx, cy=None)`, `.rotated(cx, cy, deg)`, `.from_geotransform(gt)`): metric steps (east, north) per column/row step; anisotropic and rotated rasters supported.

## raster (`raster/*`)
* `masks`: `nodata_mask(values, nodata)`, `usable_mask(values, nodata, water, extra_invalid)`, `full_support(usable, window_cells=3)`
  (border = missing), `dilate(mask, radius_cells)`, `dilate_metres(mask, radius_m, cell_size_m)` (rounds up), `fraction(mask, within=None)`.
* `normalize`: `normalize_elevation(raw, *, quantity ELEVATION|RADIUS, units m|km, scale_factor, offset, scale_already_applied, reference_radius_m, nodata_value) -> (metres NaN-missing, missing mask, NormalizationRecord)`
  (scale/offset once, radius->height once, nodata matched on raw); `looks_like_radius_not_height`;
  `aggregate_blocks(values, valid, factor, min_valid_fraction=1.0)` (area average, no hole bridging), `aggregate_any(mask, factor)`,
  `aggregate_categorical_mode(ids, factor, nodata_id)` / `class_area_fractions` (ids never averaged).
* `source`: `read_gdal_raster(path, band, variable) -> RawRaster` (raw, never scaled), `native_cell_size_m(raw, body)`,
  `resample_to_grid(raw, values_m, missing, dst_grid, *, src_cell_size_m, min_valid_fraction=1.0)` (area average, refuses to upsample),
  `SourceRaster(grid, values, nodata, native_resolution_m, support_scale_m, vertical_reference, water=, product_id=, synthetic=, source_hashes=)` with `.crop(r0,c0,h,w)`.
* `mosaic`: `mosaic_tiles([Tile(name, values, origin_x_m, origin_y_m, cell_size_m)]) -> MosaicResult` (shared border samples once; `REGISTRATION_OFFSET`, `SEAM_CONFLICT`), `check_control_points(grid, values, [ControlPoint])`.
* `store` (ANALYSIS_GRID, media type `application/x-npz`, deterministic ZIP, 1980-01-01 stamps, sorted, stored):
  `build_analysis_grid(spec, *, elevation_m, valid, land, slope_deg, aspect_deg, quality, source_evidence_ids, algorithm_id, algorithm_version, parameters_sha256) -> AnalysisGrid`
  (canonicalises invalid cells to 0), `encode_analysis_grid(grid) -> bytes`, `analysis_grid_sha256(grid)`, `write_analysis_grid(path, grid) -> (sha, size)`,
  `decode_analysis_grid(bytes)` / `read_analysis_grid(path) -> AnalysisGrid` (validates members, dtypes, invariants; the ONLY parser).
  `AnalysisGrid`: `.meta`, `.elevation_m .valid .land .slope_deg .aspect_deg .quality`, `.spec`.

## features (`features/*`)
* `slope`: `analyze_surface(elevation, geometry, *, nodata=, water=, outside_source=, flat_gradient_tolerance=) -> SurfaceAnalysis(usable, valid, land, slope_deg(NaN invalid), aspect_deg, quality)`
  - the one-call pipeline: compute over the WHOLE source, then crop to windows (real halo). Lower level: `compute_slope_aspect(elev, usable, geometry)`,
  `plane_fit_gradient`, `plane_stencil(geometry)`, `slope_from_gradient`, `aspect_from_gradient`, `directional_grade_deg(dz_dx, dz_dy, heading_east, heading_north) -> (long, cross)`.
  Aspect = downslope azimuth clockwise from north, NaN when flat.
* `roughness`: `detrended_rms_height_m(elev, usable, window_cells) -> (rms, valid)`, `tpi_m(...)`, `roughness_metric_id(window_cells, cell_m)` -> `detrended_rms_height_m@<window_m>`, `relief_metric_id`.
* `relief`: `robust_relief_m(elev, usable, window_cells, q_low=.05, q_high=.95) -> (relief, valid)`.
* `histogram`: `SLOPE_HIST_EDGES`, `SLOPE_HIST_CENTRES`, `bin_centres(edges)`, `area_weighted_histogram(values, valid, cell_area_m2, edges=, last_bin_inclusive=True) -> HistogramData(edges, area_m2, .area_fraction, .valid_area_m2)`,
  `to_port_histogram(data, *, support_scale_m, metric_id=, unit=) -> ports.Histogram`, `band_area_fraction(values, valid, lo, hi, cell_area, upper_inclusive=False) -> float | None`,
  `slope_area_metric_id(lo, hi)` -> `slope_area_fraction:12-18`, `band_label`, `weighted_quantile`, `slope_statistics -> {p05,p50,p95,mean,max}`.
* `connected`: `safe_mask(slope, valid, land, cap_deg)` (inclusive cap), `label_components(mask, 4|8)`,
  `connected_zones(safe, slope, cell_area_m2, bands=[Band(lo,hi,upper_inclusive)], *, start_cell=, min_cells=, connectivity=8) -> (list[ZoneStats], labels)`
  (sorted by -area then first cell; ids `zone-1..`; per-zone `band_area_m2["12-18"]`, `contains_start`), `largest_component(safe)` (tie: smallest row-major first cell), `to_port_zone`.
* `coverage`: quality codes `QUALITY_{OK 0,NODATA 1,WATER 2,NO_FULL_SUPPORT 3,OUTSIDE_SOURCE 4}`, `classify_cells(nodata, water, valid, outside=)`,
  `coverage_summary(quality) -> CoverageSummary(valid_fraction, water_fraction, nodata_fraction, no_support_fraction, ...)`, `is_water_only(summary, water_only_fraction)`.
  `valid_fraction` = valid land with full 3x3 support / window area (halo cells count as NOT valid; `land_data_fraction` adds them back).

## energy (`energy.py`, `earth-simple-v1`, Earth gravity 9.80665 only)
* `EnergyParams(mass_kg, nominal_speed_mps, battery_wh, min_reserve_pct, rolling_coefficient, drive_efficiency, idle_power_w, science_task_wh, roughness_multiplier, uncertainty_fraction, calibration_status, gravity_mps2=9.80665)`
  (validated, `ModelError` on bad values); `EnergyParams.from_model(model|None, *, mass_kg, nominal_speed_mps, battery_wh, min_reserve_pct) -> EnergyParams | None`;
  `EnergyParams.from_spec(EnergySpec) -> EnergyParams | None` (None = no model = unknown); `.usable_energy_wh`.
* `edge_energy(params, d_xy_m, dz_m, *, surface_slope_deg=None) -> EdgeEnergy(rolling_wh, climb_wh, drive_wh, drive_time_s, d_s_m)` (no downhill credit; d_s = hypot).
* `route_energy(params, [(d_xy, dz), ...], *, tasks_completed=0, dwell_s_total=0.0) -> RouteEnergy(nominal_wh, conservative_wh, reserve_pct, idle_wh, tasks_wh, duration_s, ...)`;
  `EnergyAccumulator(params)` (`add_edge`, `add_tasks(count, dwell_s)`, `total()`) for telemetry; `evaluate_route_energy(None, ...) -> None`;
  `reserve_pct(battery, conservative)` (negative allowed), `meets_reserve(params, conservative_wh, tol=1e-9)` (equality passes),
  `flat_lower_bound_wh(params, distance_xy_m, *, tasks=0, dwell_s_total=0.0)` (admissible lower bound for lossless energy certificates).
  Oracle `catalog.ENERGY_ORACLE_FLAT_1000M` reproduced to <= 1e-8 Wh (actual error ~1e-14).

## comparison + qualification + compatibility
* `comparison.scale`: `common_support_m(*native, requested_m=)`, `aggregation_factor(native, effective)` (refuses finer/non-multiple), `plan_support(native, requested) -> SupportPlan`,
  `check_support_window(support_m, min_m, max_m) -> SupportVerdict(supported, reason)`.
* `comparison.w1`: `binned_w1(frac_a, frac_b, centres)`, `w1_from_histograms(a, b) -> W1Result(w1_deg, centres_deg, support_scale_m)` (needs equal edges+support), `empirical_w1(...)` (independent exact).
* `comparison.compare.compare_requirement(CompareInputs, config) -> ComparisonOutcome` (never raises for data problems).
  `CompareInputs(requirement, policy_id, mode, candidate: SideEvidence, target: SideEvidence, verification: VerificationSummary | None)`;
  `SideEvidence(handles: tuple[EvidenceHandle,...], histogram: Histogram | None)` - the facade reads the slope histograms from the evidence artifacts.
  Expected metrics: candidate `slope_area_fraction:<lo>-<hi>`, `valid_fraction`, `mineral_valid_fraction`, `min_temperature_k`; verification `unique_exposure_m:<req>`, `tasks_completed`, `reserve_pct`, `route_distance_m`.
  `ComparisonOutcome`: `.status .reason_code .evaluation_stage .confidence .comparison_scale_m .measured_value .measured_unit .threshold_lower/upper .covered_subcriteria .uncovered_subcriteria .explanation .limitations .gates (SC-02..SC-11, SC-13) .validation_level .metrics (for the COMPARISON EvidenceDraft) .consulted_evidence_ids .policy_sha256`,
  and `.to_payload(comparison_evidence: EvidenceRef) -> CompareRequirementPayload`. Policy functions are in `comparison.policies.POLICY_FUNCTIONS` (keyed by policy id).
* `qualification`: `evaluate_threshold(value, operator, lower, upper, tolerance=0) -> ThresholdVerdict` (inclusive; `RequirementUnderspecifiedError`), `interval_decision(...)` (11 section 4),
  `confidence_label(*, adequate, direct_evidence, coverage, uncertainty, assumed_parameters=False, medium_min_coverage=.9)` (never UNASSESSED; HIGH only with quantified uncertainty),
  `strict_coverage(rows) -> StrictCoverage` (UNKNOWN stays in the denominator; GAP reported separately).
* `compatibility.assess_compatibility(rover, requirements, *, verification=None, constraints=None, candidate_support_scale_m=None, task_capability="geological_sampling", evidence=()) -> CompatibilityResult(preliminary, dimensions)`;
  dimension ids `max_surface_slope_deg, energy_reserve_pct, ground_clearance_m, max_obstacle_height_m, required_capability:<cap>, route_length_m (only if max_route_m)`;
  helpers `required_capabilities(requirements, constraints)`, `verified_route_supplied(verification)` (a `route_distance_m` metric must exist).
  Facade wraps: `AssessCompatibilityPayload(preliminary=..., dimensions=list(...), compatibility_evidence=EvidenceRef(local_key=...))`.
