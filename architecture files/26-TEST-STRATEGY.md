# Test strategy and release gates

Test scientific and workflow claims with deterministic fixtures before relying on live sources or stochastic model output. A rendered dashboard is not acceptance of a scientific integration. CI must clearly separate offline software correctness, real-data adapter validation, live AI behavior, and physical evidence the prototype cannot supply.

## Test layers

| Suite | Inputs | Required assertions |
| --- | --- | --- |
| Schema/contracts | Domain schema, examples, exported OpenAPI | JSON Schema validity, strict fields, unit/ID validation, client generation, response compatibility. |
| Scientific units | Analytic arrays and tiny graphs | Known slope/roughness/relief values, no-data masking, coordinate transforms, energy units, exposure accounting. |
| Property tests | Random valid rasters/routes/configs | Nonnegative distance/energy, no invalid-cell traversal, deterministic hashes, monotonic reserve with positive added work, no duplicate exposure credit. |
| Application policy | Fake repositories/typed receipts | Immutable contract, workspace scope, status/evidence rules, state transitions, review behavior, no unearned PASS. |
| Database integration | Real Postgres/PostGIS container | Migrations, constraints, leases/fencing, atomic events, revision/idempotency, RLS and artifact refs. |
| API | Real services with fake network adapters | HTTP semantics, all action variants, SSE replay/expiry, auth and quotas. |
| UI integration | Generated API fixtures | Loading, empty, unknown, failure, blocked, cancellation, resync, keyboard access; no optimistic science results. |
| End-to-end offline | Browser + full API/worker + synthetic data | Mission/rover, acceptance, qualification, critic, PROVE IT fail/replan/pass, export and reload. |
| Adapter replay | Checksummed tiny real products/crops | Labels/CRS/units/quality decoder behavior and stable derived metrics without network. |
| Live integration | Real credentials/products/model | Actual capability/access/tool receipts and honest outcome; opt-in, separately reported. |

## Analytic scientific fixtures

Create fixtures in code from known formulas; do not hand-edit arrays until they look plausible. Seed all random generators. Tiny arrays fit in repository and have explicit body/CRS/units/masks.

1. Flat plane: `z=100` with metric cell spacing; slope0, local relief0, detrended roughness0 except deliberately masked border policy.
2. Inclined plane: `z=x*tan(theta)` for theta10° and20°. At valid interior support, slope matches theta within declared numerical tolerance; detrended roughness≈0. On20° terrain a contour-heading edge still fails a generic18° full-surface-slope cap.
3. Tilted plane plus known bump/noise: distinguishes raw elevation variation from detrended roughness; verifies meter-valued roughness and scale dependence.
4. Nodata hole/channel and water strip: derivative neighborhoods masked, route supercover blocks forbidden/unknown cells, diagonal corner cutting rejected.
5. Source label scaling fixture: raw integer radius/elevation values with offset/scale; apply exactly once, reject missing reference metadata.
6. Planetary longitude seam: 359.9°/0.1° target, body-aware area/distance and no Earth CRS substitution; polar footprint behavior.
7. Comparable-scale test: high-resolution terrain aggregated to a coarser common support and compared there; upsampling never upgrades native evidence support.
8. Exposure-band boundary: 8,12,15,18° samples each assigned under the documented interval policy; sum does not double count boundaries.
9. Independent verifier: deliberately falsify solver energy/exposure totals and confirm verifier recomputes/rejects them.
10. Missing energy coefficients: cannot calculate a reserve from battery capacity alone; energy becomes UNKNOWN/INCONCLUSIVE with remediation.

Use physical tolerances appropriate to derivation and grid, not a generic equality rule for every float. Publish chosen tolerances in algorithm config and tests. A unit test confirming an implementation's own output without an independent expected value does not validate science.

## Failure and replan fixture

Use the graph defined in 12 and `examples/synthetic-route-graph.json`. The first route has120m length,26Wh mock consumption and0m unique steep exposure; it fails the accepted≥100m exposure. The repaired route has340m length,34Wh mock consumption and150m unique steep exposure, visits both tasks and returns; it passes the graph test. The mock energy provider is test-only and visibly synthetic. Separate tests exercise the production energy equation.

Assertions: both attempts have immutable result IDs; contract and rover hashes match; route/receipt IDs differ; `EXPOSURE_SHORTFALL` is preserved; one replan decision is evidenced; final passport includes both attempts; no threshold changed; repeating an edge earns energy/time costs but no extra unique exposure. A one-expansion search must be INCONCLUSIVE/SEARCH_LIMIT. No production code contains a hardcoded "second attempt passes" rule.

## Agent evaluations

Offline scripted provider fixtures test every role's valid output and malformed schema, missing evidence, wrong workspace, unsupported tool, stale revision, prompt injection, fabricated measurement, refusal, timeout, cancellation and budget exhaustion. Role output shape is not proof of correctness; assertions inspect selected tools, evidence IDs and backend decisions.

Live agent evaluation uses at least six tasks: baseline mobility; thermal-only with no Earth thermal evidence; physical clearance with coarse DEM; mission change requiring different shortlist; critic invalid-scale challenge; failed route requiring diagnosis. Assess factual/evidence adherence and legal decisions, not verbatim wording. Repeated runs may choose different legal investigations but cannot change deterministic measurements.

## UI and accessibility checks

At desktop1440px, tablet900px and mobile390px confirm readable workbench, no hidden requirement rows, correct focus order, status text/icons beyond color, selectable evidence, accessible modal/review controls, and map/table equivalence. A WebGL failure must retain candidate list, matrices, route metrics and exports. SSE disconnect must preserve committed results and reconnect without duplicate actions. Browser back/deep-link reload must restore the selected run.

## Release gates

G0 blueprint: link/schema/example validation passes. G1 foundation: migrations, health, typed client and synthetic seed. G2 deterministic science: all analytic/graph tests and independent verification. G3 core workflow: full offline end-to-end including critic/fail/replan/export. G4 real terrain: checked NASADEM/SRTM, MOLA and LOLA sources, CRS/scale lineage and outcome-neutral verification. G5 full scope: portfolio, optional-layer coverage behavior, no-rover flow and all empty/error/recovery states. G6 live agents: real model receipts and typed tool loop. G7 hosted readiness: identity, isolation, quotas, backups/restore and proxy SSE. Record gates separately; passing G3 does not imply G4/G6.

Required software gate pass criteria: no unexplained test failures, schema/client drift, broken links, fabricated fixture provenance, secrets, critical unresolved critic issues hidden from report, or unbounded retry loops. Performance targets in25 are measured on locked hardware; if unmet, record and fix the bottleneck rather than deleting constraints.

## Completion report

Produce `verification-report.json` with source commit/build lock, test suite counts, timestamps, modes exercised, real source/AI probes performed, gate outcomes and remaining blockers. List unsupported physical claims explicitly. A coding agent must not say "everything works" when it only compiled the frontend or exercised synthetic data.

## Mandatory scientific integrity matrix

The [shared SCI-01–SCI-18 gate](../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md) supplements G0–G7 and must pass for combined local integrity/UI/export acceptance. It catches source/scale/coverage/uncertainty/mode/solver/critic/claim defects, and verifies truthful negative publication. Record actual S0–S4 evidence with [the scientific report template](../team%20coordination/templates/scientific-validation-report.template.json). Offline integrity tests cannot establish G4 real-data or G6 live-agent readiness. [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) defines backend gate semantics.
