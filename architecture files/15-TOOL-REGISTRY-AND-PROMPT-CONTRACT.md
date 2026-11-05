# Tool registry and model-facing contracts

## Purpose and provider boundary

Implement a typed adapter between role prompts and application services. The worker sends server-side Responses API requests. Every callable function uses `strict: true`; object schemas disallow additional properties and declare every property required, using nullable types for optional values. Function outputs are JSON strings correlated to their original `call_id`. These provider mechanics follow the [official OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling). The application's authorization and scientific validation remain separate controls.

Use `OPENAI_API_KEY` only in the backend/worker environment and `OPENAI_MODEL` as an explicit configured model identifier. Capability-test the chosen model with the actual supported tool/structured schemas before allowing live mode. Provider request details and supported options must be checked against the installed SDK and [Responses API documentation](https://developers.openai.com/api/docs/guides/migrate-to-responses); lock the SDK and successful preflight result. Do not hardcode a model name, infer account access, or expose secrets to the browser. This document specifies application design, not a guarantee about any model's quality or availability.

No built-in web search, shell, computer-use or arbitrary code tool is exposed to production roles. Dataset discovery/fetching is through source adapters and host allowlists. External source text is untrusted data. Do not let a retrieved document expand the tool allowlist. Do not log provider hidden reasoning or ask roles to return chain-of-thought. If the provider requires opaque continuation items, pass them through the adapter in memory, with no UI rendering or application decision extraction.

## Prompt assembly

Construct each request in this order:

1. Common policy from `prompts/COMMON-SYSTEM-POLICY.md`.
2. Role instructions from the exact versioned `agents/*.md` document translated into a compact runtime prompt.
3. Machine-generated task context: IDs, mode, accepted revision hashes, task kind, budgets, allowed action enum, relevant contract fields and evidence summaries.
4. Untrusted source excerpts inside labeled source-data fields containing source ID and content hash; never concatenate them into privileged instructions.
5. Prior tool receipts and role proposals needed for this invocation, excluding irrelevant conversational history.

Hash and persist the exact prompt bundle version and sanitized task payload. The documentation files are implementation specifications; the production prompts should contain the executable policy rules, not every explanatory paragraph. Snapshot-test the generated prompt and allowlist. Any prompt change that affects decisions changes the prompt version in run provenance.

## Preparation jobs and accepted-run tasks

Mission Fingerprint is prepared before a run exists. `POST /api/v1/missions/{id}/fingerprint` creates a `PreparationJob` using `preparation_id`, `workspace_id`, `mission_id`, `draft_revision_id`, `mode`, `invocation_id`, prompt/config versions and budgets. Its `run_id` is null. The preparation-specific model envelope is `PreparationTask`; the stored output is `PreparationRoleResult`, not the run-scoped `AgentRoleResult`. Preparation receipts are scoped to `preparation_id` and cannot masquerade as run evidence. They stage schema/interpretation results, not planetary observations.

`PreparationRoleResult` fields are `schema_version`, `id`, `workspace_id`, `preparation_id`, `mission_id`, `draft_revision_id`, `mode`, `created_at`, `invocation_id`, `role` (literal `requirements`), `status` (`SUCCEEDED`, `BLOCKED`, `FAILED`), `summary`, typed `payload` and nullable `error_code`. All fields required; no additional properties. `PreparationTask` contains those context IDs plus `task_kind` (`draft_contract` or `revise_draft`), source mission text, target revision, optional rover revision, accepted-assumption references, allowed tools/actions and remaining budgets. The backend generates strict schemas; no fake run UUID is generated for preparation. Preparation has a four-model-call total cap including retries. Saved rover revisions are optional draft context, without a separate rover acceptance endpoint.

`POST /api/v1/missions/{id}/accept` records the exact accepted contract revision/hash and consequential assumption acceptance. `POST /api/v1/runs` then freezes that contract and optional saved rover revision. Main-run Requirements invocations use `validate_accepted_contract` only: they summarize/check fixed requirements and never regenerate thresholds. Evidence review and PROVE IT are run actions from `07-HTTP-API-AND-EVENTS.md`; they do not accept a new mission revision inside the old run.

## Common model task input

Every execution-run role receives an `AgentTask` object. Fields marked nullable must be present with null when unavailable. Implement Pydantic models and strict JSON Schemas alongside the domain definitions in `contracts/domain.schema.json`; do not maintain divergent hand-written wire formats.

| Field | Type and validation |
|---|---|
| `schema_version` | string literal `1.0` |
| `workspace_id`, `run_id`, `invocation_id` | UUID strings; injected by server, never trusted from model |
| `role_key` | ten-role enum from orchestration document |
| `task_kind` | role-specific enum; no free-form recursive delegation |
| `runtime_mode` | `live`, `replay`, `synthetic` |
| `expected_run_revision` | nonnegative integer |
| `contract_revision_id`, `rover_revision_id` | accepted mission UUID; saved rover UUID or null for qualification-only work; both immutable |
| `contract_hash`, `rover_hash` | accepted mission SHA-256; rover SHA-256 or null exactly when no rover selected |
| `input_evidence_ids` | unique UUID array; all must be readable in workspace/mode |
| `accepted_assumption_ids` | unique UUID array; exact accepted revision only |
| `allowed_actions` | server-generated finite action enum array |
| `budget` | remaining model calls, tool calls, wall seconds and output tokens |
| `payload` | strict role/task-discriminated object, described per role |

The model does not supply tenant identity, lease token, credentials, file paths or arbitrary URLs in tool arguments. The adapter injects hidden execution context from the invocation. A mismatched context in a submitted result is rejected; do not silently fix the result and label it model-authored.

## Common terminal role submission and persisted result

Every role ends with `submit_role_result` exactly once. The argument is a model-facing `RoleSubmission`, shown below, not the persisted `AgentRoleResult` envelope. Persist the argument as an uncommitted proposal before policy validation; submission disposition is not a scientific verdict. During preparation this same tool accepts the preparation-task-specific typed payload and stores `PreparationRoleResult` after validation.

The persisted run-scoped `AgentRoleResult` must match `contracts/domain.schema.json`: `schema_version`, `id`, `workspace_id`, `run_id`, `mode`, `created_at`, `invocation_id`, `role`, `status`, `proposed_next_state`, `evidence_ids`, `receipt_ids`, `summary`, `payload`, `error_code`. Context fields/IDs/timestamp are injected by server. Map validated submission `role_key` to `role`; COMPLETE to SUCCEEDED when policy accepts, missing dependency/review/budget to BLOCKED as appropriate, invalid unrecoverable execution to FAILED. `proposed_next_state` is nullable and computed from the allowed action by policy, not an unrestricted state from the model. Store the submitted typed role payload plus decision metadata under a strict internally generated payload wrapper; the domain schema's generic payload object is a transport envelope, not permission for untyped model output. Preserve `issues`, `assumption_ids`, `next_action`, `disposition`, and `task_kind` in that wrapper and append auditable events. `receipt_ids` come from actual executed tool receipts.

```json
{
  "schema_version": "1.0",
  "role_key": "scientific_critic",
  "task_kind": "review_qualification",
  "disposition": "NEEDS_EVIDENCE",
  "summary": "Obstacle clearance cannot be assessed from the available DEM scale.",
  "evidence_ids": ["20000000-0000-4000-8000-000000000001"],
  "assumption_ids": [],
  "issues": [{"code": "RESOLUTION_INSUFFICIENT", "severity": "BLOCKING", "requirement_id": "10000000-0000-4000-8000-000000000001", "evidence_ids": ["20000000-0000-4000-8000-000000000001"], "message": "The evidence does not resolve 0.20 m obstacles.", "recommended_action": "record_unknown"}],
  "next_action": "record_unknown",
  "payload": {"review_revision_id": "30000000-0000-4000-8000-000000000001", "objections": [], "accepted_claim_ids": [], "gate_recommendation": "REPAIR_REQUIRED"}
}
```

This is a synthetic contract example. It is not evidence about a real site. Required common fields are exactly those shown. `disposition` enum: `COMPLETE`, `NEEDS_EVIDENCE`, `NEEDS_USER_REVIEW`, `NO_VALID_ACTION`, `BUDGET_EXHAUSTED`. `summary` is a concise decision explanation, maximum 800 characters. `evidence_ids` and `assumption_ids` are unique references. Requirement IDs are opaque stable within-contract strings (for example R-SLOPE-EXPOSURE), never restricted to UUID format. Constraint/task IDs are stable strings in their frozen artifacts. Record, evidence, invocation and run IDs remain UUIDs. Example requirement strings happen to have UUID form; this is not a UUID requirement. Each issue has the shown fields, severity `INFO`, `WARNING`, or `BLOCKING`, nullable `requirement_id` (stable string or null), and one allowed recommended action. `next_action` must be in the server-issued `allowed_actions` or null when terminal. `payload` is a discriminated strict per-role schema; examples in role files show payload only. Do not accept a generic untyped map in production.

Internal model aliases `role_key`, `runtime_mode`, `contract_revision_id`, and `contract_hash` map to persisted `role`, `mode`, `mission_revision_id`, and `content_sha256` respectively. Never serialize the internal aliases as extra fields in the strict public domain envelope. `measurement_evidence_ids` always references EvidenceRecord UUIDs holding derived measurements. Individual `MeasuredMetric.metric_id` values are registered metric-name strings inside those records, not invented UUID measurement rows. Runtime search-termination aliases map to persisted TestResult.search_status: ROUTE_FOUND→FOUND, EXHAUSTIVE_NO_ROUTE→EXHAUSTIVE_INFEASIBLE, LIMIT_REACHED→BUDGET_EXHAUSTED. DATA_BLOCKED uses NOT_RUN or ERROR according to actual execution; cancellation is a job/invocation event and creates no fake TestResult. A role submission cannot contain an arbitrary computed score; numeric values in payload must be evidence-derived or explicitly declared proposed assumptions. Policy validates reference closure, units, range, contract hash and evidence freshness. A schema-valid payload can still be scientifically invalid.

## Tool receipt and evidence contracts

All tools return the model-facing `ToolExecutionResult` envelope below. It is distinct from persisted `ToolReceipt`; the server creates IDs/context and sanitizes exceptions. A receipt ID is null until a terminal receipt exists. `tool_call_id` is the application call UUID, while provider `call_id` is an opaque adapter correlation string and is never assumed to be a UUID.

Persisted `ToolReceipt` matches the domain schema exactly: `schema_version`, `id`, `workspace_id`, `run_id`, `mode`, `created_at`, `invocation_id`, `tool_name`, `tool_version`, `input_sha256`, nullable `output_sha256`, `evidence_ids`, terminal `status` (SUCCEEDED/FAILED/BLOCKED), nullable `error_code`, `elapsed_ms`, `cache_hit`. Runtime PENDING belongs to jobs/events rather than a prematurely successful receipt. Runtime PARTIAL maps to terminal SUCCEEDED only when a valid limited result exists; its partialness, missing coverage and warnings remain explicit in evidence and result payload. DATA-blocked work maps to BLOCKED. Cancelled work emits cancellation/job events and no successful scientific receipt; no evidence is synthesized. Preparation jobs use a separate preparation-scoped receipt envelope with `preparation_id` and null run context, not the run ToolReceipt schema.

```json
{
  "schema_version": "1.0",
  "tool_call_id": "40000000-0000-4000-8000-000000000001",
  "receipt_id": "90000000-0000-4000-8000-000000000001",
  "tool_name": "analyze_earth_candidate",
  "tool_version": "1.0.0",
  "status": "SUCCEEDED",
  "runtime_mode": "synthetic",
  "input_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "output_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "evidence_ids": ["20000000-0000-4000-8000-000000000001"],
  "artifact_ids": ["50000000-0000-4000-8000-000000000001"],
  "result": {"candidate_revision_id": "60000000-0000-4000-8000-000000000001", "analysis_revision_id": "70000000-0000-4000-8000-000000000001", "coverage_fraction": 1.0, "measurement_evidence_ids": ["80000000-0000-4000-8000-000000000001"], "warnings": ["Synthetic raster fixture; no field inference permitted."]},
  "error": null,
  "job_id": null
}
```

`receipt_id` is a persisted ToolReceipt UUID or null while pending/cancelled. Status enum: `SUCCEEDED`, `PARTIAL`, `PENDING`, `FAILED`, `CANCELLED`. `result` is a strict tool-specific object or null. `error` is null or `{code, detail_code, message, retryable, retry_after_seconds, affected_requirement_ids}`; `code` uses `contracts/error-codes.json`, `detail_code` is a nullable internal diagnostic enum, and affected requirement IDs are stable strings; seconds can be null. `job_id` is non-null only when pending or referencing the job that produced a terminal receipt. `output_hash` is null when no output exists. A PARTIAL receipt must explicitly list missing data; it is not permission to assume complete coverage. A PENDING receipt is not evidence for any quantitative claim.

An `EvidenceRecord` references raw source product/granule ID, retrieval time, checksum, mode, source body/CRS/datum, algorithm/version/config, input evidence IDs, output artifact IDs, measurement method and units, horizontal scale, nodata coverage, uncertainty, direct/proxy classification and limitations. See `contracts/domain.schema.json`. Quantitative tool results link to evidence; the model repeats summaries only. Source download receipts prove acquisition, not scientific comparability.

## Canonical registry

All tool args below are strict objects; all shown properties are required. Use null for omitted nullable selections. IDs resolve server-side. Every mutating command is invoked with an adapter-injected idempotency key derived from invocation, provider call ID, tool name and canonical arguments. Pure computations deduplicate by canonical input/config hash. Function descriptions tell the model when to call and what must not be inferred.

| Tool | Arguments | Successful `result` fields | Side effect and role access |
|---|---|---|---|
| `get_run_snapshot` | `{sections: enum[]}` allowed values contract, rover, target, candidates, qualification, critic, tests, budget | `run_revision`, requested sanitized section snapshots | Read; all roles, scoped to task |
| `inspect_contract` | `{contract_revision_id: uuid}` | accepted flag, hash, requirements, assumptions, unresolved fields | Read; all roles |
| `validate_mission_draft` | `{draft: MissionTestContractDraft}` | `valid`, normalized draft, violations, assumption proposals, acceptance blockers | Deterministic validation; Requirements preparation tasks only |
| `validate_rover_profile` | `{profile_revision_id: uuid}` | valid, normalized capabilities, missing fields, cross-field violations | Read/derived receipt; Rover Systems |
| `resolve_dataset_coverage` | `{subject_revision_id: uuid, dataset_family: enum, measurement_kinds: enum[]}` | approved product IDs, coverage geometry/artifacts, resolution, time range, license/access state, gaps | Catalog query; Target, Scout, Critic |
| `fetch_dataset` | `{product_id: string, subject_revision_id: uuid, selection_id: uuid}` | source artifact IDs, source checksums, metadata, coverage | Approved fetch job; Target, Scout. `selection_id` must originate in catalog receipt |
| `characterize_target` | `{target_revision_id: uuid, measurement_spec_id: uuid, source_evidence_ids: uuid[]}` | target profile revision, measurement IDs, scale, comparison support, warnings | Scientific job; Target |
| `screen_earth_candidates` | `{search_region_set_id: uuid, target_profile_revision_id: uuid, contract_revision_id: uuid, max_candidates: integer}` | ranked candidate revisions, feature-only scores, eligibility reasons, search extent, excluded candidates | Deterministic screen job; Scout. max <= run budget |
| `analyze_earth_candidate` | `{candidate_revision_id: uuid, measurement_spec_id: uuid, source_evidence_ids: uuid[]}` | candidate/analysis revision IDs, coverage fraction, measurement IDs, warnings | Scientific job; Scout |
| `compare_requirement` | `{requirement_id: string, candidate_revision_id: uuid, target_profile_revision_id: uuid, evidence_ids: uuid[]}` | proposed status, predicate result, comparable scales, measurement IDs, uncertainty, unmet parts, limitations | Deterministic evaluator; Qualification, Critic |
| `assess_rover_compatibility` | `{rover_revision_id: uuid, candidate_revision_id: uuid, test_revision_id: uuid_or_null, evidence_ids: uuid[]}` | compatibility rows, hard-limit conflicts, unknown dimensions, energy-assumption IDs | Deterministic evaluator; Rover Systems, Test Designer, Verification/Replanning |
| `review_evidence_bundle` | `{bundle_revision_id: uuid, check_set: enum[]}` enums provenance, modes, units, crs, scale, proxies, coverage, uncertainty, contract_integrity | finding IDs, blocker IDs, checked claim IDs, coverage summary | Deterministic audit; Critic, Passport |
| `design_test` | `{contract_revision_id: uuid, rover_revision_id: uuid, candidate_revision_id: uuid, strategy: enum, waypoint_set_revision_id: uuid_or_null}` | test draft revision, requirement-to-benchmark mapping, search spec, validation blockers | Deterministic benchmark assembly/validation; Test Designer |
| `search_route` | `{test_revision_id: uuid, search_config_revision_id: uuid, exclusion_mask_revision_id: uuid_or_null}` | attempt ID, candidate route ID or null, search termination reason, limits used, coverage | CPU job; Test Designer, Verification/Replanning. No PASS solely from finding path |
| `verify_route` | `{test_revision_id: uuid, route_revision_id: uuid}` | TestResult revision, PASS/FAIL/INCONCLUSIVE, constraint rows, violations, modeled energy, limitations | Deterministic verifier; Verification/Replanning |
| `diagnose_verification` | `{result_revision_id: uuid}` | failure categories, violated constraints, evidence IDs, permitted repair kinds, proof scope | Deterministic classification aid; Verification/Replanning |
| `optimize_portfolio` | `{contract_revision_id: uuid, candidate_revision_ids: uuid[], max_sites: integer}` | portfolio revision, requirement/site assignments, uncovered/gap/unknown requirements, objective/tiebreak details | Deterministic coverage optimization; Director, Scout, Qualification. default 3, hard cap 5 |
| `get_evidence` | `{evidence_ids: uuid[], include: enum[]}` metadata, measurements, limitations, lineage, source_excerpt | scoped evidence summaries, missing IDs, artifact links | Read; all roles, max 20 IDs/call and bounded excerpt size |
| `compare_evidence` | `{left_evidence_id: uuid, right_evidence_id: uuid, comparison_kind: enum}` scale, geometry, metric, uncertainty | comparable boolean, reasons, harmonization spec ID or null | Deterministic audit; Target, Scout, Qualification, Critic |
| `build_passport_manifest` | `{run_revision: integer, selected_candidate_revision_ids: uuid[], portfolio_revision_id: uuid_or_null}` | passport draft revision, claim map, source manifest, validation blockers, artifact draft IDs | Deterministic assembly/render queue; Passport |
| `submit_role_result` | `RoleSubmission` strict discriminated schema | proposal ID, validation status, violations, committed revision or null | Proposal submission; all roles. Backend policy owns commit |

The source-policy lock permits catalog queries/acquisition of additional granules within its pinned product versions, allowed extents and quality policy. Fetch appends an immutable asset-manifest entry and never rewrites an existing input hash. A newly discovered allowed granule does not require a new run; changing a locked source version/policy does. Passport freezes the final asset manifest.

Dataset family enums correspond to installed approved adapters: NASADEM/SRTM, MOLA, LOLA, EMIT, Diviner and future explicitly registered sources. Do not infer a source supports a measurement because its name is recognized. Geometry is passed by subject revision ID; target body and CRS are never inferred from bare coordinates.

`measurement_spec_id`, `search_config_revision_id`, `search_region_set_id`, and `waypoint_set_revision_id` refer to immutable server-validated configuration revisions. Agents choose from server-provided eligible IDs; they cannot inject arbitrary formulas, SQL, raster paths, code, or unbounded global polygons. A tool may propose a new config for user review through a role result, but cannot silently install it.

## Authorization, execution and errors

Order of checks: parse strict schema; verify invocation active; enforce role allowlist; enforce workspace scope; validate referenced revisions and mode; check accepted contract hash; check budgets/cancellation; validate tool-specific constraints; execute; validate output schema; persist receipt/evidence; return sanitized envelope. No handler can bypass these checks because it is called internally.

Canonical error codes come from `contracts/error-codes.json`; do not create a competing wire-code registry. The more specific internal reasons below are `detail_code` values only, with these mappings:

- `VALIDATION_ERROR`, `FORBIDDEN_TOOL`, `WORKSPACE_SCOPE_MISMATCH`, `MODE_MISMATCH`, `PROXY_UNACCEPTED` → `INPUT_INVALID`; deny before handler execution, fail or block according to policy, and do not repeat an unauthorized tool call. HTTP authorization endpoints still use their specified 403/404 behavior; internal function calls are not public HTTP requests.
- Stale input → `REVISION_CONFLICT`. `LEASE_LOST` → `WORKER_LOST`; the stale worker cannot publish. `RUN_CANCELLED` creates a cancellation event rather than a scientific error/FAIL.
- `COVERAGE_MISSING` → `NO_COVERAGE`; `RESOLUTION_INSUFFICIENT` → `SCALE_INCOMPATIBLE`; `DATUM_UNRESOLVED` → `UNSUPPORTED_CRS`; unusable masks → `INSUFFICIENT_VALID_DATA`. Affected scientific dimensions remain UNKNOWN, not GAP.
- Source transport outage → `SOURCE_UNAVAILABLE`; provider 429 → `PROVIDER_RATE_LIMITED`; provider/tool timeout → `TOOL_TIMEOUT`. Use at most three total transport attempts including initial.
- `SEARCH_LIMIT_REACHED` → `SEARCH_LIMIT`, preserving INCONCLUSIVE and counters. This is a valid bounded scientific result, not permission for unlimited transport retries.
- `ARTIFACT_CORRUPT` → `SOURCE_CHECKSUM_MISMATCH`; corrupt source bytes → `SOURCE_CONTENT_INVALID`; invalid structured model/tool proposal → `MODEL_OUTPUT_INVALID`. Quarantine unsupported output; do not attach its numbers to qualification.

Use exponential backoff with jitter for transient retries, respecting server retry-after; default 2 and 4 seconds before the two retries (three total attempts including initial), capped at 60 seconds. Retry budget is worker-controlled. Model cannot classify its own malformed call as a network retry to evade budgets. Never ask the model for credentials.

## Receipt-to-claim enforcement

For each quantitative role payload field store a measurement/evidence reference or explicit assumption proposal. Policy resolves every evidence ID, verifies its tool receipt terminal state and artifact checksum, confirms context compatibility and confirms that the cited measured field actually supports the claim. Mere existence of an evidence ID is insufficient.

A result with a slope histogram can support terrain-distribution comparison at its declared scale. It cannot support centimeter obstacle clearance, actual traction, autonomous-navigation accuracy, real sampling completion, field safety, access permission, or flight readiness. Sensor presence proves only declared capability. Missing mineral or thermal products produce UNKNOWN for those dimensions; terrain resemblance cannot substitute for them. Earth gravity/atmosphere mismatch is GAP only for a requirement explicitly demanding planetary environmental replication, not every possible field task.

## Completion and acceptance

- Generate provider tool schemas from Pydantic, then fail preflight if strict schemas include unsupported optional fields or permit extra properties.
- Every role sees only its allowlist; attempt to invoke an unlisted tool is rejected before execution.
- Unknown IDs, stale hashes and mixed modes never reach scientific handlers.
- Every successful compute tool yields an evidence record and reproducible artifact/config hashes.
- A pending fetch, cancelled analysis, malformed tool output or no-coverage result cannot establish PASS.
- Scripted role fixtures using these same contracts run synthetic mode with no external key and all network/provider clients disabled.
- Replay uses recorded role/tool outputs and rejects an unrecorded new call.
- Provider refusal, partial stream and malformed function arguments are visible typed failures; no parser falls back to prose-based decisions.
- Logs and SSE contain approved summaries and receipts, with no credentials or hidden reasoning.
- Contract tests cover all tool argument/result variants and each role payload. Science correctness tests remain in the deterministic tools, not prompt string assertions.
