# Merged interface review

Review scope: the executable source at `c263d2affedfcb17b9e9adb69765f832019650a7`, real API, worker, science and renderer, plus the same frontend in preview mode. Final audit and manual results are recorded in `MERGE-REPORT.json` and the small `out/` summaries. Both full final visual audits and the33-page print inspection completed successfully.

This is one review by the merging agent. The user's instruction to use no subagents overrides merging guide 04 §4b.4, which asks to “spawn three fresh reviewer subagents.” No independent reviewers or verbatim external reviewer reports are claimed. The review considers operations, accessibility/typography, and visual restraint as three perspectives within the same review.

The review inputs are the actual screenshot catalog and images in the clean merged checkout's `analogforge/out/visual/`, the corresponding preview audit, the printed passport, and browser interactions in this chat. Screenshots from interrupted or failed revisions are comparison evidence; they do not count as final passes.

## Defects caught and repaired

| Finding | Evidence and selector | Assessment | Repair and check |
|---|---|---|---|
| Superseded qualification rows appeared as current | Real qualification screen; `[data-testid=qual-cell]` and candidate header totals; 18 rows for a 9-requirement contract | Major: wrong current assessment could be read | MERGE-15 pins exactly the snapshot's qualification IDs, including pagination; unit and real persisted/browser assertions |
| Elevation range mixed metres and kilometres | `S05-1440-light-default.png`; `.planetary-interpretation .legend .quantity`; 2500–2874 m appeared as “2,500–3 km” | Major scientific display error | MERGE-21 formats both endpoints in the same unit and precision; exact red/green regression and fresh real screenshot |
| Prepared terrain image was absent | `S05-1440-light-default.png` and `S06-1440-light-default.png`; `[data-testid=planetary-panel] svg image` and `.earth-map-panel`; published PNG requests returned 404 | Major: missing scientific display | MERGE-22 authorizes only workspace-published PNGs with registered metadata; real images, MIME, bytes and dimensions tested; private and foreign access remain denied |
| Actual timestamp exceeded its operations column | `operations-drawer-1440-dark-default.png`; `.drawer-bottom .timeline time`; one cause produced 816 repeated C05 findings | Major overflow in a high-use operations view | MERGE-23 displays UTC seconds, keeping original microseconds/offset in semantic attributes |
| Landing table moved as detail queries completed | `S01-390-dark-default.png`, `S01-1440-dark-default.png`; `.workspace-table-slot`, `.table-overflow-hint`; measured CLS up to 0.079 | Major against the unchanged 0.02 gate | MERGE-24 reserves column/row geometry and gives the native scroll region stable instructions; focused real 12-cohort check passed |
| Full manifest appeared after the first printed page | Real passport PDF and C17 bounds; `[data-testid=manifest-digest]` at y=9554; footer held a prefix only | Major provenance placement defect | MERGE-25 moves the existing full digest before the assurance block; final33-page PDF verified below |
| A successful stream appeared as a failed request | Real audit transport finding on `/runs/{id}/events`; terminal SSE response | Operational reliability defect | MERGE-26 consumes terminal EOF instead of aborting a successful response; red/green protocol regression; final C12 check passed; see MERGE-29 and out/stream-audit.json |

The original audit failure had 827 findings, not 827 independent defects: 816 were the same timestamp overflow repeated across cohorts and rows, nine were landing-page layout shifts, and one each concerned print placement and terminal stream closure. Thresholds were unchanged. MERGE-29 subsequently improved terminal-stream classification with unique request identity, complete contiguous protocol, correct run/workspace, terminal state and an independently observed exact final cursor within that response lifetime. Eight positive/negative tests and an actual unexpected-abort negative control preserve C12 failure detection; this is not a blanket SSE exception.

## Review method and interpretation

- Compare S01–S12 at desktop and narrow widths in dark and light themes. Inspect the qualification matrix, route attempts, provenance disclosures, controls and drawers at their focused/expanded positions, rather than scoring only the top of each route.
- Check that candidate screening order is labelled as screening, native support and missing evidence remain visible, and result state is separate from workflow state and publication permission.
- Inspect the printed pages for bounds, complete tables, mode, headline, full manifest, running references and page numbers. A shortened footer reference does not substitute for the full first-page digest.
- Use the automatic font, contrast, geometry, focus, glyph, numeric, print, production and locked-threshold checks as evidence alongside the images; a mock-only pass cannot establish the real-data result.

Minor usability observations to retain in the handoff: some compatibility dimensions expose precise backend metric identifiers; the printed route diagram becomes dense with many labelled samples. The corresponding definitions, numeric samples, receipts and full identifiers remain available. These do not alter a result or hide missing evidence. They cap the copy/density/chart scores rather than being reported as absent.

## Final rubric

Single reviewer scores,0–4, minimum3 and mean3.75. These apply to the declared local/generated-data demonstration. There is no claim of three independent reviewers.

| Criterion | Score | Specific evidence / limitation |
|---|---:|---|
| hierarchy | 4 | S07-1440-dark-default.png; S11-390-light-default.png; .run-shell-header separates lifecycle from latest modeled test; immutable attempt history remains below |
| restraint | 4 | S01–S12 light/dark; state badges use word+glyph+border; neutral panels and a single blue primary action per active region |
| typography | 4 | S03-1440-light-default.png; S07-1440-dark-default.png; numeric columns and units, locally bundled type, stable table styles; audit font/contrast/geometry checks pass |
| density_spacing | 3 | S07-1440-light-default.png; S12-390-dark-default.png; dense qualification/passport content uses labelled scrolling and disclosure. Printed route labels remain compact; numeric sample table follows |
| tables | 4 | S05-390-light-default.png; S07-1440-dark-default.png; S10-1440-light-default.png; right-aligned values, unit headers, current qualification rows only, labelled native scrolling |
| states | 4 | S09-1440-dark-default.png empty portfolio; S10 PROVEIT pending/disabled; S11 completed attempts. Full501frame catalog covers loading/error/disabled and their explanations |
| copy | 3 | S08-390-light-default.png .compatibility-panel retains technical metric IDs; definitions/provenance explain them. Other primary copy distinguishes screening, Unknown, modeled verification and physical limits |
| consistency | 4 | S01–S12 desktop/narrow, light/dark; same controls, tables, spacing and status vocabulary; styleguide all3densities regenerated |
| map_chart_integrity | 3 | S05-1440-light-default.png histogram units/support and uniform elevation legend; S06 candidate geometry explicitly labelled offline/synthetic.33page print route is dense, with committed numeric samples retained |
| accessibility | 4 | J09 narrow/keyboard/zoom; audited focus/help/textspacing/reducedmotion/glyphsilhouettes/contrast. Boththemes501frames0findings; manual narrow-tab navigation reaches passport and downloads |
| credibility | 4 | S12-1440-light-default.png; printedpage1 synthetic/LIMITED/fullmanifest. Scientific Unknown/GAP and native support remain visible; credibility applies to an engineering demonstration, not NASA endorsement or physical certification |
| slop_absence | 4 | S01–S12 and styleguide; neutral engineering surfaces, no promotional decoration/emoji/gradient, no nonlocal font/image requests; forbidden-pattern and production checks pass |

## Own checklist

All ten answers are yes within the demonstrated engineering-tool scope:

1. **Status first:** lifecycle and latest modeled test occupy the run header; completion does not erase failed attempts (S11/S12).
2. **Greyscale distinction:** word, unique glyph and border distinguish the six states; the audit checks silhouettes as well as glyph identity.
3. **Numbers and units:** quantitative columns align right with tabular numerals; headers carry units; Unknown remains explicit (S05/S07/S10).
4. **Table consistency:** candidate, qualification, benchmark and operations tables share header/row treatment and labelled scrolling.
5. **Primary action:** authoring, portfolio and test-lab each expose one primary action for their current region; completed PROVEIT explains why it is disabled.
6. **Designed states:** empty portfolio, pending test, loading, cancellation and actionable failures explain the state; current audit covers the additional catalog states.
7. **Plain copy:** primary instructions are precise and avoid hype. Technical compatibility metric identifiers retain definitions/provenance and are recorded as a minor usability limitation.
8. **Spacing/alignment:** final geometry, textspacing and responsive audits pass; no page overflow or interactive overlap. Intentional table scrolling is labelled.
9. **Themes/print:** both themes use the same hierarchy; printed light-token passport has full provenance onpage1 and sequential page numbers on all33pages.
10. **Presentable engineering demonstration:** yes, with synthetic/TEST_HARNESS, modeled support, Unknown/GAP and LIMITED disclosures. No NASA approval, real-source validation or physical readiness claim is implied.

## Final evidence

- Real audit:501frames,0findings,0skips; `out/visual-real.json` records the manifest hash and local archive.
- Preview audit:501frames,0findings,0skips; `out/visual-mock.json` records component provenance and local archive.
- Print:33pages inspected via6contact sheets plus enlargedpage1,0out-of-page words, complete tables continue across pages. Mode, exact headline and full64-character manifest appear onpage1 (`out/print-review.json`).
- Hands-on J01: fresh committed checkout, actual ARES-1 import, frozen contract, FAIL/A → FAIL/A → PASS/B,54current qualification cells, committed playback and3UI downloads independently byte/hash-checked against API (`out/manual-journey.json`).
- Final rubric and minor observations: `out/design-scores.json`. All major defects listed above were repaired and rechecked; no remaining blocker or major was observed within this inspection scope.

Final source follow-up: MERGE-31 fixed a real blank saved-rover label after the library exceeded25records. The unchanged red UI assertion now passes; later-page, cursor, cancellation propagation, cycle and failure tests were added. Both real J09 keyboard/zoom paths pass on the existing larger library. Authoring/library, qualification and passport screenshots were rechecked in both themes at1440and390; all33new PDF pages were inspected. The complete current real501-check audit passes with0findings/0skips. The final preview suite passes all41cases. Its report accumulates120focused visual checks plus the full501-record catalog,621total, with0findings/0skips. The last501check signatures match the full real catalog exactly. All623preview manifest entries and504real entries match their actual PNG hashes.
