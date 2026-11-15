# Tanush visualization delivery

Round base: `ui-split-base-20261114`, commit `52f41e58091a735527ef819beb4bdfb7bb6d1ed9`. Branch: `tanush/platform-agents-integration`. Claude's corrected BETTERUI state `fc5e084` is inherited unchanged. Compare this round from the base tag, rather than classifying all inherited UI code as Tanush edits.

The backend and imagery delivery is implemented. Aradhya still owns connecting it to the Mission Control frontend, report page, responsive/accessibility work and browser tests. This branch does not claim those UI tasks are complete. No frontend component, camera code, dependency, lockfile or existing fallback asset was edited by this delivery.

## What now exists

| Task | Delivery |
|---|---|
| T0: contracts | Six opt-in, authenticated GET operations, effective OpenAPI, five packaged JSON schemas, frozen core unchanged. |
| T1: global imagery | Real attributed NASA Earth/Mars/Moon context images, pinned inputs, deterministic bounded preparation, complete receipts and catalog. |
| T2: regional detail | Reuses real science's registered elevation/slope manifests and RGBA image artifacts for the exact selected target/candidate. Actual NASADEM/MOLA rehearsal target and all four candidates verified usable. |
| T3: availability | Explicit offline footprint preparation and authenticated reads bound to the actual scenario, source lock, configuration and source identities. No raster acquisition in HTTP. |
| T4: benchmarks | Exact accepted requirement and committed qualification projection. Numeric measurements require the correct registered comparison artifact, compatible units/support and exact candidate ancestry. |
| T5: verification | New regression/HTTP tests, full backend and science checks, independent audit, actual LIVE read-only inspection and handoff instructions. See STATUS and VALIDATION for final outcomes. |

No additional API key is required for these features. No Aleph code, server, Google imagery, paid map provider or cloud account is a runtime dependency. See `04-ALEPH-REFERENCE.md` for the reviewed reference patterns and Earth-only boundaries. Existing NASA acquisition credentials, when required for different scientific source products, remain server-side and separate from this public imagery catalog.

## Enable and discover the optional API

Use the same private DATA_ROOT, CONFIG_DIR, database and identity configuration as the existing app. Add `ANALOGFORGE_VISUALIZATION=1` to the local server environment, then restart that server. Default is false; disabled visualization paths return 404. This display feature flag is excluded from the scientific configuration digest, so it does not revise accepted scientific inputs.

With the flag enabled, the normal application identity policy applies: local mode uses the local principal; OIDC mode requires a verified session/workspace. Run-specific responses use the current authenticated workspace. All responses are `Cache-Control: no-store` through the existing global boundary. There are no visualization mutations, provider calls, new workers or migrations.

All paths below have the `/api/v1` prefix:

| GET path | Meaning |
|---|---|
| `/visualization/capabilities` | Explicit v1 feature availability and same-origin imagery/OpenAPI paths. Capability means a feature exists, not that a region has data. |
| `/visualization/openapi.json` | Frozen core plus the actual six registered operations and their schemas. Authenticated like the other extension paths. |
| `/visualization/coverage` | Prepared, validated operator source footprint availability; exact query parameters below. |
| `/runs/{run_id}/visualization/target` | Actual accepted target geometry and usable registered display-manifest IDs. |
| `/runs/{run_id}/visualization/candidates/{candidate_id}` | Same envelope for a candidate pinned to this run. |
| `/runs/{run_id}/visualization/candidates/{candidate_id}/benchmarks` | Current accepted requirements, qualifications, attributable comparison measurements and candidate-specific test-result IDs. |

Unknown or duplicate coverage parameters, malformed UUIDs, nonfinite boxes, mismatched locks and incompatible body/scenario selections fail explicitly. Foreign/unpinned run resources return 404. Unavailable source/detail data returns the documented unknown/unavailable envelope rather than fetching, recomputing or queuing work.

The immutable core contract in `analogforge/contracts/openapi.bundled.json` and architecture35's materialized kit are unchanged. The extension is documented by `api/visualization_contracts.py`, with packaged schemas under `api/visualization_schemas/`. A deployment without the handoff documentation still has every runtime schema. Wheel packaging was verified.

Generate separate visualization types after integrating this branch:

```sh
rtk proxy uv run --locked analogforge export-openapi --include-visualization --out out/openapi.visualization.json
rtk proxy corepack pnpm --dir apps/web exec openapi-typescript ../../out/openapi.visualization.json -o src/generated/visualization-schema.d.ts
```

Aradhya owns that generated frontend file and its consumer. Preserve the current core generation command. Omitting `--include-visualization` still exports the frozen core. The combined specification has already generated TypeScript successfully and that declaration passed strict typechecking in an ignored output directory.

## Catalog adapter for Aradhya

1. Fetch `${BASE_URL}globe/data/catalog.v1.json`; validate schema_version1.0, body identity and safe same-origin paths. On missing/invalid catalog, preserve current truthful fallback navigation.
2. Resolve each BASE_URL-relative `surface_path`. Preserve attribution, product/acquisition context, source URI, usage terms and placeholder flag. Source URI is citation metadata; the browser loads the committed same-origin delivery image.
3. All delivered surfaces are real visual context (`placeholder:false`). All `relief_path` values are null. Clear the old synthetic bump texture rather than keeping it on a real image.
4. Apply no extra 180-degree roll. Files are north-up, east-positive, -180 at left and zero at center. The inherited sphere's UV convention already agrees. Inspect landmark orientation after wiring the actual renderer.
5. Global context is not terrain evidence. Earth is a July2004 visual composite; Mars is natively1440x720; the Moon publisher's aesthetic polar fill is explicitly disclosed. Zoom never adds source resolution.

Full paths, SHA-256, bytes, licenses, controls, limits and reproducible preparation commands are in `IMAGERY-DELIVERY.md`. Total three-image payload:4,216,978bytes. No raw downloaded originals are committed.

The nullable-relief correction is isolated as commit `e50a3e9`. `SCHEMA-ERRATUM-001.md` explains why JSON Schema had accidentally rejected its explicitly permitted null. The runtime copy is tested against the corrected shared schema. Do not invent relief to satisfy the old defect.

## Coverage preparation and reads

Validate scientific source datasets, create their frozen policy lock and bind the selected scenario using the existing dataset CLI. Finish scenario/algorithm/dataset configuration before preparing coverage:

```sh
rtk proxy uv run --locked analogforge visualization prepare-coverage --dataset-lock YOUR_FROZEN_POLICY_ID
```

This is an explicit bounded offline action through the existing real science intake facade. It verifies locked source bytes and writes only `DATA_ROOT/visualization/coverage/<policy-id>.json`. It does not overwrite source rasters, validation reports, manifests, the policy lock, scientific results or accepted contracts.

GET `/visualization/coverage` requires `body`, `bbox` and `scenario_config_id`; `dataset_lock_id` is optional. `bbox` is the comma-separated west,south,east,north box in east-positive NEG180_180 degrees. Use the scenario's exact `default_dataset_lock_id`; omitting the lock yields UNKNOWN. Query bodies are EARTH/MARS/MOON, with Earth permitted for an Earth-source query and the selected planetary body matching its scenario. Split dateline crossings; poles and empty/unordered boxes are rejected.

Reads use bounded metadata and filesystem identities; they do not read/hash raster contents, run science, download or write caches. Configuration, lock, manifest, validation or source identity changes invalidate the prepared index. Prepare again after moving/copying source files to another machine or changing configuration. Do not copy another machine's index and assume its filesystem identities remain valid.

This implementation returns `basis:VALIDATED_FOOTPRINT`, not valid-mask coverage. COVERED means the requested box lies inside the validated eligible source footprint. PARTIAL means overlap, NONE means no overlap, UNKNOWN means unsupported/missing/stale/unbound availability. Comparison support remains null here; source posting is not comparison support. Unsupported footprint frames stay UNKNOWN. Eligibility for a data footprint never means mission PASS.

The catalog describes shared operator-configured datasets, not private per-workspace uploaded datasets or access entitlements. It is authenticated. Run-specific detail and benchmarks are additionally workspace/run scoped. Do not use this operator catalog to advertise another workspace's private data.

## Regional detail adapter

The returned `display_layer_manifest_ids` are references to existing `DisplayLayerManifest` rows, not URLs, new image formats or measurement arrays. Load manifests using the existing `/display-layers` API, constrain them to the selected run/subject and intersect with these IDs. Load `image_artifact_sha256` through the existing authorized `/artifacts/{sha256}` endpoint. Reuse EarthMap for Earth and PlanetaryPanel for the planetary frame.

The backend independently verifies each advertised manifest's workspace/run/mode/subject, accepted target, source evidence, successful receipt, exact registered BUILD_DISPLAY_LAYERS payload and producer image-key-to-hash binding. It validates body, metre CRS, body radius, affine, raster corners, site center, PNG digest, RGBA format and dimensions. Blob reads are bounded before allocation, reject symlinks/FIFOs and detect growth/tampering. AVAILABLE requires usable elevation and slope with no invalid selected-subject row. A valid subset is PARTIAL; absence is UNAVAILABLE. Reads never manufacture missing layers.

Earth Web Mercator must stay Earth-only. Mars/Moon use body-specific projected images. Show original source/scale/mask/height-reference/mode metadata from registered evidence and manifests, retaining unknowns. The images are display products; decoding pixel colors into physical measurements is not supported. A finer camera view does not change the500m analysis support of the tested LIVE rehearsal.

Cache keys include workspace, run, candidate/target, lock and immutable manifest IDs. Clear the old subject immediately on selection changes, cancel obsolete requests and release textures/object URLs. Do not let a late response install the previous site's layer.

## Benchmark adapter

Rows contain the accepted `requirement` verbatim, current qualification ID/status/explanation and a `measurement` object with value, unit, support_scale_m, comparison evidence ID, receipt ID and reason. Missing or incompatible numeric evidence remains null with an explanation. A genuine numeric zero at positive support is preserved; zero/negative support is unavailable. No margins are invented from display pixels or free text.

Preserve pinned candidate order and PASS/PARTIAL/FAIL/GAP/UNKNOWN. Route-related measurements require this candidate's committed test/attempt lineage. The envelope's `test_result_ids` are candidate scoped. A no-rover run has no borrowed route result or verification claim. Buttons continue to use current server allowed_actions and expected_revision; tour selection alone is not a committed selected candidate.

The actual LIVE rehearsal retained the four registered terrain comparisons, in order:2.9065566378066467 PASS;3.682316468253976 PASS;5.722340285976658 FAIL;6.538455988455997 FAIL, all in degrees at500m support. These are verification observations, not fixtures/defaults in application code. LIMITED assurance and missing-rover semantics were preserved; no claim of field or physical validation is made.

## Verification and integration boundary

See `VALIDATION.json` for executed checks and source digest. Private DB configuration, raw rasters, cache, test outputs and source-acquisition originals stay ignored. LIVE inspection used a database connection enforcing PostgreSQL default_transaction_read_only=on and disabled model credentials. The six coverage responses, target/four candidate details and four exact measurements validated against actual HTTP response schemas; scientific record snapshots were unchanged before/after.

An initial platform run was interrupted by confirmed macOS clamshell sleep. Both affected tests passed on a clean retry with unchanged source and limits. The final report distinguishes that interrupted attempt from the fresh complete run with idle sleep prevented. Keeping the laptop awake is an execution requirement; lease and science deadline protections were preserved.

After merging Aradhya's tested branch with this branch on latest main, integration must run the complete merged check script, regenerate/reconcile frontend types, run all existing browser journeys plus coverage/target/site drill-down journeys, inspect Earth/Mars/Moon orientation and masked edges, and verify report/export actions against the real backend. Recheck on the exact merged source, not a scratch UI copy. The main release's old1994/17/72 counts are not certification for this round.

Remaining limits: no new high-resolution global Mars texture, no new live lunar regional source, no automatic multi-site proving, PDF service, attachment/chat interface, private dataset-entitlement catalog or cloud deployment. Existing scientific acquisition/manual proving/export paths remain the authorities. Additional real source regions require normal acquisition, validation, locking and a new supported run; opening a globe pin does not authorize fetching arbitrary URLs.
