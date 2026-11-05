# Tanush implementation plan

Proceed autonomously within your owned scope. Keep `team handoffs/tanush/implementation-status.md` with checkpoint, commit, base contract, tests and exact external blockers. Preserve existing user work and stop a dangerous/contradictory operation rather than silently overriding another owner.

## T0 Verify branch and baseline

Confirm you are inside the Tanush worktree and the named branch. Run team/document validation. Read architecture00/03/04/05/06/07/14/15/20/21/22/23/26/27/32 and shared service boundaries; use the reading map for role specifics. Inventory files before scaffolding. Implement one app under `analogforge/`, not a `tanush-app` separate from the other contributions.

## T1 Deliver F0 quickly

Scaffold Python package, dependencies/uv lock, Postgres/PostGIS Compose service, API/worker images and four isolated runtime profiles. Verify native science imports in the worker image even before science modules arrive. Create Pydantic public models consistent with architecture contracts and required semantic validators. Provide `/api/v1/health/live`, ready and safe capabilities. Add exported OpenAPI command.

Create `ports/science.py`, `ports/passport_renderer.py`, artifact/mode/cancellation/source-policy interfaces as described in shared03. Include operation-specific input/result models, typed collaborator test doubles and contract tests. Provide `make bootstrap`, `dev`, `migrate`, `test`, `generate-client`, `build`, `seed-synthetic`, `preflight` commands; frontend build target may delegate to Aradhya's later package instead of generating her files.

F0 exit: clean checkout starts DB/API/worker, settings invalidity is clear, modes and scenario IDs visible, dependencies locked, ports importable and schema export matches accepted C1. Commit and submit exact F0 SHA for integration into main. Do not wait for all roles/science/UI before sharing this foundation.

## T2 Durable domain and evidence

Implement migration order in06; drafts versus accepted revisions, optional rover input, content hashes, idempotency and expected-revision CAS. Implement pre-run Requirements preparation separately from run-scoped invocations. ACCEPT points to immutable content; rover saves create revisions with no separate rover-accept endpoint.

Implement blob write/fsync/hash/atomic-rename then metadata commit, lineage DAG and source-policy/final-asset manifests. Evidence is append-only. Ayan returns draft local keys; your registrar allocates UUIDs and resolves parents/results before exposing receipts. Reject missing cross-workspace/mode/artifact references. Do not persist an invented PASS if a producer returns incomplete evidence.

Exit: import/accept/run APIs, artifact round trip and negative/unknown states pass on real Postgres. No private tokens in source URLs or errors. Provide actual retrieval for drafts, target profiles, operations, receipts, critiques, reviews, display layers and exports, not only write endpoints.

## T3 Durable worker and public operations

Implement claim/lease120s/heartbeat20s/fencing/reaper, bounded retries and subprocess cancellation. Commit run-event sequence with result publication. Preserve immutable context across crash/resume; expired owner cannot publish. Provide authoritative RunSnapshot selection pointers and pending reviews. SSE replays committed rows, handles cursor expiry and heartbeat without depending on browser lifetime.

Start scripted synthetic roles and fake typed science only in platform tests to exercise persistence/state transitions. Production modes report scientific capability unavailable until Ayan's facade is installed. Integrate S0 as soon as delivered; replace collaborator doubles in integration tests.

Exit: restart API/worker, lose lease, replay events, cancel active work and duplicate/revision-conflicting mutations behave correctly. No late PASS after cancellation. No network in synthetic/replay.

## T4 Agent Council and policy

Implement ten role configurations from architecture `agents/`, shared tool registry and strict model schemas. Use one explicitly configured server-side model. Tool callers receive scoped IDs/evidence and approved actions; no raw SQL/shell/secret access. Store sanitized public action summaries and actual receipts.

Preparation proposes thresholds for user review; accepted-run Requirements only validates frozen input. Target/scout/qualification call Ayan's facade. Critic creates concrete evidence-linked issues; missing science cannot be waived into truth. Test Designer uses frozen criteria; Verification/Replanning reads independent results and requests legal route/zone/site repair. Evidence role assembles only supported claims. Policy, not model prose, commits statuses/transitions.

Set40 model calls including retries,900 active seconds,3 replans(two same-candidate repairs plus one candidate switch) and preparation4-call cap per architecture. Keep lower per-invocation budgets and tool caps. Missing key/model/access blocks live mode with remediation; do not select an invented model or switch silently to fixture output.

Exit: scripted all-role tests and real capability probe where authorized; malformed/unsupported/fabricated/injected/stale outputs rejected; real critic repair and independent result produce visible decisions.

## T5 Complete application wrappers and reporting

Connect candidate nomination/discovery, qualification, compatibility, SELECT actions, no-rover flow, portfolios, test design/search/verify/diagnose and bounded replan. Reuse scientific outputs; preserve first failures and exact changes. Build manifest including final acquired-asset hash and all input/result/evidence versions.

Load Aradhya's renderer behind the typed port. Serve asynchronous HTML/JSON/CSV exports with correct MIME/filename/file hash/ETag and frozen manifest digest. Keep full evidence unknowns and physical gaps in successful modeled-terrain passports. User review cannot revise a frozen threshold in place.

Exit: real combined synthetic UI→API→science→verifier→renderer flow works, both attempts exist in DB, file/manifest hashes agree and full unknown/negative/no-rover states remain inspectable.

## T6 Integrate and harden

Follow shared02 with isolated merge candidates from exact tested SHAs. Import F0, S0/U0, then S1/U1/P1 incrementally. Run full tests after actual module connections; adapt contracts with recorded accepted changes rather than copying branch files manually. Use integration profile and separate test DB. Respect branch ownership while repairing cross-boundary defects.

Complete local security, workspace isolation, quotas, source allowlists, logs/redaction, recovery/backups and reproducible launch. Hosted identity architecture is preserved as a later deployment gate; no public server or deployment is needed for this task. Run live Earth/Mars/Moon/provider gates only with authorized inputs and record unsupported ones.

## T7 Deliver exact evidence

Run own05 plus combined gates. Update58-row traceability with code/test references, gate report and actual command results. Produce clean build/run instructions, tested commit/merge refs and demo mode declaration. The final report distinguishes your code, integrated software, synthetic arithmetic, actual downloaded sources, actual model calls and unresolved physical/source requirements. Continue fixing ordinary failures; ask humans only for real missing choices/credentials, never for routine reversible fixes.

## Mandatory scientific implementation checkpoint

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
