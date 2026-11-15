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

R92 exposed a second audit startup race: an arbitrary visible h1 could be the bootstrap heading during a fresh load cohort. The audit now waits for the actual app shell and intended route heading. The unchanged C01/C13 assertions passed in the focused R94 design smoke across workbench/component-kit themes, widths, glyphs and chart alignment (exit 0). R95 passed the complete 36/36 UI catalog on this corrected audit. Runtime code is unchanged after the complete R86 gate; these follow-up changes affect audit synchronization only.

Final integration gate and all 72 fault-injection checks passed. Current compiled-app inspection showed the LIMITED assurance beside Completed, real site imagery and the unchanged benchmark values. The whole-Earth view and return-to-site controls worked; nearby global marker labels can overlap and are a separate presentation follow-up. The per-site inspector/list disambiguates those locations.
