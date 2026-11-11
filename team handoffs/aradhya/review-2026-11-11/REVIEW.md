# Aradhya branch review — November 11, 2026

Incoming branch: `aradhya/frontend-experience` at `7433cd84d56f537137eb1035d1a97f4ac51a315e`.
Reviewed application source: `f5e4a238013e091ab6c8fe248a77bb73176a6d68` (authoring integrity, passport audit validation, isolated mutation controls, responsive authoring polish).

This is a frontend and pure-renderer contributor review. It does not certify the merged platform/science backend, live providers, real terrain datasets, physical rover performance, NASA endorsement, or competition results. No subagents or other chats were used, following the user's current instruction.

## Reproduced findings and corrections

| Finding | Reproduction / consequence | Correction |
| --- | --- | --- |
| Mission route identity retained | Navigate directly from mission A's edit route to mission B's edit route. A's form and save destination remain active. | Key the editor lifecycle by workspace and mission identity. |
| Latest edit can remain unsaved | Delay the first draft receipt; edit again while the first save is in flight. The later autosave timer can expire without retrying. | A completed save triggers reconciliation and another save of a waiting newer edit. Existing conflict handling and same-key transport retry remain intact. |
| Existing draft editable before loading | Delay the initial read on an existing mission route. A writable blank form is exposed before its saved identity/draft arrives. | Keep the editor behind a loading state until the complete saved record arrives. A failed read exposes a retry and cannot issue a blank new-mission command. |
| Obsolete fingerprint restored | Edit the draft while its fingerprint job is pending. The old proposal later appears and can be accepted. | Bind asynchronous proposal receipts to the issuing draft version and mounted editor. Ignore older receipts. |
| Obsolete acceptance restored | Edit after accepting begins but before its response arrives. The older accepted contract reappears on the changed draft. | Apply acceptance receipts only to the issuing draft version. The server's immutable old revision is preserved; it cannot become the new draft's displayed accepted input. |
| Invalid publication report can appear qualified | Supply an unknown publication value, missing claims, a different run/workspace/mode, or a different accepted mission hash with a passing test result. The UI previously displayed a positive headline. | Validate the entire frozen assurance schema using a precompiled validator and bind passport/audit identity to current accepted inputs, including the rover hash. Invalid reports show INCOMPLETE, a recoverable error and no download controls. No scientific calculation or manifest hashing was added to the browser. |
| Candidate acknowledgement redirects newer navigation | Select a candidate, navigate to Qualification before acknowledgement settles, then complete the old command in the same turn. The old query update navigates back to Analogs. The full browser case reproduced this at both desktop and mobile widths. | Update the selection query only if the browser URL still matches the URL that issued the command. Preserve authoritative selection and normal stay-on-page URL updates. Two deterministic tests cover both paths. |
| Mutation isolation lacked a reliable control | Vite's configuration gained `hmr` ahead of `strictPort`; the isolation patch silently stopped adding dependency filesystem access. The runner did not require a passing unmutated isolated layout. | Require a unique configuration anchor, allow the owning dependency checkout, and run unmodified unit/browser controls before counting any kill. Match browser navigation and server readiness to the configured origin; use isolated port 5178. |

`MissionEditor.review.test.tsx` adds five asynchronous regressions and a safe initial-load retry case (six tests). `PassportView.review.test.tsx` adds a valid positive control and twelve malformed/context-mismatch cases. The original ten failing cases were recorded before production edits. The initial-load regression was additionally reproduced on `bc73c25` before its correction. The candidate-navigation race adds a failing-navigation regression and a stay-on-page positive control. There are twenty-one new frontend tests in total, bringing the full suite to 111. The additional six malformed-artifact cases exercise missing/invalid timestamps, malformed claims/limitations, and the wrong rover hash. Existing acceptance tests and thresholds were preserved.

## UI refinement

The authoring page now highlights the current workflow step, groups the draft save receipt, gives target-body choices a clear selected state, names geographic limits as west/south/east/north with explicit degree units, and keeps paired bounds in two columns on mobile. Styles are scoped in `apps/web/src/styles/authoring.css` and use the existing frozen tokens. Scientific statuses, wording, accepted values, and map measurements are unchanged. No outside UI repository or extra visual dependency was necessary.

## Verification and evidence

The original branch passed 90 frontend tests and 131 Python tests before fixes. Its initial full browser invocation passed 39 cases; the long visual crawl was deliberately interrupted after the regressions were reproduced, and the remaining WebGL case had not run. That invocation is not reported as a complete passing gate.

The first generated-validator browser attempt exposed a CommonJS/ESM helper packaging error. It was corrected and the complete mission-to-export smoke journey passed, including independently verified download bytes. A later pre-polish browser run was interrupted when the user requested UI refinement. A Qualification heading transition exceeded its unchanged 15-second assertion during concurrent verification and again at mobile width in an unchanged serial run. The serial reproduction ruled out a resource-only explanation. `navigation-red.json` then proved the late candidate-acknowledgement redirect deterministically; the guarded URL update fixes it without weakening the assertion. Interrupted browser evidence is preserved under `transition-failure/` and `navigation-failure-serial/` in the raw evidence directory. Final readiness is based on the complete polished-source runs recorded in `RESULTS.json`, not those interrupted invocations.

Raw local evidence is under `analogforge/out/review-baseline-2026-11-11/`, with browser JSON and the visual packet under `analogforge/out/`. Generated screenshots, runtime binaries, dependencies and build output are intentionally excluded from Git. Durable summaries and selected assertion receipts are stored beside this report. Re-run instructions are in `apps/web/README.md` and `team guides/Aradhya/05-TEST-AND-MERGE-GATES.md`.

The review uses a checksum-verified official Node 22.21.1 runtime, pinned pnpm 10.22.0, Python 3.12.13, and matching Playwright Chromium 141/build 1194. The system Node executable is broken because its simdjson dylib is missing; no global Node installation was changed. Semantic indexing did not finish, so targeted source searches and direct code inspection were used.

Existing multi-reviewer visual evidence remains historical. This review performs a new single-agent image inspection plus automated visual/accessibility gates; it does not invent new independent reviewers. The user specifically requested work in this chat without subagents.

## Integration boundary

`MRG-03` real-backend execution remains for the merging agent after Tanush, Ayan and Aradhya are combined. Mock journeys demonstrate frontend behavior against synthetic fixtures. They do not establish real scientific qualification. The existing large map/application bundle warning remains a nonblocking performance limitation; no build threshold was weakened.

The final handoff commit also refreshes the twelve permitted component-guide images generated by the passing audit. Two existing browser journeys gain read-only `inspectHooks` captures while excluded windows and invalid-rover field errors are visible; focused J01/J04 reruns verify these additions and complete the81-hook receipt union. Application runtime remains exactly the tested source above.
