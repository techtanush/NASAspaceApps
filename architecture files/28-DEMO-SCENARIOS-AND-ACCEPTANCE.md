# Demo scenarios, negative controls and acceptance evidence

The scenarios in this document validate the complete product; they are not instructions to hardcode outcomes. All runtime modes obey `00-ARCHITECTURE-DECISIONS.md`. Acceptance must distinguish scientific validity, software correctness and presentation quality. A smooth animation is not evidence of a real calculation.

## 1. Runtime-mode contract

| Mode | Inputs and operations | Permitted presentation |
|---|---|---|
| `live` | Real scientific products, real configured model requests and deterministic tool execution. | “Live investigation”; tool/agent rows appear only after actual work. Missing input blocks affected work. |
| `synthetic` | Analytically generated rasters, explicit fixture metadata and scripted agent decisions where used. | “Synthetic test scenario”; validates algorithms/workflow, never a real-site scientific recommendation. |
| `replay` | Immutable previously computed artifacts, checksums and recorded operation receipts. | “Recorded replay” with original computation timestamp/mode; playback never pretends new data/model calls occurred. |

Run mode is immutable. A disconnected live run cannot silently switch to replay. Offer opening a separately labeled replay run when available. Export preserves run mode, original evidence mode and provenance of imported replay evidence. Do not label synthetic terrain NASADEM/MOLA/LOLA merely because the fixture exercises those adapters.

## 2. Scenario package manifest

Each executable scenario needs a versioned manifest, stored under implementation fixture data rather than inferred from prose:

```text
scenario_id and version
purpose / runtime mode / original computation mode where replay
mission contract fixture and accepted revision digest
rover profile fixture and revision digest (nullable only for site-only scenario)
target body, region, longitude convention, CRS/datum
candidate AOIs and origin labels (control/catalog/manual/discovery)
required products/granules, local paths or authorized retrieval refs
source checksums, source licenses, product versions and acquisition context
comparison grid/scale, derivation/tool versions and parameter hashes
energy model parameters, task assumptions and uncertainty treatment
search/replan budgets, deterministic seeds and solver tie-breaking rules
required observed branches and forbidden claims
expected assertions and numerical tolerances
recorded evidence/attempt/event IDs and digests for replay
```

Do not store credentials in manifests. Live-preflight seed-source identifiers/geometry/checksums and allowed source policy/product versions must be resolved and frozen before claiming the scenario is ready. Permitted newly discovered granules append a new immutable acquired-asset manifest revision; final passport pins all actual bytes. No existing derivation may silently change its input hashes. This architecture does not invent final granule IDs or claim that an uncomputed location will pass. Synthetic fixtures must include the generator version/parameters so they can be regenerated.

Numerical assertions use tolerances defined by science/tool specifications. Presentation rounding is never the tolerance policy. Record metric differences and artifact versions when comparing repeated runs.

## 3. Required scenario catalog

### SC-01 — Mars terrain investigation with ARES-1, live

**Purpose:** real Mars target → real Earth terrain candidates → complete qualification, critic, compatibility, verification and passport.

**Preparation:** choose a MOLA-covered Mars region and Earth candidate regions for which approved terrain products can be retrieved and analyzed at a documented compatible scale. Include a known-analog control, one discovered/nominated region outside the known-example list, and a negative control. Resolve exact geometry and products in the scenario manifest. No candidate is premarked `PASS`.

**Rover:** ARES-1, 42 kg, safe slope 18°, clearance 0.20 m, wheel diameter 0.30 m, 1800 Wh, 20% minimum reserve, 0.5 m/s nominal speed, stereo/IMU/LiDAR and declared navigation/sampling capability.

**Mission:** terrain mobility, slope-band exposure, roughness/relief diversity, two task waypoints, return to base and modeled battery reserve. Example exposure proposals may start with 100 m at 8–12°, 200 m at 12–15° and 100 m at 15–18°, but final values must be reviewed and frozen before the run. These are scenario assumptions, not NASA requirements. Include Mars gravity/atmosphere as explicit gaps. If geology is requested, require actual supported geology evidence or retain that dimension as unknown/partial under policy.

**Execute:** author and accept contract → pin rover → characterize MOLA target → discover/analyze Earth candidates → critic → select candidate → generate test → deterministic verification → bounded diagnosis/replanning where warranted → final passport/export.

**Assert:** all quantitative claims link to real receipts; source/comparison scale is visible; terrain results do not certify 0.20 m obstacles or autonomous navigation; no false geology claim; contract/rover digest fixed across attempts. A truthful final `FAIL`/`INCONCLUSIVE` is valid. The product must not force final success.

**Demo preparation for failure/replan:** if a real computed failure and later real computed repair have been found within one frozen contract, record both. If not, use SC-03 to demonstrate the branch or a separately labeled checksummed replay. Do not alter a live result to improve the story.

### SC-02 — Moon target and gap treatment, live

**Purpose:** genuine lunar data path, planetary coordinates and unsupported natural conditions.

**Preparation:** select a LOLA region with approved terrain data and supported lunar projection. For a thermal requirement, configure the Diviner adapter and inspect actual product coverage/time context. Pick Earth candidates according to this mission rather than copying SC-01's result order.

**Mission:** lunar surface-mobility or surface-operations test with measurable terrain conditions, an optional/required thermal dimension as specified, lunar gravity and vacuum. Pin ARES-1 or a separate explicit rover profile. The Earth's terrain does not reproduce lunar wheel–soil interaction.

**Assert:** Moon panel contains lunar CRS/longitude metadata; Earth geometry remains WGS84; gravity/vacuum stay `GAP`; thermal is supported only by retrieved comparable evidence. Missing Earth/lunar thermal source results in `UNKNOWN`, not an inferred pass based on a cold place name. Final passport is available with residual gaps and limited scope.

### SC-03 — Statistically promising site fails continuous test, synthetic

**Purpose:** reproducible demonstration of qualification versus verification and genuine failure-driven replanning.

**Fixture construction:** analytic candidate A contains enough desired slope/roughness values in its overall analyzed distribution, but the required exposure lies outside the start-reachable safe terrain component under the accepted rover limit/forbidden-area definition. Use an explicit known unsafe/forbidden barrier, not unknown pixels, to distinguish modeled failure from data insufficiency. Candidate B contains a connected safe corridor with the required exposures, reachable task waypoints and adequate modeled energy under frozen assumptions.

The generator and independent fixture checks must establish those properties before this scenario is accepted. The route engine still computes every attempt; no frontend constant supplies its result. A graph reachability certificate may support impossibility for the fixed modeled grid/zone. A generic timeout cannot.

**Execute:** site-level distribution qualification supports terrain → first proposed route/test fails a required reachable-exposure constraint → diagnosis cites that constraint → replan changes route zone or candidate to B without changing mission/rover → verification independently computes a pass if supported.

**Assert:** candidate A's site statistic and failed route are both displayed with their different scope; route attempt receipts resolve; fixed digests unchanged; pass only appears after B is computed; synthetic badge is visible in all screens and exports. If the fixture fails to produce the intended branch, fix the fixture generator or algorithm, never fake the badge.

### SC-04 — Insufficient modeled energy and bounded repair

Use a synthetic or checksummed real-data fixture in which the first test route exceeds usable battery energy under explicit drive/task model parameters. Required minimum reserve remains 20% for the ARES example; usable energy ceiling is computed by the deterministic model, not retyped in the UI.

Assert the exact failed reserve benchmark and modeled assumptions. A shorter legal path preserving waypoints/exposures can be attempted. If none found within budget, result remains inconclusive or failed for the tested route as warranted. Replanner cannot reduce required reserve, omit tasks or increase battery capacity. Proposed hardware changes require a new profile/revision and new run, not automatic success.

### SC-05 — Missing mineral coverage and Scientific Critic challenge

Mission explicitly requires mineral evidence. Supply valid terrain and no approved mineral coverage for at least one candidate. Scout proposes the site on terrain; critic flags the unsupported mineral claim. Qualification must remain `UNKNOWN` or a policy-supported limited proxy `PARTIAL`, never direct mineral `PASS`.

If a second candidate has legitimate mineral evidence, retrieve/verify it and revise the assessment with provenance. If not, close with unresolved geology. Assert challenge → evidence request → receipt/unavailable result → explicit resolution or unresolved blocker. A role merely saying “I checked” without evidence does not satisfy this case.

### SC-06 — Incompatible spatial scales

Provide terrain rasters with different native resolutions and a requirement concerning features below their supported scale. A valid comparison can aggregate to a supported common footprint; an unsupported fine-obstacle requirement remains unknown. Assert original and effective resolution, aggregation/window parameters, critic finding and downstream limitation. Browser zoom cannot clear the limitation.

### SC-07 — Composite complementary campaigns

Provide two sites with complementary supported dimensions and at least one residual physical gap. Mark which experiment requirements may be satisfied across separate campaigns and which require co-location/continuous execution. Compute a bounded portfolio objective including a site-count penalty.

Assert a requirement-to-site assignment, site-specific verification results, residual gaps and objective receipt. Required concurrent mobility-plus-thermal conditions cannot be declared met by putting mobility at one site and cold at another. A continuous route cannot sum distances from unrelated sites. Unknown access/travel/permissions remain unmodeled.

### SC-08 — Negative control: low-relief candidate

Use an analyzed real or synthetic low-relief region as a negative control for a steep-exposure mission. Do not hardcode failure because it is tropical, urban or visually green. Compute the relevant terrain evidence; fail/partial the desired exposure only when supported by measured absence/insufficiency. Confirm that a single matching statistic does not compensate for a mandatory failed dimension.

### SC-09 — Mission sensitivity

Use the same target/candidate set with two separately accepted contracts: terrain mobility and thermal operations. Hold relevant data/geometry constant and change the experiment requirements. Assert requirement/evidence requests and qualified-use conclusions differ according to the contract. Ranking need not always change; identical rankings are valid if justified by the actual evidence. Hardcoding a forced order change is not a valid test.

### SC-10 — No-data versus physical gap versus measured zero

Fixture contains valid zero elevations, masked no-data cells, no thermal coverage and a gravity requirement. Assert zero remains numeric zero, missing data produces `UNKNOWN`, gravity produces `GAP`, and uncomputed rows are pending. A route needing unknown terrain is not certified safe. Export preserves nulls and mask/coverage metadata.

### SC-11 — Search limit without proof of infeasibility

Run a deliberately low search budget on a valid nontrivial terrain graph. Assert `INCONCLUSIVE` with `SEARCH_LIMIT` and stated explored bounds/budget. Any best-found partial route is labeled partial and cannot produce all-green success. A retry uses the documented dependency/budget policy; changing accepted requirements is not part of retry.

### SC-12 — Contract and rover revision immutability

Start a run; attempt to edit a slope exposure, reserve threshold and rover limit through UI and direct API. UI routes edits to new revision/run. Backend rejects mutation of pinned revisions or unauthorized actions. Original test/passport digests remain unchanged. A new accepted mission/rover combination creates an independent run with a clear comparison link if supported.

### SC-13 — Resumable connection and worker failure

While qualifying/verifying, disconnect stream, reload browser, deliver duplicate/missing events, expire cursor and restart worker within the supported lease model. Assert snapshot/cursor resynchronization, one logical command per idempotency key, preserved artifacts, accurate terminal state and no invented progress. Worker retries cannot duplicate a committed verification attempt as a different scientific result without attempt lineage.

### SC-14 — Site qualification without rover

Create run with null rover revision. Characterize target, discover/qualify candidates, critic review, build limited passport. Assert compatibility and PROVE IT are unavailable with reason. Choosing a rover later creates a new run pinning that revision; existing run remains null and historical passport unchanged.

### SC-15 — Tampered replay artifact and export verification

Create a replay from valid recorded evidence, then deliberately modify one fixture blob in an isolated test copy. Checksum validation rejects corrupted evidence; no final verified badge/passport may cite it as intact. Separately verify normal HTML/JSON/CSV export digests and provenance. Tampered artifact does not trigger a network/model call labeled as replay unless a separate explicitly requested live run is created.

## 4. End-to-end acceptance matrix

| Acceptance ID | Required observation | Product requirements |
|---|---|---|
| E2E-001 | Manual mission draft → fingerprint proposal job → explicit accepted revision → run. | PR-001–004, PR-010–017 |
| E2E-002 | Manual/JSON rover paths validate, preserve unknowns and pin revisions. | PR-020–025 |
| E2E-003 | Real Mars and Moon adapters produce body-correct profiles and evidence-linked passports. | PR-030, PR-035, PR-083 |
| E2E-004 | Bounded discovery includes controls/new candidate origin and preserves exclusion reasons. | PR-031–036 |
| E2E-005 | Every requirement has a supported status/evidence/scale with honest no-data handling. | PR-040–046 |
| E2E-006 | Critic challenge reopens work or remains unresolved with concrete affected IDs. | PR-050–054 |
| E2E-007 | Compatibility differs from site qualification and route verification. | PR-060, PR-065 |
| E2E-008 | PROVE IT generates independent benchmark receipts and immutable attempts. | PR-061–066 |
| E2E-009 | Bounded diagnosis/replanning preserves frozen requirements and explains terminal limits. | PR-070–073 |
| E2E-010 | Composite assigns responsibilities without violating co-location requirements. | PR-074–076 |
| E2E-011 | Operations/events recover correctly and expose useful receipts without hidden thought/secrets. | PR-080–082 |
| E2E-012 | Positive, limited and negative passports export HTML/JSON/CSV with provenance digest. | PR-083–085 |
| E2E-013 | 360 px, keyboard-only, 200% zoom and reduced-motion paths remain usable. | Product quality criteria; UX/FE/MAP acceptance |
| E2E-014 | Missing credentials/model/product cannot cause silent synthetic fallback or fake success. | PR-004, PR-034, PR-041, PR-082 |

Record exact requirement coverage; passing this grouped matrix does not excuse an unimplemented individual `PR-*` row.

## 5. Execution order for a fresh build

1. Run schema/API validation and deterministic science fixtures, including units, no-data and CRS controls.
2. Run synthetic full workflow SC-03 and negative cases SC-04/06/08/10/11 with no external credentials.
3. Exercise fingerprint/model failure and valid live model tool-call path with configured model capability preflight.
4. Preflight real data/checksums and execute SC-01 plus SC-02.
5. Exercise critic coverage, mission sensitivity, composites and no-rover mode.
6. Run resilience/idempotency/revision scenarios, then verify exports and replay integrity.
7. Run browser accessibility/responsive journeys and record final acceptance evidence.

Tests must inspect persisted records/receipts as well as screenshots. A mocked frontend cannot prove dataset ingestion, worker calculation, policy decisions or model orchestration. Keep expensive live external tests separate from fast deterministic checks but require successful live reports before claiming full end-to-end completion.

## 6. Demonstration script with truthful branches

**Opening:** “Tell AnalogForge which Moon or Mars test you need and which rover you have.” Show the accepted fingerprint and ARES-1 limits, including physically unavailable conditions.

**Evidence:** open target/Earth comparison at the same stated scale. Show the operations row that retrieved/computed evidence. Open one critic challenge and its resolution or retained unknown.

**PROVE IT:** review accepted benchmark criteria, start design+verification, and inspect the actual generated test once committed; alternatively state that the viewer is opening an explicitly recorded result. Show benchmark failures with measured values. Inspect the diagnosed cause and changed route/zone/candidate.

**Outcome:** show computed later result if a repair succeeded; otherwise show a limited/negative passport and next action. Never promise a pass in a live run. Finish with qualified uses, unsupported dimensions and provenance.

A 90-second presentation can use a labeled replay of a prior live run while preserving original timestamps/digests. Keep a short live calculation/receipt available separately if reviewers ask. A synthetic branch demonstrates software behavior and should be introduced as such.

## 7. Release evidence bundle

For each acceptance run save: scenario manifest/version, environment/data lock manifest, contract/rover digests, tool versions, run ID/mode, event excerpt, evidence/attempt IDs, qualification/critic result, final passport ID/digest, export checksums, assertion report and key screenshots. Sanitize secrets and private account details. Include expected failures as passing acceptance observations only when the test explicitly intended them.

Release report labels outcomes **implemented and verified**, **implemented but not yet live-verified**, **blocked by named dependency**, or **future extension**. The full application is complete only when all in-scope requirements are implemented and their required verification is recorded. Do not confuse honest scientific uncertainty in a completed investigation with missing software functionality.
