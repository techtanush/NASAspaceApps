# Aradhya — design system, professional look, and visual QA

This file is the **procedure and gate** for the look of the product. The **standard** (what it must look like, banned slop, component specs, screen briefs, copy voice, QA catalog VIS-01…VIS-18) is [architecture 41](../../architecture%20files/41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md) — read it completely before writing a single component. The palette is [design/tokens.json](design/tokens.json).

> **The bar:** this ships to a NASA mission planner who uses it for a six-hour shift tomorrow. It must read as a calm, dense, exact engineering console — NASA Open MCT / Grafana-on-call / Carbon-enterprise discipline — and never as a template, a landing page, or generic AI-generated UI. If a stranger could mistake it for a "space-themed SaaS template", you have failed this file even if every test is green.

## 1. What you are given (copy, do not re-derive)

| Given file (in this guide) | Copy to | Rule |
| --- | --- | --- |
| `design/tokens.json` | `analogforge/apps/web/design/tokens.json` | byte-identical unless a recorded decision changes a value and `verify_tokens.py` still passes |
| `design/verify_tokens.py` | `analogforge/scripts/ui/verify_tokens.py` | byte-identical |
| `design/gen_tokens_css.py` | `analogforge/scripts/ui/gen_tokens_css.py` | byte-identical |
| (generated) | `analogforge/apps/web/src/styles/tokens.css` | `python3 scripts/ui/gen_tokens_css.py --out apps/web/src/styles/tokens.css`; never hand-edited |

Run `python3 scripts/ui/verify_tokens.py` first: it must print `150/150 checks passed`. These files are not in the kit (they are design assets, not a cross-branch contract); the merging agent compares them against this guide's copies (MRG-11).

## 2. Phase V (runs inside the phases of `02-IMPLEMENTATION-PLAN.md`)

| When | Do | Exit proof |
| --- | --- | --- |
| **U1** (shell) | Copy the three design files; generate `tokens.css`; install `@fontsource-variable/inter` (or `@fontsource/inter`), `@fontsource/ibm-plex-mono`, `lucide-react`, Radix primitives, `clsx`, `d3-*` primitives; write `styles/{reset,base,layout,print}.css` using only variables; build the shell (header, context column, evidence drawer rail, operations bar) per arch 41 §5.2 with real layout, themes (`data-theme`, `public/theme-init.js`), `theme-toggle`, `density-toggle`; implement `format/*` per arch 41 §8 | `verify_tokens` pass; screenshot of an empty shell in dark+light at 1440×900 |
| **U1b** (component kit + styleguide) | Implement **every** component in arch 41 §19 with all states; build `/__styleguide` (dev+mock only) showing them all in both themes and all three densities; write `components/ui/*.test.tsx` for the behaviors (keyboard, aria, focus return, disabled-reason) | styleguide renders; axe clean on it; component tests pass |
| **U3** (screens) | For each screen, follow its brief in arch 41 §10: first-glance hierarchy, layout, signature element. After implementing a screen, run `pnpm run audit:visual -- --screen <id>` and fix findings **before** moving on (do not defer design debt) | per-screen audit pass + screenshots |
| **U5** (journeys) | Implement the full `visual_audit` (§3) and the keyboard-walk, print and reduced-motion/text-spacing specs; wire `pnpm run audit:visual` | UIX-13 pass |
| **U6** (self-audit) | Run the design mutation checks (§5), then the **design review** (§4) with ≥ 3 reviewer subagents; fix all blockers; re-run the audit and review until the rubric passes | DR-01…DR-04 pass |

## 3. `scripts/ui/visual_audit.mjs` (gate UIX-13 — implement exactly this)

Playwright script (Chromium, deterministic: fixed clock, mock mode with 300 ms latency, `reducedMotion: 'no-preference'` unless stated, fonts awaited with `document.fonts.ready`). It crawls the mock-mode app through the click scripts of J01/J05/J10 to reach every screen/state, then for **each** (screen state × viewport × theme) runs the checks below and writes `out/visual/report.json` and screenshots with `out/visual/manifest.json` (name, viewport, theme, density, sha256). Exit 1 on any finding. Viewports: **1920×1080, 1440×900, 1280×800, 1024×768, 768×1024, 390×844**; themes: dark, light; densities: default everywhere + compact and comfortable on S06, S07, S10.

| Check | Implementation detail | Threshold |
| --- | --- | --- |
| C01 fonts | Walk all visible text nodes; `getComputedStyle().fontFamily` first family ∈ {Inter, IBM Plex Mono} (mono fallbacks allowed after); `document.fonts` contains loaded faces; `PerformanceObserver`/`page.on('request')` shows **0** requests to hosts other than the app origin | 0 violations |
| C02 min size | every visible text node `fontSize ≥ 12px`; body/table/input text ≥ 13px | 0 |
| C03 contrast | run axe `color-contrast` AND a custom sampler: for each visible text node compute foreground vs. the **effective background** by walking ancestors' opaque backgrounds (for text over map/canvas use a screenshot pixel sample of the surrounding 4 px ring); WCAG ratio | ≥ 4.5 (≥ 3.0 for ≥ 24 px / 18.66 px bold and non-text UI boundaries) |
| C04 grid | for every element matching `[class*="panel"],[class*="card"],td,th,button,input,select,[role="tab"],[role="row"]` assert computed margin/padding/gap/row-gap/column-gap/width/height are `0` or multiples of 4 px, **allow-list only**: 1 px borders, 2 px focus, 3 px state edge, `auto`, percentages, `fit-content`, flex/grid-derived widths | 0 (allow-list is a constant in the script, ≤ 12 entries, each commented) |
| C05 overflow | `document.documentElement.scrollWidth ≤ innerWidth` at every viewport ≥ 360; for every element with text `scrollWidth ≤ clientWidth + 1` unless `[data-overflow="intentional"]` which must also expose full value via tooltip and focusable expand; no two interactive elements' bounding boxes overlap by > 2 px | 0 |
| C06 targets | every interactive element ≥ 24×24 CSS px (≥ 44×44 with `hasTouch`/`pointer: coarse` at 390 px) | 0 |
| C07 focus | Tab through each screen (≤ 80 stops): at each stop the focused element has an `outline`/`box-shadow` ring of ≥ 2 px with contrast ≥ 3:1 against the adjacent background; the element is not covered by a sticky header/drawer (`elementFromPoint` at its centre is itself or a descendant) | 0 |
| C08 states greyscale | apply `filter: grayscale(1)` to `html`; for the matrix, test lab and passport, for each of the six states assert (a) visible word, (b) distinct glyph SVG path-data hash across the six, (c) a pixel-level check: render each glyph at 24 px to canvas, binarize, require pairwise IoU ≤ 0.85 | 0 |
| C09 numerics | every `td`/`[data-numeric]` cell whose text matches a number: `text-align: right`, `font-variant-numeric` includes `tabular-nums`; page text never matches `/\b(NaN|undefined|null|\[object Object\])\b/` | 0 |
| C10 slop | `getComputedStyle` scan of all elements: no `background-image` containing `gradient` (except `[data-allowed="scientific-ramp"]`), no `backdrop-filter`, `text-shadow` none, `box-shadow` only the token overlay shadow on popover/dialog/drawer, `border-radius` ≤ 6 px (or `50%` on ≤ 12 px dots), no emoji code points in any text node/`aria-label`/`alt`/`title`, no text matching `/lorem ipsum|todo|coming soon|!{1,}\s*$/i` in visible copy | 0 |
| C11 CLS | `PerformanceObserver('layout-shift')` summed (excluding user-input-driven) across load + data arrival | ≤ 0.02 on S01, S06, S07, S10, S12 |
| C12 console | no `console.error`/`warning`, no `pageerror`, no failed requests | 0 |
| C13 hierarchy | exactly one `h1` per route; heading levels never skip; ≤ 1 primary-variant button per region (`[data-variant="primary"]` count per `[data-region]` ≤ 1); PROVE IT is the only element with `data-size="xl"` | 0 |
| C14 no hex | static grep (in `forbidden_scan.py`, reused): no `#[0-9a-fA-F]{3,8}` or `rgb(`/`hsl(` literals in `src/**/*.{css,tsx,ts}` outside `styles/tokens.css`, `maps/**`, `*.test.*`, `mock/fixtures` | 0 |
| C15 text-spacing | inject the WCAG 1.4.12 override stylesheet (line-height 1.5; paragraph spacing 2×; letter-spacing 0.12em; word-spacing 0.16em) and re-run C05 on S02, S04, S07, S12 | 0 |
| C16 reduced motion | emulate `prefers-reduced-motion: reduce`: all computed `transition-duration`/`animation-duration` ≤ 1 ms; route playback does not start by itself | 0 |
| C17 print | `page.pdf()` of the passport route: page 1 contains mode badge, headline, manifest digest (text extracted by `pdf-parse`-free method: render HTML and inspect the DOM at `emulateMedia('print')`); no table wider than the page; `@page` margins 18 mm; light tokens active (canvas colour is light) | 0 |
| C18 styleguide | `/__styleguide` lists every component of arch 41 §19 (a JSON list in the script); each rendered in dark and light, 3 densities; axe 0 critical/serious | 0 |
| C19 prod bundle | after `pnpm run build`: `dist` has no `__styleguide`, no `msw`, no `MOCK PREVIEW`, no `http(s)://` URLs other than allowlisted documentation constants | 0 |
| C20 thresholds locked | the script's constants (min size 12, contrast 4.5/3, grid 4, CLS 0.02, targets 24/44, radius 6, viewports) equal arch 41 §20; a unit test `visual_audit.thresholds.test` imports them and compares with literal values from this guide | equal |

`audit:visual` also writes `out/visual/screens.md`: a table of every screenshot (file, screen, state, viewport, theme) — the **review input** for §4. Screenshots are **not** committed except the styleguide set (`apps/web/docs/design-review/styleguide-*.png`, ≤ 12 files, ≤ 400 KB each).

### Hard rules for the audit itself
* No check may be skipped, quarantined, scoped to a hand-picked element list, or given an allow-list beyond what is written above. Adding to an allow-list requires a `DECISIONS.md` entry with the visual reason and the screenshot name.
* You may not satisfy a check by hiding content (`display:none`, `visibility:hidden`, zero-size) that is meant to be visible; C05/C06 also assert that every element required by `ui-testids.json` for the screen is visible and has non-zero size.
* The audit must be run against **both** themes. A dark-only pass is a fail.

## 4. Design review (gate DR) — human-grade, performed by you with subagents

After `audit:visual` is green:

1. Spawn **three reviewer subagents with different personas** and give each *only*: `architecture files/41-…md`, the screenshot catalog `out/visual/screens.md` + images, and the rubric below. They must open the images (Read tool) and cite file names and element selectors. Personas: **(a) mission-operations HMI reviewer** (ISA-101/Open MCT mindset: is status the loudest thing, is chrome neutral, is density right), **(b) accessibility & typography reviewer**, **(c) hostile "slop detector"** whose only job is to find anything that looks AI-generated, templated, decorative or inconsistent (checks X-01…X-29 against screenshots and DOM).
2. Each returns the **rubric** of arch 41 §20 (12 criteria, 0–4) with at least **five concrete defects** (or an explicit, evidenced statement that fewer than five exist), ordered by severity, each with screenshot name + selector + proposed fix.
3. You fix every defect rated blocker/major (any criterion ≤ 2, any X-xx item), re-run `audit:visual`, regenerate screenshots, and re-submit to **fresh** reviewers (new subagents). Repeat until every criterion ≥ 3 and the mean ≥ 3.5 for all three reviewers.
4. Write `team handoffs/aradhya/DESIGN-REVIEW.md` containing: reviewer prompts, each round's scores, defects, fixes (commit SHAs), and the final scores. Reviewers may not be told the previous round's scores. You may not write the scores yourself — paste the reviewers' reports verbatim.

| Gate | Passes when |
| --- | --- |
| **UIX-12** | `verify_tokens.py` = `150/150`; `tokens.json`/`verify_tokens.py`/`gen_tokens_css.py` byte-identical to this guide's copies (or recorded decision + verifier pass); regenerated `tokens.css` byte-identical to the committed file; C14 clean |
| **UIX-13** | `pnpm run audit:visual` exit 0 over all screens × viewports × themes with 0 findings and 0 skipped checks; report + manifest present; C20 passes |
| **DR-01** | `/__styleguide` complete (VIS-12) and its screenshots committed |
| **DR-02** | three reviewers, final round, all rubric criteria ≥ 3, mean ≥ 3.5 |
| **DR-03** | no X-01…X-29 finding open (the slop detector's final report states "no open findings" with evidence) |
| **DR-04** | `DESIGN-REVIEW.md` complete and `STATUS.json.design` filled with observed values |

## 5. Design mutation checks (add to `mutation_check.py`; each must be killed)

| # | Mutation | Killed by |
| --- | --- | --- |
| M25 | a `linear-gradient` added to the header | C10 / forbidden scan |
| M26 | `border-radius: 16px` on the panel class | C10 |
| M27 | `font-size: 11px` on a caption | C02 |
| M28 | numeric column switched to left aligned / proportional digits | C09 |
| M29 | a status glyph swapped to look the same as another | C08 |
| M30 | `text-secondary` token lightened below 4.5:1 on `surface-1` | `verify_tokens` / C03 |
| M31 | an emoji added to an empty-state title | C10 |
| M32 | focus outline removed on buttons | C07 |
| M33 | page given `min-width: 1200px` | C05 at 1024/768/390 |
| M34 | a hex literal added to a component stylesheet | C14 |
| M35 | second primary button added to a region | C13 |
| M36 | Google Fonts `<link>` added | C01 / C19 |

## 6. Quality checklist you must satisfy by inspection (beyond automation)

Open each screenshot and answer yes to all: Is the status the first thing my eye lands on? Could I tell the six states apart in greyscale? Is every number right-aligned with its unit in the header? Do all tables share one row/header style? Is there exactly one primary action? Do empty/error/loading/disabled states look designed and say *why*? Is copy plain engineering English with no hype, emoji or exclamation marks? Are spacing and alignment rigorous (nothing off by a few px)? Does dark mode look like a control-room console and light/print like an engineering document? Would I be comfortable showing it to a NASA program manager as a delivered tool? Any "no" is a defect to fix before declaring done.

## 7. Reference study (optional but recommended before U1b)

Arch 41 §3 lists study references (NASA Open MCT, Carbon, Blueprint, Primer, USWDS, Radix, TanStack Table, Grafana, Observable Plot, MapLibre, Inter/Plex, Lucide, ISA-101, Okabe–Ito, WCAG 2.2) with exactly what to borrow and avoid. They are **unverified** in the authoring sandbox: if your network allows, open them to calibrate taste; if not, the rules in arch 41 are sufficient. Never copy code/assets without confirming an MIT/Apache/BSD/OFL/CC0 licence and recording it in `analogforge/apps/web/THIRD-PARTY.md`.
