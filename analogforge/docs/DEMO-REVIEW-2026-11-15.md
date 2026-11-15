# Demo review fixes — 15 November 2026

This addresses Claude’s review of main `d6ee539`. The review used the real API, worker, science engine and PDF subprocess with explicitly synthetic practice data. The native review used the user’s Comet app. No billing, credentials, source locks or scientific acceptance thresholds changed.

## What changed

| Finding | Resolution |
| --- | --- |
| Empty fresh rover library | The empty state offers **Use ARES-1 example rover**. Creation requires a click and uses the canonical profile. Assumed, uncalibrated values stay explicit. Custom profiles and no-rover runs remain available. |
| Unrequested external tiles | Both production Earth map callers leave auto-load disabled. Each selected site needs an explicit **Load satellite imagery** click. A blocked provider retains the measured terrain and an actionable notice. |
| Dense first result | The tour defaults to an all-location plan: coordinates, supported capabilities, accepted limits, recorded status counts and the next test. The globe faces a candidate location. Each card opens its exact regional evidence. |
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

- Full platform backend suite: **1,247 passed**, with existing dependency deprecation warnings. New procedural guidance and latest PDF changes also passed focused tests.
- Final frontend full suite: **360 passed**. Production build, TypeScript and changed-area lint checks passed.
- Real-backend browser journeys: desktop globe, grouped markers, exact-site changes, opt-in blocked imagery and PDF; mobile 390 px; keyboard/reduced motion and serious/critical accessibility scan; no-WebGL; Moon unsupported coverage and explicit Moon practice data. All passed after the camera and test synchronization corrections.
- Native Comet run: `25fbdc53-69c7-4c79-8672-8ce5168cdfb2`. Selected an existing canonical ARES-1 profile, prepared and accepted requirements, opened the overview, inspected a location, and ran its rover model in the tour. Two attempts were recorded and the run published a **LIMITED** passport. The first location showed **5 met, 2 need more evidence, 2 cannot be tested on Earth**. No physical rover pass is claimed.
- Native Comet satellite check: explicitly loaded the public USDA/USGS aerial layer and zoomed twice. Roads/terrain loaded at a 500 m scale bar. Source vintage and approximate local sampling remain displayed.
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
- The separate account/landing work remains local until published independently; it is not required for these demo fixes.

Screenshots and PDFs are ignored local receipts under `out/demo-review/` and `out/mission-control-*.png`; no account data, credentials or large generated files are included in Git.
