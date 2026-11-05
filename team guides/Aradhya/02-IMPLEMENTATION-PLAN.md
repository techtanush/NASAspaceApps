# Aradhya implementation plan

Build reusable screens against real contracts, then connect actual durable results early. Keep `team handoffs/aradhya/implementation-status.md` with U0/U1 status, tested/base SHA, schema hash, mock versus real mode and blocked API needs.

## U-A0 Bootstrap and contract client

Confirm own branch/worktree. Read architecture00/02/05/07/16–19/26/28 and shared ownership/service/runtime files. Scaffold only owned frontend files, root frontend package/lock and renderer package. Use current configured Codex; do not require an extra model or cloud service for frontend creation.

Generate client/types from accepted architecture OpenAPI C0, then from Tanush's exported F0 implementation schema. Resolve/bundle relative schema refs rather than hand-copying partial interfaces. Provide `typecheck`, `test`, `build`, `generate:client`, `dev`, `dev:mock`, `test:e2e` scripts with locked versions. A generated client diff signals contract drift; do not edit generated fields manually.

Set up an explicit MSW/mock-development switch with prominent MOCK/SYNTHETIC preview badge and network isolation. Fixtures cover all five qualification states, three verification outcomes, pending critic review, no rover, blocked source, revision409, empty candidates, cancellation and event reconnect. They are development fixtures, not fake backend persistence.

## U-A1 Workbench and authoring

Implement app navigation and recent run/missions views with deep links. Responsive shell uses mission/rover context, central target/Earth view, evidence/qualification panel and operations timeline; do not make a giant chat window.

Mission drafts save/reload with visible saving/saved/conflict states. Build body/region/objective/priority input, bbox/preset planetary target selection with body/longitude metadata and validated units. Requirements preparation submits job then fetches proposed contract; numeric default origins are visible. Acceptance binds exact revision/hash. Editing accepted inputs creates new revision/run.

Rover editor/import shares one input model and round-trips baseline ARES-1 values. Invalid/missing fields stay editable with errors; unknown capability is not zero/false. Site-only no-rover run is supported and PROVE_IT explains why unavailable until a new run pins a rover.

Deliver U0: generated client, functional mock authoring/workbench/matrix, visible modes, accessibility basics and tests. Publish exact SHA so Tanush can integrate the interface before all maps/report polish is done.

## U-A2 Read scientific state and operations correctly

Build target/candidate summaries, side-by-side comparable-scale plots/tables, complete requirement matrix and evidence drawer. Render PASS/PARTIAL/FAIL/GAP/UNKNOWN distinctly with text/icons and exact units/support. Pending calculation is not provisional PASS. Confidence uses dimension-specific evidence strength, no fake planetary percentage.

Selection mutations include expected revision/idempotency and update only on server confirmation. Fetch authoritative run snapshot. Implement EventSource committed-seq dedup, cursor-gap/410/reconnect refetch, selected pointers, terminal close and cleanup. Durable operations/receipt/critique retrieval remains available after SSE event retention. Never display private provider reasoning.

Critic issues reference actual evidence/requirement IDs; view prior/superseding state and concrete repair/review request. User review can acknowledge a supported limited experiment, not turn missing data into observed truth. First PROVE_IT previews accepted benchmark criteria and launches actual design/verification; no route is claimed before its artifact exists.

## U-A3 Integrate real backend and scientific layers

Merge accepted F0/main. Set own profile API/CORS and run a real seeded backend; disable MSW for integrated journeys. Make actual mission/rover/run requests and assert server records/receipts, not only UI snapshots. Record any endpoint/field gaps precisely through handoff requests.

Read Ayan's registered DisplayLayerManifest images with correct Earth corners or planetary affine/CRS. Add legend/support/attribution/nodata transparency. Earth map/table selections agree. WebGL failure leaves list/matrix/route metrics usable. Planetary bbox selection stays body-aware; no Earth tile labels on Mars/Moon.

Display proposed/computed route, science waypoints, violations, exact attempt outcome, failure category, telemetry and changed route/site. Preserve original failure even after PASS; show unchanged contract/rover hashes and actual number of replans. Search cap is INCONCLUSIVE. A map animation is not physical rover execution.

## U-A4 Portfolio and full report experience

Implement portfolio creation/selection, requirement-to-site responsibility and unresolved gaps. Distinguish separate campaign coverage from co-located conditions. Do not claim a combined executable route between sites.

Implement immutable passport preview and pure renderer per shared03/architecture19. Cover positive, limited, failed, inconclusive, site-only and composite results. Include all attempts, data provenance/scale, model assumptions, field-specific unknowns, source/final-manifest/build hashes and next steps. Escape arbitrary user/model strings, embed supplied validated images, preserve safe attribution and print pagination.

Handle asynchronous export202/Retry-After/job polling, correct downloadable formats/filename/digests, errors and stale versions. File digest verifies downloaded bytes; manifest digest identifies frozen scientific content. Do not create a new report from changing current UI state.

## U-A5 Browser renderer and integration quality

Run own05 at1440/900/390px and keyboard/screen-reader friendly control semantics. Test autosave conflict, invalid import, no data, no rover, unknown clearance, missing mineral, negative control, review, PROVE_IT, fail/replan/pass, portfolio co-location, export, cancel/reconnect/reload and WebGL fallback. Test renderer HTML/CSV injection and no secret/internal path leaks.

Run both visible mock-preview component suite and separately real backend/science/worker browser suite. Assert mocks disabled in the latter and persistence survives reload. UI-only fixtures cannot pass the actual app acceptance gate. Resolve frontend warnings/errors that indicate broken state/imports; do not silence failures or hide rows to pass screenshots.

## U-A6 Final handoff

Deliver U1 exact tested SHA/base/schema hash, package lock, browser/renderer commands/results, real integration evidence, assets/licenses and blockers. Keep only owned paths. Request shared changes through exact contract-change file; do not rewrite Tanush's schema or Ayan's scientific outputs. Tanush integrates the tested commit and reruns combined gates before main advances.
