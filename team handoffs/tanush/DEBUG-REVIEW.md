# Independent debug review of the Codex-delivered platform branch (2026-11-07)

Reviewer environment: clean Linux container, Python 3.13 (`uv sync --frozen --all-extras`), PostgreSQL 16.15 + PostGIS 3.4.2 started from a private cluster, no Docker.

## What was checked
1. Merged `main` (`36cd52c`) into the branch. Only the kit copy drifted: `contracts/openapi.bundled.json` (accepted central correction TANUSH-CR-001) and `contracts/ui-testids.json` (4 added design-system ids). `materialize.py --repair` fixed both; `--verify` PASS.
2. Executed every Tanush gate (`team guides/Tanush/05-TEST-AND-MERGE-GATES.md`): kit tests (20), platform suite (278 tests, 0 skipped, real PostgreSQL), ruff, mypy, forbidden scan, mutation check (20/20 killed), OpenAPI export (43 operations, byte-equal to the kit bundle), real-switch entry-point probe, ownership check, `validate_docs`, merging-guide `wire_check --stage after-tanush`.
3. Grepped source/tests/scripts/ops for developer-machine leakage (absolute home paths, usernames, ports, tool names).

## Defect found and fixed (replaced, not layered)
| Where | Defect | Fix |
| --- | --- | --- |
| `analogforge/tests/integration/platform/test_runtime_journey.py` | Module constant `DB = "postgresql+psycopg://tanushchokshi@127.0.0.1:5433/analogforge_test"` hard-coded the delivering developer's database role and port. On any other machine every test of that module (and `test_live_choices`, which reuses its fixtures) errors with `role "tanushchokshi" does not exist`; the gate could only pass on the original laptop. | Constant **removed**; the `runtime` fixture now reads `TEST_DATABASE_URL` and `pytest.fail`s when it is unset, identical to `test_migrations.py` (`platform_store`). After the fix: 278 passed. |

## Observations that are correct and were left alone
* Preflight in synthetic mode reports `FAIL` for `SCIENCE_FACADE_MISSING`, `RENDERER_MISSING`, `DATASET_LOCK_MISSING` and three `CONFIG_MISSING` (`config/{datasets,algorithms,candidates}.yaml`). Those files/entry points belong to Ayan and Aradhya (`ownership.json`); the failure is the designed truthful behavior of this isolated branch. `make check` can only reach exit 0 after the merge.
* Absolute `/Users/...` paths exist only in recorded evidence files under `team handoffs/tanush/validation/` and `audits/` (historic command logs); no code, config or script depends on them.
* `test_secrets.py` contains deliberately fake secret literals to prove that they never reach public surfaces; the merging guide's secret scan now recognises such fakes.
* The frozen-kit change request TANUSH-CR-001 was reviewed: the corrected spec exports/validates correctly and the branch conforms to it (43/43 operations, conformance tests green).

## Not verifiable here
Real OpenAI calls, Docker image build, real science/renderer/NASA data (BLOCKED_EXTERNAL / BLOCKED_ENVIRONMENT as already recorded in `STATUS.json`).

## Second pass (2026-11-11): seam fixes from a real-science trial merge

A trial merge `main + Tanush + Ayan` running Tanush's journeys with `AF_SCIENCE_IMPL=real` exposed two platform-side gaps that fake-science tests could not reveal. Both are fixed here by replacing the defective behavior; Ayan's matching science fixes are on his branch.

| Defect | Fix | Guard |
| --- | --- | --- |
| `config/scenarios.yaml`: `synthetic-graph-regression-v1` used the abstract `canonical-graph-v1` as `target_source`/`earth_source`; it has no terrain raster, so real CHARACTERIZE_TARGET returned `NO_COVERAGE` and the run blocked before PROVE IT | terrain sources are now `practice-mars-target-v1` / `practice-earth-grid-v1` (same Mars AOI as the mobility mission); `graph_fixture_id: canonical-graph-v1` still drives PROVE IT, so S-GRAPH-1 numbers are unchanged | `tests/unit/platform/test_scenario_sources.py` (fails on the old config) |
| A refused positive claim (`ScientificClaimRejected` from the final audit) escaped `WorkflowEngine.advance` as an unhandled exception, contrary to architecture 33 §2.7/§6 (refuse, retain the diagnostic audit, publish no passport) | `advance` catches it and stores the run `BLOCKED` with `blocked_dependencies = ["SCIENTIFIC_CLAIM_REJECTED"]`, `runtime.stop_reason`, `runtime.claim_rejection_issues`, and a `run.blocked` event; no passport row is created | `test_runtime_journey.py::test_runtime_rejected_claim_blocks_run_without_passport` |

Results:
* Trial merge with the real science engine: `test_runtime_journey.py` 4/4 and `test_journey_api.py` 6/6 passed. All runs end COMPLETED with audited passports: Mars mobility with ARES-1, PRACTICE-LITE, PRACTICE-NO-ENERGY-MODEL and PRACTICE-SMALL-BATTERY, graph regression and Moon gap.
* This branch alone (fake doubles, real PostgreSQL): 281 passed / 0 skipped (278 + 3 new); kit verify PASS; ruff and mypy clean; forbidden scan 0; mutation check 20/20; `validate_docs` PASS; ownership PASS.

## Third pass (2026-11-12): real-backend browser journeys against the merged stack
Aradhya's Playwright journeys driven through this API/worker with the real science engine and real renderer (mocks off) exposed five platform defects; each is fixed by replacing the defective behavior and guarded by a test that fails on the old code:

| Defect | Fix | Guard |
| --- | --- | --- |
| `GET /critiques` listed `CRITIQUE` evidence that was never created (critiques lived only in their table), so critic cards never appeared | every opened/resolved critique registers immutable `CRITIQUE` evidence (artifact = `CritiqueIssue` JSON); the row keeps the latest id and the endpoint returns the latest record per issue | `test_journey_api` (one record per issue, BLOCKING/RESOLVED present) |
| Replan picker summed every `band_area_m2` key; low-slope bands dominated and the candidate switch chose the rolling window `grid-r1c0` instead of B | start-zone area of the availability requirement's own band (architecture 40 §4) | `tests/unit/platform/test_replan_picker.py` (real observed band areas) |
| Replan changes were stored but absent from the public test record, so the workbench showed "no comparison supplied" | public `VerificationTest.assumptions` carries one `Changed elements: …` line (`none` for attempt 1) | `test_journey_api` |
| `UNKNOWN`/`GAP` qualification claims with no limitation text made the assurance report violate the frozen schema; the workbench refused the passport (`INVALID_PASSPORT_AUDIT`) | claims fall back to the science explanation, and the audit never emits a non-supported claim without a limitation (unmet gate reasons) | `test_assurance` now validates reports against `scientific-assurance.schema.json` |
| `RETRY` was offered for `SCIENTIFIC_CLAIM_REJECTED`, re-running an audit that cannot change | not an allowed action for that stop | `test_runtime_rejected_claim_blocks_run_without_passport` |

Results: platform suite 303 passed (kit 20 passed in its own process, as the gate specifies); mutations 20/20; forbidden scan 0; validate_docs PASS; kit verify PASS; ownership PASS. Real-backend browser journeys on the merged stack: J01 and J02 pass end to end (remaining journeys: see the merge report).

### Third pass, continued: remaining journeys (J03–J13)
Three more platform gaps, each replaced and guarded (platform suite 285 passed, ruff and mypy clean, forbidden scan 0 findings):

| Defect | Fix | Guard |
| --- | --- | --- |
| A no-route result published the diagnosis but not which repairs are permitted, so the Test Lab could not say that only a new contract helps (PRACTICE-LITE/SMALL) | no-route `TestResult.limitations` adds `Permitted repairs: …` from `DIAGNOSE_RESULT.permitted_repairs` | `test_journey_api` (`Permitted repairs: NEW_CONTRACT_REQUIRED` for practice-lite/small) |
| The public test record did not carry the search strategy, so attempts showed no strategy | `VerificationTest.assumptions` adds `Strategy: <strategy>` before the `Changed elements:` line | `test_journey_api` (every public test has one `Strategy:` line) |
| `capabilities.modes` listed `live` only when an LLM credential was configured, so the option silently disappeared. Architecture 39 J13 and PLT-16 instead require that a live run without credentials is refused with 503 `PROVIDER_AUTH_FAILED` and a remediation hint (readiness is reported separately in `live_ai_configured`) | `live` is offered whenever any scenario's `allowed_modes` contains `live` | `test_live_mode_is_offered_once_bound_even_without_credentials` |

J13 needs a scenario bound for live data. In a real merge, that binding comes from the MRG-05b TEST_HARNESS rehearsal or from real NASA data. Unbound, `live` is correctly absent.

## Fourth pass (2026-11-13): hardening of the merged release candidate
An independent audit of `integration/rc` (5e08b80) went beyond the gates: a spec-driven fuzzer (1,006 hostile requests over all 43 operations), concurrency and idempotency probes, a load measurement, a dependency scan and a warning sweep. The logs of a full real-backend run held no traceback. Defects, each replaced and guarded by a test that fails on the old code:

| Defect (measured) | Fix | Guard |
| --- | --- | --- |
| Deeply nested JSON made every write operation return a bare plain-text 500: `RecursionError` is not a `ValueError`, so it escaped the body-parse handler | `MAX_JSON_DEPTH` (64; the deepest kit fixture is a small fraction of it) is checked by a non-recursive scan before any recursive parser, hasher or schema validator runs, and `RecursionError` is treated as invalid input there and in the list-cursor decoder | `test_http_hardening` (all 9 write routes at three depths, the cursor, the limit's headroom over every contract fixture) |
| Unmatched routes and methods answered `{"detail": "Not Found"}`, violating the frozen error envelope (50 fuzz cases) | handlers map framework 404 and 405 to `NOT_FOUND` and `METHOD_NOT_ALLOWED` in the envelope (with `Allow`), and any unforeseen failure to an enveloped `INTERNAL_ERROR` that reveals nothing; the traceback stays in the log | `test_http_hardening` |
| `/docs`, `/redoc` and `/openapi.json` were on by default; Swagger UI loads its scripts from a CDN, against the offline-first rule | opt-in through `ANALOGFORGE_API_DOCS` (excluded from the provenance hash) | `test_http_hardening` |
| An oversized body was read before being refused | the declared `Content-Length` is checked first | `test_http_hardening` |
| Listing runs took 213 ms, a passport read 53 ms and `GET /runs/{id}` 16 ms: every page loaded the **whole table** and sliced it in Python, and rows carry large internal payloads (a run ~365 kB against 3.6 kB public, a passport 1.77 MB against 22 kB) | public reads and lists drop never-public keys in PostgreSQL (`jsonb - text[]`, table `INTERNAL_PAYLOAD_KEYS`), and generic lists page by keyset `(created_at, id) > cursor LIMIT n+1` in SQL | `test_listing_efficiency`: no excluded key is ever a public property; the SQL carries the exclusion and the limit; keyset walks at six page sizes visit every row once; malformed cursor positions are 422 |

Measured effect on the same data: run list 213 → 7 ms, passport 53 → 9 ms, single run 16 → 5.5 ms; throughput at 32 clients plus 20 event streams 12 → 153 requests per second and the 95th-percentile latency 8.7 s → 252 ms, no errors. **Behaviour is unchanged:** a golden-master comparison of the old and the fixed server on the same database (2,625 requests: every read, every run-scoped list, global lists walked at six page sizes, cursors minted by the old server consumed by the new one) found 2,436 identical responses, 189 intended differences (the unmatched-route envelope) and **0 others**.

Checked and sound, with no change needed: idempotency under concurrency (30 simultaneous identical writes gave one record and 30 identical replies; a changed body under the same key gave 409; 30 distinct keys gave 30 records), cross-origin handling (no foreign origin is ever allowed), SQL-injection and traversal inputs in every identifier and query parameter (clean 4xx), local auth refusing a non-loopback host, security headers, and `pip-audit` on all 258 locked Python requirements (no known vulnerabilities).

Not changed, with reasons: request handlers are `async` but use the synchronous driver, so one event loop serves requests one at a time; at about 6 ms a request that is ample for a single-tenant analysis tool, and moving to a thread pool is a larger change with no measured need. `GET /critiques` makes one read per issue (about 27 ms a page). The pytest-asyncio loop-scope warning comes from the frozen `pyproject.toml`.
