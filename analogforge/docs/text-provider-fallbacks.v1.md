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
Fallbacks default to 1024 output tokens, including reasoning where counted.
An explicit `NVIDIA_MAX_OUTPUT_TOKENS` may select 256–4096 for NVIDIA only;
the current local review uses 2048. It never raises the primary/Groq allowance
or an individual request's smaller cap. Non-default NVIDIA allowances enter the
configuration hash. Truncated output remains invalid at every allowance. Each
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

The R78 rehearsal uses primary `gpt-6.1-sol` with explicit `low` reasoning,
a 2,048-token total output cap and 40-second minimum request
spacing, then the explicit order `["nvidia"]` with
`NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b` and a 2,048-token cap.
Groq passed the small schema check but later returned a tool-use error and a
quota response during full investigations; it is disabled in this local chain.
Its adapter and explicit configuration remain available. This is a selected runtime
configuration, not an app default, model-quality guarantee or completed-run claim.
A small schema health success does not establish every role's performance.
A configured failure does not silently route around an authentication or unsupported-schema problem.
Use only a new run after changing the effective configuration; old runs and
receipts remain immutable.

## Bounded output and final assessment

Role reviewers receive the committed facts before proposing an assessment. The model-only terminal payload can now be `{"_task_payload_ref":"authoritative_submission.payload"}`. It references only that invocation's exact canonical payload, never an arbitrary path or another run. Expansion deep-copies the registered facts, then runs the same complete Pydantic, evidence-namespace, task-identity, policy and scientific-publication validators as an explicit payload. Extra reference fields, other paths, absent authority and foreign evidence remain invalid. The model still chooses its summary, disposition, issues and next action; a reference cannot force COMPLETE, PASS or publication. Explicit payloads remain available for permitted assessment changes.

This avoids making a bounded fallback repeat long shortlist/qualification records. All source facts remain visible to review; none are removed to fit the output. At the final permitted model dispatch, only the terminal submission tool is advertised, preserving room to return an assessment after read tools. It can still return a supported evidence gap or review request. A nonterminal call at that point fails closed. The six-request invocation and 40-request run ceilings, independent scientific computation and cancellation fences remain unchanged; the optional NVIDIA-only allowance is described above.

The native live rehearsal also exposed empty target-review source/dimension links. Target context now follows only registered target-profile evidence ancestry and the target's saved measurement specification. It identifies terrain profile availability separately from downstream criterion satisfaction; missing mineral/power/other dimensions remain unresolved or retain their recorded coverage reason. Unrelated Earth sources and unregistered parents cannot become planetary evidence.

OpenRouter passed the schema health check but later returned HTTP 402 during a full investigation. It is disabled in the current local chain; the provider implementation remains available for a user-configured account. No billing or account limits were changed. This operational note is not a claim that every live role or a complete live investigation has passed.

An earlier bounded primary check (`out/final-primary-budget-probe-r29.json`)
completed the actual strict submission schema using `gpt-5.4-mini` with a 1,024-token
allowance (374 output tokens). The local R29 rehearsal uses this lower primary cap
and 60-second request spacing within the existing account limit. This is request
configuration only: no billing, credit, project quota or account settings changed.
It remains a point-in-time schema check, not a completed investigation.

The R60 task context includes the exact accepted contract and acceptance record
already checked by the scheduler. Its requirements use a lossless column/row
representation only when every row has the same keys. The canonical read tool
returns a deep copy of the same facts; no accepted requirement, null, unit,
negative result or evidence reference is dropped. Missing-evidence reads remain
available. A role must submit on its final allocated request, including when the
run's remaining allowance is smaller than six; the submission may still express
a justified stop, review request or Unknown. This avoids spending the last run
request on a redundant read, without raising any budget or assuming success.

R60 reached all four candidate qualification reviews, then the fallback twice
changed a recorded qualification status and was rejected. The qualification
prompt now explicitly preserves computed row statuses; its one correction names
the exact affected row and expected status, using only the already supplied
canonical facts. A model may still object or request review without rewriting a
FAIL/GAP/UNKNOWN into a different result. Repeated invalid output still fails
closed. R63 is a new investigation with these instructions and 40-second pacing;
starting it is not a completed-publication claim.

R63 preserved the computed rows but paused over an unrequested wheel-scale
obstacle/route capability in a terrain-only mission with no rover. Qualification
instructions now explicitly separate accepted coarse-support terrain predicates
from unrequested route, battery and obstacle tests. Real defects affecting an
accepted predicate or source eligibility can still block. R65 starts fresh with
that scope guidance. The UI also displays sanitized, admitted reviewer concerns
so a genuine pause is actionable; it never removes objections to obtain approval.

Subsequent bounded availability checks found exhausted or nearly exhausted
daily request allowances on the larger selected OpenAI models, while nano had
capacity. These are point-in-time account observations, not universal model
quotas. Selecting nano did not alter billing or account limits. R67 exposed a
director-prompt ambiguity about future prerequisites; the algorithm now asks
only about the current bounded review, retaining concrete current blockers.

`OPENAI_REASONING_EFFORT` is optional (`none`, `low`, `medium`, `high`, `xhigh`).
Omitting it preserves the prior request and public-configuration hash. An explicit
value enters that hash and applies only to primary OpenAI requests, never to a
fallback transport. The selected model must support it; unsupported API options
fail closed. Reasoning uses the same total output cap and request budgets.
Responses remain `store:false`; replayable encrypted reasoning stays only in the
private invocation conversation and is never persisted as evidence, activity,
diagnostic text or an exported report. The [nano model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-nano)
lists supported effort levels, and the [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
describes stateless encrypted continuation. R69 is a new investigation with this
configuration; its outcome must be read from its terminal receipt.

Nano's R69 review still misread a recorded acceptance. A separate availability
check established access and unused request capacity for `gpt-6.1-sol`, selected
for R70/R72/R78 at the existing 10,000-token account rate limit. Its [official model
documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol) supports
low reasoning and requires Responses for tool calls. This is an explicit runtime
selection, not an increased account quota or a changed app default.

R70 identified a missing review handoff: the Scout's evidence references did not
expose the target profile's numeric primitives. Target/Scout tasks now include
the exact registered target profile, including histogram, support, uncertainty
notes and unavailable dimensions. Duplicate metric copies and homogeneous metric
rows are encoded losslessly and reconstructed exactly; no primitive, negative,
null or future field is removed from canonical facts. Derived pair-comparison
metrics remain downstream work, not invented target-only scalars. The R72
investigation used this handoff; old blocked runs retain their original records.

R72 then exposed an incorrect geometry-receipt reference: a contract inspection
was being presented in place of deterministic target preparation. R78 binds the
actual successful characterization operation and receipt to the same workspace,
run, mode, AOI and registered evidence set. Source coordinate/height metadata is
projected only from the matching successful ingestion manifest and receipt. The
operator AOI remains an unchanged horizontal footprint; it does not acquire an
invented source datum. Missing or foreign provenance remains null/unavailable.
The helper was checked against the actual R72 database snapshots as well as
namespace, scope, source-body and evidence-mismatch regressions.

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

The wire submission schema asks for summaries of at most 160 characters without aliases or IDs. Canonical summary length is still checked against 800 characters after restoring aliases; no returned text is truncated to pass validation. Correction feedback contains the schema-owned length bound and keeps references in structured evidence fields. The request-size regression retains its 22,000-byte ceiling.

Literal tilde escaping uses `~~` in this private, per-invocation wire format. Ordinary model prose such as `~5 m` or `~0.5 km` is preserved. Reserved letter-and-number aliases still require exact membership; unknown aliases are rejected. Encoded source text round-trips without changing approximate quantities or literal alias-like text.

A passport proposal with `ready_to_publish=false` must cite a known unresolved issue or contain a concrete WARNING/BLOCKING issue. An unexplained false receives the existing single correction, never automatic approval. A justified false still holds publication, and a repeated invalid assessment fails closed. Published reports may accurately contain failed criteria, Unknowns, gaps and unrun rover tests; these do not themselves establish a report defect.
