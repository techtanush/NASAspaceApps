# Aradhya frontend handoff

## Current acceptance — round11

Application source `adb076e99103a3a42fa77c0a823826075a60a997` on `aradhya/frontend-experience` passes the requested frontend visual-acceptance gate. Main is unchanged; no deployment or backend integration was performed.

- Complete visual audit: 501 reports, 0 findings, 0 skipped checks. Frozen review packet: 568 images, 502 reports including pagination proof, 16 PDF pages and 48 faithful detail crops.
- Three fresh independent reviews: HMI 3.6667, accessibility 3.6667, slop 3.5833. Every criterion >=3; every mean >=3.5; no confirmed open prohibited findings. Exact prompts and reports are preserved verbatim in DESIGN-REVIEW.md.
- All 41 distinct browser cases verified: complete visual audit, 39 passing regression cases and corrected J02 rerun. Initial J02 failed because its selector expected a raw visible identifier; updated test locates the retained ID in details and asserts the readable label, preserving every numerical/persisted oracle assertion. No cases skipped or reported flaky; the initial failed batch is preserved. Current 90 frontend unit tests in 22 files, TypeScript, ESLint and production build pass.
- Frozen-kit, ownership, prohibited-pattern scan, 150/150 tokens and byte identity of supplied token assets/generated CSS pass. Twelve complete native-resolution component-guide images are updated.

Readable benchmark/rule/metric names retain exact original identifiers, operators and accepted wording in details. The evidence now includes actual rover parsing/validation errors and valid-import results, below-fold acceptance/hash controls, the complete target chart and data, later attempts, replanning/playback, and actual HTML/JSON/CSV export statuses. Packet: `analogforge/out/visual-review11-complete/screens.md`.

Minor, nonblocking polish findings remain recorded: print Reserve label/value pagination, a footer-only final print sheet, a screen scroll hint in print, target-scale label proximity and practice launcher density. The passing review is not a claim that all polish issues are eliminated.

Real-backend MRG-03 remains BLOCKED_ENVIRONMENT and belongs to the merging agent. Synthetic preview/fixture evidence verifies frontend presentation and contract behavior, not live terrain/model access or physical rover execution. The 131 Python tests, 36 mutations and 27 export/27 tamper checks below are historical 4c801f4 baseline evidence, not reruns of this presentation follow-up.

## Historical verification and follow-ups

The following prior notes are preserved as history; their older scores/counts/readiness do not describe the current accepted source.

Application source `4c801f40ca86751fc16f0557d14bd0d160892a34` on `aradhya/frontend-experience` builds and passes functional verification. Independent visual acceptance remains failed, so `ready_to_merge` is false.

Verified on the final application source:

- 33 browser tests pass, with zero failures, skips or flaky results. This includes J01–J13, reload/reconnect recovery, keyboard use, 200% reflow, declared unknown rover values, scientific display, rapid worker reloads, and WebGL-disabled exports.
- 84 frontend tests in 19 files and 131 Python kit/renderer/contract tests pass.
- TypeScript, ESLint, Ruff and strict mypy pass. Production builds reject mock mode and exclude the mock worker and component guide.
- All 36 required mutations are detected by their intended assertions. Export verification accepts 27 files and rejects 27 tampered files.
- The automated visual report has 407 reports and 409 screenshots with zero findings or skipped checks. Direct text-range assertions now protect matrix value ownership and Run context under expanded spacing.
- Frozen-kit verification, branch ownership and all 150 token checks pass. The supplied contract/design assets remain unchanged.

The branch implements S01–S12, authenticated workspace bootstrap, typed API transport, revision-safe commands, SSE recovery/replay, a persistent synthetic preview, Earth/planetary displays and the pure Python passport renderer. Development exports call that renderer. The preview worker survives document replacement without an unregister/update race. Selecting Known for an absent optional measurement never inserts zero. Saved times come from the API; absent actor/duration information remains Unknown.

Three fresh image reviewers inspected the exact final captures. Their means were HMI 3.333, accessibility 3.167 and slop 3.167, below the required 3.5. Remaining findings concern mobile density, caption/table presentation and other visual details. All six rounds are preserved verbatim in DESIGN-REVIEW.md; no pass is inferred from automated checks.

The component guide has 12 native-resolution images, two contiguous parts per theme/density with 48 px overlap. The largest is 283,202 bytes; together they show the complete guides. Other screenshots and reports remain under analogforge/out and are excluded from Git.

Original-workspace dependencies are restored. The final checks use Node 22.21.1, pnpm 10.22.0, Python 3.12.13 and matching Playwright Chromium. No other owner's implementation or frozen architecture/kit files were changed. Main was not modified.

Real-backend MRG-03 validation remains the merging agent's integration gate. The synthetic preview and fixture exports establish frontend/contract behavior, not live terrain, model access, physical rover validation or production readiness.

## Requested three-layout follow-up

Source `8ca8769` addresses the three explicitly requested issues. The phone shell folds metadata/actions/workspace links into Run context, removes duplicate view naming, uses a single44px operations row and fills the available viewport. At390px the focused test requires two complete candidate and matrix rows and an initially visible PROVE IT. Captions sit outside horizontal data scrolling and remain readable under expanded text spacing at375,390 and768px. Passport requirements now top-align with their first candidate result and use compact candidate subrows.

TypeScript, ESLint, production build and84 frontend tests pass. The selected browser batch passed10 of11 cases; the zoom case hit a native filechooser timeout. Its manually created browser tab now explicitly owns focus before keyboard interaction, and the unchanged keyboard/zoom assertions pass three consecutive repetitions. The scoped mobile, caption, passport, accessibility, export, print and WebGL checks pass. All12 component-guide images were refreshed. Logs and screenshots are under out/three-layouts-* and out/visual.

The prior complete visual baseline is retained under out/visual-before-three-layout-fixes. This follow-up does not claim a new full visual review, resolution of other findings, or real-backend verification. Overall merge readiness remains false.


## Candidate readability, loading rows and preset follow-up

Source35077fb keeps the desktop40/60 list/map split and makes Origin/Window visible inside each candidate row without horizontal scrolling. Bounds/access remain in the row disclosure. Both pending workspace tables reserve four complete skeleton rows across both themes, three densities and phone/desktop widths; loaded tables release the extra reservation. Practice links wrap in a compact desktop panel and use a collapsed phone disclosure.

Verified84 frontend unit tests, TypeScript, ESLint, production build, ownership and forbidden scan. All4 selected browser cases pass, including keyboard/200% zoom and the previous mobile/caption/passport regression. The focused visual report has22 reports and zero findings. Evidence: analogforge/out/list-loading-presets-* and out/visual. This is scoped verification, not a new full audit or independent rubric review. Overall merge readiness remains false; main is untouched.


## Operations rows and chart descriptions

Source bb6af30 compacts committed events while retaining full UTC timestamps, explicit unknown actors and all evidence/details. Visible chart summaries describe supplied patterns and preserve missing-data limits; the SVG references the same prose. The alleged compact first-tick displacement was not reproduced in the saved screenshot or all six live theme/density cohorts; geometry was left unchanged. All12 native component-guide images were refreshed.

Verified87 frontend tests, TypeScript, ESLint, production build, forbidden scan and ownership. All3 selected browser cases pass: component/shell smoke (including all6 histogram alignment cohorts), compact drawer behavior, and candidate/loading/preset regressions. Focused visual report: 25 reports, zero findings. The first smoke attempt exposed a previous homepage CLS regression when the pending height collapsed; stable table reservation fixes it, and the unchanged smoke assertions pass. Evidence is under analogforge/out/operations-charts-*. No new full audit, independent rubric acceptance or real-backend validation is claimed. Overall merge readiness remains false.


## Empty tables, rover labels and benchmark wording

Application source ed7ab5b removes horizontal-scroll prompts from empty/skeleton-only tables while retaining them for actual overflowing data. Rover list-field labels use sentence case and separately associated comma-entry hints. Benchmarks use readable names/comparison phrases, with original requirement IDs/operators/observables and accepted wording in Rule details. Both interval limits remain visible for BETWEEN rules.

Verified87 frontend tests, TypeScript, ESLint, production build, ownership and forbidden scan. Four distinct browser cases verified: component/shell smoke, empty/loading/populated table behavior, rover editing/saved list arrays, and mobile benchmark details plus existing layout/passport checks. The first mobile assertion incorrectly expected a standalone text node despite its contextual slope-band helper;8bce5d3 scopes the phrase check to the rule cell, and the complete mobile case passes. Logs: analogforge/out/table-labels-*. Full visual audit, independent rubric acceptance and real-backend validation were not rerun; overall merge readiness remains false.
