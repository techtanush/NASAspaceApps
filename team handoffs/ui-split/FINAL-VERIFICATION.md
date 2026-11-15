# Integrated release verification

This record separates software checks, genuine data observations and remaining limits. The integration branch contains Tanush, Aradhya, Ayan, BETTERUI and premium-glass ancestry. PR #3 is the release boundary; consult its final head/merge metadata rather than interpreting a combined local branch as a merge into main.

## Software verification

| Check | Observed result | Local receipt |
| --- | --- | --- |
| Final complete merged gate | PASS: kit 20; platform 1,221; science/renderer/UI contracts 1,290; frontend 311; client contracts 3; docs, Ruff, mypy (266 files), build, scans, wire, purity and synthetic preflight | `analogforge/out/final-make-check-r86.log` |
| Platform recheck after prefilled contract context | 1,194 passed | `analogforge/out/final-platform-r61.log` |
| R79 platform sweep / corrected R86 sweep | 1,215 passed; one opt-in-default assertion failed because the browser profile forced visualization on. The same assertion passed with the proper default flag in R84. The corrected R86 full backend sweep passed all 1,221 checks; the rest of the complete gate passed too (exit 0). | `analogforge/out/final-platform-r79.log`, `final-config-hash-r84.log`, `final-make-check-r86.log` |
| Final entire frontend | 311 passed; lint, typecheck and production build pass, including live-update map preservation, concise/exact chart modes and visible assurance | `analogforge/out/final-make-check-r86.log` |
| Final affected provider/activity/provenance subset | 244 passed | `analogforge/out/final-affected-platform-r84.log` |
| Provider routing, reasoning, budgets, role boundary and activity subset | 204 passed | `analogforge/out/final-reasoning-r69.log` |
| Role completion / justified hold / policy correction / wire subset | 84 passed | `analogforge/out/final-role-boundaries-r71.log` |
| Registered target handoff / coordinate provenance / exact wire reconstruction / provider boundaries | 125 passed; additional source-frame/namespace boundary subset 38 passed | `analogforge/out/final-coordinate-context-r78.log`, `final-coordinate-boundary-r80.log` |
| Final source checks | mypy 266 files, Ruff, all three forbidden scanners, wiring and merged structural purity pass | `analogforge/out/final-mypy-full-r79.log` and R79/R80 scan receipts |
| Browser journeys against the real backend | 25 passed, including all J01–J13 journeys, registered artifacts, document context and site reports | `analogforge/out/final-real-browser-r52.log` |
| Fresh backend-connected browser recheck | 7 passed: persisted export/assurance checks, layout reservation, slow fonts, exact-site reports, mobile/reduced motion, no WebGL and honest lunar gaps | `analogforge/out/final-affected-browser-r62.log` |
| Mock accessibility and contract edges | 11 passed; explicitly synthetic browser-preview behavior | `analogforge/out/final-legacy-accessibility-r57.log` |
| Refreshed platform/science mutation catalogs | Platform 20/20; science 16/16, with passing untouched baselines | `analogforge/out/final-platform-mutations-r89.json`, `final-science-mutations-r89.json` |
| Refreshed UI mutation catalog | PASS: complete 36/36, with passing untouched unit/browser baselines; focused corrected design smoke passed R94 | `analogforge/out/final-ui-mutations-r95.json`, `final-design-smoke-r94.log` |

Receipts are intentionally ignored local verification outputs. They are not credentials, source data to commit, a claim that overlapping test counts are unique, or a claim that every possible browser/visual audit ran. The R86 complete gate covers the final backend/source-context repairs and presentation components. The later audit-only font wait is exercised by the refreshed UI mutation/visual baseline, without changing app startup or C01 font assertions. No numerical science algorithm or accepted predicate was weakened to get a green result. The full C01–C20 visual-audit matrix was not rerun.

## Live data investigation

The genuine R78 investigation (`d2b0fa2f-7120-47ac-90a0-51c8261ef918`) completed at revision 188 and produced passport `8c0b623e-1320-40af-9bce-3d6fe509bfe4`. Its independently computed publication status is **LIMITED**, not full qualification. Two candidate slope-similarity predicates pass under the nominal terrain model; two fail. All four optional steep-ground availability predicates fail. No rover was supplied, and no physical rover success is claimed. It uses genuine Gale MOLA and Flagstaff NASADEM, the same accepted two-criterion contract and immutable source lock. The selected runtime is OpenAI `gpt-6.1-sol`, low reasoning, a 2,048-token total output cap and 40-second primary pacing, with explicit NVIDIA fallback. Account limits, billing and the six/40-request and 900-second run budgets remain unchanged. Ten model role invocations completed with 24 provider attempts; one rate-limited primary attempt used the configured NVIDIA fallback. The passport audit contains 12 claims and no blocking issue codes.

Earlier live runs are retained exactly, including cancellations, provider failures and review holds. In particular, R70 exposed a missing target primitive handoff to Scout. The new context includes the registered histogram, metrics, comparison support, unavailable dimensions and uncertainty notes, with lossless wire reconstruction. This is evidence delivery, not a fabricated target metric or a forced assessment. R72 additionally exposed an incorrect geometry receipt and missing source-frame metadata. The repaired handoff was checked against those actual saved database snapshots; it uses the real characterization/ingestion receipts without overwriting operator AOI metadata. A started run, a passed small provider health check or a downloadable current-evidence PDF is not proof of completed live publication.

## Interactive verification

Native Comet checks at earlier checkpoints inspected real Mars/Moon orbital imagery, detailed Earth aerial zoom to a 100 m scale, a fitted unchanged candidate footprint and an opened 14-page PDF. Later native computer controls returned unavailable-window/time-out failures; fresh compiled-app checks continued in the in-app browser. Do not describe the final native Comet rerun as passed.

A zero-width browser capture surface was recovered with an explicit desktop test viewport; screenshots are local verification artifacts. The final desktop check inspected actual Mars orbital zoom and Earth aerial imagery showing roads/trees, then fitted the unchanged candidate footprint. It also caught a tour remount while new qualification records load; the tour now retains its existing map through that update, covered by a DOM-identity regression. The compiled app was clicked through for Mars/Moon selection, mission context controls and the live regional tour. On completed R78, site 2 showed its own coordinates, nominal W1 PASS at 4.506562500000001 degrees, and steep-ground FAIL at 0.002066115702479339 fraction. Simplified/technical controls preserved those results and the report route opened with its matching site ID. The download control returned to ready without an error. Fresh close aerial imagery at a 100 m scale showed actual trees; the fit control restored the original registered footprint. Its pause notice now shows sanitized admitted reviewer concerns, without changing the retained criterion results. The completed R78 location-2 PDF (`out/native-review/gale-location-2-completed-r84.pdf`, SHA-256 `d0d63ba84d2165802f55ae3a32ef947ce6ef9faca5f28b41a1954b17556e4f50`) was freshly downloaded and all 14 pages rendered/inspected with no empty or out-of-bounds pages; executive summary, simplified overview and full technical detail remain distinct. The current-evidence brief remains a snapshot; the completed R78 passport has a LIMITED publication. Do not relabel it ASSURED or describe it as full qualification. Its source-scale and unquantified-uncertainty limits remain visible.

## Operational boundaries

- Numeric coverage is regional Gale/Flagstaff at 500 m comparison support. This is not a global Earth search or wheel-scale rover proof.
- Moon imagery is real visual context; lunar numeric coverage remains unavailable.
- Meteomatics Earth weather and historical Mars REMS are context. They do not establish climate equivalence, operating safety, current global planetary weather or weather-based ranking.
- Local mode uses an automatic loopback Owner workspace. OIDC security is tested, but no external identity provider or manual production account journey is configured here.
- USGS/EOX imagery is historical context. Zoom does not invent finer measurement resolution or change the accepted AOI.
- The official redemption site displayed `analog-forge.earth` as available on 2026-11-15. It is not reserved/registered. The form requires an eligible adult registrant, terms, CAPTCHA and email verification; registrant/contact confirmation is pending. Hosting/DNS/cloud provisioning are not complete. See the root Sponsor Integrations document.
- No personal TKS/Tabla content was removed for disk cleanup. Re-downloadable caches and inactive temporary tests outside TKS were cleared. No account, quota or billing settings were changed.

The final merge must preserve these limits and every negative/Unknown/gap result. Publish an accurate bounded result rather than changing a contract, replacing real data with fixtures or suppressing a justified review to obtain completion.


## Source freeze

The final application/backend/frontend/contracts/scripts/tests digest covers 858 tracked files: `44042ef7c1851f1233659281e6f2ca3649a6a719bb91dcedb722779662f91845`. This digest excludes operational prose and generated local receipts. Simplified graph labels use concise presentation precision; technical labels, persisted values, evidence IDs and plotted positions remain exact. A regression compares both views and verifies unchanged input records. The defensive nullable-receipt guard is covered by missing/foreign-scope tests; the live R78 receipt used valid registered IDs.

The final frontend freeze includes the assurance badge beside workflow completion, covered by a regression that keeps LIMITED visible with technical details collapsed. Backend source was unchanged after its 1,221-test pass; the complete gate runs frontend checks after these presentation repairs.

The R89 UI mutation baseline correctly refused to run mutants when C01 found an unloaded unused font family. The audit now explicitly loads Inter/IBM Plex Mono before visual captures while preserving the computed-family, loaded-family and external-request checks. R91 was interrupted to avoid competing full browser/unit loads; R92 then found the bootstrap-heading race described below; its failed baseline did not count as a mutation kill. Platform 20/20 and science 16/16 were freshly killed in R89 with passing untouched baselines.

R92 exposed a second audit startup race: an arbitrary visible h1 could be the bootstrap heading during a fresh load cohort. The audit now waits for the actual app shell and intended route heading. The unchanged C01/C13 assertions passed in the focused R94 design smoke across workbench/component-kit themes, widths, glyphs and chart alignment (exit 0). R95 passed the complete 36/36 UI catalog on this corrected audit. At the R95 checkpoint, runtime code was unchanged from the complete R86 gate; those repairs affected audit synchronization only.

Final integration gate and all 72 fault-injection checks passed. Current compiled-app inspection showed the LIMITED assurance beside Completed, real site imagery and the unchanged benchmark values. The whole-Earth view and return-to-site controls worked; the globe-label follow-up below resolves the nearby marker overlap observed at this checkpoint.

## Main merge and globe readability follow-up

PR #3 was merged into main with merge commit `1210b0fdfa7581fb9bf4c5f9388af919e9f69471`, from tested head `41e05ff914cefe8dc56a0685d6693b634f7e4c62`. A fresh fetch confirmed identical source trees and preserved Tanush, Aradhya, Ayan, BETTERUI and premium-glass ancestry.

The subsequent UI-only follow-up groups nearby globe labels without merging evidence or moving any underlying location. A group is anchored to an actual selected member, displays its member count with neutral status, and opens that member's exact site view. The individual site list, benchmarks, report links and negative/Unknown results remain unchanged. Grouping handles longitude wrap and high latitudes and cannot chain neighbors into an arbitrarily wide group. This is a display rule, not a science score, new candidate or broader dataset search. The panel explains how to choose each member.

Focused marker/tour tests passed 10/10. The three affected browser journeys passed: exact-site inspection/report with grouped-marker click, mobile/keyboard/reduced-motion accessibility, and no-WebGL access. Typecheck and lint passed. The style scan initially caught an excessive marker corner radius; the final marker inherits the existing approved radius, without weakening the scanner. The full frontend passed 316/316 tests (68 files), and the final production build, forbidden scan, wiring, merged purity and docs checks passed. Receipts: `analogforge/out/globe-frontend-r97.log`, `globe-browser-r97.log`, `globe-build-r99.log`, `globe-ui-forbidden-r99.json`, `globe-wire-r99.json`, `globe-purity-r99.json` and `globe-docs-r99.log`.

Final compiled-app computer interaction on the completed R78 investigation verified one neutral four-member globe marker. Clicking it opened the unchanged selected site 2 (`12b148c6-b33f-4d86-955e-59e55f412a17`) in the aerial map. Its own coordinates, 4.507-degree nominal PASS, 0.207% optional FAIL, individual report target and LIMITED assurance remained visible; no console warnings/errors were recorded. Captures: `out/native-review/completed-earth-grouped-r99.jpg` and `completed-location-final-r99.jpg`.

The follow-up source digest covers 860 tracked application/backend/frontend/contracts/scripts/tests files: `b93b12a8e23273e6704bdd01a853885d8cac4d0ddf63ec8fa384bbf7ffeed112`. It supersedes the R86 digest for this UI-only follow-up; the earlier complete backend and 72-mutation receipts remain checkpoints of PR #3. No backend, accepted predicates or dataset bindings changed in the follow-up.

## Fresh local computer journey - 15 November, final follow-up

PR #4 merged as `3fb9a54925cf34674d7b5c031d45fe8f750b651e`, preserving its tested tree. The user explicitly chose to keep this verification local. This pass therefore tests the automatic loopback Owner workspace, not an external identity-provider login/logout. Native Comet automation timed out again; the computer interaction used the actual compiled app at `http://127.0.0.1:5220` through the connected in-app browser, against the real API on 8035.

The fresh journey traversed landing, Moon/Mars selection, a real lunar mosaic, real Mars orbital zoom, a Gale 10 km target, mission prose, uploaded/reviewed mission and rover Markdown, an imported saved rover JSON revision, a custom informational camera feature, exact context pinning, live fingerprint review/acceptance and the progressive recorded work log. The declared test rover is expressly not a manufacturer-certified or real flight rover; its assumed energy calibration and missing limits remain explicit.

The live checks found and repaired actual faults: the landing recent list loaded the oldest records; Rover Systems received an inspect-contract receipt instead of a real profile-validation report; preparation retained the selected rover ID/hash but omitted the full declared profile from its model request; reviewers confused proposal provenance with current operator acceptance; the guided review hid contract assumptions; reopening a saved library mission omitted the pinned rover; and a later budget stop could misleadingly display a historical role concern. The new optional read projection does not change the frozen ascending core listing API. Schema/semantic profile validation cannot establish physical performance.

Historical runs `1fa9b428-4945-437f-888a-8a628bb01ee8` and `87dbcbf7-ab82-4e1e-9659-b0c1d6b356d8` remain unchanged. Fresh run `c9ba8605-5ff0-4c39-bee8-a4ae150e6516` passed the corrected requirements/rover/target/scout/qualification/critic reviews, registered four genuine Earth windows and eight criterion assessments, exercised real Meteomatics point context and historical NASA REMS context, and recovered HTTP 429 responses through the configured NVIDIA fallback. A modeled-test attempt was retained after the bounded review retry; the run ultimately reached its 40-request budget before passport assembly. Its budget and negative/Unknown results were not altered or suppressed. The final clean attempt is recorded separately below.

Each of the four location selections changed its own ID, coordinate readout, benchmark measurements and report destination. Close Earth aerial zoom showed trees/roads at a 100 m scale and Fit restored the original registered footprint. Simplified and Technical details preserve the same stored values; the latter exposes exact precision and receipt/evidence references. Four actual location-report PDF downloads (`out/native-review/fresh-location-{1,2,3,4}-r110.pdf`) were checked: each has 15 nonempty pages, no out-of-bounds text, executive/simplified/technical sections, graphs, registered terrain displays and Technical terminology. Every page was rendered and visually inspected; those are intermediate evidence snapshots, not published passports.

Verification receipts: R103 full merge gate passed kit 20, platform 1,230, science/renderer/UI contracts 1,290, frontend 318 and client contracts 3. After the preparation/target regressions, R107 re-ran the entire final backend platform with the real science/renderer: 1,234 passed. The later shared prompt interpretation is covered by R112 role/receipt/reference/request-budget tests: 100 passed, preserving the 22,000-byte conversation ceiling and all operator budgets. Final frontend R117 passed 322 tests in 70 files plus 3 client-contract tests, typecheck, lint and production build. R117 re-ran and passed the three affected browser journeys (exact-site/report/recent-link, mobile/keyboard/reduced-motion, no-WebGL); the subsequent terminal/resume repairs have focused regressions and actual computer verification. The source scans and wiring passed. No account, billing, rate/quota setting, frozen predicate, accepted contract or dataset policy was weakened.

Source freeze: 920 tracked files under application source, apps, contracts, config, scripts, tests and ops. SHA-256 `f2c40b757f53f4616c945ccab2f5f9d3567aa3674c8e25edc1ff993ae2b59449`, computed over sorted repository-relative path + NUL + bytes + NUL. Operational prose and local evidence receipts are excluded. The scan of 1,393 tracked/build files found no private configured credential values. Detailed boundaries in the earlier operational section still apply: regional 500 m terrain evidence, historical visual imagery, weather context, and no physical rover qualification.

The actual 390 x 844 reduced-motion computer pass caught a long pause notice pushing the footer below the viewport. Notices now share the scrollable panel body, and a new notice scrolls to the start of that body. The corrected current build kept all three site-navigation controls between y=747 and y=791, with no horizontal page overflow. Both the earlier clipped capture and corrected proof are retained locally (`fresh-mobile-r116.jpg`, `fresh-mobile-fixed-r117.jpg`). R117 browser journeys include the affected mobile/footer, exact-site/report and no-WebGL paths.

## Clean completed rover investigation and actionable field briefs

The fresh R115 investigation `aca422e6-4010-426a-93ce-7fcc7a883b66` completed at revision 273 with no blocked
dependencies. It pins accepted mission revision `04045baa-dac8-43f8-ba87-6bdc589ccc65` and declared rover revision
`8e6b987c-107f-40cf-8981-76820e25679f`. Passport `21515f65-4254-4816-bc6a-92035a4ed91c` has independent
publication status **LIMITED**, with 13 scoped claims. Its manifest is
`370154aee4fd1c2928e061798d75dac0a273d5a6d2abe0668d974c0139dfb965`. Four genuine Earth windows retain
eight terrain assessments: two nominal mandatory W1 passes, two mandatory failures and four optional failures.
The same regional 500 m support, unquantified terrain uncertainty and Earth/planetary transfer limits apply.

The local operator explicitly chose PROVE IT at the normal review checkpoint. Site 1's recorded modeled route
result `44581e36-9cad-4755-b505-01eccd1782a1` passed within raster feasibility only. The route digest is
`2502b48a3d39d289b8aed00addc61e2d9114267f5ec79a0ec24f520ac14aa45d`. Its independently modeled distance
is 7,414.21 m, with 15 telemetry samples and about 81.6% modeled battery reserve. Generated W1/W2 sampling stops,
the design-default distance bound, 500 m task tolerance and assumed energy calibration are recorded assumptions,
not additional accepted mission requirements or evidence of physical sampling performance. No physical trial,
surveyed corridor, material evidence or mission-success probability is claimed.

The clean run completed 14 model role invocations using 37 charged provider attempts within the unchanged 40-attempt
run budget. Real primary rate limits recovered through the configured NVIDIA fallback. No billing, quota or account
settings were changed, and the older failed/budget-limited runs remain intact.

At the user's request the current-evidence PDFs now connect methods, final coordinates, a site-specific field plan
and exact benchmarks. A combined mission brief provides a location directory and PDF sidebar bookmarks for each
site; individual downloads retain their executive summary, simple graphs and full technical evidence appendix.
The online report mirrors the methods / where to test / benchmark sequence. A centre coordinate is explicitly not
a route start. Only a site's latest experiment, matching frozen constraints/rover/mission, registered verifier artifact,
receipt and scientific invocation may supply its endpoints and checkpoints. Projected task locations use their own
executable route-node geometry; another site's route is never substituted. Uncomputed routes remain absent.

All five final PDFs were downloaded through the compiled app against the actual completed live run in R126.
The combined brief has 22 pages; the individual site briefs have 19, 18, 18 and 18 pages. All 95 pages were rendered
and visually inspected, with zero empty pages or out-of-bounds text, plus checked navigation bookmarks.
Files are ignored local receipts under `analogforge/out/output/pdf/`; no dataset, private credential or local
evidence snapshot is added to Git. Final report computer inspection showed the actual site-owned start/return loop,
two numbered checkpoints and explicit limits. The 390 px mobile report had a 390 px document width and 324 px map
schematic, preserving the coordinates without page overflow.

Final added-scope verification: 33 focused PDF/field-plan and real PostgreSQL integration checks passed (R125),
including foreign workspace/site rejection, modified blobs, stale/newer experiments, scope/hash mismatches and
read-only downloads. The entire platform unit suite passed 1,035 checks (R127). Its first R126 invocation used the
browser profile's opt-in visualization flag and failed only the expected default-off assertion; R127 reran the
entire suite with the intended default flag rather than changing that assertion. Frontend: 325 tests in 71 files
(R123), three client-contract checks, typecheck, lint and production build. Three affected browser journeys passed
in R125. These are in addition to the earlier complete R107 backend platform pass and R112 role/prompt boundary
checks, not a claim that their overlapping counts are unique. The final field-plan UI uses the existing theme
tokens and approved corner-radius variables; the scanners were not weakened to allow the new presentation.

Final R128 source freeze: 924 tracked application/source/test/configuration files, SHA-256 `ed700fa7506684059382c24c7bd7074835f049132e6f9d6cb223bedf872917cd` using the same sorted path + NUL + bytes + NUL method. This supersedes the earlier R117 checkpoint digest. Credential-value scan: 1398 tracked/build files, 11 configured private values, zero matches. Final wiring, all three forbidden scanners and merged structural purity passed.
