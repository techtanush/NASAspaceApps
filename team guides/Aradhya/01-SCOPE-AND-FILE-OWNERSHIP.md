# Aradhya — scope and file ownership

## Owned paths (see `team coordination/contracts/ownership.json`)

* `analogforge/apps/web/**` (React app, generated client, mock backend, unit/component tests)
* `analogforge/{package.json,pnpm-lock.yaml,pnpm-workspace.yaml}`
* `analogforge/src/analogforge/rendering/passport/**` (pure renderer)
* `analogforge/tests/unit/passport_renderer/**`, `tests/contracts/ui/**`, `tests/e2e/**`
* `analogforge/scripts/ui/**`, `analogforge/scripts/build_mock_exports.py`
* `team guides/Aradhya/**`, `team handoffs/aradhya/**`
* Your `extra-aradhya` list in `pyproject.toml` (renderer-only Python dependencies; `jinja2`/`markupsafe` are already in the kit). Install Python deps with `uv pip install -e ".[dev,extra-aradhya]"`; never commit `uv.lock`.

## Not yours (report, never edit)

The kit; Tanush's backend/config/compose/Make/migrations/lock; Ayan's science/adapters/tiles/config; original architecture files; others' guides/handoffs.

## What you deliver

1. The workbench: S01–S12 per architecture 16 and `08` §4, with every `data-testid` of `contracts/ui-testids.json`.
2. Maps: offline Earth map + body-aware planetary panel with affine-correct overlays and numeric alternatives.
3. State/server layer: generated client, idempotent/revision-guarded mutations, SSE controller with dedup/gap/410/reconnect/terminal handling.
4. Mock backend (mock mode only) replaying architecture 40 storylines, with real-renderer exports.
5. Pure renderer (html/json/csv) with fixtures and hostile-string tests.
6. Journeys J01–J13 (Playwright) that run in mock mode now and in real mode at merge.
7. Filled `STATUS.json`, pushed.

## Boundaries you enforce in your own code

* No scientific computation (qualification, energy, slope, exposure, coverage, similarity) in TypeScript or in the renderer; the renderer only arranges frozen bundle data. Metric lookups for CSV use the fixed mapping of `08` §7 and never arithmetic.
* No second declaration of a scientific enum; no handwritten API types.
* No network except the API base URL; no CDN assets; basemap bundled.
* The renderer is pure and deterministic (no clock, env, filesystem writes, network).
* Mock mode is a development/test tool: bannered, absent from production builds, never a runtime fallback.
