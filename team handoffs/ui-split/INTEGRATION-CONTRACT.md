# UI/data seam contract v1 — frozen for this build round

## Authority and present reality

This document specifies the parallel work, including PROPOSED additive interfaces. The JSON schemas beside it are planning contracts, not declarations that an endpoint exists. Existing transport authority remains `analogforge/contracts/openapi.bundled.json`, generated frontend types and the frozen contract kit. Never hand-edit generated files or alter scientific statuses to satisfy a screen.

Current implemented seams: `GlobeScene`/`GlobeStage`, `GLOBE_ASSETS` (surface context), `DisplayLayerManifest` (quantitative regional display), pinned candidate/qualification helpers, run snapshot/events, existing mission/rover/actions/passport APIs. `coverage.ts` deliberately returns UNKNOWN. Part F of Claude's plan is a backlog, not installed functionality.

## Ownership without shared-file edits

| Surface | Aradhya | Tanush |
|---|---|---|
| Browser components/styles/routes/maps | Owns | Does not edit |
| `src/maps/globeAssets.ts` and GlobeStage interface | Owns loader/fallback/rendering | Supplies data to loader; no TS edits |
| `apps/web/public/globe/data/`, `public/globe/deliveries/` | Consumes; does not edit | Owns new catalogs/assets |
| Existing `public/globe/*` prototype files | Leave as fallbacks | Do not replace in place; version new assets |
| Python API/application/display/acquisition | Consumes generated contract | Owns |
| Frontend API adapters + MSW + browser tests | Owns | Does not edit |
| OpenAPI/frozen kit/additive wire changes | Generates only after contract lands | Integration owner; follows architecture 35 |
| Package/lock frontend changes | Owns minimal justified additions | No frontend dependency changes |
| This contract + schemas | Frozen; propose changes in own STATUS | Frozen; reconcile at integration |

The original architecture's scientific, security and deterministic build constraints remain. Older round-one contributor path classifiers are historical; compare round-two ownership from the COMMON HANDOFF commit, not all prior commits inherited from main/BETTERUI. Do not weaken old scientific gates. Any necessary ownership-rule update must be narrow and reviewed by the integration owner.

## 1. Global visual imagery (not quantitative evidence)

Tanush delivers `analogforge/apps/web/public/globe/data/catalog.v1.json`, matching `schemas/imagery-catalog.v1.schema.json`. Every path is BASE_URL-relative, same-origin and under `globe/deliveries/`; no credentials, signed URLs, traversal or external browser dependency. Aradhya owns an asset loader under `src/api/` and the mapping into `globeAssets.ts`. Until that optional catalog exists or validates, retain current truthful fallbacks. A malformed new catalog must not remove fallback navigation.

Each image is 2:1 equirectangular, north up; record longitude convention, source URI, acquisition/product context, SHA-256, bytes, dimensions, attribution, usage terms and placeholder flag. New image filenames are versioned. Source URIs are citation metadata, not instructions for the browser to contact that host. `relief` means decorative shading only. Global texture pixels never become slope/elevation measurements.

## 2. Coverage projection (proposed; not currently implemented)

Reserved additive path: `GET /api/v1/visualization/coverage?body=MARS&bbox=w,s,e,n&scenario_config_id=...&dataset_lock_id=...`.

Response matches `schemas/coverage.v1.schema.json`: body/box/scenario/lock echo, COVERED/PARTIAL/NONE/UNKNOWN, basis, reason, and eligible validated dataset summaries. COVERED means available under the actual scenario/lock and stated coverage basis; it never means mission PASS. A footprint alone does not prove every cell has usable data. Dataset unavailable, unvalidated or not locked must not produce a green available claim. Never use globally installed datasets to imply another workspace's access.

Aradhya consumes this only after Tanush publishes an additive contract and an explicit enabled runtime capability. Until then use the existing UNKNOWN resolver; do not issue speculative requests to an absent endpoint. Client tests mock COVERED, PARTIAL, NONE, UNKNOWN, unavailable, stale request and wrong-body responses. A late response for an old pin is discarded.

## 3. Regional location drill-down (required experience)

Global globe → select candidate or target → fit its actual bbox → open a regional detail viewport. This is the explicit interpretation of the user's 14 November Fable screenshot: users must inspect the actual selected place, not merely magnify a global texture or see a flat diagram of boxes.

Use existing authenticated display artifacts first. Aradhya adapts existing `DisplayLayerManifest` objects to EarthMap for EARTH and PlanetaryPanel for MARS/MOON. If an additional read projection is useful, reserve `GET /api/v1/runs/{run_id}/visualization/target` and `GET /api/v1/runs/{run_id}/visualization/candidates/{candidate_id}`. Their proposed envelope matches `schemas/site-detail.v1.schema.json`; manifest IDs resolve through the existing authorized artifact/evidence transport. This envelope is metadata only. It does not replace the frozen DisplayLayerManifest or invent new measurement fields.

Keys for a detailed view: workspace + run + target/candidate + dataset lock + immutable manifest IDs. Validate body, current run membership, bbox and artifact ancestry before rendering. Drop old layers immediately on selection changes. Cache bounded metadata/display resources, abort obsolete requests, and release GPU resources. No public static JSON may contain private run artifacts or credentials.

Every detail view shows source/product, scale bar, horizontal CRS, height reference, native/effective resolution when known, analysis/comparison support, valid-mask/no-data information, mode and attribution. Unknown fields remain Unknown. Display-pixel inspection is not an analysis-cell sample. Without a validated sample API, do not decode image color into physical values.

Earth Web Mercator is Earth-only. Mars/Moon use documented body-specific projected display images. UI globe camera math is navigation context and cannot redefine scientific coordinates. Datum shifts and reprojection stay in versioned backend preparation. Unsupported pole/dateline cases get explicit boundaries/errors.

## 4. Benchmarks, selection, actions and publication

Accepted `Requirement` rows supply operator/bounds/unit/support/origin. Committed qualifications supply PASS/PARTIAL/FAIL/GAP/UNKNOWN and explanations. Numeric measurements/margins must be traced to compatible registered comparison artifacts; otherwise render Unknown. Never invent values or infer coverage from an attractive texture.

Preserve `snapshot.candidate_ids` order. Frontend may filter or provide a clearly labelled user-selected sort, but must not silently rank best sites or replace the pinned science ordering. Per-requirement PASS lists are presentation of committed facts, NOT an optimized portfolio or proof of co-location. Portfolio responsibilities come from a persisted portfolio artifact.

Attempts/results must be joined to their actual candidate/test zone/attempt ancestry. No selected-site card may show all run-level results as if they belong to that site. Actions are controlled by the latest server allowed_actions and expected_revision. A selected tour card is a view preference until SELECT_CANDIDATE commits; await that command before any dependent action/navigation. No automatic multi-site proving in this round.

The printable browser summary is labelled as a presentation of current data; it is not an immutable passport or independently certified report. Published exports use existing passport endpoints and digest verification; an unpublished report says report not published. Missing rover remains NOT_ASSESSED/NOT_RUN as appropriate. LIMITED, failed, unknown, blocked and synthetic labels remain visible.

## 5. Delivery sequence and compatibility

1. Both branches begin at common handoff; write down its SHA in branch STATUS before further edits.
2. Aradhya proceeds using current APIs + mocked optional seams; Tanush prepares data/projections with isolated backend tests.
3. Tanush lands any small additive contract change separately via the architecture-35 materialization process. Never casually rewrite the kit for convenience. Aradhya regenerates the client only after that exact contract is integrated.
4. Tanush delivers versioned catalog and regional artifacts; frontend adapter changes only at the defined seam. Enable optional features only when both sides validate the same schema version. Unknown version ⇒ truthful fallback, no guessed parsing.
5. Merge both tested branches onto latest main in an isolated integration branch. The common seed is merged once. Run the full merged suite, browser journeys, mutation gates and real live drill-down inspection. main's previous 1,994/17/72 results do not certify new UI code.
6. Freeze changed source while final checks run. Compare merged tree to the tested tree; record commit, source hash, commands, counts, screenshots and open limitations. No destructive history edits or force push.

Aleph is a reviewed reference, not a runtime dependency. See the role-specific Aleph notes for permitted patterns and Earth-only boundaries. No Google scraping, extra terrain source, cloud purchase or billable automatic integration is required for either contributor to complete independently.
