# Scientific validation and evidence release gates

Software tests verify implementation behavior; scientific validation verifies that the stated inference is supported by the actual data and model. This plan is mandatory alongside [26-TEST-STRATEGY.md](26-TEST-STRATEGY.md). It does not require every site to pass. A correctly rejected or unresolved candidate is a valid scientific result.

## 1. Acceptance levels

| Level | Evidence | Allowed conclusion |
|---|---|---|
| S0: contracts | Schema-valid synthetic inputs and policy cases | Interfaces and guards behave as specified |
| S1: analytic science | Analytic surfaces and hand-computable resources | Numerical implementation matches declared equations |
| S2: real-product ingestion | Downloaded, checksummed product plus inspected metadata | Selected source is decoded/georeferenced correctly |
| S3: real comparative analysis | Actual Earth and planetary data at matched support | Stated regional or modeled-terrain comparisons are reproducible |
| S4: modeled experiment | Independently verified route under locked constraints | Proposed test meets or fails its listed model criteria |
| S5: physical validation | Survey/field observations and calibrated rover response | Only the specifically observed hardware/environment claims |

The required application supports S0–S4 with honest limitations. It does not claim S5 without an actual field campaign. Do not call synthetic S1 success real NASA validation, or an S4 route result proof that autonomy/traction/clearance works in the field.

## 2. Test evidence organization

Implement `tests/unit/science/{test_geometry,test_raster_metrics,test_comparison,test_qualification,test_energy,test_route_solver,test_route_verifier,test_portfolio}.py` inside the application repository. Use `tests/fixtures/synthetic/` for generators and deterministic graph fixtures; `tests/fixtures/real/` for permitted tiny verified extracts/labels; `tests/integration/live_data/` for network/credential-dependent validation. The repository layout follows [04-REPOSITORY-AND-DEPENDENCIES.md](04-REPOSITORY-AND-DEPENDENCIES.md).

Each case records ID, input artifact hashes, mode, expected scope, invariant/assertion, numerical tolerance, source citations, result, and reviewer. Store a validation report artifact with the release/runtime digest. CI runs offline S0/S1 plus locked real extracts; explicitly triggered integration runs do S2/S3. Skipping a credential-dependent case is SKIPPED with reason, never PASS.

Golden expected values are manually derived, from analytic truth, or independently checked against documented source encoding. Do not regenerate the expected file using the same production function under test. Snapshot tests for prose or rendered percentages do not establish scientific correctness.

## 3. Analytic geometry and terrain oracles

Use a 101×101 grid, centered metric coordinates, 10 m spacing, and sufficient halo. Compute on interior cells to avoid boundary ambiguity.

| ID | Input | Expected assertion |
|---|---|---|
| GEO-01 | Flat `z=100` | Slope 0; detrended RMS near zero; aspect null |
| GEO-02 | `z=tan(12°)*x+100` | Surface slope 12° within 1e-6°; directional grade along x is 12° |
| GEO-03 | Same plane, route along y | Longitudinal grade 0; surface slope remains 12° |
| GEO-04 | `z=a*x+b*y+c`, x/y pixel spacings 10/30 m | Recovered a,b agree with truth; no square-pixel assumption |
| GEO-05 | Same physical surface with rotated affine transform | Same physical slope within declared floating-point tolerance |
| GEO-06 | Missing center/neighborhood samples | Invalid derivative halo; no zero-filled flat area |
| GEO-07 | Plane plus known deterministic residual pattern | RMS matches manually calculated plane-residual result |
| GEO-08 | Adjacent mosaicked tiles with duplicate border samples | No duplicated column, seam, or distance shift |
| GEO-09 | Deliberate one-pixel registration offset | Validation catches mismatch against known control coordinates |
| GEO-10 | Planetary longitude crossing 0/360 and polar AOI | Correct bounds/body; no Earth CRS coercion |

For GEO-07 choose residuals orthogonal to the plane-fit basis or calculate the residual projection explicitly, so the expected answer accounts for detrending. A simple alternating pattern can otherwise be partially absorbed into the fitted plane and make the test oracle wrong.

Test physical distance using each source body's declared geometry. A one-degree equatorial Mars arc is different from Earth. Do not use an Earth haversine radius inside a planetary helper. Validate datum/frame conversion with labeled fixtures; an unknown frame must be rejected rather than silently approximated.

## 4. Energy and resource oracles

Test the exact model in [12](12-ROUTE-ENERGY-AND-VERIFICATION.md), not an undocumented intuitive consumption estimate. For a flat 1,000 m Earth route with mass 42 kg, gravity 9.80665 m/s², rolling coefficient 0.06, efficiency 0.65, roughness multiplier 1, speed 0.5 m/s, idle power 35 W, no tasks, and margin 0.25, expected values are approximately:

```text
rolling_Wh = 10.5610076923
idle_Wh = 19.4444444444
nominal_Wh = 30.0054521368
conservative_Wh = 37.5068151710
reserve on 1800 Wh = 97.9162880461 percent
```

These are analytic model outputs, not observations about ARES-1. Use tighter internal expected precision computed from the displayed formula and a 1e-8 Wh tolerance for this fixed double-precision case. If these rounded values disagree at the last digit, the formula is the oracle.

Required additional assertions: doubling mass doubles rolling/climb terms but not idle power; doubling route distance doubles a flat no-task cost; doubling speed halves modeled travel idle consumption but does not alter rolling work; downhill does not create battery charge; out-and-back includes climbing work; task dwell and incremental science energy are charged once per completed task; conservative margin affects reserve; exact reserve equality passes; invalid efficiency or missing energy model cannot produce PASS.

Do not force an 1800 Wh ARES-1 route to fail energy merely because an illustrative brief used a low-reserve story. Choose a supported actual failing condition or use a labeled synthetic fixture.

## 5. Source decoding and metadata gates

For each adapter, S2 requires an actual public or authenticated download selected during preflight. Lock original bytes and checksum; preserve label/header/metadata; save a small valid extraction for offline regression when permitted. The source register identifies the original full product even when tests use only an extract.

| Source | Required independent inspection |
|---|---|
| NASADEM | Tile/member identity, byte order, dimensions, height datum, sample registration, water mask, auxiliary source coding, neighboring-tile border |
| SRTM | Product/version distinct from NASADEM, units/datum, nodata, registration; substitution triggers revision |
| MOLA | Actual maintained PDS product and label, topography versus radius, areoid interpretation, longitude/latitude conventions, geometry, observation counts |
| LOLA | Label-derived scale/offset applied once, reference radius interpretation, body/frame/projection, product-specific valid extent |
| EMIT | Variable dictionary, geolocation mapping, categorical mineral semantics, supported quality masks, valid retrieval footprint after masking |
| Diviner | Actual thermal variable/units, channel/product semantics, local-time/season/aggregation support, missing values, body/frame |

Check at least five control pixels/locations per selected source against raw encoding and documented mapping, including one valid interior, one edge, and one invalid/quality-masked example where available. Control locations and expected values are chosen from actual inspected products; they are not specified or invented here.

Compare a manually decoded small array with the library decoder. Since many libraries share GDAL internally, agreement between two GDAL wrappers is a consistency check, not full independence. Add manual label/byte and coordinate checks to catch common scaling/georeferencing errors.

An EMIT or Diviner no-coverage state is valid behavior for a run, but does not by itself validate that adapter's successful decode path. Before advertising a source as working, validate at least one real supported decode and one no-coverage/invalid-data case. If access prevents this, retain a documented release limitation; do not mark the source scientifically validated.

## 6. Common-scale comparison tests

COM-01: Create the same analytic terrain at two native resolutions. Aggregate to an identical supported physical grid/window. Metrics should agree within defined discretization tolerance. Compare mismatched native-grid slopes and ensure policy rejects a direct match when the mission requires common support.

COM-02: Upsample a coarse raster to a fine grid. Ensure metadata retains coarse effective support, the scale gate still fails a fine requirement, and no new independent samples are claimed.

COM-03: Use identical histograms to obtain Wasserstein distance 0; move all mass by a known angle to obtain the corresponding degree distance. Check valid-area weighting and nonuniform bin widths. The distance's units remain degrees, never percent Mars-likeness.

COM-04: Alter smoothing/window size and report sensitivity. Do not require qualification to remain unchanged when the phenomenon is scale-dependent. A threshold crossing is an uncertainty/scale issue to expose, not a reason to choose whichever window passes.

COM-05: Add nodata/cloud/invalid mineral retrieval regions. Valid coverage decreases; missing retrievals do not become a mineral absence claim. Test target mineral evidence absent with Earth EMIT present: cross-world mineral qualification must remain UNKNOWN.

## 7. Qualification and critic gates

Cover every status and reason code from [11](11-QUALIFICATION-AND-UNCERTAINTY.md). Specific adversarial cases:

- MOLA regional slope is offered as meter-scale rover exposure: reject the scale match.
- NASADEM RMS relief is offered as 0.20 m clearance evidence: UNKNOWN/SCALE_UNSUPPORTED.
- A lunar gravity requirement has complete Earth terrain data: GAP remains.
- Thermal metadata is missing: UNKNOWN, not GAP.
- A well-defined lower-bound interval straddles the threshold: UNKNOWN under conservative policy.
- No uncertainty model exists: no fabricated ± interval or confidence percentage.
- NASADEM and SRTM agree: preserve source dependence, do not call it independent ground truth.
- Critic raises a valid missing-provenance issue: reopen affected qualification and recompute/retain UNKNOWN.
- Agent requests PASS with an unresolved evidence ID: reject policy mutation.
- A mandatory unsupported physical criterion coexists with a passing terrain route: passport states only the supported modeled result and preserves the unresolved criterion.

The critic loop must have an observable effect. A synthetic orchestration fixture begins with a scale/provenance defect, critic emits a blocking issue, and policy prevents final PASS until correction. A model that writes an agreeable critique without changing the evidence state does not satisfy the requirement.

## 8. Route solver and independent verifier gates

Implement the exact synthetic failure/replan fixture in [12](12-ROUTE-ENERGY-AND-VERIFICATION.md): initial route FAIL with zero required steep exposure; repaired route PASS with 150 m unique steep exposure, two tasks, and return. Assert unchanged mission and rover hashes. Mark every related UI/export artifact synthetic.

Additional route cases: insufficient exposure although marginal histograms look promising; useful bands in disconnected components; contour-travel longitudinal grade below cap while surface slope exceeds cap; diagonal corner cutting; unknown terrain bridge; repeated-edge exposure gaming; missing return; task snapping outside tolerance; impossible science capability; max duration; falsified solver energy rejected by independent recomputation.

Distinguish complete exact finite-model infeasibility from bounded search exhaustion. Force a tiny expansion limit and a label-retention cap. Both must produce INCONCLUSIVE/SEARCH_LIMIT when no feasible route was verified, including when the remaining queue later becomes empty after lossy pruning. Small fully enumerated graphs can validate EXHAUSTIVE_INFEASIBLE. Neither outcome proves the physical world has no route.

Cancellation must stop computation and preserve committed evidence without producing a late PASS. The independent verifier must reject a route with a stale raster/constraint hash. Replay must produce the recorded outcome from verified stored artifacts, without a live network/model fallback.

## 9. Known analog, negative control, mission sensitivity, discovery

Use the pinned [NASA Planetary Analog Explorer](https://science.nasa.gov/solar-system/analog-explorer/) reference set as context, not a pass-label oracle. For each validation site record the mission question the reference supports, its georeferenced area, citation, and which quantitative dimensions the selected products can actually measure. A known site need not pass every requirement, and out-of-coverage data must yield UNKNOWN.

Known analog recovery is satisfied when supported mission-relevant dimensions and limitations are recognized from evidence; it does not require ranking a famous site first. Hold reference labels out of the feature-scoring function. Record whether sites helped tune thresholds to distinguish calibration examples from independent evaluation cases.

Choose a real low-relief negative-control area using downloaded data, and apply a demanding terrain-exposure mission. Verify that the observed evidence justifies failure or an unresolved result; do not declare a tropical site unsuitable merely from climate/name. A site can be a poor mobility analog and a useful operations analog for another question.

Mission sensitivity uses the same target and candidate pool under two accepted contracts: terrain exposure versus thermal operations. Expected behavior is changed evidence requests, applicable dimensions, gaps/unknowns, and coverage; a result identical because the system ignored the mission is a defect. Missing compatible Earth thermal data should become UNKNOWN, not a terrain-based thermal PASS.

Discovery acceptance requires at least one deterministically proposed eligible candidate outside the pinned reference catalog, if the configured search region contains one. Persist search extent, grid/index parameters, capped/excluded windows, and proposal origin. "Not in reference catalog" is the maximum supported novelty statement without broader independent review. No requirement forces the novel candidate to pass.

## 10. Real-data end-to-end acceptance

For Mars: fetch actual MOLA regional topography/counts and actual NASADEM or explicitly selected SRTM Earth terrain. Run body-aware normalization, common-support characterization, bounded candidate screening, per-requirement qualification, critic review, and a modeled Earth route. For Moon: repeat the target path with actual LOLA; validate selected Diviner context or its honest limitation. Exercise EMIT supported coverage or no-valid-retrieval handling and preserve target-mineral unknowns where appropriate.

For at least one real Earth candidate, independently verify a real proposed route. Save the computed outcome without requiring PASS. If a deterministic failure occurs, attempt a permitted bounded replan; save the result even when still FAIL/INCONCLUSIVE. The presentation can use a visibly synthetic guaranteed failure/replan or an honest replay of a recorded real case. Do not edit masks, waypoints, thresholds, or energy parameters after seeing results merely to obtain the desired story.

Every displayed quantity in the resulting passport must resolve through its evidence DAG to downloaded bytes or declared assumptions. Required audit entries: source IDs/versions, checksums, acquisition/processing dates, body/frame/datum, analysis/support scale, masks, algorithms, comparison rules, model parameters, search limits, outcome, residual gaps, and unknowns. Real-data acceptance is incomplete while any required acquisition/decoder gate remains unvalidated, even if synthetic tests pass.

## 11. Release report and limitations

The release report separates PASSED, FAILED, SKIPPED, and NOT_IMPLEMENTED checks. It lists tested source products rather than claiming all products in an instrument archive work. It reports model assumptions, calibration status, unsupported physical dimensions, bounded discovery extent, search approximation, and unverified operational access.

Release-blocking scientific defects include body/CRS confusion, radius/height or scaling errors, use of nodata as terrain, manufactured source IDs or measurements, source-scale clearance PASS, relaxed mission constraints inside replanning, search-budget exhaustion called infeasibility, and unsupported full-mission success. Correct UNKNOWN/GAP/INCONCLUSIVE results are expected product behavior, not defects to conceal.

## Executable assurance and release evidence

Enforce these validation boundaries using [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md), immutable assurance artifacts and [shared SCI tests](../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Control split membership, thresholds and tolerances are locked before tuning; preserve related-source dependence and finite-search limits. Complete [the scientific report](../team%20coordination/templates/scientific-validation-report.template.json) with observed checks for the exact tested SHA. S0–S4 labels require corresponding executed evidence; baseline cannot self-award S5.
