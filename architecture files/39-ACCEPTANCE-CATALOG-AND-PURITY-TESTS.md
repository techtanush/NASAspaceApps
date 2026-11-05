# Acceptance catalog, purity tests and browser journeys

This is the single catalog of tests that decide whether a branch is *pure* (§1–§2), whether the merged product works (§3–§4), and whether the NASA-data slot is proven (§5). Branch guides (`05-TEST-AND-MERGE-GATES.md`) implement their rows; the merging guide runs all of them. IDs are stable and appear in status reports. A row passes only when the test **executes and asserts**; skipped, xfail, deselected or unrun is not a pass.

## 1. Test catalog by owner

### Kit (everyone)
| ID | Check |
| --- | --- |
| KIT-01 | `materialize.py --verify` → `PASS` |
| KIT-02 | `pytest tests/contracts/kit` passes unchanged (20 tests) |

### Platform (Tanush) — path prefix `tests/{unit,integration,contracts}/platform`
| ID | Check |
| --- | --- |
| PLT-01 | Migrations apply on an empty DB and on a seeded previous schema; downgrade path documented; no auto-drop |
| PLT-02 | **OpenAPI conformance:** all 43 operations exist with the bundled operationIds/methods/paths; every GET response and every 2xx/4xx body produced by the real app validates against `contracts/openapi.bundled.json` (jsonschema 2020-12); every kit request fixture validates |
| PLT-03 | Idempotency (same key+body ⇒ same response; changed body ⇒ 409 `IDEMPOTENCY_CONFLICT`) and `expected_revision` CAS (`REVISION_CONFLICT`) on every mutating endpoint |
| PLT-04 | Workspace isolation: cross-workspace read/write ⇒ 404; lists never leak; artifacts require evidence/export ownership |
| PLT-05 | Two workers: one lease owner; expired-lease publication fenced; crash after blob move before commit recovers with no duplicate result |
| PLT-06 | Cancellation during a CPU tool: run `CANCELLED`, evidence retained, no later PASS |
| PLT-07 | SSE: replay after cursor, duplicate/gap handling inputs, `410 EVENT_CURSOR_EXPIRED`, heartbeat, terminal event |
| PLT-08 | **Registrar rejections:** artifact hash/size mismatch, scratch path escape, dangling `local_key`, parent in other workspace/mode, `SYNTHETIC_` naming rules by mode, signed-URL `source_uri`, `input_sha256` mismatch, `request_id` mismatch |
| PLT-09 | Policy rejections: fabricated evidence id, wrong-workspace evidence, changed threshold/rover limit, stale revision, unlisted tool, prompt-injected source text, qualification status/confidence inflation |
| PLT-10 | All ten roles run through the scripted provider with strict schemas; seeded scale-defect loop of [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §7 produces OPEN→RESOLVED critic issue and matrix revision 2 |
| PLT-11 | Budgets from `catalog.BUDGETS` enforced and persisted across restart (model calls, tool calls, replans 2+1, active seconds, preparation cap 4) |
| PLT-12 | Assurance: SC-01…SC-15 audit; SCI-01/04/06/07/09–18 platform parts; blocked/limited/allowed publication; atomic rollback; stale audit rejected; tamper detected |
| PLT-13 | Passport assembly: acyclic hashing (snapshot → audit evidence → manifest → export file); `manifest_sha256` independently reproduced with a separate RFC 8785 call |
| PLT-14 | Export endpoint: 202+`Retry-After` then 200; headers `Content-Type`, `Content-Disposition`, `ETag`, `X-Artifact-SHA256`, `nosniff`; byte-stable on re-download |
| PLT-15 | Entry-point loading: missing facade/renderer ⇒ named startup/preflight failure (no silent double); import hygiene for `analogforge.main` |
| PLT-16 | No-key startup in `synthetic`; `live` without key/model ⇒ `503 PROVIDER_AUTH_FAILED` with `details.dependency`; never a fallback |
| PLT-17 | Dataset CLI: validate/lock/bind/scaffold/generate-practice/generate-mock-nasa-drop; tamper after lock ⇒ `SOURCE_CHECKSUM_MISMATCH` block; synthetic dataset into `live-hackathon-v1` ⇒ `MODE_MISMATCH` |
| PLT-18 | `live` mode rejects the mock graph resource provider; `synthetic`/`replay` forbid network (socket-level test) |
| PLT-19 | Secret scan: no key/token/DSN in logs, SSE, exports, errors, OpenAPI, git-tracked files |
| PLT-20 | Frontend-facing seed: `analogforge seed-synthetic` idempotent and offline; capabilities list scenarios per [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §10 |
| PLT-21 | Fake-OpenAI live-path rehearsal (test hooks): the live role loop completes against a local fake Responses server with strict tool calls; malformed/refusal/timeout handled |

### Science (Ayan) — path prefix `tests/{unit,property,integration,replay}/science`
| ID | Check |
| --- | --- |
| SCN-01 | Analytic geometry oracles GEO-01…GEO-10 ([29](29-SCIENTIFIC-VALIDATION.md) §3) |
| SCN-02 | Energy oracle `catalog.ENERGY_ORACLE_FLAT_1000M` (1e-8 Wh) and the additional assertions of 29 §4 |
| SCN-03 | Canonical graph: every entry of `catalog.GRAPH_EXPECTED`, brute-force oracle, tie-break |
| SCN-04 | Verifier rejects falsified solver totals, diagonal corner/nodata traversal, stale hashes, repeated-edge exposure gaming, missing return, unreachable/snapped-too-far waypoints |
| SCN-05 | Search limits: one expansion ⇒ `BUDGET_EXHAUSTED`; lossy pruning forbids `EXHAUSTIVE_INFEASIBLE` (also enforced by the payload validator) |
| SCN-06 | Practice Earth grid satisfies **every property** of [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §4 by an independent checker |
| SCN-07 | Screening result of 40 §4.1 |
| SCN-08 | Qualification truth table of 40 §5 incl. oracle rule for the context row |
| SCN-09 | Science-level storylines S-RASTER-1, S-GRAPH-1, S-ROVER-LITE, S-NO-ENERGY, S-SMALL-BATTERY |
| SCN-10 | Perturbation tests PERT-01…PERT-09 |
| SCN-11 | Dataset validation: one failing fixture per `check_id` of [36](36-DATASET-PLUG-IN-AND-NASA-SLOT.md) §4 |
| SCN-12 | Mock NASA drop of §5 below validates and runs end-to-end through the facade |
| SCN-13 | PARITY-01: fixture-id source ≡ LOCAL_DATASET source (identical metrics) |
| SCN-14 | Moon polar wedge AOI, longitude wrap, radius→height once, scale applied once |
| SCN-15 | Optional layers: absent/partial EMIT & thermal ⇒ `UNKNOWN` with the specified reason; categorical class ids never interpolated |
| SCN-16 | Portfolio fixtures of [13](13-COMPOSITE-ANALOG-PORTFOLIOS.md) §6 (1–7) and stability under input order |
| SCN-17 | Display layers: Earth corners NW,NE,SE,SW; planetary affine/CRS; nodata transparent; legend/units/attribution |
| SCN-18 | Live adapters with recorded fixtures: NASADEM tile decode (NUM/water), MOLA/LOLA label scaling, EMIT categorical+mask, Diviner kelvin; HTML-login, bad archive, checksum mismatch, redirect auth leak |
| SCN-19 | Import hygiene: science facade imports without `fastapi/sqlalchemy/psycopg/openai`; no environment reads; no network in synthetic/replay |
| SCN-20 | Determinism: same request ⇒ identical payload and artifact bytes (wall-clock fields excluded) |
| SCN-21 | Cancellation/deadline honored within 1 s in search, screening and analysis |

### Frontend and renderer (Aradhya) — `apps/web`, `tests/unit/passport_renderer`, `tests/e2e`
| ID | Check |
| --- | --- |
| UIX-01 | `pnpm run typecheck && pnpm run test && pnpm run build` from a frozen lockfile |
| UIX-02 | Generated client freshness: regenerate from `contracts/openapi.bundled.json` and `git diff --exit-code` |
| UIX-03 | Every MSW fixture body validates against the bundled OpenAPI |
| UIX-04 | **Test-id coverage:** every id in `contracts/ui-testids.json` appears in `apps/web/src` and is asserted by at least one Playwright test; required `data-*` attributes present |
| UIX-05 | Component/interaction suites FE-001…FE-014 ([17](17-FRONTEND-COMPONENTS-AND-STATE.md)) and UX-001…UX-012 ([16](16-USER-JOURNEYS-AND-SCREENS.md)) |
| UIX-06 | SSE controller: dedup, gap resync, 410 resync, backoff, terminal close, unmount cleanup |
| UIX-07 | axe accessibility (no critical/serious) at 1440, 900, 390 px; keyboard-only path through authoring; 200 % zoom reachability |
| UIX-08 | Renderer: determinism, HTML escaping with hostile strings, CSV exact `CSV_COLUMNS` + formula neutralization, JSON canonical-manifest hash reproduction |
| UIX-09 | Renderer purity: subprocess import test shows no network/DB/model modules; all attempts/GAP/UNKNOWN present in HTML |
| UIX-10 | Mock mode: permanent `MOCK PREVIEW` banner; production build fails when mock flag set |
| UIX-11 | WebGL-failure fallback keeps candidate list, matrix, route table and exports |

### Merge (merging agent) — see `merging guide/`
| ID | Check |
| --- | --- |
| MRG-01 | Every branch passes its purity checks standalone |
| MRG-02 | Combined offline suite (all PLT/SCN/UIX rows) on the merged candidate |
| MRG-03 | Browser journeys J1–J13 (§3) with mocks disabled and DB/receipt assertions |
| MRG-04 | Parity: `synthetic-mars-mobility-v1` vs `local-dataset-practice-v1` produce identical qualification and attempt outcomes |
| MRG-05 | Mock NASA drop rehearsal (§5) |
| MRG-06 | Clean-checkout rebuild: `git clone` → bootstrap → `make check` → journeys, from committed files only |
| MRG-07 | Restart/recovery: kill API, kill worker mid-search, SSE reconnect |
| MRG-08 | Secret/ownership/forbidden-pattern scan on the merged tree |
| MRG-09 | Requirements ledger: all 58 `PR-*` rows with module, test, observed result |
| MRG-10 | Scientific validation report with SCI-01…SCI-18 for the exact merged SHA |

## 2. Branch purity (what "pure" means)

A branch is **pure** when, checked out alone on a clean clone:
1. `materialize.py --verify` passes and `git diff <base>...HEAD --name-only` touches only paths the owner may edit (or exact kit files);
2. its own catalog rows pass with executed assertions (no skips/xfail/deselect, no weakened asserts versus the guide);
3. no forbidden patterns (merging guide `02`): `NotImplementedError`, `TODO`/`FIXME`/`HACK`, hard-coded practice outcomes, `if mode == "synthetic": return …` shortcuts, broad `except Exception: pass`, committed secrets, NASA labels on synthetic data, network use in synthetic paths;
4. its mutation checks (guide `09`) show the tests can fail;
5. it declares only contradictions it recorded in `STATUS.json`.

## 3. Browser journeys (merged product; Playwright; mocks off)

All drive the UI **only** through `data-testid`s from `contracts/ui-testids.json`, and assert persisted state through the API (job/receipt/evidence ids exist) — never screenshots alone. Fixtures come from `tests/fixtures/kit/`. Timeouts: preparation 60 s, run to `AWAITING_REVIEW` 180 s, PROVE IT sequence 240 s.

**J1 — Golden Mars path (synthetic, ARES-1)**
1. `/` → `app-shell`; click `btn-new-mission`.
2. Fill `input-mission-name`; click `radio-body[data-body=MARS]`; fill `input-objective` (the objective of `mission-mars-mobility.json`); choose the practice Mars preset in `select-target-preset`; the four `input-bbox` fields read `137, -5, 138, -4`; `save-indicator[data-save-state=saved]` appears.
3. Set `file-rover-import` to `tests/fixtures/kit/rovers/ares-1.json`; `rover-import-preview` visible; click `btn-rover-save`.
4. Click `btn-build-fingerprint`; `preparation-status[data-job-state=SUCCEEDED]`; exactly 9 `requirement-row`s (ids of `mission-mars-mobility.json`), every row has `data-origin`; ≥ 1 `assumption-card`; `R-GRAVITY`/`R-ATMOSPHERE` rows are present.
5. `select-scenario` = `synthetic-mars-mobility-v1`; `select-mode` = `synthetic`; click `btn-accept-contract`, then `btn-start-run`.
6. `mode-badge[data-mode=synthetic]` visible; `run-state-banner[data-state=AWAITING_REVIEW]` within 180 s.
7. Tab `target`: `planetary-panel[data-body=MARS]` visible and **no** `earth-map`.
8. Tab `analogs`: 6 `candidate-row`s (set per [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §4.1); exactly one `data-origin=KNOWN_CONTROL`; `excluded-window[data-reason=WATER_ONLY]` and `[data-reason=INSUFFICIENT_VALID_DATA]` present; `earth-map` and `candidate-list` both present.
9. Tab `qualification`: for candidate `Practice grid-r0c1` assert the cells of the truth table (`R-SLOPE-AVAILABILITY` PASS; `R-EXPOSURE` UNKNOWN `data-stage=PRELIMINARY`; `R-CLEARANCE` UNKNOWN; `R-GRAVITY` GAP); a `critic-card[data-severity=BLOCKING][data-status=RESOLVED]` exists with a `qual-history` for `R-TARGET-SLOPE-CONTEXT`.
10. Click `btn-select-candidate[data-candidate-name="Practice grid-r0c1"]`; tab `compatibility`: `compat-table[data-preliminary=true]`, `compat-row[data-metric-id=ground_clearance_m][data-status=UNKNOWN]`.
11. Tab `test-lab`: `benchmark-preview` visible; **no** `attempt-row`, **no** `route-playback`; `btn-prove-it[data-enabled=true]`; click it.
12. Within 240 s: `attempt-row[data-attempt-number=1][data-outcome=FAIL]` with `failure-category[data-category=ROUTE]` and `benchmark-row[data-constraint-id=C-EXPOSURE-R-EXPOSURE][data-status=FAIL]`; `attempt-row[data-attempt-number=2][data-outcome=FAIL]` with category `ANALOG`; `attempt-row[data-attempt-number=3][data-outcome=PASS]` with candidate `Practice grid-r0c0`; `replan-diff` lists the strategy change and the candidate change; `route-playback` now present; `run-state-banner[data-state=COMPLETED]`.
13. Tab `passport`: `passport-view[data-draft=false]`; 3 `attempt-row`s; `assurance-badge[data-publication=LIMITED]`; `manifest-digest` (64 hex); for each format click `export-btn[data-format]`, wait `export-status[data-state=ready]`, `file-digest[data-format]` (64 hex).
14. Download all three (Playwright `download`); then in the test: `sha256(file) == displayed file digest`; JSON `canonical_manifest` re-canonicalized (RFC 8785) hashes to `manifest-digest`; CSV first line equals `CSV_COLUMNS` joined by commas; HTML contains `synthetic`, the manifest digest, three attempts, every GAP row, and contains no `http://`/`https://` resource loads (`src=`/`href=` to external hosts) and no `<script`.
15. Reload: `mode-badge`, `attempt-row`s, `passport-view` identical.
16. Whole journey: no console errors; every network request host is `localhost`/`127.0.0.1`; no request or response body contains the strings `OPENAI_API_KEY`, `sk-`, `EARTHDATA_TOKEN`.

**J2 — Graph regression:** scenario `synthetic-graph-regression-v1` with the blueprint rover; attempts: 1 FAIL `EXPOSURE_SHORTFALL` observed 0 m (120 m / 26 Wh), 2 PASS (230 m, 30 Wh, 150 m); `benchmark-row` values read exactly those numbers; passport mode synthetic; assurance `ALLOWED`/`LIMITED` per audit (the test asserts equality with the persisted assurance artifact).

**J3 — Moon site-only (no rover):** `btn-continue-no-rover`; scenario `synthetic-moon-gap-v1`; `planetary-panel[data-body=MOON]`; `R-THERMAL` UNKNOWN, `R-GRAVITY`/`R-VACUUM` GAP; `btn-prove-it[data-enabled=false]` with `prove-it-disabled-reason`; direct `GET /compatibility` ⇒ 409 `ROVER_REQUIRED`; passport `LIMITED` with the text "No rover supplied — site qualification only" in HTML and `not_run_reason` in JSON.

**J4 — Rover import errors:** invalid JSON file ⇒ `error-panel`; file with `mass_kg: -3` ⇒ `rover-field-error[data-field=mass_kg]`, no rover persisted (API list unchanged), text typed by the user preserved.

**J5 — Rover conflict (`PRACTICE-LITE`):** attempts end `FAIL`, category `ROVER`; passport states `NEW_CONTRACT_REQUIRED` as the next step; `R-EXPOSURE` unchanged at 100 m (no relaxation).

**J6 — No energy model:** final outcome `INCONCLUSIVE`, `failure-category[data-category=DATA]`; energy values render `unknown-value`, never `0`.

**J7 — Cancellation:** start the J1 run, click `btn-cancel-run` after the first `operation-row`; `run-state-banner[data-state=CANCELLED]` within 10 s; previously committed evidence still openable; no passport; no later `attempt-row[data-outcome=PASS]`.

**J8 — Connection loss:** during a run `page.context().setOffline(true)` for 6 s ⇒ `connection-indicator[data-connection=paused]` then `connected`; all `operation-row[data-seq]` values are unique and strictly increasing; the final state equals the API snapshot.

**J9 — Responsive/keyboard/zoom:** J1 steps 1–4 and 8–9 at 390×844 with keyboard only (Tab/Enter/Space; visible focus); at 200 % zoom the primary actions remain reachable; axe finds no critical/serious violations.

**J10 — Immutability:** after run start, editing the mission creates a new draft revision (`save-indicator`), the existing run's `requirement-row` thresholds are unchanged; direct API attempts to mutate a pinned revision return 409/403/405 and change nothing.

**J11 — Local dataset parity:** run `datasets generate-practice` + `datasets lock --policy-id local-practice-policy-v1`, then repeat J1 with scenario `local-dataset-practice-v1`; qualification rows and attempt outcomes equal J1's (`R-MINERAL` reason differs as specified).

**J12 — Live scenario not bound:** `scenario-note[data-scenario-id=live-hackathon-v1][data-available=false]` with `empty-state[data-reason=AWAITING_DATASETS]`; `btn-start-run` disabled for it.

**J13 — Live without key:** choose mode `live` without `OPENAI_API_KEY`: run creation returns 503 `PROVIDER_AUTH_FAILED`; UI shows `error-panel[data-error-code=PROVIDER_AUTH_FAILED]` and `remediation-hint[data-dependency=OPENAI_API_KEY]`; no run is created and no scripted fallback occurs.

## 4. Adversarial acceptance (platform-level, merged)

Run against the merged API (not mocked): fabricated evidence id in a role result; role result for another workspace; role attempts to lower `R-RESERVE` to 13 %; replan with changed contract hash; unlisted tool call; stale `expected_revision`; replayed idempotency key with new body; lost lease then late publish; worker killed during `SEARCH_ROUTE`; `CANCEL` during search; tampered blob in replay (`REPLAY_INTEGRITY_ERROR`, no network call); export tampered after publication (digest mismatch visible); SSE `Last-Event-ID` beyond retention (410). Expected outcomes are exactly those in [14](14-AGENT-ORCHESTRATION.md), [23](23-JOBS-AND-RECOVERY.md), [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md).

## 5. Mock NASA drop (tier R rehearsal of the slot)

`analogforge datasets generate-mock-nasa-drop` (Ayan's generator) writes into `analogforge/data/incoming/` the following synthetic datasets in **deliberately varied real-world formats and metadata quirks**. All are `provider: SYNTHETIC_MOCK_NASA_DROP`, `is_synthetic: true`.

| dataset_id | Format and quirks it exercises |
| --- | --- |
| `mock-nasa-earth-dem` | **HGT** SRTM3-style 1201×1201 int16 big-endian tiles `N36W112.hgt` + `N36W111.hgt` sharing the border column (seam dedup); nodata −32768; EPSG:4326; 90 m |
| `mock-nasa-mars-dem` | **GeoTIFF float32 with GDAL scale/offset metadata** (`scale_already_applied: true`); `ZERO_360` longitudes; planetary equirectangular WKT |
| `mock-nasa-lunar-radius` | **PDS3** `.lbl` + `.img` int16 with `SCALING_FACTOR`/`OFFSET` in the label, quantity `RADIUS`, km, `reference_radius_m` |
| `mock-nasa-emit` | **NetCDF** with a group variable path; categorical ids; nodata −9999 |
| `mock-nasa-ascii-dem` | **Esri ASCII grid**, projected Earth CRS, `NODATA_value` |
| `mock-nasa-bad-no-crs` | GeoTIFF without CRS ⇒ `crs_resolved` FAIL |
| `mock-nasa-bad-html` | an HTML login page saved as `.tif` ⇒ `html_login_page` FAIL |
| `mock-nasa-bad-double-scale` | scale in both file metadata and manifest, ambiguous ⇒ `scale_offset_once` FAIL |
| `mock-nasa-bad-units` | radius values declared as elevation ⇒ `units_and_quantity` FAIL |

### 5.1 Rehearsal procedure (MRG-05)

1. `analogforge datasets generate-mock-nasa-drop`; for each `good` dataset run `datasets scaffold` (check it infers format/CRS/nodata/transform), complete the `TODO_FILL_IN` fields, then `datasets validate` ⇒ all PASS; the four `bad` datasets must FAIL with exactly the named check.
2. `datasets lock --policy-id local-practice-policy-v1 --datasets mock-nasa-earth-dem mock-nasa-mars-dem`; `scenario bind local-dataset-practice-v1 --target-terrain mock-nasa-mars-dem --earth-terrain mock-nasa-earth-dem`; `preflight --mode synthetic --scenario local-dataset-practice-v1` ⇒ pass.
3. Run the journey of J1 (steps 5–16) on this scenario; the run completes and produces a passport; whatever the outcome (PASS/FAIL/INCONCLUSIVE) is truthful and consistent across UI/API/exports.
4. Attempt `scenario bind live-hackathon-v1 --target-terrain mock-nasa-mars-dem …` ⇒ rejected `MODE_MISMATCH` (synthetic data may not enter live).
5. Flip one byte in `mock-nasa-earth-dem` after lock ⇒ next run blocks `SOURCE_CHECKSUM_MISMATCH`; no scientific FAIL is produced.
6. Restore the scenario binding to practice defaults.

### 5.2 Live-path rehearsal with test hooks (PLT-21 / MRG-05b)

With `ANALOGFORGE_TEST_HOOKS=1`, a local fake OpenAI Responses server (`tests/support/fake_openai_server.py`, Tanush) and datasets whose provider is `TEST_HARNESS` (accepted only under the hooks, flagged in every output as `TEST HARNESS — not NASA data`), the **live** role loop and registrar run end-to-end offline. This is the closest possible rehearsal of the live path; it never produces a labeled-NASA result and is impossible without the hooks.

## 6. Completion report

Every branch and the merge produce a JSON status (templates in `team guides/<Name>/STATUS-TEMPLATE.json` and `merging guide/templates/`) listing per catalog id: `PASSED` | `FAILED` | `BLOCKED_ENVIRONMENT` | `BLOCKED_EXTERNAL` | `NOT_IMPLEMENTED`, with the command, exit code, counts and a pointer to the output file. `PASSED` requires executed assertions. A summary of unmet gates must be the first thing printed.
