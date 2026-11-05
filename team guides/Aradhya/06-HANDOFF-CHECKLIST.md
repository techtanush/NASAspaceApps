# Aradhya — definition of done (checklist)

Tick only with observed evidence recorded in `STATUS.json`.

- [ ] Correct branch/clone; kit materialized and `--verify` PASS at start and end; `tests/contracts/kit` green.
- [ ] Only owned paths changed (ownership checker PASS); `extra-aradhya` the only `pyproject.toml` edit; no `uv.lock`; no build output committed.
- [ ] Client generated from `contracts/openapi.bundled.json`; no handwritten API/enum types; regeneration produces no diff.
- [ ] Every `data-testid` of `contracts/ui-testids.json` implemented with required attributes and asserted by Playwright.
- [ ] S01–S12 implemented with all loading/empty/error/pending/unknown/gap/fail/inconclusive/blocked/cancelled states; null renders `Unknown`; GAP/UNKNOWN/PENDING/FAIL distinct with text+icon.
- [ ] Planetary panel is body-aware and separate from the Earth map; affine tests pass; offline basemap; WebGL-failure fallback works.
- [ ] Mutations are idempotent/revision-guarded; SSE controller dedups/resyncs/handles 410/terminal/unmount; reload restores state from the server.
- [ ] No scientific computation, no optimistic scientific updates, no similarity percentages, no hidden failed/unknown rows.
- [ ] Mock backend implements all 43 operations, fixtures validate against the bundled OpenAPI, storylines of architecture 40 replayed, banner visible, impossible in production builds; mock exports are **real renderer output**.
- [ ] Renderer: html/json/csv deterministic, escaped, complete (every requirement/attempt/GAP/UNKNOWN), correct headline logic, exact CSV columns, canonical-manifest digest reproduces, pure (subprocess import test), `RendererError` codes, 9 fixtures.
- [ ] Journeys J01–J13 pass in mock mode (0 skipped) and contain the real-mode assertions behind `isMock()`.
- [ ] axe 0 critical/serious at 1440/900/390; keyboard-only path; 200 % zoom; reduced motion.
- [ ] No `eval`/`dangerouslySetInnerHTML`/`localStorage` run state/external requests/secrets; no `TODO`/`FIXME`/`HACK`; no weakened/skipped tests; mutation checks demonstrate tests can fail.
- [ ] `STATUS.json` complete and truthful; contradictions and cross-area defects listed; committed; pushed to `origin aradhya/frontend-experience`.

Push at every phase gate, but the branch is only mergeable at the end.
