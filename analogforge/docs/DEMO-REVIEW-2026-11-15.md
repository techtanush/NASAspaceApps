# Demo review fixes — 15 November 2026

This addresses Claude’s review of main `d6ee539`. The review used the real API, worker, science engine and PDF subprocess with explicitly synthetic practice data. The native review used the user’s Comet app. No billing, credentials, source locks or scientific acceptance thresholds changed.

## What changed

| Finding | Resolution |
| --- | --- |
| Empty fresh rover library | The empty state offers **Use ARES-1 example rover**. Creation requires a click and uses the canonical profile. Assumed, uncalibrated values stay explicit. Custom profiles and no-rover runs remain available. |
| Satellite view / external tiles | Following the owner’s explicit authorization, selected Earth maps load bounded public USGS/EOX imagery by default. Dates and visual-only limits stay visible. Measured terrain is a deliberate secondary view; a blocked provider does not silently reveal colored analysis cells. |
| Dense first result | Research stays on one progress screen until reviewable results arrive. Then Earth opens with an individual numbered pin for every candidate, anchored to its actual coordinate. Nearby labels have leaders, not an aggregate marker. A pin or directory entry opens satellite detail, benchmarks, procedure and PDF. **Open results dashboard** removes the globe and shows the all-location matrix; **Back to Earth** restores it. |
| Rover test leaves the tour | **Run rover test here** selects and confirms the exact candidate/revision, then submits PROVE_IT. It preserves backend review gates, remains in the tour, and never runs without a click. Completed runs retain their evidence rather than being silently reopened. |
| Ambiguous site verdict | Counts distinguish met/unmet/partial, route work, missing observations and Earth transfer gaps. A missing weather observation is not labeled as a pending route test. |
| Long / generic PDF | The combined file has a styled two-page directory and coverage matrix, then bookmarked per-location plans. Per-site files lead with an executive summary and simplified benchmark matrix/plots; full tables, exact values and hashes remain in a technical appendix. Procedures use each accepted observable, slope band and task identifiers. No empty route sketch is drawn. |
| Internal passport sentences | Newly published claims use accepted requirement labels, readable scopes and outcome language. Structured IDs and enums remain auditable; previously published immutable passports are not rewritten. |
| Grid labels | Main tour, regional inspector and location-report headings use coordinate-based names for generated grid labels. Stored source labels remain intact. |
| Developer event titles | Run lifecycle entries have readable titles while retaining actual recorded summaries and evidence references. |
| Footer overlap | Imagery source controls, attribution, progress rail and dashboard reserve separate space. |
| Hidden scrolling | Scrollable panels have a keyboard focus target, visible scrollbar and conditional “More details below” cue. |
| Phone header collisions | At 390 px the compact header, progress rail, regional view, results panel and imagery footer have distinct positions. |
| Inert local Owner badge | Local mode hides that account-like context badge. This change does not require the separate, locally developed authentication feature. |
| Misleading coordinates | Empty fields say **Enter latitude** / **Enter longitude**. A selected place supplies actual values. |

## Evidence and validation

- Main-based platform backend sweep: **1,253 passed**, plus two PDF extraction assertions that needed normalization for line breaks and numeric formatting. Those assertions were corrected; the complete affected **72-test** PDF/guidance/assurance set passed afterwards. The separately rerun CPU/science tests passed (20). No application budgets were relaxed. Existing dependency deprecation warnings remain.
- Integrated local frontend suite: **360 passed**. The separate main-based release branch passed its complete **331-test** frontend suite, **72 focused backend tests**, TypeScript and production build. The additional local account tests and account code are excluded from the release branch.
- Real-backend browser journeys: desktop globe, individual pins, map-free results dashboard, exact-site changes, default imagery with blocked-provider fallback and PDF; mobile 390 px; keyboard/reduced motion and serious/critical accessibility scan; no-WebGL; Moon unsupported coverage and explicit Moon practice data. All passed after the camera and test synchronization corrections.
- Native Comet run: `25fbdc53-69c7-4c79-8672-8ce5168cdfb2`. Selected an existing canonical ARES-1 profile, prepared and accepted requirements, opened the overview, inspected a location, and ran its rover model in the tour. Two attempts were recorded and the run published a **LIMITED** passport. The first location showed **5 met, 2 need more evidence, 2 cannot be tested on Earth**. No physical rover pass is claimed.
- Native Comet satellite check: loaded public USDA/USGS aerial tiles and zoomed twice. After default-loading authorization, selected a pin and verified aerial imagery loaded without another click. Roads/terrain loaded at a 500 m scale bar. Source vintage and approximate local sampling remain displayed.
- PDF review: a six-location snapshot is **14 pages before route verification / 15 afterwards**, versus the reviewed 51-page version. A detailed proved per-site file is **18 pages including its full audit appendix**, versus the reviewed 25. Its executive summary and benchmark matrix/graphs are the first two pages. Rendered PNGs were checked for layout. Document length depends on actual requirements, routes and source evidence; no fixed page count is promised.
- TypeScript, ESLint for changed frontend areas, Ruff for changed backend areas, production build, forbidden-pattern scan and whitespace checks are included in the final gate.

Reproducible commands from `analogforge/` (profile configuration and outputs are ignored):

```sh
rtk proxy .venv/bin/python .runtime/profile.py test pytest tests/unit/platform tests/integration/platform -q
rtk proxy .venv/bin/python .runtime/profile.py test pytest tests/unit/platform/test_field_guidance.py tests/unit/platform/test_evidence_brief.py tests/integration/platform/test_assurance.py -q
rtk proxy .venv/bin/python scripts/ui/forbidden_scan.py
```

From `apps/web/`, use the supported Node installation in PATH and run `vitest run`, `tsc --noEmit`, `eslint`, `vite build`, and the real-backend `mission-control.spec.ts` suite with E2E_BASE_URL set to the review server.

## Explicit limits

- This fix pass did not execute a fresh live NASA-data/model-provider research run. Existing live data, weather and provider adapters are unchanged. Synthetic scientific measurements remain labeled synthetic even when real historical imagery is used as context.
- A regional search is not a claim of global optimality. Missing lunar coverage remains an explicit coverage stop; the separate Moon practice journey uses its declared synthetic target.
- Route endpoints appear only after matching, independently verified route evidence exists for that location. They are model-derived planning references, not a surveyed or cleared driving corridor. Earth tests cannot assure mission success in different gravity, atmosphere or other unreproduced conditions.
- The separate account/login work remains local until published independently; it is not required for these demo fixes.

Clean-release verification also corrected the original landing animation so its headline stays below the header. The end-to-end regression checks that position and runs the rover model inside the tour through to passport claims.

Screenshots and PDFs are ignored local receipts under `out/demo-review/` and `out/mission-control-*.png`; no account data, credentials or large generated files are included in Git.

Additional release gates: 159 renderer/UI contract tests; 20 frozen contract-kit tests; three browser contract checks; full Ruff and Mypy (269 source files); final wire and structural purity checks passed. The extended backend attempt initially used an incorrect local launcher without a multiprocessing main guard, causing spawned CPU workers to rerun pytest. The launcher was corrected, and the affected CPU/science tests passed without changing application budgets. This launcher is ignored local tooling, not part of the release.

## Final flow review

The owner approved default loading of USGS/EOX tiles after being told that the provider receives the viewed area and client IP. This supersedes the earlier opt-in-only review requirement. Public source allowlists, per-view budgets, failure cancellation, source zoom caps and scientific coverage boundaries remain enforced. The reusable component remains offline unless its caller enables satellite imagery.

Native Comet receipts: `earth-pins-comet.png` (six independent numbered pins), `satellite-default-comet.png` (real aerial landscape), and `results-dashboard-comet.png` (full plan with no globe). Receipts are ignored under `out/demo-review/`.

The final mobile accessibility scan caught focusable location pins inside a static-image role. The globe is now an interactive region. Its corrected real-backend mobile, keyboard and reduced-motion journey passed with no serious or critical Axe violations. The other four real-backend journeys passed in the same review batch.

## Geographic accuracy follow-up

Every globe pin comes from the center of the returned candidate’s geographic Earth bounds. The numbered badges may move in screen space to avoid overlap; their leader lines remain anchored to the original location. They are region centers, not independently surveyed route starts. Rotation and zoom remain enabled; clicking a pin opens the corresponding candidate ID. Pins on the far side of Earth are occluded as the globe rotates; the complete location directory remains available.

Regression fixtures cover returned sites in South America, Australia, northern Europe and both sides of the date line, changing input bounds, retained unknown verdicts, and rejection of projected or out-of-range coordinates. The current regional practice search is explicitly labeled; a global display is not a claim that the algorithm searched beyond acquired terrain coverage.
