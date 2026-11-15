# AnalogForge "Mission Control" — final UI plan and backend plug-in list

Audience: any coding agent implementing the frontend, and the backend owner (Codex) who plugs data in afterwards.
Repo: `techtanush/NASAspaceApps`, app in `analogforge/apps/web` (React 19 + Vite + TypeScript, TanStack Query, React Router 7, MapLibre). Base: `main` at `1721844`.

Part A is the product vision. Part B is the screen-by-screen specification. Part C is the visual system. Part D is the technical build. Part E is verification. **Part F is what the backend and data must supply afterwards so nothing on screen is a placeholder.**

---

# Part A — Vision

**One sentence:** a mission planner drops a pin on a globe of Mars or the Moon, describes the mission and the rover, and is then flown around the Earth to the sites where that mission can be rehearsed — each site stating which capability it tests and the benchmark the rover must meet there.

**Why this wins:** every competing project will show a table of analog sites. This one makes the answer spatial and obvious in ten seconds, and still exposes the rigorous evidence underneath.

**The product truth the UI must carry**
- No single Earth place matches everything. The result is a *set* of places, each responsible for specific capabilities.
- Each place carries a **benchmark**: the measurable thing the rover must do there.
- Each place also states what it **cannot** show (gravity, atmosphere, thermal…). Uncovered capabilities are shown as gaps.
- Failing sites, UNKNOWN, GAP, LIMITED assurance, "no rover supplied", synthetic/live mode and placeholder imagery are always labelled. The UI never invents a number.

**Experience principles**
1. *Orientation first* — the user always knows where they are, what is done, what is next, and what the system is doing.
2. *One decision per screen.* Evidence tables are one click away, never the headline.
3. *The globe is the stage.* Motion always explains something (a place, a transition, progress). No decoration for its own sake.
4. *Parity.* Everything doable on the globe is doable from the panel by keyboard; without WebGL the flow still completes.
5. *Calm, not busy.* One accent colour, generous spacing, few words.

**Flow**
`Welcome → 1 Place → 2 Mission → 3 Rover → 4 Review & lock → Run (progress) → Tour of Earth sites → Report (new tab)`; the existing eight-tab workbench remains as "Evidence workbench" for experts.

---

# Part B — Screen specifications

## B0. Global layout (all stage screens)
- Full-viewport **stage**: the 3-D globe on a starfield, always mounted; it persists between steps so transitions are continuous camera moves.
- **Top bar** (transparent, 64 px): wordmark left; right links "Evidence workbench", "Rovers", "About". Mock banner above it when in mock mode.
- **Panel** (right, 420 px wide, 24 px from the right edge, 72 px from top and bottom, glass surface, 12 px radius via the existing `.panel` glass class): header (eyebrow "STEP n OF 4", title, one-line lead), scrollable body, sticky footer with a one-line summary left and the primary button right.
- **Step rail** (bottom-left, 36 px from bottom): `1 Place — 2 Mission — 3 Rover — 4 Review — 5 Earth sites`; done = accent with a check, current = filled accent, next = muted; done steps are links.
- **Imagery credit** bottom-left under the rail area: attribution text; amber when the surface is a placeholder.
- **Globe offset:** the globe is shifted left by half the panel width so it is centred in the free area; on Welcome it sits right of centre (20% of width).
- Responsive: ≤900 px panel 360 px; ≤767 px the globe occupies the top ~42% (offset up) and the panel becomes a bottom sheet (58% height), rail collapses to numbered dots under the top bar.

## B1. Welcome — route `/`
- Globe: Earth, slow auto-rotation, altitude 2.3.
- Left column (max 560 px, vertically centred): eyebrow "MISSION-CONDITIONED ANALOG QUALIFICATION"; H1 "Find where on Earth to rehearse a mission to Mars or the Moon." (30–46 px, weight 600, tight tracking); lead paragraph (16 px, secondary colour, ≤52 characters per line); primary button **"Begin a new investigation →"** (48 px high) → `/start/place`.
- Four-cell "how it works" grid (2×2, hairline dividers): Pick the place / Describe the mission / Add the rover / Tour Earth sites, each with an icon and one sentence.
- "Continue an investigation": up to four recent runs (short id, state in sentence case, mode badge) linking to `/runs/:id/tour`. Hidden when there are none (first-run state has no empty tables).
- Footer line: "Not a NASA product; no endorsement implied. Results are modeled terrain evidence, not field validation."
- No login screen (the app runs in local-auth mode). If OIDC sign-in is later required, it is a screen *before* this one; do not fake it.

## B2. Step 1, Place — `/start/place`
Purpose: choose the body and the area of interest.
- **Target body** segmented control: Mars | Moon. Switching swaps the globe surface, atmosphere colour and clears the pin.
- **Known sites** (2-column cards, name + note). Mars: Gale Crater (−4.8, 137.4), Jezero Crater (18.38, 77.58), Valles Marineris (−13.9, −59.2), Olympus Mons flank (18.65, −133.8). Moon: South polar region near Shackleton (−88.5, 0), Mare Tranquillitatis (0.674, 23.473), Tycho (−43.3, −11.2). These are navigation shortcuts with approximate centres.
- **Latitude / Longitude** inputs. Convention is fixed and stated under the fields: planetocentric latitude, north positive; longitude east positive; −180…180 stored, 0…360 accepted and converted. A mono readout shows both forms, e.g. `4.800° S, 137.400° E · 137.400° E (0–360)`.
- **Click the globe** sets the same fields.
- **Area to analyse**: 10 / 20 / 40 / 80 km (default 40). The app analyses areas, so the pin becomes a square box drawn on the globe.
- **On setting a place:** camera flies to it (1.5 s), a pulse ring radiates from the point, the pin drops (450 ms), the box outline appears.
- Validation, inline: latitude outside ±90; longitude outside −180…360; box crossing a pole; box crossing ±180°.
- **Coverage chip** (terrain data availability): Data available / Partial / None / "Not yet known — checked when the investigation starts". Until the backend supplies coverage (Part F3) only the last state is shown.
- Footer: summary "Mars · 4.800° S, 137.400° E · 40 km area"; primary **Confirm location →** (disabled with reason until valid).
- Guide line: before a pin "Start by choosing where on Mars the rover will operate."; after "Pin set on Mars. Adjust the area if needed, then confirm."

## B3. Step 2, Mission — `/start/mission`
- Fields: **Mission name** (prefilled, e.g. "Gale Crater mobility rehearsal"); **What must the rover achieve?** large text area with three example chips that insert text ("Climb 12–18° slopes for 100 m and return with at least 20% battery", "Reach two sampling points and return", "Qualify the terrain only").
- Explanation block: "AnalogForge turns this into measurable requirements. You review every requirement before anything is locked."
- Globe keeps the pinned target, no rotation. Footer: Back, **Continue →** (requires name and objective).
- Not in v1: file attachments (no backend field). Show nothing for it — do not add a dead upload control.

## B4. Step 3, Rover — `/start/rover`
- Saved rovers as selectable cards: name, revision, and a spec grid with units (mass kg, max slope °, clearance m, wheel Ø m, battery Wh, min reserve %, speed m/s; optional obstacle height, max route).
- **Add a rover**: form with the same fields and units, plus **Import JSON** (reuse the existing import validation in `features/rovers`). Saving creates a rover revision through the existing API.
- **Energy model** block on each card: badge `Assumed` (amber) or `Calibrated` (green); if absent: "No energy model — route results will be inconclusive."
- **"No rover — qualify the site only"** is a first-class card. Selecting it explains that route benchmarks will not be run.
- Footer: Back, **Continue →**.

## B5. Step 4, Review and lock — `/start/review`
- Summary: three rows (Place, Mission, Rover) each with an Edit link.
- **Prepare requirements** button → creates the mission draft, starts the requirement-proposal job, shows its real progress step text.
- Then **Proposed requirements** as readable cards: label, rule in words ("Slope-distribution distance ≤ 5°, compared at 500 m"), origin chip (`Supplied by you` / `Derived from target` / `Proposed default`), mandatory flag.
- Notice: "Accepting locks this test. It cannot be changed afterwards; a change creates a new revision."
- Footer: **Accept and start investigation** → accepts the revision, starts the run, navigates to `/runs/:id/tour`.
- Errors use the existing error panel with retry; a failed/blocked proposal job is shown as such.

## B6. Run in progress — `/runs/:id/tour` while the run is not yet reviewable
- Globe on the target body, focused on the pin, a slow scanning sweep ring; no rotation.
- Panel title "Working on your investigation"; an ordered progress list driven by run state, current item animated, done items checked:
  1. Checking inputs (`VALIDATING`) 2. Measuring the target terrain (`CHARACTERIZING`) 3. Screening Earth areas (`DISCOVERING`) 4. Checking each requirement (`QUALIFYING`) 5. Independent review (`CRITIQUING`) → ready.
  During proving: Designing the test (`DESIGNING_TEST`), Verifying the route (`VERIFYING`), Diagnosing / Re-planning, Building the report (`BUILDING_PASSPORT`).
- Latest event summary line under the list; mode badge; Cancel run (secondary). `BLOCKED`, `FAILED`, `CANCELLED` each have a designed state with the reason and next action.

## B7. Tour of Earth sites — `/runs/:id/tour` once candidates exist
- Globe switches to **Earth** (cross-fade), pulls back to show all sites, then flies to the best one.
- **Tickers** on the globe: numbered badge coloured by status (pass green, partial amber, fail red, gap violet, unknown grey); the selected ticker expands to show the site name and gets a pulse ring. Clicking a ticker selects it.
- **Tour controls** (panel header): `‹ Previous` `2 of 4` `Next ›`, an "All sites" button (pulls the camera back), and a list toggle (keyboard-equivalent list of sites).
- **Coverage strip** (top of panel body): one chip per requirement/capability → the site number(s) that cover it, or "No Earth site" for gaps (gravity, atmosphere are always gaps).
- **Site card** for the selected site:
  - Name, coordinates, origin chip (Discovered / Known control / Nominated / Synthetic practice), overall status with word + glyph.
  - **Capabilities tested here** — for each requirement: status badge, the **benchmark** ("must be ≤ 5° at 500 m support"), measured value and margin when available, origin of the threshold.
  - **What this site cannot show** — limitations and gaps in plain words.
  - If a rover exists: **Prove it here** (runs the modeled route test; result shows attempts, pass/fail, failure category) — else "No rover supplied; route benchmark not run."
  - **Open report** (new tab) and **View evidence** (opens the workbench at this site).
- Failing sites stay in the tour labelled "Does not match", with the failing requirement.
- **Guide** narrates each stop from structured fields only, e.g. "Site 2 of 4. Matches the target's slope distribution (3.68° against a 5° limit at 500 m). It cannot reproduce Mars gravity or atmosphere."
- Assurance badge (e.g. LIMITED) and mode badge are always visible in the panel header.

## B8. Report — `/runs/:id/report?site=<candidateId>` (new tab)
- Light, print-first page (A4/Letter), no globe: header (mission name, target place, rover or "site only", mode, assurance), the site's benchmarks table, qualification rows with evidence ids, limitations, provenance (contract digest, dataset lock, manifest digest), attribution, generated time.
- **Save as PDF** button (browser print). Links to the full passport exports (HTML/JSON/CSV) that already exist.

## B9. Evidence workbench — `/workbench` and existing `/runs/:id/<tab>` routes
- The current application unchanged; only its home moves from `/` to `/workbench`.

## B10. States required on every screen
Loading skeleton shaped like the final layout; empty; error with retry; offline/reconnecting; blocked dependency; run failed/cancelled; no rover; LIMITED assurance; live/synthetic/replay badge; placeholder-imagery label; no-WebGL fallback message ("The 3-D globe is not available in this browser. Use the coordinate fields and site list.").

---

# Part C — Visual system

- **Mood:** deep space, quiet, precise. Dark stage in both themes (the stage root sets `data-theme="dark"`); the report page is light.
- **Colour:** existing tokens only. Accent `--accent` (blue) is the single brand colour; status colours only for status. No new palette.
- **Globe:** Earth atmosphere halo blue (altitude 0.17), Mars amber (0.09), Moon none; graticule lines on; starfield background; accent-coloured area box and pulse rings.
- **Surfaces:** panel = existing glass `.panel`; cards inside the panel = solid tinted surfaces with 1 px hairlines, radius ≤ 6 px; tickers = solid `surface-1` with a strong border.
- **Type:** Inter for text, IBM Plex Mono for coordinates, ids, eyebrows (12 px, uppercase, 0.14 em tracking). Panel title 22 px; hero title 30–46 px; body 14 px; helper 12–13 px.
- **Spacing:** 4-px grid; panel padding 24; field gap 18; card padding 10–16.
- **Motion:** fly-to 1.5 s; pin drop 450 ms; panel entrance 320 ms slide/fade; hero 500 ms rise; hover 100–160 ms; ring pulse 1.5 s. `prefers-reduced-motion`: no rotation, instant camera, no rings, no entrance animation.
- **Copy voice:** short, plain, specific; sentence case; never "AI"; numbers always with units.
- **Hard rules (enforced by `scripts/ui/forbidden_scan.py` and design standard doc 41):** no hex/rgb colours outside `src/maps/` and tokens; no CSS gradients, text-shadow or backdrop-filter outside `glass.css`; radius ≤ 6 px outside `glass.css`; no external URLs; no emoji; no `localStorage` for domain state; no `fetch` outside `src/api`; no `Math.random`/`Date.now` in display code; no banned libraries (framer-motion, gsap, lottie, MUI…).

---

# Part D — Technical build

## D1. Dependencies and assets
- Add `globe.gl@2.46.2` (MIT; brings three.js). Record in `src/app/thirdParty.ts`. It must be **dynamically imported** inside the globe component so it is a separate chunk.
- `public/globe/`: `earth-blue-marble.jpg` and `starfield.png` copied from the `three-globe` package (MIT; Earth image is NASA Blue Marble); `mars-placeholder.jpg`, `mars-relief.jpg`, `moon-placeholder.jpg`, `moon-relief.jpg` produced by `scripts/ui/generate_planet_textures.py` (deterministic, 2048×1024, labelled placeholders).
- **Single plug-in file for imagery:** `src/maps/globeAssets.ts` — per body: `surface`, `relief`, `placeholder`, `attribution`, `atmosphere`, `radiusKm`, `label`.

## D2. Files
```
src/maps/globeAssets.ts          imagery manifest (plug-in point)
src/maps/GlobeStage.tsx          globe wrapper: scene in, picks/selections out
src/features/missionControl/
  state.tsx                      wizard state + scene controller (React context)
  StageShell.tsx                 layout route: globe, header, step rail; Panel, Guide, Choice, useScene
  coordinates.ts                 parse, normalise, area box, formatting (pure)
  namedSites.ts                  shortcuts and area sizes
  coverage.ts                    useCoverage() (plug-in point, returns UNKNOWN today)
  Welcome.tsx PlaceStep.tsx MissionStep.tsx RoverStep.tsx ReviewStep.tsx
  useRunData.ts                  snapshot + stream + contract + candidates + qualifications + results + action()
  RunProgress.tsx TourView.tsx SiteCard.tsx CoverageStrip.tsx
  tour.ts                        pure: site ordering, per-site status, coverage, benchmark text
  narrator.ts                    pure: guide sentences from structured fields
  ReportPage.tsx
src/styles/mission-control.css   all new styles (`mc-` prefix)
```

## D3. GlobeStage contract
```ts
interface GlobeScene {
  body: 'EARTH'|'MARS'|'MOON';
  focus?: {lat:number; lng:number; altitude?:number} | null;   // camera target
  pin?: {lat:number; lng:number} | null;                        // dropped pin + rings
  box?: [west,south,east,north] | null;                         // area outline
  markers?: {id; lat; lng; label; status?; index?}[];           // tour tickers
  selectedMarker?: string | null;
  autoRotate?: boolean; layout?: 'hero'|'panel'|'center'; scanning?: boolean;
}
<GlobeStage scene onPick={(lat,lng)=>…} onMarkerSelect={(id)=>…}/>
```
Implementation notes: `new Globe(el,{animateIn:false})`; `backgroundImageUrl(starfield)`, `showGraticules(true)`, `globeImageUrl/bumpImageUrl` per body, `atmosphereColor/Altitude`, `pointOfView(…, 1500)`, `htmlElementsData` for pin and tickers (DOM built with `createElement`, never `innerHTML`), `ringsData` for pulses, `pathsData` for the box, `onGlobeClick` for picking, `globeOffset([x,y])` for layout, `controls().autoRotate`. ResizeObserver keeps size. WebGL check first; on failure render the fallback. Tickers are `aria-hidden` (the panel list is the accessible equivalent). Root exposes `data-testid="globe-stage" data-body data-state`.

## D4. Routing and shell
- `app/router.tsx`: a layout route with `<StageShell/>` for `/`, `/start/place|mission|rover|review`, `/runs/:runId/tour`; `/runs/:runId/report` standalone; `/workbench` → existing `Workspace`. All other routes unchanged.
- `app/App.tsx`: for stage routes render only skip-link + mock banner + `<main>` (no sidebar/header/footer); workbench chrome otherwise; the sidebar "Missions and runs" link points to `/workbench`.
- Update the e2e helpers and the five specs that `goto('/')` expecting the workspace to use `/workbench`.

## D5. Data flow (existing API only)
- Welcome: `GET /runs?limit=4`.
- Review: `POST /missions` (draft: name, objective, target `{body, bbox, longitude_convention:'NEG180_180', latitude_type:'PLANETOCENTRIC', crs_wkt:null, vertical_datum:'Unknown'}`) → `POST /missions/{id}/fingerprint {expected_revision, mode, rover_revision_id}` → poll `GET /jobs/{id}` → `GET /mission-revisions/{proposed_revision_id}` → `POST /missions/{id}/accept` → `POST /runs {mission_revision_id, rover_revision_id, mode, dataset_lock_id, scenario_config_id}`.
- Scenario/mode: from `GET /capabilities` and `GET /configuration/scenarios/{id}`; pick the scenario whose `body` matches and whose `allowed_modes` is non-empty; prefer `live` when available, else `synthetic`; show the mode badge.
- Rover: `GET /rovers` (paged helper exists), `POST /rovers`, `POST /rovers/{id}/revisions`.
- Tour: `GET /runs/{id}` + event stream (`useRunStream`), `GET /mission-revisions/{id}`, pinned candidates and qualifications helpers, `GET /test-results/{id}`, `GET /portfolios/{id}` when present; actions `SELECT_CANDIDATE`, `PROVE_IT` via `POST /runs/{id}/actions`.
- Site position = centre of `candidate.aoi.bbox`. Site status = worst mandatory requirement status for that candidate. Coverage = for each requirement, the candidates with PASS.
- Benchmark text = from `Requirement` (`operator`, `lower`, `upper`, `unit`, support scale, `origin`); measured values from the comparison display artifact when present.

## D6. Build order (each step ends with typecheck + lint + unit tests green)
1. Assets, dependency, `globeAssets`, `GlobeStage` *(prototype exists locally and renders: Mars globe, pin ring, area box, panel, step rail)*.
2. Shell, Welcome, Place *(prototype exists locally)*.
3. Mission, Rover, Review.
4. Run progress.
5. Tour, site card, coverage strip, guide.
6. Report page.
7. Responsive, accessibility, motion pass.
8. Tests and audits (Part E).

---

# Part E — Verification
- Unit: `coordinates` (parsing, 0–360 conversion, pole and antimeridian rejection, box maths), `tour` (status, coverage, ordering), `narrator` (exact sentences, no invented values), state reachability of steps.
- Component: each step with the globe module mocked (`vi.mock('globe.gl')`).
- Browser (mock mode): full first-run journey; no-rover variant; failing-site variant; Moon; no-WebGL fallback; 390 px; reduced motion. Launch Chromium with `--use-gl=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist` so the globe renders in CI.
- Existing gates stay green: `scripts/ui/forbidden_scan.py`, glass contract tests, purity, typecheck, lint, 134+ unit tests, production build, J01–J13 against the real backend (only the entry path changes), visual audit extended with the new screens (zero findings), `pnpm audit`.
- Any design-standard change is made by amending doc 41 with a recorded decision and refreshing its entry in `team coordination/contracts/architecture-baseline.json`.

---

# Part F — What must be plugged in afterwards (backend, data, imagery)

Each item names the UI slot that is already waiting for it. Until an item is done the UI shows the stated honest fallback, never fake data.

## F1. Real planet imagery (visual only)
- Supply equirectangular global maps (2:1, longitude −180…180 left→right, north up, ≥4096×2048, JPG/WebP):
  - Mars: e.g. USGS Viking MDIM 2.1 colour mosaic or MOLA colour shaded relief.
  - Moon: e.g. LROC WAC global mosaic or LOLA shaded relief.
  - Optional higher-resolution Earth (Blue Marble Next Generation).
- Put files in `apps/web/public/globe/`, edit `src/maps/globeAssets.ts`: set `surface`, optional `relief`, `placeholder:false`, real `attribution`. No other code changes. Check each image's usage terms; no NASA insignia.
- Fallback today: generated surfaces with an amber "Placeholder surface imagery" label.

## F2. More terrain datasets (so the tour has real, varied places)
- Today real data exists only for Mars/Gale (MOLA) and Earth/Flagstaff (NASADEM n35w112), local to the operator's machine.
- Needed: more Earth regions (NASADEM tiles for other analog areas), Moon target terrain (LOLA), further Mars areas. Each goes through the existing manifest → validate → lock → bind flow; no UI change.
- Fallback today: synthetic practice sites, labelled.

## F3. Dataset coverage endpoint (pin step and globe footprints)
- New read endpoint, e.g. `GET /coverage?body=MARS&bbox=w,s,e,n` → `{state:'COVERED'|'PARTIAL'|'NONE', datasets:[{id,name,bbox}]}` and `GET /datasets?body=…` → footprints for drawing on the globe.
- UI slot: `features/missionControl/coverage.ts` `useCoverage()`; the Place step chip and (optionally) footprint outlines.
- Fallback today: "Not yet known — checked when the investigation starts."

## F4. Target area acceptance
- Confirm that a custom target box of the offered sizes (10–80 km) is accepted for each bound scenario, or expose allowed sizes/bounds per scenario in `GET /configuration/scenarios/{id}` so the UI can limit choices.

## F5. Per-site benchmarks and capability assignment
- For every candidate × requirement the UI needs: threshold (lower/upper/unit/support), measured value, margin, status, and a plain-language limitation list. Today the measured value is only inside display artifacts and route benchmarks exist only for the single proven candidate.
- Needed: benchmark fields on the qualification rows (or a `GET /runs/{id}/site-benchmarks`), and portfolio assignment (requirement → sites) produced automatically at review time rather than only on the "Build portfolio" action.
- UI slot: `tour.ts` (`siteBenchmarks`, `coverage`) and the Coverage strip.

## F6. Automatic proving
- Run the route test for the best site per capability without a manual click per site (or allow `PROVE_IT` for several candidates). UI slot: the "Prove it here" button becomes a status.

## F7. Report and PDF
- Per-site report export (`GET /passports/{id}/exports/pdf` or a per-site HTML bundle). UI slot: `ReportPage` "Save as PDF" switches from browser print to the real file.

## F8. Run progress detail
- Stable `event_type` values and a percentage or step count on run events so the progress list can show sub-steps. UI slot: `RunProgress`.

## F9. Optional later
- Mission file attachments (new draft field + upload endpoint) → an "Attach files" control in the Mission step.
- OIDC sign-in screen before Welcome.
- Live guide chat grounded in the passport (model key required) replacing the scripted narrator; avatar artwork.
- Site names and photos for Earth candidates (reverse-geocoded names, attributed imagery) to replace "grid-r1c0"-style labels in tickers.

## F10. Integration checklist when backend items land
1. Regenerate the API client (`pnpm run generate:client`) and adapt `tour.ts` / `coverage.ts` only.
2. Run the mock journeys, then the real-backend journeys with the live datasets bound.
3. Confirm no placeholder label remains (`[data-placeholder=true]` absent) and the coverage chip shows a real state.
4. Re-run the visual audit and update the attribution list on the About page.
