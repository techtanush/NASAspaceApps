# BETTERUI progress log

Read `UI-PLAN.md` first. This file says how far the build is and how to continue. Update it with every push.

## State at this commit
Build order step (plan Part D6): **steps 1–3 done in mock mode** (globe, shell, Welcome, Place, Mission, Rover, Review incl. requirement proposal). Run progress, Tour, Report, responsive pass, tests and e2e repointing are not started unless listed below.

| Piece | File(s) | State |
|---|---|---|
| Dependency `globe.gl` | `apps/web/package.json`, `pnpm-lock.yaml` | added (not yet listed in `src/app/thirdParty.ts`) |
| Globe textures | `apps/web/public/globe/*`, `scripts/ui/generate_planet_textures.py` | Earth + starfield real; Mars/Moon generated placeholders |
| Imagery manifest (plug-in point) | `src/maps/globeAssets.ts` | done |
| Globe component | `src/maps/GlobeStage.tsx` | works: body switch, fly-to, pin drop, area box, pulse ring, click-to-pick, layout offset, no-WebGL fallback. Tickers untested until the Tour exists. |
| State + scene controller | `src/features/missionControl/state.tsx` | done |
| Shell (header, panel, step rail, guide, choice) | `src/features/missionControl/StageShell.tsx` | done |
| Coordinates maths | `src/features/missionControl/coordinates.ts` | done, **no unit tests yet** |
| Named sites, coverage slot | `namedSites.ts`, `coverage.ts` | done (coverage returns UNKNOWN by design) |
| Welcome (`/`) | `Welcome.tsx` | done, reviewed at 1440×900 |
| Mission, Rover, Review steps | `MissionStep.tsx`, `RoverStep.tsx`, `ReviewStep.tsx`, `scenario.ts` | work in mock mode: create draft → propose requirements → review. `Accept and start` navigates to `/runs/:id/tour`, which does not exist yet |
| Tour logic (pure) | `tour.ts` | benchmark text, site status, coverage written; **no unit tests yet**; not yet used by a Tour screen |
| Place step (`/start/place`) | `PlaceStep.tsx` | works in mock mode (reviewed at 1440×900) |
| Styles | `src/styles/mission-control.css` | covers shell, welcome, place, rail, pin, tickers, mobile basics |
| Routing | `src/app/router.tsx`, `src/app/App.tsx` | stage routes added; old home moved to `/workbench` |

## Checks at this commit
typecheck pass · lint pass · unit tests 144 pass · `scripts/ui/forbidden_scan.py` PASS.
**Not yet done / expected to fail until fixed:** e2e specs and helpers that open `/` expecting the old workspace (`tests/e2e/support/workbench.ts`, `journeyChecks.ts`, `a11y.spec.ts`, `list-loading-presets.spec.ts`, `J01-golden.spec.ts`, `integration/merge-assertions.spec.ts`) must be repointed to `/workbench`; visual audit not extended; no tests for the new code.

## Next steps, in order
1. Add unit tests for `coordinates.ts`, `tour.ts`, `scenario.ts`.
2. Repoint the e2e entry paths to `/workbench`.
3. Verify the wizard against the real synthetic backend (custom target box acceptance, plan F4).
4. `useRunData`, Run progress, Tour, site card, coverage strip, narrator (B6–B7).
5. Report page (B8). 6. Responsive/a11y/motion pass. 7. Tests and audits (Part E). 8. Add `globe.gl`/three.js to `thirdParty.ts`.

## How to run
```bash
cd analogforge && corepack pnpm install --frozen-lockfile
cd apps/web && VITE_API_MOCK=1 WEB_PORT=5300 corepack pnpm exec vite --host 127.0.0.1
```
Open `/` and `/start/place`. For headless screenshots launch Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`.
