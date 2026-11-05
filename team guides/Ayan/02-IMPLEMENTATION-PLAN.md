# Ayan implementation plan

Implement pure numerical correctness first, then source realism, then optimization/detail. Keep progress and actual tests in `team handoffs/ayan/implementation-status.md`. Every scientific output carries scale, method, inputs and limitations.

## S-A0 Establish contracts and offline fixtures

Confirm Ayan branch/worktree. Read architecture00/05/08–13/26/29 and shared03. Use current public schemas C1 until accepted F0 ports arrive. Create your owned `science` package and operation-specific value types; avoid importing nonexistent platform internals. If F0 is pending, use a local test fixture implementing the **documented port**, not a second production interface.

Generate small flat/inclined/bumpy/nodata rasters with explicit metric CRS/body/units and deterministic seeds. Copy the canonical graph/constraints fixture semantics, keeping its mock resource provider test-only. Include machine expected values and source labels. No fixture generated from a formula is NASA data.

## S-A1 Terrain and comparison core

Implement normalized source handles, valid/water masks, cell registration, bounds, height scaling/offset and source/body metadata. Handle Earth projected metric grids and planetary source frames separately. Preserve native support while resampling; aggregation can establish comparable coarser support but upsampling cannot create measurement resolution.

Compute slope from documented derivative neighborhoods, detrended roughness rather than raw tilt, local relief and valid-area/coverage statistics. Propagate nodata and border policy. Separate surface slope from longitudinal/cross-heading grade. Define feature/measurement/rule registries with exact units/windows/parameters and deterministic hashes.

Implement compatible-scale comparison and per-requirement status/confidence. Missing or incompatible evidence gives UNKNOWN; known analyzed absence gives FAIL; physical gap registry gives GAP. Requirements parameters hold slope band/counting/tasks/co-location; numerical lower is required exposure distance, not the slope endpoint.

Exit: analytic expected-value/property tests pass and complete candidate matrices return evidence-backed proposals. No floating NaN or missing value becomes zero.

## S-A2 Route energy and independent verification

Build bounded Earth directed graph from valid/masked metric cells. Enforce full surface slope, supercover hazards, diagonal corner rules, waypoint snapping and return. Track tasks, unique undirected exposure, optional contiguous exposure, class thresholds and edge-use limits. Repeated travel consumes energy/time but does not automatically earn new unique exposure.

Implement the accepted Earth energy model with explicit rolling/efficiency/idle/task/roughness/uncertainty assumptions and Earth gravity. Battery size alone is not a consumption model. No downhill regeneration credit unless separately supported; missing coefficients yield unknown/inconclusive energy.

Implement bounded multi-resource labels/search, valid dominance/pruning and deterministic tie-breaks. Record every approximation/label pruning/budget. FOUND is only a proposal; independent verifier reloads actual grid/constraints/route and recomputes all metrics. Queue empty after lossy pruning cannot become exact infeasibility. Produce machine-readable violations and scope-supported failure classification.

Exit S0: graph first120m/26Wh/0m steep exposure FAIL, repaired340m/34Wh/150m steep exposure PASS, both unchanged criteria; one-expansion limit INCONCLUSIVE; falsified solver totals rejected; production energy tests separate from mock graph. Publish a tested S0 SHA and typed facade coverage immediately.

## S-A3 Connect platform port and scientific display

Merge accepted F0/main into your branch. Implement `ScienceService.execute` through your facade with cancellation/deadline/progress and safe scratch I/O. Return artifacts/evidence drafts with local keys/parents, not fake persisted IDs. Handle cache keys from input bytes+algorithm+scale/config; no stale cached result under changed source inputs.

Provide display-layer manifests/images: Earth Web Mercator image with WGS84 corners, planetary planar image with body-specific affine/CRS, units/legend/masks/attribution/scale. Display smoothing must not alter executable route geometry. Hand an actual fixture manifest/image to Aradhya and a facade result to Tanush for registration tests.

Exit: Tanush registrar can persist your results and expose real evidence/receipt IDs without a numerical rewrite; Aradhya can draw layers without interpreting raw binary source formats.

## S-A4 Real source adapters

Implement NASADEM/SRTM discovery/decoding including coverage/NUM/water semantics; MOLA maintained PDS products/counts/frame; LOLA labels/scaling/radius reference/polar coverage. Resolve actual metadata/version/access and lock actual bytes. Reject HTML login pages, wrong endian/shape/unit/CRS, corrupt checksums, path-traversing archives and unauthorized redirects. Keep authentication provider-specific and tokens out of artifacts.

Freeze permitted source policy; append newly acquired permitted granules immutably. A corrected existing source interpretation or version requires new lock/run, not silent mutation. Every derivation pins exact parent hashes.

Add EMIT supported mineral/geolocation/quality/uncertainty processing and Diviner selected thermal variable/time-support processing. Correct no-coverage/unsupported/access behavior is required even if no usable source is available for the final scenario. Do not average categorical mineral IDs or compare incompatible thermal quantities.

Exit: actual Earth/Mars/Moon source paths validated where access permits; optional-layer state tested; source report separates fetched bytes from registry references. Actual NASADEM coverage gates may exclude famous sites; reputation cannot override missing source coverage.

## S-A5 Discovery portfolios and scientific validation

Implement bounded source-supported coarse screening and detailed analysis of promising windows, with known controls and a beyond-reference-list candidate. Record search extent, exclusions, feature scores and stop reason; no global-best or global-novelty claim. Mission changes alter relevant objectives/evidence/ranking as appropriate.

Implement portfolio coverage/min-site objective, residual gaps/unknowns and co-location. A continuous experiment cannot join slopes from different countries. Separate site tests remain required for portfolio claims. No fabricated travel costs.

Run known-control recovery, negative control, mission sensitivity, scale/proxy critique, actual raster-route results and alternative-source dependence checks. Real data is outcome-neutral: it may remain FAIL/UNKNOWN/INCONCLUSIVE after a legal repair. Never hardcode a live second attempt to pass.

## S-A6 Final handoff

Run own05, port tests with real platform registrar and actual display consumer. Commit only owned code/config/tests/reports, no downloaded bulk data or secrets. Produce S1 report with exact tested/base SHA, operations supported, source metadata/checksums available, numeric tolerances, examples, dependencies and blockers. Continue until all owned operations and tested failure paths are complete; distinguish software completion from unperformed real-data/field validation.

## Mandatory scientific implementation checkpoint

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
