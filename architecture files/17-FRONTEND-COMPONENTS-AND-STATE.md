# Frontend implementation, components and state ownership

This is an implementation design for React 19, TypeScript, Vite, React Router, TanStack Query and MapLibre GL JS. It is not a second API schema. Generate transport types from `contracts/openapi.yaml`; use `05-DOMAIN-MODEL-AND-CONTRACTS.md` and `07-HTTP-API-AND-EVENTS.md` for exact persistence and transport behavior. Pin dependency versions during preflight and record them in the lock manifest.

## 1. Directory responsibilities

Proposed application layout:

```text
frontend/src/
  app/                 router, providers, error boundary, workspace context
  api/generated/       generated OpenAPI client/types; never hand-edit
  api/client.ts        base URL, auth transport, structured errors, idempotency
  api/queryKeys.ts     stable workspace-scoped query key factories
  api/runStream.ts     SSE parser, cursor, reconnection, resynchronization
  features/missions/   setup, fingerprint proposal, revision/acceptance review
  features/rovers/     manual editor, import parser, revision viewer
  features/runs/       run shell, snapshot queries, commands, state selectors
  features/targets/    body-aware target selection and profile
  features/analogs/    Earth candidate list, filters and nomination
  features/qualification/ matrix, evidence cells, critic review
  features/compatibility/ rover-versus-test assessment
  features/portfolio/  site assignments, residual gaps, alternatives
  features/testLab/    proposal, attempts, benchmarks, playback and diagnosis
  features/passport/   final report and exports
  components/ui/       buttons, forms, dialogs, table, status, live region
  components/evidence/ receipt viewer, lineage tree, uncertainty/scale labels
  components/operations/ role/task graph, activity timeline, challenge cards
  maps/                Earth MapLibre adapter, planetary panel, layer registry
  format/              unit/date/number formatting and null handling
  styles/              design tokens, responsive layouts and print styles
```

Keep domain modules dependent on generated API types and shared presentational components, not on each other's mutable stores. Run selectors create view models from server objects. Do not duplicate qualification logic in React, a map layer expression, or a chart tooltip.

## 2. State ownership rules

| State | Owner | Persistence / constraints |
|---|---|---|
| Mission draft and accepted revisions | API + PostgreSQL | Frontend form is a working buffer until save acknowledged. |
| Rover profile/revisions | API + PostgreSQL | Imported local file is untrusted input until validated/persisted. |
| Accepted contract, pinned rover and mode | Run snapshot | Immutable; no local setter. |
| Run state, review availability, allowed actions | API | Buttons use server-allowed actions; backend rechecks. |
| Candidate measurements/qualification | API artifacts | Render immutable referenced versions; no optimistic PASS. |
| Critic challenge state | API | Local collapsed/expanded state does not resolve a challenge. |
| Test geometry/results and energy values | Worker artifacts/API | Browser can animate or inspect; cannot calculate authoritative results. |
| Portfolio coverage and site responsibilities | API | Frontend can request a proposal but cannot declare union coverage itself. |
| Passport/export status | API artifact | Download only published immutable export, or label draft clearly. |
| Current section, candidate, requirement, evidence, attempt | Router/search params | Validate against current run/workspace. |
| Drawn unsaved AOI, unsubmitted text, form errors | Feature-local React state | Warn on navigation if genuinely unsaved; no secrets. |
| Map viewport/layer toggles, drawer widths, playback frame | Local component state | May persist harmless preferences; never changes scientific artifacts. |
| SSE connection/cursor/retry timer | One run-stream controller | Cursor applies only to its workspace/run; no cross-run reuse. |

Use TanStack Query for server state and small local reducers/hooks for transient UI state. A global state library is not needed initially. Do not maintain a second long-lived copy of the whole run in context. Context supplies workspace ID, runtime configuration and selected run ID; query cache supplies data.

## 3. Query keys and data loading

Centralize key factories. Conceptual key shape:

```text
['workspace', workspaceId, 'missions', filterKey]
['workspace', workspaceId, 'mission', missionId, revisionId]
['workspace', workspaceId, 'rover', roverId, revisionId]
['workspace', workspaceId, 'run', runId, 'snapshot']
['workspace', workspaceId, 'run', runId, 'candidates', filterKey]
['workspace', workspaceId, 'run', runId, 'qualifications', version]
['workspace', workspaceId, 'run', runId, 'tests', attemptId]
['workspace', workspaceId, 'run', runId, 'evidence', evidenceId]
['workspace', workspaceId, 'passport', passportId, revision]
```

Normalize filter keys deterministically, including page/cursor where appropriate. Never omit workspace ID. Immutable versioned artifacts can be cached for the browser session and refetched on explicit invalidation; mutable snapshots use stream-driven invalidation and a conservative fallback polling interval while disconnected. Avoid repeated full raster downloads from query hooks; maps use authorized artifact tile/image endpoints.

Load run shell from `GET /api/v1/runs/{id}`. Fetch only the visible tab's detailed records plus shared summary. The snapshot lists immutable artifact IDs/versions. Avoid requesting every candidate's complete raster/lineage payload on first render. Candidate and event lists paginate. Fetch evidence details on demand; prefetched small metadata is allowed.

Loading, stale data, unavailable evidence and transport error are different states. Query exceptions enter a structured `ApiError` view containing safe message, code, retryability, field errors and request/correlation ID. Render no raw stack trace or credential-bearing URL.

## 4. Mutation protocol

Every persisted command has one stable idempotency key for its logical submission and the expected revision required by the API. Disable only the relevant action while pending. Do not disable independent navigation or evidence inspection.

Sequence:

1. Validate local structure and display missing fields without sending invalid data.
2. Snapshot user intent and current revision. Generate one command idempotency key.
3. Submit using generated client. Transport retries reuse exactly the same payload/key.
4. On acknowledgement, invalidate/refetch the run snapshot and affected collections. Job acknowledgement is **queued**, not completed.
5. On uncertain network outcome, resynchronize first; reuse the same key for retry. Never manufacture a new key merely because a response was lost.
6. On revision conflict, fetch current snapshot and show what changed. An outdated review cannot be automatically approved against new evidence.
7. On validation/policy error, preserve the user's input and show actionable safe details. Do not translate a rejected action into a local successful state.

Optimistic updates are allowed for harmless view preferences and reversible draft text with visible unsaved state. They are prohibited for accepted revisions, scientific qualification, critic resolution, verification outcomes and final passport publication.

Draft autosave is debounced and revision-guarded. Abort obsolete network requests where possible, but still handle a late committed save by its returned revision. If two tabs edit the same draft, surface a conflict and offer explicit merge/review or reload; do not use last-write-wins silently.

The preparation operation `POST /missions/{id}/fingerprint` creates a preparation job. Poll `GET /jobs/{id}` until it returns the proposed mission revision or fails. It does not invent a run ID or pretend a run is executing before the contract is accepted.

## 5. Event stream and cursor resynchronization

One stream controller exists per mounted run shell. It opens `GET /api/v1/runs/{id}/events?after={seq}` and supports `Last-Event-ID` according to the API. Use a tested SSE parser over authenticated fetch transport, so transport behavior matches the generated client rather than depending on unsupported header assumptions. Heartbeats are connection health signals, not domain events.

Persisted events use a monotonically increasing run-local sequence. `GET /runs/{id}` supplies a consistent snapshot with `last_event_seq`. The server must replay committed events after that cursor, including events committed between snapshot fetch and stream connection.

Client algorithm:

```text
mount(workspace, run):
  fetch snapshot
  reject snapshot from wrong workspace/run
  render its artifact references and state
  lastApplied = snapshot.last_event_seq
  open stream after lastApplied

on event e:
  validate event envelope and workspace/run identity
  if e.seq <= lastApplied: ignore duplicate
  if e.seq != lastApplied + 1: resynchronize snapshot; reopen stream
  else:
    append safe activity row / mark indicated query keys stale
    lastApplied = e.seq
    schedule bounded batched refetch for changed references

on disconnect:
  show updates-paused indicator
  retry with bounded exponential backoff and jitter, after lastApplied
  on reconnect: resynchronize snapshot; reopen after returned cursor

on cursor expired / malformed event / unknown incompatible event:
  stop current stream
  fetch authoritative snapshot
  refetch referenced active artifacts and paginated recent operations
  replace cursor with snapshot cursor
  reopen stream

on run/workspace change or unmount:
  abort fetch/stream; clear retry/refetch timers and stale closures
```

After a terminal committed event, fetch the final snapshot/artifact references, close the stream deliberately, and cancel reconnect timers. Do not interpret intentional terminal closure as a disconnect. If an API-supported later action produces a new run revision, revalidate state before starting a new stream.

Domain event payloads are hints for cache updates and operations rendering, not authority to create a full qualification row from prose. A committed artifact reference can be fetched immediately. Status updates must not move backward when a slower stale snapshot resolves; compare snapshot revision/cursor and discard older responses. A duplicate terminal event cannot trigger a second export or action.

Coalesce invalidations arriving in a burst; cap operations rendered in memory and use list virtualization/pagination for history. Keep stream cursor independently from the visual page of events, so scrolling older history does not reopen the stream at an old cursor.

Proposed reconnect delays: 1, 2, 4, 8 and 15 seconds with bounded jitter, then at most 15 seconds between attempts. Reset after a stable connection. On hidden tabs, pause route playback and reduce nonessential polling; on visibility return fetch a current snapshot. No reconnect creates another scientific job. Respect explicit rate-limit/retry guidance from the server.

## 6. Component contracts

Component input names below describe view models, not wire schema fields. Convert from generated types in selectors.

| Component | Inputs | Emits / responsibility |
|---|---|---|
| `RunWorkbenchShell` | run ID, snapshot/query state | Navigation, pinned context, stream lifecycle, drawer slots. |
| `RuntimeModeBadge` | immutable run mode, source detail | Always-visible live/replay/synthetic label; no toggle for existing run. |
| `RunStateBanner` | state, blocker, allowed actions, connection | Safe state description and exact available actions. |
| `MissionDraftForm` | draft revision, validation | Save new draft revision and fingerprint request. |
| `FingerprintReview` | proposed/accepted contract, assumptions | Explicit acceptance; accepted mode is read-only. |
| `RequirementEditor` | draft requirement, quantity definitions | Validate units/rule; never edit accepted row. |
| `RoverProfileEditor` | profile revision, validation | Save new revision, optional fields with unknown state. |
| `RoverImportPreview` | parsed candidate/errors | Accept import or return to edit without persistence side effects. |
| `PlanetaryRegionPicker` | body, CRS/longitude metadata, region | Supported preset or numeric/drawn region; body-safe geometry. |
| `TargetProfilePanel` | target artifacts, coverage | Charts/metadata with evidence links. |
| `EarthCandidateMap` | Earth geometries, selection, allowed overlays | Select candidate; never recompute qualification. |
| `CandidateList` | paginated summaries, filters | Selection/compare/nomination intents. |
| `QualificationMatrix` | requirements, candidate assessment versions | Accessible cells, filters, evidence/challenge selection. |
| `QualificationStatus` | exact status, pending flag, reason | Text + icon + color; no inference from null values. |
| `EvidenceStrength` | category, uncertainty/limitations | Dimension-specific support; no fabricated numeric confidence. |
| `CriticChallengeCard` | challenge and resolution refs | Request supported review action, expand comparison. |
| `CompatibilityTable` | assessment revision, rover/test refs | Distinguish preliminary known/unknown constraints. |
| `PortfolioCoverage` | computed portfolio, site tests | Assignment table, residuals, objective receipt. |
| `TestProposalReview` | accepted benchmark preview, generated test if already available, allowed action | First PROVE IT starts design+verification; generated test renders only after commit; new material assumptions use explicit review. |
| `AttemptTimeline` | attempt summaries, selected attempt | Navigation among immutable attempts. |
| `BenchmarkResults` | measured benchmark records | Rule, measurement, residual, result, evidence. |
| `RoutePlayback` | computed route and sampled metrics | Local play/pause/scrub; never sends motor/job commands. |
| `ReplanDiff` | parent/current test artifacts | Exact changed geometry/parameters and fixed-contract proof. |
| `AgentOperations` | paginated safe events and task refs | Filter roles/status, inspect receipts; no hidden reasoning. |
| `EvidenceDrawer` | authorized evidence metadata/artifact refs | Lineage/details and source links. |
| `AnalogPassportView` | immutable report snapshot | Human-readable result and export links. |

## 7. Data presentation and form invariants

- Use a single quantity formatter; `null` renders **Unknown** or context-specific no-data label. Do not coerce null, undefined, infinity or NaN to zero.
- Round for display only. Tooltips/export JSON preserve original computed precision and units. Comparison against thresholds occurs server-side using defined tolerance.
- Percent values such as battery reserve retain explicit percent semantics; `20` is not silently converted to `0.20` in a payload unless schema conversion explicitly requires it.
- Display units in table headings and field labels; never rely on placeholders. Degree labels distinguish slope angle from geographic coordinates.
- Parse editable decimal values carefully; allow intermediate input like `0.` without destructive coercion. Validate on blur/submit and retain field text on error.
- All timestamps come from server UTC values; show user-local time with timezone and allow precise ISO value in receipts. Playback time is modeled elapsed time, not acquisition time.
- Maintain a deterministic status mapping in one place; unknown server enum values trigger a safe unsupported-state notice and snapshot refresh.
- Do not use HTML from model output. Render prose as text or sanitized constrained Markdown with restricted links. Content security policy must match authorized artifact sources.

## 8. Maps, charts and performance boundary

Create MapLibre instances once per mounted Earth map; update sources/layers through the adapter, clean up on unmount, and use stable feature IDs for selection. React remains owner of selection and layer toggles; the map remains owner of instantaneous viewport/pointer state. Do not push every pointer movement into global React state.

Terrain visualization consumes prepared raster/tiles and vectors, not large raw scientific arrays serialized into component props. Heavy transformations belong to backend workers. A small image reprojection/paint for display may run in a browser worker only if it does not create authoritative measurements. Lazy-load map/chart modules and cap plotted points through server-generated display series with disclosed aggregation. Preserve full-resolution receipts separately.

Charts need table alternatives for slope bands, uncertainty, route distance/exposure and energy. Hover is optional; keyboard/focus selection retrieves the same values. Do not smooth charts in a way that hides a hard-limit violation. See `18-MAPS-LAYERS-AND-VISUAL-DESIGN.md` for body/CRS boundaries.

## 9. Accessibility and navigation

Use semantic landmarks, a skip link, visible focus, labeled buttons and native controls where possible. Modal drawers trap focus only while modal; desktop nonmodal side panels do not steal focus. Closing a dialog returns focus to its trigger. Live regions announce stage changes and terminal results, not every sample/event. Keep an accessible complete operations list independent of the visual DAG.

Validation includes linked error summary and per-field descriptions. Critical status never depends on red/green. Tables have headers/captions and a meaningful reading order. At narrow widths use stacked comparison cards or labeled overflow; do not shrink labels to unreadability. Honor reduced motion; stop playback when its tab is hidden. Exports have an accessible download name including mission, mode and revision.

## 10. Frontend acceptance tests

Use component tests for real branch logic and a browser journey for cross-screen behavior; do not test implementation details such as the number of hook calls.

| ID | Required verification |
|---|---|
| FE-001 | Accepted mission/rover cannot be modified by editing a local query-cache object or form; new edits create revision workflow. |
| FE-002 | Qualification/benchmark null values render unknown; zero is rendered as a valid measured zero only when supplied. |
| FE-003 | Duplicate, out-of-order and missing stream sequence trigger the defined ignore/resync paths without duplicate commands. |
| FE-004 | Snapshot older than current rendered revision cannot overwrite terminal state or newer artifact references. |
| FE-005 | Stream closes/timers cancel on run switch; no old-run event appears in the new run. |
| FE-006 | A lost mutation response retries with the same key/payload; revision conflict requires refreshed review. |
| FE-007 | Fingerprint preparation failure preserves the mission draft; successful job yields a proposed revision requiring acceptance. |
| FE-008 | Invalid rover JSON never persists or mutates the selected pinned rover. |
| FE-009 | Every status and required action is understandable without color, hover or pointer input. |
| FE-010 | Synthetic/replay badges survive navigation, refresh, drawer open, print and export. |
| FE-011 | Route playback renders only committed geometry and its local controls cannot change outcome. |
| FE-012 | Qualification, compatibility and verification remain three distinct view models and have distinct result labels. |
| FE-013 | Missing dataset coverage, expired stream cursor, disconnected network and failed worker each render the specified recoverable state. |
| FE-014 | Workspace change clears/isolates queries and stream; unauthorized artifact detail is never reused from another workspace. |

Implementation is ready when these pass with a real API adapter, plus the product scenarios in `28-DEMO-SCENARIOS-AND-ACCEPTANCE.md`. Mock transport fixtures are useful for isolated tests but do not fulfill live integration acceptance.

## Scientific claim presentation

Implement an assurance/evidence view using the required passport assurance_evidence_id and resolved JSON artifact. Display exact audited scope, mode, validation level, support, uncertainty/proxy limits, essential unknowns and issue restrictions. Missing audit stays incomplete; no client-derived PASS/confidence/coverage or hidden required row. See [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) and Aradhya's personal07 guide.
