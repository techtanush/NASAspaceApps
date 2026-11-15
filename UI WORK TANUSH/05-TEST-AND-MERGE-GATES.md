# Tanush tests and completion gates

## Focused meaningful tests

- Catalog: JSON schema, bytes/hash/dimensions, 2:1 orientation and known geographic landmarks at image controls; invalid paths/../external URLs/missing attribution rejected. Missing catalog leaves frontend fallback possible.
- Source preparation: exact source hashes/labels, deterministic derivative recipe, no overwriting parent/lock, body radius and height-reference preservation. Real zero distinct from nodata. Hash mismatch fails before publish.
- Regional geometry: four raster corners and an interior control point independently agree with footprint/affine for EARTH/MARS/MOON; Earth CRS rejected for planetary view. Non-square/north-up variants, row direction, pixel centre/corner, seam/pole boundary and masked edge cases. Valid-region fraction retained.
- Coverage: valid/partial/no/no-provider, footprint vs mask basis, wrong lock/scenario/body/workspace, invalid bbox, changed lock/config cache invalidation, unauthorized dataset omission and finite request bounds.
- Detail projection: each ID belongs to this run and candidate, immutable refs, stale/wrong layer fails; no local filesystem disclosure; missing detail is unavailable, no acquisition side effect on GET; partial derivative never published complete.
- Benchmark projection: exact current candidate/requirement/artifact join, unit/support compatibility, nulls, FAIL and GAP, absent rover and attempt ancestry. No fabricated numeric margins or qualification changes.
- Resource/security: bounded acquisition/download/timeouts/cache, allowlisted sources and no arbitrary URLs, private credentials, same-origin artifact transport, deterministic registered publication; preserve event/job recovery and real science guards.

## Commands from analogforge

```sh
rtk proxy uv sync --locked
rtk proxy uv run --locked python '../architecture files/contracts/kit/materialize.py' --verify
rtk proxy uv run --locked pytest tests/unit/science tests/integration/science tests/contracts/science -q --strict-markers
rtk proxy uv run --locked pytest tests/unit/platform tests/integration/platform tests/contracts/platform -q --strict-markers
rtk proxy uv run --locked ruff check src tests --extend-exclude tests/contracts/kit
rtk proxy uv run --locked mypy src/analogforge --exclude src/analogforge/ports
rtk proxy uv run --locked python scripts/science/forbidden_scan.py --json out/science-forbidden.json
rtk proxy uv run --locked python scripts/forbidden_scan.py --json out/platform-forbidden.json
```

Add focused tests for new modules and run those first. The public schemas/samples must validate; they are not a substitute for real API contract tests. Use synthetic/isolated databases for default tests, real facade implementations, no private live credentials required. For actual data checks use explicit local configuration, validated source acquisition and existing bounded preflight; do not modify the previous accepted contract or test hooks to force a green run.

## Merge handoff

Deliver branch/head/commonbase, exact changed modules, additive contract commit if any, schemas/capability, data preparation recipe and hash manifest, tested actual endpoints, available regional artifacts, unknown/deferred fields and machine-readable gate results. No rasters, .env, keys, database copies or entire Aleph repository in Git. Tiny redistribution-approved context images are permitted only as versioned assets with provenance.

Integration runs full `rtk make check`, 17+ existing real browser journeys plus new drill-down journeys, all mutation gates and hands-on Earth/Mars inspection on the actual merged source. Scientific smoke cases preserve FAIL/UNKNOWN and LIMITED/no-rover; compare exact registered export bytes/digests when published. No physical validation claim.

Do not mark this round completed because old main's gates passed. Both app sources and contract seam must be unchanged during final gates, and the final pushed tree must match the tested tree.
