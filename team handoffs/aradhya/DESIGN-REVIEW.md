# Aradhya frontend design review

Round1 source: `8f3d883`. Full automated visual audit passed389reports/380screenshots with0findings and0skips; independent image review identified additional human usability defects. The reports below are preserved verbatim. No passing score was authored by the implementation agent.

## Round1 reviewer prompts

Each fresh reviewer received only architecture41, out/visual/screens.md and its images, the exact12-criterion0–4 rubric, and a distinct persona (mission-operations HMI; accessibility/typography; hostile slop detector). Each was required to open images, cite screenshot names and selectors, identify5defects or justify fewer, state evidence limits, and write an independent report without source/history/prior-score access.


## Round1 — Mission operations (verbatim)

# Independent mission-operations HMI review — round 1

**Decision: fail architecture 41 §20. Mean 2.42/4 (29/12); eight criteria below 3.** No 0–1 rubric blocker established; major defects prevent acceptance.

## Scope

Read only architecture 41, `out/visual/screens.md`, and catalog images. No source, previous reviews or history inspected. Images opened with `view_image`. Locators below are semantic selectors/specification names, not verified implementation CSS classes. Static images cannot prove keyboard navigation, tooltip availability, focus return, successful scrolling, CLS, elapsed-time behavior, numeric correctness, print, font metrics, ARIA or token/source compliance.

Images inspected (all `.png`, relative to `out/visual/`): S01 through S07 at 1440-dark-default; S08 through S12 at 1440-light-default; S06-1024-light-default; S07-390-dark-compact; S12-390-light-default; S03-390-light-default; loading-missions-1440-dark-default; error-rover-import-1440-light-default; evidence-drawer-1440-dark-default; operations-drawer-1440-light-default; shortcut-dialog-390-light-default; change-body-dialog-1440-dark-default; evidence-drawer-390-light-default; S09-composite-1440-dark-default; S08-rover-conflict-1440-light-default; S07-1440-light-compact; S10-1440-dark-comfortable; S05-1440-light-default; S12-1440-dark-default; loading-missions-390-light-default; error-rover-import-390-dark-default; operations-drawer-390-dark-default; evidence-drawer-1440-light-default.

This covers representative S01–S12, both themes, desktop/mobile, compact/default/comfortable table samples, overlays, loading and error states. It is not every catalog image.

## Exact §20 rubric

| # | Criterion | Score | Evidence |
|---|---|---:|---|
|1|hierarchy — status is the loudest thing|2|S11-1440-light-default: COMPLETED has no scientific outcome; PROVE IT dominates.|
|2|restraint — colour only for state|4|S07 and S12 both themes: neutral surfaces, semantic statuses, one interactive accent; no decorative colour excess.|
|3|typography — scale, alignment, numerals|2|S06-1440-dark-default: raw coordinate tails wrap over many lines. S03 repeats units.|
|4|density & spacing rhythm|2|S07 first row is roughly 210 px tall; mobile chrome consumes nearly a viewport before evidence.|
|5|tables — scannable, aligned, units|2|S08 Unknown comparison cells contradict known assessment values; S07 summary headers absent.|
|6|states — empty/error/loading/disabled are designed|3|Reasoned empty panels, scoped loading, persistent import error/remediation. Disabled behavior unverified.|
|7|copy — plain, precise, no hype|3|Candid scientific caveats; raw schema/reason strings and duplicated units reduce precision.|
|8|consistency across screens|3|Shared shell and table frames; portfolio/passport verdicts abandon shared glyph badges.|
|9|map & chart integrity|2|S06 six anonymous extents without visible scale/readout/attribution; S05 raster without visible value legend.|
|10|accessibility feel (focus, contrast, keyboard)|2|Good captured overlay focus rings, but mobile receipt measurements collapse to a sliver. Keyboard/contrast pass unverified.|
|11|“would a crew member trust this?” credibility test|2|Limitations are honest; compatibility contradiction and hidden completed scientific result undermine operational trust.|
|12|absence of every X-xx slop item|2|X-13 native file chooser, X-26 clipping, bounded X-28 state inconsistency remain visible.|

Total **29**, mean **2.4167 → 2.42**. Required all ≥3 and mean ≥3.5: not met.

## Severity-ordered concrete defects

### Major M1 — compatibility verdict contradicts comparison columns

Screens: `S08-1440-light-default.png`, `S08-rover-conflict-1440-light-default.png`.
Semantic selector: table caption “Rover versus selected candidate · Preliminary”; row `max_surface_slope_deg`; “Rover value”, “Required”, “Assessment” columns.

Both value columns say Unknown, but PASS prose says declared 18 deg/required upper 18 deg; conflict FAIL prose says declared 12 deg/required upper 18 deg. The display withholds known comparison data and presents a verdict alongside apparently unknown operands. This is a presentation contradiction; scientific calculation correctness is not established.

Fix: populate declared/required columns with 18.0 deg/18.0 deg and 12.0 deg/18.0 deg, or explicitly separate unavailable measured quantities from known declared limits. Keep Preliminary and declared-versus-observed scope. Audit required-capability and other rows too.

### Major M2 — lifecycle completion masks scientific outcome

Screens: `S11-1440-light-default.png`, `S12-1440-light-default.png`, `S10-1440-light-default.png`.
Selector: specification `run-state-banner`, Test lab h1/description, PROVE IT control.

Banner shows lifecycle, mode, connection and revisions, but no separate scientific outcome or stage/elapsed. Completed S11 has a large PROVE IT and “Waiting for committed evidence and an allowed PROVE IT action,” with no first-glance pass/fail/inconclusive headline. Publication Limited is distinct from scientific outcome.

Fix: show separate labelled lifecycle, stage/elapsed where applicable, and scientific-outcome badge. Put the required one-line attempts/result headline above the experiment panel; explain unavailable PROVE IT prerequisites beside that action. Static images do not show whether the button responds.

### Major M3 — mobile evidence measurements collapse

Screens: `evidence-drawer-390-light-default.png`; desktop comparators `evidence-drawer-1440-light-default.png`, `evidence-drawer-1440-dark-default.png`.
Selector: Evidence receipt drawer; table/section “Receipt metrics”.

At mobile width the table is approximately a 24 px sliver at y659–683: even its title is partly clipped. Desktop measurement/support are not visible there, while Limitations below remains readable. No visible disclosure or labelled scroller explains the tiny region. An unseen scrolling mechanism cannot be certified.

Fix: one vertical drawer-body scroller; metrics section must not flex-shrink; natural table height or explicit expanded disclosure. Verify actual value/support can be reached using normal vertical scrolling and keyboard focus at 390×844.

### Major M4 — maps lack visible interpretive essentials

Screens: `S06-1440-dark-default.png`, `S05-1440-dark-default.png`, `S05-1440-light-default.png`.
Selector: Earth candidate map figure/canvas; Mars target-region raster figure.

S06 shows six anonymous rectangles without visible selected-candidate distinction, labels, scale, coordinate readout or attribution. S05 raster shades have no visible numeric legend or layer/source key beside the data. Region extent and display-pixel instruction do not explain the measured shades. Some material might exist lower down; §11 requires essentials always visible.

Fix: anchor scale, labelled coordinate readout, attribution, source mode and scientific legend (quantity/unit/min/max) inside the map frame. Label candidate extents; selected extent gets corner ticks. Show an honest no-basemap/synthetic notice where appropriate; do not invent an unsupported scale.

### Major M5 — raw coordinate precision overwhelms candidate rows

Screens: `S06-1440-dark-default.png`, `S06-1024-light-default.png`.
Selector: Candidates table, Window column, “Practice grid-r0c0” row.

Floating tails such as −110.92999999999999 wrap over several lines. The 1440 split layout cuts the right columns with no visible horizontal-scroll instruction. This is component clipping, not proof of page overflow.

Fix: central coordinate formatting to required 5 decimal places, frame/axis labels and true minus; raw precision belongs in accessible detail. Prevent mid-token numeric wrapping. Reserve Window width; expose a labelled table scroller or responsive detail. Verify status/selection are reachable.

### Major M6 — matrix lacks summaries and uses excessive repeated cell content

Screens: `S07-1440-dark-default.png`, `S07-1440-light-compact.png`.
Selector: “Requirement qualification · by requirement” table candidate headers and specification `qual-cell`.

Headers show candidate/select button but omit required origin and PASS/FAIL/GAP/UNKNOWN counts. FINAL, machine reason, strength, support and disclosure repeat per cell, leaving roughly two requirements visible; compact density makes little difference. Rightmost candidate action/reason is clipped at scroller edge without an obvious overflow cue. Required leading state edge is not visible.

Fix: compact scan row for verdict/value/support; reason prose/details in explicit expansion. Add header origin/counts and failure summary/footer. Preserve evidence through expansion. Add obvious labelled overflow and sticky requirement column.

### Major M7 — portfolio/passport abandon state silhouettes

Screens: `S09-composite-1440-dark-default.png`, `S12-1440-dark-default.png`, `S12-1440-light-default.png`.
Selector: Portfolio Coverage cells; Passport Status/candidate cells visible at bottom.

Portfolio UNKNOWN/GAP are plain words; passport visible row reads plain “PASS · 02cc3dad”. Unlike matrix/compatibility, there is no shared shape+glyph+word badge. Text avoids colour-only meaning, but fast silhouette scanning and consistency are lost.

Fix: shared StatusBadge/StatusGlyph in every requirement/coverage row, including inline SVG for passport/print. Label candidate identity separately. Verify all six states in grayscale.

### Moderate D8 — browser file chooser leaks through

Screens: `S03-1440-dark-default.png`, `S03-390-light-default.png`, `error-rover-import-1440-light-default.png`.
Selector: “Import rover JSON” field, native `input[type=file]` chooser.

Browser-gray “Choose File” button/“No file chosen” remain visible. Selected state lacks size and explicit Replace/Remove. This directly violates X-13 and §9.3.

Fix: accessible real input behind a styled labelled drop/select zone, filename/size, Replace/Remove and associated validation. Preserve keyboard activation.

### Moderate D9 — mobile navigation consumes evidence viewport

Screens: `S07-390-dark-compact.png`, `S12-390-light-default.png`.
Selector: AppHeader, workspace navigation, `run-state-banner`, eight `run-nav-tab` items.

Four-row tab grid plus header/workspace/banner consume about 700 px before Qualification heading; no matrix cell visible. Passport outcome headline is likewise below first viewport. This is hierarchy cost, not evidence scrolling fails.

Fix: compact workspace menu, expandable revision metadata and labelled horizontal run-tab strip or compact selector. Keep lifecycle/scientific outcome visible and bring first evidence row into the initial viewport.

### Moderate D10 — clearing confirmation lacks labelled Cancel

Screen: `change-body-dialog-1440-dark-default.png`.
Selector: dialog “Change target body”, action row.

Only “Change body and clear region” and X are visible. Standard specifies secondary Cancel plus primary action; clearing uses ordinary accent rather than danger treatment. Loss copy itself is clear.

Fix: explicit Cancel, danger clearing action, retain exact scope statement. Escape/focus behavior unverified.

### Moderate D11 — labels duplicate units/storage names

Screens: `S03-1440-dark-default.png`, `error-rover-import-1440-light-default.png`.
Selector: labels “mass kg (kg)”, “max slope deg (deg)”, “battery wh (Wh)”, “nominal speed mps (m/s)”.

Fix: “Mass”, “Maximum slope”, “Battery capacity”, “Nominal speed”, each with one non-editable adjacent unit suffix; keep schema keys in import/advanced detail.

## All X-01–X-29 findings

Not observed means only inspected pixels, not source certification.

|Item|Disposition|
|---|---|
|X-01 emoji|Not observed.|
|X-02 gradients|Not observed; raster shades are data. Source expressions unverified.|
|X-03 glassmorphism|Not observed; drawers opaque.|
|X-04 glow/neon|Not observed; visible focus rings are functional.|
|X-05 excessive radii|Not observed; computed values unverified.|
|X-06 hero/marketing splash|Not observed.|
|X-07 decorative space imagery|Not observed.|
|X-08 feature grids|Not observed.|
|X-09 placeholders|Not observed. Named presets/Load example are domain content, not dummy labels.|
|X-10 proportional numerals|No definite visual violation; computed tabular feature unverified.|
|X-11 small/low-contrast text|No quantified finding; font-size/contrast measurements unverified.|
|X-12 shouty paragraphs|No definite finding; requirement identifiers/reason codes are identifiers.|
|X-13 browser defaults|**Open D8**: native file chooser. Native number spinner also visible; chooser is definite finding.|
|X-14 loading|Scope is named. More-than-2-second elapsed behavior and resolution unverified.|
|X-15 critical toasts|Not observed; temporal behavior unverified.|
|X-16 modal misuse|Not observed; displayed body-change and shortcut dialogs are allowed patterns.|
|X-17 unnamed icon buttons|Accessible names/tooltips unverified; icon-only rendering alone does not prove missing names.|
|X-18 mixed icons|No definite mismatch; dependency/stroke audit unverified.|
|X-19 fake similarity viz|Not observed; explicit non-similarity wording is good.|
|X-20 motion/carousels|Not observed; temporal behavior unverified.|
|X-21 off-grid spacing|Computed spacing unverified.|
|X-22 fonts/CDNs|No obvious display font; actual fonts/requests unverified.|
|X-23 NASA marks/official claims|Not observed.|
|X-24 hype|Not observed.|
|X-25 CLS/re-sort|Unverified from still images.|
|X-26 clipping/overflow|**Open M3/M5/M6**: receipt clipping, cut table columns without visible labelled affordance. No page-overflow claim.|
|X-27 black/white dark theme|Not visually observed; exact values unverified.|
|X-28 visual-language divergence|**Open, bounded M7**: semantic status rendering differs; shell otherwise consistent.|
|X-29 colour literals|Unverified; source deliberately not inspected.|

## Acceptance status

No score-defined blocker (0–1) established. **M1–M7 are open majors**, D8–D11 are open moderate defects. **X-13, X-26, bounded X-28 are open.** Eight rubric criteria below 3 independently fail acceptance. No behavior-, print-, source-, font- or timing-dependent gate is certified.

After fixes recapture the named views in both themes, including readable mobile receipt metrics and visible completed scientific outcome. Separately verify keyboard focus/return, table scrolling, loading elapsed-time behavior, grayscale states, contrast, numeric formatting and print with live/runtime evidence. Calm chrome does not compensate for contradictory comparison cells or hidden evidence.


## Round1 — Accessibility and typography (verbatim)

# Independent accessibility and typography review — round 1

Read only architecture 41, `out/visual/screens.md`, and the catalog images named below, opened with `view_image`. No source, prior reviews, history or runtime audit results were inspected. Product files were not changed. Selectors below are semantic remediation targets, not verified DOM class names.

**Verdict: FAIL. Scores total 32/48, mean 2.67/4. Six criteria fall below 3. No rubric-defined blocker (no score 0–1); five major defects require correction before acceptance.** This screenshot review does not certify WCAG compliance.

## Exact architecture 41 §20 rubric

| # | Criterion | Score | Rationale |
|---|---|---:|---|
| 1 | hierarchy — status is the loudest thing | 3 | Persistent banners are recognizable; S11 does not distinguish scientific outcome from completion. |
| 2 | restraint — colour only for state | 4 | Neutral surfaces, one accent and semantic badges in both themes. |
| 3 | typography — scale, alignment, numerals | 2 | Mono numeric alignment generally works; raw coordinate precision and fragmented timestamp undermine readability. |
| 4 | density & spacing rhythm | 2 | Desktop is orderly; mobile shell consumes approximately 700 px before qualification content. |
| 5 | tables — scannable, aligned, units | 2 | Right-aligned quantities; clipped inner table edges lack obvious overflow cues, matrix summaries are missing. |
| 6 | states — empty/error/loading/disabled are designed | 3 | Persistent import rejection and empty states have useful instructions; loading lacks specified final-shape skeleton rows. |
| 7 | copy — plain, precise, no hype | 3 | Honest scientific limits; raw schema names and duplicate unit labels persist. |
| 8 | consistency across screens | 4 | Shared shell, forms, badges, table treatment and overlays across S01–S12. |
| 9 | map & chart integrity | 2 | Histogram zero baseline and disclaimers are useful; candidate map lacks visible identities and coordinate formatting is poor. |
| 10 | accessibility feel (focus, contrast, keyboard) | 3 | Visible close-button focus rings and shape-plus-word badges; keyboard and exact contrast unverified. |
| 11 | "would a crew member trust this?" credibility test | 2 | PASS beside Unknown operands and completion without a visible test result weaken trust. |
| 12 | absence of every X-xx slop item | 2 | X-13 confirmed open; X-26 requires targeted verification. Source/runtime-only items cannot be cleared. |

## Severity-ordered concrete defects

### D01 — Major: verdict contradicts displayed operands

**Screenshot:** `S08-1440-light-default.png`. **Semantic selector:** compatibility table row `max_surface_slope_deg`, columns Rover value, Required, Assessment. Both operands say Unknown while assessment says PASS and prose declares 18 deg versus an 18 deg upper band. Required capability likewise has Unknown operands beside PASS. A reader cannot audit the verdict by scanning. **Fix:** display declared/required quantities from the same evidence as assessment, units in headers; if missing, show Unknown assessment and name the missing operand. This establishes a presentation contradiction, not an incorrect backend calculation. §§8, 10 S08.

### D02 — Major: completed test does not expose scientific result at first glance

**Screenshots:** `S11-1440-dark-default.png`, compared with `S12-1440-light-default.png`. **Semantic selector:** `run-state-banner`, Test lab heading/Experiment region. COMPLETED has no separate scientific-outcome badge or one-line modeled-test headline. Dominant PROVE IT is followed by “Waiting for committed evidence and an allowed PROVE IT action.” Passport later shows Qualified and Limited. **Fix:** show terminal state, stage/elapsed and separate scientific outcome in the banner, then latest modeled-test result headline and attempt/receipt link above Experiment. Explain rerun availability beside the action. Actual disabled behavior and attempts below the scroller remain unknown. §§9.7, 10 S10/S11.

### D03 — Major: raw coordinate precision wraps numbers across lines

**Screenshots:** `S06-1440-light-default.png`, `S06-1920-dark-default.png`. **Semantic selector:** Candidates table, Window column, Practice grid-r0c0 WGS84 extent. Longitude beginning `-110.92999…` continues across multiple lines, with inconsistent precision elsewhere. This bloats rows and invites misreading. **Fix:** normalize to required 5 decimal places and degree/axis notation, true minus; keep each coordinate quantity unbroken and offer an expandable full extent. §§7.3, 8, 9.5. Related X-26 reading concern; proportional digits are not established.

### D04 — Major: mobile chrome displaces work below the initial viewport

**Screenshots:** `S06-390-light-default.png`, `S07-390-dark-default.png`, `S12-390-light-default.png`. **Semantic selector:** mobile AppHeader, workspace navigation, run-state-banner, run-nav-tab group. Settings/header occupy about 154 px, workspace links another 108 px, expanded run banner about 220 px on S06/S07 and four rows of run tabs about 200 px. S07 at 844 px reaches only title and orientation controls; no qualification result appears. **Fix:** compact header; collapse secondary settings/workspace links/revisions; use an accessible compact current-view switcher; preserve mode/state while bringing a result row into the initial viewport. Excess navigation density is established; broken scrolling is not. §§1, 5, 15.

### D05 — Major: matrix headers omit required candidate summaries

**Screenshots:** `S07-1440-dark-default.png`, `S07-1920-light-comfortable.png`, `S07-1024-light-compact.png`. **Semantic selector:** qualification matrix candidate `th` headers. Names and selection controls appear without origin label or `n PASS · n FAIL · n GAP · n UNKNOWN` summary counts. Even 1920 comfortable shows about two complete requirement rows, so summaries are valuable. **Fix:** add compact origin and glyph-backed counts, retaining sticky requirement names; separate summary from expandable detail. Footer lies outside these captures and is not asserted missing. §9.5.

### D06 — Moderate: native file picker leaks browser styling

**Screenshots:** `S03-1440-dark-default.png`, `error-rover-import-1440-light-default.png`, `error-rover-import-390-dark-default.png`. **Semantic selector:** Import rover JSON `input[type="file"]`, file-selector button. Grey native Choose File and No file chosen remain; no designed drop zone, file size or Replace/Remove actions. **Fix:** use specified styled FileDrop with a labelled native input as accessible backing. X-13, §9.3.

### D07 — Moderate: inner table overflow lacks visible guidance

**Screenshots:** `S06-1440-light-default.png`, `S07-1024-light-compact.png`, `S07-1440-dark-default.png`, `loading-missions-390-light-default.png`. **Semantic selector:** candidate/matrix/investigations table scroll regions. Candidate pane cuts screening text and hides selection at 1440; matrix cuts the next value/candidate at 1024; mobile header cuts Scientific outcome. No obvious horizontal scrollbar or scroll-for-more cue appears. **Fix:** keep intentional inner scrolling but add overflow edge/cue and accessible region label, pin identity/status and make selection readily discoverable. Pixels do not prove page-level overflow or unavailable full values; X-26 remains open for targeted proof. §§9.5, VIS-06.

### D08 — Moderate: timestamp fragments into unreadable pieces

**Screenshot:** `loading-missions-1440-dark-default.png`. **Semantic selector:** Investigations Created (UTC) cell. UTC timestamp wraps into roughly four short lines with a stranded `00Z`. **Fix:** reserve a nonwrapping timestamp column, or deliberately group date and full UTC time on two lines. Use `<time>` and full accessible text in implementation. §§8, 9.5.

### D09 — Moderate: schema-like labels obscure plain field names

**Screenshots:** `S03-1440-dark-default.png`, `error-rover-import-1440-light-default.png`, `S08-1440-light-default.png`. **Semantic selector:** rover FormField labels, import error-panel heading, compatibility Metric cells. Labels include mass kg (kg), max slope deg (deg), battery wh (Wh); metric `max_surface_slope_deg` and headline VALIDATION_ERROR expose schema formatting. **Fix:** plain labels Mass, Maximum slope, Battery energy, one unit suffix; human error title Rover import rejected, code secondary in mono. §§9.3, 14.

### D10 — Moderate: candidate map objects lack visible identities

**Screenshot:** `S06-1920-dark-default.png`. **Semantic selector:** Earth analog map candidate extent overlays. Six rectangles have no visible names/key relating them to table rows. Footer gives a coordinate frame rather than a sampled coordinate. **Fix:** short stable labels or numbered markers matching rows and a clear selected treatment; preserve full name/status on focus. First-glance correspondence is deficient; synchronization and focus labels are unverified. §§10 S06, 11.

### D11 — Minor: loading does not resemble final rows

**Screenshots:** `loading-missions-1440-dark-default.png`, `loading-missions-390-light-default.png`. **Semantic selector:** Missions loading table body. Reserved panel says Retrieving saved missions but has no four final-height skeleton rows. **Fix:** render the specified four skeleton rows and scoped text; add elapsed time after two seconds. Timing is unknown, so no perpetual-loading or CLS defect is asserted. §§9.5, 9.9.

## Complete X-01–X-29 disposition

Not observed means only sampled pixels, not a scan pass. Unverified items remain evidence gaps, not alleged defects.

| Item | Disposition |
|---|---|
| X-01 emoji | Not observed; alt/code/fixtures unverified. |
| X-02 gradients | Not observed in chrome; scientific raster is data. CSS scan unverified. |
| X-03 glassmorphism | Not observed; opaque overlay surfaces. |
| X-04 glow/neon | Not observed; blue close-button outline is a focus ring. |
| X-05 large radii | No conspicuous pills/blobs; computed radii unverified. |
| X-06 hero/marketing | Not observed; S01 opens into work. |
| X-07 space decoration | Not observed. |
| X-08 feature grids | Not observed in product; styleguide specimens are appropriate. |
| X-09 placeholder copy | No clear banned fake placeholder. Load example labels identify real presets; source scan unverified. |
| X-10 proportional numerals | Not observed; computed tabular-nums unverified. |
| X-11 small/low-contrast text | No obvious illegible body text; actual size, line-height and contrast ratios unverified. |
| X-12 uppercase paragraphs | Not observed; short statuses/codes differ from paragraphs. |
| X-13 browser defaults | **OPEN, confirmed:** native file-selector styling, D06. Select appearance alone cannot prove native versus Radix. |
| X-14 unscoped/endless loading | Scoped text exists. Duration/resolution unverified; D11 is a skeleton specification departure. |
| X-15 important toasts | Not observed; runtime result delivery unverified. |
| X-16 inappropriate modals | Not observed; shortcut dialog explicitly required by §13. |
| X-17 icon names/tooltips | Visual consistency acceptable; accessible names/tooltips unverified. |
| X-18 mixed icons | No obvious mismatch; implementation unverified. |
| X-19 fake similarity viz | Not observed; screening-order disclaimer explicit. |
| X-20 parallax/carousels | Not observed; motion unverified. |
| X-21 off-grid spacing | Orderly overall; computed dimensions unverified. |
| X-22 font/CDN policy | Sans/mono visually coherent; font identity/count and network unverified. |
| X-23 NASA insignia | Not observed; filenames/strings scan unverified. |
| X-24 marketing science | Not observed. |
| X-25 CLS/reordering | Unverified from stills. |
| X-26 overflow/clipping | **OPEN, targeted verification required:** D03/D07/D08 show broken numeric reading and cut inner table edges. Page overflow and expand/tooltip/scroll behavior unverified. |
| X-27 pure-black/white dark | Not visually apparent; computed colours unverified. |
| X-28 inconsistent language | Not observed. |
| X-29 colour literals | Unverified; source inspection forbidden. |

## Accessibility evidence limits

Captures establish visible focused close buttons, readable first-glance text in both themes, distinct Pass/Fail/Unknown glyphs plus words, larger mobile controls and shortcut help matching the seven §13 commands. They do not establish tab order, focus return/trapping, Esc behavior, typing suppression, ARIA names/live regions, table semantics, keyboard map inspection, pointer-coarse measurements, screen-reader output, exact contrast, 200% zoom or reduced motion. The S12 spacing-override image reflows without an obvious overlay collision in its visible region; hidden content is unverified. No keyboard/ARIA behavior is claimed passed or failed from pixels alone. Drawer receipt metrics are partly out of view on mobile; that alone does not establish lost content or a broken scroller.

## Images actually opened

S01-1440-dark-default.png; S02-1440-light-default.png; S03-1440-dark-default.png; S04-1440-light-default.png; S05-1440-dark-default.png; S06-1440-light-default.png; S07-1440-dark-default.png; S08-1440-light-default.png; S09-1440-dark-default.png; S10-1440-light-default.png; S11-1440-dark-default.png; S12-1440-light-default.png; S06-390-light-default.png; S07-390-dark-default.png; S12-390-light-default.png; evidence-drawer-390-dark-default.png; shortcut-dialog-390-light-default.png; operations-drawer-1440-dark-default.png; loading-missions-1440-dark-default.png; error-rover-import-1440-light-default.png; error-rover-import-390-dark-default.png; S06-1920-dark-default.png; S07-1024-light-compact.png; S12-1440-dark-default-spacing.png; styleguide-1440-light-default.png; S07-1920-light-comfortable.png; loading-missions-390-light-default.png; evidence-drawer-1440-light-default.png.


## Round1 — Hostile slop detector (verbatim)

# Independent hostile visual review — round 1

Verdict: FAIL. Mean 2.25/4; criteria 9 and 11 score 1 and are blockers under architecture 41 §20. The screenshots show a restrained application, but restraint alone does not make an engineering instrument. The major problems are contradictory scientific presentation, decorative-looking maps without interpretive equipment, and a shell that overwhelms the working content on mobile.

## Scope and evidence limits

Read only architecture 41 and out/visual/screens.md, then opened the actual named PNGs with view_image. No product source, previous reviews or history were inspected. No product files were edited. Locators below are semantic targets inferred from visible labels, not claims that source CSS classes or DOM roles were verified. Static screenshots cannot certify DOM accessibility, CSS tokens, fonts actually loaded, numerical contrast, timing, keyboard behavior, tooltip presence, network policy or production exclusion.

Inspected images:

- S01-1440-dark-default.png; S02-1440-light-default.png; S03-1440-dark-default.png; S04-1440-light-default.png.
- S05-1440-dark-default.png; S06-1440-light-compact.png; S06-1024-dark-default.png; S07-1440-dark-compact.png; S07-1440-dark-default-spacing.png.
- S08-1440-light-default.png; S09-1440-dark-default.png; S09-composite-1440-light-default.png; S10-1440-light-compact.png; S11-1440-dark-default.png; S12-1440-light-default.png.
- S02-390-light-default.png; S06-390-dark-compact.png; S07-390-light-default.png; S12-390-dark-default.png.
- evidence-drawer-390-dark-default.png; evidence-drawer-1440-light-default.png; operations-drawer-1440-light-default.png; shortcut-dialog-1440-dark-default.png.
- styleguide-1440-light-default.png; styleguide-390-dark-default.png; loading-missions-1440-dark-default.png; loading-missions-390-light-default.png; error-rover-import-390-light-default.png.

## Exact §20 rubric

| # | Criterion | Score /4 | Evidence and reason |
|---|---|---:|---|
| 1 | hierarchy — status is the loudest thing | 2 | S11-1440-dark-default.png: COMPLETED and large PROVE IT dominate; scientific outcome/headline is absent from the visible first view. Mobile shell hides almost all working status. |
| 2 | restraint — colour only for state | 4 | S07, S08 and S12 use neutral surfaces and small state marks; no decorative gradient, hero or illustration observed. |
| 3 | typography — scale, alignment, numerals | 2 | S06-1440-light-compact.png exposes long floating-point coordinates broken across lines; loading-missions-1440-dark-default.png splits a timestamp into multiple fragments. |
| 4 | density & spacing rhythm | 2 | S07-390-light-default.png spends about 710 px on shell/navigation before its title; compact S07 desktop exposes fewer than two requirement rows. |
| 5 | tables — scannable, aligned, units | 2 | S08 presents Unknown in both quantitative columns while the assessment prose supplies actual values and PASS; S06 candidate table is squeezed beside a mostly empty map. |
| 6 | states — empty/error/loading/disabled are designed | 3 | S01 has explicit empty reasons; rover error remains inline and names retention. Loading is scoped but has no visible skeleton/elapsed display, and completed S11 has a confusing disabled-action explanation. |
| 7 | copy — plain, precise, no hype | 3 | No hype observed. Raw field names, duplicate units and machine reason codes make routine reading unnecessarily technical. |
| 8 | consistency across screens | 3 | Shell, surfaces, tabs and tables are consistent. Portfolio/passport status words bypass the glyph badge vocabulary visible in qualification. |
| 9 | map & chart integrity | 1 | S06 map has six unlabeled rectangles and no visible geographic context or scale; S05 raster lacks visible legend and histogram axis context is incomplete. |
| 10 | accessibility feel (focus, contrast, keyboard) | 2 | Drawer/dialog close buttons visibly have focus rings. Mobile content is displaced and raw file widgets leak. Keyboard/screen-reader compliance remains unverified. |
| 11 | “would a crew member trust this?” credibility test | 1 | S08 contradicts its own numeric columns; S11 says completed while waiting for committed evidence; missing run scientific outcome forces interpretation. |
| 12 | absence of every X-xx slop item | 2 | Definite X-13, X-26 and X-28 findings below; X-12 also has visible cases. Most decorative slop is absent, but not every banned item is cleared. |

Total: 27/48. Arithmetic mean: 2.25/4. Acceptance requires every score ≥3 and mean ≥3.5.

## Severity-ordered concrete defects

### 1. Critical — compatibility table contradicts its own measured columns
Screenshot: S08-1440-light-default.png.
Semantic selector: table caption “Rover versus selected candidate · Preliminary” → row “max_surface_slope_deg” → columns “Rover value”, “Required”, “Assessment”.
Both numeric columns read Unknown, while assessment says PASS and “Declared 18 deg; required band upper 18 deg.” The field values necessary to audit the verdict are suppressed in the designated columns, then reintroduced in prose. The required_capability row has the same Unknown/PASS tension. This is a concrete presentation contradiction, regardless of backend correctness.
Fix: bind the actual declared/required quantities into their columns, put declaration provenance beneath them, and reserve Unknown for genuinely unavailable values. Keep unknown assessments separate from unobserved declared capability. Show units in headers.

### 2. High — completed test view fails to put scientific result first
Screenshot: S11-1440-dark-default.png.
Semantic selector: run-state banner “COMPLETED”; main heading “Test lab”; button “PROVE IT”; adjacent “Waiting for committed evidence and an allowed PROVE IT action.”
The first view contains no required headline about modeled test result, while COMPLETED and a large blue action are prominent. “Waiting for committed evidence” then implies incompleteness. The banner has terminal state but no separate scientific outcome, stage or elapsed time. A crew member cannot determine the modeled result at a glance.
Fix: show the plain result headline above Experiment, add a separate scientific-outcome badge to the run banner, and replace the generic disabled reason with the concrete completed-run reason. Prioritize attempt outcome/evidence above an unavailable rerun action.

### 3. High — candidate map reads as decorative geometry
Screenshot: S06-1440-light-compact.png.
Semantic selector: analog map region beside “Candidates · 6 of 6 visible”; its six rectangle features and top-right map controls.
The map occupies roughly 60% of the split yet shows only six anonymous rectangles against an empty field. No scale, coordinate readout, attribution, north/reset description, candidate name or visible selected extent distinction is available in this view. The table is visibly squeezed while the secondary map contributes little interpretable information. This is precisely how an engineering instrument becomes a template dashboard with a large illustration slot.
Fix: render extent geometry in a labelled geographic frame with scale/readout/attribution, candidate labels or a keyed selection; retain corner ticks for the selected extent. If geographic rendering is unavailable, present the specified map-unavailable notice and allocate space to the candidate list.

### 4. High — mobile shell pushes operational content below the first viewport
Screenshots: S06-390-dark-compact.png; S07-390-light-default.png; S12-390-dark-default.png.
Semantic selector: AppHeader + workspace navigation + run-state-banner + run-nav-tab region before main content.
In S07, the title begins around y=733 and the matrix is completely absent at 844 px height. S06 similarly reaches the filter only at the bottom. S12 shows the sheet heading but cuts off its claim. Large wrapped shell blocks and eight tabs in four rows consume the first screen. “Compact” does not rescue the mobile working view.
Fix: use a compact mobile header, collapse workspace links into a labelled menu, reduce the run summary to its critical state/mode and expandable revisions, and use a compact accessible tab selector. Keep scientific outcome and the first actionable data row visible without scrolling through several screens of chrome.

### 5. High — unformatted coordinates damage the primary candidate list
Screenshots: S06-1440-light-compact.png; S06-1024-dark-default.png.
Semantic selector: “Candidates · 6 of 6 visible” table → Window column → Practice grid-r0c0.
Raw “-110.92999999999999” style precision breaks across several lines. In the 1440 split view this inflates row height and leaves the Screening status column cut at the panel edge. Numbers should not wrap, and coordinate precision/frame should be deliberate (§8).
Fix: use the centralized coordinate formatter, fixed five decimals and hemisphere/frame labels; keep each coordinate pair unbroken and provide a labelled internal horizontal scroll affordance or responsive row detail. Do not allocate the list narrower than its scientific columns can support.
Open X: X-26.

### 6. High — raster and histogram are not self-explanatory scientific plots
Screenshot: S05-1440-dark-default.png.
Semantic selector: “Mars target region” raster; “Slope histogram” chart.
The raster shows grey vertical bands but no visible variable legend, units or min/max. The histogram y scale runs 0–1 but has no visible axis label; x bins/unit labels and a required slope-threshold annotation are not visible in the captured first view. This cannot be accepted as chart integrity simply because a Chart/Table toggle exists.
Fix: make the map legend/readout/attribution persist within its viewport; give the histogram labelled axes, explicit slope bin intervals/units and requirement threshold label. Keep plot labels inside the chart’s reserved height so the scroller/footer cannot crop the interpretive context. The screenshot alone cannot establish whether labels exist farther down.

### 7. Medium — native file input leaks into the tokenized form
Screenshots: S03-1440-dark-default.png; error-rover-import-390-light-default.png.
Semantic selector: field “Import rover JSON” → input[type=file] and field “Use an existing revision” → select-shaped control.
The browser’s “Choose File” button and filename text are directly visible inside a plain input frame. This is an unequivocal X-13 raw-file-control leak. The select also visually resembles native UI, but native DOM implementation is unverified and is not needed to establish this finding.
Fix: use the specified styled FileDrop with filename, file size, Replace/Remove controls and validation result. Use the prescribed styled Select primitive for revision choice.
Open X: X-13.

### 8. Medium — statuses lose their shape vocabulary in downstream tables
Screenshot: S09-composite-1440-light-default.png; also visible at the first requirement row in S12-1440-light-default.png.
Semantic selector: coverage table → Coverage cells “UNKNOWN” / “GAP”; passport “Requirement evidence summary” → Status / candidate cells.
Coverage is plain uppercase text, lacking the custom hexagon/diamond glyphs, tint and consistent badge anatomy used in S07. The passport’s visible PASS is also plain text. Reading across screens requires a different visual decoding strategy. Color is not required for accessibility, but the binding system explicitly requires shape + glyph + word, consistently.
Fix: use the same StatusBadge/StatusGlyph in portfolio and passport, including print-safe glyphs and sentence-case words. Ensure badges do not imply an aggregate scientific PASS.
Open X: X-28 (status-component visual language differs across screens).

### 9. Medium — repeated raw implementation labels make the interface feel generated
Screenshots: S03-1440-dark-default.png; S05-1440-dark-default.png; S08-1440-light-default.png.
Semantic selector: rover labels “mass kg (kg)”, “max slope deg (deg)”, “battery wh (Wh)”; target metric “slope_area_fraction:12-18”; compatibility metric “max_surface_slope_deg”.
Duplicate units, abbreviations and snake_case metric keys are rendered as routine labels. They read like schema fields exposed through a generic form/table generator rather than a deliberate operator vocabulary.
Fix: map schema keys to stable human labels: “Mass (kg)”, “Maximum slope (deg)”, “Battery capacity (Wh)”, “Area within 12–18 deg slope band”, “Maximum surface slope”. Keep canonical IDs in secondary mono details where useful.

### 10. Medium — timestamp column breaks an exact value into fragments
Screenshot: loading-missions-1440-dark-default.png.
Semantic selector: Investigations table → “Created (UTC)” cell.
The date wraps as “2026- / 11-05 / 12:00: / 00Z”. This makes the timestamp difficult to read and violates the single deliberate timestamp format/no-wrapped-numerical-value discipline.
Fix: reserve a nonwrapping mono width for the timestamp, shorten other low-priority columns or move timestamp to responsive row detail. Keep exact UTC value available without reconstruction.
Open X: X-26.

### 11. Medium — uppercase status headlines and prose exceed the restrained casing rule
Screenshots: S05-1440-dark-default.png; evidence-drawer-1440-light-default.png.
Semantic selector: run banner “AWAITING REVIEW”; Limitations paragraph beginning “SYNTHETIC PRACTICE DATA”.
The banner uses a prominent all-caps heading rather than sentence-case heading or small status badge; the evidence drawer begins a body-size limitation sentence with a four-word all-caps phrase. This exceeds §7.3’s ≤3-word 12 px status/column exception.
Fix: use sentence-case “Awaiting review” with a glyph/badge, and write “Synthetic practice data — not terrain of this location.” Keep mode badges uppercase as explicitly permitted.
Open X: X-12.

## X-01–X-29 disposition

Definite open findings: X-12 (casing), X-13 (raw file widget), X-26 (wrapped numeric values and squeezed/clipped candidate-table presentation), X-28 (inconsistent status language). These are not cleared.

- X-01: no emoji observed in inspected images; fixture/alt text scanning not possible here.
- X-02, X-03, X-04, X-05: no visible gradients, blur, glow or excessive radii observed; CSS implementation not verified.
- X-06, X-07, X-08: no hero, decorative space background or marketing feature grid observed. Styleguide component grid is an appropriate inventory, not a marketing feature grid.
- X-09: no Lorem ipsum/TODO/Coming soon-style placeholder observed. “Load example” names actual domain presets and is not treated as the banned dummy “Example 1”.
- X-10: numerical alignment generally appears deliberate; actual tabular-numeral computed properties are unverified. Floating-point formatting is separately defective.
- X-11: exact font-size/line-height/contrast cannot be certified from these PNGs. No claim of AA compliance is made.
- X-12: OPEN, defect 11.
- X-13: OPEN, defect 7. Underlined links also appear in S01, but screenshots cannot establish whether that styling is default-browser leakage; no additional finding asserted.
- X-14: loading text is scoped (“Retrieving saved missions”), without spinner. Static evidence cannot determine wait duration, resolution or whether elapsed text appears after 2 s. Not cleared behaviorally.
- X-15: no significant-result toast observed; notification behavior unverified.
- X-16: no nested modal observed. Shortcut-help dialog is explicitly permitted by §13 and is not flagged.
- X-17: icon-only controls exist, but accessible names/tooltips are not visible/verifiable. No unsupported missing-ARIA finding asserted.
- X-18: visible icons mostly appear consistent; package/stroke provenance unverified.
- X-19: no similarity gauge, radar or fake percentage badge observed. Poor map interpretation is defect 3, not an invented similarity-viz claim.
- X-20: no tilted/parallax/carousel presentation observed; animation cannot be assessed in stills.
- X-21: exact grid/token measurements require computed layout; no false pixel-precision compliance claim.
- X-22: font requests/count/families cannot be certified visually.
- X-23: no NASA insignia, approved badge or lookalike mark observed.
- X-24: no marketing scientific hype observed.
- X-25: data-arrival layout shift and sorting stability cannot be assessed from single frames.
- X-26: OPEN, defects 5 and 10. Internal matrix overflow may be intentional; no blanket claim that every partially visible column is illegal page overflow.
- X-27: dark surfaces visibly use blue-grey rather than pure-black/pure-white treatment; exact values unverified.
- X-28: OPEN, defect 8.
- X-29: source color-literal/token usage cannot be assessed under this review’s source restriction.

No claim of “no open findings” is justified. The absence of conspicuous AI decoration is real; the generated-schema feel, incomplete plot semantics and contradictory result presentation are more consequential here.


## Round1 disposition

Not accepted. All three reports fail the rubric. Implementation fixes are in progress for scientific outcome hierarchy, mobile chrome, compatibility operands/provenance, matrix summaries/density, receipt scrolling, maps/legends/coordinate precision, shared status vocabulary, file controls and labels, numeric overflow, and destructive-confirmation actions. A new full visual audit and fresh independent review are required before DR-01–04 can pass.


## Round2 inputs and prompts

Source `f2f088d`; full browser gate29/29,398visualreports,388screenshots,0findings,0skips. Catalog archived as `analogforge/out/visual-r2/screens.md`; full component images preserved there. Fresh reviewers received only architecture41, final screens.md and its images, the exact12criterion rubric and distinct personas. Each was explicitly barred from source/history/prior reports and required actual image inspection, semantic selectors, five defects or evidenced fewer, scope limits, actual independent scores and open X findings.


## Round2 — Mission operations (verbatim)

# AnalogForge independent mission-operations HMI review

Decision: **FAIL**. Mean **2.58 / 4** (31 / 12). Five criteria are below 3; map/chart integrity is 1 and is a blocker. The required gate is every criterion at least 3 and mean at least 3.5.

This is an independent visual review using an ISA-101/Open MCT mindset: an operator must distinguish lifecycle, scientific outcome, scale and uncertainty while tired. Inputs were restricted to `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and catalogued images. No implementation, histories, logs, other reviews or handoffs were read. No implementation or image was modified.

## Evidence and scope

Actual images were opened using `view_image`: S01–S08 at 1440 dark/default; S09–S12 at 1440 light/default; S06/S07/S08/S12 at 390 dark/default; S02/S10 at 390 light/default; S05 at 1920 light/default; S06 at 1024 light/default; S08-rover-conflict at 1440 dark/default; S09-composite at 1440 light/default; desktop evidence and operations drawers; mobile evidence and operations drawers; mobile shortcut dialog; desktop loading-missions; mobile error-rover-import. Full-length component styleguide images were inspected in dark/default, light/default, dark/compact and light/comfortable, including the lower chart, table, layer, scale, coordinate and attribution examples. The full-length images were automatically scaled for display, so they support inventory and overall composition judgments, not exact pixel/contrast measurements.

Selectors below are **semantic inspection targets**, expressed as role/name or visible-text locators. They identify concrete elements without pretending that screenshot inspection verified actual DOM roles, accessible names, test ids or CSS selectors. A role-based selector must be confirmed against the implementation before automation. Runtime behavior, keyboard operation, tooltip availability, contrast ratios, font loading, CSS dimensions, source scans, exports and printing remain unverified.

## Scores

| Exact criterion | Score 0–4 | Independent rationale |
| --- | ---: | --- |
| hierarchy | 3 | Lifecycle and latest modeled test remain separate, persistent and legible in S07 and S11. On mobile the shell dominates the actual evidence; the latest-result badge alone cannot compensate for the small working area. |
| restraint | 4 | Neutral flat chrome; state colors carry meaningful badges; neutral SYNTHETIC labeling. No decorative space imagery, glow, gradient or marketing hero observed. |
| typography | 3 | Consistent neutral sans/mono treatment and visible status words. Compatibility precision and receipt-label wrapping compromise numerical/identifier readability. Actual typeface and tabular numeral properties are unverified. |
| density/spacing | 2 | S06-1024 and mobile S07/S10 devote most of the viewport to shell and framing. A dense operational tool should expose more than a small fragment of one evidence row. |
| tables | 2 | Consistent table chrome and explicit overflow hints are good. S06 desktop candidate rows are tall while status and actions lie beyond the visible table width; S08 ground clearance loses meaningful precision. |
| states | 3 | Scoped skeletons, honest empty reasons, prominent import error/remediation, disabled PROVE IT reason, and persistent result history summary are designed. Full runtime transitions and loading elapsed-time thresholds are unverified. |
| copy | 3 | Plain engineering voice, clear synthetic disclaimers, and explicit modeled-versus-physical scope. Raw event codes and malformed metric wrapping remain a burden. |
| consistency | 3 | Shell, banners, badges, tables and buttons recur consistently across both themes. Native-looking file input and styleguide/header theme mismatch are exceptions. |
| map/chart integrity | 1 | S05 histogram reference lines are spatially inconsistent with the labelled bins. This can cause incorrect scientific interpretation. Honest map fallback disclosures do not resolve it. |
| accessibility feel | 3 | Status words and distinct glyphs, visible close-button focus rings, generous mobile controls, explicit scroller hints and readable contrast by eye. Keyboard, focus return, screen readers and measured AA contrast are unverified. |
| crew-member credibility | 2 | Synthetic scope and uncertainty are responsibly visible, but misplaced scientific thresholds and a displayed 0 m clearance are unacceptable for operational trust. |
| absence of X-01–X-29 | 2 | Observable X-13 and X-26 defects remain, plus a result-notification example contrary to X-15. Screenshot evidence cannot clear source/runtime-only bans. |

## Defects ordered by severity

### 1. P1 — Scientific reference lines do not correspond to their histogram bins

**Evidence:** `S05-1920-light-default.png`; also visible in the upper portion of `S05-1440-dark-default.png`.

**Semantic selector:** heading `Slope histogram` → its following chart/SVG → text `12 deg` and `18 deg` and their dashed vertical lines; x-axis bins `2–5`, `12–15`, `15–18`.

**Observed:** Both threshold lines sit above the `2–5` bin near the left side of the plot, while the x axis places `12–15` and `15–18` much farther right. The title text explains that these are accepted lower/upper slope limits. Their geometry therefore communicates a different threshold region than the axis labels. The threshold labels also crowd the y-axis quantity title.

**Fix:** Use one coherent x-coordinate mapping for bars, ticks and reference limits. With categorical bin rendering, place 12 and 18 at their actual bin boundaries; alternatively use a numerical degree axis with correctly sized bins and explicit fraction-versus-density semantics. Reserve a separate annotation band so reference labels do not overlap the axis title. Recheck the actual chart and adjacent table together.

**Scope:** Visual inconsistency is confirmed. Underlying scale implementation and data correctness are not inspected. This violates the integrity intent of §10.5 even though it is not itself a percentage-similarity/fake-score X-19 visualization.

### 2. P1 — Compatibility displays meaningful sub-meter clearance as zero

**Evidence:** `S08-1440-dark-default.png` and `S08-rover-conflict-1440-dark-default.png`.

**Semantic selector:** table caption containing `Rover versus selected candidate` → row named `Ground clearance` → `Declared rover value` cell; same row → assessment/provenance cell.

**Observed:** The declared value reads `0 m`, while the explanation in the same row says `60 m support cannot resolve 0.20 m clearance`. These two presentations create conflicting quantitative impressions even without reading source. An operator scanning the numeric column can infer no clearance instead of 20 cm. S03's rover form also displays a 0.2 m ground-clearance value, but the within-row contradiction alone is sufficient evidence.

**Fix:** Preserve domain-appropriate sub-meter precision (`0.20 m`, or `200 mm`) throughout rover specifications, compatibility and receipts; never round a positive physical limit to a displayed zero. Resolve the formatting contract's whole-meter rule for physical dimensions explicitly. Keep support and assessment distinct from the declared capability.

**Scope:** The screenshot contradiction is confirmed; no conclusion is drawn about stored values or verifier computation.

### 3. P2 — Responsive shell consumes the evidence workspace

**Evidence:** `S06-1024-light-default.png`, `S07-390-dark-default.png`, `S10-390-light-default.png`, `S08-390-dark-default.png`.

**Semantic selector:** workspace navigation/aside; lifecycle banner containing `Latest modeled test`; run tab strip; main qualification/benchmark table; footer controls `Open operations` and `Open evidence`.

**Observed:** At 1024 the left sidebar remains roughly 200 px wide with explanatory prose, while the run-state panel grows to roughly 196 px high. This contradicts the standard's 48 px collapsed context rail and 40 px banner intent. Only part of the first candidate row is visible. At 390, the table starts around y=506 (qualification) or y=585 (test lab), with the persistent bottom region beginning near y=745. Test lab shows its header and a sliver of its first row; the primary PROVE IT action is outside the visible working area. This is a viewport-budget problem, not proof of inaccessible content or page overflow.

**Fix:** Collapse context at 1024 as specified, remove instructional sidebar prose from the persistent operational shell, compress the mobile lifecycle into a summary with explicit expansion, and reserve the mobile sticky action bar for the current screen's primary action. Keep operations/evidence reachable without letting them dominate the reading area. Show several meaningful rows before requiring another scroll.

### 4. P2 — Candidate comparison favors an oversized secondary map over usable table columns

**Evidence:** `S06-1440-dark-default.png`.

**Semantic selector:** table caption `Candidates · 6 of 6 visible`; columns `Origin`, `Window`, `Screening status`, selection actions; adjacent offline extent view with C1–C6.

**Observed:** The table occupies less than half the working width and exposes screening order, name and origin, but the status/action columns are outside the initial horizontal viewport. Each visible candidate consumes a tall row because bounds and origin prose wrap. The map occupies the larger adjacent region although it currently conveys six simple extent rectangles. Only about two candidates are visible, reducing glance comparison.

**Fix:** Make the initial table show candidate name, screening status and selection action without horizontal exploration. Move full bounds and verbose origin explanation into row details, use a compact origin label, and allocate the list priority over this sparse map. Preserve full coordinates through deliberate expansion.

**Scope:** Intentional, labelled internal scrolling is visible and is not counted as forbidden horizontal page scrolling.

### 5. P2 — Evidence metric identifiers break in the middle of words

**Evidence:** `evidence-drawer-1440-dark-default.png`, `evidence-drawer-390-light-default.png`.

**Semantic selector:** evidence drawer heading `Receipt metrics` → metric cell containing `slope_area_fraction:12-18`.

**Observed:** The identifier wraps as `slope_area_fractio` / `n:12-18`, splitting the metric token at an arbitrary letter. The narrow metric column and competing value/support stack make the receipt harder to audit. §9.5 expressly requires text wrapping without mid-word clipping. This is a confirmed X-26 readability defect; whether a tooltip or accessible full-value alternative exists is unverified.

**Fix:** Show a human-readable metric name, with the intact technical key beneath it in an expandable/copyable field. On a narrow drawer, stack metric and measured-value sections vertically instead of squeezing both into a two-column table.

### 6. P2 — File import retains native-looking file-widget chrome

**Evidence:** `S03-1440-dark-default.png`, `error-rover-import-390-light-default.png`; full styleguide `FileDrop` examples.

**Semantic selector:** label `Import rover JSON` → file chooser showing `Choose File` / filename; adjacent `Replace file` and `Remove file` controls.

**Observed:** A browser-shaped inner `Choose File` widget remains nested inside the custom import panel. On the error screen, the filename appears both inside that widget and again below it, yielding two visual control languages and duplicate filename presentation. This is the visible native file-control leak prohibited by X-13; the actual input type/DOM styling cannot be proved from pixels alone.

**Fix:** Present one consistently styled import/drop-zone control with one filename/size summary and the existing replace/remove actions. Keep a properly associated accessible file input behind that presentation.

### 7. P2 — Styleguide teaches an important result as a toast

**Evidence:** `styleguide-dark-default.png`, `styleguide-light-default.png` (full component captures), section labelled `Toast`.

**Semantic selector:** component group heading `Toast` → visible text `Evidence export ready`.

**Observed:** The toast example is an export-ready result. The binding standard explicitly bans toasts for export-ready results and reserves them for non-critical confirmations. This is an X-15 example/content violation in the component reference, not evidence that the actual passport export uses a disappearing toast.

**Fix:** Use a non-critical example such as `View preference saved`; demonstrate export-ready state as a persistent export row containing format and digest. Keep that persistent record visible until the operator leaves the relevant view.

### 8. P3 — Component-reference header contradicts its displayed theme/density

**Evidence:** `styleguide-dark-default.png`, `styleguide-dark-compact.png`, `styleguide-light-comfortable.png`.

**Semantic selector:** app-header theme/density controls versus styleguide labels `Dark theme`, `compact density`, `comfortable density`.

**Observed:** The dark full captures show `Theme: light` in the header; compact/comfortable full captures retain `Density: default` in the header. The component region itself is visibly in the stated showcase theme/density. This makes the reference harder to trust and invites ambiguity about which controls govern the visible state.

**Fix:** Synchronize shell labels with the active showcase, or explicitly label independently scoped showcase settings. This does not prove theme switching fails in the actual product.

### 9. P3 — Operations rows expose implementation-style event codes instead of actor-led summaries

**Evidence:** `operations-drawer-1440-light-default.png`, `operations-drawer-390-dark-default.png`.

**Semantic selector:** `Operations timeline` → first event containing `1 · run.state_changed` and `VALIDATING: synthetic practice replay`.

**Observed:** The initial row repeats `VALIDATING` and uses the raw event key as a leading label. The standard calls for seq, time, actor role and a short human summary. The screenshot provides less operational explanation than the specified pattern.

**Fix:** Lead with `Planner started validation for the synthetic practice run`, retaining the raw event key in expandable details. Keep sequence/time and committed evidence links available.

## Open X findings and boundaries

Confirmed visual/example findings: **X-13** (native-looking file widget, defect 6); **X-26** (mid-word receipt metric wrapping, defect 5); **X-15** (export-result toast example, defect 7, limited to styleguide evidence).

No observable finding in the inspected images for X-01–X-08, X-10–X-12, X-16, X-18–X-20, X-22–X-24, X-27 or X-28. This is not a source-level clearance. X-09 is not charged for `Example histogram`/`Example table` in a clearly identified developer styleguide: those describe demonstration components, not fake operational data. The practice preset label `Load example` is similarly an explicit practice action, not a fabricated scientific value.

**Unverified X items/aspects:** X-02–X-05 source restrictions and exact radii/shadows; X-09 forbidden-string scanning; X-10 computed tabular numerals; X-11 measured size/line-height/contrast; X-13 select implementation and focus styling provenance; X-14 actual wait duration, eventual resolution and elapsed-time behavior; X-15 runtime notification persistence; X-16 dialog behavior; X-17 tooltip/accessibility names; X-18 actual icon package; X-20 motion behavior; X-21 exact 4 px grid; X-22 font count/origin; X-25 CLS/reordering; X-26 keyboard reachability, accessible expanded values and page-scroll behavior; X-29 color literals. These require runtime or source checks outside this review's permitted scope. Screenshots alone cannot close them.

## Strengths worth preserving

`S11-1440-light-default.png` states both failed attempts and the eventual pass, with the lifecycle separate from the latest test badge. `S12-1440-light-default.png` displays SYNTHETIC, LIMITED, a modeled-versus-physical disclaimer and the unresolved clearance scope together. `S09-composite-1440-light-default.png` retains UNKNOWN and GAP rows instead of a single portfolio PASS. `loading-missions-1440-dark-default.png` uses scoped retrieval text and table-shaped skeletons; `error-rover-import-390-light-default.png` gives cause/remediation and says the existing profile was retained. Drawer close buttons show clear visible focus in both themes, and shortcut help lists the expected keys without chord navigation. These choices support the intended instrument character.

## Acceptance judgment

The product has a coherent operational visual language, but it does not meet the stated review gate. Correct the chart threshold geometry and clearance formatting first, then reclaim responsive workspace and repair receipt/file/reference patterns. A later screenshot-only review can reassess those visual changes; keyboard, contrast, scientific computation, persistence and export assurance still require independent runtime evidence.


## Round2 — Accessibility and typography (verbatim)

# AnalogForge — independent accessibility and typography review R2

Verdict: **FAIL**. Score **33/48; mean 2.75/4**. Acceptance requires every criterion at least 3 and mean at least 3.5. Tables, map/chart integrity, crew-member credibility and absence of banned items fall below 3; map/chart integrity is a blocker at 1.

## Scope and evidence boundary

I read only the binding `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and cataloged images. I opened actual image files with `view_image`. I did not read implementation, history, previous reviews, handoffs, logs or reports, and did not modify implementation or images.

Screens inspected: S01-1440-dark-default; S02-1440-light-default; S03-1440-dark-default; S04-1440-light-default; S05-1440-dark-default and S05-1920-light-default; S06-1440-light-default; S07-1440-dark-default; S08-1440-light-default; S09-1440-dark-default; S10-1440-light-default; S11-1440-dark-default; S12-1440-light-default; S01-390-light-default; S03-390-dark-default; S05-390-light-default; S06-390-dark-default; S07-390-light-default; S10-390-dark-default; S11-390-light-default; S12-390-light-default; S09-composite-768-light-default; S07-1024-dark-default-spacing; S08-rover-conflict-1440-light-default; S04-edited-draft-390-dark-default; evidence-drawer-1440-light-default and evidence-drawer-390-dark-default; operations-drawer-1440-dark-default and operations-drawer-390-light-default; shortcut-dialog-390-light-default; loading-missions-390-light-default; error-rover-import-1440-dark-default and error-rover-import-390-light-default. Each name in this paragraph ends in `.png`.

Also inspected the full catalog-linked `apps/web/docs/design-review/styleguide-dark-default.png`, `styleguide-light-default.png`, and `styleguide-dark-compact.png`; the compact image was emitted at original detail for legibility throughout its complete height.

Selectors below are concrete **semantic targeting recipes**, not verified DOM queries. `getByRole`, `getByText` and `getByLabel` specify the intended visible component by its name. No screenshot proves that the corresponding ARIA role, accessible name, label association or DOM selector currently exists. Screenshot assessment cannot certify contrast ratios, font sizes, tabular font features, touch hitboxes, focus traversal, screen-reader announcements, reduced motion, tooltip access, text-spacing behavior beyond the supplied capture, scrolling, CLS or print output.

## Scores

| Exact criterion | Score 0–4 | Evidence and judgment |
| --- | ---: | --- |
| hierarchy | 3 | Lifecycle and latest test are distinct in S11-1440-dark-default.png, but the accepted-experiment preview dominates the first viewport over committed attempt evidence. |
| restraint | 4 | Flat neutral surfaces, restrained accent, semantic status colors across both themes; no decorative planetary imagery. |
| typography | 3 | Clear sans/mono distinction and readable hierarchy; drawer metric midword breaking and left-aligned numeric compatibility values weaken precision. |
| density/spacing | 3 | Consistent panels and grid rhythm; S07-1440-dark-default.png fits only the start of one requirement row below a tall candidate header, reducing useful evidence density. |
| tables | 2 | Qualification and benchmark structures are explicit, but compatibility numbers are left-aligned and ground clearance loses meaningful precision. |
| states | 3 | Scoped skeleton caption, durable import error, explicit unknown values and completed-run disabled reason are visible. Error anatomy is incomplete. |
| copy | 3 | Strong modeled/synthetic limitations and plain wording; error remediation and operation summaries still expose generic/internal phrasing. |
| consistency | 4 | Shell, badges, tables, neutral controls and drawer language remain visually coherent across S01–S12 and both themes. |
| map/chart integrity | 1 | Target histogram threshold positions contradict their degree labels and category axis; full styleguide charts omit the third category tick and clip the last series extent. |
| accessibility feel | 3 | Status word plus distinct silhouette, conspicuous drawer/dialog close focus and mobile control expansion are visible. Keyboard and WCAG compliance remain unverified. |
| crew-member credibility | 2 | Honest provenance and limitations help, but contradictory clearance precision and incorrectly located scientific reference lines undermine trust. |
| absence of X-01–X-29 | 2 | Open X-13, X-15 and X-26 findings below; screenshot evidence does not establish scan-only or behavioral absences. |

## Defects, ordered by severity

### 1. P1 — scientific threshold markers appear in the wrong slope bins

**Screenshot:** `S05-1920-light-default.png` (also the threshold heading area in `S05-1440-dark-default.png`).

**Semantic selector:** `getByText('Slope histogram', {exact:true})` → associated chart SVG → reference-line labels `12 deg` and `18 deg` and their dashed lines.

**Observed:** Both dashed lines intersect the chart above the `2–5` bin. The axis farther right explicitly includes `12–15` and `15–18`. The chart therefore visually associates 12 and 18 degree constraints with an unrelated lower slope category. The `12 deg` text also crowds the vertical-axis title. This is visible scientific misregistration, irrespective of the underlying scale implementation.

**Fix:** Map thresholds using the same bin/degree transform as the plotted distribution. For a categorical interval chart, place boundaries at the correct interval edges or clearly encode partial-bin interpolation. Reserve a separate label lane so threshold text cannot touch the axis title. Verify the visible 12 and 18 degree markers against the labeled 12–15 and 15–18 bins.

### 2. P1 — clearance precision changes the declared engineering value

**Screenshots:** `S08-1440-light-default.png`, `S08-rover-conflict-1440-light-default.png`; comparison evidence `S03-1440-dark-default.png`.

**Semantic selector:** `getByRole('table', {name:/Rover versus selected candidate/}).getByRole('row').filter({hasText:'Ground clearance'})` → `Declared rover value` cell.

**Observed:** Compatibility displays `0 m`; the assessment in the same row explicitly says support cannot resolve `0.20 m` clearance. The rover profile also visibly holds `0.2`. Zero is a materially different declared value. This is an observable display contradiction; its implementation cause is unverified.

**Fix:** Preserve submeter precision for rover geometry (for example `0.20 m`) using quantity-specific formatting. Keep the unknown assessment and scale limitation separate from the declared value.

### 3. P2 — component charts clip or omit their last category

**Screenshots:** full `styleguide-dark-compact.png`, `styleguide-dark-default.png`, `styleguide-light-default.png`.

**Semantic selector:** `getByRole('heading', {name:'Chart(Histogram|Line|Bar)'})` → charts titled `Example histogram`, `Example line`, `Example bar` → x-axis labels and final bar/point.

**Observed:** Adjacent data tables explicitly list A, B and C. Chart axes visibly label only A and B. The third bar reaches the right boundary with reduced visible width; the line continues to the right edge without the corresponding final labeled point. The same pattern occurs in both themes and compact/default captures.

**Fix:** Give all three categories complete horizontal space, including final tick and marker clearance. Compute a bounded plot area separately from the outer SVG. Verify all A/B/C labels and full terminal bar/point remain visible at each responsive width. This is an open X-26 finding.

### 4. P2 — compatibility numeric columns are not aligned for comparison

**Screenshots:** `S08-1440-light-default.png`, `S08-rover-conflict-1440-light-default.png`.

**Semantic selector:** `getByRole('table', {name:/Rover versus selected candidate/})` → cells under `Declared rover value` and numeric portions under `Required value`.

**Observed:** Declared values such as `18.0 deg` and `0 m` begin at the left cell edge. They are not right-aligned numeric columns as required by §9.5. Requirements and support prose compete within these cells, making numerical comparison slower.

**Fix:** Align numeric quantities to a common right edge, use stable mono/tabular numerals, and separate supporting provenance onto a secondary line or dedicated column. Put stable units in column headers where possible. Font feature settings themselves were not verified.

### 5. P2 — error panel does not provide the specified diagnostic/remediation anatomy

**Screenshots:** `error-rover-import-1440-dark-default.png`, `error-rover-import-390-light-default.png`.

**Semantic selector:** `getByText('Review the entered values', {exact:true})` → associated error panel; `getByText(/file: Invalid JSON/ )`.

**Observed:** The panel has a red edge and generic title, then a `VALIDATION_ERROR` code and generic advice to correct listed fields. The concrete cause, invalid JSON, is separated below it. No error glyph, request identifier/copy control, or Copy details action is visible in this complete error region. For malformed JSON, “correct the listed fields” is imprecise because parsing failed before valid fields existed.

**Fix:** Put “Rover JSON could not be parsed” and a concrete next step in the persistent panel, include an error glyph, and provide copyable diagnostic details. Include request id when a server request actually exists; for client parsing use an explicitly identified local diagnostic rather than inventing a request id. Preserve the reassuring statement that the existing profile was retained.

### 6. P2 — evidence metric identifiers wrap midword

**Screenshots:** `evidence-drawer-1440-light-default.png`, `evidence-drawer-390-dark-default.png`.

**Semantic selector:** drawer headed `Evidence receipt` → `getByRole('table', {name:'Receipt metrics'})` → metric name `slope_area_fraction:12-18`.

**Observed:** The metric splits as `slope_area_fractio` / `n:12-18`. This damages scanability of a scientific identifier in the component intended to explain provenance. The mobile drawer devotes most of its initial height to metadata before the metric, compounding the reading burden.

**Fix:** Use the readable label “Slope-band area fraction”, show the 12–18 deg band separately, and retain the exact identifier in copyable metadata. Wrap only at meaningful separators. Do not simply hide the identifier. This is an open X-26 text-layout finding; tooltip availability is unverified.

### 7. P3 — full styleguide theme control contradicts the rendered theme

**Screenshots:** full `styleguide-dark-compact.png` and `styleguide-dark-default.png`.

**Semantic selector:** `getByRole('button', {name:/Theme:/})`; section heading `Dark theme`.

**Observed:** The header control reads `Theme: light` while the entire component surface and the section heading indicate dark theme. The density header similarly says default in the compact full capture while the section states compact density. These are visible state-label contradictions in the proof artifact.

**Fix:** Bind control labels to the rendered root theme/density, or clearly identify per-section previews as independent of global controls. Regenerate captures with mutually consistent state labels.

### 8. P3 — raw file-input anatomy remains exposed

**Screenshots:** `S03-1440-dark-default.png`, `S03-390-dark-default.png`, full `styleguide-dark-compact.png` FileDrop section.

**Semantic selector:** `getByLabel('Import rover JSON')` → visible `Choose File` / `No file chosen` control; styleguide section `FileDrop`.

**Observed:** The familiar native file chooser button plus “No file chosen” line is visible inside a styled wrapper; the error state duplicates the selected filename both in that row and below it. The standard specifically calls for the styled FileDrop primitive rather than raw file input presentation.

**Fix:** Use one explicit “Choose JSON file” action and one consistent selected-file row with size, Replace and Remove. Keep a real accessible file input behind the intentional presentation. This is the visible anatomy portion of X-13; source element type and native select implementation are unverified.

### 9. P3 — Toast demonstration uses a consequential export result

**Screenshots:** full `styleguide-dark-default.png`, `styleguide-light-default.png`, `styleguide-dark-compact.png`.

**Semantic selector:** styleguide section headed `Toast` → text `Evidence export ready`.

**Observed:** The component demonstration explicitly puts “Evidence export ready” under Toast. X-15 forbids export readiness as a toast result. This proves a misleading component example, not that a real export currently fires a transient notification.

**Fix:** Demonstrate Toast with a noncritical confirmation and show export readiness in a persistent export-status row with digest and retrieval action. Open X-15 is limited to the demonstrable example until runtime is inspected.

## Open X findings and coverage

**Open:** X-13 (raw file-chooser anatomy); X-15 (Toast demo uses export-ready result); X-26 (last chart category/series clipping and midword metric identifier wrapping).

**No visible instance in inspected captures:** X-01, X-02, X-03, X-04, X-05, X-06, X-07, X-08, X-12, X-16, X-18, X-19, X-20, X-23, X-24, X-27, X-28. These are visual observations, not source scans or absolute absence claims. The shortcut-help dialog is an explicitly required exception/pattern, not counted as an inappropriate modal.

**Not fully decidable from screenshots:** X-09 (styleguide explicitly contains demo/example labels; I do not count component-demonstration titles as a product placeholder finding without a defined exception ruling), X-10 (computed tabular numerals), X-11 (computed typography and measured contrast), X-14 (loading duration/resolution), X-17 (accessible names and tooltip behavior), X-21 (computed 4 px grid), X-22 (actual font inventory/network sources), X-25 (layout shift/resorting), X-29 (source color literals). X-13 native select provenance and X-15 actual toast delivery also remain unverified.

## Positive evidence and limits

Both themes retain readable neutral surfaces and consistent status shapes. The receipt drawer and shortcut dialog show strong visible close-button focus outlines. Mobile controls visibly expand and content stacks rather than becoming tiny desktop columns. Loading is scoped to saved missions; error and empty states retain meaningful structure. The S12 sheet explicitly limits the physical-clearance claim and maintains a visible synthetic mode badge. These are substantive strengths.

Horizontal table scrolling is explicitly labeled in S06/S07/S10; I do not classify an intentionally cropped scroller viewport as page overflow or claim that the fixed operations bar hides unreachable content. The mobile run-tab strip cuts off Compatibility with later tabs out of view and no visible overflow hint; this merits hands-on keyboard/touch verification, but the images alone cannot prove navigation is inaccessible. The text-spacing capture retains the shell without visible page overlap, but does not expose all lower table content or all focus stops. No behavioral or full WCAG pass is inferred from these artifacts.

The chart-marker and quantity-formatting defects should be corrected before acceptance, followed by regenerated screenshots that directly demonstrate the corrected scientific geometry and precision. Keyboard focus, semantic table structure, drawer focus return, live regions, contrast and tooltip access need direct inspection before any accessibility-compliance claim.


## Round2 — Hostile slop detector (verbatim)

# AnalogForge independent hostile design review — round 2

## Verdict

**Reject the visual acceptance gate. Open findings remain.** The screenshots show a restrained engineering console, not a generic landing page: there are no decorative planets, gradients, hero illustrations, percentage-similarity gauges or marketing card grids. However, a visually calm instrument can still mislead. The histogram threshold positions and clearance formatting undermine trust more seriously than decorative slop would.

This review used only `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md` and the catalogued images. No source, history, other reviews, handoffs, logs or reports were read. Images were opened with `view_image`. Selectors below are concrete **semantic targeting instructions**, not assertions that corresponding roles, accessible names or CSS selectors exist in the DOM. Screenshot evidence cannot establish keyboard operation, actual CSS values, network requests, computed contrast, runtime layout shift or persistence.

## Exact rubric

| Criterion | Score / 4 | Evidence and reason |
| --- | ---: | --- |
| hierarchy | 3 | Persistent lifecycle and outcome are separated, e.g. S11; mobile run chrome consumes considerable space before evidence. |
| restraint | 4 | Flat neutral panels, sparse accent, semantic state colour; no decorative imagery in inspected views. |
| typography | 3 | Clear UI/mono distinction and mostly orderly numerals; run IDs break into tiny fragments and chart labels collide. |
| density/spacing | 2 | S01 has large unused vertical gaps; mobile run shell leaves only a small evidence viewport. |
| tables | 2 | Qualification has useful status silhouettes, but loading investigations crushes its primary identifier; compatibility displays misleading precision. |
| states | 3 | Scoped skeleton, persistent error panel, explicit unknowns and disabled PROVE IT explanation are visible. |
| copy | 3 | Scientific scope and synthetic limitations are candid; a few developer-like identifiers and repeated cautionary paragraphs reduce quick reading. |
| consistency | 3 | Shared shell, badges and panels throughout; styleguide dark capture has a light-theme header label. |
| map/chart integrity | 1 | Histogram threshold lines contradict the bin labels. This is an operational blocker. |
| accessibility feel | 3 | Visible focus rings, text alongside status glyphs, labelled table overflow; actual accessibility remains unverified. |
| crew-member credibility | 2 | The ground-clearance display and threshold geometry cannot be trusted at a glance. |
| absence of X-01–X-29 | 2 | Open X-26 overlap and X-13 visual treatment, plus an X-15 styleguide example. |

**Total: 31 / 48. Mean: 2.583 / 4.** Acceptance requires every criterion ≥3 and mean ≥3.5. Neither condition is met; the score of 1 is independently a blocker under §20.

## Defects, ordered by severity

### 1. Histogram requirement lines point at the wrong slope bins — critical

- **Screenshot:** `S05-1920-light-default.png`; also visible in `S05-1440-dark-default.png` at the chart top.
- **Semantic selector:** Target evidence → Slope histogram → chart → reference lines labelled `12 deg` and `18 deg`.
- **Observed:** Both dashed lines sit over the left-side `2–5` bin region. The x-axis explicitly lists `0–2`, `2–5`, `5–8`, `8–12`, `12–15`, `15–18`, etc. A 12-degree threshold should align with the 8–12 / 12–15 boundary; 18 degrees with the 15–18 / 18–25 boundary. These are visibly different locations.
- **Impact:** A planner can infer that the large 2–5 bar lies within the accepted 12–18 band. The textual thresholds do not rescue misleading geometry.
- **Fix:** Derive threshold geometry from the same displayed bin boundaries as the bars, or use a coherent numeric x-axis with correctly positioned bins. Ensure line labels identify lower/upper thresholds explicitly. Check 12 and 18 against axis boundaries at each width.
- **Rule:** §10.5 honest chart anatomy. This is not an X-19 fake similarity gauge; it is a scientific chart-integrity defect.

### 2. Ground clearance loses its significant decimal value — high

- **Screenshots:** `S08-1440-light-default.png`, `S08-rover-conflict-1440-light-default.png`.
- **Semantic selector:** Rover versus selected candidate table → Ground clearance row → Declared rover value cell; compare Server assessment / provenance cell in the same row.
- **Observed:** Declared value reads `0 m`, while provenance says `60 m support cannot resolve 0.20 m clearance`. The screenshot therefore presents two conflicting impressions of the clearance magnitude. Source value and formatting cause cannot be verified here.
- **Impact:** Zero clearance is materially different from a sub-metre declared clearance. It makes a precise-looking table unsafe to skim.
- **Fix:** Retain meaningful sub-metre precision, e.g. `0.20 m`, and use a consistent value across the row. If the declared value is actually missing, render `Unknown`. The standard's generic whole-metre precision must not erase a scientifically meaningful quantity.
- **Rule:** §1 numbers first-class and impossible to misread; §8 deliberate precision.

### 3. Chart title and threshold annotations collide — medium

- **Screenshots:** `S05-1920-light-default.png`, `S05-1440-dark-default.png`.
- **Semantic selector:** Slope histogram → SVG top annotation band → `fraction of valid area`, `12 deg`, `18 deg` text.
- **Observed:** `12 deg` overlaps the y-axis title line; threshold labels crowd one another in the chart's upper margin. This persists on the wide 1920 screenshot, so it is not merely a mobile compression issue.
- **Fix:** Reserve a separate annotation row or place reference labels in collision-free positions inside the plot with sufficient padding. Keep the axis title outside that band.
- **Open X finding:** **X-26**, overlapping text.

### 4. Primary run identifier becomes a stack of fragments — medium

- **Screenshot:** `loading-missions-1440-light-default.png`.
- **Semantic selector:** Investigations table → first data row → Run link.
- **Observed:** Run link is rendered on four lines as `86`, `5fe`, `3d`, `1`, while other columns consume the width. The timestamp also runs beyond the visible right edge, although the table explicitly announces horizontal scrolling.
- **Impact:** The row's identifying anchor becomes difficult to compare or recognise. Labelling horizontal overflow does not justify shrinking the primary identifier to two characters per line.
- **Fix:** Give Run a stable minimum width and a single-line mono identifier; use the standard's short-ID plus accessible full-value/copy pattern. Let the labelled table scroller handle remaining columns.
- **Rule:** §8 IDs; §9.5 column minimums and no mid-word fragmentation. Tooltip/copy availability is unverified.

### 5. Home view wastes space between short tables — medium

- **Screenshots:** `S01-1440-dark-default.png`, `S01-390-light-default.png`.
- **Semantic selector:** Missions and runs → Missions panel / Investigations panel / Practice presets panel layout.
- **Observed:** Desktop has about 128 px of blank canvas between the short tables and Practice presets. Mobile has about 108 px of blank canvas between Missions and Investigations, pushing the practice choices below the first viewport even with no missions or runs.
- **Impact:** The interface feels like a stretched generic panel layout rather than a dense working instrument; the empty state occupies more navigation effort than its information warrants.
- **Fix:** Use content-driven table heights and a consistent 16–24 px inter-region gap. Keep Practice presets a slim list as §10 requests. Reserve height for loading within table bodies rather than between independent regions.
- **Rule:** §1 density with order; §10 S01 compact tables and slim preset strip. Exact CSS spacing/token compliance is unverified.

### 6. Shortcut help loses key-to-description alignment — low

- **Screenshot:** `shortcut-dialog-1440-light-default.png`.
- **Semantic selector:** Keyboard shortcuts dialog → `o` / Toggle operations drawer and `Esc` / Close drawer or dialog entries.
- **Observed:** `/` and `]` appear alongside their descriptions, but `o` and `Esc` have descriptions on a following line. The right column simultaneously continues with `e` and `?`, creating an irregular reading order.
- **Fix:** Render each binding as an atomic two-column row (fixed key column and flexible description), then arrange those complete rows in one or two columns. Keep wrapping within the description column.
- **Rule:** §1 predictable consistency; §13 readable keyboard help. Actual DOM order is unverified.

### 7. Default-looking blue underlined links interrupt the chrome — low

- **Screenshots:** `S01-1440-dark-default.png`, `loading-missions-1440-light-default.png`.
- **Semantic selector:** Practice presets → Load example links; Investigations table → Run link.
- **Observed:** These links have the bright-blue, always-underlined browser-default appearance explicitly named in X-13, while navigation and buttons use the restrained component vocabulary.
- **Fix:** Give these actions a deliberate shared link/tertiary-action treatment consistent with the system; preserve clear hover and keyboard focus. The actual stylesheet or native origin of the current treatment is not known from pixels.
- **Open X finding:** **X-13, visual appearance**, not a claim that the controls are technically unstyled.

### 8. Styleguide teaches a critical-result toast — low, demonstration scope

- **Screenshots:** `styleguide-dark-default.png`, `styleguide-light-compact.png` in the full-component capture directory linked by the catalog.
- **Semantic selector:** Component styleguide → Toast example → `Evidence export ready`.
- **Observed:** The Toast example uses export readiness, exactly the kind of consequential result X-15 requires to be persistent.
- **Fix:** Demonstrate a non-critical confirmation such as a harmless view preference, and demonstrate export readiness as a persistent row/banner with its digest.
- **Open X finding:** **X-15 in the styleguide's example contract.** No real export interaction or transient runtime notification was observed.

### 9. Dark styleguide's header names the light theme — low

- **Screenshot:** `styleguide-dark-default.png` full-component capture.
- **Semantic selector:** Global header → Theme control; compare Dark theme section.
- **Observed:** Dark canvas and Dark theme section are shown while the header says `Theme: light`.
- **Fix:** Synchronise displayed theme control state with the theme demonstrated, or explicitly label the styleguide as a forced preview so the control does not claim the wrong state.
- **Scope:** Visible inconsistency; theme persistence or switching behavior is unverified.

## X-01–X-29 accounting

**Open:** X-13 (default-looking links; finding 7), X-15 (styleguide export-ready toast example only; finding 8), X-26 (chart label overlap; finding 3).

**No visible instance found in inspected images:** X-01 emoji; X-02 decorative gradients; X-03 glass; X-04 glow/neon; X-05 large pills/blobs; X-06 hero/marketing sections; X-07 space decoration; X-08 feature grids; X-09 production placeholder copy; X-12 all-caps paragraphs; X-18 visibly mixed icon language; X-19 fake similarity viz; X-20 3D/parallax/carousels; X-23 NASA insignia; X-24 marketing scientific claims; X-27 pure-black/pure-white theme appearance; X-28 a different visual language per screen. Demonstration labels such as Example histogram belong to a component styleguide and are not treated as production placeholders.

**Cannot be closed from still images:** X-10 actual tabular-number font settings; X-11 exact font size/line-height/AA contrast; X-14 whether waits resolve and get elapsed text; X-17 accessible names/tooltips; X-21 actual 4 px CSS grid; X-22 font count/source/CDNs; X-25 runtime CLS/reordering; X-29 colour literals. Static inspection also cannot exclude unseen animated X-20 effects or hidden uses of other items. X-13 native select/file-input implementation is likewise unverified; the open finding is limited to visible link treatment.

## Inspected coverage

Opened actual images for all S01–S12: desktop S01/S03/S05/S07/S09/S11 dark; S02/S04/S06/S08/S10/S12 light; S09-composite light; S05 1920 light; S06 1024 dark. Opened mobile S01 light, S02 dark, S04-edited-draft light, S05 dark, S07 light, S08 dark, S10 light, S12 dark. Opened evidence drawer desktop dark/mobile light, operations drawer desktop dark/mobile light, shortcut dialog desktop light, loading missions desktop light, rover import error mobile dark and rover-conflict desktop light. Opened full component styleguide dark/default and light/compact, including the chart/table, state, overlay and input examples throughout the full tall captures.

The reviewed evidence supports a coherent, restrained product direction, but does **not** support a “no open findings” declaration or acceptance. Fix the misleading numeric/chart presentation first, then refresh these exact captures and repeat the rubric.


## Round2 disposition

Not accepted. Corrective work addresses categorical-bin threshold registration, submeter precision, chart extent visibility, numeric alignment, responsive viewport budget, candidate scan columns, receipt labels, intentional file controls, consistent styleguide settings, meaningful local error diagnostics, shortcut rows and low-consequence Toast examples. Fresh audit and reviewers are required. The unchanged source passed36/36 intended mutation failures; this does not override the independent design findings.


## Round3 inputs and prompts

Source `49372f1`;30/30browser tests,83frontend tests,402visualreports,392screenshots,0findings/0skips. Catalog archived as `analogforge/out/visual-r3/screens.md`. Three fresh reviewers received only architecture41 and the catalog/images, exact12criterion0–4rubric, distinct HMI/accessibility/slop personas and instructions to inspect actual images (original detail/crops allowed), cite concrete semantic selectors, report five defects or evidence of fewer, distinguish static evidence from behavior, disclose open X findings and give independent scores. They were barred from source/history/other reviews/handoffs/logs.


## Round3 — Mission operations (verbatim)

# AnalogForge independent HMI review R3

**Decision: does not meet design acceptance.** Scores total **37/48**, mean **3.083/4**. Hierarchy and density/spacing are below 3. Acceptance requires every score >=3 and mean >=3.5.

This is an independent ISA-101 / mission-operations review against `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`. I read only that standard, `out/visual/screens.md`, and the catalogued images. I did not read implementation, history, previous reviews, handoffs, logs, or reports. Implementation and delivered images were not modified. I opened actual images with `view_image` at original detail; because the full styleguide images were automatically reduced for display, I inspected temporary, lossless 1440-wide crops covering their entire height in both themes.

## Evidence and limits

Inspected at original detail:

- `S01-1440-dark-default.png`, `S02-1440-light-default.png`, `S03-1440-dark-default.png`, `S04-1440-dark-default.png`, `S04-edited-draft-1440-dark-default.png`.
- `S05-1440-dark-default.png`, `S05-1024-light-default.png`, `S06-1440-light-default.png`, `S06-390-light-default.png`.
- `S07-1440-dark-default.png`, `S07-1920-dark-default.png`, `S07-390-dark-default.png`, `S08-1440-dark-default.png`, `S08-rover-conflict-1440-dark-default.png`.
- `S09-1440-light-default.png`, `S09-composite-1440-dark-default.png`, `S10-1440-dark-default.png`, `S11-1440-light-default.png`, `S12-1440-dark-default.png`, `S12-390-light-default.png`.
- `evidence-drawer-1440-dark-default.png`, `evidence-drawer-390-dark-default.png`, `operations-drawer-390-light-default.png`, `shortcut-dialog-1440-light-default.png`.
- `loading-missions-1440-dark-default.png`, `error-rover-import-390-light-default.png`.
- Full `apps/web/docs/design-review/styleguide-dark-default.png` and `styleguide-light-default.png`, including all component specimens and all three chart/table pairs.

Selectors below are **semantic review targets**, expressed with visible headings, roles and text. They are concrete locators for the intended element, not assertions that an inspected DOM contains those roles or exact test IDs. A screenshot proves rendered appearance only. Scrolling, sticky headers, tooltips, full-value expansion, ARIA, focus return, keyboard operation, computed contrast/font metrics, source provenance, state transitions and chart geometry calculations remain unverified. Content ending at a viewport/scroller boundary is not by itself a defect or proof of inaccessible content.

## Exact rubric

| Criterion | Score /4 | Judgment and evidence |
|---|---:|---|
| Hierarchy | 2 | Status badges are distinct, but the qualification work is subordinated to shell, spacious controls and tall candidate headers; the passport puts digest before the important clearance limitation. `S07-1440-dark-default.png`, `S12-390-light-default.png`. |
| Restraint | 4 | Flat neutral surfaces, limited accent, semantic state colour; no decorative space theme or marketing panel. `S01-1440-dark-default.png`, `S09-composite-1440-dark-default.png`. |
| Typography | 3 | Readable hierarchy and visibly aligned mono quantities; precision and range formatting vary between rover editing and assessment. `S03-1440-dark-default.png`, `S08-1440-dark-default.png`. Font family and exact numeric features are unverified. |
| Density/spacing | 2 | At 1440x900 the matrix presents only the first requirement row, and the candidate list shows three rows while allocating most of its region to the map. Repeated support text and oversized headers consume working height. `S06-1440-light-default.png`, `S07-1440-dark-default.png`. |
| Tables | 3 | Structured headers, explicit status shapes, identifiers and right-aligned measurements are strong. Long qualification descriptions and header summaries impede comparative scanning. `S07-1920-dark-default.png`, `S08-rover-conflict-1440-dark-default.png`. |
| States | 3 | Clear no-portfolio, pending, validation error, loading scope and completed disabled-action copy. Connection states use the same glyph, and exhaustive control-state coverage is not demonstrated by static specimens. `S09-1440-light-default.png`, `error-rover-import-390-light-default.png`, full styleguide. |
| Copy | 4 | Plain operational language; synthetic and modeled limits are explicit; screening order is expressly distinguished from similarity. `S06-1440-light-default.png`, `S11-1440-light-default.png`, `S12-1440-dark-default.png`. |
| Consistency | 4 | Shell, panel edges, tables, badges and typography remain coherent across both themes and all viewed routes. Full dark/light styleguides support the same conclusion. |
| Map/chart integrity | 3 | Synthetic provenance, analysis support, scale, coordinate-frame text and chart data tables are visible. Chart axes start at zero in styleguide specimens. Operational target chart is low in the initial viewport; source-to-rendered geometry and interaction are unverified. `S05-1024-light-default.png`, `S06-1440-light-default.png`, full styleguides. |
| Accessibility feel | 3 | Large mobile controls and clear close-button focus rings; words accompany status shapes. Clipped navigation and mobile information allocation weaken discoverability. `evidence-drawer-390-dark-default.png`, `shortcut-dialog-1440-light-default.png`, `S07-390-dark-default.png`. This is not a WCAG certification. |
| Crew-member credibility | 3 | Good separation of lifecycle, latest modeled result and preliminary compatibility, with explicit immutable attempts and synthetic caveats. Insufficient at-a-glance requirement coverage and hidden mobile revision context still make a long shift harder. `S07-1440-dark-default.png`, `S08-1440-dark-default.png`, `S11-1440-light-default.png`. |
| Absence of X-01–X-29 | 3 | Strong visible restraint overall. X-26 has an open visible navigation-clipping concern. Source-only and behavior-only items cannot be certified from images. |

## Defects ordered by severity

### 1. P1 — Qualification uses too little of the working height for actual comparison

**Evidence:** `S07-1440-dark-default.png`; corroborated by `S07-1920-dark-default.png` and `S07-390-dark-default.png`.

**Semantic selectors:** heading `Qualification`; table caption `Requirement qualification · by requirement`; candidate column headers containing `Practice grid-r0c1`; cells for `R-SLOPE-AVAILABILITY`.

**Observed:** At 1440x900 the table begins around y=436, with its first data row beginning around y=687. Only that first requirement row is presented in the initial working viewport. The shell and control region occupy roughly half the height; each candidate header repeats six zero-inclusive status counts, origin, and selection control. Individual cells repeat support, FINAL and a disclosure. Even 1920x1080 presents only two complete requirement rows and part of a third. Nine requirements require substantial vertical inspection before an operator can understand the situation.

**Impact:** This is the primary operational table, but cannot support fast cross-requirement fault detection. It scores below the standard's density-with-order intent, even though contained scrolling itself is allowed.

**Fix:** Compact the run summary, move optional contextual prose into a disclosure, put selection in a compact header control, summarize counts on one or two short lines, and make the closed matrix cell a single compact status/value/support layout. Keep rationale in expansion. Target several complete requirement rows in the initial 1440x900 viewport. Preserve all exact values and usable touch targets.

### 2. P1 — Mobile run identity and pinned revisions disappear behind collapsed context

**Evidence:** `S07-390-dark-default.png`, `S12-390-light-default.png`, compared with `S07-1440-dark-default.png`.

**Semantic selector:** button with visible `SYNTHETIC Run context` and plus indicator; run-state region containing `Lifecycle` and `Latest modeled test`.

**Observed:** Mobile initially shows lifecycle and latest result, but the run-context section is collapsed. The mission name and rover/contract/run revision badges visible on desktop are absent from that initial header. The passport later names contract revision 2, but does not restore the pinned rover/run identity in the shared header.

**Impact:** A screenshot or handoff of a mobile qualification result lacks the revision context that makes it safe to interpret. The standard calls for pinned revision badges; requiring expansion makes those badges nonpersistent.

**Fix:** Keep a compact, wrapping mission/run identifier and contract/rover revisions visible under the two status columns. Reserve collapse for secondary context. This is an appearance issue; whether expansion actually works was not tested.

### 3. P2 — Candidate table is visually secondary to a low-information map

**Evidence:** `S06-1440-light-default.png`.

**Semantic selectors:** table caption `Candidates · 6 of 6 visible`; `Select candidate` row buttons; map notice beginning `Offline extent view · WGS84`.

**Observed:** The candidate table is approximately 442 px wide beside a roughly 662 px map. It displays three rows in the visible working height; the Origin column is off to the right. Each selection button wraps onto two lines, increasing row height. The map devotes a broad panel to six labelled rectangles while provenance and selection details demand horizontal table scrolling.

**Impact:** The standard explicitly makes the list the primary object. Here the operator must scroll for essential selection/provenance context while the secondary view dominates space.

**Fix:** Give the table more width or stack it above a shorter map. Use a compact single-line row action, concise visible origin labels and expandable provenance. Keep all six candidates readily comparable in the ordinary desktop viewport.

### 4. P2 — Mobile navigation cuts off labels without an explicit overflow cue

**Evidence:** `S06-390-light-default.png`, `S07-390-dark-default.png`, `S12-390-light-default.png`.

**Semantic selectors:** workspace link `About and licences`; run navigation link/tab `Compatibility`.

**Observed:** Workspace navigation ends mid-label at `About and lice…` without a visible ellipsis; run navigation ends in `Compatibil…` at the viewport edge. Neither strip shows a visible scroll hint, end fade, next control or overflow menu. This differs from the tables, which explicitly instruct horizontal scrolling.

**Impact:** Destinations after Qualification/Compatibility are difficult to discover on mobile, and clipped labels look unfinished. This is an **open X-26 visible clipping concern**. The screenshot does not establish whether a tooltip, full-value expansion or keyboard access exists.

**Fix:** Use an overflow menu or clearly signposted horizontal tab strip with edge controls and selected-tab visibility. Fit workspace navigation in a menu or wrap complete labels. Verify focus and text-spacing behavior separately.

### 5. P2 — Evidence remains a side overlay on mobile instead of the specified bottom sheet

**Evidence:** `evidence-drawer-390-dark-default.png`; compare `operations-drawer-390-light-default.png`.

**Semantic selector:** drawer headed `Evidence receipt`.

**Observed:** Evidence opens as a full-height right-side drawer, leaving an approximately 38 px sliver of unrelated background at the left. Operations uses a bottom sheet. The narrow evidence drawer forces receipt metadata into a long single-column sequence before the measurement and limitation sections.

**Impact:** Two related secondary panels use different mobile presentation and evidence gives away width without giving useful context. The standard requires bottom-sheet drawers below desktop thresholds.

**Fix:** Use the shared full-width mobile bottom-sheet pattern for evidence, with a clear header/close control and internal scroll. Place claim/value/support near the top, with verbose provenance below. Do not change focus semantics without testing them.

### 6. P2 — Passport's digest precedes the material scientific limitation

**Evidence:** `S12-1440-dark-default.png`, `S12-390-light-default.png`.

**Semantic selectors:** heading `Manifest digest`; publication badge `LIMITED`; text `Physical obstacle clearance is UNKNOWN at 60 m support.`

**Observed:** The headline and LIMITED badge are followed by the large Manifest digest heading and hash. The specific reason the claim is limited comes afterward. On the 390 px initial capture, that physical-clearance limitation falls below the visible document region while the digest occupies the available space.

**Impact:** Operators can see that a claim is limited without seeing the condition that constrains it. Technical identity is being prioritized over the key interpretation limit.

**Fix:** Put the assurance explanation and clearance limitation directly beneath LIMITED, before the digest. Keep digest and copy available in a quieter metadata row or later document section. Preserve the complete hash and exact limitation text.

### 7. P2 — PROVE IT is presented before the benchmark preview

**Evidence:** `S10-1440-dark-default.png`.

**Semantic selectors:** button `PROVE IT`; disclosure `Accepted benchmark requirements (4)`; table caption `Frozen benchmark preview`.

**Observed:** The large PROVE IT control appears above the accepted benchmark disclosure/table. The standard places benchmark preview directly above the action. The active control thus precedes the information defining the test it initiates.

**Impact:** A fatigued operator can launch before reviewing the frozen limits. This is ordering, not a claim that the underlying test is incorrect.

**Fix:** Put the compact benchmark preview and accepted contract revision before PROVE IT. Place the action at the end of the review sequence and retain the disabled reason when completed.

### 8. P3 — Connection-state specimens reuse the same silhouette

**Evidence:** full `styleguide-dark-default.png` and `styleguide-light-default.png`, `ConnectionIndicator` specimen.

**Semantic selector:** component region headed `ConnectionIndicator`, containing `connected`, `Updates paused`, `reconnecting`.

**Observed:** All three displayed connection states have the same hollow-circle marker. Text distinguishes them, but the expected secondary shape cue does not.

**Impact:** Peripheral state scanning depends entirely on text. This misses the standard's connection shape distinction, though it does not constitute colour-only communication because words remain visible.

**Fix:** Assign distinct simple neutral silhouettes to connected, paused and reconnecting, retaining the words; show scoped elapsed reconnect time when applicable. Verify actual behavior separately.

### 9. P3 — Numeric presentation varies across editing and assessment

**Evidence:** `S03-1440-dark-default.png`, `S08-1440-dark-default.png`.

**Semantic selectors:** numeric fields `Mass (kg)`, `Maximum slope (deg)`, `Battery capacity (Wh)`, `Nominal speed (m/s)`; compatibility row `Maximum surface slope`, required-value cell.

**Observed:** Inputs show `42`, `18`, `1800`, `0.5`, whereas the standard's display contract specifies 1 dp kg/slope/Wh and 2 dp speed. The assessment renders slope `18.0 deg`, while its ranges repeat the unit at both ends (`12.0 deg–18.0 deg`) rather than `12.0–18.0 deg`.

**Impact:** Inconsistent display precision weakens quick transcription and comparison. Static images cannot establish whether fields normalize on blur.

**Fix:** Normalize displayed saved values through the shared quantity formatting contract and use a single unit at the end of ranges. Keep input editing tolerant and do not introduce false measurement precision beyond the declared display convention.

## Open X findings and complete X disposition

**Confirmed open visual concern: X-26 (clipped mobile navigation), defect 4.** Whether accessible full labels/overflow navigation already exist is unverified. Do not count normal, explicitly labelled contained table scrolling as an X-26 failure.

| X item(s) | Disposition from this permitted evidence |
|---|---|
| X-01 | No visible emoji in inspected operational views. Source, fixtures and alt text unverified. |
| X-02–X-08 | No observed surface gradients, glass, glow, large-radius decorative forms, hero/marketing sections, space decoration or feature-card grids. Scientific map swatches are data. Full styleguide's specimen grid is component documentation, not a feature-marketing grid. |
| X-09 | No operational placeholder copy observed. `Example`/`First`/`Second` in the dev component styleguide are demonstration labels, not evidence of unfinished operational content. |
| X-10 | Numeric values look aligned; computed tabular-numeral settings unverified. |
| X-11 | Generally legible at original detail; no numerical contrast/size certification from screenshots. No confirmed open finding. |
| X-12 | No all-caps paragraphs or shouty headings observed. Status labels, IDs and mode labels are appropriate short labels. |
| X-13 | Selects/file controls have coordinated styling. Checkboxes look native-like but screenshots do not establish raw browser markup or a leak; no confirmed X-13 finding. |
| X-14 | Scoped retrieval text is visible. Elapsed time, resolution and skeleton stability cannot be inferred from one loading frame. No confirmed open finding. |
| X-15 | No important result shown solely in a toast; persistent result/limitation rows visible. Toast specimen says `View preference saved`, an appropriate low-impact use. |
| X-16 | Evidence is a drawer, operations a sheet, help one dialog. No modal stacking observed. Mobile drawer direction is defect 5, not evidence of a modal violation. |
| X-17 | Operational icons generally accompany labels; icon-only close/copy/zoom/help controls exist. Accessible names/tooltips cannot be verified. Glyph-only styleguide specimen is intentionally demonstrating glyphs. |
| X-18 | No clear mixed-icon-set defect observed; source/stroke specifications unverified. |
| X-19 | No fake similarity gauge, radar, pie or percent-similarity observed. |
| X-20 | 3D/parallax/carousels absent in frames; autoplay behavior unverified. |
| X-21 | General spacing is orderly; precise 4 px grid compliance needs computed layout. Density issues above do not prove off-grid values. |
| X-22 | Typography appears coherent; font sources, number of families and CDN requests unverified. |
| X-23–X-24 | No NASA insignia, approval claim or marketing hype observed. Attribution disclaimer is visible in the full styleguide footer. |
| X-25 | Static captures cannot prove layout stability or stable sorting. Unverified. |
| X-26 | **Open:** mobile workspace/run navigation clips visible labels without visible overflow affordance; defect 4. No claim of page-wide desktop horizontal overflow. |
| X-27 | Dark canvas/text visibly use dark slate and off-white, with no apparent pure-black/pure-white theme. Exact computed colours unverified. |
| X-28 | No different visual language per screen; strong consistency observed. Responsive drawer-pattern mismatch is localized, not a wholesale different language. |
| X-29 | Source-only colour-literal rule cannot be assessed; unverified, not assumed failed or passed. |

The review finds nine actionable design defects, with one directly open X concern. The remaining issues concern operational hierarchy, responsive context, information allocation and component specification. Screenshots support a calm and credible foundation, but they do not support declaring the complete ISA-101-inspired acceptance gate passed. Fix the P1 issues first, then recapture the same operational views and verify interactive/accessibility behavior independently.


## Round3 — Accessibility and typography (verbatim)

# AnalogForge independent accessibility and typography review (R3)

Decision: **Not accepted.** Scores total 37/48; mean **3.083/4**. Density/spacing, accessibility feel and absence of X findings score below 3, and the mean is below 3.5. This is my independent judgment of the supplied visual evidence.

## Scope and limits

Read only the binding `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and images catalogued there. No source, previous reviews, history, handoffs, logs or reports were consulted. Delivered images and implementation were not changed. The full dark default styleguide was also inspected in six lossless original-scale crops generated in `/tmp` solely for review.

Screenshots establish appearance at the captured state. They do not establish accessible names, landmarks, HTML table semantics, focus order/return, keyboard scrolling, live announcements, tooltip availability, touch behavior, reduced motion, elapsed loading time, or zoom/text-spacing compliance. The semantic selectors below identify concrete controls by visible role/name/label; they are review locators to resolve against implementation, **not assertions that those DOM roles or labels currently exist**.

## Scores

| Exact criterion | Score (0–4) | Evidence and judgment |
| --- | ---: | --- |
| Hierarchy | 3 | S11-1440-dark-default.png separates Completed, latest PASS and attempt history. On mobile the shell consumes excessive height, and S10 puts the commitment action above its benchmark preview. |
| Restraint | 4 | S01, S07, S09-composite and S12 have neutral surfaces, restrained state colors, flat fills and no decorative space imagery. |
| Typography | 3 | Titles, body, labels and mono values are legible and consistent in inspected images. S03 uses poor-contrast Unknown input text and inconsistent numeric precision; see findings. Computed font and minimum-size compliance are unverified. |
| Density/spacing | 2 | S07-1440-dark-default.png exposes only the beginning of one requirement row after the tall matrix header. S05-390-light-default.png spends its entire working viewport on pre-map legend/context. |
| Tables | 3 | Numeric alignment, units, explicit support and state words are strong in S08 and S09-composite. Matrix and compatibility layouts require considerable scrolling; overflow is at least explicitly explained in table banners. Sticky behavior and table semantics are unverified. |
| States | 4 | S01 empty tables, loading-missions-1440-dark-default.png, error-rover-import-390-dark-default.png and the disabled PROVE IT in S11 have scoped messages and persistent explanation. Loading duration and eventual resolution are unverified. |
| Copy | 4 | Synthetic provenance, modeled-versus-physical limits and failure remediation are unusually clear. S12 explicitly refuses a physical clearance claim. No hype was observed. |
| Consistency | 4 | Shell, tabs, badges, borders, drawers and button treatments remain coherent across S01–S12 and both themes. |
| Map/chart integrity | 3 | S06 labels offline extents, source, WGS84 and scale; S05 distinguishes synthetic display raster from analysis support. Full styleguide charts show zero baselines, labels and adjacent data tables. Real geographic accuracy, full target histogram and playback cannot be established from these screenshots. |
| Accessibility feel | 2 | Drawer/dialog close controls show conspicuous focus rings and status badges combine words with silhouettes. Low-contrast Unknown text and incomplete mobile navigation labels remain concrete obstacles. Keyboard/screen-reader operation is unverified. |
| Crew-member credibility | 3 | Honest scope and evidence support encourage trust; matrix scan inefficiency and mobile navigation make sustained use less credible. |
| Absence of X-01–X-29 | 2 | X-11 is supported by sampled raster contrast; X-26 remains open for visibly clipped navigation labels without a visible expansion/overflow affordance. Source-only prohibitions cannot be certified from screenshots. |

## Defects, ordered by severity

### 1. High — meaningful Unknown field content falls below normal-text contrast

- Screenshot: `S03-1440-dark-default.png`.
- Semantic selectors: `getByLabel('Maximum obstacle height (m)')` and `getByLabel('Maximum route distance (m)')`, specifically their visible `Unknown` content.
- Observation: Unknown appears substantially dimmer than surrounding helper text and values. Sampling the first field's image rectangle x=1325–1395, y=586–606 finds a flat text color RGB(117,117,117) on RGB(23,31,41), yielding approximately **3.60:1**. This is screenshot-pixel evidence rather than computed CSS. The image cannot establish whether the text is a placeholder or disabled content; neither makes an important unknown measurement easy to read. The standard requires an explicit Unknown text state and X-11 prohibits low-contrast greys.
- Fix: render Unknown with the same accessible secondary-text token as the rest of the form, preserving its explicit unknown state. Recheck both themes and the unknown toggle's state. Confirm computed contrast and semantics independently.
- Open X: **X-11**.

### 2. High — mobile navigation clips destination names and conceals later destinations

- Screenshots: `S07-390-dark-default.png`, `S12-390-dark-default.png`, `S08-rover-conflict-390-light-default.png`, `S03-390-light-default.png`.
- Semantic selectors: `nav >> getByRole('tab', {name:'Compatibility', exact:true})`, `nav >> getByRole('tab', {name:'Passport', exact:true})`, and `nav >> getByRole('link', {name:'About and licences', exact:true})` (resolve equivalent link/tab roles if different).
- Observation: Compatibility is visibly cut mid-word at the right edge; later run tabs are outside the visible strip, including the current Passport destination in the S12 capture. The workspace link similarly ends at “About and lice…”. Unlike the table overflow banners, neither navigation strip visibly explains overflow or offers a next/previous control. Screenshot evidence does not prove these destinations are unreachable by swipe or keyboard, nor that full accessible names are missing; the observable defect is incomplete labels and poor discoverability.
- Fix: provide an explicit overflow menu or visible next/previous affordance, keep the current destination visible and fully named, and allow labels to remain intact. Verify focus auto-scroll and full accessible names.
- Open X: **X-26**, pending correction or explicit evidence of accessible full-value expansion; horizontal scrolling behavior alone was not tested.

### 3. Medium — qualification matrix header consumes its useful comparison viewport

- Screenshot: `S07-1440-dark-default.png`; comparison: `evidence-drawer-1440-dark-default.png` (by-candidate view).
- Semantic selectors: `table:has(caption:text-is('Requirement qualification · by requirement')) thead`, candidate header `getByRole('columnheader', {name:/Practice grid-r0c1/})`.
- Observation: the table begins near y=436; its candidate header extends from about y=505 to y=686. Only about 126 px remain before the working pane ends, showing the start of one requirement row. Six separate status-count lines and a selection button in every candidate header push evidence below the fold. This undermines the whole-screen engineering-matrix brief even though content may scroll correctly.
- Fix: compress status counts into a compact two-line summary with an explicit details control, move selection actions out of each header's vertical stack, and reserve substantially more height for requirement rows. Keep exact counts available to keyboard users.
- X status: a density/usability defect; no additional X code asserted.

### 4. Medium — mobile target opens on chrome and repeated legend text, with no terrain visible

- Screenshot: `S05-390-light-default.png`.
- Semantic selectors: `main >> getByRole('heading', {name:'Target evidence'})`, target-region `getByRole('region', {name:/Mars target region/})`, and its slope legend.
- Observation: the shell/run navigation ends around y=326; the target panel starts around y=431. Between the panel heading, source/support statement, four legend lines and two synthetic notices, the map and measurement results are entirely outside the visible working area above the persistent operations bar at y=758. Each legend line repeats both the interval label and the same numeric limits. The entry view provides little working evidence for its space.
- Fix: compact repeated legend intervals to one value range each, combine the synthetic notices without losing their warning, and expose an initially visible map or measurement summary. Collapse secondary context on narrow viewports while retaining a clear expansion control.
- X status: density defect, not proof of inaccessible offscreen content or obscured focus.

### 5. Medium — PROVE IT precedes the evidence needed to review the action

- Screenshots: `S10-1440-light-default.png`, `S10-390-dark-default.png`.
- Semantic selectors: `getByRole('button', {name:'PROVE IT', exact:true})` and `getByText('Frozen benchmark preview', {exact:true})` within Accepted experiment.
- Observation: PROVE IT appears above the accepted benchmark requirements. On mobile the button is fully visible while none of the benchmark rows are initially visible. The standard §9.4 explicitly places the benchmark preview directly above PROVE IT. The play-in-square glyph specified there is also absent in the captured button.
- Fix: place a compact accepted benchmark preview before PROVE IT in reading and visual order, retain the candidate/revision context, and add the specified labeled-action glyph. Confirm the preview remains available before activation by keyboard and on mobile.
- X status: component/hierarchy defect; no slop code asserted.

### 6. Low — rover form spreads a single profile across three columns and inconsistent number formatting

- Screenshot: `S03-1440-dark-default.png`; comparison: `S08-1440-light-default.png`.
- Semantic selectors: `getByRole('group', {name:/Rover profile/})`, `getByLabel('Mass (kg)')`, `getByLabel('Maximum slope (deg)')`, `getByLabel('Nominal speed (m/s)')`.
- Observation: mass 42, slope 18 and speed 0.5 appear in a three-column form. The standard calls for single-column field groups, allowing paired columns only for min/max or bounding-box edges. Its precision contract specifies mass and slope to one decimal and speed to two. The compatibility table meanwhile shows slope as 18.0, so the same value changes display conventions across views. A screenshot cannot establish whether normalization occurs on blur.
- Fix: group related rover fields in a single sequential column (paired fields only when meaningful) and normalize display to 42.0 kg, 18.0 deg and 0.50 m/s after editing, with a shared formatter.
- X status: typography/consistency defect; no new X code asserted.

### 7. Low — connection variants have identical silhouettes

- Screenshot: `styleguide-dark-default.png`, ConnectionIndicator block; full image inspected at original scale via crop.
- Semantic selector: ConnectionIndicator sample containing `connected`, `Updates paused`, `reconnecting`.
- Observation: all three variants use the same small hollow circular marker. Words do distinguish them, so this is not a color-only failure. It does fail the standard's explicit request that connection states differ in glyph shape too, reducing quick peripheral recognition.
- Fix: use distinct neutral silhouettes for connected, paused and reconnecting, keeping the visible words. Demonstrate all variants together in both themes.
- X status: no additional X code asserted.

## Open X findings and prohibited-item coverage

- **X-11: open**, low-contrast Unknown content documented above. Minimum font sizes, line heights and other contrast pairs require computed verification; no blanket failure is inferred.
- **X-26: open**, mobile navigation clipping/discoverability documented above. This review does not assert horizontal page overflow, absence of an offscreen full label, or lack of a tooltip without DOM/behavior evidence.
- No visible evidence of X-01–X-08, X-12, X-15–X-16, X-18–X-20, X-23–X-24, X-27–X-28 was found in the inspected frames. This is a visual observation, not source-scan certification. Styleguide specimen labels containing “Example” identify demonstrations rather than fabricated production measurements, so I do not flag X-09 from those labels.
- X-10, X-13–X-14, X-17, X-21–X-22, X-25 and X-29 include DOM, behavior, exact metrics, font loading or source requirements that screenshots cannot fully decide. The loading images have scoped text; elapsed-time behavior remains unverified. A default-looking control alone is insufficient to prove a prohibited native implementation.
- No other X finding is asserted. Missing proof is not treated as proof of a violation or as a passed gate.

## Inspected image inventory

All names refer to images in the supplied catalog. Desktop defaults: `S01-1440-dark-default.png`, `S02-1440-light-default.png`, `S03-1440-dark-default.png`, `S04-1440-light-default.png`, `S05-1440-dark-default.png`, `S06-1440-light-default.png`, `S07-1440-dark-default.png`, `S08-1440-light-default.png`, `S09-1440-dark-default.png`, `S09-composite-1440-light-default.png`, `S10-1440-light-default.png`, `S11-1440-dark-default.png`, `S12-1440-light-default.png`. Narrow/medium: `S03-390-light-default.png`, `S04-edited-draft-390-dark-default.png`, `S05-390-light-default.png`, `S06-1024-dark-default.png`, `S07-390-dark-default.png`, `S08-rover-conflict-390-light-default.png`, `S10-390-dark-default.png`, `S12-390-dark-default.png`. Overlays/states: `evidence-drawer-1440-dark-default.png`, `evidence-drawer-390-light-default.png`, `operations-drawer-1440-light-default.png`, `operations-drawer-390-dark-default.png`, `shortcut-dialog-390-light-default.png`, `loading-missions-1440-dark-default.png`, `error-rover-import-390-dark-default.png`. Full component captures: `styleguide-dark-default.png`, `styleguide-light-compact.png`, `styleguide-dark-comfortable.png`.

This report is a visual design assessment, not a WCAG certification or a functional acceptance result.


## Round3 — Hostile slop detector (verbatim)

# AnalogForge independent hostile design review — R3

Verdict: FAIL the specified design acceptance gate. Mean 3.00/4; density/spacing, tables and absence of X findings are below 3. The application largely avoids fashionable template decoration, but the evidence-first instrument brief is compromised by space allocation and several unfinished primitives. This review does not assert that it was AI generated.

## Scope and evidence limits

Read only the binding `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and catalog-listed images. No implementation, history, prior reviews, handoffs, logs or reports were read. Opened actual screenshots with `view_image`; inspected the entire 5610 px default component styleguide in both themes through four original-resolution crops per theme. Crops were temporary review aids; delivered screenshots were not modified.

All selectors below are concrete semantic locators for the pictured element, not verified DOM selectors or claims that a particular test id exists. For example, `table[caption="Requirement qualification · by requirement"]` identifies a table by its visible caption. Static pictures cannot establish actual keyboard navigation, tooltip availability, native HTML element types, accessible names, computed contrast/font sizes, CSS literals, overflow behavior, motion, or data accuracy. No such behavior is certified here.

Inspected screenshots:

- Desktop S01–S12: `S01-1440-dark-default.png`, `S02-1440-light-default.png`, `S03-1440-dark-default.png`, `S04-1440-light-default.png`, `S05-1440-dark-default.png`, `S06-1440-light-default.png`, `S07-1440-dark-default.png`, `S08-1440-light-default.png`, `S09-1440-dark-default.png`, `S10-1440-light-default.png`, `S11-1440-dark-default.png`, `S12-1440-light-default.png`.
- Additional working views: `S07-1024-light-default.png`, `S05-1920-light-default.png`, `S09-composite-1440-light-default.png`.
- Mobile: `S07-390-dark-default.png`, `S06-390-light-default.png`, `S12-390-light-default.png`.
- Drawers/dialog: `evidence-drawer-390-dark-default.png`, `evidence-drawer-1440-light-default.png`, `operations-drawer-1440-light-default.png`, `shortcut-dialog-390-dark-default.png`.
- States: `loading-missions-1440-dark-default.png`, `error-rover-import-390-light-default.png`; disabled PROVE IT in S11 and disabled control in the full guides.
- Full guides: `apps/web/docs/design-review/styleguide-dark-default.png` and `styleguide-light-default.png` (linked by the catalog).

## Twelve criterion scores

| Criterion | Score / 4 | Independent judgment |
| --- | ---: | --- |
| hierarchy | 3 | Distinct lifecycle and modeled-test outcome are useful. Matrix chrome and passport digest compete with the scientific work. |
| restraint | 4 | Flat neutral panels, restrained accents, state colors, no marketing hero, gradients, glow, space wallpaper or decorative illustration observed. |
| typography | 3 | Readable common scale; monospaced quantities and ids; good numeric alignment. Some ranges/legends are needlessly repetitive. Computed fonts and metrics unverified. |
| density/spacing | 2 | At 1024 the matrix shows no complete requirement row; desktop candidate evidence is compressed beside the larger geometry view. |
| tables | 2 | Basic tables and coverage table are orderly, but the main qualification table has an oversized header and candidate table forces lateral scrolling despite substantial adjacent map space. |
| states | 4 | Scoped loading skeletons, explicit empty states, persistent import error with cause and next step, and a visible disabled reason. Duration/resolution behavior unverified. |
| copy | 3 | Generally plain and scientifically bounded. Range notation and duplicative legend text reduce precision and scanning efficiency. |
| consistency | 4 | Same shell, badges, borders, typography and controls across desktop/mobile and themes; no separate visual language per screen observed. |
| map/chart integrity | 3 | Honest synthetic/geometry-only labels, scale/attribution on candidate map, chart axes and adjacent tables in guide, explicit thresholds in S05. Candidate map receives disproportionate visual priority. Scientific correctness not tested. |
| accessibility feel | 3 | Visible focus around drawer/dialog close, clear labels and glyph+word states. Mobile clipped navigation and native-looking checkbox remain concerns. Keyboard/contrast compliance unverified. |
| crew-member credibility | 3 | Uncertainty, preliminary assessments, synthetic limits and immutable attempts are candid. Matrix efficiency and passport ordering fall short of the six-hour-shift brief. |
| absence of X-01–X-29 | 2 | Open visual X-13 and X-26 findings below; source-only and temporal rules cannot be cleared from screenshots. |

Total 36/48; arithmetic mean **3.00/4**. Acceptance requires every criterion >=3 and mean >=3.5. Neither condition is met.

## Defects ordered by severity

### 1. P1 — Qualification header crowds the actual qualification out of the viewport

Evidence: `S07-1024-light-default.png`; `S07-1440-dark-default.png`.

Semantic selectors: `table[caption="Requirement qualification · by requirement"] thead`; candidate header containing `Practice grid-r0c1`, six status-count lines and `button[name="Selected"]`; `run-state-banner`; `heading[name="Qualification"]` and its control group.

At 1024×768 the table starts around y=409, its candidate header runs roughly y=479–660, and only a sliver of the first requirement remains before the work viewport ends around y=681. At 1440×900 only part of one requirement is visible. Most of the view is shell, heading/filter spacing, caption and repeated per-candidate counts. This is an observed space-allocation defect, not a claim that rows cannot be reached by scrolling.

Fix: compress the banner and heading/filter stack; put candidate counts into a compact summary line or expandable summary; move selection actions out of tall header cells. Preserve sticky identity but reserve space for several complete requirement rows at 1024×768. The specification calls this the money screen; its rows should dominate it.

### 2. P2 — Candidate list is squeezed while the secondary geometry view gets the wider panel

Evidence: `S06-1440-light-default.png`; corroborating mobile `S06-390-light-default.png`.

Semantic selectors: `table[caption="Candidates · 6 of 6 visible"]`; sibling map region identified by `Offline extent view · WGS84 · no basemap imagery`; `button[name="Select candidate"]`.

The desktop candidate table has about 442 px while the adjacent geometry view has about 662 px. Candidate names wrap, selection labels wrap to two lines, and provenance columns disappear into the horizontal scroller. The map has six simple extent boxes and generous empty space. The table does have an explicit horizontal-scroll instruction, so this intentional table overflow is not itself an X-26 finding. The defect is prioritization and density: evidence discovery becomes more cumbersome than the secondary geometry presentation.

Fix: allocate enough width to keep name, status, selection and origin visible, or make the map collapsible/stacked when the list cannot fit. Move long provenance into row expansion while retaining its origin summary. Default to the candidate evidence as the primary object as required by §10.

### 3. P2 — Mobile navigation leaves controls visibly cut off with no visible overflow explanation

Evidence: `S07-390-dark-default.png`, `S06-390-light-default.png`, `S12-390-light-default.png`.

Semantic selectors: workspace `nav` link beginning `About and lice…`; run navigation tab beginning `Compatibil…`; run `nav` following `Run context`.

The rightmost workspace label and a run-tab label end abruptly at the viewport boundary. No visible scroll instruction, overflow button or edge control explains access to the remainder. Unlike the tables, these navigation strips do not visibly explain their overflow. This is an open **X-26 visual finding**: clipped navigation text. Whether swipe, keyboard focus or an accessible full name exposes it is unverified; screenshots do not prove a missing accessible name.

Fix: use a visible overflow menu or a labeled horizontal navigation scroller with clear edge affordances. Keep each visible label intact or expose its full name through an explicit, discoverable expansion mechanism. Preserve the selected tab and access to every destination at 390 px.

### 4. P2 — Passport prioritizes the manifest hash ahead of the material scientific limitation

Evidence: `S12-1440-light-default.png`; especially `S12-390-light-default.png`.

Semantic selectors: passport `heading[name="Manifest digest"]`; subsequent paragraph `Physical obstacle clearance is UNKNOWN at 60 m support.`; `table[caption="Requirement evidence summary"]`.

The digest becomes the next large heading after the assurance badge. On mobile the long digest and copy control consume the remaining initial viewport, while the actual clearance limitation begins at the bottom and the requirement evidence summary is below it. The hash is useful provenance, but it is less decision-critical than what is unknown. The specified passport order puts the manifest digest after requirements, attempts and GAP/UNKNOWN lists.

Fix: place the scientific limitations immediately after the assurance statement, then the requirements/attempts and GAP/UNKNOWN lists; move digest/export provenance below that evidence, using a compact hash treatment and copy action.

### 5. P2 — Checkbox treatment looks native and inconsistent with the surrounding primitives

Evidence: `S07-1440-dark-default.png`, `S07-390-dark-default.png`, full `styleguide-dark-default.png` and `styleguide-light-default.png`, LayerPanel section.

Semantic selectors: `checkbox[name="Hide optional requirements"]` (mobile visible label `Hide optional`); `checkbox[name="Synthetic slope"]` in LayerPanel.

The matrix checkbox appears as an oversized dark gray square, with a different fill/border treatment from the adjacent token-styled buttons. The guide's checked layer checkbox has the characteristic solid blue native check treatment. Their raw browser-like appearance breaks the otherwise deliberate primitive language. This is an open **X-13 appearance finding**; it is not a verified claim about the underlying HTML, browser defaults or CSS implementation.

Fix: provide a common checkbox primitive with matching neutral control fill, deliberate border/check glyph, and consistent selected/focus treatment in both themes. Keep the large touch target around a compact visual checkmark rather than scaling a raw-looking square.

### 6. P3 — Range and legend notation repeats the same units and boundaries

Evidence: `S08-1440-light-default.png`; `S05-1440-dark-default.png`; `S05-1920-light-default.png`.

Semantic selectors: `table[caption="Rover versus selected candidate · Preliminary"] td[column="Required value"]` for `Maximum surface slope`; target slope legend entries starting `0–5 deg`, `5–12 deg`, `12–18 deg`, `18–25 deg`.

Compatibility displays `12.0 deg–18.0 deg`, repeating units inside the range; the standard requires `12.0–18.0 deg`. Each target legend repeats an interval label and then the same endpoints, such as `0–5 deg · 0.0 deg – 5.0 deg`. At 1440 this pushes the legend into several lines before the data. This is visible notation/redundancy, not a claim that numerical values are wrong.

Fix: format each interval once with deliberate precision and the unit once. Retain source mode and support as separate concise lines. Share the quantity/range formatter across compatibility and legends.

## X-01–X-29 disposition

Open visual findings: **X-13** (native-looking checkbox primitives, finding 5) and **X-26** (mobile clipped navigation labels without visible overflow explanation, finding 3). Therefore the evidence does not support the statement "no open findings".

| X item | Screenshot-only disposition |
| --- | --- |
| X-01 emoji | None observed. Alt text/source/fixtures unverified. |
| X-02 gradients | None visibly observed; source declarations unverified. |
| X-03 glass | None observed. |
| X-04 glow/neon | None observed; focus outlines are functional, not counted as glow. |
| X-05 pills/large radii | None visually apparent; exact computed radius unverified. |
| X-06 hero/marketing | None observed. |
| X-07 space decoration | None observed; planetary panels are labeled data/geometry. |
| X-08 feature-card grids | None in product screens. The component guide inventory grid is functional documentation, not a feature grid. |
| X-09 placeholder copy | No open product finding. Generic illustrative labels in the component guide are demonstrations; they are not evidence of a placeholder leaking into a working route. Source scan unverified. |
| X-10 numeral alignment | No clear visual violation; numeric tables appear aligned. Computed tabular numeral setting unverified. |
| X-11 text/contrast | No confirmed visual violation; computed size, line height and WCAG contrast unverified. |
| X-12 shouty copy | No open finding; status labels and domain identifiers do not constitute all-caps paragraphs. |
| X-13 browser defaults | OPEN — checkbox appearance. Underlying native/default styling unverified. |
| X-14 loading | No open finding: pictured mission loading is scoped and shaped; elapsed time and eventual resolution unverified. |
| X-15 important toasts | No such toast observed; guide toast is a harmless view-preference confirmation. |
| X-16 modal misuse | No misuse observed; help dialog is expressly permitted by the keyboard specification. |
| X-17 icon labeling | No confirmed finding. Icon-only controls exist, but accessible names/tooltips cannot be assessed from stills. |
| X-18 mixed icons | No obvious mixed visual set; source library/stroke settings unverified. |
| X-19 fake similarity viz | None observed; explicit screening-order caveat, scientific tables and ordinary charts. |
| X-20 parallax/autoplay | No visual evidence; motion cannot be certified. |
| X-21 off-grid spacing | Exact computed spacing unverified; poor allocation is documented separately without inventing token violations. |
| X-22 fonts | No obvious display typography; actual fonts/CDN requests unverified. |
| X-23 NASA branding | No logo or approval claim observed. |
| X-24 hype | None observed. |
| X-25 shift/resort | Unverifiable from stills. |
| X-26 clipping/overflow | OPEN — mobile navigation. Labeled table scrolling is not counted as a violation. Page-level overflow and hidden tooltip/focus expansion unverified. |
| X-27 pure black/white dark | No visibly pure-black/pure-white dark treatment; exact token values unverified. |
| X-28 inconsistent screen language | No broad violation observed. Local checkbox issue is covered under X-13. |
| X-29 color literals | Unverifiable without source, which was intentionally not read. |

The strongest positive evidence is operational honesty: preliminary, unknown, synthetic and modeled scope are exposed rather than replaced with a giant success score. The acceptance failure is driven by observable scanning efficiency and unfinished control/navigation presentation, not by decorative spectacle.


## Round3 disposition

Not accepted. Corrective work addresses matrix/header density, persistent compact revisions, explicit mobile navigation affordances, placeholder contrast, checkbox appearance, passport limitation/digest order, mobile evidence sheets, preview-before-action ordering, interval notation, connection silhouettes and saved-input precision. Specific screen briefs in architecture41 §10 prescribe S03three-column fields and S06map60%/list40%; these proportions are retained while the concrete readability/scanning defects are corrected. Fresh audit and review are required.

## Round4 — source b96462a

The full automated gate passed30 browser tests,402 visual reports,392 screenshots and zero findings/skips. Fresh reviewers received only architecture41, the final screenshot catalog/images and the exact12-criterion rubric. Personas: mission-operations HMI, accessibility/typography, hostile slop detector. They were instructed to inspect actual legible images, preserve §10 specific proportions, cite concrete selectors/files, supply five defects or evidenced fewer, and distinguish observed visual defects from source/behavior unknowns. Prior scores, fixes and reports were not supplied.


### Verbatim hmi reviewer report

# AnalogForge independent mission-operations HMI review — R4

Decision: **NOT ACCEPTED** under §20. Scores total **39/48**, mean **3.25/4**. Every criterion reaches 3, but the required mean of 3.5 is not met. The screenshots show a restrained, credible instrument foundation, with remaining screen-brief and operator-orientation defects. No 0–1 blocker was observed.

## Scope and evidence boundary

Read only `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and images named by that catalog. No source, logs, prior reviews, handoffs, memory, or live application were consulted. The catalog's assertion that an automated audit passed was not treated as independent proof.

Opened S01–S12 default screenshots at 1440×900 and 390×844 in both dark and light themes (48 screen images). Also opened evidence-drawer, operations-drawer, shortcut-dialog, S08-rover-conflict, S04-edited-draft, S09-composite, loading-missions and error-rover-import at those two widths in both themes (32 images). Supplementary inspection: S03-1920-dark-default, S06-1920-dark-default, S06-1024-light-default, S07-1024-dark-default. All six complete component guides listed in the catalog were inspected from top through footer in 1000-pixel-high, full-width crops: dark/light × compact/default/comfortable. Crops were temporary inspection derivatives; supplied images were not edited.

Findings below concern observable presentation. Selectors are **semantic locators**, expressed in Playwright-like role/label notation, not claims about inspected DOM attributes. No claim is made about working keyboard handlers, accessible names, focus restoration, URL synchronization, scroll reachability, exact computed contrast/font sizes, source purity, animation, runtime data validity, print output or hidden content. Content below a screenshot viewport is unverified, not presumed absent.

## Scores

| §20 criterion | Score | Screenshot evidence and rationale |
|---|---:|---|
| Hierarchy | 3 | S07 and S11 separate lifecycle and scientific outcome; status badges are distinct and persistent. S03 places the broad import region before the operational field review and lacks the prescribed adjacent summary; S10 separates PROVE IT from its experiment panel. |
| Restraint | 4 | S01–S12 use quiet opaque surfaces, neutral chrome and state colour. No decorative space imagery, gradients, hero or similarity gauges observed. |
| Typography | 3 | Legible body hierarchy and aligned mono numeric values in S07/S08/S10; S06's rank header visibly breaks within the word at all inspected desktop widths and mobile. |
| Density and spacing | 3 | Shell, tables and guides have a consistent rhythm. S03's full-width upper controls consume room intended for simultaneous editing/summary; S11 first attempt has generous prose spacing. |
| Tables | 3 | Qualification matrix, compatibility and composite coverage read as engineering tables, with support and status words. S06 rank header and operations row anatomy still need correction. Horizontal table overflow is explicitly labelled and is not treated as page overflow. |
| States | 4 | Persistent pending/pass/fail/unknown/gap evidence, empty portfolio, import error with remediation, scoped loading, and disabled PROVE IT explanation are visibly designed. |
| Copy | 3 | Scientific scope and synthetic disclaimers are candid. Mobile navigation has ambiguous “Mission” labeling; “1 bytes” in the import error is a small polish defect. |
| Consistency | 3 | Shared shell, badge, table, drawer and focus styling persists across screens/themes. S03 unknown controls and evidence drawer structure diverge from the specified patterns. |
| Map/chart integrity | 3 | S05 labels synthetic raster support and chart axes/thresholds; adjacent data table is visible. S06 explicitly says no basemap imagery and gives scale/source text. Guide legend lacks swatches and its ScaleBar represents comparison support rather than a clear map-distance scale. Numerical/projection correctness is unverified. |
| Accessibility feel | 3 | Clear close-button focus rings in both overlay themes; coarse targets and mobile table overflow hints are visible. Mobile location labeling and S06 broken header impair effortless scanning. Keyboard behavior and measured AA compliance remain unverified. |
| Crew credibility | 3 | S11 preserves failed attempts and labels modeled execution; S12 prominently states clearance UNKNOWN and LIMITED assurance. Missing adjacent rover summary and weaker evidence/operations anatomy reduce review-at-a-glance confidence. |
| Absence of X-01–X-29 | 4 | No confirmed open X item in the inspected visual scope. This is a visual score, not certification of scan-only/source-only bans or temporal behavior. |

## Defects, ordered by severity

### 1. P2 — S03 lacks the prescribed simultaneous profile summary/import layout

- Evidence: `S03-1440-dark-default.png`, `S03-1440-light-default.png`, `S03-1920-dark-default.png`.
- Semantic selector: `main → region/section headed “Rover profile”`; `getByLabel('Use an existing revision')`; import region labeled “Import rover JSON”.
- Observable issue: The numeric fields **do use a three-column grid**, as §10 specifically prescribes. However, the form occupies the full working width and import spans above it. The right side is occupied by editable fields, with no adjacent read-only profile summary or right-side import review panel in the captured desktop composition. This is a layout nonconformance, not a claim that a summary cannot exist farther down the page.
- Operator impact: A planner cannot cross-check a compact, read-only overview alongside edits in the intended desktop view.
- Fix: Reserve a right-hand column for an entered-values-only summary and import validation table. Keep the three-column field grid in the form region; stack the summary below on narrow screens. Show explicit “No file imported”/“Awaiting validation” rows when applicable.
- Standard: §10 S03; §1 density with order.

### 2. P2 — Mobile run navigation presents conflicting location cues

- Evidence: `S05-390-dark-default.png`, `S07-390-light-default.png`, `S08-390-dark-default.png`, `S12-390-light-default.png` (also S06/S09/S10/S11 in both themes).
- Semantic selector: run navigation between the previous/next arrow buttons, visible text “Mission”; adjacent “View: Qualification/Target/Passport” label.
- Observable issue: The center navigation item reads “Mission” on every inspected run page while the adjacent current-view label names Target, Qualification, Compatibility, Test lab or Passport. Without interacting, its purpose is ambiguous: selected destination, current tab, or a shortcut back to Mission.
- Operator impact: The navigation does not communicate its state at one glance, particularly when operating from the much smaller mobile viewport.
- Fix: If this is the active-view selector, synchronize its visible value with the current view. If it is an independent Mission link, label it “Go to mission” and visually distinguish it from the current-view selector. Preserve the adjacent explicit location label.
- Standard: §1 predictable consistency; §9.8 active navigation; §14.4 actionable labels.

### 3. P2 — Evidence drawer omits the specified claim/requirement reading structure

- Evidence: `evidence-drawer-1440-dark-default.png`, `evidence-drawer-1440-light-default.png`, `evidence-drawer-390-dark-default.png`, `evidence-drawer-390-light-default.png`.
- Semantic selector: drawer headed “Evidence receipt”; table caption “Receipt metrics”; disclosure “Source and computation provenance”.
- Observable issue: The visible drawer provides metric, value/support and limitations, but no visible Claim section or Linked requirement(s) section. Its header is the generic “Evidence receipt”; the identifier is a later body line rather than the header's primary identifier. The drawer has substantial blank space beneath the final provenance disclosure in desktop captures, so the missing top-level reading structure is directly observable. The unopened provenance payload is unverified.
- Operator impact: A reader must mentally reconnect the measured fraction to the requirement and qualifying claim after switching focus into the drawer.
- Fix: Use evidence ID + type in the header, then explicit Claim, Measured value/unit, Support/valid fraction, Source, Algorithm, Receipt/digest, Limitations and Linked requirements disclosures in the §9.6 order. State unavailable fields explicitly rather than silently omitting the section.
- Standard: §9.6; §1 evidence status and rigor.

### 4. P2 — PROVE IT is detached from its experiment panel

- Evidence: `S10-1440-dark-default.png`, `S10-1440-light-default.png`, `S10-390-light-default.png`.
- Semantic selector: `getByRole('button', {name:'PROVE IT'})`; section headed “Accepted experiment”.
- Observable issue: The benchmark preview is in the Accepted experiment panel, while the filled 48-pixel PROVE IT control is in the persistent bottom operations/evidence bar, outside that bordered panel. On mobile, a large amount of experiment content separates the visible command bar from the panel's heading.
- Operator impact: The exceptional primary command is visually grouped with drawer utility controls instead of the experiment it executes.
- Fix: Place the authoritative PROVE IT control and running stepper inside the Experiment panel, directly after the benchmark preview. A sticky contextual action may mirror it only if the grouping and affected candidate/contract remain explicit and the primary-action rule is preserved.
- Standard: §9.4; §10 S10/S11.

### 5. P2 — Rover numeric controls lose the required unit/unknown anatomy

- Evidence: `S03-1440-dark-default.png`, `S03-1440-light-default.png`, `S03-1920-dark-default.png`; complete `styleguide-dark-default.png` and `styleguide-light-default.png` FormField/NumberInput sections.
- Semantic selector: `getByLabel('Mass (kg)')`, `getByLabel('Battery capacity (Wh)')`, field group “Maximum obstacle height (m)” and its “Unknown” button.
- Observable issue: Units appear only in labels, not as noneditable suffixes adjacent to entered values. Optional unknown fields show an “Unknown” value plus another full-width “Unknown” button underneath, rather than the prescribed explicit known/unknown segmented choice.
- Operator impact: Repeated identical Unknown text obscures whether it is current state or an available action; numeric cross-checking requires looking away from the value to its label.
- Fix: Add unit suffixes within numeric controls and render explicit Known/Unknown segmented state for optional fields, with one visibly selected segment and a clearly disabled numeric control when unknown.
- Standard: §9.3; §10 S03.

### 6. P2 — Candidate rank column has the wrong label and breaks mid-word

- Evidence: `S06-1920-dark-default.png`, `S06-1440-dark-default.png`, `S06-1440-light-default.png`, `S06-1024-light-default.png`, `S06-390-light-default.png`.
- Semantic selector: Candidates table → first column header, visible “Order” split as “Orde”/“r”.
- Observable issue: §10 explicitly asks for “Screening order.” The shorter “Order” is used and still wraps inside the word, even at 1920 width. The 60% map / 40% list split itself is approximately correct: around 940/627 px at 1920 and 662/442 px at 1440, excluding gap. This finding must not be interpreted as a request to reverse the prescribed proportions.
- Operator impact: A critical ordering qualification is weakened and the header looks unfinished.
- Fix: Use “Screening order” with a sufficient minimum column width and wrapping only at the space; allow labelled table scrolling to absorb the width. Retain the 60/40 map/list composition and primary list position.
- Standard: §10 S06; §9.5 no mid-word clipping/wrapping; §14 precision.

### 7. P3 — Operations rows do not expose the prescribed actor/time columns

- Evidence: `operations-drawer-1440-dark-default.png`, `operations-drawer-1440-light-default.png`, `operations-drawer-390-dark-default.png`.
- Semantic selector: “Operations timeline” → first row “1 · Run state changed”.
- Observable issue: The row shows event title, “validating”, summary and an absolute timestamp at the far right. A role badge such as Planner/Terrain engine/Verifier is absent from the visible row; the event-title presentation differs from the specified stable seq → time → actor → summary anatomy. On mobile the timestamp is pushed beneath the summary.
- Fix: Show compact fixed sequence/time columns and a neutral actor badge before the summary. On mobile stack deliberately with actor adjacent to the event and preserve the full UTC value as secondary detail.
- Standard: §9.11; §10 Operations drawer.

### 8. P3 — Component guide's map primitives do not demonstrate complete scientific anatomy

- Evidence: all six `apps/web/docs/design-review/styleguide-{dark|light}-{compact|default|comfortable}.png`, bottom Legend, ScaleBar and LayerPanel sections.
- Semantic selector: guide section headed “Legend”; guide section headed “ScaleBar”; “Display layers” fieldset.
- Observable issue: Legend shows two textual bins without swatches; LayerPanel is just one checkbox without a source badge, opacity slider or inline legend. ScaleBar is an entire panel-width horizontal line labeled “480 m comparison support,” which describes analytical support rather than clearly identifying map ground distance. These are concrete deficiencies in the demonstrated guide primitives; they do not prove every live map uses those incomplete forms (S05 has visible swatches; S06 has a conventional distance bar).
- Fix: Demonstrate the full primitives with swatches/ranges/units, source badge, opacity slider, and a calibrated ground-distance scale distinct from the analysis-support annotation. Include their disabled/unavailable examples so the guide can serve the §19 audit purpose.
- Standard: §11 map chrome; §19 component inventory/every state.

Small copy defect: `error-rover-import-1440-dark-default.png` and light/mobile variants show “1 bytes · JSON import.” Semantic locator: import panel file-size line. Use singular “1 byte”; retain the clear cause/consequence/recovery message.

## Screen-brief assessment

| Screen | Observed assessment |
|---|---|
| S01 | Direct work view, side-by-side compact tables on desktop, stacked mobile, preset rows and one New mission primary. Empty fixtures prevent judging populated mission column completeness; the pictured headers omit body/objective/updated specified by S01. |
| S02 | Form + body-aware planar region, paired bbox fields and explicit unsaved state. Section anchors, later constraints, timestamped save states and body-change dialog are outside the inspected captured view. |
| S03 | Three-column grid verified; right-side summary/import composition and suffix/segmented anatomy need correction (findings 1, 5). |
| S04 | Fingerprint/Review/Accept/Start stepper visible. Captured S04 stays on authoring form, so requirements table, assumption rows, accepting hash and run-configuration presentation cannot be judged from these viewport captures. Edited draft visibly has changed objective and Saved indicator; this does not prove contract acceptance. |
| S05 | Explicit synthetic raster and support, honest region-only map description, histogram with unit axes, thresholds and data-table companion; point-inspect behavior and lower content unverified. |
| S06 | Prescribed 60/40 map/list proportions verified, list leads reading order, excluded section visible at 1920. Map explicitly identifies offline geometry scope. Rank header needs fix (6); sync/URL behavior unverified. |
| S07 | Dense matrix with status words/glyphs, support and final/preliminary separation. Mobile by-candidate arrangement is visible. Critic/history/review/hidden-row behavior outside supplied visible states remains unverified. |
| S08 | Persistent Preliminary caption and metric/declared/required/assessment table visible; rover-conflict capture changes maximum-slope badge to FAIL, retaining Unknown clearance. |
| S09 | Empty state designed; populated composite uses requirement/candidate/coverage table and explicit residual section. No blanket PASS or summed co-location claim. |
| S10 | Frozen benchmark and primary command visible, but grouping is wrong (4). |
| S11 | Clear three-attempt headline retains failure history; disabled further action has persistent explanation. Deep attempt diffs/receipt/playback content is below the viewport and not certified. |
| S12 | Centered 880-pixel document sheet on desktop; mode, headline, modeled scope, LIMITED assurance and explicit clearance UNKNOWN lead. Requirement table begins below. Full exports/digests/print behavior not visible and unverified. |

## X findings and acceptance limits

**No confirmed open X-01–X-29 findings within the inspected visual scope.** The defects above are principally explicit component/screen-brief nonconformances and operator clarity issues. Mid-word “Order” is a table typography defect; it is not being misreported as page overflow. Intentional, labelled horizontal table/chart scrolling is not X-26 page overflow. Viewport-bottom cropping is not automatically content clipping. Generic component demonstration labels were not treated as production placeholder claims.

X-01/02/03/04/05/10/11/13/17/18/21/22/27/29 require source/computed-style or accessible-name evidence for exhaustive clearance; X-14/15/20/25 and motion/keyboard rules require behavior evidence. Their scan- or behavior-only aspects remain unverified. This screenshot review cannot adopt the catalog's reported automated PASS as its own finding.

Re-review should retain the same neutral palette and table vocabulary, resolve findings 1–6 first, then provide captures of S04 contract review/acceptance, expanded evidence provenance, deep S11 attempts/playback and full passport/export states before claiming comprehensive screen-brief conformance.


### Verbatim accessibility reviewer report

# Independent accessibility and typography visual review — r4

**Decision: FAIL the §20 acceptance gate.** All twelve rubric scores are at least 3, but the mean is **3.33/4**, below the required 3.5. Eight concrete visual/specification defects remain. No implementation or supplied image was changed.

## Evidence and limits

Read only the supplied binding standard 41 and `out/visual/screens.md`, then inspected actual catalog images. The manifest's own PASS assertion was not treated as independent evidence. No memory, implementation, logs, handoffs, or other reviews were consulted.

Inspected S01–S12 at 1440 desktop and 390 mobile, each in dark and light default theme/density (48 images), plus native-resolution S03 at 1920 dark, S06 at 1920 light, and native-resolution reinspection of S01 light and S10 dark. Inspected evidence drawer, operations drawer, shortcut dialog, loading missions, rover import error, rover conflict, edited draft, and populated composite portfolio at 1440 and 390 in both themes (32 more images). Inspected all six complete 1440-wide component guides: dark/light × compact/default/comfortable, including their bottom sections; used sequential legible crops rather than judging a shrunken tall-page thumbnail.

This is a visual review of those supplied captures, not a live accessibility test. Semantic selectors below are **human-readable semantic targets**, not asserted DOM or CSS selectors. Keyboard execution, actual accessible names, focus return/trapping, tooltip behavior, real table semantics, screen-reader announcements, CSS font sizes, computed contrast, token purity, responsive states outside the inspected viewports, and source/license/network claims remain unverified. Visible focus on a drawer close button or chart bin proves that captured focus appearance only. Content below a viewport or inside a collapsed disclosure is not claimed absent from the product.

## Findings, ordered by severity

### 1. P2 — S03 omits the prescribed side-by-side profile summary

- Evidence: `S03-1920-dark-default.png`, `S03-1440-dark-default.png`, `S03-1440-light-default.png`.
- Semantic target: `main > region("Rover profile") > form` and the prescribed adjacent `region("Profile summary")`.
- Observable defect: the existing-revision picker, import region and field grid span the working area's full width. At 1920 the third field column occupies the right side; there is no concurrent right-hand derived summary alongside the grid. This is a failure of the explicit §10 S03 brief even though the form itself correctly uses three columns. It forces the reader to reconstruct the entered rover properties while editing.
- Fix: retain a three-column field grid in the main form area and add the specified read-only summary/import-validation region on the right at a suitable desktop width. Derive only from entered fields. Stack this region explicitly on mobile. This finding concerns the missing **right-side layout**, not whether a summary could exist below the captured viewport.

### 2. P2 — S06 screening-order header breaks a word and loses its prescribed label

- Evidence: `S06-1920-light-default.png`, `S06-1440-dark-default.png`, `S06-1440-light-default.png`, `S06-390-dark-default.png`, `S06-390-light-default.png`.
- Semantic target: `table[caption="Candidates · 6 of 6 visible"] > thead > th:first-child`.
- Observable defect: the first header reads `Orde` on one line and `r` on the next, including at 1920. It is labelled merely `Order`, whereas §10 S06 explicitly requires `Screening order`. The subtitle helps explain screening but does not repair the column's damaged label.
- Fix: label it `Screening order`; reserve a sufficient minimum width and allow a line break between the two words, never within a word. Keep the table's labelled horizontal scroller rather than squeezing the rank header.
- Proportions checked separately: the 1920 capture allocates approximately 40% to the candidate table and 60% to the map, as prescribed. Do not reverse these proportions to fix the header. The list is first in reading order and moves above the map on mobile; those choices respect its primary role.

### 3. P2 — S01's table anatomy does not match its screen brief

- Evidence: `S01-1440-light-default.png`, `S01-1440-dark-default.png` and both `S01-390-*-default.png` captures.
- Semantic target: `table[caption="Missions"] > thead` and `table[caption="Investigations"] > thead`.
- Observable defect: Missions shows `Name / Revision / Contract`, omitting the specified body, objective excerpt and updated columns. The run table shows `Created (UTC)` and has no duration column, whereas §10 S01 calls for started and duration. These are visible header differences even in the honest empty state; the table shapes are not overflowed here.
- Fix: restore the prescribed domain columns; retain revision/contract only as additional information or an expandable detail if useful. Distinguish created from started explicitly and show an honest Pending/Unknown value when a run has not started. Keep terminal state and scientific outcome separate, which the current design already does well.

### 4. P2 — Rover numeric controls do not carry their units

- Evidence: `S03-1920-dark-default.png`, `S03-1440-light-default.png`, `S03-390-dark-default.png`; also the NumberInput/FormField sections of `styleguide-dark-default.png` and `styleguide-light-default.png`.
- Semantic target: `form > field("Mass (kg)") > numeric input`, with the same issue in slope, clearance, wheel diameter, capacity, reserve and speed.
- Observable defect: units exist in the labels but the controls themselves show bare `42.0`, `18.0`, `0.20`, etc. The required persistent noneditable unit suffix inside the control (§9.3 and §10 S03) is absent. Right alignment and monospace values are otherwise good.
- Fix: render the unit suffix inside each numeric control, keep the editable number right aligned before it, and preserve a complete accessible label. Demonstrate the same anatomy in the guide.

### 5. P2 — Optional Unknown values have a single ambiguous action instead of a segmented choice

- Evidence: `S03-1920-dark-default.png`, `S03-1440-dark-default.png`, `S03-1440-light-default.png`.
- Semantic target: `field("Maximum obstacle height (m)") > button("Unknown")` and `field("Maximum route distance (m)") > button("Unknown")`.
- Observable defect: each field displays Unknown inside an input and again on one full-width button immediately below it. The screenshot provides no visible paired known/unknown choices or selected-state distinction. This does not satisfy the explicit segmented control in §10 S03 and gives a tired operator little visual indication of whether Unknown is the present value or the action that will change it.
- Fix: use a labelled two-option segmented choice such as `Value / Unknown`, visibly mark selection, and enable the numeric field only in Value mode. Keep the Unknown value explicit. Actual click behavior of the current button was not tested.

### 6. P2 — PROVE IT is detached from its Experiment panel

- Evidence: `S10-1440-dark-default.png`, `S10-1440-light-default.png`, `S10-390-dark-default.png`, `S10-390-light-default.png`.
- Semantic target: `button("PROVE IT")` within the bottom action bar, relative to `region("Accepted experiment")`.
- Observable defect: the only visible PROVE IT control is grouped with `Open operations / Open evidence` in the persistent bottom bar, outside the bordered Accepted experiment panel. The immutable-attempts heading sits between the experiment and that action. §9.4/§10 place the control in Experiment with the benchmark preview directly above it.
- Fix: place the primary control and its run/disabled explanation within the Experiment band immediately after the preview; if a sticky representation remains necessary, keep its relationship to the experiment explicit and avoid duplicate primary actions. Preserve the mobile space reserved for the bottom bar.

### 7. P3 — Saved state lacks a glyph and UTC time

- Evidence: `S04-1440-dark-default.png`, `S04-1440-light-default.png`, `S04-edited-draft-1440-dark-default.png`, both mobile edited-draft captures.
- Semantic target: `status("Saved")` at the top right of Mission authoring.
- Observable defect: the captured save indicator is only `Saved`. The §10 S02 anatomy requires a glyph and `Saved HH:MM:SSZ`. The current indicator does not tell the operator which save is being acknowledged.
- Fix: show a quiet save glyph plus the confirmed UTC time; preserve equally explicit Saving, Unsaved and Conflict states. Do not infer an actual save timestamp from these images.

### 8. P3 — Hash components display full strings instead of the specified compact identity

- Evidence: CopyHash and Hash sections of all six full `styleguide-{dark,light}-{compact,default,comfortable}.png` guides; particularly `styleguide-dark-default.png` around y=2600 and y=2900.
- Semantic target: `region("CopyHash") > code` and `region("Hash") > code` in the component guide.
- Observable defect: the CopyHash sample prints a full repeated digest and wraps it onto a second line; Hash prints the full long value. §8 requires the first 12 hex characters plus ellipsis, with full value available for inspection/copy. The full-width strings disrupt compact evidence scanning.
- Fix: use the shared compact display, retain the exact full value for accessible inspection and copying, and test the narrow and text-spacing variants. This is a concrete guide-component presentation discrepancy; I did not inspect runtime source or claim that copying is broken.

## Screen-brief assessment

| Screen/region | Observed result against §10 |
|---|---|
| S01 | Direct work entry, left title, one primary action, side-by-side desktop tables, stacked mobile and row presets are good. Header anatomy defect #3 remains. |
| S02 | Body-aware neutral region geometry, numeric bbox pairing and honest no-terrain copy are visible. The desktop two-region composition is legible. Save detail is incomplete where Saved is captured; sticky anchors and below-viewport form sections cannot be confirmed. |
| S03 | Three-column desktop field grid is present, one column on mobile. Right summary layout, suffixes and segmented Unknown affordance fail the specified brief (#1/#4/#5). Import parse failure is clear and retains values. |
| S04 | Fingerprint→Review→Accept→Start stepper is visible. The capture is at the authoring top; requirements, accept/hash adjacency and run-configuration sections below the viewport cannot be certified or declared absent. |
| S05 | Honest synthetic region/raster legend, slope histogram, threshold labels and adjacent table heading are visible. Support is explicit. Chart overflow is labelled; exact bin access, inspection popover and full table contents require live/scroll evidence. |
| S06 | Desktop 60% map / 40% table passes the proportion brief at 1920; list first and excluded section visible. Rank header defect #2 remains. No imaginary imagery or similarity score. |
| S07 | Precise matrix with status shapes, words, leading edges, value/support/stage and visible orientation controls. Horizontal overflow is explicitly labelled. Critic/history/pending-review content is not shown in the inspected viewport and cannot be certified. |
| S08 | Assessment table distinguishes rover/required/server assessment, carries Preliminary in caption and separate badge, and shows visible Pass/Fail/Unknown cases. No substitution of missing values with zero. |
| S09 | Honest initial empty state and populated per-requirement table with Gap/Unknown are provided. Co-location explanation is concise and no blanket PASS dominates. Residual section begins below table. |
| S10/S11 | Benchmark preview, chronological attempt section, explicit modeled-test headline and retained failure are visible. PROVE IT location fails #6. Playback, before/after diff and lower evidence bands are outside these captured viewports, so no claim of completeness or absence. |
| S12 | Centred document sheet, neutral mode badge, scoped claim and Limited assurance are visible. UNKNOWN clearance and synthetic limits remain conspicuous. Lower manifest/export/digest/print pagination are outside the captured viewport. |
| Drawers/dialog | Opaque consistent surfaces, visible focused close controls, nondecorative content. Shortcut help lists exactly the requested keys and typing caveat. Evidence source disclosure is collapsed; focus return, modal trap and deeper provenance cannot be inferred. |
| Full guides | Both themes and all three densities visually coherent throughout, with chart/table pairings, visible state shapes, disabled reason and an error panel. Hash discrepancy #8 remains. The static guides show launch controls for Dialog/Drawer/Tooltip/Popover rather than their open variants; catalog overlays cover some, not every interactive state. |

## §20 rubric (0–4)

| Criterion | Score | Visual basis |
|---|---:|---|
| Hierarchy | 3 | Evidence/status distinct and mission/test outcome separated; S03 summary absent from prescribed position and Experiment action detached. |
| Restraint | 4 | Quiet neutral chrome, restrained semantic colour, no decorative space/marketing treatment. |
| Typography | 3 | Legible stable sans/mono distinction and numeric alignment; broken S06 header and verbose hashes disrupt scanning. |
| Density / spacing | 3 | Consistent grid and stable regions; broad S03 input rows and missing side summary waste the desktop width. |
| Tables | 3 | Clear borders, alignment, state glyphs and support; S01 column anatomy and S06 rank header remain wrong. |
| States | 3 | Honest empty, loading, error and disabled states visible; save-state detail and Unknown affordance need work. |
| Copy | 4 | Plain scope/limitations, no hype; synthetic versus actual measurements and modeled tests are explicit. |
| Consistency | 4 | Shell, table, badges, buttons and overlays remain visually consistent across routes/themes/densities. |
| Map / chart integrity | 3 | Neutral geometry, labelled support, units, thresholds and chart/table pairings. Complete map inspection and chart-bin accessibility remain outside static evidence. |
| Accessibility feel | 3 | Visible focus examples, contrast appears strong, words plus glyphs and labelled scrollers; no live keyboard/AA certification and Unknown selection affordance is weak. |
| Crew credibility | 3 | Honest uncertainty and retained failures support trust; missing comparison anatomy and save time reduce hour-five confidence. |
| Absence of X-01–X-29 | 4 | No confirmed open X item in the inspected visual scope; this is not source-scan or behavior certification. |
| **Total / mean** | **40 / 48; 3.33** | **FAIL: mean < 3.5, although every score ≥ 3.** |

## X-item disposition

**No confirmed open X-01–X-29 findings within the inspected visual scope.** The concrete findings above are direct screen/component brief failures, not inflated claims of an X violation. In particular, S06's wrapped header is a readability defect; I did not relabel it as proven clipped content. Labelled table/chart overflow is intentional and was not counted as page overflow. The help dialog is an explicitly required §13 exception to the general preference for drawers.

No emoji, decorative gradient/glass/glow, large pills, marketing hero, starfield, feature cards, fake similarity gauge, NASA insignia, hype or mixed visual language was observed. Static pixels cannot verify X-10 computed tabular numerals, X-13 underlying select implementation, X-17 accessible naming/tooltips, X-21 computed grid purity, X-22 font delivery, X-25 layout shifts, X-29 literals or every behavioral/scan condition. Those remain unverified rather than passed. No implementation or image changes were made by this review.


### Verbatim slop reviewer report

# AnalogForge independent hostile visual review — round 4

## Decision

**FAIL the §20 acceptance threshold.** Scores total **40/48**, mean **3.33/4**; every criterion is at least 3, but the required mean is 3.5. This is a restrained engineering interface, with several concrete departures from the binding screen briefs and component contract. It is not a marketing-template or decorative-space interface.

**No open X-01–X-29 findings are established within the inspected visual scope.** The findings below are binding standard violations outside the X list, or specific proof gaps. This is not a source-scan or behavioral clearance of the X list.

## Scope and method

Read only the supplied standard 41 and `out/visual/screens.md`, and opened their actual images. No source, memory, logs, handoffs, or other reviews were read. The catalog's own PASS statement was not treated as evidence of conformance.

Inspected all S01–S12 at 1440×900 and 390×844 in both themes; desktop evidence/operations/shortcut overlays in both themes and their mobile light versions; loading and rover-import error states in desktop dark/light and mobile light; desktop dark S08 rover conflict, S09 composite, and S04 edited draft. Inspected **all six full component guides** (dark/light × compact/default/comfortable), split into sequential 900 px crops at original 1440 px width, through their footer. Crops were temporary review aids; original screenshots and implementation were unchanged.

Selectors below are **semantic locators**, not claims about source CSS/test IDs. The screenshots cannot prove DOM semantics, font configuration, exact contrast, measured pixel grid, keyboard functionality, tooltip availability, animation, network activity, or content below a captured viewport. Ordinary viewport cutoffs and explicitly labelled table scrollers are not automatically clipping defects.

## Concrete findings, ordered by severity

### 1. P2 — S03 satisfies the three-column grid, but loses the prescribed right-side summary/import composition

- Evidence: `S03-1440-dark-default.png`, `S03-1440-light-default.png`.
- Semantic locator: `main > section[heading="Rover profile"]`; form group `Import rover JSON`.
- Visible: selector and import zone span essentially the entire working area above a full-width three-column field grid. There is no right-side read-only summary alongside that grid. This is visibly different from §10 S03, which requires the grid **and** a right-side summary/import panel. A possible summary below the screenshot would not satisfy the right-side composition.
- Fix: retain the existing three-column field grid within the main form area and reserve a right-hand column for the derived entered-field summary and import validation table. Stack at the mobile breakpoint. Do not invent derived values.

### 2. P2 — Home tables omit the operational fields prescribed by S01

- Evidence: `S01-1440-dark-default.png`, `S01-1440-light-default.png` (also mobile versions).
- Semantic locator: `table[caption="Missions"] thead`; `table[caption="Investigations"] thead`.
- Visible: Missions headers are `Name / Revision / Contract`, without body, objective excerpt or updated time. Investigations shows `Run / Mode / Terminal state / Scientific outcome / Created (UTC)` without duration. The empty state does not justify dropping the eventual table schema. Separate terminal/outcome columns are correctly present.
- Fix: implement the §10 S01 columns; preserve the separate terminal and scientific outcomes. Put revision/hash details into secondary text or a detail view if needed to keep the table compact.

### 3. P2 — Candidate screening-order header is shortened and broken inside the word

- Evidence: `S06-1440-dark-default.png`, `S06-1440-light-default.png`, `S06-390-dark-default.png`, `S06-390-light-default.png`.
- Semantic locator: `table[caption="Candidates · 6 of 6 visible"] th:first-child`.
- Visible: the first heading renders `Orde` then `r`; it also uses `Order` instead of the explicitly prescribed `Screening order`. This looks like a squeezed generic table column and impairs first-glance reading. It is a §9.5 mid-word-wrap and §10 S06 label defect, rather than proven X-26 clipping.
- Fix: label it `Screening order`, give the header a deliberate min-width, and wrap between words only. Preserve right-aligned numeric ranks.
- Proportion check: **the desktop map/list proportions are correct**: map approximately 60%, table approximately 40%. Table-first placement gives the list priority. No finding is raised against these proportions.

### 4. P2 — Required unit suffixes are absent inside rover number controls

- Evidence: `S03-1440-dark-default.png`, `S03-1440-light-default.png`; all six `styleguide-{theme}-{density}.png` guides, NumberInput/FormField specimens.
- Semantic locator: `input[label="Mass (kg)"]`, `input[label="Maximum slope (deg)"]`, `input[label="Battery capacity (Wh)"]`; guide `section[heading="NumberInput"]`.
- Visible: units appear in field labels, but the controls themselves contain only `42.0`, `18.0`, `1800.0`, etc. §9.3 and the specific S03 brief require non-editable unit suffixes inside numeric controls. The guide's bare `20` reproduces the omission.
- Fix: use a shared suffix slot for kg/deg/m/Wh/%/m/s inside NumberInput. Keep the numeric value right-aligned before the suffix with a reserved width.

### 5. P2 — Full component guides do not visually demonstrate the complete status contract

- Evidence: all six `styleguide-{theme}-{density}.png` full guides, `StatusBadge` and `StatusGlyph` sections near their top.
- Semantic locator: `section[heading="StatusBadge"]`; `section[heading="StatusGlyph"]`.
- Visible: both sections show six qualification states only. The full guides contain no corresponding visible specimens for **Inconclusive**, **Blocked**, **Allowed**, and **Limited**. Limited does appear in S12, but that does not make the §19 all-component/all-state guide complete. Buttons likewise show primary, secondary and disabled examples without visible danger/loading specimens.
- Fix: expand the guide's status matrix to include the four additional states and silhouettes, and show the required button variants and busy state explicitly. Capture focus/hover/active examples as separate labelled specimens or state screenshots. This finding concerns the supplied visual deliverable; it does not assert those implementations are absent.

### 6. P3 — Hash specimens ignore the prescribed compact hash presentation

- Evidence: all six full `styleguide-{theme}-{density}.png` guides, CopyHash and Hash sections in their middle.
- Semantic locator: `section[heading="CopyHash"]`; `section[heading="Hash"]`.
- Visible: long complete hex strings fill the Hash line, and CopyHash wraps its long string onto a second line. §8 specifies the first 12 hex characters plus an ellipsis, with full value available via title/copy. This is avoidable visual noise in a component intended for repeated dense use.
- Fix: render a stable 12-character prefix plus `…`, retain the full value for copying/accessible inspection, and keep the copy button adjacent. Do not silently truncate the underlying copied value.

### 7. P3 — Coordinate component specimen is unlabeled and underprecise

- Evidence: all six full `styleguide-{theme}-{density}.png` guides, CoordinateReadout near their bottom.
- Semantic locator: `section[heading="CoordinateReadout"]`.
- Visible: `137.5000, −4.5000 · MARS` provides four decimals with no degree signs, axis labels or specific body-fixed frame. §8 requires five decimals with degree/axis notation and a named body-fixed frame. The authoring screens do name planetocentric frame and use five decimals; the reusable specimen should meet the same standard.
- Fix: show e.g. `137.50000° E, 4.50000° S · Mars planetocentric`, explicitly identifying longitude/latitude order. Use one consistent sign/hemisphere convention.

### 8. P3 — Save state is too generic for the specified authoring contract

- Evidence: `S04-1440-dark-default.png`, `S04-1440-light-default.png`; `S02-1440-dark-default.png`, `S02-1440-light-default.png`.
- Semantic locator: authoring header `save-indicator` semantic region (top right).
- Visible: `Saved` or `Unsaved changes` appears as plain text. The saved state lacks the required glyph and absolute UTC save time (`Saved 14:02:11Z`) from §10 S02. On a long editing session this makes saved evidence less exact than the rest of the instrument.
- Fix: shared glyph + timestamp indicator for saved, saving, unsaved and conflict states. Preserve a stable reserved width.

## Screen-brief checks

| Screen | Visual conclusion |
|---|---|
| S01 | Direct work entry, two desktop tables and preset rows; required schema omissions in finding 2. No hero/card marketing grid. |
| S02 | Desktop two-column form/planetary region is present; mobile stacks. Numeric bbox is shown with geometry-only qualification. Save precision issue in finding 8. Sticky anchors/confirmation behavior unverified. |
| S03 | Three-column field grid is visibly present on desktop. Right-side composition and in-control units fail findings 1/4. Optional fields visibly display Unknown and an Unknown action; actual segmented-control behavior unverified. |
| S04 | Pipeline is present, but the captured top remains the authoring form. Requirements/acceptance/hash content below viewport cannot be judged absent from this capture. Edited draft visibly changes objective. |
| S05 | Neutral raster legend, honest synthetic/source support, chart threshold labels, axes and adjacent table heading are present. Internal horizontal chart scroll is disclosed. Exact raster fidelity and keyboard chart access unverified. |
| S06 | Map 60% / list 40% desktop split conforms; list precedes map. Offline extents are clearly labelled, no fake basemap. Finding 3 concerns table label/readability. Selection/URL sync unverified. |
| S07 | Engineering matrix dominates; values, support, state words/glyphs and edges are visible. Horizontal overflow is explicitly labelled. Critic/history/pending-review states are not established by these captured viewports. |
| S08 | Table and persistent Preliminary caption are present. Conflict capture clearly changes slope assessment to Fail; scale unsupported remains Unknown. |
| S09 | Empty state is designed; composite variant shows coverage table with Unknown/Gap and a residual-conditions region. No single misleading big Pass. |
| S10 | Benchmark preview and fixed PROVE IT action are visible; footer keeps action accessible. The action is outside the bordered experiment panel rather than inside as §9.4 prescribes, a minor additional placement deviation. |
| S11 | Explicit three-attempt history headline and retained failed attempt are visible. Later playback/evidence below viewport cannot be declared missing. |
| S12 | Centered 880 px desktop sheet, Synthetic mode and Limited assurance with explicit physical-clearance limitation. Lower document/export content and print behavior unverified. |
| Overlays/states | Opaque restrained drawers, readable shortcut dialog, visible close-button focus rings. Error states name cause/remediation; loading has scoped text. Drawer focus return/trap, loading resolution, live regions, and tooltips cannot be tested from pixels. |

## §20 rubric scores

| Criterion | Score | Evidence and rationale |
|---|---:|---|
| Hierarchy | 3 | Run status distinct and pinned, but S03 has no side summary and authoring spends large first-view space on generic form chrome. |
| Restraint | 4 | Flat neutral surfaces, limited semantic state color, no decorative hero/space effect throughout inspected screens. |
| Typography | 3 | Consistent sans/mono appearance; mid-word Order header, missing input suffixes and full hash strings reduce precision. |
| Density/spacing | 3 | Orderly tables and panels, but S03 full-width import stack and tall authoring first view are weaker than prescribed composition. |
| Tables | 3 | Qualification matrix and compatibility table scan well; home schema and S06 heading remain defective. |
| States | 3 | Real empty/error/loading/disabled presentations; full guide omits required status/variant specimens. |
| Copy | 4 | Plain, cautious modeled/synthetic claims, no hype; failure/remediation wording is specific. |
| Consistency | 4 | Shared shell, neutral controls, state silhouettes, table frames and drawer vocabulary across screens/themes. |
| Map/chart integrity | 3 | Honest synthetic/offline labelling, axes/thresholds and data tables. Coordinate specimen fails the exact format; runtime geometry unverified. |
| Accessibility feel | 3 | Legible contrast by appearance, labelled scrollers and visible overlay focus rings. Keyboard and exact WCAG metrics remain unverified. |
| Crew credibility | 3 | Limits, revisions and failed attempts are candid, but required home fields, precise save indicator and summary composition need completion. |
| Absence of X-01–X-29 | 4 | No confirmed visual X violations; source/behavior-only items are expressly unverified below. |
| **Total / mean** | **40 / 3.33** | **FAIL mean ≥3.5; all individual scores ≥3.** |

## Individual X-01–X-29 assessment

`Clear visually` means no instance observed in inspected images; it is bounded by the screenshots, not a code audit.

| Item | Assessment |
|---|---|
| X-01 emoji | Clear visually; no emoji observed. Alt text/fixtures unverified. |
| X-02 gradients | Clear visually; flat fills. CSS unverified. |
| X-03 glass | Clear visually; drawers opaque; modal scrim is not blurred glass. |
| X-04 glow/neon | Clear visually; focus rings are ordinary functional outlines. |
| X-05 large radii/pills | Clear visually; small square/rectangular primitives. Exact computed radii unverified. |
| X-06 heroes/marketing | Clear visually; direct tables/forms. |
| X-07 decorative space | Clear visually; planets only named as data frames. |
| X-08 feature grids | Clear visually; component guide grid is a specimen inventory, not marketing features. |
| X-09 placeholders | Clear for application screens. Explicit demonstration titles such as Example histogram in the development guide are specimen descriptions, not fabricated operational data; do not count these as production placeholder findings. |
| X-10 proportional numerals | Numeric presentation appears mono/aligned. Actual tabular-numeral computation unverified. |
| X-11 tiny/low-contrast text | No confirmed instance by appearance at original resolution; computed sizes, line heights and contrast unverified. |
| X-12 shouty paragraphs | Clear visually; uppercase scientific identifiers/status labels are not paragraphs. |
| X-13 browser defaults | Clear visually; controls and focus appear deliberately styled. Native implementation/scrollbars unverified. |
| X-14 scopeless spinners | Clear visually; supplied loading states use scoped retrieval wording/skeletons. Resolution and >2s elapsed-time behavior unverified. |
| X-15 important-result toast | Clear visually; guide toast is noncritical view-preference confirmation. Results shown persistently in lab/passport. Runtime toast inventory unverified. |
| X-16 wrong/nested modals | Clear visually; evidence/operations are drawers. Shortcut dialog is explicitly required by §13, so not an X-16 violation. |
| X-17 unlabeled icons | No established finding: most icons have visible text; icon-only controls require aria-label/tooltips that screenshots cannot establish. |
| X-18 mixed icons | Clear visually; consistent thin line glyphs and explicit custom status silhouettes. Library/stroke computation unverified. |
| X-19 fake similarity viz | Clear visually; histogram and matrix have scientific labels; screening order expressly disclaims similarity. |
| X-20 3D/parallax/carousel | No visible instance; motion behavior unverified. |
| X-21 off-grid spacing | No conspicuous visual irregularity; exact computed grid unverified. |
| X-22 excess/display typefaces | Clear visually; sans/mono only by appearance. Font identity/CDN loading unverified. |
| X-23 NASA skin/insignia | Clear visually; no insignia or approval claim. Explicit no-endorsement footer appears in full guide. |
| X-24 hype | Clear visually; restrained engineering copy. |
| X-25 layout shifts | Unverified: static screenshots cannot measure CLS or live sorting. |
| X-26 overflow/clipping | No confirmed open instance. Table/chart horizontal scrolling is labelled; viewport bottoms are not proof of inaccessible content. S06 broken Order word is a §9.5 defect, not proven clipping. |
| X-27 black/white dark skin | Clear visually; dark surfaces are blue-grey and text is off-white by appearance. Exact token colors unverified. |
| X-28 different visual languages | Clear visually; shell/components coherent across all twelve screens and themes. |
| X-29 color literals | Unverified source-only rule; cannot clear from screenshots. |

## Verification boundary

This review establishes the visible defects and inspected-scope conclusions above. It does **not** establish functional compliance, production build purity, precise metrics, hidden content, or a successful live workflow. No implementation or supplied image was edited.


## Round4 disposition

Not accepted: all criteria reach3, but means remain below3.5. Source b96462a functional gates passed30 browser,84 frontend,131 Python tests and all36 mutations. Corrections target the concrete missing screen/component anatomy: side-by-side rover summary/import, unit suffixes and explicit known/unknown input state without invented values, complete home schema, readable screening-order heading, route-synchronized mobile tabs, experiment-local PROVE IT, explicit receipt claim/requirement structure, actor-unknown operation metadata, precise save acknowledgement, and complete component specimens. No scientific result or frozen contract is changed.

## Round5 — source6ad0e65

The complete32-test browser gate and402 visual reports passed with404 captured images,0findings,0skips and0flaky results. All84 frontend tests,131 Python tests and36 mutants also passed. Three fresh reviewers received only architecture41, the final catalog/images (including all12 native component-guide parts) and the exact12-criterion rubric. They inspected both themes, desktop/mobile, all screens, overlays/states and full guides; they were not given prior scores or reviews.

### Verbatim hmi report

# AnalogForge independent mission-operations HMI review R5

Decision: **REJECT against §20 acceptance**. Scores total **39/48**, mean **3.25/4**. Consistency scores 2; the required all-at-least-3 and mean-at-least-3.5 gates both fail. The interface is restrained and broadly credible, but contradictory mobile navigation and scientific display inconsistencies need correction.

## Independence and scope

Read only the binding `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`, `out/visual/screens.md`, and catalogued images. No memory, source implementation, logs, handoffs, other reviews, or external reference material was consulted. The catalog's reported test/audit results were not treated as independent evidence.

Opened actual S01–S12 images at 1440×900 and 390×844, dark and light, default density. Opened evidence drawer, operations drawer and shortcut dialog at those sizes in both themes; loading missions, rover import error, rover conflict, edited draft and composite portfolio variants in both themes and sizes. Opened all twelve full component-guide files: dark/light × compact/default/comfortable × parts 1/2. For legibility, each supplied native-width guide part was temporarily cropped into two overlapping 1440px-wide inspection images in `/tmp/hmi-r5`; every supplied part was inspected through its bottom, including charts, map controls and footer. Supplied images were not changed.

This is a screenshot-based visual judgment, not a runtime or accessibility conformance certification. Semantic selectors below identify the visible element by role/name/context; they are proposed locators, not claims about source attributes.

## Rubric

| §20 criterion | Score | Evidence and reason |
|---|---:|---|
| Hierarchy | 3 | S07-1440-dark-default.png prioritizes verdict shapes and values; S11 separates lifecycle, latest result and attempt failures. Mobile shell occupies substantial height before the working object. |
| Restraint | 4 | S01/S07/S12 in both themes use neutral surfaces, limited accent, no decorative imagery, and semantic status color. |
| Typography | 4 | S03-1440-light-default.png has readable input labels, aligned mono values, adjacent units and a derived summary. Full guides show coherent heading/body/caption hierarchy. |
| Density and spacing | 3 | S06 desktop gives primary list left and larger map right; mobile S08 spends most initial viewport on chrome/explanatory text before assessments. Disabled PROVE IT changes desktop height. |
| Tables | 3 | S07 matrix is precise, explicit and readable, with labeled horizontal overflow. S12 uses opaque abbreviated candidate identifiers rather than the readable names used elsewhere. |
| States | 3 | Empty, loading and terminal disabled states are designed; S11 explains disabled action. Error-import captures do not expose the actual error panel in the captured viewport, so its detailed treatment cannot be approved. |
| Copy | 4 | S08 explicitly distinguishes declared capability from physical observation; S12 clearly limits physical-clearance claims and labels synthetic scope. |
| Consistency | 2 | S05/S08/S09/S11 light-mobile central navigation says Passport while the content and adjacent View label identify another screen; guide scientific swatch order differs from target view. |
| Map/chart integrity | 3 | S05 shows support, units, baseline zero, thresholds and an adjacent data table. S06 honestly identifies geometry-only offline extent view. Scientific legend consistency and area-fraction formatting require fixes. |
| Accessibility feel | 3 | Drawer/dialog close controls show clear focus rings; mobile controls are generous, status includes shape and word. Contradictory current-view indicators harm orientation. Keyboard operation/ARIA remain unverified. |
| Crew credibility | 3 | Explicit modeled/synthetic/unknown limitations and immutable attempt language are credible. An operator should not have to resolve contradictory navigation or mentally map short identifiers back to named candidates. |
| Absence of X-01–X-29 | 4 | No confirmed open X finding within the inspected static visual scope; source-only and behavioral rules remain unverified. |

## Concrete defects, ordered by severity

### 1. P1 — mobile current-view indicator contradicts the actual screen

**Files:** `S05-390-light-default.png`, `S08-390-light-default.png`, `S09-390-light-default.png`, `S11-390-light-default.png`; also `S08-rover-conflict-390-light-default.png` and `S09-composite-390-light-default.png`.

**Semantic selector:** run navigation, central current-tab control between “Previous run tab” and “Next run tab”; compare the nearby `View: Target/Compatibility/Portfolio/Test lab` text and page heading.

The central control reads **Passport** on all these images while the explicit View label and rendered content identify a different view. Dark counterparts show the expected current view. This is a directly visible contradiction, regardless of whether it originates in UI state or capture timing. In a mission console this erodes position awareness. **Fix:** derive the central label/selected treatment from the same active-route state as the View label/content; retake both-theme mobile images after route state settles. Screenshots do not establish the underlying cause or whether clicking it changes route.

### 2. P2 — scientific legend's value-to-shade mapping is inconsistent

**Files:** `S05-1440-dark-default.png` versus `styleguide-dark-default-part-2.png`, `styleguide-dark-compact-part-2.png`, `styleguide-dark-comfortable-part-2.png`; compare the corresponding light guide parts.

**Semantic selector:** target slope legend; full-guide `LayerPanel` and `Legend` swatches labeled `0.0–5.0 deg` and `5.0–12.0 deg`.

The dark target maps the lowest slope band to the darkest swatch and the next band to a lighter swatch. In the dark full guides the lowest band is light and the next dark; light guides reverse those two again. This makes the same labeled scientific scale change its visual ordering between documented components/themes. **Fix:** use one scientific ramp mapping for the same numeric bins across themes and components, with contrasting outlines if needed; render the full layer legend from that mapping. This is a visible consistency defect, not a claim that analysis data are wrong.

### 3. P2 — area coverage is presented as a generic fraction rather than required percentage

**Files:** `S05-390-dark-default.png`, `S05-390-light-default.png`; corroborating slope-band-area metric in `evidence-drawer-1440-dark-default.png` and light counterpart.

**Semantic selector:** `table[caption="Target measurements"]`, row `Area within 12-18 deg slope band`, Value/unit cell; evidence receipt metrics row `Slope-band area fraction`.

The target row displays `0.2 fraction`. §8 explicitly specifies coverage fractions of area as percentages; the visible row is exactly that quantity. **Fix:** display `20 %` for area coverage (and `40 %` for the corresponding receipt's 0.4), with consistent precision and support/validity beside it. Preserve raw fractions in machine data if required. The screenshot proves the formatting mismatch, not a numerical calculation error.

### 4. P2 — passport loses human-readable candidate identity

**Files:** `S12-1440-dark-default.png`, `S12-1440-light-default.png`; compare `S07-1440-dark-default.png` / `S09-composite-1440-dark-default.png`.

**Semantic selector:** passport `Requirement evidence summary` table, `Status / candidate` cells for `R-SLOPE-AVAILABILITY`.

The passport lists `a93ebf16`, `9fc0745a`, `b401970c`, etc. beside badges, while qualification and portfolio use `Practice grid-r0c1` and related names. No visible mapping accompanies the identifiers in the shown passport table. An operator cannot immediately identify which named candidate passed or failed. **Fix:** show candidate display name plus its short immutable id, or provide a compact adjacent name/id key. This is a local readability/traceability defect; screenshots do not prove that expansion or links are absent elsewhere.

### 5. P3 — disabled desktop PROVE IT collapses its specified control height

**Files:** `S10-1440-dark-default.png` compared with `S11-1440-dark-default.png`, likewise light.

**Semantic selector:** Experiment panel `button[name="PROVE IT"]`.

The initial control is approximately 48px tall; the terminal disabled control is approximately 32px tall. §9.4 gives this exceptional control a 48px height, and §9.1 requires no layout shift across button states. The reason text is good, but the affordance changes geometry across the two views. **Fix:** retain the 48px PROVE IT block in disabled state and keep the persistent terminal explanation. These screenshots demonstrate a static size inconsistency, not measured CLS on one transition.

### 6. P3 — chart bar gaps exceed the prescribed one-pixel treatment

**Files:** all `styleguide-{dark,light}-{compact,default,comfortable}-part-2.png` files, Histogram and Bar examples.

**Semantic selector:** `Chart(Histogram|Line|Bar)` section, histogram/bar SVG adjacent rectangles.

At native-width inspection, bars have roughly 8px gaps rather than the 1px gap mandated by §10.5. The full guide therefore documents a chart treatment different from the binding design contract. **Fix:** use square bars separated by 1px, preserving their numeric heights and table values. This is a low-severity visual-contract discrepancy, not evidence of fabricated data.

## Specific §10 briefs

- **S01:** opens directly into work; left title, one New mission primary, side-by-side desktop tables, presets as rows. Terminal state and scientific outcome have distinct columns. Mobile stacking is sensible.
- **S02:** desktop has approximately 480px authoring form and body-aware planetary geometry panel with matching bbox values. The panel explicitly disclaims measurement imagery. Sticky section-anchor behavior cannot be established from these captures.
- **S03:** **complies with the prescribed three-column field grid and right-side summary/import placement** at desktop. Values have unit suffixes; explicit Known/Unknown controls are visible for optional fields. Mobile correctly becomes single-column. Import validation result table lies below captured viewport; not verified.
- **S04:** stepper and saved state are visible, but ordinary captures begin at authoring form. Requirements review table, acceptance hash adjacency and run-configuration details are outside the captured viewport; no invented finding of their absence.
- **S05:** support-aware target representation, histogram and adjacent table appear on desktop; mobile measurements move ahead of map. See area-formatting finding.
- **S06:** **complies with prescribed approximately 60% map / 40% list desktop split**: list on left, map on right. List appears before map and screening order is explicitly not similarity. Intentional horizontal table overflow is labeled; partially visible right columns are not counted as clipped-content X-26 defects. Selection/URL sync cannot be verified.
- **S07:** engineering matrix dominates the work area; state glyph + word + value + support/stage; orientation controls and optional-row count visible. Critic/history/review behavior not verified.
- **S08:** declared/required/assessment structure and persistent Preliminary treatment visible, including conflict Fail state. Mobile nav contradiction remains open.
- **S09:** empty state and populated requirement-to-site coverage table inspected; gaps remain explicit rather than aggregate PASS.
- **S10/S11:** benchmark preview precedes action; terminal attempt history preserves failed results and explicit modeled scope. Route playback and full later attempt content are below capture, unverified. Disabled size finding remains open.
- **S12:** centered approximately 880px document sheet, mode, assurance, limitation and requirements present. Candidate naming finding remains open. Print, digests and export outcomes cannot be judged from initial viewport.
- **Overlays:** evidence drawer has structured claim/support/provenance/limitations; desktop 352px side placement, mobile bottom treatment. Operations timeline uses persistent rows and explicit event details. Shortcut dialog lists the seven prescribed commands and typing exclusion, with legible focus indicator in both themes.

## X findings and unverified scope

**No confirmed open X-01–X-29 finding within the inspected static visual scope.** The six findings above are concrete §8/§9/§10/consistency issues; they are not artificially relabeled as unrelated banned items. In particular, labeled intentional table overflow is not X-26, and the developer-only guide's explicit component demonstrations are not product placeholder data.

Screenshots cannot independently verify X-10 computed numeral properties, X-11 exact WCAG contrast/computed text sizes, X-13 actual native-control implementation, X-17 accessible names/tooltips, X-21 exact computed spacing, X-22 font loading/CDNs, X-25 layout shift/stable ordering, X-29 color literals, keyboard traversal, focus return/trapping, screen-reader semantics, reduced motion, animation, backend truth, persistence, export readiness, or PDF pagination. No claimed pass for those checks follows from this review. Rover-import error captures show the upload filename near the desktop fold and ordinary top-of-form on mobile; they do not expose the error itself. Capture that state scrolled to the actual validation/error result for a complete visual acceptance packet.

Retain the restrained shell, distinct status silhouettes, visible uncertainty and modeled/synthetic disclosures. Re-review corrected screenshots for the six findings before accepting the HMI visual gate.


### Verbatim accessibility report

# AnalogForge independent accessibility and typography review — R5

Decision: **FAIL the §20 visual acceptance gate.** Scores total **37/48**, mean **3.083/4**. Accessibility feel and absence of X findings score below 3; the mean is below 3.5.

This is a screenshot-only review against `41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md`. Only that standard, `out/visual/screens.md`, and catalogued images were read. No memory, source, logs, handoffs, or other reviews informed this report. Catalog provenance assertions were not treated as independently verified checks.

## Inspected evidence

- S01–S12: each `Snn-1440-dark-default.png`, `Snn-1440-light-default.png`, `Snn-390-dark-default.png`, and `Snn-390-light-default.png` (48 images).
- Evidence drawer, operations drawer, shortcut dialog, loading missions, and rover-import error: each at 1440 and 390, dark and light (20 images).
- S08-rover-conflict, S04-edited-draft, and S09-composite: each at 1440 and 390, dark and light (12 images).
- S04, S07, and S12 text-spacing captures: each at 1440 and 390, dark and light (12 images).
- All twelve full-guide files under `apps/web/docs/design-review/`: `styleguide-{dark,light}-{compact,default,comfortable}-part-{1,2}.png`. Both contiguous parts of every theme/density were inspected from top to bottom. Native-width crops at y=0–1400 and y=1352–end were made in `/tmp/af-accessibility-r5/` to avoid tool downscaling; these retain a further 48 px overlap. The delivered images were unchanged. The original parts already have the catalogued 48 px overlap.

The viewport crops do not show the entire scrolled length of every route. In particular, the rover-import error itself is below the visible area in the supplied error captures, S04's detailed requirements/freeze controls are below the first viewport, and later S11 attempt/evidence/playback sections and S12 exports are below the first viewport. Their absence from these screenshots is an evidence limitation, not proof they are absent from the app.

## Concrete defects, ordered by severity

Selectors below are semantic locators identifying the pictured element, not assertions about implementation CSS or DOM inspected in source.

### A11Y-01 — P1: mobile navigator contradicts the displayed route

**Evidence:** `S05-390-light-default.png`, `S08-390-light-default.png`, `S09-390-light-default.png`, `S09-composite-390-light-default.png`, `S11-390-light-default.png`, `S08-rover-conflict-390-light-default.png`.

**Semantic selector:** run navigation, central current-view control between the previous/next arrow buttons; e.g. `nav >> [current-view control]`.

The left label says Target, Compatibility, Portfolio, or Test lab and the page content agrees with that left label, but the central control says **Passport**. In the dark counterparts the central label matches the route. In the affected light screenshots it also loses the active underline shown on the correct dark version. A tired operator has two conflicting location indicators immediately above the work.

**Fix:** derive both visible current-view labels and selected appearance from the same active route; when a control is displaying a prospective destination, label it explicitly as a destination rather than presenting it as the current view. Recapture these exact states. This finding concerns visible contradictory text; it does not claim that a click actually routes incorrectly.

### A11Y-02 — P1: text-spacing causes measured values/units to cross matrix cell boundaries

**Evidence:** `S07-1440-dark-default-spacing.png`, `S07-1440-light-default-spacing.png`; compare `S07-1440-dark-default.png` and its light counterpart.

**Semantic selector:** `table[caption="Requirement qualification · by requirement"] >> row[R-SLOPE-AVAILABILITY] >> candidate value/unit line`.

At the first three candidate columns, the expanded `0.4 fraction`, `0.11 fraction`, and `0.08 fraction` lines reach or cross the vertical cell boundaries. In the second column, `fraction` visibly enters the next column's green edge/status area. These are measurements, so adjacent-column contamination is more serious than clipped descriptive prose. The ordinary-density unmodified capture does not show this collision.

**Fix:** let the matrix's minimum column width grow with text-spacing and retain an intentional labelled horizontal scroller; alternatively move the value/unit line below the badge with enough intrinsic width. Keep value and unit together and ensure all internal content remains inside the owning cell. Verify all candidate columns under the actual spacing override.

**Open X mapping:** X-26 (overlapping text); §15 / VIS-17 text-spacing resilience.

### A11Y-03 — P2: expanded Run context label extends outside its control

**Evidence:** `S07-390-dark-default-spacing.png`, `S07-390-light-default-spacing.png`, `S12-390-dark-default-spacing.png`, `S12-390-light-default-spacing.png`.

**Semantic selector:** `run-state-banner >> button/disclosure[Run context]`.

`Run context` wraps into two lines, with the end of `context` extending beyond the right border of the disclosure control. This sits beside Cancel run on active-run captures and is part of the core status region. The resulting boundary ambiguity weakens both legibility and hit-target understanding.

**Fix:** allow the context control to take the available row width or place its text on a separate full-width row; use intrinsic sizing and wrapping instead of a constrained inline label. Preserve clear separation from the adjacent action.

**Open X mapping:** X-26; §15 / VIS-17.

### A11Y-04 — P2: candidate extent outlines do not use the prescribed interactive accent

**Evidence:** `S06-1440-dark-default.png`, `S06-1440-light-default.png`.

**Semantic selector:** `map[Earth analog candidates] >> candidate extents C1–C6`.

All six visible candidate rectangles use neutral grey outlines. §11 prescribes 2 px accent outlines for candidate extents and stronger selected treatment. The numbered C1–C6 labels are useful, but the grey outlines read similarly to background geometry rather than list-linked selectable objects.

**Fix:** use the single interactive accent for candidate extent outlines; retain numbered labels and give the selected extent the specified 3 px edge plus corner ticks. Do not add arbitrary series colours. No selected state is asserted missing here because none is pictured.

### A11Y-05 — P3: target coordinate readout exceeds the specified precision

**Evidence:** `S05-1440-dark-default.png`, `S05-1440-light-default.png`.

**Semantic selector:** `section[Mars target region] >> coordinate readout >> West longitude`.

The visible readout says `West 137.000000° E` (six decimal places). The same authoring panel in `S02-1440-dark-default.png` uses `137.00000° E` (five). §8 specifies five decimals. The inconsistent precision adds digits without improving the presented scientific support and interrupts scanning between authoring and evidence views.

**Fix:** use the shared five-decimal coordinate formatter in both readouts, preserving the planetary frame and axis labels.

These five findings are visible defects. No extra findings have been invented from unseen content, source assumptions, or absent interaction recordings.

## Screen-specific §10 checks

| Screen | Visible assessment |
|---|---|
| S01 | Opens directly into two side-by-side desktop tables, stacked on mobile. Terminal state and scientific outcome are separate headers. Presets are rows. Empty states explain their cause. No hero or illustration. |
| S02 | 480 px-class left form and body-aware right panel; bbox and readout are visible. Unsaved indicator has glyph plus words. Section anchors and below-fold constraints cannot be established from these crops. |
| S03 | **Three-column field grid plus right-hand read-only entered-profile summary and import panel are present at 1440. This satisfies the specific S03 layout brief.** Units are adjacent to right-aligned monospace values, and optional unknown fields have explicit Known/Unknown controls. Mobile stacks fields clearly. Import validation results below the fold are not independently visible. |
| S04 | Stepper and saved state are visible. The initial viewport remains dominated by the authoring form and target panel; the detailed requirements/acceptance/hash presentation is outside the pictured area and receives no unsupported pass/fail assertion. |
| S05 | Support and validity appear next to the measurement. Desktop histogram has units, zero origin, labelled threshold lines, and adjacent data-table heading. Mobile prioritizes measurement table. Coordinate precision finding A11Y-05 applies. |
| S06 | **Map about 662 px and candidate list about 442 px at 1440, excluding the gap: approximately 60% map / 40% list, as explicitly prescribed.** The list is first in reading order and first on mobile. The proportions are not reversed and are not a defect. Horizontal table overflow is explicitly labelled. The offline geometry/no-imagery notice is scientifically honest. A11Y-04 applies. |
| S07 | Matrix dominates; strong labels, glyphs, support, explicit Unknown, and clear status edges. Candidate/requirement orientation controls are visible. Spacing overrides reveal A11Y-02/03. Critic/history/review details not shown are unverified. |
| S08 | Preliminary appears persistently and in the caption. Value, required value, and assessment are separate columns. Conflict state shows FAIL plus a reason. Mobile's assessment is off to the right in a labelled table scroller; screenshot alone cannot verify its keyboard operation. A11Y-01 applies in light mobile. |
| S09 | Empty portfolio has cause and action. Composite state has requirement/site/coverage table with Unknown/Gap and a residual-conditions section beginning below. Co-location warning is plain and short. No oversized PASS. A11Y-01 applies in light mobile. |
| S10/S11 | Experiment preview, primary PROVE IT, disabled reason, headline outcome, and first immutable attempt are presented in calm bands. S11 explicitly retains failed attempts in its headline. Later evidence/playback controls fall below the screenshot and are unverified. A11Y-01 applies to S11 light mobile. |
| S12 | Centred 880 px desktop sheet, mode, qualified-under-assumptions headline, LIMITED shield/word, and explicit physical-clearance UNKNOWN. Mobile stacks sensibly. Requirement table starts below narrative. Export bar, digests and print pagination outside these images cannot be verified. A11Y-03 affects its shell under spacing. |

## Full component guide assessment

All six theme/density combinations retain the same components and visual language. Inspected top sections include shell/header, mode/connection/revision badges, all ten status words/glyphs, button variants and focus appearance, input/number/select/segmented/file/form fields, table, matrix cell, sort header, and tabs. Middle sections include banner/mock banner, empty/error/loading examples, dialog/drawer/tooltip/popover triggers, toast, copy/hash, quantity, timestamp, stepper, and timeline. Both parts' lower sections include histogram/line/bar plus adjacent tables, Chart/Table toggles, layer availability/opacity, legend, scale bar, coordinates, attribution, keyboard hint, assistive-text demonstration, and footer.

The status collection has visible words and distinguishable silhouettes, supporting non-colour reading. The focus demonstration has a clear double boundary in both themes. Disabled controls explain why they are unavailable. Charts start at zero and data tables retain exact values. Neutral surfaces and restrained typography persist through compact/default/comfortable. Demo wording such as "Example histogram" is confined to the component demonstration, not treated as production scientific content.

The guide contains triggers rather than open captures for dialog, tooltip, and popover. Their open visual states are not all demonstrated here; the separate shortcut and drawer images cover their named overlays only. This is a coverage limitation, not evidence that those components fail behavior.

## Rubric scores

| §20 criterion | Score /4 | Evidence and reason |
|---|---:|---|
| Hierarchy | 3 | S07 status cells and S12 LIMITED/UNKNOWN are clear; mobile shell occupies substantial space and A11Y-01 confuses location. |
| Restraint | 4 | S01, S07, S10, and all guides: neutral chrome, scientific status colour, single interactive accent; no ornamental effects. |
| Typography | 3 | S03 numeric inputs and S07 values are orderly; A11Y-02 and A11Y-05 prevent a top score. Font loading/computed families are unverified. |
| Density and spacing | 3 | S03 grid and six guide variants retain rhythm; mobile spacing override exposes A11Y-03. |
| Tables | 3 | S07, S08, S09-composite are scannable with labels/status/units; A11Y-02 is material under spacing. Intentional labelled horizontal scrolling is not itself a defect. |
| States | 4 | S01 emptiness, loading-missions scope text, S08 conflict, S11 disabled explanation, and full-guide error/availability states are designed. Actual rover-import error details are not visible in the supplied crop. |
| Copy | 4 | S05 geometry/support notice, S09 co-location warning and S12 conditional claims are precise and cautious. No hype visible. |
| Consistency | 3 | Shell, panels and status styles are shared; A11Y-01 and coordinate precision inconsistency remain. |
| Map/chart integrity | 3 | S05 zero-origin histogram, units, threshold labels/data table, and S06 offline notice are honest; A11Y-04 remains. Geographic truth and value correctness are not established from screenshots. |
| Accessibility feel | 2 | Clear focus rings and coarse-size mobile controls are positive, but A11Y-01/02/03 make navigation and enlarged text unreliable visually. No keyboard or screen-reader pass is claimed. |
| Crew credibility | 3 | Evidence limitations, mode and failed attempts are explicit; navigation contradictions and measurement overlap need correction before hour-five trust. |
| Absence of X-01–X-29 | 2 | **Open X-26** from A11Y-02/03. No other open X finding established within inspected visual scope. |
| **Total / mean** | **37/48 · 3.083** | **FAIL: not all scores ≥3 and mean <3.5.** |

## Open X findings and unverified behavior

**Open X-26:** text-spacing measurement overlap in the qualification matrix and label overflow in Run context (A11Y-02 and A11Y-03). The table's intentional, labelled horizontal viewport crop is not counted as an X-26 defect by itself. Ordinary below-fold scrolling is not counted as missing content.

No additional open X finding is established in the inspected visual scope. There is no visible emoji, decorative gradient, glass, glow, large pill motif, hero, stock/space decoration, fake similarity gauge, NASA insignia, marketing hype, or per-screen visual reinvention. This does not certify source-enforced X checks.

Screenshots cannot verify: real table/landmark semantics; accessible names/tooltips on icon buttons; focus order, return/trapping or obscuration across a full keyboard walk; screen-reader announcements; shortcuts while typing; URL/list/map selection sync; reduced motion; layout shift; numeric tabular settings; font provenance or network requests; token-only CSS; exact computed font sizes/contrast ratios; build purity; import validation below the captured fold; source data truth; print or export. Visible focus rings on the pictured close buttons and guide demonstration show those pictured appearances only.

Acceptance requires fixing the visible issues and recapturing affected normal/spacing states, followed by the separate behavioral and source checks required by §20. This review did not change implementation or supplied images.


### Verbatim slop report

# AnalogForge independent visual slop review — R5

Decision: **REJECT visual acceptance**. Scores total **39/48**, mean **3.25/4**. Every criterion reaches 3, but the required mean is 3.5. The interface is restrained and recognizably an engineering tool; the remaining weaknesses are operational presentation, mobile prioritization and user-facing copy, rather than decorative AI styling.

## Scope and method

Read only standard 41 and `out/visual/screens.md`, then opened actual catalogued images. No implementation, other review, memory, logs or handoff was read. The catalog's claimed test/audit results were not used as verification. Selectors below are **semantic descriptions of visible elements**, not confirmed CSS selectors or DOM attributes.

Inspected S01–S12 at 1440×900 and 390×844, dark and light, default density (48 screenshots). Additionally inspected evidence-drawer, operations-drawer, shortcut-dialog, loading-missions, error-rover-import, S08-rover-conflict, S04-edited-draft and S09-composite at those two sizes in both themes (32 screenshots). Inspected all twelve full component-guide files at native resolution: `styleguide-{dark,light}-{compact,default,comfortable}-part-{1,2}.png`. Both contiguous parts were viewed for each combination, including the chart/data tables and bottom layer/legend/scale/coordinate/attribution sections; no supplied image was altered. This is a visual sample of catalogued widths, not a claim to have inspected every catalogued file or every scroll position.

Screenshots cannot prove persistence, keyboard operation, tooltip names, focus return, screen-reader semantics, animation, sorting stability, loading duration, exact computed contrast/font sizes, source token compliance or backend/scientific correctness. An image ending at a viewport edge is not by itself evidence of inaccessible content. Labeled local horizontal table/chart scroll is not counted as horizontal **page** overflow or automatically treated as X-26.

## Defects, ordered by severity

1. **P1 — Mobile light navigation contradicts the visible current screen.** Evidence: `S05-390-light-default.png`, `S08-390-light-default.png`, `S09-390-light-default.png`, `S11-390-light-default.png`, also `S08-rover-conflict-390-light-default.png` and `S09-composite-390-light-default.png`. Semantic selector: `run navigation > central tab between previous/next buttons`. The central label says **Passport** while the adjacent `View:` label and page heading say Target, Compatibility, Portfolio or Test lab. Corresponding dark captures show the correct current title and active underline. This is visibly inconsistent orientation information; a screenshot cannot establish whether the underlying route or only the displayed navigator is stale. **Fix:** derive the central label and active styling from the same current-view state as the heading/View label; recapture each light mobile route and investigate capture-state contamination before attributing the cause to implementation.

2. **P2 — Mobile compatibility conceals the assessment behind introductory material and horizontal columns.** Evidence: `S08-rover-conflict-390-dark-default.png` and `S08-rover-conflict-390-light-default.png`, compared with desktop variants where a red Fail is visible in the first row. Semantic selector: `Rover compatibility > preliminary explanation + compatibility table > Server assessment/provenance`. On mobile, chrome/navigation occupy roughly the first 378 px, explanation extends to ~596 px, and the table only begins ~600 px. The Fail assessment is neither visible above the operations bar nor in the visible leftmost table columns. A crew member's first view of the failure contains only a Pending latest modeled test badge, a different result. This is a hierarchy problem, not a claim the table cannot scroll. **Fix:** put a compact compatibility assessment summary immediately below the page title; on narrow screens show metric + assessment first, with declared/required values as expanded detail. Keep modeled-test status explicitly separate.

3. **P2 — Passport scope reads like a validation fixture description rather than a usable test scope.** Evidence: `S12-1440-dark-default.png`, `S12-1440-light-default.png`, also visible at the bottom of mobile captures. Semantic selector: `Analog Passport > assurance/scope paragraph`. Copy reads `Scope: Synthetic test of inadequate terrain support for physical clearance · validation S0` and then `Fixture support is insufficient...`. The limitation itself is necessary and good; `validation S0` and `Fixture support` expose internal testing language without explaining its operational meaning. **Fix:** retain Synthetic and the 60 m support limitation, write the actual modeled test scope in domain language, and move validation-case identifiers into an explicit provenance/details section. Do not remove the uncertainty.

4. **P2 — Passport's candidate column substitutes opaque identifiers for recognizable candidates.** Evidence: `S12-1440-dark-default.png` and `S12-1440-light-default.png`. Semantic selector: `Requirement evidence summary > Status / candidate column`. Rows display badges followed by strings such as `a93ebf16`, `9fc0745a`, `b401970c`; the same user's candidates are named `Practice grid-r0c1`, etc. on S06/S07/S10. This turns the document's evidence comparison into a code lookup and weakens the continuity of the otherwise consistent language. No claim is made that these identifiers are truncated unsafely or lack expansion. **Fix:** show the candidate's recognizable name first and retain the short identifier as secondary mono metadata, with full identifier expansion/copy.

5. **P3 — Attempt cards repeat metadata instead of using the prescribed compact timeline anatomy.** Evidence: `S11-1440-dark-default.png` and `S11-1440-light-default.png`. Semantic selector: `Immutable attempts > first attempt panel`. The heading names Attempt 1, the next line says `Strategy: WAYPOINT_RETURN`, another line says `Modeled test failed`, and a later sentence repeats `Attempt 1; parent none; strategy WAYPOINT_RETURN`, while a Fail badge already carries the result. A sparse card consumes nearly 170 px of the visible region before showing evidence. **Fix:** consolidate attempt number, strategy, parent and result into one compact metadata row; use subsequent space for changed elements, proof scope and receipt. Preserve the vertical chronology and failed attempt.

6. **P3 — Error component's headline is generic despite a specific known conflict.** Evidence: `styleguide-dark-default-part-1.png`, `styleguide-light-default-part-1.png` (also both other densities). Semantic selector: `ErrorPanel demonstration > title`. `Request could not complete` makes the reader scan a separate machine code and body to discover that the revision changed. This is less precise than the standard's actor/cause/remediation voice. **Fix:** use `Revision changed before this action completed` (or similarly precise operation-specific title), retain `REVISION_CONFLICT` as secondary diagnostic metadata and keep the existing retrieve/review remediation. This finding is about the demonstrated copy; it does not assert that all runtime errors reuse it.

## Screen-brief checks

- **S01:** opens directly into Missions and runs, one New mission action, side-by-side desktop tables and row-based Practice presets. No hero or feature cards. Terminal-state/scientific-outcome columns are separate. Empty state is honest.
- **S02:** desktop has ~480 px form and planetary region panel, save status and bbox values. Geometry-only warning prevents the planar grid being misrepresented as measured terrain. Mobile stacks cleanly. Lower form sections and body-switch dialog are outside captured view and not verified.
- **S03:** **passes the specific layout brief**: three actual form columns (Name/Mass/Maximum slope, then Clearance/Wheel/Obstacle) plus a separate right-hand Entered profile summary and import panel at 1440. Explicit Known/Unknown controls and adjacent unit suffixes are visible. Mobile is a single column. Import validation result is below the visible viewport, so the error-rover-import captures do not independently prove its final error message.
- **S04:** pipeline and saved/edited draft states visible. The captured first viewport is still mission authoring; lower requirements, assumptions, acceptance hash and configuration cannot be certified from this framing.
- **S05:** scientific raster legend, explicitly synthetic map support, histogram with units, zero baseline, dashed labeled 12/18 deg thresholds and adjacent data-table frame. Chart's horizontal scroll is explicitly labeled. Full metrics/legend extent below viewport not certified.
- **S06:** **passes the prescribed 60% map / 40% list split**: desktop list is ~442 px and map ~662 px of the ~1104 px combined widths; the 16 px gutter does not reverse that ratio. List is placed first and title/filter prioritize it. Screening order is expressly not similarity. Local table scroll is labeled, scale/coordinate/source labels appear on the map. Collapsed excluded section and selection synchronization are not proven.
- **S07:** precise requirement/candidate matrix, shape+word badges, numeric values/support, details disclosure, candidate summary counts. Mobile switches to candidate orientation. Critic list/history/review panel and pinned footer may be outside viewport; cannot certify absence or behavior.
- **S08:** visible Preliminary label and separate declared/required/assessment fields, including visible desktop fail/unknown state. Mobile prioritization needs defect 2 fixed.
- **S09:** honest unbuilt empty state; composite variant is a coverage table with Unknown and Gap rather than a large PASS. Co-location explanation is compact. Residual conditions starts below table, content below fold unverified.
- **S10/S11:** benchmark preview immediately above PROVE IT; completion disables the control with a persistent reason; headline preserves earlier failed attempts and eventual pass. Attempts appear as a chronological vertical stack but are verbose (defect 5). Route playback/evidence band is outside captured scroll position, hence not certified.
- **S12:** centered ~880 px document sheet, explicit Synthetic/Limited/Unknown scope and requirement table. No decorative watermark. Copy/identifier issues in defects 3–4. Export area, draft banner state and print not visible here.
- **Overlays/states:** evidence and operations use drawers; shortcut help uses one clear dialog with visible focus outline. No result-only toast. Scoped loading labels and table-shaped skeletons appear. Error component has remediation and code. Disabled actions in guides have visible reasons. These images do not establish timing or keyboard functionality.
- **Component guides:** all six theme/density combinations maintain the same component language. Part 1 covers shell, mode/connection/revision/status glyphs, controls/forms/table/matrix/tabs/banner/empty/error/skeleton, overlay launchers, hashes/quantity/time/stepper/timeline. Part 2 covers histogram/line/bar with adjacent data tables and zero baselines, layer unavailable state/opacity controls, legends, scale/readout/attribution, keyboard hint and assistive-text demonstration. Colored badges are semantic, not decoration. Demonstration labels are reviewed as guide specimens, not mistaken for runtime placeholder scientific data.

## Rubric (0–4)

| Criterion | Score | Evidence and rationale |
|---|---:|---|
| Hierarchy | 3 | Desktop status and matrix are clear; mobile S08 fail is not first-glance visible. |
| Restraint | 4 | Flat neutral shell, no effects, colorful status only plus action accent and series. |
| Typography | 4 | Legible consistent sans/mono, visible numeric alignment and adjacent units throughout. Exact computed sizes/font features remain unverified. |
| Density / spacing | 3 | Strong desktop form/matrix rhythm; mobile chrome/explanation and attempt repetition spend scarce working area. |
| Tables | 3 | Consistent headers/rows/units and honest local scroll; passport candidate identity and mobile assessment visibility need improvement. |
| States | 3 | Honest Unknown/Pending/Gap, empty and disabled reasons, scoped loading; generic conflict headline and offscreen runtime import error limit confidence. |
| Copy | 3 | Generally precise and uncertainty-aware; internal fixture/validation wording and redundant attempt metadata remain. |
| Consistency | 3 | One shell/table/badge/drawer language, but mobile light route navigator visibly contradicts the page. |
| Map / chart integrity | 3 | Honest support/synthetic labels, axes/data tables/thresholds; complete chart/map interaction and below-fold context cannot be verified. |
| Accessibility feel | 3 | Visible focus rings, readable light/dark, labeled states; mobile information priority and navigation inconsistency reduce confidence. Keyboard/contrast measurements unverified. |
| Crew credibility | 3 | Explicit scientific limitations and receipts support trust; contradictory navigation and internal test scope detract. |
| Absence of X-01–X-29 | 4 | No definite open banned visual slop finding in inspected scope; source/dynamic requirements remain unverified as listed below. |

**Mean 3.25; required 3.5. Reject pending concrete presentation fixes and fresh capture review.** No 0–1 blocker score is assigned.

## Individual X-01–X-29 assessment

“Clear visually” means no observed manifestation in the inspected images, not a source-scan or behavioral pass.

| Item | Assessment |
|---|---|
| X-01 Emoji | Clear visually: geometric/lucide-style symbols, no emoji. Hidden alt/test IDs/source unverified. |
| X-02 Gradients | Clear visually: flat surfaces; scientific swatches are flat. CSS scan unverified. |
| X-03 Glass | Clear visually: opaque panels; modal backdrop dims without apparent blur. CSS unverified. |
| X-04 Glow/neon | Clear visually: restrained borders and clear focus rings, no halos. |
| X-05 Large radii/pills | Clear visually: square/small-radius controls and badges. Exact radius measurements unverified. |
| X-06 Hero/marketing sections | Clear visually: direct work entry on S01; no splash or illustration. |
| X-07 Decorative space imagery | Clear visually: geometry/raster data panels only, no stars/planets as decoration. |
| X-08 Feature card template | Clear visually: operational tables/forms/panels. Guide specimen grid is a component inventory, not a feature marketing grid. |
| X-09 Placeholder labels | No definite runtime placeholder finding. Practice presets are explicitly named scenarios; guide's Example table/chart labels honestly identify demonstrations. Fixture language in passport is copy defect 3, not fabricated placeholder measurement. |
| X-10 Numerals | Clear visually: mono values and aligned numeric columns; actual tabular-nums declaration unverified. |
| X-11 Tiny/low-contrast text | No definite visual breach; labels remain legible at opened native scale. Computed size/line-height/AA contrast require measurement. |
| X-12 Shouty copy | Clear visually: sentence-case prose/headings; caps used for short status and domain IDs. |
| X-13 Browser defaults | No definite default-browser leak: select/file controls are integrated visually. Range-control styling and native/control implementation cannot be established from a static image. |
| X-14 Unscoped loading | Clear visually: scoped retrieving labels and table skeletons, no bare spinner. Resolution/elapsed timing unverified. |
| X-15 Critical results as toast | Clear visually: persistent state/attempts/passport. Guide toast is View preference saved. Other runtime delivery unverified. |
| X-16 Modal misuse | Clear visually: evidence/operations drawers and a single shortcut-help dialog, which §13 explicitly permits. No modal stack seen. |
| X-17 Unlabeled decorative icons | No definitely decorative isolated icon. Close/copy/map icon buttons are recognizable; accessible names/tooltips cannot be certified visually. |
| X-18 Mixed icon styles | Clear visually: coherent thin-stroke controls plus intentionally distinct custom status silhouettes. |
| X-19 Fake science viz | Clear visually: histogram/matrix/coverage, no match gauges, radar or similarity percent. |
| X-20 Tilt/parallax/carousel | No visible 3D tilt. Motion/autoplay/scroll-jacking unverified. |
| X-21 Off-grid spacing | No visually obvious rhythm break. Exact all-4-px compliance cannot be established from pixels without layout/source measurement. |
| X-22 Typefaces/CDN | Clear visually: coherent sans plus mono, no display font. Actual font count, self-hosting and requests unverified. |
| X-23 NASA impersonation | Clear visually: plain AnalogForge mark; guide footer explicitly disclaims NASA product/endorsement. Source strings unverified. |
| X-24 Hype | Clear visually: no revolutionary/AI-powered marketing claims. Internal test wording is a precision/credibility issue, not hype. |
| X-25 Layout shift/re-sort | Unverifiable dynamically. Static loading views show structured reserved areas, but cannot prove CLS or stable ordering. |
| X-26 Overflow/clipping | No definite unlabelled page-wide overflow or irrecoverably clipped value observed at sampled 1440. Local table/chart scrolling is explicitly labeled. Below-fold content and mobile local scroll are not inherently defects. Other widths and tooltips unverified. |
| X-27 Pure-black/white dark | Clear visually: dark blue-grey canvas and off-white text, no pure-black/white console appearance. Exact token values unverified. |
| X-28 Different visual language | Clear visually: shared shell, table, status and drawer across all screens. Defect 1 is contradictory navigation content/state, not evidence of a second design system. |
| X-29 Color literals | Source-only requirement; unverified. No source read permitted. |

**Open X findings: none established within inspected visual scope.** This does not close source-only or dynamic X requirements and does not override the six concrete presentation findings or failed mean threshold.


## Round5 disposition

Not accepted. Corrective work resolves text-spacing containment in matrix cells/Run context, restores active navigation before each canonical capture (the prior keyboard walk could leave Passport visible), uses the same fixed scientific legend as the prepared raster, formats area coverage as percentages, exposes readable candidate names, keeps the exceptional action height stable, and brings compatibility assessments into the mobile first view. Raw scientific values, claim/provenance text, API contracts and immutable exports remain unchanged. The coordinate formatter already emits exactly5decimals; that review observation is being checked against actual DOM text rather than changing a correct formatter.

## Round6 — source4c801f4

The complete33-test browser gate passed with zero failures, skips or flaky tests. The visual report includes407 reports and409 screenshots (including the permanent spacing regression and12 complete guide parts), with zero automated findings/skips. Fresh HMI, accessibility/typography and hostile slop reviewers received only architecture41, the exact final catalog/images and the12-criterion rubric. They inspected both themes, desktop/mobile, spacing, special states and all12 guide parts. Prior scores and reports were not supplied.

### Verbatim hmi report

# Independent mission-operations HMI review — round 6

**Decision: FAIL. Scores: 3, 4, 4, 2, 3, 3, 4, 4, 3, 3, 3, 4. Mean: 40 / 12 = 3.333.** Acceptance requires every score at least 3 and mean at least 3.5. Density fails the individual threshold; the mean also fails. No score is 0–1.

## Scope and evidence boundary

Read only standard 41, `out/visual/screens.md`, and images named by that catalog. No implementation, logs, previous reviews, handoffs, memory, or external references were consulted. ISA-101/Open MCT is used as the reviewer perspective expressed in standard 41, not as a claim of certification.

Opened actual S01–S12 screenshots at 1440×900 and 390×844 in both themes. Opened evidence drawer, operations drawer, shortcut dialog, loading missions, rover import error, rover conflict, composite portfolio, and edited draft at those viewports in both themes. Opened the S02/S04/S07/S12, edited-draft, and spacing-owned text-spacing samples at those viewports in both themes. Opened all twelve full guide parts: `styleguide-{dark,light}-{compact,default,comfortable}-part-{1,2}.png`. Each pair was read across its 48px overlap; additionally cropped each supplied part into two overlapping native-scale reading sections under `/tmp/hmi-r6-guide-crops/` because tall image display initially reduced their size. Supplied images were not changed.

This is a screenshot review, not an implementation or interaction acceptance. Scores for typography, accessibility and X absence describe visible appearance only. Font files, computed sizes/contrast, numeric font feature settings, token literals, DOM semantics, names/tooltips, focus return/trapping, keyboard traversal, scroll reachability, CLS, latency duration, reduced motion, route/data truth, print, and exports remain unverified. Semantic selectors below identify visible elements by role/name or standard component name; they are not asserted source selectors.

## Rubric

| Criterion | 0–4 | Evidence / limitation |
|---|---:|---|
| Hierarchy | 3 | Separate lifecycle and latest modeled test; PASS/FAIL/UNKNOWN glyph + word. Mobile chrome competes heavily with work. S07, S08-conflict, S11, S12 both themes. |
| Restraint | 4 | Neutral flat shell; colour reserved for state, selection/accent, scientific series. No decorative space imagery. All inspected application screens and guide pairs. |
| Typography | 4 | Clear title/body/mono hierarchy; quantities visually align right with adjacent units. S03, S07, S08, S10 and guide Quantity/FormField. Computed typography unverified. |
| Density and spacing | 2 | Mobile work often starts around y396, with persistent lower operations region near y758; S06 initially exposes only a fragment of one candidate row. S01 preset block is large rather than slim. See HMI-01/03/05. |
| Tables | 3 | Matrix is recognizably an engineering table; requirement IDs, units, support and state retained. Horizontal overflow is expressly labelled. Caption handling under text spacing and shallow loading viewport need work. |
| States | 3 | Real empty reasons; scoped retrieval text; persistent conflict FAIL; disabled PROVE IT explains completed run. Loading table presentation is shallower than required. Import error capture does not expose the actual validation message. |
| Copy | 4 | Synthetic scope, modeled-vs-physical distinction, scale limitations, and co-location caveat are explicit. No hype. S05, S08, S09-composite, S11, S12. |
| Consistency | 4 | Same shell, table anatomy, state glyph/word, disclosure and drawer appearance in both themes. All six guide theme/density combinations preserve component language. |
| Map/chart integrity | 3 | S06 extent-only view explicitly disclaims basemap/raster; C1–C6 labels correspond to table. Scale and attribution visible. S05 chart has zero baseline, units, threshold labels and adjacent table. Exact spatial/scientific correctness and offscreen chart content unverified. |
| Accessibility feel | 3 | Visible focus ring in drawers/dialog/guide; large mobile controls; colour never sole state carrier. Text-spacing samples substantially reflow; caption is awkward at 390px. Actual keyboard and AA metrics unverified. |
| Crew credibility | 3 | Explicit limited assurance, unknowns and provenance inspire confidence. Poor mobile information yield and sparse operations event view impede shift work. |
| Absence of X-01–29 | 4 | No confirmed open X violation within the inspected visual scope. This is not a source scan or behavioral clearance. See X disposition. |

## Findings, severity ordered

### HMI-01 — P2: mobile shell leaves too little room for operational work

**Images:** `S06-390-dark-default.png`, `S06-390-light-default.png`, `S07-390-dark-default.png`, `S07-390-light-default.png`, `S07-390-dark-default-spacing.png`, `S07-390-light-default-spacing.png`.

**Semantic selectors:** AppHeader; workspace navigation; `run-state-banner`; button “Run context”; run view selector; collapsed operations region containing “Open operations” / “Open evidence”.

At 390px, application chrome plus run context and view selection occupies roughly the first 380px; the operations region occupies roughly the last 76px. S06's initial candidate body begins around y715 and stops around y750, exposing no complete candidate row. In the spacing override S07, the first data row begins near y730 and only a small fragment remains. The primary engineering object loses to context chrome. This is a visible density/hierarchy defect, not a claim that scrolling is broken.

**Fix:** compact the mobile summary to lifecycle + latest test + mode in a short summary row; put revisions and mission context behind the existing disclosure; combine “View:” and the selector into one row. Keep the bottom rail to a single 44px action row and move the event cursor into expandable operations. Retain 44px touch targets. Aim to show at least two complete candidate/matrix rows at initial 390px view.

### HMI-02 — P2: loading tables expose only a shallow skeleton fragment

**Images:** `loading-missions-1440-dark-default.png`, `loading-missions-1440-light-default.png`, `loading-missions-390-dark-default.png`, `loading-missions-390-light-default.png`.

**Semantic selectors:** table/caption “Missions”; loading tbody/Skeleton; status “Retrieving saved missions”; table/caption “Investigations”.

The loading Missions frame shows one complete skeleton row and a sliver of the next, whereas §9.5 requires four skeleton rows of final row height. In the desktop dark image Investigations has the same shallow fragment. Scoped retrieval copy is good, but the content-shaped placeholder is visually cut short.

**Fix:** reserve a table loading body tall enough to display four final-height skeleton rows without the lower row being bisected; place retrieval text inside the table's labelled loading region. Preserve the same reserved body across loading and settled states. No CLS measurement is inferred from the screenshots.

### HMI-03 — P3: practice presets are an oversized panel, not a slim strip

**Images:** `S01-1440-dark-default.png`, `S01-1440-light-default.png`, `S01-390-dark-default.png`, `S01-390-light-default.png`.

**Semantic selector:** region heading “Practice presets”; preset action rows.

The desktop preset region runs approximately y386–724 (338px), roughly twice the height of either mission/run table. On mobile its first preset only appears around y830. This reverses §10 S01's emphasis on work tables followed by a slim preset strip, even though the presets are correctly rows rather than cards.

**Fix:** use a compact region header with one concise scope note, tighter desktop row padding, and a disclosure for the preset list on mobile. Keep the synthetic/live availability explanation accessible in the opened region.

### HMI-04 — P3: matrix caption is horizontally displaced by text spacing

**Images:** `S07-390-dark-default-spacing.png`, `S07-390-light-default-spacing.png`, `spacing-owned-390-dark-default-spacing.png`, `spacing-owned-390-light-default-spacing.png`.

**Semantic selector:** table caption “Requirement qualification · by candidate”.

The caption crosses the right edge of the visible table frame; “by candidate” is cut at the edge. The table correctly advertises intentional horizontal scrolling, so this is not evidence of inaccessible text or a confirmed X-26 violation. Nevertheless, the caption that names the current orientation should remain readable independently of matrix scroll position.

**Fix:** keep caption and scroll instruction outside the horizontally scrolling column canvas, with normal wrapping and an unconstrained height. Only the matrix columns should require horizontal scrolling.

### HMI-05 — P3: operations drawer spends its visible event area on one sparse event

**Images:** `operations-drawer-1440-dark-default.png`, `operations-drawer-1440-light-default.png`, `operations-drawer-390-dark-default.png`, `operations-drawer-390-light-default.png`.

**Semantic selectors:** drawer heading “Operations timeline”; `operation-row` with seq “#1”, actor “Actor unknown”, summary “Run state changed”.

The desktop 220px drawer contains a heading, repeated generic evidence/provenance introduction, and one event spread across the remaining region: timestamp and actor at far left, summary in the middle, stage and message at far right. This is unusually sparse for the §9.11 telemetry-like event timeline and makes a sequence harder to scan. On mobile one event occupies most of the drawer's visible body.

**Fix:** remove the repeated generic introductory sentence from operations; align seq, time, actor, summary and evidence on compact event rows, with stage/message composed into one summary. Keep full detail in the existing disclosure. Unknown actor is honest and should remain explicitly labelled until supplied.

## Brief-specific checks and evidence gaps

- **S03:** meets the specific desktop composition: three field columns and right-hand entered-profile summary plus import/validation region. Unknown segmented controls and unit suffixes are visible. Mobile stacks cleanly. Do not remove the summary or replace this with a full-width undifferentiated form.
- **S06:** meets the specific desktop proportion: list is approximately 40%, map 60%; list comes first and uses “Screening order”, with a clear non-similarity statement. Table overflow is intentional and labelled. Missing offscreen columns are not declared absent. Selection synchronisation and geographic fidelity cannot be proven by stills.
- **S04:** captures show authoring with the four-step pipeline and active Start, but the requirements/freeze panel itself is below the captured viewport. Revision/hash adjacency to Accept contract and assumptions/conflicts cannot be accepted or failed from these views alone. Obtain a scrolled capture of that region.
- **S05:** units/support and synthetic source caveat are visible. Horizontal chart overflow is explicitly announced; no assertion that the ninth bin is lost. Full chart/table and planetary-panel controls below the fold need scrolled evidence for complete acceptance.
- **S08 conflict:** FAIL at maximum surface slope is visible alongside declared 12deg and required 12–18deg at desktop, and as a prominent mobile summary row. Preliminary stays persistent. Good separation from modeled-test outcome.
- **S09 composite:** actual coverage table shows UNKNOWN and GAP rather than a misleading global PASS. Residual conditions continue below the viewport; they were not declared absent.
- **S10/S11:** experiment, accepted preview/disabled explanation, outcome headline and first immutable attempt are visible. Later attempts, before/after diff, evidence band and route transport are offscreen; behavior and completeness there remain unverified.
- **S12:** centred desktop sheet, synthetic mode, qualified-with-assumptions headline, LIMITED assurance and explicit clearance UNKNOWN are present. Attempts, digest/export bar and print cannot be accepted from initial-viewport screenshots.
- **Errors:** the guide shows a designed conflict ErrorPanel with cause and remediation. The `error-rover-import` captures show chosen invalid filename at the desktop lower edge, but not the actual error panel or validation table; mobile shows only the upper form. This is an evidence gap, not a fabricated claim of missing error handling.
- **Complete guide:** all six theme/density pairs cover component primitives, badges/glyphs, buttons and focus appearance, form controls, error/empty/loading, overlay launchers, hashes, stepper/timeline, three chart types and adjacent data tables, layers/legend/scale/coordinates/attribution, keyboard hint and visually hidden example. “Open…” overlay launchers are not proof of all opened overlay states. Example chart points and table values agree visually (0.4, 0.3, 0.2); baselines start at zero.

## X-01–29 disposition

**No confirmed open X finding within inspected visual scope.** No emoji, marketing hero, gradients, blur/glow, large decorative radii, starfield, fake similarity viz, noisy typography, NASA insignia or inconsistent screen language was seen. Labelled table/chart overflow is expressly allowed and is not scored as an X-26 failure. The right-clipped caption in HMI-04 remains a presentation issue; inability to recover its full text has not been established.

Source-only X items (including colour literals, font/CDN requests), exact pixel thresholds, inaccessible icon names/tooltips, motion and layout-shift behavior remain unverified rather than passed. Initial viewport cutoff at the scroll boundary is not automatically a text-overlap defect. Reported deficiencies concern density and required loading presentation, not an invented scientific or runtime failure.


### Verbatim accessibility report

# AnalogForge independent accessibility and typography review — R6

Decision: **FAIL visual acceptance**. Score **38/48; mean 3.17/4**. All criteria reach 3, but the required mean is 3.5. This is a screenshot review, not a WCAG conformance certification.

## Scope and evidence

Read only standard 41 and `out/visual/screens.md`, and opened their supplied images. No memory, implementation, logs, handoffs, or other reviews were consulted. Inspected S01–S12 at 1440×900 and 390×844, dark and light; evidence and operations drawers, shortcut dialog, mission loading, rover-import error, S08 rover conflict, and S09 composite at both sizes/themes; S02, S04 edited draft, S07 and S12 text-spacing captures at both sizes/themes; S07 and S10 compact/default/comfortable desktop captures. Opened all twelve complete guide parts: `styleguide-{dark,light}-{compact,default,comfortable}-part-{1,2}.png`, including each second part through the footer. The contiguous parts include the documented overlap. The guide remains readable, with consistent token-like treatment across densities.

All screenshot filenames below are relative to `out/visual/`, except guide parts, which are in `apps/web/docs/design-review/`. Selectors below are semantic identification recipes, not verified DOM/CSS selectors.

## Findings, severity order

1. **P2 — Mobile text spacing leaves the matrix caption cut at the right edge.** `S07-390-dark-default-spacing.png` and `S07-390-light-default-spacing.png`: the caption “Requirement qualification · by candidate” runs into the right frame rather than wrapping. The normal version fits. Semantic selector: table named “Requirement qualification · by candidate” → caption. This is precisely where extra letter spacing should remain safe (§15/VIS-17). Fix: allow caption text to wrap independently of the horizontally scrolling data grid; size its box to the visible table frame. **Open X-26 visual concern.** Whether a tooltip, expand action or horizontal scrolling exposes this caption cannot be established from pixels; the clipping itself is visible.

2. **P2 — First mobile work viewport is dominated by shell and explanatory chrome.** `S06-390-dark-default.png`, `S06-390-light-default.png`, `S10-390-dark-default.png`, `S10-390-light-default.png`: header/navigation/context/view switch occupy roughly the first 380 px; filters, descriptions, captions and headers leave only part of one candidate row on S06, and no benchmark data or PROVE IT on S10. Semantic selectors: main → run-state banner; navigation named current view; candidate table; “Accepted experiment” panel. This reduces scanning and adds scroll burden for users with large text or limited motor endurance. Fix: retain lifecycle/result and one compact revision line, fold ancillary context, shorten repeated helper strips, and place the principal table/action earlier. This is a visible density issue, not a claim that scrolling or focus is broken.

3. **P2 — Passport summary separates the requirement label from its first results.** `S12-1440-dark-default.png` and `S12-1440-light-default.png`: the first requirement cell is largely blank while several candidate statuses stack at the top of the adjacent cell; “R-SLOPE-AVAILABILITY” and its rule sit down near the viewport bottom. Semantic selector: table “Requirement evidence summary” → first body row → requirement header cell. The eye cannot associate the first PASS entries with their rule at a glance. Fix: top-align requirement cells, then use compact candidate subrows or an explicit expanded detail list. Preserve the 880 px sheet and complete status text.

4. **P2 — S06 primary list loses essential columns even on desktop.** `S06-1440-dark-default.png` and `S06-1440-light-default.png`: the list correctly uses about 40% and map about 60%, but the visible list ends in the middle of Origin; window information is outside the frame. The wide map uses generous blank space while primary list names wrap. Semantic selector: table caption “Candidates · 6 of 6 visible” → Origin/window columns. The horizontal-scroll instruction makes this intentional overflow, so it is **not** automatically X-26. It is still poor primary-object scannability under the S06 brief. Fix within the required ratio: combine rank and selection affordance, give name a clear compact line, and present origin/window as labelled second-line metadata or an expandable row. Do not shrink the type.

5. **P3 — Loading table presentation cuts off its own skeleton rows.** `loading-missions-1440-dark-default.png`: each table frame shows one skeleton row and a sliver of another before the boundary, instead of the four designed skeleton rows specified by §9.5. `loading-missions-390-dark-default.png` and the corresponding light capture likewise show a very short skeleton region. Semantic selector: “Missions” table → loading body; “Investigations” table → loading body. Fix: reserve a deliberate four-row loading body, or use a clearly bounded scoped loading state matching the final empty/table region. No CLS or load-resolution claim is made; static screenshots cannot establish either.

6. **P3 — Chart help is metadata rather than an analytical text summary.** All six guide `*-part-2.png` images show histogram/line/bar sections with “3 supplied bins · fraction. Exact values are retained in the data table.” The adjacent exact-value tables are good, but the prose does not describe the visible pattern. Semantic selector: component guide → Chart(Histogram|Line|Bar) → chart subtitle/summary. §10.5 explicitly requires a text summary line. Fix: add “A is highest at 0.4; values decrease to C at 0.2” for these fixtures, and domain-specific summaries in product charts. This improves nonvisual comprehension without treating a table as a substitute for a summary. Screen-reader descriptions may exist but are unverified.

## Brief-specific assessment

S03: the desktop captures do show the required three-column field grid and right-side entered-profile summary/import panel; explicit Known/Unknown controls and numeric unit suffixes are visible. No finding alleging the earlier missing layout is supported. Mobile stacks the form legibly. Import-error capture has the invalid filename low in the desktop viewport and the actual validation result below the captured mobile viewport; error-summary focus or failure visibility after scroll remains unknown.

S06: map/list 60/40 is visibly respected, and C1–C6 labels connect the map to the list. Scale bar, coordinate-readout instruction and attribution appear. The 40% list still needs better prioritization as described above. Geometry truth, map interaction, URL sync, coordinate accuracy and scale calculations are unverified.

S07: strong state glyph/word/edge combinations, units and mono-looking values support scanning; labelled horizontal table overflow is deliberate. S08 explicitly distinguishes preliminary assessment and shows a visible FAIL for the conflict capture. S09 composite uses requirement-level Unknown/Gap results rather than an unjustified global PASS. S10/S11 distinguish modeled tests from physical execution and retain failed attempts. S12 visibly qualifies assurance with LIMITED and obstacle-clearance Unknown.

## Rubric

| Criterion | Score | Evidence and limit |
|---|---:|---|
| Hierarchy | 3 | Lifecycle and scientific outcome separate; mobile work competes with substantial shell. |
| Restraint | 4 | Flat neutral chrome; semantic state and restrained accent colour; no decorative space imagery. |
| Typography | 3 | Legible, coherent sans/mono appearance and clear numbers; passport association and spaced caption need correction. |
| Density/spacing | 3 | Ordered panels and grids; mobile chrome and S06 list impose unnecessary scrolling. |
| Tables | 3 | Good dividers, status labels and quantity alignment; S12 row association and S06 metadata visibility weaken scanning. |
| States | 3 | Scoped loading, honest emptiness, disabled reason, conflict badges; skeleton region lacks a complete designed body. |
| Copy | 3 | Precise modeled/synthetic/unknown distinctions; chart text summary is incomplete. |
| Consistency | 4 | Same shell, status grammar, inputs, buttons and drawer treatment across both themes and guide densities. |
| Map/chart integrity | 3 | Explicit synthetic support, labelled limits, adjacent tables and no fake similarity gauge; scientific/interactive correctness unverified. |
| Accessibility feel | 3 | Focus rings visible in drawer/dialog/guide captures; word+shape states and comfortable mobile controls. Text-spacing caption defect remains; actual keyboard/AT behavior unverified. |
| Crew credibility | 3 | Honest scope/assurance and provenance presentation; first-viewport efficiency and passport association need work. |
| Absence of X-01–29 | 3 | No decorative slop visible; X-26 clipping concern remains in spaced mobile matrix caption. Source-only bans unverified. |

Total 38; mean 3.17. Threshold: every score ≥3 AND mean ≥3.5. **FAIL**.

## X findings and verification boundary

Open within inspected visual scope: **X-26 / VIS-17 concern** for the S07 mobile text-spacing caption. Labelled table/graph overflow elsewhere is not counted as prohibited page overflow. Viewport-bottom cutoffs alone are not proof of unreachable content or obscured focus.

No visible evidence of emoji, gradients, glass, glow, oversized decorative radii, hero/card marketing, starfields, hype, fake similarity gauges, mixed screen languages, NASA insignia, or pure-black/pure-white dark treatment. Pixel appearance cannot prove font identity, computed font size/line-height/contrast, tabular-numeral CSS, 4 px token compliance, accessible names/tooltips, focus order/return/trapping, semantic table markup, screen-reader announcements, reduced motion, live loading resolution, source literal restrictions, dependency licensing, runtime requests, print behavior or build exclusions. Those remain unverified, not passed. The guide’s component demonstration labels are not interpreted as product placeholder-copy defects.


### Verbatim slop report

# Independent hostile visual review — round 6

Decision: **FAIL**. Scores total **38/48**, mean **3.167/4**. Density/spacing is below 3 and the mean is below 3.5. This is a restrained engineering interface, not an obvious marketing template; the failure is operational information placement and repetitive presentation, not gradients or decoration.

## Scope and evidence limits

Read only standard 41 and `out/visual/screens.md`, then opened actual supplied screenshots. Inspected S01–S12 at 1440×900 and 390×844 in both themes; S04/S07/S12 text-spacing variants at both sizes and themes; S07/S10 compact and comfortable desktop variants; evidence drawer, operations drawer, shortcut dialog, loading missions, rover import error, rover conflict and composite portfolio at desktop/mobile in both themes; edited-draft desktop in both themes. Opened **all twelve** native guide parts (`styleguide-{dark,light}-{compact,default,comfortable}-part-{1,2}.png`) at original detail, including their contiguous overlap. No supplied images or application source were changed. No memory, implementation, logs, other reviews or handoffs were consulted.

Selectors below are semantic visual locators (role/text/label), not source-verified DOM selectors. No claims are made about hidden accessibility names, font files, computed CSS, actual keyboard execution, persistence, motion, loading duration, exports, provenance truth or runtime map geometry. A viewport boundary is not by itself proof of inaccessible content. Labelled horizontal table scrolling is explicitly distinguished from page overflow.

## Scores

| Criterion | Score | Evidence and reason |
|---|---:|---|
| Hierarchy | 3 | S07 matrix statuses and S12 LIMITED are visible; mobile run chrome repeatedly outranks working content. |
| Restraint | 4 | Flat neutral surfaces, small semantic state accents; no hero, decorative imagery, glow or reward UI. |
| Typography | 3 | Numeric values visibly mono/right aligned and units adjacent; S03 label casing and S12 row alignment remain uneven. Computed font properties unverified. |
| Density/spacing | 2 | Mobile S06/S10 show almost no actionable table content above the bottom bar; S12 expands one requirement into an excessively tall row. |
| Tables | 3 | Strong row rules, captions and status cells; excessive caption/scroll-helper overhead and passport vertical alignment weaken scan paths. |
| States | 3 | Scoped loading, empty portfolio, persistent conflict FAIL, disabled PROVE IT explanation, focused overlay close controls. Import-error captures do not expose the actual error message. |
| Copy | 3 | Plain scientific qualification and explicit uncertainty; presentation still leaks machine-oriented names and inconsistent field casing. |
| Consistency | 4 | Shell, borders, badges, tables and overlays retain one visual language across themes and screens. |
| Map/chart integrity | 3 | No similarity gauge; explicit synthetic/offline limitations and tables. Compact guide histogram has a misaligned first tick. |
| Accessibility feel | 3 | Clear focus rings on captured overlays, textual states and large mobile controls; spacing variant caption and small working viewport need improvement. Behavior/AA not certified. |
| Crew credibility | 3 | Honest model/physical distinction and limitations are strong; excessive repetitive chrome and machine-code copy reduce hour-five usability. |
| Absence of X-01–29 | 4 | No unequivocal open banned-item finding established in the inspected visual scope; source-only and temporal items remain unverified, not certified. |

## Concrete defects, severity ordered

### 1. P2 — Mobile shell consumes too much of the usable work area

Evidence: `S06-390-dark-default.png`, `S06-390-light-default.png`, `S10-390-dark-default.png`, `S10-390-light-default.png`, `S07-390-dark-default-spacing.png`, `S07-390-light-default-spacing.png`.

Semantic selectors: `banner`, `navigation` containing Missions/Rovers/About, run-context disclosure, run-tab navigation, operations footer.

The repeated header, preview strip, workspace navigation, lifecycle panel, revision line and view switch occupy approximately the first 378 px. The bottom operations bar consumes another ~85 px. S06 shows only a fragment of candidate 1; S10 reaches the benchmark header before the fold, while PROVE IT is below. Spacing overrides worsen S07 to a fragment of its first result. This is visible density/hierarchy failure under §0, §1.3 and §20, not proof that scrolling is broken.

Fix: compress mobile context to a one-line lifecycle/outcome/revision summary, move full run metadata into its existing disclosure, eliminate duplicated View/current-tab naming, and reduce repeated table helpers. Reserve meaningful space for at least two result rows or the primary action.

### 2. P2 — Passport requirement name is stranded far below its first result

Evidence: `S12-1440-dark-default.png`, `S12-1440-light-default.png`; especially `S12-1440-dark-default-spacing.png` and `S12-1440-light-default-spacing.png`.

Semantic selector: table caption `Requirement evidence summary`, first body row, row header `R-SLOPE-AVAILABILITY`.

The right column vertically stacks candidate verdicts while the left requirement cell is vertically centered in the resulting tall row. At default spacing its identifier appears near the bottom of the screenshot after several candidate outcomes. With spacing overrides the first PASS is visible while its requirement name falls below the visible working area. That breaks the immediate requirement→result association and makes a document intended for review look unfinished.

Fix: top-align requirement cells; preferably make one candidate assessment per subrow with the requirement heading repeated or grouped at the top, and keep explanatory text attached to its group. Preserve full evidence without generating huge blank left cells.

### 3. P2 — Compact guide histogram first category tick is visibly off-center

Evidence: `styleguide-dark-compact-part-2.png`, `styleguide-light-compact-part-2.png` (top chart, `Example histogram`).

Semantic selector: chart `Example histogram`, x-axis tick `A`, first bar.

A is positioned near the first bar's left edge while B/C are at their respective centers. The default and comfortable equivalents place A centrally. The compact variant therefore demonstrates inconsistent chart geometry, not merely reduced padding. Tables retain the correct 0.4/0.3/0.2 values, so the defect is axis placement rather than established numerical falsification.

Fix: derive all tick anchors from the same band-center calculation as the bars for every density; re-capture the compact variant.

### 4. P3 — Generic table instructions add noise even to empty tables

Evidence: `S01-1440-dark-default.png`, `S01-1440-light-default.png`, `S01-390-dark-default.png`, `S01-390-light-default.png`.

Semantic selectors: tables `Missions` and `Investigations`, helper text `Scroll horizontally for all columns · use arrow keys when focused`.

Both empty tables carry identical instructional strips. Mobile spends two full lines on each before displaying the empty state; there is nothing substantive to inspect horizontally. This gives the screen a generic component-demo feel and competes with the one useful next step, New mission.

Fix: show the scroll instruction only when populated columns overflow, keep an unobtrusive accessible description, and omit header scaffolding for an entirely empty table until useful data exists.

### 5. P3 — Rover field naming slips into source-schema casing

Evidence: `S03-1440-dark-default.png`, `S03-1440-light-default.png`.

Semantic selectors: labels `sensors (comma separated)`, `capabilities (comma separated)`, `assumptions (comma separated)`.

These lowercase labels follow the sentence-cased Name/Mass/Maximum slope fields. The abrupt casing and repeated serialization instruction look like schema labels inserted into an otherwise deliberate form.

Fix: use Sensors, Capabilities and Assumptions; move `Separate entries with commas.` to consistent field hints or use an editable list control. This is copy/typography polish, not an X-12 all-caps violation.

### 6. P3 — Benchmark rules expose serialization identifiers at the main scan level

Evidence: `S10-1440-dark-default.png`, `S10-1440-light-default.png`, compact/comfortable equivalents.

Semantic selector: table `Frozen benchmark preview`, Rule cells such as `GTE · unique_slope_exposure_m` and `GTE · final_battery_reserve_pct`.

The accepted values are well aligned, but a crew member must decode internal-looking snake_case rather than read a requirement. The page repeatedly insists on scientific precision while its most useful rule labels look like API payload fields.

Fix: render `Unique slope exposure ≥` and `Final battery reserve ≥` with the original metric identifier available in a disclosure. Keep stable requirement IDs unchanged. This is domain copy improvement, not evidence of placeholder data.

## Specific §10 brief checks

- S01 opens directly into work and two desktop tables, with preset rows, not a feature grid. Empty-state helper redundancy is finding 4.
- S02 is a form beside an explicitly geometric planetary panel; save states are visible. The screenshot does not establish sticky section anchors or body-switch confirmation behavior.
- **S03 meets the requested three-column field grid plus right-hand entered-profile summary/import panel.** It must not be failed as a missing-summary layout. Optional Unknown controls are visible. Validation results below the fold cannot be certified from these shots.
- S04 captures authoring with pipeline header and saved/edited drafts. Requirements acceptance/hash/configuration are not visible in these viewport captures; no inference that those sections do not exist.
- S05 has explicit synthetic raster support, threshold labels, histogram and adjacent table. Chart clipping is in an explicitly labelled horizontally scrolling region, so not automatically X-26.
- **S06 visibly implements approximately map 60% / list 40%.** The list comes first in the reading order and is the principal named object. Its narrow pane requires labelled horizontal scrolling for origin/window columns; that is a usability cost, not proof of banned page overflow. Excluded-section and selection synchronization behavior unverified.
- S07 reads as an engineering matrix with explicit PASS/FAIL/UNKNOWN, support and stage. Critic/history/review behavior is not established by this visual set.
- S08 has the required comparative table and Preliminary caption; conflict images show FAIL for 12 deg against 18 deg upper requirement. Mobile gives a useful assessment summary, with detailed values lower down.
- S09 composite uses per-requirement coverage and GAP/UNKNOWN states, not a giant PASS. Co-location caveat is one short paragraph.
- S10/S11 show experiment/attempt bands and a plain result headline; the first attempt in S11 remains FAIL despite latest PASS. Evidence/playback lower down is outside these captured viewports.
- S12 uses the centered 880 px document sheet, explicit mode and LIMITED assurance. Finding 2 prevents a clean document-review score. Export/print state is not proven.
- Evidence uses a right desktop drawer/mobile sheet and operations a bottom drawer. Keyboard-help dialog shows the specified seven shortcuts. Focus rings are legible in both themes; actual shortcut handling is unverified.

## X-01–29 individual disposition

`No visible finding` is confined to inspected pixels and does not mean a scan or behavioral gate passed.

| Item | Disposition |
|---|---|
| X-01 Emoji | No visible finding; status shapes are restrained monochrome/semantic glyphs. Underlying codepoints/alt text unverified. |
| X-02 Gradients | No visible surface/button/text gradient finding. Source CSS unverified. |
| X-03 Glass | No visible blurred/translucent glass panel finding. Modal dimming alone is not glass. |
| X-04 Glow | No visible glow/neon finding; focus rings are legitimate interaction affordances. |
| X-05 Large radii/pills | No visible finding; panels/buttons have small squared corners. Exact computed radii unverified. |
| X-06 Hero/marketing | No finding; S01 starts with operational tables and New mission. |
| X-07 Decorative space art | No finding; planetary panels are labelled geometry/data. |
| X-08 Feature grids | No product-screen finding. Guide component catalog is a legitimate demonstration grid, not product marketing. |
| X-09 Placeholder text | No product-screen placeholder finding. Guide's Example table/chart labels describe component demonstrations, not substituted scientific data. |
| X-10 Numerals | No visible aligned-column numeral defect. Computed tabular-nums unverified. |
| X-11 Small/low-contrast text | No unequivocal visual finding. Exact font sizes, line heights and contrast require measurement. |
| X-12 Shouty text | No finding. Compact status labels and machine identifiers are not all-caps paragraphs. Spacing override images intentionally increase tracking and are not default styling. |
| X-13 Browser leakage | No unequivocal finding. Range sliders in guide resemble native controls but are not enough to establish unstyled implementation; file/select primitives are visibly styled. |
| X-14 Unscoped loading | No finding; Retrieving saved missions/investigations/scenario availability scopes the work. Duration/resolution unverified. |
| X-15 Critical toasts | No finding; guide toast only says View preference saved. Temporal runtime notification behavior unverified. |
| X-16 Modal misuse | No finding; evidence/operations are drawers and shortcut help is an appropriate single overlay. No modal-on-modal shown. |
| X-17 Unlabelled icons | No proven finding. Icon-only close/copy/zoom controls visible; aria-label/tooltips require DOM/interaction inspection. |
| X-18 Mixed icon sets | No visible incompatible icon language. Exact icon library/stroke widths unverified. |
| X-19 Fake similarity visualization | No finding; no radar/gauge/similarity score. Compact histogram tick defect is finding 3, not a forbidden similarity chart. |
| X-20 Parallax/autoplay | No static visual finding; temporal behavior unverified. |
| X-21 Off-grid spacing | No unequivocal pixel-level finding; computed spacing tokens unverified. |
| X-22 Fonts | No visible display/script/third-face finding; font sources and network requests unverified. |
| X-23 NASA branding | No finding; no insignia/approval badge; guide footer explicitly denies endorsement. |
| X-24 Hype | No finding; scientific uncertainty and modeled-test limitations are explicit. |
| X-25 Layout shift | Unverified from static screenshots; no pass claim. |
| X-26 Overflow/clipping | No unequivocal banned finding. Table/chart boundaries are explicitly labelled horizontal-scroll regions; viewport bottom cuts do not prove inaccessible content. Spacing caption readability merits improvement but is within a labelled scrolling table. Page overflow/tooltips/scroll reachability unverified. |
| X-27 Pure black/white dark | No visible finding; dark canvas/text are softened. Exact tokens unverified. |
| X-28 Different screen languages | No finding; strong consistent shell/table/badge/drawer treatment across the inspected set. |
| X-29 Color literals | Source-only; unverified and not inferable from screenshots. |

**Open X findings within inspected visual scope: none established.** Six concrete non-X design defects remain above. This is not source/behavior certification and does not waive any VIS check.


## Current disposition

Build and functional verification pass. Independent visual acceptance does not pass: HMI40/48, accessibility38/48, slop38/48. Remaining findings concern mobile information density, matrix caption presentation under spacing, passport table layout and other presentation details described verbatim above. DR-02 and DR-03 remain failed; ready_to_merge remains false. No visual acceptance or production-readiness claim is made.
