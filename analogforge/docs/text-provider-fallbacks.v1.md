# Optional text-provider fallbacks

The primary remains `OPENAI_API_KEY` / `OPENAI_MODEL`. Enable an explicit ordered
fallback chain with `MODEL_FALLBACK_ORDER`, a JSON array such as
`["groq","nvidia"]`. Each enabled provider requires its own `*_API_KEY` and
explicit `*_MODEL`. Names are `GROQ`, `OPENROUTER`, `ANTHROPIC`, `SAMBANOVA`,
`NVIDIA`, and `GEMINI`. OpenRouter additionally requires `OPENROUTER_UPSTREAM`
to pin one upstream provider. Credentials are `SecretStr`; neither credential
values nor private environment files enter effective public configuration hashes.
The ordered provider/model identities do enter the hash.

Omitting the order preserves the previous `GROQ_FALLBACK_ENABLED` behavior.
An explicit `[]` disables every fallback, including legacy Groq opt-in. Merely
providing a key enables nothing. Settings do not automatically load
`.runtime/provider-fallback-keys.env`; the live launcher must load this ignored
private file explicitly. Non-live launchers must clear all seven provider keys,
all provider model variables, and the fallback order. The tracked optional
template is `config/examples/optional-integrations.env`; the frozen kit example
and core OpenAPI are unchanged.

Only HTTP 429 advances to the next configured provider. Authentication failures,
invalid schemas or output, transport failures, and server errors do not advance
the chain. Existing explicitly budgeted role transport retries/corrections remain;
there are no SDK retries, automatic model substitutions, provider-side OpenRouter
fallbacks, or billing/account changes. Shared process cooldowns retain only
provider deadlines, never conversation data. Active invocations remain on their
selected fallback; new invocations skip providers currently cooling down.

The primary defaults to a 4096 role output cap. Optional `OPENAI_MAX_OUTPUT_TOKENS`
can lower it to an integer from 256 through 4096; it cannot raise the ceiling or
raise an individual request’s smaller allowance. Non-default values are included
in the effective public configuration hash; the legacy default hash is unchanged.
Every fallback is capped
at 1024 output tokens, including reasoning where the provider counts it. Each
additional dispatch first charges the caller's existing request/cancellation/
lease fence. Six requests per invocation and forty per run remain unchanged.
A seven-provider configured chain cannot visit all seven within a single
six-request invocation; choose the order deliberately. Incomplete output fails
closed. Provider failures never imply scientific success.

## Transport and scientific boundaries

| Provider | Transport | Acceptance gate |
| --- | --- | --- |
| OpenAI, Groq | Stateless Responses; strict functions; serial calls | Existing schema, wire alias, authorization, evidence, and scientific checks |
| OpenRouter | Stateless Responses; strict tools; `require_parameters:true`; pinned upstream; `allow_fallbacks:false` | Exactly one returned tool call is enforced before dispatch, then existing schema/authority/science checks |
| Anthropic | Native Messages strict tools and JSON output; no parallel tools | Full original JSON Schema validated locally before normalization; existing role/science checks still run |
| SambaNova, NVIDIA | Chat JSON-schema output with one named-tool/arguments envelope | Exact full envelope validated locally; no parsing of freeform prose or inferred tools |
| Gemini | Stateless Interactions JSON envelope; `store:false`; explicit API revision | Exact full original envelope validated locally; no native tool/thought-signature replay or guessed signatures |

Anthropic documents unsupported numeric/string/array bounds; only its wire copy
omits those bounds and describes them. Gemini documents ignored string-length and
other constraints; its wire copy omits those documented ignored keywords. Full
canonical bounds remain mandatory locally. SambaNova/NVIDIA receive the original
schema in their JSON envelope and may reject unsupported features. The original
tool definitions are never mutated. Missing fields, extra fields, unknown tools,
multiple calls, non-JSON output, invalid bounds, and truncated output are rejected;
invalid output never triggers a provider switch. Tool result roles and call
correlation survive continuation. Operator/user content remains untrusted data.

Provider/model/key availability is separate from adapter support. A small health
request cannot certify every future role/schema or provider quota. No fallback
changes terrain measurements, benchmark limits, qualifications, route verification,
portfolio coverage, or evidence authority. Non-text services (Composio, Deepgram,
ElevenLabs) and Cloudflare account-scoped APIs are excluded.

## Bounded live check receipt

`out/final-new-primary-schema-health-r7.json` records one successful strict
OpenAI `gpt-5.4-nano` tool check, with a 128-token cap and no tool execution.
`out/final-text-fallback-health-r7.json` records at most one request per fallback,
using the actual fixture mission-director submission schema and its registered
tool structures, a 4968-byte canonical packet, and a 1024-token cap. No returned
tool was executed; no raw provider body, output, key, or provider identifier was
saved. These are point-in-time checks, not a guarantee of a full mission run.

| Provider / explicit model | Result |
| --- | --- |
| Groq / `openai/gpt-oss-120b` | Complete, exact original submission accepted |
| NVIDIA / `nvidia/nemotron-3.5-super-vl-120b-a12b` | Complete, exact original submission accepted |
| OpenRouter / `openai/gpt-5.4-nano`, upstream `openai` | HTTP 404; model/endpoint capability unconfirmed |
| Anthropic / `claude-haiku-5-5` | HTTP 400; model/schema capability unconfirmed |
| SambaNova / `DeepSeek-V3.1` | HTTP 401; credential/access rejected |
| Gemini / `gemini-3.8-flash` | HTTP 503; model/endpoint capability unconfirmed |

Subsequent bounded diagnosis found that the pinned OpenRouter route rejected the
optional `parallel_tool_calls` request parameter under `require_parameters`,
although the strict tool schema itself was supported. The adapter omits this
unsupported transport parameter, adds an explicit serial-call instruction and
rejects zero or multiple returned calls **before any dispatcher**. Strict schemas,
the upstream pin, required supported parameters, and disabled upstream fallbacks
are preserved. Tests inject zero/two calls and verify rejection without switching
providers or executing tools. The actual mission-director schema passed this
adapter with `openai/gpt-5.4-mini`; see the bounded receipt
`out/final-openrouter-adapter-health-r16.json`.

Anthropic's diagnostic was rejected for an account credit restriction; no billing
or account action was taken. SambaNova's credential rejection and Gemini's
service error remain unresolved, so these providers stay disabled locally.

The current rehearsal uses primary `gpt-5.4-mini`, then the explicit order
`["groq","nvidia"]`, `GROQ_MODEL=openai/gpt-oss-120b`, and
`NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b`. This is a selected runtime
configuration, not an app default, model-quality guarantee or completed-run claim.
A small schema health success does not establish every role's performance.
A configured failure does not silently route around an authentication or unsupported-schema problem.
Use only a new run after changing the effective configuration; old runs and
receipts remain immutable.

## Bounded output and final assessment

Role reviewers receive the committed facts before proposing an assessment. The model-only terminal payload can now be `{"_task_payload_ref":"authoritative_submission.payload"}`. It references only that invocation's exact canonical payload, never an arbitrary path or another run. Expansion deep-copies the registered facts, then runs the same complete Pydantic, evidence-namespace, task-identity, policy and scientific-publication validators as an explicit payload. Extra reference fields, other paths, absent authority and foreign evidence remain invalid. The model still chooses its summary, disposition, issues and next action; a reference cannot force COMPLETE, PASS or publication. Explicit payloads remain available for permitted assessment changes.

This avoids making a 1,024-token fallback repeat long shortlist/qualification records. All source facts remain visible to review; none are removed to fit the output. At the final permitted model dispatch, only the terminal submission tool is advertised, preserving room to return an assessment after read tools. It can still return a supported evidence gap or review request. A nonterminal call at that point fails closed. The original six-request invocation and 40-request run ceilings, fallback token caps, independent scientific computation and cancellation fences remain unchanged.

The native live rehearsal also exposed empty target-review source/dimension links. Target context now follows only registered target-profile evidence ancestry and the target's saved measurement specification. It identifies terrain profile availability separately from downstream criterion satisfaction; missing mineral/power/other dimensions remain unresolved or retain their recorded coverage reason. Unrelated Earth sources and unregistered parents cannot become planetary evidence.

OpenRouter passed the schema health check but later returned HTTP 402 during a full investigation. Subsequent local rehearsals use `MODEL_FALLBACK_ORDER=["groq","nvidia"]`; the provider implementation remains available for a user-configured account. No billing or account limits were changed. This operational note is not a claim that every live role or a complete live investigation has passed.

The latest bounded primary check (`out/final-primary-budget-probe-r29.json`)
completed the actual strict submission schema using `gpt-5.4-mini` with a 1,024-token
allowance (374 output tokens). The local R29 rehearsal uses this lower primary cap
and 60-second request spacing within the existing account limit. This is request
configuration only: no billing, credit, project quota or account settings changed.
It remains a point-in-time schema check, not a completed investigation.

## Primary references

- [OpenAI function calling and strict mode](https://developers.openai.com/api/docs/guides/function-calling)
- [Groq Responses API](https://console.groq.com/docs/responses-api)
- [OpenRouter stateless Responses](https://openrouter.ai/docs/api_reference/responses/overview)
- [OpenRouter provider routing controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- [Anthropic documented schema limitations and wire transformations](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [SambaNova function calling and JSON Schema](https://docs.sambanova.ai/docs/en/features/function-calling)
- [NVIDIA hosted Nemotron JSON-schema Chat interface](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer)
- [Gemini structured JSON output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini Interactions API schema](https://ai.google.dev/static/api/interactions.openapi.json)

Summary length is checked after restoring wire aliases. Correction feedback contains the schema-owned length bound and asks for a brief outcome sentence with IDs kept in structured evidence references. It never echoes rejected summary text, truncates a proposal, expands the output ceiling or converts a rejected result into an accepted one. The request-size regression retains its 22,000-byte ceiling after instruction compaction.
