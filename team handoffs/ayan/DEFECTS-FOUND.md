# Defects found in other owners' areas (facade worker)

## D-01 `features/slope.py::aspect_from_gradient` can return exactly 360.0 (core, not mine)
`np.degrees(np.arctan2(-dz_dx, -dz_dy)) % 360.0` returns `360.0` when the angle is a tiny negative number (e.g. `-1e-15 % 360.0 == 360.0`),
violating the documented `[0, 360)` range; `raster.store.build_analysis_grid` then raises `RasterError("aspect_deg must lie in [0, 360)")`.
Reproduction: analyse window `grid-r2c2` of the default practice grid through `ANALYZE_CANDIDATE` (before the workaround it came back
`BLOCKED SOURCE_CONTENT_INVALID`). Workaround: `science/ops/terrain.py::clean_aspect` folds values `>= 360` back by 360 before building the grid.
Proper fix (owner of `features/slope.py`): `aspect = np.where(aspect >= 360.0, 0.0, aspect)` after the modulo.

**RESOLVED**: the fix is applied at the source in `aspect_from_gradient` (regression test `test_d01_aspect_never_rounds_up_to_360` in `tests/unit/science/test_features.py`) and the `clean_aspect` workaround has been removed from `ops/`.

## R-CFG-01 Config values never read by routing-owned code (for the routing worker)
`config/algorithms.yaml` keys that only routing/ops-route code could consume and that nothing reads today (checked with grep on `src/analogforge`):
* `route_search.max_edge_traversals` (2): the search/verify hard-code the traversal limit instead of reading it.
* `thresholds.hazard_min_intersection_m` (1e-9): the verifier/supercover use their own epsilon.
* `design_defaults.auto_waypoints.w1_min_edge_fraction` (0.15), `w1_max_edge_fraction` (0.30), `w2_min_from_w1_edge_fraction` (0.10), `band_neighbourhood_cells` (5),
  `tolerance_cells` (1): `routing/waypoints.py::auto_waypoints_v1` embeds the same literals.
* `energy_defaults.*` (rolling_coefficient 0.06, drive_efficiency 0.65, idle_power_w 35, science_task_wh 10, roughness_multiplier 1.0, uncertainty_fraction 0.25,
  calibration_status, gravity_mps2): no code path uses them (rovers carry their own `energy_model`); either feed them to DESIGN_BENCHMARK as the documented proposals or delete them.
Science-owned keys `thresholds.numeric_tolerance`, `thresholds.energy_tolerance_wh` and `grid.target_support_m.earth_default_m` are now wired (DECISIONS RV-10).
Also found: `tests/contracts/kit/test_kit_contracts.py:222` has an E501 (121 > 120) - kit file, left untouched.
