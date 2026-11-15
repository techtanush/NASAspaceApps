# Groq fallback for live model requests

This extends the Tanush backend delivery at `8744335a8d3b1abcf77053e2f03510b7dd48044f`. It is independent of Aradhya's frontend work and does not change the frozen API, science ports, database schema, requirements, acceptance process, or verification algorithms. `VALIDATION.json` remains the historical visualization report for that earlier delivery; the additional provider checks are recorded in `GROQ-VALIDATION.json`.

## Configuration and activation

Keep the existing server-side `OPENAI_API_KEY` and explicit `OPENAI_MODEL`. Add these settings to the deployment's private environment or ignored `.env`:

```dotenv
GROQ_FALLBACK_ENABLED=1
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<private Groq credential>
```

The secondary model is an explicit operator choice, never a guessed production default. Both Groq credentials and model must be present when enabling fallback; invalid partial configuration fails typed settings validation. A supplied but disabled secondary key never activates routing. `GROQ_FALLBACK_ENABLED=0` restores primary-only routing.

Use the existing OpenAI Python SDK against Groq's native Responses API. The Groq origin is fixed to `https://api.groq.com/openai/v1`; OpenAI and Groq have separate SDK clients and credentials. No extra package, browser-side key, subscription change, paid-account upgrade, or new cloud deployment is required by this code.

On this machine the supplied credential is saved in ignored, mode-0600 `.runtime/groq.env` in the Tanush app and in the original local rehearsal's existing private `.env`. Neither is committed. The already-running original rehearsal does not hot-reload backend Python/configuration. Its old process must be replaced with this branch's tested source and restarted at the normal integration/deployment step to activate routing; do not claim that editing private configuration updated a running server. Keep accepted/published historical runs and dataset locks intact.

## Exact routing behavior

1. Healthy OpenAI requests continue using their explicitly configured primary model.
2. An OpenAI HTTP 429 enables the separately configured Groq fallback. This covers rate/quota exhaustion; it does not grant either account additional quota.
3. Before the extra Groq HTTP request, reserve another request from the existing applicable budget. If reservation fails or preparation was cancelled/superseded, send no secondary request.
4. Keep the selected Groq provider for the remainder of that client's tool conversation. Never switch providers back in the middle of tool continuation.
5. A worker engine shares only a monotonic cooldown deadline across its clients. The default cooldown is 60 seconds; a numeric `Retry-After` is bounded to 1–300 seconds. A new conversation after cooldown tries OpenAI again. Other processes have their own cooldown. No conversation, source content or workspace identifiers are shared by this state.
6. Auth failures, malformed requests, unsupported schemas, refusals, invalid proposals, timeouts and HTTP 5xx never initiate a provider switch. Existing bounded transport/HTTP retries remain in the role provider, and SDK automatic retries stay disabled for both clients. A Groq HTTP 400 with the exact `tool_use_failed` code is classified as rejected model generation and shares the existing single schema-correction allowance. Only fixed safe feedback is sent; the provider's `failed_generation` is never parsed, executed, persisted or replayed. For strict JSON drafting/probing, Groq `json_validate_failed` similarly receives at most one fixed-feedback correction with the same strict schema; that extra HTTP request is reserved from the preparation budget before sending. Repeated generation errors or invalid proposals fail closed; other HTTP 400 errors are not retried by these rules.
7. If the secondary is also rate limited, the existing bounded retry path returns `PROVIDER_RATE_LIMITED`. There is no scripted or synthetic substitution for live output and no third provider.

Only explicit text messages and correlated local function calls/results cross providers. Opaque response/item IDs and provider reasoning/encrypted reasoning are stripped. Tool call IDs, names, JSON arguments and verified tool outputs retain their correlation. Unsupported continuation kinds fail closed. The secondary receives the same task, allowed tools and strict result schema; no built-in web browsing, arbitrary code execution or remote MCP tool is enabled.

## Budget, persistence and scientific integrity

- Role invocations count **every actual HTTP attempt** against both `model_requests_per_invocation` and `model_requests_per_run`, including a primary 429 followed by Groq. The local loop also enforces the invocation cap when no ledger callback is supplied. Existing limits are unchanged.
- Mission preparation keeps its existing separately persisted four-dispatch cap. The initial dispatch is reserved durably before generation; every secondary/correction dispatch is reserved under the current job lease before sending. No database transaction is held during provider inference.
- Live role invocation documents retain `provider_attempts`: actual provider, explicit model, HTTP-attempt outcome, and HTTP error status when available. This is private operational metadata, without keys, prompts, response bodies or reasoning.
- Preparation records persist the same attempt trace on success and failure, set `provider`/`model` to the actual last provider used, and record actual dispatch count in `usage_json`. Lost leases cannot publish a proposal. Budget exhaustion remains `BLOCKED`.
- The same WireCodec, strict result parsing, evidence membership checks, policy validation, deterministic semantic validation, publication fencing and user acceptance gates apply to both providers. A capability probe is compatibility evidence, not scientific validation.
- Synthetic and replay modes never construct a live model provider. Scientific measurement, route verification, provenance and assurance continue through their existing deterministic code.
- Secrets remain `SecretStr`, excluded from public configuration and effective hashes. Sanitization also removes `groq_api_key` fields and embedded `gsk_` credentials. Rotating a key does not change scientific configuration hashes.
- Disabled fallback preserves the previous public configuration/hash shape. Enabling fallback adds only a non-secret provider/model/trigger policy to effective settings, so new runs declare their model-routing configuration. Historical accepted records are not rewritten to adopt it.

## Preflight and real-provider evidence

The live preflight uses the same routing configuration for its two strict checks: a local function call and a separate structured JSON continuation. Both are bounded to 1,024 output tokens. The successful gate identifies the actual selected provider/model. This does not increase provider-account limits.

The supplied key authenticated successfully. Both GPT-OSS models passed real Groq strict-tool and structured-continuation checks. The 120B model was near its daily token allowance and also returned a tool-generation error in a later full role request. The configured `openai/gpt-oss-20b` subsequently passed a representative mission-director role through the actual application provider, with a simulated primary 429 and real Groq inference. The final check exercised a registered read tool, one safe generation correction, secondary rate-limit failures, and a validated submission: six actual requests, six charges, within the unchanged cap. A separate real Groq mission-drafting check also passed, preserving all supplied fields and keeping the proposal unaccepted, with two attempts/two charges and no stored records. These checks prove the exercised protocol/role/preparation paths; it does not certify all roles, a complete NASA mission, physical science validity, or unlimited account capacity. See `GROQ-VALIDATION.json` for exact checks and limitations. Never replace a failed role with the result of a tiny capability probe.

## Checks for the merger

Run the complete platform suite with real science and renderer implementations, the frozen kit tests/verifier, strict typing, lint, forbidden-pattern scan and platform mutation checks. The validation report separates the broad regression run started before the final generation-correction additions from the final provider/preparation regression rerun after those additions; their counts overlap and must not be added together. The focused additions cover primary health, credential isolation, 429 switching, other HTTP/transport failures, cooldown expiry, hidden-reasoning removal, mid-conversation switching, actual attempt charges, cap exhaustion, simultaneous provider limits, invalid evidence, preparation lease/budget/acceptance boundaries, settings/hash/secrets, preflight routing, and success/failure attribution.

Merge this branch with Aradhya's independently owned UI from the common handoff base. No frontend imports or contracts need to change for fallback. Restart the integrated backend/worker with private configuration and run the documented real-backend browser journeys. Do not mark the overall UI delivery complete from these backend checks.

## Official references

- [OpenAI rate-limit handling](https://developers.openai.com/api/docs/guides/rate-limits)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Groq native Responses API](https://console.groq.com/docs/responses-api)
- [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
- [Groq local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling)
- [Groq model catalog](https://console.groq.com/docs/models)
- [Groq account limits and response headers](https://console.groq.com/docs/rate-limits)
