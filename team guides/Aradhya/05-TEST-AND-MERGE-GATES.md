# Aradhya — tests and merge gates

A gate passes only when its tests **execute and assert**. Skips, xfails, deselects and "no tests found" are failures. Catalog ids: architecture 39 §1.

## 1. Commands (from `analogforge/`; omit `rtk` if not installed)

```bash
python3 "../architecture files/contracts/kit/materialize.py" --verify                      # KIT-01
uv run pytest tests/contracts/kit -q                                                       # KIT-02
uv run pytest tests/unit/passport_renderer tests/contracts/ui -q --strict-markers          # UIX-08, UIX-09 + fixtures
uv run ruff check src/analogforge/rendering/passport tests/unit/passport_renderer tests/contracts/ui scripts/ui scripts/build_mock_exports.py
uv run mypy src/analogforge/rendering/passport                                             # strict
pnpm install --frozen-lockfile
pnpm run generate:client && git diff --exit-code apps/web/src/generated                    # UIX-02
pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run test:contracts && pnpm run build   # UIX-01/03/04/05/06/10
pnpm run test:e2e:mock                                                                      # journeys J01..J13 in mock mode
pnpm run a11y                                                                               # UIX-07
python3 scripts/ui/forbidden_scan.py --json out/forbidden.json && python3 scripts/ui/mutation_check.py --json out/mutations.json
python3 "../team coordination/scripts/check_branch_ownership.py" --person aradhya --repo ..   # PASS
```

`scripts/ui/forbidden_scan.py` additionally fails the gate if the JUnit/Playwright JSON report contains any skipped/fixme test among the journeys or UIX suites.

## 2. Required test files (names are part of the gate)

| File | Catalog | Must assert |
| --- | --- | --- |
| `apps/web/src/test/typecheck+build` (via scripts) | UIX-01 | strict TS clean, lint clean, production build succeeds |
| `apps/web/src/test/client-freshness` (script) | UIX-02 | regenerate from the bundled spec ⇒ no diff |
| `apps/web/src/test/msw-validate.test.ts` | UIX-03 | every mock response body for every operation/script validates against the bundled OpenAPI (ajv 2020-12) |
| `apps/web/src/test/testids.test.ts` + Playwright assertions | UIX-04 | every id of `ui-testids.json` occurs in `src` and is asserted by ≥ 1 Playwright test; required `data-*` attributes present on rendered elements |
| `apps/web/src/features/**/*.test.tsx` | UIX-05 | FE-001…FE-014 (architecture 17 §10) and UX-001…UX-012 (16 §7): immutability of accepted inputs, null⇒Unknown (never 0), distinct GAP/UNKNOWN/PENDING/FAIL, no optimistic science, same-key retry, revision-conflict flow, invalid import never persists, no color-only status, mode badge persistence, route playback only over committed data, three distinct result view models, recoverable error states, workspace isolation of caches |
| `apps/web/src/api/runStream.test.ts` | UIX-06 | duplicate ignored, gap ⇒ resync, 410 ⇒ resync, backoff schedule, heartbeat not an event, terminal close, unmount cleanup, run switch isolation |
| `apps/web/src/maps/affine.test.ts` | SCN-17 consumer | four corners + interior point round-trip ≤ 0.5 px for north-up and rotated transforms; Earth corner order NW,NE,SE,SW; layer registry rejects body/CRS mismatches |
| `analogforge/tests/unit/passport_renderer/test_determinism.py` | UIX-08 | same bundle ⇒ identical bytes for all 9 fixtures × 3 formats |
| `…/test_html.py` | UIX-08/09 | headline logic (4 cases), every requirement row/attempt/GAP/UNKNOWN present, mode text, manifest digest, assurance statements, no `<script`, no external `src=`/`href=`/`url(`, draft banner, `Unknown` for nulls |
| `…/test_escaping.py` | UIX-08 | hostile strings never become executable HTML; CSV formula prefixes neutralized; JSON round-trips originals |
| `…/test_csv.py` | UIX-08 | exact `CSV_COLUMNS`, one row per candidate×requirement, metric mapping of `08` §7, empty (never 0) when absent, delimiter ` | `, rectangular |
| `…/test_json.py` | UIX-08 | structure of architecture 35 §4; `sha256(rfc8785(canonical_manifest)) == manifest_sha256` using `analogforge.ports.hashing` **and** an independent `rfc8785` call |
| `…/test_errors.py` | UIX-08 | each `RendererError` code for its crafted inconsistent bundle; BLOCKED audit; digest mismatch; draft never raises |
| `…/test_purity.py` | UIX-09 | subprocess import shows none of `socket, http.client, urllib.request, requests, httpx, sqlalchemy, psycopg, openai, fastapi`; no file writes; no env reads |
| `tests/contracts/ui/test_openapi_fixtures.py` | UIX-03 | mock fixtures (exported to JSON by the web test) validate with Python `jsonschema` too |
| `tests/contracts/ui/test_bundle_fixtures.py` | UIX-08 | all bundle fixtures validate as `PassportExportBundle`; `contracts/algorithm-ids.json` equals `analogforge.ports.catalog.ALGORITHM_IDS` |
| `tests/e2e/journeys/J01…J13*.spec.ts` | UIX-04/05/07/10/11 | the click scripts of architecture 39 §3, exactly, in mock mode (mock banner present) |
| `tests/e2e/a11y.spec.ts` | UIX-07 | axe: 0 critical/serious on S01–S12 at 1440/900/390; keyboard path; 200 % zoom; reduced motion |
| `tests/e2e/webgl-fallback.spec.ts` | UIX-11 | with WebGL disabled the candidate list, matrix, route table and exports still work |
| `tests/e2e/prod-build-guard.test` | UIX-10 | build with `VITE_API_MOCK=1 NODE_ENV=production` fails; real build has no `msw` in the bundle |

## 3. Frozen thresholds

Journey step timeouts: preparation 60 s, run to `AWAITING_REVIEW` 180 s (mock: ≤ 10 s), PROVE IT sequence 240 s (mock ≤ 15 s). axe: 0 critical/serious. Affine tolerance 0.5 px. Renderer: byte-identical across 3 repeated renders in separate processes (`PYTHONHASHSEED` 1/2/3).

## 4. Merge readiness

`STATUS.json.ready_to_merge = true` only if: every UIX row `PASSED`; J01–J13 pass in mock mode with **0 skipped**; kit verify and ownership `PASS`; all linters/typecheck clean; forbidden/mutation checks clean; the self-audit complete. Real-backend execution of the journeys is **not possible in your environment** and is listed `BLOCKED_ENVIRONMENT` for `MRG-03` only (it belongs to the merging agent); your specs must already contain the real-mode assertions (guarded by `isMock()`).
