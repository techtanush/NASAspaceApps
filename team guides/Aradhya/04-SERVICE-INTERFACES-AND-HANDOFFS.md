# Aradhya — interfaces and handoffs

All seams are frozen kit artifacts ([35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)). No mid-build hand-offs: you deliver a branch that works against the bundled OpenAPI, the mock backend and the renderer fixtures; the merging agent connects it to the real backend.

## You consume

| Artifact | How |
| --- | --- |
| `contracts/openapi.bundled.json` | Generate `apps/web/src/generated/schema.d.ts`; validate mock fixtures against it |
| `contracts/ui-testids.json` | Implement every id; test coverage (UIX-04) |
| `contracts/algorithm-ids.json` | Discover UI-readable artifacts by `algorithm_id` ([35 §5b](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)) |
| `analogforge.ports.passport_renderer` (`PassportExportBundle`, `ProvidedAsset`, `RenderedExport`, `CSV_COLUMNS`, `RendererError`) | The renderer's input/output types |
| `analogforge.ports.science_payloads` (artifact JSON shapes), `domain_models`, `assurance_models` | Typing the artifacts and the bundle fixtures |
| `tests/fixtures/kit/**` | Missions/rovers/graph/blueprint fixtures for mock data and renderer bundles |
| Server (at merge): `/api/v1/**`, SSE, `/artifacts/{sha}`, exports | Same specs, real mode |

## You provide

| Entry point / artifact | Consumer | Contract |
| --- | --- | --- |
| `analogforge.rendering.passport:create_passport_renderer` → `PassportRenderer` | Tanush's export service | pure, deterministic; `render(bundle, assets, fmt)`; errors as `RendererError` |
| `apps/web` build (`pnpm run build`) | Compose/Make wrapper (Tanush) | static assets; dev server on `WEB_PORT`; API proxied to `API_PORT` |
| `tests/e2e/journeys/J01…J13` | merging agent | run with `E2E_TARGET=real`, `E2E_BASE_URL`, `E2E_API_URL`; mock-mode equivalents already green |
| `scripts/ui/verify_exports.py` | merging agent | given a downloaded html/json/csv and the displayed digests, performs the digest/canonical-manifest/CSV-header/HTML-purity checks of journey J01 step 14 |

## The export seam in detail

Tanush assembles the bundle and calls you; you never look anything up. The bundle guarantees (architecture 35 §4): references resolve, `manifest_sha256` matches `canonical_manifest_json`, attempts ordered and complete, assurance present for non-draft. You guarantee byte-determinism, escaping, completeness of rows/attempts/GAP/UNKNOWN, mode visibility, and that the file digest (`RenderedExport.sha256`) is **different from** the manifest digest. The frontend displays the **server's** `manifest_sha256` and `X-Artifact-SHA256`; it never hashes anything itself.

## Defects you find elsewhere

Record in `STATUS.json.defects_in_other_areas` with a reproduction (e.g. "the bundled spec lacks X"); never edit the kit or another owner's files. Kit blockers: `team handoffs/aradhya/CHANGE-REQUEST-<n>.json` plus a local workaround.

## Dependencies

JS dependencies in your `package.json`/lockfile (commit the lock). Python renderer dependencies only from the kit (`jinja2`, `markupsafe`, `pydantic`); extras via `extra-aradhya`. Never commit `uv.lock`.
