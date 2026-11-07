# AnalogForge

AnalogForge qualifies Earth analog sites against Moon and Mars mission requirements, then records rover route verification, uncertainty, and a traceable passport. Practice scenarios run without an OpenAI key or network data. Live mode needs an operator-selected model and bound datasets.

## Local start

Use Python 3.12 or 3.13, `uv`, Docker with Compose, and PostgreSQL 16/PostGIS 3.4. Copy `.env.example` to `.env`; set `DATA_ROOT` to an absolute writable path such as this checkout's `data/`, set `DATABASE_URL` to `127.0.0.1` with the selected local port, and set a local database password. Then run `make bootstrap`. For native macOS development, set `DB_PORT` to the chosen private port before bootstrapping. Run `make dev`; it starts the database, migrations, local seed, API, worker, and the web dev server when `apps/web` is installed. Stop with Ctrl-C, then `make down` for the Compose database. `AUTH_MODE=local` requires a loopback `API_HOST`.

The local practice scenario is selected with `SCENARIO_DEFAULT=synthetic-mars-mobility-v1`. The API health and capability endpoints show service readiness and available scenarios. Source and export data live in ignored `data/`; no real secrets or downloads belong in Git.

## Commands

`make migrate` updates the database schema. `make seed-synthetic` is offline and repeatable. `make preflight` checks runtime, storage, identity, model, science, scenario, source lock, and datasets. `make test` runs offline contract and platform tests. `make check` adds docs, lint, typing, forbidden-pattern, and mutation checks. `make test-live` runs only with server-side OpenAI settings and bound live datasets; otherwise it reports `BLOCKED_EXTERNAL`. `make generate-client` updates frontend API types. `make build` compiles Python and the web app. `make backup` makes a PostgreSQL custom-format backup and `make restore-check` restores it to a disposable database to verify the backup.

Every `analogforge` command accepts `--json` for structured output and exits nonzero on failure. `analogforge datasets list` reports intake state; `scaffold <id> --body MARS --role TARGET_TERRAIN` drafts a manifest from local files; `validate <id> --write-checksums` asks the science facade to inspect it; `lock --policy-id <id> --datasets <id> ...` writes an immutable source-policy lock. `generate-practice` and `generate-mock-nasa-drop` call the science fixture generators. `analogforge scenario show <id>` shows full operator configuration; `scenario bind live-hackathon-v1 --target-terrain <id> --earth-terrain <id> [--earth-mineral <id>] [--lunar-thermal <id>]` binds validated real files. Synthetic datasets are rejected from this live slot.

The intake manifest format and role meanings are in `architecture files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md`. Fill provenance, CRS, quantity, units, nodata, and citation from the actual product label before validation. Lock hashes are checked on every preflight. Missing optional mineral or thermal data remains visible as an unknown claim.

## Operations

Keep `.env` private. OpenAI keys and model IDs are needed only for live runs. Live preflight probes strict model capabilities and fails if a key, model, or required dataset is missing. For a machine without Docker, follow `ops/runbooks/native-postgres.md`. The local reverse-proxy example is `ops/proxy/Caddyfile`; keep SSE buffering disabled. Back up both PostgreSQL and the ignored `data/` volume together for a full evidence restore. The backup command covers PostgreSQL; copy the data volume separately under the same maintenance window.
