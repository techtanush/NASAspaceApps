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
