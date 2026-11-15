# Aradhya ordered implementation plan

Every step ends with focused tests, typecheck/lint and a small commit. Completion means observable behavior and evidence, not files merely existing.

## A0 — Stabilize contracts and existing behavior
- Record common base, read frozen seam and inspect all inherited screens.
- Resolve the design-standard exception narrowly; retain the expert /workbench and every /runs/:id/<tab> deep link.
- Add route-scoped test helpers. Repoint legacy workspace starts from `/` to `/workbench` in e2e support/workbench.ts, journeyChecks.ts, a11y.spec.ts, list-loading-presets.spec.ts, J01-golden.spec.ts and integration/merge-assertions.spec.ts. Search for other workspace assumptions; do not globally replace home navigation tests.
- Add missing third-party notices for pinned globe.gl/three and source-image notices with actual upstream versions/licenses. No copied Aleph code in this phase.

## A1 — Correct wizard state and preparation
- Coordinate input tests: whitespace, decimal intermediates, NaN/infinite rejection, ±90 boundaries, 0/180/360 normalization, body switch, pole/seam boundaries and invalid area. Retain explicit unsupported geometries rather than expanding into a nearly global bbox.
- Changing place/body/objective/rover invalidates downstream prepared proposal and local acceptance controls. The server's accepted revision is immutable; start a new revision/run to change it.
- Route guards identify the earliest missing step. Refresh/back/edit preserves or clearly discards an unsaved draft; use normal persisted mission workflow when saving. No domain localStorage.
- Rover creation/import/no-rover: reuse validation/library; preserve wizard when visiting editor, unknown values/energy assumptions visible. Avoid duplicate imports and stale selected revisions.
- Explicitly display chosen scenario, source mode, lock and missing-data reasons. Do not infer that named Gale/Jezero shortcut or 40km box is runnable. Unknown height reference remains Unknown until established by source evidence.
- Job polling uses abort/cleanup, finite budget and actual job states. Keep command identity/recover/resync; don't create duplicate missions/jobs/runs after a lost response. Review cards expose origin/support/assumptions and exact accepted revision/hash.

## A2 — Progress, tour and state truth
- Handle all run states, allowed actions, blocking reasons, disconnect/reconnect and monotonic snapshot updates. Existing stream controller is reused, not forked.
- Keep pinned candidate order and exact candidate IDs through list/marker/URL. A cluster count says several sites; selecting a cluster opens its actual members, including failing/unknown sites. Do not give a mixed cluster an all-pass scientific label.
- Add assurance visibility, committed per-requirement status and origin/support. Preserve FAIL/GAP/UNKNOWN; coverage list is not a computed portfolio.
- Scope attempts to correct candidate or explicitly run-level; await selection then use refreshed revision for dependent actions. Route actions remain modeled verification, no implied physical test.
- Fix long narration, empty/provisional candidates, missing classifications and partial query failures. Errors in rover/result/qualification reads must not silently disappear.

## A3 — Required exact-location drill-down
- Implement the interaction in `04-SCREENS-AND-LOCATION-ZOOM.md`. Both globe marker and keyboard list choose the same immutable site.
- Use a URL view state such as `?site=<id>&view=regional` validated against this run; preserve legacy `candidate` query handling where applicable.
- Compose existing EarthMap for Earth detail and PlanetaryPanel for planetary detail, through one Aradhya-owned view adapter. Read existing registered display manifests now; mock optional Tanush envelope until its API lands.
- Metadata mismatch/unknown resolution/no coverage gets a designed fallback, not a blurred texture labelled exact detail. Full flow still works without WebGL.

## A4 — Browser report and published exports
- Add `/runs/:runId/report?site=<id>` outside the stage and workbench chrome. Validate candidate membership. Reuse run data selectors but do not treat data from a failed fetch as an empty successful report.
- Print-first light document: mission/place/rover, source mode, assurance or Pending, exact benchmark rules, supplied measurements only, evidence IDs, gaps/limitations and published contract/lock/manifest metadata. No unsupported scientific headline.
- Browser print is a convenience summary. Link only actual published immutable passport HTML/JSON/CSV with existing safe download/digest verification. Unpublished passport says unavailable; do not mint hashes or mark the browser report official.

## A5 — Catalog seam, polish and merge evidence
- Add optional validated same-origin imagery catalog loading in src/api; retain GLOBE_ASSETS when missing/invalid. Implement coverage/detail adapters behind delivered capability, never probe absent endpoints by default.
- Screens at 1440x900, 390x844 and required design viewports; keyboard parity, semantic local site list, contrast, long labels, reduced-motion, reduced-transparency, WebGL unavailable/context loss and printable report.
- Extend the visual audit/catalog and focused tests; run full frontend and real-backend gates. Update status with exact source SHA and limitations. Never call mock-only success a live-data demonstration.

Deferred: automatic multi-candidate proving, model narrator chat/avatar, attachments, sign-in, Google Street View/meshes, all-body global data expansion and PDF rendering service. They do not block a complete first UI.
