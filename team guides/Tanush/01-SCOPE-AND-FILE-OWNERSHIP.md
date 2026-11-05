# Tanush — scope and file ownership

## Owned paths (see `team coordination/contracts/ownership.json`)

* `analogforge/src/analogforge/{main.py,settings.py,cli.py,api,domain,db,jobs,application,agents,tools}/**`
* `analogforge/src/analogforge/adapters/{openai,storage,identity}/**`
* `analogforge/{README.md,Makefile,compose.yaml,uv.lock,services/api/**,ops/**,scripts/{bootstrap,preflight,seed_synthetic,validate_docs,lock_sources}*}`
* `analogforge/config/scenarios.yaml`, `analogforge/config/presets/**` (byte-identical copies of kit fixtures)
* `analogforge/tests/{unit,integration}/platform/**`, `tests/contracts/platform/**`, `tests/support/**`
* `architecture files/**`, `team coordination/**`, root `README.md`/`.gitignore` — **only via the recorded change process; you do not change them in this build.**
* `team guides/Tanush/**`, `team handoffs/tanush/**`, `team guides/COMMON-BUILDER-PROTOCOL.md` (unchanged)
* Your `extra-tanush` list in `pyproject.toml` (platform-only dependencies) and `uv.lock`.

## Not yours (report, never edit)

The kit; Ayan's `science/**`, science adapters, `rendering/tiles`, `config/{datasets,algorithms,candidates}.yaml`, science tests; Aradhya's `apps/web/**`, `package.json`/`pnpm-*`, `rendering/passport/**`, renderer/e2e tests.

## What you deliver

1. A running system: `make dev` brings up DB + API + worker (+ the frontend dev server when Aradhya's package exists); `make seed-synthetic` is offline and idempotent; `make preflight` reports truthfully; `make check` runs all offline suites.
2. All 43 API operations conforming to `contracts/openapi.bundled.json` (PLT-02), durable jobs, events, SSE, idempotency, revisions, workspace isolation.
3. The scheduler/state machine of `08` §5, the registrar of §6, policy, budgets, scripted + live providers, 21 tools, 10 roles.
4. Assurance + passport assembly + export service; dataset CLI; preflight; capabilities.
5. Test doubles under `tests/support/` and PLT-01…PLT-21.
6. Filled `STATUS.json`, pushed.

## Boundaries you enforce in your own code

* Production code imports science/renderer **only** via entry points (dynamic `importlib`), so your branch runs and tests without them (with doubles) and with them (merged).
* A missing/non-conforming entry point is a named preflight/startup failure, never a silent fallback.
* No platform code computes terrain/route/energy/exposure metrics.
* Secrets: server-side only; never in logs/exports/SSE/errors/OpenAPI.
* Test-hook environment switches are inert and rejected outside `ANALOGFORGE_TEST_HOOKS=1` + local auth + (for live) explicit hook flag.
