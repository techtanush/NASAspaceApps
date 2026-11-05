# User journeys, screens and interaction states

This document implements the product requirements in `02-PRODUCT-REQUIREMENTS.md`. The binding technical decisions are in `00-ARCHITECTURE-DECISIONS.md`; wire operations are in `07-HTTP-API-AND-EVENTS.md` and `contracts/openapi.yaml`. Do not replace these screens with a chat transcript. An objective textbox is a mission input inside a structured workbench.

## 1. Routes and persistent shell

Use React Router routes:

| Browser route | Purpose |
|---|---|
| `/` | Workspace missions and runs |
| `/missions/new` | Draft mission setup |
| `/missions/:missionId/edit` | Editable draft, revision history and acceptance |
| `/rovers` | Rover profiles and new-profile entry |
| `/rovers/:roverId` | Rover profile, revisions and JSON import |
| `/runs/:runId/mission` | Accepted Mission Fingerprint and pinned rover |
| `/runs/:runId/target` | Moon/Mars target evidence |
| `/runs/:runId/analogs` | Earth discovery and candidate detail |
| `/runs/:runId/qualification` | Qualification comparison and critic review |
| `/runs/:runId/compatibility` | Rover versus selected test |
| `/runs/:runId/portfolio` | Complementary site plan |
| `/runs/:runId/test-lab` | Proposed test, verification attempts and replanning |
| `/runs/:runId/passport` | Final or explicitly draft passport |

Use search parameters `candidate`, `requirement`, `attempt` and `evidence` for shareable selection. Treat values as IDs scoped to the run and validate them through API responses. Missing/deleted/inaccessible selection yields an explanatory inline panel with a clear way to return to the list. Never select an unrelated record merely because an ID was provided in a URL.

The run shell contains: mission title, target body, immutable runtime-mode badge, current run state, pinned contract/rover revision, connection indicator, main navigation, available run actions, evidence drawer and operations drawer. A compact persistent summary shows accepted constraints and pending required conditions. At desktop width, use left mission context, center map/workspace, right detail panel, bottom operations. At narrow widths these become tabs/stacked sections; none are hidden permanently.

Navigation remains available while work progresses. Sections not yet produced show prerequisites and current job state. Do not disable the entire application while a raster worker runs.

## 2. Journey A: create a complete investigation

1. From workspace, choose **New mission**. Enter a name, choose Moon or Mars, select a target, describe the experiment, and choose optional objective categories. Save a draft immediately after valid minimum input.
2. Choose an existing rover revision, create one manually, upload JSON, or explicitly continue with site qualification only. The last choice identifies rover verification as unavailable for this run.
3. Request **Build Mission Fingerprint** through `POST /missions/{id}/fingerprint`. This creates a preparation job before a run exists; poll `GET /jobs/{id}` for the proposed mission revision. Show Requirements-role preparation activity and processing state. Preserve the objective text while the proposal is generated. AI unavailability leaves the draft intact and exposes retry/configuration guidance; it does not substitute a hidden hardcoded contract in live mode.
4. Review each proposed requirement and assumption. Show source of every threshold. Resolve required missing values and conflicts. A gap such as gravity remains visible and does not block terrain investigation by itself.
5. Review a freeze summary: body/region, objective, hard/soft requirements, measurement scale, rover revision, assumptions, runtime mode, search/compute budget. **Accept contract and start** accepts the mission revision, then creates the run using that revision and selected rover revision. If run creation fails after acceptance, allow idempotent run creation without modifying the accepted contract.
6. Follow target characterization, Earth screening and detailed candidate analysis. Read receipts as they arrive. Candidate rows begin pending, never prefilled green.
7. Open qualification. Inspect evidence/limitations. The critic may reopen work. If human review is required, review the specific evidence proposal and scope, then approve or retain unresolved requirements according to the server action contract.
8. Select a candidate, inspect preliminary rover compatibility and review the benchmark preview drawn from the accepted contract. Use **PROVE IT** to start test design followed by verification within those criteria. The actual test/route appears after its artifact commits; new material assumptions pause dependent work for review. No browser animation may start an unrequested second verification job.
9. Read result. If failed or inconclusive, inspect failed benchmarks and diagnosis; follow bounded replans or choose a supported next action. Historical attempts remain available.
10. Open final passport. Export HTML, JSON or table CSV. A limited or negative result is a legitimate final passport and must have the same export capability as a positive result.

## 3. Screen specifications

### S01 — Workspace

Show mission name, body, latest accepted revision, last run status/mode, last update and unresolved-review count. Filters: body, mode and active/completed state. A run's terminal state and scientific outcome are different columns: `COMPLETED` can contain `FAIL` or `INCONCLUSIVE`. Empty state: short purpose statement, **New mission**, **Load example**. Example choices explicitly state synthetic, replay or live requirements.

Actions: create/open mission, open run, open rover library. Archiving/deleting is outside this document unless the API provides it; do not render nonfunctional menu items. On access failure show retry and workspace context. Do not erase the list during background refresh.

### S02 — Mission setup and target selection

Fields: mission name; body radio group; objective textarea; experiment categories; target preset/list or custom region; location metadata; optional candidate search bounds. The target picker uses a planetary panel, not the Earth map. Display selected region extent, longitude convention, coordinate units and source identifier. Changing body clears incompatible target selection after warning about the unsaved selection; it cannot reinterpret lunar coordinates as Mars coordinates.

Before saving, validate bounding-box extent, body match and input limits. The initial `AreaOfInterest` contract is a four-value bounding box with body/coordinate metadata, so the custom-region control draws a rectangle or accepts equivalent numeric bounds. Keyboard users can choose presets or type bounds. An arbitrary polygon editor requires a future explicit contract extension and must not appear as a supported control in this release.

Body-specific catalogs can be empty or unavailable. Show **No target presets loaded** with custom-region entry if supported, and a separate **Catalog unavailable** error for network/configuration failure. Do not silently use a different world or demo region.

### S03 — Rover editor and import

Group fields as identity, geometry/mobility, energy, sensors, instruments and declared capabilities. Always display units beside fields. Optional quantities have a clear **Unknown** option. No parser guessing: convert explicitly supported input units and show conversion before save. The shared Pydantic/OpenAPI schema is authoritative.

Import sequence: choose file → read locally → enforce configured size/type → parse JSON → schema validation → preview supported fields, unknown fields and unit interpretation → user accepts preview → persist new profile/revision. Do not upload file contents to the model. A malformed file never overwrites an existing rover. Support drag/drop only in addition to the accessible file picker.

Canonical example fields: ARES-1, 42 kg, 18°, 0.20 m clearance, 0.30 m wheel diameter, 1800 Wh, 20% reserve, 0.5 m/s nominal speed, stereo camera/IMU/LiDAR, autonomous-navigation and geological-sampling declarations. Values from a user import supersede the example and receive a new immutable revision.

When editing a rover used by existing runs, show **Save as new revision**. Explain that previous investigations retain their pinned specification. Do not offer an inline “increase rover slope” repair in an existing run.

### S04 — Mission Fingerprint and freeze review

Requirements appear in a table with expandable rows: ID, category, requirement, priority, observable, target/threshold, unit, measurement scale, Earth reproducibility, evidence required and threshold origin. Group physically unavailable conditions separately without removing them from the complete contract.

Each proposed threshold is labeled **From your input**, **Derived from target evidence**, or **Proposed assumption**. Derived thresholds link to their calculation; proposals require review. Hard limits and experiment exposures have different labels. A conflict card identifies exact incompatible rows and offers editing the draft. E.g. requested 20° traversal versus rover safe limit 18° cannot be resolved by silently lowering either number.

Actions: edit proposed requirement; accept explicit assumptions; regenerate proposal from revised objective; accept contract; select rover revision; choose runtime mode. Once accepted, show a read-only revision badge and **Create revised mission**. No contenteditable control may mutate accepted rows.

### S05 — Target profile

Show planetary raster/coverage panel, region summary, source products, comparison scale, elevation/slope/roughness/relief charts and optional thermal/mineral dimensions when supported. Each chart includes units, bin definitions, valid-data count, no-data fraction, method and evidence link. Empty dimension has **Not requested**, **Pending**, **No coverage**, **Unsupported comparison**, or **Failed to retrieve**, not an unlabeled blank chart.

Provide target/source metadata through a single visible evidence panel, including body/longitude convention/datum. A profile available only at coarse resolution warns against interpreting tiny terrain features. A target with no valid required terrain evidence blocks downstream comparisons and shows which data action can resolve it.

### S06 — Earth analog discovery

Render candidate polygons/centers, candidate list and filters: analyzed/pending/excluded; dimension support; evidence availability; candidate origin. Site cards show name, region, source of nomination, analyzed extent, required-dimension status counts and unresolved required evidence. Ranking label describes its explicit basis, e.g. **terrain screening order**, never **most Mars-like**.

Clicking a map candidate and selecting a list row update the same URL selection. Detail includes required evidence, terrain charts at comparable scales, exclusions, supported uses and investigation history. Allow comparing a small number of selected candidates without hiding the remaining catalog. “0 candidates” explains search bounds and exclusion counts. It offers expanding bounds/new run or manual nomination only where supported; it does not invent sites from model memory.

Candidate nomination requires a labeled Earth region; it enters pending analysis. Route previews do not appear before a test artifact exists. A country outline is context, not a candidate boundary or permission to access land.

### S07 — Qualification workbench

Rows are accepted requirements; columns are selected candidates. Each cell shows status text/icon, evidence strength, pending indicator where applicable, and concise reason. Expanding a cell shows target measurement, Earth measurement, comparison method/scale, threshold, evidence references, limitations and critic challenges. Keep `GAP` visually distinct from `FAIL`; keep `UNKNOWN` distinct from not-yet-computed.

A view toggle shows **By requirement** or **By candidate**. Filters can hide optional rows but display a persistent hidden-row count and never remove required failures from the summary. Sort/filter operations never recompute scientific states.

The critic review area shows challenge ID, affected claims, reason, requested evidence, severity, status and resolution receipt. When a revision changes a row, display **Previous → Current**, timestamp and responsible policy decision. A stale open panel shows a revision banner and refresh choice; it must not submit approval for the wrong revision.

### S08 — Rover–site compatibility

Three columns: rover declared limit/capability, proposed test requirement/measurement, assessment. Separate known hard violations, supported checks and unknown checks. Show energy-model assumptions and route dependence. Before a route exists, label the assessment **Preliminary**. Coarse terrain cannot certify 0.20 m ground clearance; that row remains unknown or scoped to an approved larger-scale proxy.

Declared stereo/LiDAR capability can satisfy a task prerequisite; it cannot certify autonomous navigation accuracy. Lack of actual mineral evidence leaves sampling composition unknown even if the rover declares a sampling instrument.

If rover absent: show the site investigation result and **Rover verification unavailable** with a new-run route using a selected rover. It is acceptable to create a new pinned run; never inject a rover into the immutable current run.

### S09 — Composite portfolio

Show requirement-to-site assignment, site-specific tests, unresolved rows, co-location constraints, site count and objective/penalty description. Users can compare supported alternative portfolios if returned by the backend; the UI cannot claim an optimum absent a computed optimizer receipt.

Show clearly when a requirement needs several exposures across campaigns versus one continuous co-located experiment. A 100 m segment at site A and 100 m at site B cannot satisfy a 200 m single-route exposure. Physical gaps remain regardless of site count. Unknown logistics remain unknown.

Each site has independent qualification, compatibility and test outcome. A portfolio summary never displays a single `PASS` while required site tests remain unverified. Export includes site responsibilities and residual gaps.

### S10 — PROVE IT benchmark preview and generated test

Before the first action, show the selected candidate, accepted requirements/benchmark preview, rover limits, required slope-band distances, terrain exposure, return/energy rules, known task/waypoint inputs, accepted assumptions and search budget. Unchosen route/base/zone details are **To be designed**, not invented map features. After the Test Designer commits an artifact, show its test zone, start/base, waypoint list with evidence type, exposures, length constraints, forbidden regions and task energy/time assumptions. Distinguish **task waypoints proposed by the user/agent** from **evidence-supported geological targets**.

Action **PROVE IT** is enabled when the server allows it. Disabled reasons list missing/invalid items; the frontend does not bypass them by constructing an alternate payload. Review accepted criteria/assumptions at this boundary. Submitting sends an idempotent `PROVE_IT` run action with expected revision and starts `DESIGNING_TEST`, followed by `VERIFYING` once the generated test validates against accepted criteria. It does not require a preexisting frozen route. If design introduces a material new assumption/proxy requiring review, show the exact affected values and pause dependent work through the documented review flow; approval cannot change mission or rover thresholds. Then wait for committed test/job/result IDs.

Route animation represents sampled modeled route positions. Before an actual route exists show the test zone, not a moving fictional rover. Once computed, playback can be scrubbed, paused and reset. Playback state does not send worker commands.

### S11 — Verification result, diagnosis and replan

Lead with **Modeled test passed**, **Modeled test failed**, or **Inconclusive**. Beneath, show each benchmark: rule, measured value, unit, residual/margin, status and evidence. Present route distance, exposure distances, maximum modeled slope, predicted reserve and waypoint access only when computed. Null is **Unknown**, never `0`.

For failure, show category and scope: a specific route failed; a required condition was absent in analyzed zone; evidence missing; search budget exhausted; or system error. Do not turn an optimizer timeout into a claim that the site is unusable.

The attempt timeline displays immutable attempt number, candidate/zone, parent attempt, changed elements, result and receipt. Compare routes side by side or as labeled overlays. For an automatic replan, show **Replanning within the accepted contract** and exact action; for a blocked new requirement, show **New contract required**. A terminal unsuccessful run offers passport export and supported retry/new-run options.

### S12 — Passport

Implement `19-ANALOG-PASSPORT-AND-EXPORTS.md`. Distinguish draft from immutable final export. Lead with scoped qualified uses and result, then unsupported conditions. Mode badge, contract/rover revisions, evidence digest and incomplete dimensions are always visible. Failed and inconclusive passports have full narrative/provenance treatment.

## 4. Operations drawer and evidence drawer

Operations is a structured event timeline and compact task graph. Each row shows timestamp, role/tool, action summary, status, linked evidence and decision/result. Ten conceptual roles can share one model; do not show ten simultaneous typing indicators. Tool activity derives from persisted events, never an animation script in live mode.

Role names: Mission Director, Requirements, Rover Systems, Planetary Target, Earth Analog Scout, Qualification, Scientific Critic, Test Designer, Verification & Replanning, Evidence/Passport. Deterministic tools have their own attribution. Show **Terrain engine computed slope histogram** rather than attributing that number to a model.

An expanded operation contains sanitized input summary, tool/version, started/finished timestamps, evidence IDs, safe output summary and resulting decision. It contains no raw secrets, hidden prompts or private chain-of-thought. A critic challenge links to the exact evidence/requirement and its resolution.

Evidence drawer shows claim, measurement type, source lineage, collection/product/granule, region, CRS/datum, acquisition time if relevant, source and comparison resolution, method/parameters, uncertainty, quality/no-data mask, checksums and limitations. Provide source links from trusted metadata; never render arbitrary agent-supplied HTML.

## 5. Shared failure-state behavior

| State | UX and allowed response |
|---|---|
| Loading initial data | Skeleton with section label; no example PASS values. |
| Background refresh | Keep previous data; mark last updated and connection status. |
| Network disconnect | Persistent “Updates paused” indicator; reconnect and resynchronize; no duplicate mutation. |
| API validation error | Field-specific message from structured envelope; preserve entered data. |
| Revision conflict | Show server/current revision difference; refresh or recreate proposed action. |
| Data missing or uncovered | Affected requirement `UNKNOWN`; inspect coverage and request supported follow-up. |
| Dataset credential/config failure | Name missing service/configuration without exposing a secret; allow other independent work. |
| Model unavailable | Preserve receipts/drafts; show retry after configured backoff; never downgrade to synthetic silently. |
| Worker queued | Queue state and elapsed time; cancel if permitted; no invented progress percentage. |
| Worker failed | Failed job ID, safe reason, available retry, committed artifact status. |
| Search budget exhausted | `INCONCLUSIVE`/`SEARCH_LIMIT`; report limits and any best-found route separately. |
| Evidence revision changed | Mark stale selection/action and require current revision; do not overwrite silently. |
| Unauthorized/inaccessible | Explain access limitation without leaking record contents. |

## 6. Human actions and API boundary

Use `POST /missions`, `POST /missions/{id}/revisions`, `POST /missions/{id}/fingerprint`, `GET /jobs/{id}`, `POST /missions/{id}/accept` and rover revision operations for authoring. Create a run with `POST /runs` and pinned revision IDs/mode. Run commands use `POST /runs/{id}/actions` with `action_type`, action-specific payload and `expected_revision`. Documented actions include `NOMINATE_CANDIDATE` (AOI/name), `SELECT_CANDIDATE` (candidate ID), `BUILD_PORTFOLIO` (candidate IDs/maximum sites), `SELECT_PORTFOLIO` (portfolio ID), `APPROVE_EVIDENCE`/`REJECT_EVIDENCE` (review/evidence IDs/comment), `PROVE_IT` (candidate ID), `RETRY` (dependency ID) and `CANCEL` (empty payload). Exact field spelling/types and valid states are authoritative in OpenAPI. If an intended interaction needs a missing command, implement the backend contract before rendering a functional UI control. Do not create client-only actions that appear persisted.

Read run snapshot and `/candidates`, `/qualifications`, `/tests` scoped by run ID. Read final passport and `/passports/{id}/exports/{format}`. All exact field names, action availability, idempotency headers and pagination follow `contracts/openapi.yaml`.

## 7. Screen acceptance criteria

- UX-001: A new user can complete mission → rover → accepted fingerprint → run without reading a JSON schema.
- UX-002: Both Moon and Mars targets remain geometrically distinct from the Earth analog map; all three selections survive refresh.
- UX-003: All accepted contract rows remain reachable through qualification, test and passport views, including gaps and unresolved rows.
- UX-004: The same selected candidate/requirement/evidence opens after copying its URL within an authorized workspace.
- UX-005: Invalid import, failed save or AI outage does not erase user input or create a fake accepted record.
- UX-006: Changing mission or rover after acceptance creates a new revision/run; old screens stay unchanged.
- UX-007: A critic challenge causes an observable evidence/revision change or remains unresolved; it cannot disappear without a resolution record.
- UX-008: A verification failure and later pass display separate attempts and exact changes with unchanged contract digest.
- UX-009: A zero-data region, no-candidate search and search timeout all have distinct complete UX, including export of the limited result.
- UX-010: The entire journey works at 360 px width, keyboard only and 200% zoom; maps have accessible lists/numeric alternatives.
- UX-011: No displayed live agent action or route position appears before a corresponding committed artifact/event exists.
- UX-012: Event disconnect/reload does not revert a final result to pending or duplicate any action.
