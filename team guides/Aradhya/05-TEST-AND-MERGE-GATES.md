# Aradhya browser renderer and merge gates

Demonstrate working user flows and truthful data, not only a successful frontend compilation. Keep mock-preview tests separate from real backend/science integration. An empty UI, hidden failed row or hardcoded second pass cannot satisfy acceptance.

## Tooling and contracts

TypeScript strict checking, generated-client freshness, frontend test suite and production build pass from committed pnpm lock. No duplicate scientific enums or manual edits to generated client. Actual request bodies, null behavior, errors, state/action guards and selection restoration match accepted OpenAPI. Report schema hash/base SHA.

## Component and interaction suite

Test draft autosave saving/saved/failure/conflict and reload; manual/import rover round trip and exact field errors; Mission Fingerprint proposed defaults and explicit acceptance; no-rover mode; all five qualification statuses and confidence text; pending versus unknown; evidence drawer actual references; critic/review/blocked actions; all three verification outcomes; immutable attempt history; portfolio residual/co-location; passport/export error and polling.

Inputs preserve user text on failed validation. A review cannot hide a scientific blocker. A first PROVE_IT button cannot display a computed route before backend artifact commit. Candidate selection and status changes require server acknowledgment. Missing provider/source capabilities show exact remediation without asking for a secret in a browser form.

## Event and recovery tests

Repeated seq is deduplicated, missing seq triggers authoritative snapshot,410 cursor expiry resyncs, disconnect/reconnect does not duplicate a user command, terminal event closes stream, component unmount removes listeners. Reload restores selected_candidate_id/selected_portfolio_id and current attempts/qualification versions. No optimistic green qualification or fake private reasoning timeline.

## Maps and responsive accessibility

At1440px,900px and390px verify readable layout with no required row/action hidden or clipped. Keyboard focus order, form labels, status text/icons, dialog/drawer focus management and route/table alternatives work. No status is color-only. A WebGL failure leaves complete candidate/qualification/route information and actions.

Earth images use supplied corners/legend/units/attribution/transparency. Planetary target displays body-specific planar affine/CRS, not Earth map labels/tiles. Bad/missing manifest produces a visible unavailable layer, not guessed projection. Route is labeled modeled terrain feasibility; imagery smoothing cannot alter route or create claimed measurement detail.

## Renderer security and integrity

Pure renderer runs without DB/model/network. Positive, limited, failed, inconclusive, no-rover and composite fixtures preserve exact accepted inputs/evidence/attempts/unknowns. HTML escapes script/tag payloads, is self-contained and prints readably. CSV text formula injection is escaped while actual typed numeric values retain meaning. JSON contains scientific frozen snapshot, not DOM-derived summaries. No credential/signed URL/internal path/private reasoning in exports. Separate byte hash and manifest hash match their intended content.

## Real combined journey

With actual F0/platform and Ayan science installed, explicitly disable mock handlers and run: draft→preparation→accept→rover→run→candidate/matrix/critic→PROVE_IT→computed fail→real replan→verified result→passport/download→reload. Assert actual backend job/evidence/receipt IDs and unchanged contract/rover hashes. The graph regression values are expected synthetic test outputs, not mocked successful API responses.

Also exercise no-rover block, unknown clearance, missing geology/thermal, negative control, search INCONCLUSIVE, review, portfolio co-location, cancellation/reconnect and stale revision. Test at least one actual Moon and Mars body-specific response path. If live source/model is blocked, report it separately from the completed offline browser journey.

## Commands to supply and run

From `analogforge/`, implement root frontend scripts that delegate to `apps/web`:

```bash
rtk pnpm install --frozen-lockfile
rtk pnpm run generate:client
rtk pnpm run typecheck
rtk pnpm run test
rtk pnpm run build
rtk pnpm run test:e2e
rtk proxy uv run pytest tests/unit/passport_renderer
```

Document profile URL/mock flag/fixture seed for each browser test. Do not treat a missing script, skipped entire suite, unavailable browser or hidden mock server as a passing run. Use provided preview/browser tools when available; report actual verification limits otherwise and continue static/renderer checks.

## Ready to merge

Owned-path diff only, no secrets/bulk assets/runtime output, no test failures/client drift/unsupported state claims, reproducible mock and actual-API commands, test counts/screenshots where useful, asset provenance and known blockers. Submit exact tested commit SHA and base schema/main checkpoint. Tanush tests the final combined merge candidate; no hosting/publication happens automatically.
