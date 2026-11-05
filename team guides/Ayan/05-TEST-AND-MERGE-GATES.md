# Ayan scientific testing and merge gates

Your merge evidence must establish numerical correctness and honest scope, not just produce attractive terrain maps. Separate pure synthetic tests, verified-source replay, actual source access and physical performance. No real-data gate passes from a registry entry alone.

## Numerical fixture tests

- Flat metric plane: slope/relief/detrended roughness0 at valid interior cells.
-10°/20° plane: correct angle within declared tolerance, detrended roughness near0; contour-heading traversal still rejects surface20° for18° cap.
- Known bump/noise: distinguish terrain roughness from overall tilt; test support-window sensitivity and units.
- Nodata/water/channel/diagonal: derivatives/masks propagate and no illegal supercover/corner crossing occurs.
- Planetary scaling: apply integer scale/offset/radius interpretation exactly once; fail unresolved frame/vertical units rather than defaulting Earth.
- Longitude seam/polar grids: body-aware transforms, normalized positive-east API input, preserved native metadata, correct actual scale.
- Comparison: aggregate to a valid common support; no higher confidence/clearance claim from upsampling.
- Requirement boundaries: angle-band inclusion, distance threshold equality, units, mandatory/optional/gap/unknown and co-location parameters.

Use independent expected values and mathematical properties, not snapshots copied from the function under test. Record tolerances and why they are appropriate. Quantities must be finite; null stays unavailable. Test that related NASADEM/SRTM agreement does not claim independent observations.

## Route and energy tests

Canonical graph120m/26Wh/0m exposure must fail EXPOSURE_SHORTFALL; repaired340m/34Wh/150m exposure must pass with W1/W2/return and unchanged contract. The mock edge energies are test-only. Oscillating across the same steep edge cannot multiply unique terrain exposure. Each traversal still costs time/energy.

Test true production Earth energy formula: J→Wh conversion, rolling+uphill terms, idle during drive/dwell, incremental task cost, no downhill credit, conservative uncertainty/reserve, invalid efficiency and missing model. Negative reserve is not clamped. Earth test uses Earth gravity, not Mars gravity.

Test waypoint tolerance/snapping/tasks/return, maximum surface slope, forbidden/unknown intersections, class thresholds, length/time/edge limits, exact and approximate search termination, cancellation. Force one-expansion/label/time cap and require INCONCLUSIVE/SEARCH_LIMIT. Exact finite-model infeasibility is permitted only with complete lossless search/proof for that declared domain. Independently verify a corrupted route and falsified solver totals; the verifier must reject them.

## Source and qualification tests

For NASADEM/SRTM/MOLA/LOLA use actual small permitted source/replay fixtures where available and verify checksum, shape, label/CRS, units, nodata/quality and derived support. Test EDL auth failure, HTML login response, bad archive member/size/redirect, source checksum mismatch, unsupported frame/format and no coverage. Those are input/dependency states, not terrain FAIL.

EMIT tests categorical mineral handling, geolocation/quality mask and valid retrieval fractions. Diviner tests actual variable/time-support/Kelvin semantics. Missing target mineral or compatible Earth thermal evidence remains UNKNOWN even if an attractive Earth layer exists. Physical clearance/traction/autonomy remain UNKNOWN without suitable evidence.

Discovery tests known controls, obvious non-analog negative control, beyond-reference candidate origin, mission sensitivity, finite search extent and stopping. Portfolio tests minimum site-count/coverage tradeoff, residual gaps/unknowns and co-location; no joining a continuous route across sites or invented logistics cost.

## Port and integration tests

Pure math imports without FastAPI/SQLAlchemy/OpenAI. Facade accepts F0 port models and returns all artifact/evidence drafts with resolvable local keys, input hashes/units/body/scale. Cancellation/deadline tested. Live mode rejects mock resource provider; offline mode makes no external calls. Registrar integration persists actual UUIDs and route telemetry without altering computed values. Display consumer renders image/manifest correctly and preserves mask/source scale.

## Required commands

From `analogforge/`, after environment/bootstrap:

```bash
rtk proxy uv run pytest tests/unit/science tests/property/science tests/integration/science
rtk proxy uv run pytest tests/replay/science
rtk proxy uv run ruff check src/analogforge/science src/analogforge/adapters/earthdata src/analogforge/adapters/pds
rtk proxy uv run mypy src/analogforge/science
```

Provide a documented opt-in source validation command under `scripts/science/` and report actual selected files/checksums. External access tests never run implicitly in every offline CI invocation. Run complete science suites after scientific input/algorithm changes; avoid unrelated installation or repeated unchanged full-world downloads.

## Ready to merge

No failing/unrun mandatory pure tests, unexplained tolerance changes, fake NASA labels, unsupported PASS, out-of-scope file changes, secret/raw-data commits or incompatible port. Source-dependent gates may be BLOCKED_EXTERNAL only with precise remediation and honest limited capabilities; they cannot be marked verified. Record tested SHA/base/locks, numeric outcomes, runtime/resource measurements, supported operations, actual source probes and remaining limitations. Tanush runs the combined app gate before main advances.
