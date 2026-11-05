# Repository layout and dependencies

Create the application beside `architecture files`, preserving this specification as documentation. Do not build a separate application inside every specification directory. Use one Python package and one frontend project.

```text
analogforge/
  README.md
  Makefile
  compose.yaml
  .env.example
  .gitignore
  pyproject.toml
  uv.lock
  package.json
  pnpm-lock.yaml
  apps/web/
    package.json
    index.html
    vite.config.ts
    src/{app,features,components,generated,map,styles,test}/
    public/{basemap,icons}/
  services/api/
    Dockerfile
    alembic.ini
    migrations/
  src/analogforge/
    main.py
    settings.py
    cli.py
    api/{dependencies,errors,routers}/
    domain/{models,enums,policy,hashing}/
    application/{missions,runs,qualification,verification,exports}/
    db/{models,repositories,unit_of_work}/
    jobs/{queue,leases,worker,handlers}/
    agents/{runtime,roles,schemas,prompts}/
    tools/{registry,receipts}/
    science/{raster,planetary,features,comparison,routing,energy,portfolio}/
    adapters/{openai,earthdata,pds,emit,diviner,storage,identity}/
    rendering/{tiles,passport}/
  config/{datasets.yaml,algorithms.yaml,scenarios.yaml}
  contracts/{domain.schema.json,openapi.json}
  tests/{unit,property,integration,contracts,e2e,fixtures}/
  scripts/{bootstrap,preflight,seed_synthetic,lock_sources,validate_docs}
  ops/{proxy,backup,restore,runbooks}/
  data/                    # ignored, mounted persistent storage
```

## Runtime selection

Use Python 3.12, Node 22 LTS, pnpm 10, PostgreSQL 16/PostGIS 3.4 as selected compatibility baselines. These are design pins, not claims to be the newest releases. Resolve exact available patched versions and image digests at bootstrap, record them in `build-lock.json`, and commit dependency locks. Never silently switch major versions or leave production image tags as `latest`.

Python package groups:

- API: fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, alembic, psycopg with pool support, httpx, python-multipart.
- Science: numpy, scipy, rasterio, pyproj, shapely, pillow; xarray/h5netcdf or netCDF4 for the chosen EMIT product; pvl for PDS labels when appropriate. Pin GDAL compatibility with the rasterio build rather than mixing arbitrary native versions.
- AI: openai. Do not require an orchestration framework; implement role scheduling with the documented state machine.
- Validation: jsonschema, referencing, rfc8785, pytest, hypothesis, pytest-asyncio, coverage, ruff, mypy. Backend scientific calculations require tests; do not waste tests on static CSS details.

Frontend groups: react/react-dom 19, TypeScript, Vite, React Router, TanStack Query, MapLibre GL JS, a JSON-schema form/validation bridge if needed, lucide-react or another single licensed icon set, Vitest, Testing Library, and Playwright. Use native accessible controls before adding a large widget library. Resolve compatible exact versions into `pnpm-lock.yaml`.

## Interfaces and generated code

Pydantic models implement the architecture schema. Export OpenAPI from the backend; generate TypeScript types/client into `apps/web/src/generated`. The checked-in blueprint contract is the starting authority, not a parallel hand-maintained API after implementation. CI compares exported shapes against the approved contract and reports breaking changes.

Frontend code may not declare a second enum for scientific statuses. Import generated types. Python may not use strings such as `almost_pass` in place of shared enums. Changes to a public model require schema version handling, fixture updates, and an architecture decision.

## Local commands to implement

Provide Make targets `bootstrap`, `dev`, `migrate`, `seed-synthetic`, `preflight`, `test`, `test-live`, `generate-client`, `build`, `check`, `backup`, and `restore-check`. Each target must explain prerequisites and fail nonzero on incomplete work. `make dev` should start services without downloading large data. `make seed-synthetic` must be reproducible and offline. `make test-live` is opt-in and never part of normal offline CI.

Use `rtk` prefixes when executing shell commands in this user's environment, as required by their instructions. Build scripts should test for `rtk` and provide documented direct equivalents for other environments; the product itself must not depend on a terminal output filter.

## Git and data hygiene

Ignore `.env`, `data/`, downloaded products, derived rasters, credentials, local model traces containing private prompts, caches, generated screenshots, and database volumes. Track small synthetic fixtures, schemas, manifests, algorithms, source metadata, and license notices. A dataset lock records source hashes and storage-relative paths; it does not commit restricted credentials or signed URLs.

## Acceptance

A clean checkout can install from committed locks, start a healthy database, run migrations, generate the client, build the frontend, and complete the offline synthetic end-to-end test. Docker image builds must confirm imports for rasterio, pyproj, and the selected NetCDF stack before application work depends on them.
