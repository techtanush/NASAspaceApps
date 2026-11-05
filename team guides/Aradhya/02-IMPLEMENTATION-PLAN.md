# Aradhya — implementation plan (phases with exit gates)

Follow `team coordination/05-PARALLEL-ONE-SHOT-EXECUTION-PLAN.md`. Parallelize inside a phase with subagents (single writer per file). Record each phase's completion (SHA, date) in `PROGRESS.md`.

## U0 Orient and bootstrap
Read everything named in the prompt. Materialize + verify the kit; `uv venv --python 3.12 && uv pip install -e ".[dev,extra-aradhya]"`; run `tests/contracts/kit`. Node 22 + pnpm 10; Playwright Chromium (architecture 38 §4.3). Scaffold the pnpm workspace and `apps/web`. **Exit:** kit PASS; `pnpm install` works; an empty Vite app builds; Playwright can launch a browser (or the exact blocker is recorded).

## U1 Contract client and shell
Generate the client from `contracts/openapi.bundled.json`; `api/*` (client, errors, idempotency, query keys), `format/*` (quantity/unit/time/status with the Unknown rule), tokens/layout CSS, app shell, router, providers, workspace context, mode badge, connection indicator, error boundary. Implement the SSE parser/controller with its unit tests. **Exit:** UIX-01 (build/typecheck), UIX-02 (client fresh), UIX-06 (SSE) pass.

## U2 Mock backend and fixtures
Stateful MSW server for all 43 operations, fixtures validated against the bundled OpenAPI (UIX-03), scripts for every storyline of `08` §6, timers/SSE replay with cursors, 409/410/202/503 behaviors, mock banner and the production-build guard. `scripts/build_mock_exports.py` (needs phase U4's renderer; stub-run it after U4 — until then serve placeholder bytes flagged as such and replace them in U4). **Exit:** UIX-03, UIX-10 pass; the mock can drive a run to COMPLETED in a browser.

## U3 Screens and maps
Implement S01–S12 in dependency order (workspace → mission/rover authoring → fingerprint/freeze/run creation → run shell → target → analogs → qualification/critic/review → compatibility → test lab/attempts/replan/playback → portfolio → passport/exports → operations/evidence drawers) with every test id, empty/error/unknown states and truthfulness rules. Earth map, planetary panel, affine tests, layer registry, WebGL fallback. **Exit:** UIX-04 (every test id present), UIX-05, UIX-11 pass; component suites FE-001…014 and UX-001…012 pass.

## U4 Passport renderer
`renderer.py`, `html.py`, `csv_export.py`, `json_export.py`, `escaping.py`, templates; fixtures (9 bundles) built in code; contract tests. Run `scripts/build_mock_exports.py` to refresh the mock exports with real renderer bytes. **Exit:** UIX-08, UIX-09 pass; mock exports are real renderer output.

## U5 Journeys, accessibility, hardening
Playwright J01–J13 in mock mode (`test:e2e:mock`), written so the **same specs** run against the real backend (`E2E_TARGET=real`): mode-dependent assertions go through an explicit `isMock()` helper; real-only assertions (DB/receipt checks through the API) are present and simply not executed in mock mode. axe at 1440/900/390; keyboard-only; 200 % zoom; reduced motion; WebGL-failure fallback. **Exit:** all 13 journeys pass in mock mode; UIX-07 passes.

## U6 Self-audit
`09` complete: forbidden scan, mutation checks, adversarial reviewers, hostile-string and determinism runs. **Exit:** all green; lint + typecheck + ruff + mypy (renderer) clean.

## U7 Report and push
`materialize.py --verify`, ownership check, full gate, fill `STATUS.json`, commit (no build output), push, print summary.
