# Ayan — implementation plan (phases with exit gates)

Follow `team coordination/05-PARALLEL-ONE-SHOT-EXECUTION-PLAN.md`. Within a phase you may parallelize with subagents (single writer per file). Do not enter the next phase until the exit gate holds. Record phase completion (commit SHA, date) in `PROGRESS.md`.

## A0 Orient and bootstrap
Read everything named in the prompt. Materialize + verify the kit; run `tests/contracts/kit`. Create the venv: `uv venv --python 3.12 && uv pip install -e ".[dev,extra-ayan]"`; verify `import rasterio, pyproj, shapely, scipy, numpy` and the GDAL drivers (`GTiff, HGT, PDS, PDS4, netCDF, AAIGrid`). **Exit:** kit PASS, imports OK, driver list recorded in `STATUS.json.environment`.

## A1 Deterministic core (no I/O formats yet)
`geometry.py`, `features/*`, `energy.py`, abstract graph + `routing/search.py` + `routing/verify.py` for the canonical graph, `provenance.py`, deterministic NPZ container. Write SCN-01/02/03/04/05/20-style tests first (analytic oracles from architecture 29; `catalog.GRAPH_EXPECTED`, `catalog.ENERGY_ORACLE_FLAT_1000M`). **Exit:** the canonical graph reproduces every `GRAPH_EXPECTED` entry (supplied and searched) with an independently structured verifier that rejects falsified totals; energy oracle within 1e-8 Wh; slope/relief/roughness analytic fixtures pass at declared tolerances.

## A2 Practice data and raster science
`fixtures/practice.py` generators (architecture 40 §3–§4), raster source/normalize, window grid, analysis grids, histograms, connected components, `ANALYZE_CANDIDATE`, `SCREEN_CANDIDATES`, `CHARACTERIZE_TARGET`, comparison policies, qualification rules, `routing` on rasters (graph from grid, DDA vs slab-clip supercover, certificates, auto-waypoints). **Exit:** SCN-06 (window properties by an independent checker), SCN-07 (screening), SCN-08 (truth table), SCN-09 (all five storylines at science level), SCN-10 (all nine perturbations) pass.

## A3 The port: facade for all 15 operations
`facade.py` dispatch; `DESIGN_BENCHMARK`, `SEARCH_ROUTE`, `VERIFY_ROUTE`, `DIAGNOSE_RESULT`, `ASSESS_COMPATIBILITY`, `OPTIMIZE_PORTFOLIO`, `BUILD_DISPLAY_LAYERS`, `AUDIT_EVIDENCE`, `RESOLVE_COVERAGE`, `FETCH_SOURCE`, `INGEST_LOCAL_DATASET` return kit-valid `ScienceComputationResult`s (validated in tests by constructing the pydantic model, never by dict comparison alone). Write a **registrar stub** under `tests/support/` that mimics the platform's registration rules (architecture 35 §3.3) to prove your artifacts/evidence/local-key closure. **Exit:** every operation has happy-path, `BLOCKED`/`LIMITED` and cancellation tests; SCN-19/20/21 pass.

## A4 Dataset slot
`datasets/{registry,inspect,ingest,checks}.py` with every check in architecture 36 §4 and a failing fixture per check; `fixtures/mock_nasa_drop.py` (architecture 39 §5); parity (SCN-13); moon polar/radius (SCN-14). **Exit:** SCN-11/12/13/14 pass; `draft_manifest` output validates after the TODO fields are filled.

## A5 Live adapters and optional layers
Adapters under `adapters/*` with mocked HTTP (`httpx.MockTransport`) and format-faithful synthetic files (NASADEM `.hgt` big-endian with NUM/water semantics, MOLA/LOLA PDS labels with scale/offset, EMIT NetCDF with mask, Diviner kelvin). Optional-layer behavior (SCN-15). Display layers (SCN-17). Portfolio (SCN-16). **Exit:** SCN-15/16/17/18 pass; adapters import no network at import time.

## A6 Hardening and self-audit
Determinism (SCN-20), perturbation re-run, import hygiene, no-env scan, forbidden-pattern scan, mutation checks, adversarial reviewers (`09`). Performance: each practice operation completes in the budgets of `05` §4. **Exit:** `09` complete; ruff + mypy strict clean on `src/analogforge/science` and adapters; `STATUS.json` complete.

## A7 Report and push
`materialize.py --verify`, ownership check, full gate run, fill `STATUS.json`, commit, push, print summary.
