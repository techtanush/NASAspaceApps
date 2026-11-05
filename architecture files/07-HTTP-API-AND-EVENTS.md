# HTTP API and committed events

Implement `/api/v1` endpoints from `contracts/openapi.yaml`. The file is JSON syntax, which is valid YAML 1.2; OpenAPI version is 3.1.0. Domain definitions reference `domain.schema.json`. Generate the frontend client from the implementation's exported OpenAPI and check it against this contract.

## Conventions

JSON errors have `{error:{code,message,request_id,retryable,details}}`. Return 401 unauthenticated, 403 unauthorized action, 404 absent or inaccessible object, 409 idempotency/revision/state conflict, 413 oversized upload, 422 invalid input, 429 quota, 503 unavailable required service. Never return HTTP 200 with an embedded error as a replacement for correct status codes.

Every mutation requires `Idempotency-Key`, an opaque UUID selected once by the client for that user action. Reuse returns the original response for the same body; changed body returns IDEMPOTENCY_CONFLICT. Mutable parent updates/actions require `expected_revision`. DB commit performs compare-and-swap; stale clients receive REVISION_CONFLICT and current revision, then refetch. Do not automatically repeat an obsolete semantic action after a conflict.

List endpoints accept `limit` 1–100 and opaque `cursor`; default 25. Responses are `{items,next_cursor}`. Use stable created_at+id ordering. For simple run read models GET `/runs/{id}` contains result IDs and latest selected versions. Never paginate scientific rows without preserving which snapshot version they describe.

## Mission and rover setup

- `POST /missions`: save name, objective, target, optional draft requirements and assumptions. Return header/current draft; it is not accepted yet.
- `GET /missions/{id}`: header, draft and revision references.
- `GET /mission-drafts/{id}`: complete saved draft including objective, target, proposed requirements and assumptions. `POST /missions/{id}/drafts` with expected_revision and draft creates the next immutable draft save; use it for debounced autosave. Accepted scientific revisions are separate.
- `POST /missions/{id}/revisions`: create a new proposed structured revision. Validate units/requirements; return revision ID and content hash.
- `POST /missions/{id}/fingerprint`: enqueue Requirements preparation for current draft, mode, optional rover_revision_id and expected_revision. Return preparation/job IDs. It must not create a scientific run with an unaccepted contract.
- `POST /missions/{id}/accept`: accept exactly `revision_id` using the expected parent revision. Requirements and assumptions must have been displayed; persist actor/time/hash.
- `POST /rovers`: validated manual or parsed JSON RoverInput; create immutable revision and return profile.
- `GET /rovers/{id}` and `POST /rovers/{id}/revisions`: retrieve and revise. Imported JSON is the same input shape; a browser can parse a bounded 64 KiB file before posting. Do not accept arbitrary binary CAD.
- `GET /jobs/{id}`: preparation or run job state, progress step, safe error, nullable proposed_revision_id. Authorize through its parent context.

## Investigation and user actions

`POST /runs` freezes accepted mission_revision_id, nullable rover_revision_id, mode, dataset lock ID, and scenario configuration ID. Reject unaccepted contracts, body mismatch, mutable/live-unlocked manifests when the scenario requires reproducibility, and missing live AI key. An unavailable optional layer does not block unrelated requirements.

Capabilities expose available/default scenario_config_ids and dataset_locks. GET `/configuration/scenarios/{id}` returns safe preset metadata and default policy lock. Snapshot preserves scenario_config_id/dataset_lock_id. The UI must not guess these required IDs. GET `/compatibility` on a no-rover run returns409 ROVER_REQUIRED; the UI normally skips that fetch and displays site-only mode.

`GET /runs/{id}` returns RunSnapshot. `GET /runs` lists recent runs. A command sent to `POST /runs/{id}/actions` contains `action_type`, `expected_revision`, and a typed `payload`:

| Action | Payload | Valid effect |
| --- | --- | --- |
| SELECT_CANDIDATE | candidate_id | Select an existing same-run candidate after qualification; no scientific status changes. |
| NOMINATE_CANDIDATE | name, aoi | Queue analysis for an Earth AOI within quotas; origin USER_SUPPLIED. |
| BUILD_PORTFOLIO | candidate_ids, max_sites | Queue coverage optimizer after qualification; max_sites 1–5. |
| SELECT_PORTFOLIO | portfolio_id | Select existing same-run portfolio. |
| APPROVE_EVIDENCE | review_id, evidence_ids, comment | Resolve a permitted assumption/proxy review. Does not create missing measurements or override physical constraints. |
| REJECT_EVIDENCE | review_id, evidence_ids, comment | Reject proposal, retain issue and schedule allowed alternative or end with unresolved evidence. |
| PROVE_IT | candidate_id | Freeze test design and queue verification; requires rover and mandatory modeled inputs. |
| RETRY | dependency_id | Retry a blocked, now-addressable dependency with unchanged inputs and remaining budget. |
| CANCEL | empty object | Persist cancellation request; worker stops safely and retains completed evidence. |

Return HTTP 202 with command/job IDs and current run revision when work is queued. State policy rejects actions not legal for the current state. CANCEL can be idempotent in terminal states. Selected candidates and portfolios cannot be silently replaced by UI optimism; render server confirmation.

Read endpoints: `/target-profiles/{id}`, `/candidates?run_id=`, `/candidates/{id}`, `/qualifications?run_id=&candidate_id=`, `/tests?run_id=`, `/tests/{id}`, `/test-results/{id}`, `/portfolios/{id}`, `/evidence/{id}`, `/passports/{id}`. RunSnapshot includes nullable selected_candidate_id and selected_portfolio_id for authoritative selection restoration. GET `/artifacts/{sha256}` requires access through a workspace-owned evidence/export reference, supports byte ranges when applicable, and sets content type/nosniff. Guessing a blob hash grants no access.

Exports: GET `/passports/{id}/exports/{format}` where format is `html`, `json`, or `csv`. HTML is self-contained printable content; CSV is a bounded flattened qualification table with formula injection escaping. If an export is not prepared, return 202 job status plus Retry-After; the frontend polls until the authorized artifact exists. Exports reflect the passport's frozen revision.

Successful export headers: correct `Content-Type` (`text/html; charset=utf-8`, `application/json`, `text/csv; charset=utf-8`), safe `Content-Disposition: attachment; filename=...`, `ETag` containing byte hash, `X-Artifact-SHA256` with exact file-byte digest and `X-Content-Type-Options: nosniff`. The passport manifest digest is separate from these file digests.

Durable operations are queryable beyond SSE retention: `GET /agent-actions?run_id=&limit=&cursor=` returns AgentAction records; `GET /tool-receipts/{id}` returns a sanitized ToolReceipt with evidence references. `GET /critiques?run_id=&candidate_id=` returns EvidenceRecord(kind=CRITIQUE) records whose artifact JSON validates as CritiqueIssue. QualificationDimension.critique_evidence_ids links every applicable issue/review version. `GET /reviews/{id}` returns ReviewRequest, also embedded as pending_review in RunSnapshot, with evidence IDs and a reviewable proposal artifact. No hidden provider reasoning is exposed.

GET `/display-layers?run_id=&candidate_id=&target_profile_id=` returns DisplayLayerManifest records. Each names an authorized image hash, affine pixel-to-world transform, display CRS, dimensions, units, legend, source evidence/support and transparency policy. Earth image overlays are rendered in Web Mercator and supply four WGS84 corners in NW,NE,SE,SW order; planetary images use a separate planar panel with their body-specific transform and null earth_corners. Six affine coefficients use GDAL order `[x_origin,x_pixel,x_row_rotation,y_origin,y_column_rotation,y_pixel]`. They are display artifacts, never inputs to the scientific verifier. No interpolation/color scaling creates new evidence resolution.

The first PROVE_IT command authorizes deterministic test design and verification within already reviewed accepted requirements and rover assumptions. Before that, show a benchmark preview rather than claiming a route/test exists. Pause if design uncovers a new material assumption; a mission threshold or rover-model change requires a new accepted revision/run. Evidence approval cannot edit those frozen inputs.

## SSE contract

GET `/runs/{id}/events?after=0`, `Accept:text/event-stream`. Cookies authenticate same-origin EventSource. Accept Last-Event-ID on reconnect; if both cursor inputs exist use the larger valid sequence, scoped to this run. Send `id:<seq>`, `event:<event_type>`, `data:<RunEvent JSON>` and a blank line. Sequence is run-local, monotonic and assigned in the same transaction as result publication.

Event families: `run.state_changed`, `agent.started`, `agent.completed`, `tool.started`, `tool.completed`, `evidence.created`, `qualification.updated`, `critic.issue_created`, `review.required`, `test.designed`, `verification.completed`, `replan.started`, `passport.created`, `run.blocked`, `run.cancelled`, `run.failed`. Heartbeat comments every 15 seconds do not advance the cursor. Read persisted events in ascending pages of 100; poll DB every 1 second while connected. A future LISTEN/NOTIFY optimization must not replace DB replay.

Retain events for at least 30 days. If cursor predates retained data, return HTTP 410 EVENT_CURSOR_EXPIRED with a snapshot URL before streaming; the client refetches and resumes from snapshot.last_event_seq. If a run completes, send the terminal committed event; the browser closes EventSource. Delivery is at least once. Client deduplicates by run_id+seq. On reconnect it always refetches the snapshot to recover events that arrived before listener registration.

## Health and capabilities

`GET /health/live` verifies process liveness only. `/health/ready` verifies DB and migration compatibility; missing optional data is not an unhealthy API. Authenticated `/capabilities` reports configured modes, boolean credential availability, worker heartbeat age, installed adapters, dataset lock states, and supported exports. It never returns secret values, provider account identifiers, or raw environment variables.

## Acceptance

Contract tests cover every operation, each action/state combination, revision conflict, duplicate request, cross-workspace object, and SSE replay. A frontend reload must reconstruct the exact current scientific state without relying on prior local events.
