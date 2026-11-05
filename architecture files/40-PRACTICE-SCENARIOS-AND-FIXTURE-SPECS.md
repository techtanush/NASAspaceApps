# Practice scenarios and fixture specifications

Everything the product needs *except NASA data* is rehearsed with **synthetic practice data** that is complete enough to exercise every code path: both bodies, requirement statuses, routes that fail and pass, nodata, water, categorical minerals, thermal, rover conflicts. This document defines those fixtures as **properties and oracles**, not as code, so that three branches implement and test against the same truth without sharing implementation.

All practice data is labeled `SYNTHETIC_PRACTICE` (`is_synthetic: true`, `dataset_product_id` starting `SYNTHETIC_`, mode `synthetic`). It is never labeled NASA, NASADEM, MOLA or LOLA. Its map location is arbitrary and every layer attribution reads *"SYNTHETIC PRACTICE DATA — not terrain of this location"*.

## 1. Anti-hardcoding rule

Practice outcomes must **emerge from computation on the generated rasters/graph**. For every outcome in §5–§7 an automated *perturbation test* changes a generator parameter or an input threshold and asserts the outcome changes as predicted (§8). A solution that returns the table below without computing it fails the perturbation tests and the merge gate.

## 2. Common geometry

* Practice Earth grid: `catalog.PRACTICE_GRID_*` — EPSG:32612 (UTM 12N), 60 m cells, 3×3 windows of 64×64 cells (3,840 m each), whole grid 192×192 cells (11,520 m). South-west corner easting `494240`, grid north edge northing `3900000`. Window `grid-r<R>c<C>` (row 0 is north): easting `494240 + C·3840 … +3840`, northing `3900000 − R·3840 − 3840 … 3900000 − R·3840`. WGS84 window bboxes are computed with pyproj from these extents (the tests recompute them independently).
* Elevation in metres relative to `SYNTHETIC_REFERENCE_ONLY`; nodata `-32768`; water is a separate `uint8` mask raster on the same grid (`1` = water).
* Slopes are surface slope from the 3×3 least-squares plane fit ([10](10-TERRAIN-AND-PLANETARY-COMPARISON.md) §4). "Band" = surface slope in `[12°, 18°)` (lower inclusive, upper exclusive; the final-band rule in 12 §4 applies to route exposure with the contract band `[12,18]`). "Cap" = rover maximum safe slope (18° for ARES-1). Unless stated otherwise a slope is exact on the **interior** of a planar facet (cells whose full 3×3 neighbourhood lies in the facet); transition cells are mixed.
* Seeds: every generator is deterministic from `seed = 20261105` plus the dataset id; generators record `generator_id`, version and seed in evidence parameters.

## 3. Datasets (`ports.datasets.DatasetManifest` each)

| dataset_id | body / role | content |
| --- | --- | --- |
| `practice-mars-target-v1` | MARS / `TARGET_TERRAIN` | 128×128, 480 m posting, planetary equirectangular CRS on the Mars-2000 sphere (WKT in manifest), `ELEVATION` m, vertical ref `SYNTHETIC_MARS_REFERENCE_SPHERE_3396190M`, AOI `[137,-5,138,-4]`. Alternating-sign planar strips so area fractions of surface slope are **0.40 at 3°, 0.30 at 7°, 0.20 at 14°, 0.10 at 22°** (each ±0.03 after transition smearing; independent oracle: strip widths in cells / 128). |
| `practice-moon-target-v1` | MOON / `TARGET_TERRAIN` | 160×160, **960 m** posting (= 16 Earth cells, so the common support divides the Earth grid exactly), **south-polar stereographic** CRS on the Moon-2000 sphere, quantity `RADIUS`, units `m`, stored as `int16` with `scale_factor=0.5`, `offset=1737400`, `scale_already_applied=false`, `reference_radius_m=1737400` (exercises radius→height and "apply scale once"). AOI is the wedge `[-10,-89.5,10,-87.5]` (exercises polar geometry and longitude wrap). Area fractions of slope over the AOI wedge: **0.50 at 2°, 0.30 at 6°, 0.15 at 13°, 0.05 at 20°** (±0.03). Recipe: rings of constant radial slope about the pole; ring area ∝ r², so with the wedge spanning r ≈ 15.2–75.8 km the boundaries fall at r ≈ 54.7, 68.1 and 74.0 km. |
| `practice-moon-thermal-v1` | MOON / `LUNAR_THERMAL` | same polar grid, `TEMPERATURE_K` kelvin, minimum 88 K inside a cold-trap disc, 160–250 K elsewhere. **Not bound** in the default Moon scenario; bound only by a perturbation test. |
| `practice-earth-grid-v1` | EARTH / `EARTH_TERRAIN` | the 192×192 grid of §4 (elevation GeoTIFF + `…-water.tif` listed with `role: MASK`). |
| `practice-earth-minerals-v1` | EARTH / `EARTH_MINERAL` | categorical `uint8` class ids 1–4 (dictionary in `manifest.notes`), 60 m grid, valid only over windows `grid-r0c0` (valid fraction 0.60 within the window) and `grid-r2c2` (0.85); nodata `0`. **Used in `local-dataset-practice-v1` only.** Class ids are categorical: no interpolation, nearest/area-fraction only. |

The same generators back the **fixture-id** sources used by the synthetic (non-file) scenarios: `SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id=catalog.FIXTURE_*)` and `kind="LOCAL_DATASET"` for the same content **must produce identical metrics** (parity test PARITY-01).

## 4. Practice Earth grid: window specification

Geometry is free; the **properties** below are binding and are verified by an independent checker (plain `scipy.ndimage` connected components, not the solver). `f_band` = fraction of *valid land* cells whose surface slope lies in `[12°,18°)`.

| Window (`catalog.*`) | Role in the story | Properties |
| --- | --- | --- |
| `grid-r0c0` (`WINDOW_B_CORRIDOR`) | Feasible corridor — route PASS expected | `f_band ∈ [0.07, 0.15]`. A **connected** ramp of slope **15° ± 0.5°** (interior), ≥ 8 cells wide, runs ≥ 40 cells; everything else ≤ 6°. All cells slope ≤ 18° (corridor is inside the safe component). The `auto-waypoints-v1` start and tasks lie in the largest safe component; the start-reachable component contains ≥ 400 m of band-edge length. **Binding first-attempt property:** the rule places `W1`/`W2` on non-band cells within 2 cells of the corridor and on the same side as `S`, so the minimum-distance `WAYPOINT_RETURN` loop (found by an independent 8-neighbour Dijkstra in the checker) has unique band exposure **< 100 m** (attempt 1 genuinely FAILs `EXPOSURE_SHORTFALL`), while a closed route with ≥ 100 m unique band exposure within `max_distance_m` exists. |
| `grid-r0c1` (`WINDOW_A_MESA`) | Statistically promising, **untestable** (island) | `f_band ∈ [0.25, 0.60]` over valid land. The band area is a 15° ± 0.5° plateau/island fully enclosed by a **water moat ≥ 4 cells wide**; mainland slope ≤ 6°; the start-reachable component (land, valid, slope ≤ 18°) contains **zero** band cells. Mainland area > island area, so the largest safe component is the mainland. |
| `grid-r0c2` (`WINDOW_C_FLAT`) | Negative control | `f_band = 0`; max slope ≤ 3°. |
| `grid-r1c0` (`WINDOW_ROLLING_1`) | filler | `f_band ∈ [0.02, 0.04]` |
| `grid-r1c1` (`WINDOW_WATER`) | excluded `WATER_ONLY` | ≥ 98 % water cells |
| `grid-r1c2` (`WINDOW_NODATA_STRIPE`) | excluded `INSUFFICIENT_VALID_DATA` | valid fraction **0.50–0.60** (a wide N–S nodata band); `min_valid_fraction` policy is 0.80 |
| `grid-r2c0` (`WINDOW_ROLLING_2`) | filler | `f_band ∈ [0.01, 0.03]` |
| `grid-r2c1` (`WINDOW_GENTLE`) | ranked 6th, not detailed | `f_band ≤ 0.01` |
| `grid-r2c2` (`WINDOW_KNOWN_REFERENCE`) | `KNOWN_ANALOG` reference | `f_band ∈ [0.06, 0.10]` as a small 15° plateau **enclosed by a water moat ≥ 4 cells wide** (like `A`, smaller); the start-reachable component contains **zero** band cells, so an exposure route there is infeasible; listed in `practice-reference-set-v1` |

**Replan candidate picker (normative):** when a diagnosis recommends `NEW_CANDIDATE`, the platform considers already-analyzed candidates not yet attempted whose mandatory availability rows (`R-SLOPE-AVAILABILITY`) are **not FAIL** (eligibility), ordered by (1) `ConnectedZone.band_area_m2` of the zone with `contains_start=true` for the requirement's band, descending; (2) screening rank ascending; (3) `window_id`. Properties above guarantee `B` (start-zone band area > 0, and larger than any `ROLLING_*`) is chosen: `KNOWN` is eligible but has start-zone band area 0, and `ROLLING_*`/`C` fail availability. This holds regardless of the relative screening order of `A`, `B`, `KNOWN`.

### 4.1 Screening result (`SCREEN_CANDIDATES`, 9 windows, `max_detailed=6`)

Ranking key (ascending): `deficit = max(0, 0.05 − f_band)`; then Wasserstein-1 distance to the target slope histogram at 480 m support; then `window_id`. Expected:

* `screened_count = 9`; `stop_reason = GRID_EXHAUSTED`.
* Excluded: `grid-r1c1` (`WATER_ONLY`), `grid-r1c2` (`INSUFFICIENT_VALID_DATA`). Ranked: 7 windows.
* Zero-deficit windows (`A`, `B`, `KNOWN`) rank 1–3 in an order determined by the W1 distance (tests assert **set** membership, not their relative order); then `ROLLING_1`, `ROLLING_2`, `GENTLE`, `C`.
* Shortlist = ranks 1–5 plus the labeled negative control `C` (`is_negative_control=true`) = **`{A, B, KNOWN, ROLLING_1, ROLLING_2, C}`**; `GENTLE` has `excluded=false`, `rank=6`, not detailed (reason `BELOW_SHORTLIST_CUTOFF`).
* Origins: `KNOWN` → `KNOWN_CONTROL` / `KNOWN_ANALOG`; `C` → `SYNTHETIC_CONTROL`; `A`, `B`, others → `DISCOVERED` / `NOT_IN_REFERENCE_LIST`. At least one `DISCOVERED` candidate outside the reference set is analyzed (PR-033). No candidate is called "new discovery".
* `feature_scores` are mission-relevant deficits; no field is a similarity percentage.

## 5. Qualification truth table (Mars practice contract: `mission-mars-mobility.json`, ARES-1)

`ANALYZE_CANDIDATE` + `COMPARE_REQUIREMENT` produce these rows. `stage` is `FINAL` unless stated.

| Requirement | A | B | KNOWN | ROLLING_1 / 2 | C |
| --- | --- | --- | --- | --- | --- |
| `R-SLOPE-AVAILABILITY` (≥ 0.05 in band, 60 m) | PASS `MEETS_CRITERION` | PASS | PASS | FAIL `INSUFFICIENT_EXPOSURE` | FAIL `INSUFFICIENT_EXPOSURE` |
| `R-TARGET-SLOPE-CONTEXT` (W1 ≤ 6° at 480 m; optional) | per oracle | per oracle | per oracle | per oracle | per oracle |
| `R-EXPOSURE` (≥ 100 m unique in band; route-dependent) | UNKNOWN `ROUTE_NOT_VERIFIED` (PRELIMINARY) | same | same | same | same |
| `R-TASKS`, `R-RESERVE` (route-dependent) | UNKNOWN `ROUTE_NOT_VERIFIED` (PRELIMINARY) | same | same | same | same |
| `R-MINERAL` (optional; `PRESENT`) | UNKNOWN `EARTH_EVIDENCE_MISSING` (synthetic scenario) / `TARGET_EVIDENCE_MISSING` (local-practice scenario: Earth mineral bound, target mineral absent) | same | same | same | same |
| `R-CLEARANCE` (field_validation, 0.02 m support) | UNKNOWN `SCALE_UNSUPPORTED` | same | same | same | same |
| `R-GRAVITY`, `R-ATMOSPHERE` | GAP `PHYSICAL_GAP` | same | same | same | same |

"Per oracle" means: the test computes the binned Wasserstein-1 distance (bin centres from edges `[0,2,5,8,12,15,18,25,35,90]`) with an independent implementation and asserts `status == PASS ⇔ w1 ≤ 6.0`, `measured_unit == "deg"`, and `comparison_scale_m == 480` (Mars scenario) or `960` (Moon scenario).

After PROVE IT (§6): A → `R-EXPOSURE` FAIL `ROUTE_FAILED` (FINAL), `R-TASKS` PASS, `R-RESERVE` PASS. Platform rule: the `verification` summary supplied to `COMPARE_REQUIREMENT` for candidate X is the **last attempt on X that produced a verified route** for the tasks/reserve rows and the **last attempt on X** for the exposure row; a no-route attempt turns only the rows named in `DIAGNOSE_RESULT.violated_constraint_ids` into FAIL and leaves the rest as they were. Each row cites the attempt it came from and states in `limitations` that a coupled (`co_location_group`) claim is unsupported when any member row failed. B → `R-EXPOSURE`, `R-TASKS`, `R-RESERVE` PASS `ROUTE_VERIFIED` (FINAL). Confidence values come from the rubric in 11 and are never `HIGH` for `terrain_model` rows with unquantified uncertainty (maximum `MEDIUM`).

Compatibility with ARES-1 (preliminary, before a route): `max_surface_slope_deg` PASS (18 ≥ required band upper 18 under the declared-capability rule), `ground_clearance_m` UNKNOWN (scale), `energy_reserve_pct` UNKNOWN (no route), `obstacle_height` UNKNOWN (`max_obstacle_height_m` null), `required_capability` PASS (geological_sampling declared; "declared, not observed"). After a verified route: energy row PASS/FAIL from the verifier.

## 6. PROVE IT storylines (exact expected attempts)

`auto-waypoints-v1` (normative rule): within the largest connected safe component (valid, land, slope ≤ cap; ties → smallest row-major first cell) choose start `S` = component cell nearest the component's cell centroid; `W1` = among component cells at Euclidean distance in `[0.15, 0.30]·window_edge` from `S` the one with the greatest count of band-slope cells in its 5×5 neighbourhood (ties → row-major); `W2` = same rule among cells ≥ `0.10·window_edge` from `W1`. Tolerance = one cell. Dwell 60 s; incremental energy = `energy_model.science_task_wh`. `max_distance_m = rover.max_route_m` if non-null else `design_defaults.max_route_m` (8000 m in `algorithms.yaml`, recorded in `constraints.limitations`).

**Diagnosis rule `ANALOG` vs `ROVER`** (used by `DIAGNOSE_RESULT` when `search_status = EXHAUSTIVE_INFEASIBLE`): re-evaluate the optimistic-bound certificate with the **rover-dependent constraints removed** (slope cap raised to 90°, battery treated unbounded) but with every terrain mask (water, nodata, unknown) kept. If the zone becomes feasible → `ROVER`; if it stays infeasible → `ANALOG`. `EXHAUSTIVE_INFEASIBLE` is permitted only when the certificate is lossless (`labels_pruned_lossy == 0`): reachable-component exposure upper bound `<` required, or exact enumeration completed.

### S-RASTER-1: `synthetic-mars-mobility-v1`, ARES-1, user selects **A** then PROVE IT

| # | Candidate | Strategy | Search | Verify | Violation / category | Next (from `DIAGNOSE_RESULT`) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | A | `WAYPOINT_RETURN` | `FOUND` | **FAIL** | `EXPOSURE_SHORTFALL` on `C-EXPOSURE-R-EXPOSURE` (observed 0 m < 100 m); `ROUTE` | `NEW_ROUTE`, `EXPOSURE_COVERAGE` |
| 2 | A | `EXPOSURE_COVERAGE` | `EXHAUSTIVE_INFEASIBLE` (certificate: reachable band length 0 m) | n/a | `ANALOG` (still infeasible with rover limits removed: moat) | `NEW_CANDIDATE` |
| 3 | **B** | `EXPOSURE_COVERAGE` | `FOUND` | **PASS** | none | — |

Replans used: 1 route repair + 1 candidate switch = 2 of 3. Contract and rover hashes are identical in all three attempts. Passport shows all three attempts, the changed elements (`strategy: WAYPOINT_RETURN → EXPOSURE_COVERAGE`; `candidate: Practice grid-r0c1 → Practice grid-r0c0`), qualified uses limited to modeled terrain feasibility on B, `R-CLEARANCE`/`R-MINERAL` unknown, gravity/atmosphere gap.

### S-GRAPH-1: `synthetic-graph-regression-v1` (canonical graph through the whole product)

| # | Strategy | Search | Result |
| --- | --- | --- | --- |
| 1 | `WAYPOINT_RETURN` | `FOUND` `S,A,W1,W2,W1,A,S` | verify **FAIL**: 120 m, 26 Wh, 0 m unique exposure, `EXPOSURE_SHORTFALL`, `ROUTE` |
| 2 | `EXPOSURE_COVERAGE` | `FOUND` `S,A,W1,W2,W1,C,B,S` | verify **PASS**: 230 m, 30 Wh, 150 m, reserve `98.33333333333333 %` |

Verifier oracle tests (supplied routes, not searched): the 340 m route `S,B,C,W1,W2,W1,C,B,S` PASS (34 Wh, 150 m, reserve `98.11111111111111 %`). Additional graph assertions (`catalog.GRAPH_EXPECTED`): one-expansion budget → `BUDGET_EXHAUSTED` / `INCONCLUSIVE` / `SEARCH_LIMIT`; removing the three 15° edges → `EXHAUSTIVE_INFEASIBLE`; repeated traversal of an edge earns energy/time but no extra unique exposure; any falsified solver total (energy or exposure) is rejected by the verifier; the mock resource provider is rejected in `live` mode.

### S-ROVER-LITE: `PRACTICE-LITE` (12°) on **B**
Attempt 1 `WAYPOINT_RETURN` FOUND → verify FAIL `EXPOSURE_SHORTFALL` (ROUTE). Attempt 2 `EXPOSURE_COVERAGE` → `EXHAUSTIVE_INFEASIBLE` (15° ramp exceeds the 12° cap). Diagnosis: feasible with rover limits removed ⇒ **`ROVER`**; permitted repairs `[NEW_CONTRACT_REQUIRED]`; run ends `BUILDING_PASSPORT` with FAIL/ROVER, `stop_reason = NO_PERMITTED_REPAIR`. The contract is **not** relaxed.

### S-NO-ENERGY: `PRACTICE-NO-ENERGY-MODEL` on **B**
Attempt 1 FAIL (exposure). Attempt 2 route FOUND; verification: exposure/tasks PASS, energy **not evaluable** ⇒ `INCONCLUSIVE` / `DATA` with issue `ENERGY_UNCALIBRATED`; permitted `[DATA_REPAIR]`; stop `DATA_BLOCKED`. No zero-consumption assumption anywhere.

### S-SMALL-BATTERY: `PRACTICE-SMALL-BATTERY` (30 Wh) on **B**
`WAYPOINT_RETURN` search → `EXHAUSTIVE_INFEASIBLE` by lossless energy bound (usable 24 Wh; derivable from the waypoint rule: `W1` lies ≥ 0.15·3840 m = 576 m from `S`, so any closed loop is ≥ 1152 m, whose idle energy alone is ≥ 22.4 Wh nominal, exceeding 24 Wh with the 25 % margin); diagnosis `ROVER` (feasible with battery unbounded), violated constraint `C-ENERGY-RESERVE`; permitted `[NEW_CONTRACT_REQUIRED]`.

### S-SEARCH-LIMIT
Test hook (only when `ANALOGFORGE_TEST_HOOKS=1` **and** mode `synthetic`): operator limit `search_max_expansions=1` → `BUDGET_EXHAUSTED` / `INCONCLUSIVE` / `SEARCH_LIMIT`; UI `empty-state[data-reason=SEARCH_LIMIT]`; passport states "bounded search; not proof that no route exists".

### S-MOON-SITE-ONLY: `synthetic-moon-gap-v1` (no rover)
Polar Moon target + practice Earth grid, no rover. Expected: `R-THERMAL` UNKNOWN (`EARTH_EVIDENCE_MISSING`; with `practice-moon-thermal-v1` bound the *target* gains a thermal metric but the row **stays UNKNOWN**), `R-GRAVITY`/`R-VACUUM` GAP, slope rows per oracle; `GET /compatibility` → 409 `ROVER_REQUIRED`; `PROVE_IT` rejected `ROVER_REQUIRED`; passport `is_draft=false`, `publication=LIMITED`, `not_run_reason="No rover supplied — site qualification only"`.

## 7. Scripted synthetic agent roles (platform test driver)

In `synthetic` and `replay` modes the ten roles run through a **scripted provider** (Tanush). It makes role proposals from the tool receipts that actually exist; it never emits a scientific number or verdict itself. One **seeded defect** is injected (in `synthetic-mars-mobility-v1` **and** `local-dataset-practice-v1`, flagged `defect_injection=true` in the scenario fixture, so journeys J01 and J11 are identical):

1. Scripted Qualification's first proposal for candidate A cites, for `R-TARGET-SLOPE-CONTEXT`, the 60 m Earth analysis evidence instead of the 480 m common-support comparison evidence (a **scale defect**).
2. The platform's mechanical bundle review (`review_evidence_bundle`, `scale` check) detects `comparison_scale_m (60) < requirement.minimum_support_scale_m (480)` ⇒ BLOCKING `SCALE_MISMATCH` issue (`critic-card[data-severity=BLOCKING][data-status=OPEN]`).
3. The affected claim is excluded from any positive statement while open (`SC-12`); the Director routes one repair round; Qualification revises citing the correct evidence; the issue becomes `RESOLVED` with `resolution_evidence_ids`; matrix revision 2 supersedes revision 1 and the UI shows **Previous → Current**.

**Preparation (`draft_contract`/`revise_draft`) in synthetic/replay:** the scripted Requirements role proposes the scenario's `mission_preset` requirements (kit fixture) verbatim, validates them through `validate_mission_draft`, marks every requirement `origin=PROPOSED_DEFAULT`, keeps the user's objective/target, and emits the preset's assumptions as `assumption_proposals`; a body mismatch between the draft and the preset is a blocker (`NEEDS_USER_REVIEW`).

Scripted Director/Scout/Test Designer/Verification choices come from `allowed_actions` and `DIAGNOSE_RESULT.recommended_*`; nothing scripts "attempt 3 passes" (perturbation tests change the geometry and the story changes).

## 8. Perturbation tests (mandatory)

| ID | Perturbation | Required changed outcome |
| --- | --- | --- |
| PERT-01 | `moat_cells = 0` in window A's generator | A attempt 1 FAIL then attempt 2 (`EXPOSURE_COVERAGE`) FOUND/PASS; no candidate switch |
| PERT-02 | B ramp slope 15° → 10° | `R-SLOPE-AVAILABILITY` B → FAIL; exposure infeasible → `ANALOG` |
| PERT-03 | ARES-1 `max_slope_deg` 18 → 14 | B → `ROVER` (S-ROVER-LITE behaviour) |
| PERT-04 | battery 30 Wh vs 1800 Wh | `ROVER` vs PASS |
| PERT-05 | target histogram shifted (all area to 22°) | `R-TARGET-SLOPE-CONTEXT` flips for A/B |
| PERT-06 | `R-EXPOSURE.lower` 100 → 10000 m (exceeds the 8000 m route-domain bound) | B → `EXHAUSTIVE_INFEASIBLE` by the domain-bounded certificate, category `ANALOG`, proof scope "domain-bounded"; never PASS |
| PERT-07 | remove `practice-earth-minerals-v1` binding | `R-MINERAL` reason `TARGET_EVIDENCE_MISSING` → `EARTH_EVIDENCE_MISSING` |
| PERT-08 | flip a single cell on B's route into nodata | verifier rejects that route (`UNKNOWN_TERRAIN`) or search returns a different legal route |
| PERT-09 | graph edge `S–B` length 50 → 500 m | `EXPOSURE_COVERAGE` result changes (distance/exceeds `max_distance_m` ⇒ different route or infeasible) |

## 9. Practice rovers

`catalog.PRACTICE_ROVER_FILES` (kit fixtures): `ARES-1` (baseline), `PRACTICE-LITE` (12°), `PRACTICE-NO-ENERGY-MODEL` (`energy_model=null`), `PRACTICE-SMALL-BATTERY` (30 Wh). Each loads through the manual editor and the JSON import, round-trips without loss, and is offered by "Load example".

## 10. Scenario catalog (what `GET /capabilities` lists)

| Scenario id | Body | Mission preset | Rovers | Sources | Status |
| --- | --- | --- | --- | --- | --- |
| `synthetic-mars-mobility-v1` | MARS | `mission-mars-mobility.json` | all four practice | fixtures `practice-mars-target-v1`, `practice-earth-grid-v1` (no minerals) | AVAILABLE |
| `synthetic-graph-regression-v1` | MARS | `mission-graph-regression.json` | `ARES-1` (blueprint profile) | fixture `canonical-graph-v1` | AVAILABLE |
| `synthetic-moon-gap-v1` | MOON | `mission-moon-gap.json` | none (site-only) | fixtures `practice-moon-target-v1`, `practice-earth-grid-v1` | AVAILABLE |
| `local-dataset-practice-v1` | MARS | `mission-mars-mobility.json` | all four practice | LOCAL_DATASET `practice-mars-target-v1`, `practice-earth-grid-v1`, `practice-earth-minerals-v1` | AVAILABLE after `datasets generate-practice` + `datasets lock --policy-id local-practice-policy-v1` |
| `live-hackathon-v1` | operator-set | operator-set | operator-set | LOCAL_DATASET ids bound on the day | `AWAITING_DATASETS` until `scenario bind` |

`allowed_modes`: the four practice scenarios allow `synthetic` (and `replay` once a replay exists); `live-hackathon-v1` allows `live` only. `operator_limits` keys (numbers): `search_max_expansions`, `search_max_seconds`, `search_max_labels_per_node`, `coarse_windows_max`, `detailed_candidates`, `model_requests_per_run`, `active_run_seconds`, `replans_total`.
