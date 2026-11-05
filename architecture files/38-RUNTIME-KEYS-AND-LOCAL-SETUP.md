# Runtime, API keys and local setup

Extends [20](20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) and [21](21-CONFIGURATION-AND-PREFLIGHT.md) with the practical answers a coding agent and an operator need: *which keys, when, how to run without them, how to get a database, and how to know what is still missing.*

## 1. Keys and accounts — the complete list

| # | Secret / account | Env var(s) | Needed for | Needed before the hackathon? | Needed for the hackathon run? |
| --- | --- | --- | --- | --- | --- |
| 1 | **OpenAI API key** (project-scoped, server-side) | `OPENAI_API_KEY` | `live` mode: the ten-role Agent Council and Mission Fingerprint preparation | **Optional** to *build*. Required to run the live-agent capability probe and the live-path rehearsal | **Yes** for any `live` run |
| 2 | **OpenAI model id** (explicit, chosen by the operator; must support Responses API, strict function calling and structured output on that account) | `OPENAI_MODEL` | same | same | **Yes** |
| 3 | NASA Earthdata Login token | `EARTHDATA_TOKEN` | Optional *network* adapters (`earthdata`, protected downloads) | No | **No** if NASA data arrives as files (the expected case); yes only if you choose to download protected granules during the event |
| 4 | Local Postgres password | `POSTGRES_PASSWORD` / `DATABASE_URL` | Every mode | Generate any local random value | Same |
| 5 | Session secret | `SESSION_SECRET` | `AUTH_MODE=oidc` only | No (local mode needs none) | No |
| 6 | OIDC client | `OIDC_*` | Hosted multi-user only | No | No |
| 7 | Map tile vendor token | `MAP_TILE_URL` (+ vendor token) | Optional licensed basemap | No (default basemap is bundled/offline) | No |

Not needed, ever, for this product: a `NASA_API_KEY`, Google Maps/Earth Engine, Mapbox, Meteomatics, GoDaddy/Microsoft/Google sponsor credits, a vector database, Redis. **Anthropic/Claude keys are not used by the product**; Claude Code/Codex are only the *builders*. Do not add a second model provider.

**The one thing the operator must obtain in advance for the hackathon:** an OpenAI API project with funded limits, plus the exact model id to put in `OPENAI_MODEL`. Everything else is local.

## 2. What runs with which configuration

| Configuration | What works |
| --- | --- |
| No keys at all | Everything in `synthetic` mode (all four practice scenarios), `replay`, the whole UI, passports/exports, assurance, jobs, recovery, dataset CLI, preflight. This is the default and the state of every branch's test suite. |
| + `OPENAI_API_KEY` + `OPENAI_MODEL` | `live` mode agent roles. Run `analogforge preflight --mode live` → the capability probe (strict tool call + structured result) must pass before a live run is accepted. |
| + datasets bound to `live-hackathon-v1` | A live run on real data. |
| + `EARTHDATA_TOKEN` | Optional network downloads of protected Earthdata products. |

Rules ([20](20-CREDENTIALS-AND-EXTERNAL-SERVICES.md)): never silently fall back from `live` to scripted/synthetic; never invent a model id; never read keys from anywhere except the explicitly configured environment/`analogforge/.env`; never search the user's filesystem for keys; if a key is absent, finish all offline work and report the unmet live gate as `BLOCKED_EXTERNAL`. Errors are `503 PROVIDER_AUTH_FAILED` with `details.dependency` = `OPENAI_API_KEY`|`OPENAI_MODEL` and a remediation string; the UI shows `remediation-hint[data-dependency=…]`.

## 3. Environment variables

Canonical list: the kit's `analogforge/.env.example` (copy to `analogforge/.env`, git-ignored). It extends [21](21-CONFIGURATION-AND-PREFLIGHT.md) with the profile settings `COMPOSE_PROJECT_NAME`, `API_PORT`, `WEB_PORT`, `DB_PORT`, `PROFILE`, `TEST_DATABASE_URL`, `SCENARIO_DEFAULT`. Test-only switches (honored **only** when `ANALOGFORGE_TEST_HOOKS=1`): `ANALOGFORGE_OPERATOR_LIMITS_JSON`, `ANALOGFORGE_FAKE_OPENAI_URL`, `ANALOGFORGE_ALLOW_TEST_HARNESS_PROVIDER=1`. They must be inert and rejected at startup in any profile where `AUTH_MODE != local` or `ANALOGFORGE_MODE=live` without the explicit hook flag.

## 4. Getting the services a build agent needs

A coding agent must **try the options in order** and record which one it used. Declaring a database test "blocked" before trying all options is a failure.

### 4.1 PostgreSQL 16 + PostGIS 3.4 (Tanush; and the merging agent)

1. `docker compose up -d db` using the pinned `postgis/postgis:16-3.4` service in `compose.yaml` (host port `DB_PORT`).
2. No Docker daemon: install natively — Debian/Ubuntu `apt-get install -y postgresql-16 postgresql-16-postgis-3` (or the distro's equivalent version ≥ 15 with PostGIS ≥ 3.3); macOS `brew install postgresql@16 postgis`. Initialize a private cluster in `analogforge/.runtime/pg`, start it on `DB_PORT` with `pg_ctl`, create role/db from `.env`, `CREATE EXTENSION postgis`.
3. Still impossible (no root, no daemon, no package access): run all logic that can run against the ports with in-memory test repositories, mark every `@pytest.mark.db` test as `BLOCKED_ENVIRONMENT` with the exact commands tried and their errors, and say so prominently in `STATUS.json`. The merging agent must then obtain a database by one of options 1–2 before declaring the merge complete.

`make dev` wraps option 1; `analogforge.cli` exposes `analogforge db up|down|status` that wraps whichever option was used (writes `analogforge/.runtime/db.json`).

### 4.2 Python / science stack

Python 3.12 (3.13 accepted). `uv venv --python 3.12 && uv pip install -e ".[dev,extra-<you>]"`. Verify with `python -c "import rasterio, pyproj, shapely, scipy, numpy; print(rasterio.__gdal_version__)"`. `rasterio` wheels bundle GDAL; if a wheel is unavailable install `libgdal-dev` and build. The GDAL drivers `GTiff`, `HFA`, `HGT`, `PDS`, `PDS4`, `netCDF`, `AAIGrid` must be present (preflight `RUNTIME` stage lists them); a missing driver for a *declared* format is a named validation failure.

### 4.3 Frontend

Node 22, pnpm 10 (`corepack enable`). Playwright browsers: use an already-installed Chromium if present (`PLAYWRIGHT_CHROMIUM_EXECUTABLE`), else `pnpm exec playwright install chromium`. Browser tests run headless with `--no-sandbox` when required. Aradhya's `pnpm install --frozen-lockfile` uses her committed `pnpm-lock.yaml`.

### 4.4 Ports (per [04 team coordination](../team%20coordination/04-LOCAL-RUN-AND-DATA-ISOLATION.md))

Defaults per profile: integration 8000/5173/5432; tanush 8001/5174/5433; ayan 8002/5175/5434; aradhya 8003/5176/5435. Check availability first; never kill unknown processes.

## 5. Preflight contract

`analogforge preflight --mode <live|replay|synthetic> --scenario <id> --output <path>` writes JSON and a readable summary and exits non-zero on any required failure. Stages (exact ids): `RUNTIME`, `STORAGE`, `IDENTITY`, `MODEL`, `METADATA`, `DOWNLOAD`, `SCIENCE`, `SCENARIO`, `LOCK`, `DATASETS`. Each gate: `{stage, code, severity, dependency, checked_at, explanation, remediation}`.

* `MODEL` in `synthetic`/`replay`: asserts no provider client is constructed (passes without keys). In `live`: `MODEL_KEY_MISSING`, `MODEL_NAME_MISSING`, `MODEL_CAPABILITY_FAILED`, or pass.
* `DATASETS` (new): for the scenario's bound datasets: manifest valid, files hash-match the lock, roles cover the mission's required dimensions; unbound roles listed as limitations (not failures) unless the mission's mandatory requirements depend on them.
* For `live-hackathon-v1` before binding: exit 1 with exactly the missing items, e.g. `DATASETS_UNBOUND: target_terrain, earth_terrain` and `MODEL_KEY_MISSING`.
* `SCIENCE` runs a tiny probe (analytic plane slope, nodata survival, planetary convention test, synthetic route) through the **real facade** — the check the app uses to know the science entry point is genuinely installed.

## 6. Pre-hackathon operator checklist

1. OpenAI project + funded limit + model id (§1). Put both in `analogforge/.env` on the demo machine; run `analogforge preflight --mode live --scenario live-hackathon-v1`; only the dataset items may remain unmet.
2. Run `analogforge datasets generate-practice` and the mock NASA drop rehearsal ([39](39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) §5).
3. Confirm the demo machine meets the budget: 4 CPU cores, 8 GiB RAM, 20 GiB free disk; Docker or native Postgres; Node 22; a browser.
4. Keep `data/incoming/` empty of unrelated files; confirm `analogforge/data/` is git-ignored and backed up separately.
5. Read [37](37-HACKATHON-DAY-RUNBOOK.md).
