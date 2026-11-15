# Tanush ownership

Own backend Python API/application/read projections, scientific DISPLAY preparation, dataset acquisition/validation CLI, backend-specific tests and new versioned files under `analogforge/apps/web/public/globe/data/**` and `public/globe/deliveries/**`. Do not modify frontend src, React/CSS, package/lock, MSW or e2e UI assertions. Aradhya alone owns GlobeStage/globeAssets.ts and API adapters.

Suggested new backend modules: `src/analogforge/application/visualization.py`, `api/routers/visualization.py`, display preparation helpers under science/display and acquisition scripts under scripts/data. These are planned locations, not existing required class names. Keep source acquisition out of request threads; use existing job/artifact/storage patterns.

## Deliverables

- T0: exact schema decisions, backward-compatible contract plan and fixtures; optional routes disabled/unavailable until genuinely wired.
- T1: versioned imagery catalog + licensed prepared surface assets with source/derivation receipts; visual context only. No replacement of existing fallback filenames.
- T2: actual Earth and Mars regional display artifacts for registered areas; aligned footprint/mask/metadata and independent control points.
- T3: authenticated coverage and detail read projections where current APIs cannot already supply the data; body/scenario/lock/workspace safe, no auto-fetch side effects.
- T4: benchmark read projection only where existing registered comparison data supports it; absent values explicitly unknown, route results scoped per candidate/test/attempt.
- T5: backend/unit/integration/provenance tests, data recipe, compact integration evidence and handoff to Aradhya.

Plan F6 automatic proving and F7 new PDF service are deferred. Existing APIs/manual proving/export service remain. Do not alter terrain metrics, thresholds, active budgets, acceptance rules or passport claims to make a new display look complete.

OpenAPI/kit changes, if necessary, are owned by you as integration owner through architecture35's materialization and compatibility checks. Deliver the small contract change first; frontend types are regenerated, never hand-edited. Keep the shared seam schemas frozen unless both sides are reconciled with a versioned change.
