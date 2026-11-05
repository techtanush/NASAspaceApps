# Terrain analysis, candidate discovery, and planetary comparison

This file specifies algorithms for `characterize_target`, `screen_earth_candidates`, and `analyze_earth_candidate`. Dataset facts and limits are in [08](08-DATASET-CATALOG.md); provenance is in [09](09-DATA-INGESTION-AND-PROVENANCE.md). These are proposed application algorithms, not NASA-certified qualification standards.

## 1. Separate three questions by scale

The same application must preserve three distinct evidence scopes:

1. `regional_context`: compare target and Earth landforms at mutually supportable spatial scales.
2. `terrain_model`: investigate Earth terrain exposures and modeled routes at the support of the selected Earth DEM.
3. `field_validation`: determine physical hardware performance using appropriately resolved survey/field evidence.

A MOLA regional slope and a NASADEM local slope are not observations at the same scale. Neither supports wheel-scale clearance. The first live implementation can answer the first two questions with explicit assumptions; it must retain unknowns in the third. A user may define a regional terrain test and obtain a modeled result, but the system must not silently redefine a meter-scale physical requirement as a kilometer-scale one.

## 2. Body-aware geometry

Implement `science/geometry.py` with typed `BodyGeometry` and `AnalysisGridSpec`. Body is mandatory at every public science boundary. Earth uses WGS84 input coordinates and a suitable local projected CRS. For a small Earth AOI within one UTM zone, use that zone; for an AOI crossing zones, high latitudes, or excessive distortion, use a declared local projection and validate its scale distortion. Default maximum accepted linear distortion is 1 percent; exceeding it requires a smaller AOI or a more appropriate projection, not a hidden tolerance increase.

Moon and Mars use the source label's radius/ellipsoid, reference frame, latitude definition, longitude convention, and projected geometry. Construct a body-specific projection from that metadata. Never use Earth EPSG:4326 or Earth Web Mercator as the computation CRS for planetary data. EPSG:4326 is reserved for Earth GeoJSON in the API. Planetary preview layers are body-aware image/canvas layers with explicit coordinate transforms.

Do not treat planetocentric and planetographic latitude as interchangeable on an ellipsoid. Normalize longitude for computation, preserve its original convention, and split antimeridian AOIs before Earth discovery. Test longitude wrap at both 180° and 360°. Geometry errors become `BODY_MISMATCH`, `CRS_UNSUPPORTED`, `FRAME_UNRESOLVED`, or `DISTORTION_EXCEEDED`, not generic missing-data warnings.

The body shape used for distance is distinct from gravity used for energy. A Mars sphere radius cannot substitute for Mars gravitational acceleration, and a lunar projection does not imply lunar dynamics for an Earth field test.

## 3. Grid and support contract

Every metric has `analysis_grid_id`, pixel spacing in meters, derivative support, smoothing/aggregation history, valid-area fraction, source IDs, and evidence scope. Initial defaults are design settings:

| Purpose | Initial setting | Interpretation |
|---|---|---|
| Common Mars/Earth regional comparison | 1,000 m grid; 3×3 derivative plane | Roughly kilometer-scale landform comparison, subject to actual source support |
| Common Moon/Earth comparison | Choose the coarser supported grid from actual products | Product-specific; do not assume all LOLA data are 20 m |
| NASADEM Earth route context | 60 m analysis grid after declared aggregation | Modeled broad surface, not centimeter-scale obstacles |
| Relief/roughness windows | 3, 5, and 9 analysis pixels | Always display physical window sizes |

These defaults do not establish a source's actual effective resolution. Preflight must inspect selected products and record whether their support meets the requested analysis. If the coarsest effective support is larger than the default, increase the analysis support explicitly and rerun; if this violates the accepted mission scale, the affected requirement is `UNKNOWN`.

Use an odd-sized neighborhood with complete valid support for derivative metrics. Do not interpolate across nodata holes to create traversable bridges. For descriptive summaries, allow a configured minimum valid fraction with the fraction displayed; for route masks, any missing required support makes the relevant cell unknown and forbidden by default.

## 4. Elevation and gradients

Normalize elevation units to meters and maintain the vertical quantity. Absolute heights across worlds are generally not comparable because their reference surfaces and physical meaning differ. Prefer relative relief and normalized landform structure. A 2 km Earth elevation is not automatically analogous to 2 km above the Mars areoid.

For each cell center fit a plane to its 3×3 neighborhood in metric coordinates:

```text
z(x,y) = a*x + b*y + c
[a,b,c] = least_squares([[x_k,y_k,1]], [z_k])
surface_slope_deg = atan(sqrt(a*a + b*b)) * 180/pi
```

Center coordinates within the neighborhood before fitting to improve conditioning. For square unrotated grids, a fixed precomputed least-squares stencil is allowed, but results must match the general implementation. Use true affine coordinates for rotated/anisotropic grids or reproject to an approved north-up metric grid first. Missing any required sample invalidates the slope cell. A raster border without halo is nodata, not zero slope.

Aspect is downslope azimuth clockwise from north, derived consistently from `(-a,-b)` in an east/north grid. For a flat plane below a declared gradient tolerance, aspect is null. Gradients are dimensionless rise/run. Angles are degrees in persisted UI-facing quantities and radians in trigonometric operations.

Route-direction longitudinal grade uses the horizontal unit heading `u`: `grade_long = (a,b) dot u`; the cross-heading grade uses perpendicular `n`: `grade_cross = (a,b) dot n`. Their arctangents are directional grade proxies. A route following a contour can have zero longitudinal grade on a steep hillside. Therefore the generic rover maximum slope conservatively gates full `surface_slope_deg`; it must not gate only endpoint elevation change. Explicit pitch/roll limits may be added with an approved geometry model, not substituted without user acceptance.

## 5. Roughness and relief definitions

Implement and version each metric rather than using one ambiguous `roughness` number:

- `detrended_rms_height_m(window)`: fit a local plane and compute `sqrt(mean((z-z_plane)^2))`. It quantifies surface departures at that window's support. A steep perfect plane has zero detrended roughness.
- `robust_relief_m(window)`: `quantile(z,0.95)-quantile(z,0.05)` using a documented quantile implementation. It includes slope-induced relief and must not be called obstacle height.
- `tpi_m(window)`: center elevation minus neighborhood mean, with center inclusion policy fixed in the algorithm version.
- `slope_distribution`: area-weighted histogram and quantiles of valid surface-slope pixels.

A 180 m-window RMS height does not measure a 0.20 m obstacle. Neither roughness nor relief can be compared directly to ground clearance. If a clearance requirement requests obstacle height at a scale unsupported by the source, emit `SCALE_UNSUPPORTED` and `UNKNOWN`, even if the DEM's decimal precision looks fine.

Do not call a raster cell's height standard deviation a geological material measurement. Terrain classes such as low/medium/high detrended relief are numerical classes with fixed, accepted thresholds; they are not rock, sand, or basalt classes.

## 6. Common-scale target/Earth comparison

Prepare each body's source in its own local metric projection. Aggregate to matched physical cell support and matched metric windows. The maps need not share a geographic coordinate system; they must share quantity definitions, physical support, masks, and aggregation semantics. Do not reproject Mars into an Earth CRS to make arrays align.

For slope histograms, default edges are `[0,2,5,8,12,15,18,25,35,90]` degrees, plus counts/valid area. These are design bins, not measured requirements. Include an upper overflow bin if numerical policy allows values beyond expected ranges. Weight each valid cell by physical area; use declared projected cell areas only after distortion checks.

For one-dimensional distributions compute the Wasserstein-1 distance using the empirical distributions or a declared binned approximation. For the binned approximation, place each bin's probability at its representative center `x_i`, ordered in degrees, and let `F_i` be cumulative mass through center i:

```text
W1 = sum_i abs(F_target[i]-F_earth[i]) * (x[i+1]-x[i])
# i runs from 0 through n-2; both distributions use identical centers.
```

Persist degree units and binning approximation. Do not convert this to a universal percent Mars-likeness. For scale-dependent roughness use matched windows and compare quantiles or the same distribution distance in meters. Contract-specific maximum distances or minimum exposure fractions are required before qualification; the engine must not invent a PASS threshold after seeing results.

Pixel counts are not independent observations. Spatial autocorrelation and resampling limit effective information. Report valid area and support, not a confidence percentage obtained from millions of correlated pixels. Confidence policy is in [11](11-QUALIFICATION-AND-UNCERTAINTY.md).

## 7. Earth discovery is coarse to fine

The scout must be capable of proposing candidates beyond a handpicked famous-site list. Implement a bounded search over an explicitly selected Earth search extent; show that extent and exclusions. Version 1 is not obligated to process global high-resolution Earth terrain in one request.

Discovery stages:

1. Validate mission-required observables and their source coverage. Derive requested support and required candidate size from test length/area, without relaxing accepted thresholds.
2. Generate candidate windows on a deterministic grid over the selected search extent, or use a persisted coarse feature index. The default regional window is 20 km × 20 km, configurable before the run. Grid spacing, overlap, origin, and candidate cap are recorded.
3. Exclude water-only/out-of-coverage windows and windows lacking minimum data support. Unknown mineral coverage is a penalty/issue, not an invented absence or automatic Earth-region rejection unless the mission requires known mineral evidence.
4. Compute broad terrain summaries from available verified coarse assets. Cache those summaries by source and algorithm. A not-yet-built coarse index must trigger bounded acquisition rather than returning fabricated precomputed scores.
5. Rank only by mission-relevant observable deficits and evidence coverage. Keep the Pareto front and a deterministic diversity subset; no universal similarity score enters the qualification API.
6. Investigate up to the configured number of windows at finer supported Earth DEM scale, including at least one eligible non-reference proposal when available. If none is found, disclose this instead of renaming a known site.
7. Identify contiguous zones suitable for actual route testing. Histograms across disconnected patches do not prove a continuous test exists. Pass selected zones to [12](12-ROUTE-ENERGY-AND-VERIFICATION.md).

Initial operational limits: at most 80 regional windows screened and 5 candidates fully analyzed per run, unless configuration explicitly raises the budget. Store considered/excluded windows and reason codes. Hitting a cap means discovery is bounded/incomplete, not that the returned site is globally optimal.

## 8. Novelty and reference candidates

Use the shared `EarthAnalogCandidate.origin` values: `KNOWN_CONTROL`, `DISCOVERED`, `USER_SUPPLIED`, or `SYNTHETIC_CONTROL`. Record grid/index details in `discovery_method`. Use the shared `novelty_status` values: `KNOWN_ANALOG`, `NOT_IN_REFERENCE_LIST`, or `NOT_ASSESSED`. The second status means absent from the pinned comparison catalog, not newly discovered by humanity. A discovered candidate later recognized as known retains its original origin and updates only its assessed novelty in a new revision. UI language is "candidate beyond the reference set" until independent expert review supports a stronger claim.

NASA's [Planetary Analog Explorer](https://science.nasa.gov/solar-system/analog-explorer/) is a useful reference source for validation context. Its named sites must not be used as hidden labels that force the qualification algorithm to pass. Reference-site inclusion, georeferencing, mission relevance, and source citation are separately reviewed metadata.

## 9. Outputs and tests

`TerrainAnalysisResult` contains raster artifact IDs, distributions, scale table, coverage, quality issues, connected-zone summaries, source/evidence IDs, algorithm lock, and scope. All missing quantities are null with reason codes. Tool execution success does not imply candidate qualification success.

Acceptance tests: flat plane slope 0; analytic inclined plane within 1e-6 degrees on the interior; anisotropic grid gives the same physical slope; rotated grid equivalence; detrended plane roughness near zero; nodata halo propagation; area-weighted histogram sums to one; planetary radius-to-height conversion exactly once; wrap/polar geometry; a disconnected candidate passes descriptive screening yet fails a continuous-route requirement. Source-specific real-data validation is in [29](29-SCIENTIFIC-VALIDATION.md).
