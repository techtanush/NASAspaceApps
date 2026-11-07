# AnalogForge platform and operations handoff

## Owned implementation

- `src/analogforge/settings.py` is the production environment reader. `Settings()` validates local loopback auth, exact origins, OIDC completeness and URL hygiene, heartbeat bounds, and test hooks. `public_config()` excludes credentials and token-bearing URLs from diagnostics and the effective configuration digest.
- `src/analogforge/cli.py` provides `serve`, `worker`, `migrate`, `db`, `seed-synthetic`, `preflight`, `datasets`, `scenario`, `export-openapi`, `science-check`, and `assurance-selftest`. The worker passes the configured store and settings into `PlatformRuntime`.
- `application/datasets.py` uses the frozen dataset intake and synthetic practice entry points, verifies manifests and source hashes, makes immutable locks, and rejects synthetic locks for live binding. `seed.py` creates the synthetic lock, workspace, user, and membership idempotently.
- `application/preflight.py` checks runtime, storage, identity, model capability, metadata, download, science, scenario, lock, and datasets. A missing external science or renderer implementation is reported as a failing dependency. `capabilities.py` projects the five configured scenarios and current adapters/locks onto the public capability shape.
- `config/scenarios.yaml` has five catalog scenarios. `config/presets` are byte-identical copies of the frozen kit fixtures.
- `scripts/bootstrap.sh` tries Compose then a private native PostgreSQL bootstrap. `scripts/dev.sh` now calls bootstrap before migrate, seed, preflight, API, worker, and web startup. The native bootstrap initializes UTF-8 and PostGIS. `ops/backup` and `ops/restore` select the native PostgreSQL client version and keep the password out of argv.

## Integration seams

- Science: `SCIENCE_ENTRY_POINT` must resolve to a `ScienceService`; synthetic coverage is probed through the real adapter. No fallback fake is used by preflight.
- Renderer: `RENDERER_ENTRY_POINT` must resolve to a `PassportRenderer`. Preflight checks it before marking the download stage ready.
- Dataset adapters: `INGEST_LOCAL_DATASET`, practice generation, and mock NASA generation are imported dynamically; their manifest and hash outputs are verified before locking.
- Live model: a strict Responses tool and structured output probe is required by live preflight. The local fake endpoint works only with the explicit test hook settings.
- Storage: the active `.env` uses the ignored UTF-8 native databases on port 5433. The older SQL_ASCII database was retained, not overwritten. Backup and disposable restore both passed against the active UTF-8 database.

## Checks and remaining work

- Focused owned tests: 29 passed. Ruff, formatting, mypy on six owned production modules, documentation validation, and forbidden scan passed.
- Process recovery: `test_process_recovery.py` uses disposable UTF-8 databases and spawned OS processes. API SIGKILL/restart preserves a schema-validated public run snapshot and SSE cursor replay; worker SIGKILL during a spawned slow science call is reaped and replaced, the science child PID is cleaned up, the stale token is fenced, and evidence is published exactly once. Both tests passed in 8.85 seconds.
- The complete mutation gate passed: 20 of 20 mutants were killed. `scripts/mutation_check.py` requires each baseline to pass and counts only assertion failures as kills. It writes `data/out/mutations.json`; import/setup and other failures do not pass.
- `make test` runs the frozen kit in its own pytest process before platform tests, preserving the kit's import-isolation assertion. The kit passed 20/20 independently.
- Final root source `eb4cd4c63e4477a050370c8084c89c596e9ea1af passed278 platform tests,20 separate kit tests, documentation, Ruff and strict mypy123 files. Aggregate `make check` correctly stops with exit2 at named missing Ayan configuration/science and Aradhya renderer; all remaining branch checks were run separately. See `validation/make-check.log` and `STATUS.json`.
