# BETTERUI progress log

Read `UI-PLAN.md` first. This file says how far the build is and how to continue. Update it with every push.

## State at this commit
Read this with `UI-PLAN.md`. Plan Part D6 build order: **steps 1–3 work in mock mode; steps 4–5 (run progress, tour) are written but NOT yet visually verified; steps 6–8 not started.**

| Piece | File(s) under `analogforge/apps/web/` | State |
|---|---|---|
| Dependency `globe.gl` | `package.json`, `../../pnpm-lock.yaml` | added; **not yet listed in `src/app/thirdParty.ts`** |
| Textures | `public/globe/*`, `../../scripts/ui/generate_planet_textures.py` | Earth + starfield real; Mars/Moon generated placeholders |
| Imagery manifest (plug-in point) | `src/maps/globeAssets.ts` | done |
| Globe | `src/maps/GlobeStage.tsx` | verified: body switch, fly-to, pin drop, area box, pulse ring, click-to-pick, layout offset, fallback. Tickers written, unverified |
| State, shell, panel, step rail, guide | `src/features/missionControl/state.tsx`, `StageShell.tsx` | done |
| Welcome `/` | `Welcome.tsx` | done, reviewed at 1440×900 |
| Place `/start/place` | `PlaceStep.tsx`, `coordinates.ts`, `namedSites.ts`, `coverage.ts` | done, reviewed (Mars and Moon) |
| Mission, Rover, Review | `MissionStep.tsx`, `RoverStep.tsx`, `ReviewStep.tsx`, `scenario.ts` | verified in mock mode through requirement proposal; summary-collapse fix applied but not re-screenshotted |
| Run data hook | `useRunData.ts` | written, typechecks, unverified |
| Run progress + Tour `/runs/:id/tour` | `TourView.tsx`, `tour.ts`, `narrator.ts` | **written, typecheck + lint pass, never viewed in a browser.** Nearby sites share one globe ticker and a local SVG map in the panel |
| Report `/runs/:id/report` | — | **not started** (the tour's "Open report" link points to it and will 404) |
| Styles | `src/styles/mission-control.css` | covers all of the above; mobile only roughly |
| Routing | `src/app/router.tsx`, `src/app/App.tsx` | stage routes added; old home moved to `/workbench` |

## Checks at this commit
typecheck pass · lint pass. Unit tests (144) and `scripts/ui/forbidden_scan.py` passed at the previous commit and were **not re-run** after adding the tour files.
**Known failing / not done:** e2e specs and helpers that open `/` expecting the old workspace (`tests/e2e/support/workbench.ts`, `journeyChecks.ts`, `a11y.spec.ts`, `list-loading-presets.spec.ts`, `journeys/J01-golden.spec.ts`, `integration/merge-assertions.spec.ts`) must be repointed to `/workbench`; no tests exist for any new code; visual audit not extended; nothing tested against the real backend.

## Next steps, in order
1. Open the tour in mock mode (flow: `/start/place` → Gale → Confirm → example chip → Continue → pick a rover → Continue → Prepare requirements → Accept and start) and fix what is wrong in `TourView.tsx`. Check the "Prove it here" behaviour: it currently selects the site and links to the workbench test lab.
2. Re-run unit tests and `scripts/ui/forbidden_scan.py`; fix findings.
3. Build `ReportPage.tsx` (plan B8) and its route; make `App.tsx` render it without chrome.
4. Repoint the e2e entry paths to `/workbench`.
5. Unit tests for `coordinates.ts`, `tour.ts`, `scenario.ts`, `narrator.ts`; component tests with `vi.mock('globe.gl')`.
6. Verify against the real synthetic backend (custom target box acceptance, plan F4).
7. Responsive (390 px), accessibility and motion pass; add `globe.gl`/three.js to `thirdParty.ts`; extend the visual audit.
8. Write the backend merging guide from plan Part F.

## How to run
```bash
cd analogforge && corepack pnpm install --frozen-lockfile
cd apps/web && VITE_API_MOCK=1 WEB_PORT=5300 corepack pnpm exec vite --host 127.0.0.1
```
Open `/` and `/start/place`. For headless screenshots launch Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`.
