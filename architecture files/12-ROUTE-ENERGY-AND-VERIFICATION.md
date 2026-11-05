# PROVE IT: route design, resource search, energy, and verification

This is a modeled terrain-test engine, not a dynamics simulator or flight-hardware certification. Its numerical outputs must retain the source support and unknown physical conditions from [08](08-DATASET-CATALOG.md), [10](10-TERRAIN-AND-PLANETARY-COMPARISON.md), and [11](11-QUALIFICATION-AND-UNCERTAINTY.md). Implement the deterministic engine before connecting the Test Designer and Verification/Replanning roles.

## 1. Inputs, revisions, and outputs

`search_route` requires an accepted mission contract, a pinned non-null rover revision, candidate/test-zone revision, validated Earth analysis rasters, forbidden/unknown masks, start location, task waypoints, required exposures, energy assumptions, resource limits, and solver budget. Qualification-only runs may omit a rover; they must create a new run pinned to a rover before entering verification.

The `VerificationTest` wire object is defined in `contracts/domain.schema.json`. Its `constraints_sha256` references a complete canonical constraints artifact containing task definitions and durations, route closure, waypoint tolerance, allowed zone, uncertainty model, exposure counting semantics, maximum length/time, surface/pitch/cross-slope policy, maximum edge traversals, geometry tolerances, mask dilation, and all graph/solver settings. Its `required_exposures` records requirement IDs, metric bands, and minimum distances. The artifact is immutable, reviewable, and bound to mission/rover hashes; do not hide decisive constraints in prompts.

`search_route` returns a proposed route artifact and search receipt. `verify_route` independently evaluates an existing route against source rasters and immutable constraints, returning `TestResult`, metric evidence, violations, sampled route telemetry, and limitations. The solver's stored totals are not accepted as verification evidence.

## 2. Build the traversability graph

Use an Earth metric analysis grid, initially 60 m for NASADEM context, with source support explicitly attached. Node centers are valid candidate cells. Use an eight-neighbor directed graph for initial implementation. Diagonal edges may not cut across an invalid/forbidden corner: evaluate the supercover of every crossed cell and reject if any required support is invalid. A one-pixel nodata channel cannot become a diagonal bridge.

Before graph construction, intersect candidate zone, valid derivative mask, terrestrial-land mask, approved area restrictions, and available task evidence. Dilate forbidden and unknown regions by the declared rover-footprint radius plus geolocation uncertainty where known. If the uncertainty/footprint is unknown, record the assumption and keep physical clearance UNKNOWN; selecting a one-cell visual route does not prove a physical corridor.

For each directed edge calculate horizontal distance `d_xy`, elevation difference `dz`, modeled surface distance `d_s=sqrt(d_xy²+dz²)`, direction, maximum sampled surface slope, longitudinal and cross-heading grade proxies, source-supported terrain classes, nominal/conservative energy, and time. Raster sampling uses the full edge supercover and the declared interpolation policy. An edge's endpoint difference alone cannot detect intermediate hazards. Reject edges over the accepted surface-slope cap even if their longitudinal grade is near zero.

The generic rover maximum safe slope is conservatively applied to full modeled surface slope. Separate longitudinal or cross-slope limits require explicit fields in the constraints artifact and an approved geometry interpretation. Soil traction, sinkage, contact geometry, and stability are unresolved without additional evidence. Do not label raster feasibility as a proven safe physical route.

Rasters and graph artifacts are versioned. A newly blocked edge, changed mask, newly acquired elevation asset allowed by the frozen source policy, or corrected waypoint creates a new test revision and invalidates downstream verification. Replacement of a locked source version or source-policy change requires a new run. Test revision changes must not change the accepted mission threshold or rover capability.

The initial executable route artifact contains its graph revision, canonical node/edge sequence, task events, and a display polyline. Verification reconstructs geometry from canonical edges and checks that the display geometry agrees. All initial routes must conform to this graph. A smoothed display line is never the executable route and cannot bypass masks or gain new exposure IDs. An arbitrary uploaded polyline requires an explicit graph-snapping/import operation within accepted tolerances before it can use this verifier; unsupported geometry returns a clear validation error.

## 3. Waypoints and tasks

Each task has a stable ID, requirement IDs, type, Earth location or allowed polygon, positional tolerance, evidence origin, sensor/instrument needs, dwell time, and incremental energy. Snap only within the declared tolerance and the same connected valid zone. Persist requested and snapped locations plus distance. Failure to find an allowed cell is `WAYPOINT_UNREACHABLE` or `WAYPOINT_UNRESOLVED`; never move the sample to wherever a convenient route happens to go.

Distinct science tasks require distinct task IDs. Visiting the same pixel twice does not satisfy two independently located targets unless explicitly accepted. A route must execute the task, not merely pass near it; the telemetry contains arrival, dwell, and completion events. Capability checks use the rover profile. A sampling waypoint can be user-designated without asserting mineral identity; its provenance and unconfirmed material availability remain visible.

Require return to the declared start/finish zone when the contract says return. A line ending near the last sample cannot be reported as a completed out-and-back test. Default numerical closure tolerance is the waypoint-snapping tolerance; its physical interpretation remains source-scale limited.

## 4. Exposure counting

Exposure requirements specify metric, support, band edges, minimum distance, and whether the distance is unique terrain or total traversal. The default is `UNIQUE_UNDIRECTED_EDGE_DISTANCE`, preventing a solver from oscillating on one short hillside to manufacture extensive terrain diversity. Returning along the same edge consumes time and energy but earns no additional unique exposure. An explicitly accepted repeated stress-cycling test may instead use traversed distance; label that distinction.

Split edges into raster-intersection subsegments before accumulating exposure. A segment contributes only where the metric is valid and within its band. Default adjacent bands are lower-inclusive/upper-exclusive; the final capped band includes its upper endpoint. A 12° sample belongs to the 12–15° band rather than both neighboring bands. Surface slope and longitudinal grade are different metric IDs.

For unique exposure, maintain covered undirected edge/subsegment IDs and band-distance contributions. If a later mask revision changes those subsegments, regenerate IDs from graph revision and geometry. Saturate exposure resources at the requirement thresholds for search, while the independent verifier reports the full measured values. A minimum contiguous exposure length, if required, needs its own run-length state; scattered distance cannot satisfy it.

Terrain-class diversity uses only predeclared numerical classes at the source support. Count a class only after its contract-specific minimum unique distance is reached. Do not count a one-pixel corner touch or invent lithology classes from DEM relief.

## 5. Energy model and dimensional consistency

Use a deliberately simple, explicit Earth model. Baseline constants are assumptions until calibrated, not NASA measurements. For each edge:

```text
m = rover mass [kg]
g = 9.80665 [m/s²] for the Earth test model
Crr = rolling_coefficient [dimensionless]
eta = drive_efficiency, 0 < eta <= 1
k_r = roughness_multiplier, >= 1
theta_s = modeled surface slope [radians]
d_s = modeled surface length [m]
dz = endpoint height change [m]
t_drive = d_s / nominal_speed_mps [s]

E_roll_J = k_r * Crr * m * g * cos(theta_s) * d_s / eta
E_climb_J = m * g * max(dz,0) / eta
E_drive_Wh = (E_roll_J + E_climb_J) / 3600
E_idle_Wh = idle_power_w * (t_drive + t_tasks) / 3600
E_tasks_Wh = sum(science_task_wh for each completed task)
E_nominal_Wh = sum(E_drive_Wh) + E_idle_Wh + E_tasks_Wh
E_conservative_Wh = E_nominal_Wh * (1 + uncertainty_fraction)
reserve_pct = 100 * (battery_wh - E_conservative_Wh) / battery_wh
```

For edge-varying terrain, integrate rolling contribution over sampled subsegments. `science_task_wh` is the incremental per-task energy above idle power; document that convention to avoid double counting. `idle_power_w` is paid during both drive and dwell. No regeneration is credited; downhill gravitational work is not subtracted. A return route correctly pays climbing work on whichever directed edges are uphill.

The roughness multiplier is an accepted model parameter. It is not automatically derived from NASADEM RMS height without calibration. `uncertainty_fraction` is a conservative scenario margin, not a statistical confidence interval. If more explicit calibrated parameter bounds are available, enumerate accepted scenarios and use worst-case modeled consumption; store those scenarios in constraints and evidence.

An initial assumed profile may propose `Crr=0.06`, `eta=0.65`, `idle_power_w=35`, `science_task_wh=10`, `roughness_multiplier=1.0`, and `uncertainty_fraction=0.25` for review. These are design defaults with no claim of ARES-1 calibration. A missing energy model yields an inconclusive energy requirement; it must not become zero consumption. ARES-1's actual profile fields remain 42 kg, 1800 Wh, 20 percent minimum reserve, and 0.5 m/s unless a different revision is supplied.

The hard energy constraint is `E_conservative_Wh <= battery_wh*(1-min_reserve_pct/100)`, plus any per-task power constraints explicitly supported. Negative reserve is a failure, not clamped into a plausible number. Reject invalid units, efficiencies, nonpositive battery/speed, or unbounded/NaN values at validation.

Earth analog energy is calculated using Earth gravity. A separate hypothetical Mars/Moon energy estimate must use its own declared gravity and model limitations and is never substituted for the Earth field-test budget. Geometric slope matching does not make traction or energy dynamically equivalent across worlds.

## 6. Bounded resource-constrained search

Ordinary shortest-path A* to the science waypoints is insufficient because it may avoid all required terrain exposure. Implement multi-label resource-constrained search with explicit task and exposure state. A label contains:

```text
node, completed_task_bitmask, covered_unique_edge_state,
edge_traversal_counts, saturated_exposure_vector,
energy_upper_Wh, elapsed_s, distance_m,
contiguous_exposure_state_if_required,
predecessor_label_id
```

Use deterministic node/edge ordering and stable tie breakers. Initial budgets are 200,000 label expansions, 30 seconds, and 32 retained labels per node, subject to deployment's lower caps. The constraint artifact also bounds route length/time and defaults to at most two traversals of any undirected edge. The latter is a declared test-design domain constraint supporting out-and-back travel, not a hidden proof about every conceivable route.

Keep multiple nondominated labels at the same node. Dominance is safe only when future opportunities are equivalent: same task state, same relevant unique-exposure/edge-use state, and same contiguous-exposure state. Then label A dominates B when A consumes no more energy/time/distance and has no less accepted exposure, with at least one strict improvement. Do not discard B solely because it arrived at the same cell with a higher scalar cost: B may have collected a required sample or exposure that A lacks.

Exact bitsets for covered edges and traversal counts are acceptable for small bounded zones. Persistent bitsets/hash-consed states reduce memory; hashes must be collision-checked. If implementation uses approximate exposure quantization, epsilon dominance, label truncation, beam search, or a coarsened graph, record this and prohibit an exhaustive-infeasibility claim. Conservative rounding can reject a feasible route; it cannot prove the original continuous problem infeasible.

Search sequence:

1. Reject unsupported mandatory inputs before search; return affected data issues.
2. Compute connected components and graph shortest-distance lower bounds to required tasks/return.
3. Push the start label with zero resources and uncompleted tasks.
4. Pop a label in a deterministic priority ordering favoring lower remaining resource bound, with exposure deficits as a secondary heuristic. Priority is for efficiency, not a substitute for preserving resource labels.
5. Expand allowed directed edges, execute eligible tasks, update resource totals and unique exposure, and reject hard-budget violations.
6. Apply only admissible pruning for exact claims. A shortest required-return cost is a useful lower bound. Do not treat a greedy route's cost as a lower bound.
7. At a closed route with all task/exposure constraints satisfied, emit a candidate and independently verify it. A passing route can terminate as feasible; do not claim minimum energy or global optimality unless separately proven.
8. Stop on cancellation, budget, complete queue exhaustion, or requested number of verified feasible alternatives. Persist counters, approximation flags, and why pruning occurred.

Exposure feasibility bounds must be optimistic. For example, total valid band distance in the reachable component is an upper bound on unique achievable exposure, but disconnected components cannot be added. If even the optimistic bound is too small, the discrete zone is infeasible for that requirement. Do not use a local greedy failure as such a bound.

## 7. Independent verification and outcome mapping

Verifier inputs are the immutable route bytes, source rasters, masks, task definitions, mission, rover, and constraints. It reprojects/checks route geometry, resamples every segment, calculates all resources, counts exposure independently, checks task completion and return, and emits one result per requirement. It does not trust solver eligibility flags, telemetry, or agent explanations. Shared low-level unit conversion is allowed; reuse of the solver's accumulated totals as the check is not.

| Situation | `search_status` | `outcome` | Category |
|---|---|---|---|
| Proposed route independently meets all included mandatory model criteria | `FOUND` | `PASS` | null |
| A supplied route violates a known criterion | `NOT_RUN` | `FAIL` | Usually `ROUTE`; exact violations recorded |
| Solver route is found but independent check rejects it | `FOUND` | `FAIL` | `ROUTE`, plus implementation defect issue |
| Complete exact finite graph enumeration finds no feasible route, no lossy pruning | `EXHAUSTIVE_INFEASIBLE` | `FAIL` | `ANALOG` or `ROVER` only with supported diagnosis |
| Expansion/time/label limit reached without verified feasible route | `BUDGET_EXHAUSTED` | `INCONCLUSIVE` | `SEARCH_LIMIT` |
| Required source support, task evidence, or energy assumptions missing | `NOT_RUN` | `INCONCLUSIVE` | `DATA` or `REQUIREMENT` |
| Unexpected engine error | `ERROR` | `INCONCLUSIVE` | `SYSTEM` |

Exact infeasibility applies only to the stated discrete graph, route-domain bounds, and model. It is not proof that a physical site has no route. If a label cap discarded nondominated states, an empty queue maps to BUDGET_EXHAUSTED, not EXHAUSTIVE_INFEASIBLE. A feasible route found under a budget still requires independent verification and may be reported as feasible without optimality.

Use violation codes including `MAX_SLOPE_EXCEEDED`, `FORBIDDEN_INTERSECTION`, `UNKNOWN_TERRAIN`, `WAYPOINT_MISSED`, `TASK_CAPABILITY_MISSING`, `RETURN_NOT_COMPLETED`, `EXPOSURE_SHORTFALL`, `CLASS_DIVERSITY_SHORTFALL`, `ENERGY_RESERVE_SHORTFALL`, `MAX_DISTANCE_EXCEEDED`, `MAX_DURATION_EXCEEDED`, and `SCALE_UNSUPPORTED`. Include requirement ID, observed value, threshold, units, location/segment where relevant, and evidence IDs in the detailed result artifact.

## 8. Diagnosis and bounded replanning

Diagnose observed violations before proposing changes. `ROUTE` means the evaluated route missed a condition, not that another route exists. `ROVER` requires a capability mismatch or model proof within stated assumptions. `ANALOG` requires supported absence/insufficiency of relevant conditions within the studied zone. `DATA` requests better evidence; `SEARCH_LIMIT` requests a larger supported budget/smaller search representation and remains inconclusive. `REQUIREMENT` includes underspecification or a physical gap that cannot be repaired by moving a route.

Allowed replans within the same run: change path, task order within accepted rules, start zone if accepted as selectable, another permitted test zone, or another candidate; add evidence and recompute. Prohibited: reduce exposure, delete a required sample, lower reserve, increase rover slope limit, relabel UNKNOWN as PASS, or remove planetary gaps. Those require an explicitly accepted new mission/rover revision and new run.

Default at most two route repairs and one candidate substitution after the initial test. Stop with supported FAIL/INCONCLUSIVE if still unresolved. This preserves bounded cost and truthful results. Store before/after route IDs, changed choices, invariant mission/rover hashes, deterministic results, and a brief reason for each change. Never script a successful replan for live evidence.

## 9. Deterministic failure/replan regression fixture

Use an explicitly synthetic graph unit fixture, separate from raster tests, so the failure and repair are guaranteed without pretending they came from a real site. Undirected edges have fixed modeled surface-slope/exposure metadata and mock resource costs:

| Edge | Length | Surface-slope band | Mock energy per traversal |
|---|---:|---:|---:|
| S–A | 20 m | 10° | 1 Wh |
| A–W1 | 20 m | 10° | 1 Wh |
| W1–W2 | 20 m | 10° | 1 Wh |
| S–B | 50 m | 15° | 2 Wh |
| B–C | 50 m | 15° | 2 Wh |
| C–W1 | 50 m | 15° | 2 Wh |

Require W1 and W2 tasks, return to S, no slope over 18°, at least 100 m **unique** exposure in [12°,18°], maximum distance 400 m, at most two traversals per edge, 1800 Wh battery, 20 percent reserve, and two 10 Wh mock tasks. The initial route `S,A,W1,W2,W1,A,S` has length 120 m, energy 26 Wh, and zero required steep exposure: FAIL/EXPOSURE_SHORTFALL. The repaired route `S,B,C,W1,W2,W1,C,B,S` has length 340 m, 150 m unique steep exposure, energy 34 Wh, and reserve `98.111111...%`: PASS under the synthetic graph model.

The graph's mock energies test solver accounting only and bypass the production energy formula through an explicit test-only resource provider. These graph labels are not asserted to describe a realizable raster surface. Separate analytic raster/energy tests below exercise the actual geometry and energy implementation. Production code cannot enable the mock provider in live mode.

Additional fixture assertions: a one-expansion budget gives INCONCLUSIVE/SEARCH_LIMIT, not FAIL/ANALOG; repeated W1–W2 traversals cannot earn steep exposure; lowering the requirement inside replanning is rejected; deleting all 15° edges proves discrete-model infeasibility only when exact enumeration completes.

## 10. Required verification tests

Analytic tests include flat-route energy with known units, uphill/downhill asymmetry, no downhill energy credit, auxiliary power during dwell, conservative reserve threshold equality, invalid efficiency rejection, a contour route on a steep plane rejected by full surface slope, nodata supercover, diagonal corner blocking, sample snapping beyond tolerance, exposure-band boundaries, unique-edge double counting, return closure, and independent rejection of falsified solver totals.

Live-data acceptance is outcome-neutral: analyze actual downloaded terrain, run a real proposed route, preserve the computed outcome, and produce a real replan only if supported. It is acceptable for the actual candidate to remain unqualified. The polished failure/replan story must use the visibly synthetic regression fixture or an honestly recorded real run, as specified in [29-SCIENTIFIC-VALIDATION.md](29-SCIENTIFIC-VALIDATION.md).
