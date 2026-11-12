# Implementation decisions

- Development mock previews use Vite mode `mock` on the dev server; every build rejects VITE_API_MOCK=1. The visual audit uses this explicitly bannered dev server because a production mock build conflicts with UIX-10. No runtime fallback.
- Renderer CSV evaluation_stage stays empty where the frozen QualificationDimension has no such field; no inference from prose.

- Frozen kit import itself loads `socket` via Pydantic typed schema internals. Renderer purity tests compare imports against a preloaded kit baseline and prohibit any additional network/DB/model imports, environment reads, or file writes.
- Supplied token verification/generator scripts must remain byte-identical. An owned nested Ruff config excludes only those upstream copies from style lint; authored scripts retain all project lint rules.

- Production audit distinguishes non-fetching XML/JSON-Schema identifiers and dependency documentation literals from resource URLs. Their explicit prefixes are classified in `out/production-audit.json`; HTML/CSS resources must remain local, browser requests must remain on the app origin. Production omits the development service worker entirely, including public-directory copies.

- The frozen kit ignore file omits `out/`, while the gates generate reports there and forbid committing build output. A workspace postinstall adds only `/analogforge/out/` to local `.git/info/exclude` so clean clones pass ownership checks after verification without changing the kit or tracking reports.

- Authentication is bootstrapped from the server’s `/auth/session` before any workspace query or mutation. The session adapter accepts `workspace_id` or `workspace.id`, and primary `csrf_token` plus compatible `csrfToken` spelling because architecture24 defines semantics without a frozen auth-response schema. Conflicting aliases/invalid IDs fail; no fixed workspace UUID is used by real startup.

- Layout-shift cohorts measure real reload/data-arrival at each required viewport/theme/density before audit-induced focus, resize, theme, or text-spacing changes. C12 records cancellations separately only when the test observes the actual AbortSignal or explicitly initiates a navigation; other failed requests remain failures. This reconciles required request-abort cleanup with the audit’s no-transport-failures rule.

- Overlay audit states (`Evidence-open-*`, `Operations-open-*`, `Shortcuts-open-*`) preserve the open dialog and measure its controls. C05 compares controls within the same overlay layer, since an intentionally layered drawer necessarily covers the underlying workspace; C07 walks the open overlay until focus leaves it. Ordinary screen cohorts still inspect the entire workspace. Drawer focus-out and Escape behavior are tested separately. Text and contrast checks continue across the visible document.

- The forbidden scanner includes authored audit/export scripts. It excludes only its own detection-pattern definitions and the three mutation catalogs, which necessarily contain intentionally prohibited source strings; the unmodified acceptance tests still execute against every injected mutant.

- Contract fixture exporters use a deterministic UUID sequence scoped to their Vitest tests. They still invoke the actual mock handlers and validate actual responses, but repeated test runs no longer rewrite tracked fixtures with random identifiers. Two consecutive exports were byte-identical; browser command IDs retain real random UUIDs.

- The audit waits for a drawer's actual close and focus lifecycle to finish before reopening it for the next viewport/theme. It does not force DOM visibility or suppress failures. Read-only geometry is cached within each synchronous audit measurement; all element pairs, thresholds and contrast checks remain unchanged.
- Run preparation increments its durable stage before emitting the state event, so a saved awaiting-review checkpoint cannot repeat its last preparation step on reload. The regression fails against the old order and passes against the corrected order.
- Compatibility numeric columns use structured ASSESS_COMPATIBILITY evidence. Absent numeric fields remain Unknown; explanatory prose is not parsed into invented values.

- Canvas contrast samples apply only to text whose painted bounds survive ancestor clipping and whose nearest opaque backing surface contains the canvas. Clipped candidate-list text and opaque operations-footer text are checked against their actual backing surface, rather than unrelated map pixels. Diagnostic findings retain text, geometry and sampled pixels. Contrast thresholds remain4.5/3. Cold-load headings allow60seconds for service-worker startup; CLS and request-failure limits are unchanged.

- The768–1023px investigation uses a bounded four-row layout, like desktop, to keep the operations footer stable while passport data arrives; the working evidence pane scrolls. Mobile remains in document flow. Focused actual-data audits measured passport CLS about0.00033 in both themes (limit0.02). Workspace run links use inline-flex32px targets and44px for touch/390px.
- Main-frame navigation requests mark existing in-flight requests as intentional navigation cancellations. This covers explicit page.goto as well as cold reloads; unclassified aborts remain C12 failures.

- Job SUCCEEDED is not the complete authoring readiness boundary: the client still retrieves the proposed contract and header. Scenario/mode selectors are disabled while that operation is busy, with an associated explanation. The journey waits until the proposal can actually be accepted before opening those menus. A held contract response reproduces the gap under300ms latency. Pointer focus also no longer invokes keyboard-only reveal scrolling.

- Round1 independent design review rejected the initially automated-green UI. Revised presentation separates server lifecycle/scientific outcome, displays declared compatibility operands and explicit accepted ranges without computing a scientific aggregate, keeps origins/status counts in matrix summaries, and compacts mobile chrome. Narrow matrix view initially uses candidate rows; both orientations remain available. All underlying scientific records/history remain available.
- Every query chain and prepared-image effect now propagates AbortSignal, so navigation/unmount cancels evidence/artifact/result reads instead of letting stale work issue late requests. Mobile uses the same bounded work-area/operations-footer layout as larger screens, preventing passport arrival from moving the footer.
- Coordinate display uses five-decimal magnitude plus hemisphere (the architecture example convention), avoiding a double negative on W/S; signed source geometry remains unchanged in API/export data. Categorical chart CSS values are read directly from the supplied token JSON because the byte-identical upstream generator omits those variables. No palette value or generator was modified.
- The focus audit tracks actual element identity with a WeakMap rather than treating repeated identical HTML as a completed Tab cycle. Print geometry is measured after resetting screen scroll positions, so first-page bounds are independent of the last keyboard focus position. Thresholds remain frozen.

- Nonmodal evidence and operations drawers persist during both pointer and keyboard interaction outside them. Close and Escape are the explicit dismissal actions and restore focus to the opener, unless another dialog owns focus. This avoids focus-only dismissal during cross-drawer work and makes outside-pointer/focus behavior consistent. The browser regression asserts persistence, explicit dismissal, focus return and reopening at six widths.

- Round2 image review exposed two scientific display defects beyond automated layout checks. Unequal-width slope intervals are shown as categorical bins; accepted reference limits now use the same band projection, including within-bin interpolation. They are not projected on an unrelated linear degree axis. Numeric labels reserve their own annotation lane. Source histogram values remain unchanged. A renderer unit regression and actual-browser regression check12/18degree boundaries against their corresponding bars.
- Whole-metre display precision from architecture41 §8 is unsuitable for submeter rover geometry: a declared0.20m must not display0m. Values below1m retain2–3significant digits; other units also avoid rounding a nonzero value to zero. This is a display-only precision exception; persisted numbers and server decisions are unchanged.
- Candidate columns retain rank/name/status/selection/origin/window, ordered so the initial40%list pane shows rank/name/status/selection. Verbose origin and bounds expand in their existing provenance columns. The60%map allocation is retained. Tablet context uses the prescribed48pxnav rail; smaller run context moves mission title and secondary result annotation into an expandable summary while lifecycle/outcome/mode stay visible.
- Workspace tables reserve176px for stable300msquery arrival, with internal scrolling, instead of leaving288pxempty slots. This reclaims vertical space without reintroducing data-arrival CLS. Completed test labs collapse accepted benchmark details and retain immutable attempts. FileDrop keeps its genuine visible/keyboard-operable input with custom tokenized action text and one metadata row; no native filename/button chrome leaks through.

- C05 now measures every SVG text element using transformed glyph bounds against its owning SVG viewport, with the same1pxclipping tolerance. Chromium reportedscrollWidth162/clientWidth149 for fully enclosed glyphs, unchanged even after rescaling the SVG. HTML text retains the original scrollWidth/clientWidth test; no selector allow-list or threshold changed. A wide-styleguide baseline and deliberately moved glyph establish that actual SVG overhang is still rejected (out/svg-glyph-check.log). Chart figures stop enlarging beyond720px; the smoke check now includes1920px in addition to1440/390.

- Round4 compacts closed matrix cells while retaining status, numeric value, support and stage; nonzero state counts remain visible and all six exact counts expand. Requirement definitions remain available by disclosure. Mobile navigation exposes explicit scrolling controls, a complete current-view label and whole-label pages; workspace links use concise visible names with complete accessible names. Compact pinned identity remains visible.
- Placeholder contrast is now measured explicitly by C03, using placeholder color, opacity and effective background. Checkbox appearance uses shared tokens. Connection variants have distinct neutral shapes. Numeric editors normalize only outside active editing and retain the labelled unit without SI conversion.
- Test-lab action uses a portal into the persistent run action bar after the benchmark preview in DOM order; scientific commands and enabled conditions are unchanged. Passport limitations precede the digest onscreen; print orders its compact digest onto the first page. Mobile evidence uses a full-width bottom sheet and prioritizes receipt metrics/limitations before verbose provenance.
- ENOSPC interrupted the targeted layout probe. Superseded Round1/Round2 PNG outputs were removed to recover space; their reports/manifests and the latest Round3 review images remain. No source or dependencies were removed.

## Final acceptance synchronization and disclosure sizing

Source b96462a waits for the accepted-contract acknowledgement before a journey helper returns and reserves a 72px matrix disclosure column. The production command already awaited acknowledgement. J12 passed three repetitions and the disclosure passed 13 focused visual cohorts with zero findings. The full visual audit remains required; focused checks do not establish UIX-13. A later full run encountered a service-worker update registration error despite the worker returning HTTP200; it was interrupted and restarted with CI=1 to ensure a fresh owned server. Low free disk space is an observed environment constraint, not a waived assertion. Only regenerable package/HTTP caches were removed; source, installed dependencies, user history and active application updates were preserved.

The fresh-server run reproduced the worker update error, ruling out reuse as the sufficient explanation. The worker URL continued to serve HTTP200. A focused 16-navigation retention probe is checking the registration after reclaiming inactive Clang module and Blender shader caches; no application/project files or Blender outputs were removed. Free space rose from about0.85GiB to1.9GiB.

## Round5 concrete screen anatomy and preview lifecycle

Round4 met every individual score floor but not the required mean. The fixes preserve S03 three-column fields and S06 map60/list40, complete the prescribed side summary/import and home table fields, place the sole PROVE IT inside its experiment panel, display input suffixes and explicit Known/Unknown choices, synchronize visible mobile tabs, expose claim/linked-requirement receipt sections and actor-unknown event metadata, and complete the component specimens. Selecting Known never inserts a measurement: an empty declared value blocks save until entered or changed back to Unknown. Mission timestamps come from saved MissionDraft.created_at, not the local clock. Run duration and actor identity are absent from the frozen models and are displayed as Unknown rather than guessed.

The repeated worker update failure was traced to the generated CLIENT_CLOSED handler unregistering a worker concurrently with the next document update. Cache reclamation alone did not resolve it. The local development-worker patch retains an inactive registration, while the pre-existing zero-client bypass remains. A rapid16-navigation browser regression checks page errors and session transport. No error is suppressed or allowed.

The screenshot guide permits up to12 files at400KB each. Complete guides now use two native-resolution Playwright captures per theme/density, with48px overlap, rather than shrinking content or omitting states. Their combined coverage is the complete page; screenshot sizes and coordinates are recorded in the manifest. The rubric criteria, audit thresholds and supplied tokens remain unchanged. The audit preserves the application-selected horizontal navigation position instead of resetting it to Mission before capture; data-table scroll positions still reset for canonical comparisons.

## Round6 text ownership and canonical capture state

Source4c801f4 adds direct C05 glyph-range containment checks for matrix values and Run context, in addition to existing box-overflow checks. Matrix values wrap within their own columns and the context label has its own line under expanded text spacing. Every capture restores the selected navigation tab after the previous keyboard walk, preventing a prospective Passport destination from appearing as current in the next light-theme frame. An additional permanent browser regression exercises text ownership, active navigation and five-decimal coordinates.

Area fractions are converted only for percentage display; underlying API values and exports remain unchanged. The component guide reads its scientific ramp from the same prepared fixture manifest used by the target raster, independent of theme. Candidate names accompany immutable IDs on the passport, raw assurance scope/validation wording stays available in provenance, PROVE IT retains48px height, and mobile compatibility exposes the existing per-dimension server statuses before the comparison table. No new qualification or scientific verdict is calculated. The alleged sixth decimal was not reproduced: actual DOM text passes the exact5-decimal/not6-decimal assertion.

## Verified delivery boundary

The final source passes build, all33 browser tests,84 frontend tests,131 Python tests,36 mutations and the automated visual checks. The six-round independent visual record does not meet the rubric; DR-02/DR-03 remain failed and ready_to_merge remains false. No threshold, score or remaining finding was waived or relabeled as passed. The handoff retains both the working functional result and the remaining visual/integration boundaries.

## Three-layout scope

The user explicitly selected mobile work area, matrix caption and passport association. Only these layouts, the shared caption primitive, and focused regression coverage were changed. Native table captions remain available to assistive technology; a wrapping visible caption labels the independently scrolling data region. The phone shell uses the actual remaining flex viewport rather than a hard-coded header offset. Ancillary metadata/cursor/actions and workspace links remain reachable in context; 44px touch targets remain. Passport row groups preserve every assessment and immutable identifier. An explicit browser-tab focus assertion stabilizes native keyboard file selection in the separate zoom context; no functional assertion or timeout was weakened.


## Candidate metadata and workspace compactness

Move origin/window from horizontal columns into always-visible row metadata while retaining screening rank/status, map key, actual server values and selection acknowledgement. Keep the prescribed desktop40/60 split. Reserve loading height only while requests are pending, then release unused space. Presets retain every scenario link and use native responsive disclosure. The focused browser assertions cover four-row containment, metadata text containment, split ratio, preset toggling and selection, alongside the previous mobile layout and keyboard/zoom checks. No scientific verdict or API contract changed.


## Compact events and data-derived chart prose

Use aligned sequence/time/actor/summary rows and native details for less frequently needed event type/state/evidence. Preserve complete timestamps and explicit missing actor identity. Chart prose is derived solely from supplied plotted values and units; unknown bins block a continuous-trend assertion. Associate the SVG with the visible description. Verify screenshot allegations before changing geometry: no A-specific compact tick defect was reproduced, so scales and anchors are unchanged. Stable workspace table reservation corrects the prior loading-to-empty CLS regression discovered by the smoke test.


## Empty-table and rule wording scope

Show the shared horizontal-scroll prompt only when the table both overflows and contains a substantive body row; aria-hidden loading placeholders are not data. Keep populated unknown-value rows inspectable. Retain captions, headers and keyboard scrolling. Rover list-field names use sentence case and comma-entry guidance moves to associated helper text, preserving the existing parser and saved arrays. Frozen benchmark rows use readable observable names and operator phrases; Rule details retains the exact requirement ID, operator, observable, accepted wording and note. Range limits display both bounds and nonnumeric rules are explicit. No contract data or comparison logic changes.


## Fresh visual acceptance evidence

Application source8d3c284 shares readable requirement/operator names across frozen benchmark previews, mission contracts and attempt results. Exact requirement, observable, constraint and metric identifiers and supplied raw rules remain in native details. Only display wording changes; supplied values, accepted limits, outcomes and API payloads are unchanged.

The full audit retains its complete canonical screen/viewport/theme/density checks and locked thresholds. Supplemental frames scroll the actual UI to below-fold anchors and record the anchor in the manifest/catalog. They cover contract digest/acceptance, target chart/description/data and horizontal extent, each attempt, replanning, playback geometry/controls/readouts/samples, passport manifest/export controls/completed exports, invalid JSON, negative-mass validation and successful import preview. Downloads are real mock renderer responses, not screenshots used as proof of real-backend integration.

A supplemental preflight detected four C05 overlap findings when center-scrolling deep playback samples also moved ancestor containers. Native nearest scrolling reveals the requested content without unnecessarily recentering every ancestor; the unchanged C05 checks pass in the repeated1440/390 dark/light case. No selector allow-list or threshold changed.

A stable288px workspace reservation replaces384px. All four loading rows fit at1440/390 in both themes and all three densities, and the unchanged CLS smoke checks pass. This removes96px of unused reservation while keeping data arrival stable. Real-backend MRG-03 remains the merging agent's work. Fresh reviewer reports are recorded verbatim after the complete audit.


## Printed page numbering found during image review

Rendering the actual print artifact exposed a body pseudo-element that printed page0 at the end. The previous automated print check covered mode/headline/digest placement and width, not real pagination; its passing result did not establish correct page numbers. Source3f1da3c removes that pseudo-element and uses native @page bottom-center page/pages counters. The mobile layout/print regression passes, and extracted text from all12 pages confirms one matching pageNof12 footer per page; the first rendered page was inspected. The full audit was restarted on the corrected source. PDF-review tooling is isolated under out and does not change runtime dependencies.


## Complete audit findings and measured corrections

The complete3f1da3c run produced497 reports and16 findings: four below-fold contract C05 header/control overlaps and12 S06 C11 shifts across1280/390 theme/density cohorts. It remains preserved as a failed run; no acceptance is claimed for it.

Source3e17e2b lets non-run authoring headers scroll with their long pages rather than cover other controls. The eight focused scroll/keyboard frames pass C05/C07. Run headers retain their existing sticky treatment. Candidate identities reserve72px for rank and84px for screening status. Before reservation, Unknown-to-rank shrank about42px and changed flex wrapping; the full report recorded CLS up to0.066. After reservation all12 focused load cohorts measure CLS0.000, retain40/60 and two complete mobile rows, and have zero findings. Real held/released screening evidence under expanded text spacing measures Unknown68.984px and Shortlisted83.172px; both now fit their slots. Permanent regressions cover the measured failures. No threshold or skip changed.


## Round7 reviewer findings drive Round8 presentation fixes

Independent Round7 reports are retained verbatim; no score is rewritten. The chart wrapper now has a real available-width/min-width contract so prose wraps while only the SVG scrolls. C05 additionally checks narrative glyph containment in the visible chart frame; this strengthens the existing check. A dedicated390/1440 dark/light spacing regression passes.

Attempt benchmarks reserve a readable text column on phones, use signed margins, readable metric aliases and deduplicated explanations. Raw identifiers, rules and diagnostics remain in details. Replanning shows Before/After parsed only from supplied change records, with explicit missing-data wording if no structured comparison exists. Print expands substantive disclosures and restores their screen states, shows actual run/contract/rover/UTC metadata and per-candidate supplied measurement/support/evidence, and associates every numbered page with a defined manifest prefix. Static export hashes print only when actually available; other states remain explicit. No API data, scientific verdict or accepted operand is recomputed.

The21-page focused print probe confirms expanded provenance/assumptions, actual measurements, static header metadata, matching numbered/digest footers and an Attempts heading sharing its page with Attempt1. New print-only formatting avoids hidden frozen hooks; the original visibility assertions remain intact. The golden export journey and mobile/layout probes pass after that correction. Fresh complete audit and new independent reviewers remain required.


## November11 review: receipt identity and precompiled audit validation

Mission editors are keyed by workspace and mission identity. Existing drafts remain behind a loading/retry boundary until all saved inputs arrive. Draft-version guards prevent old preparation/acceptance receipts from reappearing after an edit; a completed save schedules any newer waiting edit. Candidate URL writes also compare the current browser URL with the issuing URL, because navigation intent can reach browser history before React's passive unmount cleanup runs.

The frozen assurance schema generates standalone validation functions. Only the small AJV Unicode-length and format helpers ship to the browser; runtime schema compilation and code-string evaluation are unnecessary. The build checks generated-validator freshness. Passport display requires matching run/workspace/mode and accepted mission/rover identity; scientific decisions and canonical-manifest hashes remain backend-owned.

Mutation isolation now requires a passing unchanged unit/browser control and a unique Vite configuration anchor. The isolated server uses port5178 consistently for its process, browser origin and readiness check, preserving access to symlinked local font dependencies. Infrastructure failures cannot certify deliberate regression detection.

The user's no-subagents instruction controls this review's method. Prior independent design panels remain historical baseline evidence; the new authoring refinements receive single-agent image inspection and current automated visual/accessibility checks. No new independent panel or scores are claimed. See review-2026-11-11/REVIEW.md and RESULTS.json for source and evidence.

## D-2026-11-12-C12 — Chromium GPU-driver diagnostics are not application console output (independent review)
In a GPU-less container Chromium (a) warned that automatic software-WebGL fallback is deprecated and (b) with the opt-in flag it requests (`--enable-unsafe-swiftshader`, now in `playwright.config.ts`) emits `[.WebGL-0x…]GL Driver Message (… ) GPU stall due to ReadPixels` when a canvas pixel readback happens; the readback is the audit's own C08 glyph-raster check. Both are browser-process diagnostics, so the C12 console check now ignores exactly the regular expression `^\[\.WebGL-0x[0-9a-f]+\]GL Driver Message \(` (tests/e2e/visual-audit.spec.ts). Every other console error/warning, page error and failed request still fails C12. Evidence: full audit run 2026-11-12 — 78 and then 4 findings, all of these two messages, 0 application findings.
