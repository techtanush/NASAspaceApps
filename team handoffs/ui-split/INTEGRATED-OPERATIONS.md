# Integrated operations handoff

14 November 2026. This describes the integration checkout's behavior and operating boundaries. It does **not** certify a completed current LIVE investigation or a final release gate. Preserve failed/blocked runs and their receipts; historical results from another checkout do not establish this checkout's result.

## Start with an isolated server environment

Run commands below from `analogforge/`, with the intended private `DATABASE_URL`, `DATA_ROOT`, `CONFIG_DIR`, ports and exact `ALLOWED_ORIGINS` already selected. Keep credentials server-side in ignored configuration; never use `VITE_*` variables for secrets. Do not copy live credentials into synthetic/browser-test profiles. Actual LIVE work requires real science/renderer implementations and disabled fake-provider/test-harness hooks.

For an already prepared database and installed dependencies, the source's development supervisor starts API, worker and real-backend web together:

```bash
rtk proxy env OPENAI_MODEL=gpt-5.4-mini AF_SCIENCE_IMPL=real AF_RENDERER_IMPL=real uv run --locked python scripts/dev_services.py
```

This is an explicit process-only model choice, inherited by API and worker. `gpt-5.4-mini` was selected from availability already present in the existing account; it is not an app-wide default or a capacity guarantee. Account limits remain external. **No billing, quota or account settings were changed.** Restart both API and worker after changing their environment or source. The normal `rtk make dev` additionally bootstraps, migrates, seeds synthetic fixtures and performs synthetic preflight; it is not a live-data readiness certificate.

## Durable investigation activity

`GET /api/v1/runs/{run_id}/activity?limit=25&cursor=...` is an additive, authenticated, workspace/run-scoped, read-only endpoint with `Cache-Control: no-store`. It is outside the frozen 43-operation schema. `limit` is 1–100; the opaque cursor is scoped to workspace/run. Pages are in ascending event sequence and return `items`, nullable `next_cursor`, and `last_event_seq`.

Each item has stable `id = run_id:seq`, `run_id`, `seq`, `event_type`, `created_at`, `state`, `status`, `summary`, and nullable `failure_code`, `task_kind`, `role`, `candidate_id`, `candidate_name`, `requirement_id`, `invocation_id`, `tool_receipt_id`, plus `evidence_ids`. Statuses are `RUNNING`, `COMPLETED`, `BLOCKED`, `FAILED`, `CANCELLED`, or `INFO`. On recognized failed/blocked terminal records, `failure_code` comes only from an allowlisted identifier in the persisted event's `payload.code`; the summary adds its fixed human explanation. Unknown, absent or unsafe codes remain null. Started, successful and cancelled records cannot acquire a failure code from other run/receipt metadata. A failed background job does not relabel an already completed investigation.

Summaries project actual committed events and authorized records. Workers commit start records before scientific/provider execution; completion or failure is a separate transition. A historical “Started” record does not mean the operation is still running: correlate terminal records by invocation and consult current run state. Reload/resync reads the durable history; SSE watermark changes trigger UI refresh. The UI displays at most the first 2,000 records with a limit notice; endpoint pagination remains available. No scripted scenario outcomes, estimated percentages, raw code, prompts or hidden reasoning are progress records.

Role completion events carry `role_result_id` and `evidence_count` rather than repeating a growing global evidence list inside the 16 KiB event envelope. The full canonical role result retains every evidence reference. Activity items additionally return nullable `role_result_id`, `evidence_count`, and `evidence_ids_truncated`; `evidence_ids` displays at most 128 unique authorized references. Counts come from the scoped stored records, not an unverified count in event text. A shortened display is explicitly marked and does not remove evidence from the result.

Source: [activity projection](../../analogforge/src/analogforge/application/activity.py), [router](../../analogforge/src/analogforge/api/routers/runs.py), [UI consumer](../../analogforge/apps/web/src/features/missionControl/RunActivity.tsx).

## Optional stored weather/context

Empty optional integration variables are listed in [optional-integrations.env](../../analogforge/config/examples/optional-integrations.env); the frozen kit `.env.example` remains byte-identical. Enable `ANALOGFORGE_ENVIRONMENT_CONTEXT=true` with server-side `METEOMATICS_USERNAME` and `METEOMATICS_PASSWORD`; default is false. Meteomatics uses those Basic-auth credentials, not a separate API-key field. `EARTHDATA_TOKEN` is a separate acquisition credential, not a weather login. Visualization routes separately require `ANALOGFORGE_VISUALIZATION=1`.

A leased LIVE worker captures context once after detailed Earth candidate analysis. Synthetic/replay/test-harness work never performs this acquisition. Limits are six candidate AOI midpoints, eight HTTP calls and 30 seconds shared across acquisition/verification/publication. Interrupted attempts remain unavailable rather than silently querying again.

`GET /api/v1/runs/{run_id}/environment` is authenticated, workspace-scoped, `no-store`, and **stored-only**: viewing or reloading never calls a weather provider. `schema_version` is `environment.v1`; common fields include `run_id`, `mode`, `status` (`CAPTURED` or `UNKNOWN`), `reason_code`, `earth_candidates`, `nasa_reference`, nullable `snapshot_sha256`, `limitations`, `qualification_supported: false`, and `operating_limits: []`. Captured snapshots also carry immutable input identities, capture time, omitted candidate IDs and budget metadata. `CAPTURED` does not mean every source item succeeded. Disabled/missing credentials, absent/interrupted capture, unsupported geometry, source/storage failures and exhausted budgets remain explicit reasons; corrupted stored context fails closed.

Earth samples describe one point and a declared UTC window. NASA REMS is historical Curiosity rover-point reference context; selected Mars AOI applicability remains `UNKNOWN`. Neither establishes current/global Mars weather, climatic analogy, operating safety limits, qualification evidence or candidate ranking. See [capture/projection](../../analogforge/src/analogforge/application/environment.py) and [science handoff](../tanush/SCIENCE-HANDOFF.md).

## Identity and model behavior

`AUTH_MODE=local` requires a loopback API host. `GET /auth/session` automatically returns the fixed local `OWNER` identity, `auth_mode: local` and null CSRF token. The UI labels this “Local workspace / Owner”; there is no meaningful local account sign-in/out gate. Local `/auth/login` is disabled; clearing cookies does not remove automatic local identity.

Configured OIDC uses `AUTH_MODE=oidc`, HTTPS `PUBLIC_BASE_URL`, `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, a `SESSION_SECRET` of at least 32 characters, exact origins and administrator-provisioned workspace membership. Backend login is `GET /auth/login?workspace_id=<uuid>`, followed by `/auth/callback`; logout is `POST /auth/logout` with matching Origin and `X-CSRF-Token`. Secure cookies/session revocation are real backend behavior. Current Mission Control supplies an identity badge, not a complete OIDC account-management screen. See [auth routes](../../analogforge/src/analogforge/api/routers/auth.py).

Live models require `OPENAI_API_KEY` and explicit `OPENAI_MODEL`. Optional fallback requires `GROQ_FALLBACK_ENABLED=true`, separate `GROQ_API_KEY`, and explicit `GROQ_MODEL`. Only primary HTTP 429 permits a sticky switch; authentication/schema failures do not select another provider. Groq output is capped at 1,024 tokens; primary role requests retain 4,096. Groq `openai/gpt-oss-20b`/`120b` use documented low reasoning effort because reasoning shares that output budget. Every actual attempt/correction is charged within the six-per-invocation/40-per-run ceilings. Exactly one serial tool call, strict schemas, authorized references and one correction remain enforced. Incomplete/repeated invalid output stays `MODEL_OUTPUT_INVALID`; oversized input is `RESOURCE_LIMIT`; rate limits remain provider failures. No partial proposal is accepted to make a run appear successful. See [client](../../analogforge/src/analogforge/adapters/openai/client.py) and [provider loop](../../analogforge/src/analogforge/agents/runtime/openai_provider.py).

## Regional terrain, coverage and benchmark limits

The acquired local sources are genuine MOLA MEGDR (`mola-gale-v3`) and NASADEM HGT (`nasadem-flagstaff-v002`) regional crops. Their source identities, native posting, frame preparation, bounds, height references and checksums are described in the [acquisition runbook](../../analogforge/LOCAL-LIVE-RUNBOOK.md). The isolated regional profile uses 500 m analysis/comparison support and 12 km candidate windows; this does not turn native posting into effective measurement resolution. The operator-reviewed demonstration criterion is not a NASA-calibrated suitability threshold. Terrain crops supply neither mineral/thermal equivalence nor physical rover validation. An unreviewed reference set establishes no historical novelty.

Global globe imagery is `VISUAL_CONTEXT_ONLY`; attractive coverage on a globe does not provide quantitative regional evidence. With visualization enabled, `GET /api/v1/visualization/coverage` takes `body`, `bbox=w,s,e,n`, `scenario_config_id` and optional `dataset_lock_id`. Its `COVERED/PARTIAL/NONE/UNKNOWN` result describes a validated locked **footprint**, not valid-cell completeness or mission PASS. Missing/stale preparation stays `UNKNOWN`; polar/dateline-spanning boxes are unsupported. Prepare metadata explicitly, outside GET:

```bash
rtk proxy uv run --locked analogforge visualization prepare-coverage --dataset-lock <selected-lock-id>
```

`GET /api/v1/runs/{run_id}/visualization/candidates/{candidate_id}/benchmarks` reads accepted requirements and pinned qualifications. Numeric values require the exact registered comparison artifact, accepted criterion, candidate lineage, units/support and any necessary candidate-scoped verifier ancestry. Otherwise the value remains null/Unknown. This endpoint computes no new score, margin or measurement. GAP/UNKNOWN and nonnumeric criteria remain visible; without a rover, compatibility/verification remain unassessed/not run as applicable. The visualization schema is available at `/api/v1/visualization/openapi.json`.

An algorithm/configuration version or support change requires a **new run**, with the reviewed contract and intended source-policy lock; do not retry an old run into a different pinned algorithm configuration. Rebuild coverage metadata when configuration/source identities change. Keep original datasets/locks immutable and use fresh dataset/policy IDs for changed inputs. Acquisition/lock/bind command syntax is documented in the runbook and implemented in [CLI](../../analogforge/src/analogforge/cli.py). This handoff adds no new test, provider or final-green claim.
