# Aradhya scope and file ownership

Own the user-facing workbench and its truthful presentation of server evidence. Your interface consumes generated contracts; it does not become a second scientific engine or another database.

## Owned paths

- `analogforge/apps/web/`: React19/TypeScript/Vite app, routes/components/query state/forms/maps/style/assets/client, frontend tests and visible mock preview.
- `analogforge/package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`: single owner for frontend dependency/scripts/lock. Python/native locks remain Tanush's.
- `analogforge/src/analogforge/rendering/passport/`: pure renderer for supplied frozen passport bundle, HTML/JSON/CSV bytes, escaping/print layout/digests.
- `analogforge/tests/unit/passport_renderer/`, `tests/e2e/`: renderer correctness and real/mock-separated full browser/accessibility journeys.

Shared package root initializers and API/ports/models/settings/Compose/migrations/science/tiles paths belong to other owners. Do not write them to make frontend tests pass. The ownership registry overrides broad path guesses. If the API is missing an endpoint/field, report exact expected shape and source requirement rather than making up a private production endpoint.

## Functional coverage

Workspace recent missions/runs; mission draft autosave; target selection for both planetary bodies; manual/JSON rover editor and optional no-rover mode; Mission Fingerprint/preparation/acceptance; target/candidate map+table; qualification/evidence/confidence; agent operations/receipts/critic issues; compatibility; PROVE_IT/test lab/attempt history/replans; portfolio assignments/residual gaps; immutable passport and downloadable exports.

Every screen must handle loading, empty/pending, blocked/error, conflict, unknown/gap/fail, cancellation and resume. Every advertised button invokes a real endpoint/committed action or explains its unavailable prerequisite. No decorative dummy tabs presented as full implementation.

## Data ownership

Tanush's exported OpenAPI generates your TypeScript client/types. Import status enums and input models, do not redefine them by hand. TanStack Query owns server cache; route/query parameters own shareable selection; local state owns unsaved edits/view preferences. No duplicated authoritative run state in localStorage. Scientific mutations are acknowledged by server and snapshot/events, not optimistic green badges.

Use revision guards/idempotency/CSRF policy. SSE displays committed operations, with run-local seq dedup, gap/expiry/reconnect resync and terminal close. Selection state comes from selected_candidate_id/selected_portfolio_id, not an old component variable after reload.

## Maps and display

Use MapLibre for Earth. Planetary target uses a separate body-aware planar image/selection panel and metadata; do not render Mars coordinates on an Earth map. Read registered DisplayLayerManifest/image/route artifacts from the backend. Ayan supplies geometry/affine/units/legend/masks. Do not decode PDS/NetCDF or calculate terrain/energy in browser. Neutral local Earth background needs no paid map key; optional vendor tiles must retain license/attribution.

## Passport renderer boundary

Tanush supplies immutable accepted inputs/evidence/attempts/manifest and validated image bytes. Your pure Python renderer has no database, model, source fetch or secret access. It returns escaped self-contained printable HTML, scientific JSON snapshot and safely flattened CSV plus correct MIME/safe filename/file hash/renderer version. Manifest digest and file-byte digest remain distinct. Frontend preview uses the same report semantics and server data.

## Not your scope

Do not implement a competing FastAPI backend or hidden client-side qualification engine. Do not force success by hiding negative rows, scripts or labels. Do not buy/publish hosting or send communications. Do not change public API/mission/rover scientific semantics or hardcode live model/source results. A mock preview is useful development infrastructure, not a live product integration.
