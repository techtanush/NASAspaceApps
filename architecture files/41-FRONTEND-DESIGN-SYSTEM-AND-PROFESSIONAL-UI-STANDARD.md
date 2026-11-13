# 41 — Frontend design system and professional UI standard

**Status: binding.** This document defines how AnalogForge must *look, read and behave*. It is the visual and interaction counterpart of the functional specifications in [16](16-USER-JOURNEYS-AND-SCREENS.md), [17](17-FRONTEND-COMPONENTS-AND-STATE.md), [18](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) and [19](19-ANALOG-PASSPORT-AND-EXPORTS.md). Where [18](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) §7–§8 (the "proposed" tokens and layout) disagree with this document, **this document wins** (precedence ruling E-19 in [34](34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md)); 18 keeps authority over map and layer *behavior*. The machine-readable palette is `team guides/Aradhya/design/tokens.json`; the procedure and gates for building and proving all of this are in `team guides/Aradhya/10-DESIGN-SYSTEM-AND-VISUAL-QA.md`.

The owner of this standard in implementation is the branch that owns `analogforge/apps/web` (**Aradhya**). The merging agent re-checks it (`merging guide/`, MRG-11).

---

## 0. The one-sentence brief

> Build it as if NASA had already awarded the contract and a crew member or flight-controller-adjacent mission planner will use it for a six-hour shift tomorrow: calm, dense, exact, legible at a glance, impossible to misread, and with nothing on screen that is decoration.

Everything below derives from that sentence. When a decision is not covered, ask: *"Would a mission planner at hour five of a shift, tired, reading this under a bad monitor, misread or be annoyed by it?"* If yes, change it.

## 1. Design intent and principles

AnalogForge is an **engineering instrument**, not a marketing site and not a consumer app. It qualifies terrain against requirements and defends the result with evidence. The interface must make *evidence status* the loudest thing on every screen and make everything else quiet.

1. **Status is the only thing allowed to be colourful.** Chrome (panels, borders, buttons, headers) is neutral blue-grey. Colour appears only for scientific/operational state (PASS, PARTIAL, FAIL, GAP, UNKNOWN, PENDING), the single interactive accent, and chart series. This is the ISA-101 / HMI "grey-scale with colour for abnormal/significant state" discipline.
2. **Never colour alone.** Every state is colour **+ shape + icon + text label**. A greyscale screenshot must remain fully readable.
3. **Density with order.** Information-dense but organised on a 4/8 px grid with strict alignment. Dense does not mean cramped: row heights, padding and typography follow the scale in §5–§7.
4. **Numbers are first-class.** Right-aligned, tabular numerals, units always adjacent, precision deliberate, support/scale next to the value (§8).
5. **Honest emptiness.** `Unknown`, `Pending`, `Not requested`, `Awaiting datasets` and `Inconclusive` are designed states with their own look, not blank cells or spinners (§9, §13).
6. **One primary action per view.** Exactly one filled-accent button per screen region. PROVE IT is the single exception that earns a larger treatment (§9.4).
7. **Predictable, boring, consistent.** Same component ⇒ same look everywhere. No one-off styling. If a pattern appears twice it becomes a component.
8. **Quiet motion.** Motion explains state change in ≤ 160 ms; nothing animates to look "alive". Route playback is the only long animation and it is user-driven (§12).
9. **Readable first, impressive never.** No effect exists to impress. The "wow" is correctness, clarity, and visible rigor (evidence drawer, receipts, hashes).
10. **Keyboard, screen-reader and print are real users.** Mission planners use keyboards; reviewers print passports (§15–§17).

### 1.1 What "professional" is measured against

A reviewer must be able to tick every box in the rubric of §20 without hedging. The bar is: *indistinguishable in discipline from the operator-facing parts of NASA Open MCT, a Grafana/Datadog on-call dashboard, Bloomberg-style data tables, or a Carbon/Blueprint enterprise app* — not from a landing page template.

## 2. The "slop" list — banned outright

The following are defects, not style choices. Items marked **[scan]** are enforced by `scripts/ui/forbidden_scan.py` / the merging guide's `purity_check.py`; the rest are enforced by the visual audit and the human/adversarial review (§20).

| # | Banned | Why / use instead |
| --- | --- | --- |
| X-01 | Emoji anywhere in UI, copy, test ids visible text, alt text, commit of fixtures **[scan]** | Use `lucide-react` icons or the custom status glyphs (§9.2). |
| X-02 | Gradients on surfaces, buttons, text, borders (`linear-gradient`, `radial-gradient`, `conic-gradient`) **[scan]** | Flat tokens only. Exceptions: scientific colour ramps in raster legends, marked `/* allowed: scientific-ramp */`; and the single static ambient backdrop of the glass layer (§5.5), which is a radial gradient on one element. |
| X-03 | Glassmorphism **outside the glass layer** (§5.5): `backdrop-filter` or translucent blurred surfaces on anything except the listed chrome and panel frames **[scan]** | Opaque `surface-*` tokens. Tables, charts, maps and every scientific value are always opaque. |
| X-04 | Glow / neon: coloured `box-shadow` or `text-shadow` halos, "sci-fi" outlines **[scan]** | Borders and flat fills. Neutral dark elevation shadows below listed surfaces are allowed (§5.3, §5.5); coloured or zero-offset halos never are. |
| X-05 | Large radii / pills / blobs: `border-radius` > 6 px except `50%` on 8–12 px status dots and listed glass surfaces and data frames up to 14 px (§5.5) **[scan]** | `--radius-1..3` (2/4/6 px) for controls, badges and links. |
| X-06 | Hero banners, gradient splash headers, marketing sections, "Welcome to AnalogForge!" illustrations, stock imagery | S01 opens straight into the work (§10 S01). |
| X-07 | Starfield / space-themed backgrounds, planet illustrations as decoration, particle effects | The planet only appears as **data** (maps, panels). |
| X-08 | Centered card grids of "features", three-column icon-over-heading blurbs, testimonial strips | Tables, lists, panels. |
| X-09 | Placeholder text: `Lorem ipsum`, `TODO`, `Coming soon`, `Sample`, `Example 1`, `Test` as visible labels **[scan]** | Real domain copy (§14) or an honest `awaiting datasets` state. |
| X-10 | Non-tabular numerals in aligned columns; proportional digits in tables **[scan via audit]** | `font-variant-numeric: tabular-nums` (§7). |
| X-11 | Text smaller than 12 px; line-height < 1.25; low-contrast greys below WCAG AA **[audit]** | §7 scale, `tokens.json`. |
| X-12 | All-caps paragraphs, shouty headings, wide letter-spacing on body | Sentence case; caps only for ≤ 3-word status/column labels at 12 px (§7.3). |
| X-13 | Default browser look leaking: unstyled `<select>`, raw `<input type=file>`, system scrollbars on dark theme, default focus ring, blue underlined default links | Styled primitives (§9). |
| X-14 | Spinners with no text; skeletons that never resolve; "Loading..." with no scope | Skeleton shaped like the final content, or a text status with elapsed time (§9.12). |
| X-15 | Toasts for results that matter (run finished, verification failed, export ready) | Persistent banners/rows; toasts only for non-critical confirmations (≤ 4 s, `aria-live=polite`). |
| X-16 | Modals for things that should be inline or drawers; modal-on-modal | Drawers (evidence, operations); one dialog max, only for destructive/blocking decisions. |
| X-17 | Decorative icons without a label; icon-only buttons without `aria-label` and tooltip | Icon + text, or icon with accessible name + tooltip. |
| X-18 | Mixed icon sets, mixed stroke widths, mixed corner styles | `lucide-react` at 16 px / stroke 1.5 + the custom glyphs. |
| X-19 | Fake data viz: pie/donut for similarity, radar "match scores", 0–100 "Mars-likeness" gauges, percentage-similarity badges | Forbidden scientifically (architecture 33). Tables with explicit requirement rows. |
| X-20 | 3D-tilted, parallax, scroll-jacked or auto-playing carousels | None. |
| X-21 | Spacing that is not a multiple of 4 px; ad-hoc magic numbers (`margin: 13px`) **[audit]** | Tokens `--space-1..7`. |
| X-22 | More than 2 typefaces; display fonts; script fonts; web-font CDNs **[scan]** | Inter + IBM Plex Mono, self-hosted (§7). |
| X-23 | NASA meatball/worm/insignia, NASA-blue "official" skinning, "NASA approved" badges **[scan: filenames/alt/strings]** | Plain attribution text only (§16). |
| X-24 | Scientific claims in marketing voice: "revolutionary", "AI-powered insights", "unlock", "seamless", "supercharge", "smart" | Plain engineering voice (§14). |
| X-25 | Layout shift on data arrival (CLS ≥ 0.02), content jumping, tables re-sorting while read | Reserved heights, stable ordering, explicit sort control **[audit]**. |
| X-26 | Horizontal page scroll at 1024 px and wider; clipped or overlapping text; truncated values with no tooltip/expand | §11 layout, `text-overflow` only with accessible full value. |
| X-27 | Dark theme with pure black `#000` canvas and pure white `#FFF` text | Tokens (`canvas #0B0F14`, `text-primary #E8EDF3`). |
| X-28 | A different visual language per screen | One shell, one table, one badge, one drawer (§9). |
| X-29 | Hex/rgb colour literals in `.css`/`.tsx` outside `tokens.css` and `maps/` **[scan]** | CSS variables from `tokens.css` only (§4, §18). |

## 3. Reference products and open-source repositories (study list)

> **Network note.** These references were compiled from knowledge, **not verified live** when this standard was written (the authoring sandbox blocked outside hosts). Existence, URLs, current licences and APIs **must be re-checked by the implementing agent if its network allows**; if it does not, rely on the explicit rules in this document, which are self-sufficient. **Never copy code, CSS, icons, logos or images from any reference without confirming its licence (MIT/Apache-2.0/BSD/OFL/CC0 only) and recording it in `analogforge/apps/web/THIRD-PARTY.md`.** Prefer *studying structure and discipline* over copying anything. No reference may cause a runtime network request (§ no-CDN rule).

| Reference | Where (verify) | Study it for | Borrow | Do **not** borrow |
| --- | --- | --- | --- | --- |
| **NASA Open MCT** | github `nasa/openmct` | Mission-operations UI: tree + object views + time conductor, dense telemetry tables, plot discipline, light/dark themes | Telemetry-table density; "time conductor" idea for route playback; unobtrusive chrome; status-as-colour | Its branding/assets; its plugin architecture |
| **NASA Worldview / Moon & Mars Trek / Eyes on the Solar System** | earthdata.nasa.gov worldview, trek.nasa.gov, eyes.nasa.gov | How NASA presents layers, legends, attribution, dataset provenance on maps | Layer panel with legend + attribution + acquisition time; coordinate readout; measurement scale | Imagery, logos, fonts |
| **NASA Graphics Standards Manual / NASA Web Style** | nasa.gov brand guidelines | What **not** to imitate (insignia rules) | Attribution wording rules | Any NASA logo/insignia (X-23) |
| **U.S. Web Design System (USWDS)** | github `uswds/uswds` | Government-grade accessibility, form patterns, error messaging, focus handling | Form field anatomy (label/hint/error), accessible table and alert patterns, plain-language rules | Its visual theme (we use our tokens) |
| **IBM Carbon Design System** | github `carbon-design-system/carbon`; carbondesignsystem.com | Data-dense enterprise UI: data table specs, status indicators (shape+colour), data-viz guidance, density modes | Table anatomy and density tiers; status-indicator shape rules; accessible chart guidance | Its blue/Plex branding wholesale; React components (licence/bundle size) |
| **Palantir Blueprint** | github `palantir/blueprint` | Dense desktop-class React UI, dark theme, tables, trees, hotkeys | Compact control sizes; keyboard hotkeys dialog; dark-theme layering | Visual skin; heavy dependencies |
| **GitHub Primer** | github `primer/react`, primer.style | Restrained neutral UI, focus ring, status labels, accessibility guidance | Label/badge anatomy; focus & keyboard docs; "less is more" chrome | Its colours and logo |
| **Radix UI primitives** | github `radix-ui/primitives` | Unstyled accessible primitives (Dialog, Popover, Tooltip, Tabs, Select, Toggle, DropdownMenu) | **Use directly** for behavior/accessibility; style with our tokens | Radix Themes' look |
| **TanStack Table / Virtual** | github `TanStack/table`, `TanStack/virtual` | Headless table: sorting, column sizing, sticky headers, virtualization | **Use directly** for the matrix and large tables | n/a |
| **Grafana / Datadog on-call dashboards** | github `grafana/grafana`; public screenshots | Panel grid, density, legend/tooltip behavior, threshold colouring, dark default | Panel header anatomy; tooltip content; threshold bands | Colour-rich "rainbow" dashboards |
| **Linear / Vercel dashboard / Stripe Dashboard** | public product UIs | Typographic restraint, table + detail-drawer pattern, keyboard-first, calm dark mode | Drawer pattern; typographic hierarchy; empty-state tone | Marketing pages; gradients |
| **Bloomberg Terminal / Palantir Foundry style** | public descriptions/screens | Density, monochrome with semantic colour, numeric alignment | Numeric formatting discipline | Cluttered multi-window chaos |
| **SpaceX Dragon crew UI (public demo) / ISS flight-deck displays** | public demos/articles | Large legible touch targets, minimal palette, status first | Big-state readability; restraint | Faux-futurist styling |
| **Observable Plot / d3** | github `observablehq/plot`, `d3/d3` | Honest chart anatomy: axes, gridlines, direct labels, small multiples | **Use d3 scale/shape/axis primitives**; Plot's default restraint | Chart.js-style animated defaults |
| **MapLibre GL JS + MapLibre examples** | github `maplibre/maplibre-gl-js` | Map controls, layers, offline styles, GeoJSON rendering | **Use directly** | Mapbox-branded styles/tokens |
| **Inter / IBM Plex (fonts)** | rsms.me/inter (OFL), github `IBM/plex` (OFL) via `@fontsource/inter`, `@fontsource/ibm-plex-mono` | Neutral UI sans; engineering monospace | **Self-host via Fontsource packages** (no CDN) | Any web-font CDN |
| **Lucide icons** | github `lucide-icons/lucide` (ISC) | Consistent 24-grid stroke icons | **Use `lucide-react`** at 16 px, stroke 1.5 | Mixing with other sets |
| **ISA-101 HMI philosophy; WCAG 2.2; Okabe–Ito palette; Tufte's *Visual Display of Quantitative Information*; Few's *Information Dashboard Design*** | standards/books | Principles: grey-scale chrome, colour for state, non-text contrast, colour-blind-safe series, data-ink ratio | Principles verbatim into §1, §6, §10 | n/a |
| **Awesome Design Systems / Adele (lists of design systems)** | github `alexpate/awesome-design-systems`, adele.uxpin.com | Survey more systems if needed | Reading only | Copying a whole system |

**Dependency policy for UI libraries.** Allowed: React 19, React Router, TanStack Query/Table/Virtual, MapLibre, d3 primitives (`d3-scale`, `d3-shape`, `d3-axis`, `d3-array`, `d3-format`, `d3-time-format`), `lucide-react`, Radix primitives (`@radix-ui/react-dialog|popover|tooltip|tabs|select|toggle-group|dropdown-menu|visually-hidden`), `@fontsource/inter`, `@fontsource/ibm-plex-mono`, `clsx`. **Banned:** component kits that impose a look (MUI, Ant Design, Chakra, Mantine, Bootstrap, Tailwind-UI templates, shadcn *copied wholesale with its default styling*), animation libraries (`framer-motion`, `gsap`, `lottie`), chart kits with animated defaults (Chart.js, ECharts, Recharts default theme), CSS-in-JS runtime. Styling is **plain CSS modules or one global stylesheet using the token variables** (no utility-class framework needed). Every dependency is pinned, licensed (recorded), and imported locally (no CDN).

## 4. Theme model

* **Dark ("Mission Console Dark") is the default.** `:root, [data-theme="dark"]`.
* **Light** (`[data-theme="light"]`) for bright rooms; **print** (`@media print`) always uses the light tokens and a print layout (§17).
* Selection: `theme-toggle` in the header cycles `Dark / Light / System`. Persist as a harmless view preference with `localStorage` key `af.theme` — the single permitted use, marked `// allowed: view-preference` on the line. Apply `data-theme` before first paint (inline-free: set from a tiny blocking `<script src="/theme-init.js">` file in `public/`, not inline, to respect CSP).
* `color-scheme` is set per theme so native controls, scrollbars and form widgets match. Scrollbars are styled (`scrollbar-color`, 10 px thin) in both themes.
* All colours come from the generated `styles/tokens.css` (`scripts/ui/gen_tokens_css.py` from `design/tokens.json`). **No hex literal may appear in any `.css`/`.tsx` outside `tokens.css` and `maps/` style JSON** (scan X-29, §20 VIS-03).

## 5. Layout, grid and elevation

### 5.1 Grid and spacing
All spacing, sizes and offsets are multiples of **4 px**. Tokens: `--space-1..7 = 4, 8, 12, 16, 24, 32, 48`. Component internal padding uses 8/12/16; gaps between regions 8 or 16. The page never exceeds the viewport horizontally at ≥ 1024 px.

### 5.2 Application shell (desktop reference 1440 × 900)

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐ 48
│ AnalogForge │ Mission · Run name          [LIVE|REPLAY|SYNTHETIC]  ● connected   rev 7  ☼ theme  ?     │  header (sticky)
├──────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ MOCK PREVIEW — not a real backend   (mock mode only, 28 px, full-width)                              │
├────────────┬─────────────────────────────────────────────────────────────┬───────────────────────────┤
│ CONTEXT    │ Run state banner (state · stage · scientific outcome)       │ EVIDENCE (drawer, 352)    │
│ 264        │ ─ tabs: Target Analogs Qualification Compat Portfolio Test… │ opens on evidence-link;   │
│ mission    │                                                             │ otherwise collapsed to a  │
│ contract   │   WORKING AREA (flex): map | table | matrix | test lab      │ 40 px rail with count     │
│ rover      │                                                             │                           │
│ revisions  │                                                             │                           │
├────────────┴─────────────────────────────────────────────────────────────┴───────────────────────────┤
│ OPERATIONS (collapsible, 220 px when open; 32 px collapsed bar showing last event + seq)              │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

* Header 48 px, `surface-1`, bottom border `border-subtle`. Left: wordmark (text only, Inter 600 16 px, no logo glyph beyond a simple 16 px geometric mark drawn as inline SVG: a thin ring + dot — plain, monochrome, `text-primary`). Centre: breadcrumb `Mission › Run`. Right cluster (fixed order): `mode-badge`, `connection-indicator`, contract/rover revision badges, `theme-toggle`, `density-toggle`, help (`?`).
* Context column 264 px (collapsible to 48 px icons at < 1280 px). Working area flexible (min 560 px). Evidence drawer 352 px, overlays the working area at < 1440 px (never reflows the matrix).
* Operations bar: collapsed 32 px, expanded 220 px, resizable 160–360 px via keyboard (↑/↓ on the splitter) and pointer.
* **Responsive:** ≥ 1280 three-column; 1024–1279 context collapses to icon rail, evidence is an overlay drawer; 768–1023 single column with a 56 px top tab strip and bottom sheet drawers; < 768 stacked cards with sequential sections and a sticky 48 px action bar. At every size, **no horizontal page scroll** (tables scroll inside their own container with sticky first column).

### 5.3 Elevation and borders
Hierarchy by **fill step + 1 px border**, not shadows: `canvas < surface-1 (panels) < surface-2 (table header, inputs) < surface-3 (hover/selected)`. The only shadow in the product is the overlay shadow on popovers/dialogs/drawers: `0 8px 24px rgba(0,0,0,0.45)` (dark) / `0 8px 24px rgba(17,26,36,0.18)` (light). Dividers are 1 px `border-subtle`; control boundaries are 1 px `border-strong` (contrast ≥ 3:1). *Amended 2026-11-13:* listed surfaces additionally carry a soft neutral elevation shadow and a glass edge, as specified in §5.5.

### 5.4 Density
Three densities via `density-toggle` (`Compact / Default / Comfortable`), stored as `af.density` (same allowed-marker rule): table rows 28 / 36 / 44 px, control heights 28 / 32 / 40 px (touch pointer coarse ⇒ always 44 px targets). Default is **Default**. Density changes spacing only, never font size below 12 px.

### 5.5 Glass layer (amendment D-2026-11-13-GLASS, user-directed)

The product owner directed a premium, layered visual language: frosted-glass chrome over a soft ambient backdrop. This section supersedes X-02, X-03, X-04 and X-05 **only** as stated here; nothing else in this standard is relaxed, and no audit threshold changes.

**Where glass is allowed.** The single source of truth is `apps/web/design/glass-surfaces.json`:

* **chrome**: application header, context navigation, status strip, operations bar, drawers, dialogs, popovers, menus, toasts;
* **panels**: panel frames, run state card, metric cards, critic and attempt cards, banners, empty and error states, preset and map-layer controls;
* **frames** (opaque, never blurred): table frames, captions and scroll regions, map regions;
* **ambient**: exactly one `aria-hidden`, non-interactive, fixed element behind all content.

**What stays solid.** Every scientific value is painted on an opaque surface: table bodies and headers, charts, map and planetary views, histograms, route plots, inputs and selects. Glass frames them; it never sits behind a number a reader must trust.

**Visual rules.**

1. All colour derives from existing tokens through `color-mix()`; `glass.css` contains no hex, `rgb()` or `hsl()` literal and no new palette value.
2. The ambient backdrop is three or four static radial fields of `--accent` (blue), `--state-pending` (sky) and `--state-pass` (teal) at low strength. No violet or purple fields, no animation, no starfield or space imagery (X-07 stands), no particles.
3. Backdrop blur ≤ 24 px with saturation ≤ 1.6. Chrome ≈ 66 % opaque, panel frames ≈ 72 to 78 %, overlays ≈ 80 to 86 % (dark) and higher in light. Panels are dense enough that text contrast is judged on the painted pixels (rule 6).
4. Radii: listed surfaces and frames ≤ 14 px (panels 12, overlays 14); controls, badges and links remain ≤ 6 px.
5. Shadows: dark, below the element, negative spread, from `--glass-ink` (`--canvas` in dark, `--text-primary` in light, both near-black). Inset highlights are 1 px hairlines. No coloured shadow, no zero-offset halo, no text shadow.
6. **Text on glass is verified on painted pixels.** Computed colours cannot see blur or ambient light, so the audit renders a second frame with all glyphs transparent and measures every glass-backed text node against the real background samples (≥ 4.5:1, ≥ 3:1 for large text). This is stricter than the computed check used for flat surfaces.
7. No geometry changes: glass adds paint only (background, border colour, shadow, radius), so layout-shift and spacing gates are unaffected. No colour transitions are added; controls keep `transition: none` so audits never measure mid-transition.
8. **Fallbacks are mandatory** and enforced by the scanner: `@supports not (backdrop-filter …)` and `prefers-reduced-transparency: reduce` restore the opaque surfaces and hide the ambient layer; `forced-colors: active` uses system colours; print is flat and ink-free.

**Enforcement.** `scripts/ui/forbidden_scan.py` exempts `glass.css` only from the decorative-effect and large-radius rules and validates it structurally against the contract (listed selectors only, blur and radius limits, radial gradients on the ambient element only, dark non-halo shadows, token-derived colours, required fallbacks); every other stylesheet is still scanned in full. Audit check C10 allows glass only on listed selectors within the contract limits and requires the ambient layer to be unique, hidden from assistive technology and non-interactive. `tests/contracts/ui/test_glass_contract.py` damages the stylesheet in 19 ways and removes each fallback, and requires the scanner to fail every time.

## 6. Colour

Source of truth: `team guides/Aradhya/design/tokens.json` (both themes, 150 verified contrast/distinctness checks by `design/verify_tokens.py`). Summary:

| Role | Dark | Light | Use |
| --- | --- | --- | --- |
| `canvas` | `#0B0F14` | `#F4F6F9` | page background |
| `surface-1/2/3` | `#11171E / #171F29 / #1F2935` | `#FFFFFF / #EEF1F5 / #E2E7EE` | panels / headers+inputs / hover+selected |
| `border-subtle / strong` | `#2A3646 / #62748B` | `#D3DAE3 / #7A8798` | dividers / control edges |
| `text-primary / secondary / tertiary` | `#E8EDF3 / #AAB6C5 / #8997A9` | `#111A24 / #3B4857 / #566475` | body / labels / captions & units |
| `accent`, `accent-strong`, `on-accent` | `#5AAEFF`, `#2F7FD6`, `#06101C` | `#0B5CC2`, `#094A9E`, `#FFFFFF` | links, focus, selected edge; primary button fill (`accent-strong`, label `on-accent`) |
| `focus-ring` | `#8CC8FF` | `#0B5CC2` | 2 px outline, 2 px offset, never removed |
| `state-pass / partial / fail / gap / unknown / pending` | green `#3FBF7F`, amber `#E2A93B`, red `#F26B66`, violet `#A98BFF`, slate `#9AA7B8`, sky `#6FB7E8` | darker AA counterparts | status text/icon/edge |
| `state-*-bg` | very dark tints | very light tints | status badge/row band background |

Rules:
* A **status colour never appears alone**: always with its glyph (§9.2) and its word.
* Row/cell tinting uses `state-*-bg` at full strength (no opacity tricks) and the text on it uses `text-primary` (≥ 7:1, rule S3) — a 3 px left border in the state colour is the strong signal, the tint is secondary.
* `accent` is for interaction only (links, selected tab underline, focus). It is **never** used for a scientific state.
* **Charts:** series use the Okabe–Ito set (tokens `categorical_okabe_ito`), never the state colours, and each series has a distinct marker/dash plus a direct label (§10).
* **Greyscale test:** every screen screenshotted in greyscale (`filter: grayscale(1)`) must still distinguish all six states (glyph shapes differ; §9.2). The visual audit does this (VIS-08).
* No opacity-based text colours; text uses the three text tokens only.
* Map and raster colour ramps for scientific layers (slope, elevation, illumination) must be perceptually uniform and CVD-safe (viridis/cividis-style from `d3-scale-chromatic`, or an implementation of the same stops committed as data); labelled legend with units and min/max; never rainbow/jet.

## 7. Typography

* **Fonts (self-hosted, OFL):** `Inter` (variable, weights 400/500/600) for UI; `IBM Plex Mono` (400/500) for identifiers, hashes, IDs, coordinates in code-ish contexts, JSON, logs. Installed from `@fontsource-variable/inter` (or `@fontsource/inter`) and `@fontsource/ibm-plex-mono`; imported in `main.tsx`; `font-display: swap`; **no request to any font CDN**; fonts live in the build output (`UIX-10` also asserts the built `dist` has no external URLs).
* Keep Inter's default OpenType features, and set `font-variant-numeric: tabular-nums` globally on tables, badges, quantities and charts; `font-variant-numeric: slashed-zero` on mono.
* **Scale** (px / line-height / weight / use). Nothing below 12 px.

| Token | Size / LH | Weight | Use |
| --- | --- | --- | --- |
| `text-2xl` | 24 / 32 | 600 | page title (one per view) |
| `text-xl` | 20 / 28 | 600 | panel group title, passport headline |
| `text-lg` | 16 / 24 | 600 | panel title |
| `text-md` | 14 / 20 | 400 (500 emphasis) | **body, table cells, inputs, buttons** |
| `text-sm` | 13 / 18 | 400 | secondary text, helper text |
| `text-xs` | 12 / 16 | 500 | captions, units, column headers, badge labels |
| `mono-md` | 13 / 20 | 400 | hashes, ids, coordinates, JSON, receipts |

* Headings: sentence case, no trailing punctuation, ≤ 60 characters. One `h1` per route. Heading levels never skipped.
* Letter-spacing 0 for body. Column headers and status labels in `text-xs` may use `letter-spacing: 0.04em` and `text-transform: uppercase` if ≤ 3 words. Never uppercase a sentence.
* Max line length for prose (assumption text, claim text, passport narrative): 72 ch.
* Truncation: single-line truncation with ellipsis only where the full value is available by tooltip **and** by focusable expand; never truncate numbers, units, statuses or hashes' copy value.

## 8. Quantities, units, time, identifiers (formatting contract)

Implemented once in `src/format/*` and used everywhere; tested by `format/*.test.ts` (UIX-05).

| Thing | Rule | Example |
| --- | --- | --- |
| Number + unit | Value, **non-breaking space** (U+00A0), unit; unit in `text-tertiary`, same baseline; unit in the **column header** for tables (cells hold only numbers) | `230 m`, `26.0 Wh` |
| Precision | Per quantity from a single table in `format/quantity.ts`: lengths in m 0 dp (≥ 1000 m ⇒ km 2 dp), energy Wh 1 dp, slope deg 1 dp, fractions as `0.82` (3 s.f., **not %** unless the field is a coverage *fraction of area*, shown as `82 %` with NBSP), speeds m/s 2 dp, mass kg 1 dp, time s/min, temperature K 0 dp | |
| Signs | Use the true minus `−` (U+2212); `+` for deltas | `−0.4`, `+12 Wh` |
| Thousands | Thin separator via `Intl.NumberFormat('en-US')` | `12,480` |
| Ranges | En dash, units once | `5.0–12.5 deg` |
| Null | Text `Unknown` in `unknown-value` (`text-secondary`, italic **not** used); never `0`, `NaN`, `-`, `N/A` | |
| Support/scale | Next to every measured value, a second line or tooltip chip `60 m cell · 98 % valid` | |
| Margin | Signed with unit and direction word on benchmarks | `margin +20 Wh (pass)` |
| Timestamps | ISO‑8601 **UTC** `2026-11-07 14:32:05Z` in mono `text-sm`; relative time (`3 min ago`) only as secondary text with the absolute value in `title`; a `<time datetime>` element always | |
| Durations | `1 h 04 min`, `38 s`, `120 ms` | |
| Coordinates | Signed decimal degrees, 5 dp, with `°` and axis letters: `34.05123° N, 118.24501° W`; body-fixed coordinates for Moon/Mars labelled with the frame | |
| Hashes / ids | Mono `mono-md`, show first 12 hex characters + `…`, full value in `title` and copied by `copy-hash` button (`aria-label="Copy SHA-256"`; success text "Copied" in place for 1.5 s, not a toast) | `9f2c1ab04e7d…` |
| Counts | Always with denominators | `12 of 14 requirements evaluated` |
| Evidence strength | The words HIGH / MEDIUM / LOW with the dimension, never a number | |
| Percent-similarity | **Never** shown anywhere | |

## 9. Component specifications

All components live in `src/components/ui|evidence|operations`, are typed, documented by a living style page `/__styleguide` (**dev & mock only**, excluded from the production bundle by the same plugin guard) that renders every component in every state in both themes — this page is the primary target of the visual audit (§20 VIS-12) and a deliverable.

### 9.1 Buttons
* Heights: 32 default (28 compact, 40 comfortable, 44 coarse pointer); padding 0 12 px; radius `--radius-2`; label `text-md` 500, sentence case, ≤ 3 words, verb first (`Build fingerprint`, `Accept contract`, `Select candidate`).
* Variants: **primary** (one per region; fill `accent-strong`, label `on-accent`, hover lighten one step in-token, pressed darken), **secondary** (transparent, 1 px `border-strong`, label `text-primary`), **tertiary/ghost** (no border; hover `surface-3`), **danger** (secondary style with `state-fail` text/border; used for Cancel run, Reject), **icon button** (32×32, tooltip + `aria-label`).
* States: default, hover, focus-visible (2 px `focus-ring`, 2 px offset), active, **disabled** (reduced contrast but still ≥ 3:1 for the text; the *reason* is always available: a `…-disabled-reason` element or `aria-describedby` text; never a silent dead button), loading (inline 14 px spinner replacing the leading icon + label stays; button remains `aria-busy` and non-clickable; no layout shift).

### 9.2 Status system (the most important component)
`StatusBadge` renders **shape + glyph + word**, 20 px tall, `text-xs` 600, padding 0 8 px, 1 px border in the state colour, fill `state-*-bg`, text and glyph in the state colour (rule S2 ≥ 4.5:1). Glyph set (custom inline SVG, 12 px, 1.5 stroke, **distinct silhouettes**):

| State | Word | Glyph | Silhouette |
| --- | --- | --- | --- |
| PASS | `Pass` | check mark in a circle | round |
| PARTIAL | `Partial` | half-filled circle | round, half |
| FAIL | `Fail` | cross in a square | square |
| GAP | `Gap` | dashed-outline diamond with gap | diamond, dashed |
| UNKNOWN | `Unknown` | question mark in a hexagon | hexagon |
| PENDING | `Pending` | clock (static; spinner only while a request is actually in flight) | circle w/ hands |
| INCONCLUSIVE (test result) | `Inconclusive` | triangle with bar | triangle |
| BLOCKED / ALLOWED / LIMITED (publication) | `Blocked` / `Allowed` / `Limited` | shield-cross / shield-check / shield-half | shield |

A status always has: visible word, glyph, `aria-label="Status: Gap"`, `data-status`. Matrix cells and table rows add a 3 px leading edge in the state colour.

`ModeBadge` (`mode-badge`): mono `text-xs`, uppercase (`LIVE` / `REPLAY` / `SYNTHETIC`), 1 px border `border-strong`, fill `surface-2`. **Mode is not a verdict, so it never uses a state colour**: all three use neutral chrome with a distinct 8 px glyph (live = solid dot, replay = rewind glyph, synthetic = hollow square) so mode can never be mistaken for a result. Persistent on every run screen, in print, in exports.

### 9.3 Inputs and forms
Anatomy: label above (`text-sm` 500), control (32 px, `surface-2`, 1 px `border-strong`, radius `--radius-2`), helper text below (`text-xs` secondary), error text (`state-fail`, glyph + text, `role="alert"` on submit failure, `aria-describedby`). Focus: 2 px ring. Numeric inputs: right-aligned mono-tabular, unit suffix inside the control (non-editable, `text-tertiary`), step/min/max, parse tolerant but display normalised on blur. Select: Radix Select styled; no native `<select>` (X-13). File input: styled drop zone with filename, size, `Replace` and `Remove`, and validation result below. Required marker: the word "Required" in `text-xs`, not an asterisk-only. Form layout: single column ≤ 480 px width per field group; two-column only for paired min/max or bbox edges.

### 9.4 PROVE IT
The one oversized control: 48 px high, `text-lg` 600 uppercase `PROVE IT` with a play-in-square glyph; fill `accent-strong`; sits in a bordered "Experiment" panel with the benchmark preview (§10 S10) directly above it. Disabled state shows `prove-it-disabled-reason` in the panel (plain sentence naming the missing prerequisite). While running it becomes a stepper (Design → Search → Verify → Diagnose), each step with state glyph and elapsed time. It is never animated while idle.

### 9.5 Tables (matrix and lists)
* Header: `surface-2`, `text-xs` 600 uppercase ≤ 3 words **or** sentence case, sticky (top 0 within its scroller), 1 px bottom border `border-strong`. Units in header (`Distance (m)`).
* Rows: height per density; zebra **off** (use 1 px `border-subtle` dividers); hover `surface-3`; selected row 3 px leading `accent` edge + `surface-3`; focus row 2 px ring inset.
* Alignment: text left, **numbers right** (tabular), status centre-left as badge, actions right. Column min-widths set; text wraps (no mid-word clipping); numeric cells never wrap.
* Sticky first column with its right border when horizontally scrolled; scroll shadows (`surface-3` 1 px inset line) indicate overflow.
* Sorting: explicit header buttons with `aria-sort`; sorting never recomputes values; sorted-by indicator is a glyph + hidden text. Stable ordering by default (documented sort key) — no re-sorting while the user reads (X-25).
* Empty: one-row empty state inside the table frame (§9.9). Loading: skeleton rows of the same height (4 rows). Error: inline `error-panel` inside the frame, header retained.
* Virtualize > 200 rows (TanStack Virtual) with proper `aria-rowcount`.
* **Qualification matrix**: requirements as rows, candidates as columns (toggle "By requirement / By candidate"). Cell = `qual-cell`: state glyph + word (`text-xs`) + the primary measured value right-aligned when space permits, 3 px state edge, min cell 112×44 px. Header cells show candidate name, origin label, and the count `n PASS · n FAIL · n GAP · n UNKNOWN` (text, with glyphs). A pinned footer row "Hard-constraint failures: n". Hidden-row count is shown as text "3 rows hidden by filter — Clear".

### 9.6 Evidence drawer
352 px right drawer (overlay at < 1440), `surface-1`, 1 px left border, overlay shadow. Header: evidence id (mono, copy button), type badge, close (Esc). Body sections as collapsible `<details>` with `text-lg` headings: **Claim**, **Measured value & unit**, **Support / scale / valid fraction**, **Source & provenance** (dataset id, version, hash, licence/attribution), **Algorithm** (id, version, parameters hash), **Receipt / digest** (mono), **Limitations**, **Linked requirement(s)**. Focus moves into the drawer on open, returns to the invoking `evidence-link` on close; background is not inert-blocked (it is a drawer, not a modal) but `Esc` closes. Never contains model-authored free text presented as measurement.

### 9.7 Banners (`run-state-banner`, `connection-indicator`, mock banner)
Full-width of the working area, 40 px (28 px for mock), `surface-2` with a 3 px leading edge. Run-state banner shows `State · Stage · elapsed` left and the **scientific outcome** (separate badge) right — two distinct pieces (architecture 16). Error banners use `state-fail-bg` + glyph + message + remediation; blocking dependency banners include `btn-retry-dependency`. Connection indicator: 8 px dot + word (`Connected` / `Reconnecting 4 s` / `Offline`); states differ by glyph shape too.

### 9.8 Tabs and navigation
Run tabs (`run-nav-tab`): 40 px, underline-style, `text-md` 500; active = 2 px `accent` underline + `text-primary`; inactive `text-secondary`; each tab may show a count chip (`text-xs`, `surface-3`) and a state dot (shape + colour). Arrow keys move between tabs (Radix Tabs); tab content is lazy but keeps scroll position. Breadcrumb in header, never more than 3 segments.

### 9.9 Empty, error, loading states (designed, not defaults)
* **Empty-with-reason** (`empty-state[data-reason]`): 48 px muted glyph (neutral), one-sentence title (`text-lg`), one-sentence cause, optional action. Copy from the reason table in §14.3. Never an illustration.
* **Error panel** (`error-panel[data-error-code]`): `state-fail-bg`, glyph, title, human cause, `Request id` in mono with copy, `remediation-hint`, actions (`Retry`, `Copy details`). No stack traces.
* **Loading:** skeletons use `surface-2` blocks with a 1.2 s subtle opacity pulse (disabled under reduced motion), exact final heights (CLS-safe). Spinners only inside buttons and for in-flight stage steps, always paired with text. Any wait > 2 s shows scoped text ("Computing qualification for 3 candidates — 12 s").

### 9.10 Dialogs, popovers, tooltips, toasts
* One dialog pattern (Radix Dialog): 480 px, focus trap, `Esc`, title + description + two buttons (secondary left, primary right; danger when destructive). Used for: change-body-clears-target confirmation, discard unsaved edits, cancel run.
* Tooltips: Radix, 300 ms delay, `text-xs` on `surface-3` with 1 px `border-strong`, max 280 px, never the only carrier of information needed to act (X-17); keyboard-focus triggers them.
* Toasts: allowed only for non-critical confirmations (≤ 4 s, bottom-left, `role="status"`). Results always have a persistent in-page record.

### 9.11 Timeline (operations drawer)
Rows `operation-row`: `text-sm`; columns `seq` (mono, right-aligned, 56 px) · time (mono `HH:MM:SS`) · role badge (Planner / Terrain engine / Verifier / Critic …, neutral badge) · summary sentence ("Terrain engine computed slope statistics for window A") · optional evidence link. Auto-scroll only when pinned to bottom; "Jump to latest" button appears otherwise. Never shows hidden reasoning, prompts or chain-of-thought.

### 9.12 Charts
Detailed in §10.5.

## 10. Screen design briefs (S01–S12 + shell)

For each: **first-glance hierarchy**, **layout**, **signature element**, **what must not appear**. Data and test ids remain per `08-MODULE-SPECIFICATION.md` §4.

* **S01 Mission & run home.** Opens into work: a left-aligned page title "Missions and runs", one primary `New mission` button, then two compact tables side by side at ≥ 1280 (stacked below): *Missions* (name, body badge, objective excerpt, updated), *Runs* (run name, `mode` neutral badge, **terminal state** and **scientific outcome as separate columns**, started, duration). A slim "Practice presets" strip lists the named presets (synthetic/replay/live) as rows, not cards. No hero, no illustrations, no marketing copy.
* **S02 Mission authoring.** Two-column: left a 480 px form in sections (Identity → Objective → Target region → Operating constraints) with sticky section anchors; right the **planetary panel** (body-aware) 1:1 with the bbox inputs. Autosave indicator (`save-indicator`) top-right of the form: glyph + `Saved 14:02:11Z` / `Saving…` / `Unsaved changes` / `Conflict — reload`. Body switch confirmation dialog states what will clear.
* **S03 Rover profile.** Form in a 3-column field grid with unit suffixes; right side a **profile summary card** (read-only, derived display of entered fields only — no inferred values) and an import panel with validation results as a table (field, value, status). Unknown values via an explicit `Unknown` segmented control per optional field.
* **S04 Fingerprint & freeze.** Pipeline header: stepper Fingerprint → Review → Accept → Start. Requirements table (id mono, dimension, observable, rule, unit, support, importance, scope, origin badge `Mission-stated / Derived / Assumed`) with row-expand for rationale; assumptions and conflicts as rows with severity edge, never cards-in-a-grid. `Accept contract` shows the revision/hash (mono) it accepts, adjacent to the button. Scenario/mode selects in a bordered "Run configuration" panel with availability notes inline.
* **Run shell.** Exactly §5.2. Pinned revision badges (`Contract rev 3 · 9f2c1ab0…`, `Rover ARES-1 rev 2`) in the header cluster.
* **S05 Target.** Left: planetary panel with the layer panel and legend; right/below: metrics table (metric · value · unit · support · valid %) and slope histogram (§10.5) with its adjacent data table. Point inspect popover distinguishes "Display pixel" from "Analysis cell". Unavailable dimensions as empty-state rows with reason code text.
* **S06 Analogs.** Map (60 %) + candidate list/table (40 %); **list is the primary object**, map the secondary view. Columns: rank (labelled "Screening order"), name, origin label, window, screening status; excluded windows in a separate collapsed section "Excluded and not detailed (n)" with reasons. Selection syncs list ⇄ map ⇄ URL.
* **S07 Qualification.** The matrix (§9.5) is the whole screen; critic cards as a right-hand list with severity edge; history popover "Previous → Current" with timestamps; review panel inline under the row when a review is pending. This is the "money screen": it must look like a precise engineering table, not a dashboard.
* **S08 Compatibility.** Table: metric · rover value · required · assessment badge; a persistent `Preliminary` badge in the table caption until verification exists.
* **S09 Portfolio.** Coverage table (requirement · covering candidate(s) · coverage badge) + residual gaps list; co-location explanation as one paragraph max 72 ch; never a single big PASS.
* **S10/S11 Test lab.** Three horizontal bands: (1) **Experiment** panel (benchmark preview table + PROVE IT + stepper), (2) **Attempts** (attempt rows as a vertical timeline: attempt n, strategy, parent, changed elements, result badge, receipt digest; replan diff as a two-column before/after table), (3) **Evidence**: benchmark rows (constraint, rule, measured, unit, margin, status), failure category with proof scope, route playback (map + transport controls: play/pause, step, scrub, speed 1×/2×/4×, readout of time/distance/Wh, label "Modeled route playback"). Headline sentence at the top ("Modeled test failed on attempt 1; passed on attempt 2") — plain text, one line.
* **S12 Passport.** A document view: centred 880 px "sheet" on `canvas` (screen) matching the print layout (§17) — headline, mode badge, claims (exact permitted statements), assurance badge, requirement table, attempts, GAP/UNKNOWN lists, manifest digest, export bar (`export-btn`, `export-status`, `file-digest` with copy). Draft preview carries a full-width banner and a "DRAFT" label (no rotated watermark) in the header bar.
* **Operations drawer.** §9.11.

### 10.5 Chart standards
d3 primitives rendered as accessible SVG; **every chart has an adjacent data table** (toggle `Chart | Table`, both reachable) and a text summary line. Anatomy: chart title (`text-lg`), subtitle with unit & support, axes with unit labels, light gridlines (`border-subtle`, horizontal only for histograms), tick text `text-xs` `text-secondary`, no chart junk (no 3D, no shadows, no animated entry), direct series labels (legend only when > 3 series), reference lines (requirement threshold) as a dashed `text-primary` line **with a text label** ("Max slope 8.0 deg"), bars with 1 px gap and square corners, markers with distinct shapes, hover/focus tooltip listing exact values (keyboard reachable via arrow keys), tabular numerals, min height 200 px, responsive via ResizeObserver with stable aspect, colours from Okabe–Ito for series and state tokens only for threshold-pass/fail overlays together with glyphs. Axis starting values honest (bars start at 0).

## 11. Maps

Design of map chrome (behavior is in [18](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md)): neutral basemap from tokens (`map-land`, `map-water`, `map-graticule`), 1 px graticule, no decorative terrain textures. Controls (zoom, reset north, layer panel, fullscreen) are 32 px square tokenised buttons grouped top-right with 4 px gaps, on `surface-1` with 1 px border — never default MapLibre light controls. A **scale bar** and **coordinate readout** (mono `text-xs`, bottom-left, on `surface-1` at full opacity) and a one-line **attribution** (bottom-right, text only, from the manifest) are always visible. Layer panel: checkbox rows with name, source badge (`Synthetic` / `Replay` / `NASA` per manifest), opacity slider (keyboard accessible), legend swatches with units and min/max. Candidate extents: 2 px outline in `accent`, selected 3 px + corner ticks; excluded windows dashed `text-tertiary` with label on focus. Routes: waypoints numbered squares, legs 2 px `text-primary` with a 1 px halo in `canvas` for contrast; **violations** drawn in `state-fail` with glyph markers and listed in the table (never colour only). Selected feature announces name + status in an `aria-live` region. WebGL failure shows a bordered notice "Map unavailable (WebGL not supported). The candidate list and tables show the same information." with the list focused.

## 12. Motion

Allowed: opacity/position changes of drawers and popovers 160 ms `--ease`; hover/focus colour transitions 100 ms; skeleton pulse; stage-stepper state change cross-fade 100 ms; route playback (user-controlled). Everything else is static. `prefers-reduced-motion: reduce` ⇒ all transitions ≤ 1 ms, skeleton static, **no playback autoplay**. Banned: bouncing, shaking, confetti, typewriter text, count-up number animations, parallax, auto-scrolling marquees, looping decorative animation.

## 13. Interaction details

* **Keyboard.** Every control reachable; logical order; visible focus; shortcut help overlay on `?` (a dialog listing). **No chord navigation** (it collides with screen readers). Implement only: `/` focus the primary search/filter, `[` and `]` previous/next run tab, `e` toggle evidence drawer, `o` toggle operations drawer, `?` shortcut help, `Esc` close the top-most drawer/dialog. Shortcuts are disabled while typing in an input and are listed in the help dialog.
* **Focus management.** Route change moves focus to the page `h1` (tabindex −1); drawers return focus to invoker; errors move focus to the error summary on submit.
* **Selection persistence.** URL holds `?candidate=`, `?tab=`, `?req=` so views are linkable.
* **Hover is never required.** Every hover affordance has a focus/click equivalent.
* **Latency feedback.** 0–100 ms: immediate state; 100 ms–2 s: inline busy state; > 2 s: scoped text with elapsed time.
* **Selection** inside tables uses the checkbox/row-click pattern with `aria-selected`; destructive/bulk actions require confirmation.

## 14. Content design (copy)

### 14.1 Voice
Plain, precise, neutral engineering English. Short sentences. Name the actor ("Terrain engine computed…", "Verifier rejected…"). State facts and uncertainty; no hype, no exclamation marks, no emoji, no second-person flattery. Sentence case everywhere. Use the product's defined terms exactly: *Mission contract*, *Analog window / candidate*, *Qualification*, *Gap* (no usable data), *Unknown* (data exists but cannot decide), *Inconclusive* (test result), *PROVE IT*, *Analog Passport*, *Evidence*, *Receipt*.

### 14.2 Good vs bad

| Bad | Good |
| --- | --- |
| "Awesome! Your analog is ready! 🚀" | "Run complete. 1 of 2 candidates qualified; 1 test failed on attempt 1 and passed on attempt 2." |
| "Oops, something went wrong." | "The verifier could not start: provider authentication failed. Request id 7c1e…  Check `OPENAI_API_KEY` and retry." |
| "Most Mars-like site: 94 %" | "Terrain screening order (not a similarity score): 1 Practice B, 2 Practice A." |
| "AI-powered insight" | "Critic note (severity: high): requirement R-SLOPE has valid coverage of 61 % (min 80 %)." |
| "No data 😢" | "Gap: no elevation coverage for window C in this dataset (reason NO_COVERAGE)." |
| "Loading…" | "Computing qualification for 3 candidates — 12 s" |
| "N/A" / "—" | "Unknown" |
| "Success!" (toast) | persistent row "Evidence export ready · CSV · sha256 3ab4…" |
| "Click here to learn more" | "View evidence EV‑0042" |
| "Seamless" / "Unlock" / "Supercharge" | (delete) |

### 14.3 Required reason copy (used by `empty-state[data-reason]`)
`NO_COVERAGE` "No data covers this window for this dimension." · `NOT_REQUESTED` "This dimension is not part of the accepted contract." · `AWAITING_DATASETS` "Scenario unavailable until datasets are installed." · `SEARCH_LIMIT` "Search limit reached. This is not proof that no route exists." · `ROUTE_NOT_VERIFIED` "Depends on a verified route. Run PROVE IT." · `ROVER_REQUIRED` "Rover verification unavailable: no rover profile selected." · empty portfolio "No candidate covers any remaining requirement." Wording may be extended but never contradicts the above.

### 14.4 Microcopy rules
Button labels verb + object. Errors name cause + consequence + next step. Dates absolute. No ellipsis-only truncation of key terms. Every disabled control explains itself. Confirm dialogs state exactly what will be lost/changed.

## 15. Accessibility (additional to 17/18)
WCAG 2.2 AA minimum, AAA for body text contrast in `tokens.json`. Target size ≥ 24 px (2.5.8) — we use 32/44. Focus not obscured (2.4.11): sticky headers/drawers must not cover a focused element (scroll-padding-top = header + table header height). Landmarks: `header`, `nav`, `main`, `aside`, `footer`; skip link first in tab order. Tables use real `<table>` semantics (`<th scope>`); the matrix may use ARIA grid only if arrow-key navigation is implemented and tested. Live regions: stage changes and terminal results `aria-live=polite`, errors `role=alert`. Language `lang="en"`. Zoom 200 % and text spacing overrides must not clip (visual audit runs with a text-spacing stylesheet: line-height 1.5, paragraph spacing 2em, letter-spacing 0.12em, word-spacing 0.16em).

## 16. Branding, attribution and legal text
Product name text "AnalogForge" + the plain ring-and-dot mark. **No NASA insignia, no NASA-style lookalike marks, no "official/approved" language.** Footer line (shell and passport): "AnalogForge — mission-conditioned analog qualification. Data attributions: <from manifest>. Not a NASA product; no endorsement implied." Synthetic data is always labelled "Synthetic dataset — not real planetary or Earth measurements". Third-party licences in `analogforge/apps/web/THIRD-PARTY.md` and an in-app `/about` route (table: component, version, licence).

## 17. Passport and print design
The passport HTML (renderer) and the on-screen passport view share one stylesheet intent: A4/Letter portrait, 18 mm margins, font stack `system-ui, "Segoe UI", Roboto, sans-serif` (the pure renderer must stay self-contained, offline and deterministic: it embeds no fonts and fetches none; the on-screen passport route may use Inter). Structure: header band (title, mode badge, draft banner if draft, run/contract/rover revision, date UTC) → **headline** (one sentence from the 4 headline cases) → assurance statement block → requirement table (status glyph + word, value, unit, evidence id) → attempts table → GAP/UNKNOWN lists → manifest digest + file digests in mono → attributions → page footer with page `n of N` (CSS counters) and the digest. Print CSS: light tokens, no backgrounds except status tints (printed also with glyph+word so greyscale prints work), `break-inside: avoid` on rows, running table headers, no interactive elements. Status shapes must be inline SVG or Unicode-free CSS shapes (no emoji, no font-dependent glyphs).

## 18. Design tokens → code contract
* `apps/web/design/tokens.json` = copy of `team guides/Aradhya/design/tokens.json` (byte-identical unless a recorded decision changed a value *and* `verify_tokens.py` still passes).
* `apps/web/src/styles/tokens.css` = output of `scripts/ui/gen_tokens_css.py` (byte-identical, UIX-12).
* `scripts/ui/verify_tokens.py` = copy of the verifier (byte-identical).
* Components consume **only** CSS variables from `tokens.css`; TypeScript never contains colour literals except in `maps/*.ts` for MapLibre paint expressions, which read the variables via `getComputedStyle` at runtime and update on theme change.

## 19. Component inventory (must exist and be shown on `/__styleguide`)
`AppShell, AppHeader, ModeBadge, ConnectionIndicator, RevisionBadge, StatusBadge, StatusGlyph, Button, IconButton, Input, NumberInput, Select, Segmented, FileDrop, FormField, Table, MatrixCell, SortHeader, Tabs, Banner, MockBanner, EmptyState, ErrorPanel, Skeleton, Dialog, Drawer, Tooltip, Toast, Popover, CopyHash, Mono, Quantity, Timestamp, Hash, Stepper, Timeline, Chart(Histogram|Line|Bar), DataTableToggle, LayerPanel, Legend, ScaleBar, CoordinateReadout, Attribution, KbdHint, VisuallyHidden`. Each: all states, both themes, density variants, RTL not required.

## 20. Visual QA — acceptance (full procedure in `team guides/Aradhya/10-DESIGN-SYSTEM-AND-VISUAL-QA.md`)

Machine checks (`scripts/ui/visual_audit.mjs`, gate UIX-13) and human/agent review (rubric, gate DR-01..). Catalog:

| ID | Check |
| --- | --- |
| VIS-01 | `tokens.json` passes `verify_tokens.py` (150 checks); `tokens.css` regenerates byte-identically; light and dark both render all screens |
| VIS-02 | Fonts: only Inter and IBM Plex Mono load; computed `font-family` of every visible text node resolves to one of them (or a mono fallback); zero requests to non-`localhost` origins; fonts present in `dist` |
| VIS-03 | No hex colour literals in `src/**/*.{css,tsx,ts}` outside `tokens.css`, `maps/`, and test files; no gradient, `backdrop-filter`, text shadow, box shadow or `border-radius` > 6 px (except 50 % dots) outside the glass layer; the glass layer (`glass.css`) satisfies the structural contract of §5.5; no emoji codepoints, no `Lorem ipsum`/`TODO` visible text |
| VIS-04 | Every visible text node ≥ 12 px; body text ≥ 13 px; computed text/background contrast ≥ 4.5:1 (≥ 3:1 for large/non-text) on the rendered pixels' backgrounds (axe `color-contrast` + custom sampler for canvas/map overlays) |
| VIS-05 | 4 px grid: for every card/panel/table cell/control, computed margin/padding/gap/width/height in `{0} ∪ 4k px` except an explicit allow-list (1 px borders, 2 px focus, 3 px state edge, hairlines) |
| VIS-06 | No horizontal page overflow at 1920×1080, 1440×900, 1280×800, 1024×768, 768×1024, 390×844; no element overlapping another interactive element; no clipped text (`scrollWidth ≤ clientWidth` unless `overflow` is intentional + labelled) |
| VIS-07 | Tap/click targets ≥ 24×24 px (≥ 44×44 at `pointer: coarse`); focus ring visible (≥ 3:1) on every focusable element reached by Tab on each screen; focus never obscured |
| VIS-08 | Greyscale screenshot (CSS filter) of the qualification matrix, test lab and passport: the six states remain distinguishable — test: each state's glyph SVG path hash is unique and word present; plus pixel-level silhouette distinctness ≥ threshold defined in the audit script |
| VIS-09 | Numeric alignment: in every table, numeric columns are right-aligned and `font-variant-numeric: tabular-nums` computed; no `NaN`/`undefined`/`null`/`[object Object]` text anywhere; null renders `Unknown` |
| VIS-10 | CLS ≤ 0.02 on route load and on data arrival for S01, S06, S07, S10, S12 (PerformanceObserver) with mock latency 300 ms |
| VIS-11 | Console clean: no errors/warnings (React key, a11y, deprecation), no failed requests, during J01–J13 |
| VIS-12 | `/__styleguide` renders every component in §19 in every state, both themes, 3 densities, without axe critical/serious; its screenshots are committed under `apps/web/docs/design-review/` |
| VIS-13 | Screenshot catalog: S01–S12, run shell, empty/error/loading/disabled states, dialogs/drawers in both themes at 1440×900 and 390×844 are produced to `out/visual/` with a manifest (name, viewport, theme, sha256); the review rubric is filled from them |
| VIS-14 | Print: passport route printed to PDF (Playwright `page.pdf`) has no clipped tables, shows mode + headline + digests on page 1, uses light tokens, and has page numbers |
| VIS-15 | Keyboard walk of the S06→S07→evidence→S10 path with screenshots at each focus stop shows a visible ring; `?` help lists exactly the shortcuts of §13 |
| VIS-16 | Reduced motion: with `prefers-reduced-motion`, computed `transition-duration` ≤ 1 ms for all, no autoplay |
| VIS-17 | Text-spacing override stylesheet (WCAG 1.4.12) causes no clipped or overlapping content |
| VIS-18 | The production build contains no `/__styleguide`, no `msw`, no mock banner, and no external URLs |
| VIS-19 | Glass contract (§5.5): the scanner fails every one of the 19 damaged copies of `glass.css` and each removed fallback; `[data-allowed=ambient-canvas]` is unique, `aria-hidden` and non-interactive; C10 reports backdrop, gradient, shadow or radius outside the contract |
| VIS-20 | Text on glass: every glass-backed text node meets 4.5:1 (3:1 large) against the glyph-free rendered background in both themes at all six viewports; reduced-transparency and forced-colors renderings show opaque surfaces |

**Design review rubric (human or reviewer-subagent; each criterion scored 0–4, all ≥ 3 and mean ≥ 3.5; any 0–1 is a blocker):** (1) hierarchy — status is the loudest thing; (2) restraint — colour only for state; (3) typography — scale, alignment, numerals; (4) density & spacing rhythm; (5) tables — scannable, aligned, units; (6) states — empty/error/loading/disabled are designed; (7) copy — plain, precise, no hype; (8) consistency across screens; (9) map & chart integrity; (10) accessibility feel (focus, contrast, keyboard); (11) "would a crew member trust this?" credibility test; (12) absence of every X-xx slop item. Reviewers must cite screenshot filenames and concrete defects with element selectors, not general praise.

## 21. Anti-gaming
The visual audit may not be satisfied by: disabling checks, allow-listing selectors wholesale, scoping tests to hand-picked elements, hiding content with `display:none` to dodge overflow, or lowering thresholds. `forbidden_scan.py` and the merging guide verify the audit script's thresholds equal this document's. The merging agent re-runs the audit itself on the merged build and performs its own hands-on design review (MRG-11).
