# Ayan — scope and file ownership

Your code is a **pure scientific library plus approved source adapters**. It must run with no web API, database, model, browser or network (in `synthetic`/`replay`). Everything crosses the boundary as typed kit models.

## Owned paths (longest-prefix registry, `team coordination/contracts/ownership.json`)

* `analogforge/src/analogforge/science/**` — facade, geometry, raster, features, comparison, qualification, compatibility, routing, energy, portfolio, display, datasets, fixtures, audit, provenance (layout in `08` §2).
* `analogforge/src/analogforge/adapters/{earthdata,pds,emit,diviner,user_survey,source_http}/**`
* `analogforge/src/analogforge/rendering/tiles/**`
* `analogforge/config/{datasets,algorithms,candidates}.yaml`
* `analogforge/tests/{unit,property,integration,replay}/science/**`, `tests/contracts/science/**`, `tests/fixtures/science/**`
* `analogforge/scripts/science/**`
* `team guides/Ayan/**`, `team handoffs/ayan/**`
* Your own list `extra-ayan` in `analogforge/pyproject.toml` (science-only dependencies). Install with `uv pip install -e ".[dev,extra-ayan]"`; never commit `uv.lock`.

## Not yours (report, never edit)

The kit (`ports/`, kit tests/fixtures/contracts), Tanush's platform (`api`, `db`, `jobs`, `application`, `agents`, `tools`, `main.py`, `cli.py`, `config/scenarios.yaml`, `config/presets/`, compose/Make/migrations/lock), Aradhya's frontend and `rendering/passport/`, original architecture files, other people's guides/handoffs.

## What you deliver (summary; exact files in `08` §2)

1. `science.facade:create_science_service` returning a `ScienceService` whose `supported_operations()` is all fifteen `ScienceOperation`s and whose `execute()` is correct, deterministic, cancellable and honest (`BLOCKED`/`LIMITED` instead of guessing).
2. Dataset slot support: `INGEST_LOCAL_DATASET` with every check of architecture 36 §4; `science.datasets.inspect:draft_manifest`; format support for GeoTIFF/COG, HGT(+zip), PDS3/PDS4 through GDAL, NetCDF, ASCII grid.
3. Generators: `science.fixtures.practice:generate_all` (all datasets of architecture 40 §3) and `science.fixtures.mock_nasa_drop:generate` (architecture 39 §5), plus in-memory fixture loaders so `SourceSelector(kind="SYNTHETIC_FIXTURE")` and `LOCAL_DATASET` give identical rasters.
4. The route engine: constraints design (`auto-waypoints-v1`), graph (raster + abstract), resource-constrained search with certificates, **independent verifier**, diagnosis (ANALOG vs ROVER rule), telemetry.
5. Qualification/compatibility/portfolio math, display-layer images and manifests, audit evidence (`AUDIT_EVIDENCE`).
6. Live adapters (`earthdata`, `pds`, `emit`, `diviner`, `user_survey`, `source_http`): discovery/fetch/decode/mask/normalize, safe redirects/checksums, honest `NO_COVERAGE`/`AUTH_REQUIRED`/`UNSUPPORTED` states — validated against **format-faithful synthetic files and mocked HTTP transport**. They are never claimed validated against real servers.
7. Tests for every catalog row `SCN-01…SCN-21`, perturbation tests, and a filled `STATUS.json`.

## Hard boundaries

* No imports of `fastapi`, `sqlalchemy`, `psycopg`, `openai`, `analogforge.api|db|jobs|application|agents|tools|rendering.passport` anywhere under your paths (tested, SCN-19).
* No `os.environ`/`os.getenv` in science code; credentials arrive only through `context.http_client()` supplied by the platform. (The adapter modules receive an injected client; they never read the environment.)
* No network access in `synthetic`/`replay`; `context.http_client()` is `None` there and `source_policy.allow_network` is `False`.
* Write files only under `context.scratch_dir()`; never under `data/incoming/`; never outside the repo scratch.
* Never convert unknown to zero; never interpolate categorical ids; never upsample to claim resolution; never use Earth CRS for Moon/Mars.
