# Local runtime and data isolation

Different Git clones/worktrees isolate source files, not ports, Docker project names, database contents, caches, credentials or process IDs. Configure those separately. Tanush implements the profile selection in Compose/Make; each agent then runs only its own profile. Ayan and Aradhya may not have Tanush's Makefile on their branch: they run the underlying commands directly (`uv run pytest …`, `pnpm …`) and need no database unless they choose to test against the real API.

## Profile allocation

| Profile | Compose project | API host port | Frontend host port | Postgres host port | Data root on host |
| --- | --- | --- | --- | --- | --- |
| integration | af-integration |8000|5173|5432| root checkout `analogforge/data/` |
| tanush | af-tanush |8001|5174|5433| Tanush worktree `analogforge/data/` |
| ayan | af-ayan |8002|5175|5434| Ayan worktree `analogforge/data/` |
| aradhya | af-aradhya |8003|5176|5435| Aradhya worktree `analogforge/data/` |

These ports are selected local defaults, not guaranteed free. Check availability, then change the profile and its API/CORS/base URL settings together if occupied. Do not kill an unknown process to free a port. Separate computers may reuse the integration defaults, but the reported profile must match its actual settings.

Inside Compose, PostgreSQL still listens at `db:5432`; mapped host5433/5434/5435 are not container connection ports. API-to-worker communication is through the local profile's database. Named volumes use the Compose project prefix. Bind mounts are relative to the current worktree; do not hardcode the root integration data folder into all three profiles.

## Settings and launch commands

Keep architecture21 canonical setting names. Add nonsecret profile configuration for API_PORT, WEB_PORT, DB_PORT and COMPOSE_PROJECT_NAME in ignored application `.env` or an operator profile file. PUBLIC_BASE_URL, ALLOWED_ORIGINS and VITE_API_BASE_URL must target that same profile. DATA_ROOT inside a container can remain `/data` while its host mount differs. Each worktree has its own `.env`; never copy another person's secrets into a committed profile.

Tanush supplies `make dev PROFILE=<profile>`, `make test PROFILE=<profile>` and `make down PROFILE=<profile>` with documented defaults, plus equivalents if Make is unavailable. Commands must not tear down all projects globally. Ayan can run pure science unit tests without API/DB, and Aradhya can run a visible mock preview without Python while those services are being prepared.

## Database and fixture isolation

Use a separate database/volume per profile and disposable separate databases for integration tests. Never run destructive migrations/tests against another person's profile. Fixed UUID fixture IDs may repeat across isolated databases; they must never be treated as global live identities. Production/new records get fresh IDs. Namespace temporary paths by job/run UUID and profile.

Each synthetic seed command is idempotent and offline. Do not run three workers against one shared DB unintentionally: that would consume the same queue and make ownership/debugging unclear. Multiple workers against one integration profile is an explicit recovery test, not the default individual setup.

## Dataset caches

Ayan may provide a checksummed permitted read-only cache or source manifest for rehearsal. Consumers verify bytes/rights/version metadata; original acquisition lineage is retained. Do not let several workers write the same raw/derived directory concurrently without a content-addressed atomic store. Default separate caches are simplest. Large real products remain ignored; share manifests and approved transfers outside Git. A file called `NASA-data.tif` is not sufficient provenance.

## Credentials and model calls

Use architecture20 for exact server keys. No coding-assistant plan level is used as proof that the product's live API credentials are configured. Each live profile preflights OPENAI_API_KEY/OPENAI_MODEL and selected protected Earthdata access. Synthetic/replay mode never silently calls a real model or source. If a shared funded API project is used, preserve per-run call caps and operator visibility to avoid duplicate exploratory runs; do not change budgets to chase a preferred result.

## Browser tests

Aradhya's Playwright config reads the selected profile URL and uses disposable fixture data, not a hardcoded Tanush URL. Full integration browser tests can start/stop their own declared server processes; they must not terminate an unrelated existing preview. Before testing frontend against real backend, disable MSW explicitly and assert an actual backend receipt/job exists. A mock-handler response alone cannot pass the full integration gate.

## Acceptance

Launch two profiles simultaneously; source edits, database writes, worker claims, exports and cancellation in one do not affect the other. Shut down one project and verify the other stays healthy. Confirm each profile's capabilities/base URL/mode/source lock is visible and agrees with its test report. No runtime files appear in changed-path Git reports.

## Merging agent profile

The merging agent uses profile `integration` (8000/5173/5432, project `af-integration`) on a clean clone. It starts and stops only its own Compose project and never touches another profile. A database is mandatory for the merge ([38](../architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md) §4.1).
