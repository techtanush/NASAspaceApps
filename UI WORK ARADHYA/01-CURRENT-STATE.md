# Starting inventory — verified 14 November 2026

Base main: `1721844`; BETTERUI tip: `fc5e084`. All five BETTERUI commits are inherited, not cherry-picked fragments: b1f6013 plan; 9c44946 globe/shell/welcome/place; 95fef4b mission/rover/review and pin fix; ac859c2 progress/tour; fc5e084 corrected progress note.

## Existing files and honest status

| Implementation | Status / what remains |
|---|---|
| `src/maps/GlobeStage.tsx` | Dynamic globe.gl wrapper, body textures, focus, markers/rings/area, resize and fallback exist. Final interaction, unmount/context loss, selection and reduced-motion tests still needed. Globe camera minDistance limits deep zoom; a global texture is not regional detail. |
| `src/maps/globeAssets.ts` | Earth Blue Marble/starfield present; Mars/Moon are labelled generated placeholders. Loader for Tanush's versioned catalog not implemented. |
| `features/missionControl/state.tsx`, `StageShell.tsx` | Wizard/context/panel/rail/scene exist. Deep-link, back/edit invalidation, route changes and reload recovery need verification. |
| `Welcome.tsx`, `PlaceStep.tsx`, `MissionStep.tsx` | Initial screens exist. Coverage intentionally UNKNOWN. Area sizes are visual choices, not proof of scenario/data eligibility. |
| `RoverStep.tsx` | Saved rover cards, JSON import and no-rover exist. Full create form is not implemented here; library link currently leaves wizard shell and can lose state. |
| `ReviewStep.tsx`, `scenario.ts` | Create/propose/poll/accept/start flow exists. Async disposal, retry/idempotency, stale prepared contract and explicit mode/data eligibility need work. No implicit paid/live switch hidden from user. |
| `useRunData.ts` | Snapshot/stream/pinned candidate/qualification and results reads exist. Loading/error/stale/run-switch completeness needs tests. |
| `TourView.tsx`, `tour.ts`, `narrator.ts` | Tour and progress written; Claude inspected tour top half in mock mode. Site map, bottom card, actions, dispersed sites and real backend unverified. No source-specific regional terrain drill-down yet. |
| `ReportPage.tsx` and report route | ABSENT. Current Open report link reaches not-found. |
| `src/styles/mission-control.css`, router/App | New stage chrome and /workbench route exist. Mobile, print, a11y and visual audit not completed. |
| Third-party register | globe.gl added to package/lock but not yet recorded fully in application notices. |

## Direct code findings to resolve

- `tour.ts/buildSites` silently re-sorts the pinned candidate list. Preserve authoritative screening order; label any optional user sort explicitly.
- Tour header currently lacks the required scientific assurance badge. Never manufacture one while publication/review is pending.
- `TourView` renders every run test result under the selected card. Join results to candidate/test/attempt ancestry or show a run-level section clearly separated from the site.
- Prove link launches asynchronous selection and navigates immediately; it does not await a confirmed current revision. Make selection/action flow sequential and honor actual allowed_actions. Do not imply a test ran because a link opened.
- Progress logic treats an unrecognized phase (`current === -1`) as all steps done. Map every state explicitly; terminal/blocked/failed states remain honest even if some candidates already exist.
- `ReviewStep` sets an `alive` ref but never clears it on disposal; prepared/accepted state can outlive changed inputs. Use abort/cleanup and bind proposal state to the exact input snapshot/revision.
- Rover cards stringify unknown numeric values; null must render Unknown, not `null` with units. Library/create navigation must preserve or explicitly warn about the unsaved wizard.
- The local SVG site arrangement is useful but is not a real basemap, detailed imagery, or validated distance measurement. Keep the accessible site list and add a genuine regional data viewport.
- Guide is too verbose with long labels; concise summary plus expandable exact rows, no lost uncertainty.

These are observed implementation risks, not a declaration that all are reproduced bugs. Add focused tests and inspect live behavior before deciding the precise fix. Do not rewrite unrelated stable modules.

## Fresh handoff checks

On the inherited BETTERUI code, before any new implementation: frozen-lock dependency installation PASS; TypeScript PASS; ESLint PASS; existing Vitest suite 144/144 PASS; UI forbidden scan PASS, zero findings. New Mission Control code has no dedicated coverage yet. No new browser journeys, production build, responsive audit, real-backend UI run or merged full suite was executed for this handoff. The previous main's 1,994 tests/17 journeys/72 mutation checks are historical evidence for main, NOT this unfinished UI.
