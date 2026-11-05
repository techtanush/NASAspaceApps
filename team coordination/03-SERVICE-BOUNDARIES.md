# Service boundaries that make the branches composable

Public HTTP/domain shapes remain those in `../architecture files/contracts/`. This document fixes the internal seams between the owners. Implement concrete typed Python ports at F0 rather than communicating through screenshots, hidden globals or raw model prose.

## Boundary A Frontend to platform

Aradhya consumes the generated client from Tanush's exported OpenAPI. All science statuses, quantities, mode, revision IDs, selection pointers and cursors come from persisted server responses. The frontend can preview a user edit but cannot optimistically mark qualification/verification as successful.

Requests use `/api/v1`, idempotency keys, expected_revision and typed action payloads from07. Mission Fingerprint is a pre-run preparation job. Accepted mission and optional saved rover are immutable run inputs. First PROVE_IT authorizes design/verification within accepted assumptions; a new material input change requires review/new revision. SSE is committed run events; authoritative snapshot reload recovers disconnects.

MSW/test fixtures may simulate these endpoints **in a visible test/preview mode**. They are not fallback production responses when the backend or a credential is missing. Aradhya hands over the fixture server command, seed identities and negative cases so Tanush can run identical UI tests against the real backend.

## Boundary B Scientific calls and durable registration

Tanush owns the registered tool wrapper and persistence. Ayan owns `science/facade.py` and pure typed scientific operations. The accepted interface is a Python `ScienceService.execute(request, context) -> ScienceComputationResult`; long work executes inside the worker, not in an HTTP handler. Async download adapters may be awaited inside the worker; CPU operations remain separately cancellable processes. Do not expose arbitrary strings as tool-to-function execution.

`ScienceRequest` fields:

| Field | Meaning |
| --- | --- |
| operation | Fixed operation enum below, never arbitrary import path. |
| mode | live/replay/synthetic, injected by platform. |
| inputs | Operation-specific typed data copied from frozen domain records; full actual models, not just IDs that a pure module cannot resolve. |
| input_evidence | Authorized immutable metadata/handles for required evidence, including byte hashes/scale/body. |
| source_policy | Frozen allowed products/versions/extents/quality/decoder settings; permits append-only acquisition within policy. |
| options | Validated algorithm/search settings and budget, not replacement scientific requirements. |

`ScienceContext` contains run/workspace/job/invocation IDs, remaining monotonic deadline, cancellation check, server-controlled scratch directory, read-artifact and write-scratch callbacks, safe progress callback, approved source HTTP/auth access and algorithm/config versions. It has no SQL session, no provider model client, no unrestricted shell and no arbitrary filesystem access. Credentials are accessed by the approved downloader adapter, never returned in a scientific result or agent prompt.

`ScienceComputationResult` fields:

- `status`: SUCCEEDED, LIMITED, BLOCKED or FAILED describing computation, not mission qualification.
- `operation`: matching request enum, algorithm ID/version, parameters hash, input hashes and execution counters.
- `artifacts`: drafts with `local_key`, safe scratch handle, SHA256, bytes/media type, body/CRS/support/quality metadata. `local_key` is a result-local stable string, not a fabricated persisted UUID.
- `evidence_drafts`: local key, kind, parent draft keys or actual input evidence IDs, artifact key, typed measurements, limitations, direct/derived/proxy/assumed flags.
- `payload`: strict operation-specific computed proposal, referencing local evidence keys until registered.
- `issues`: canonical code, detail code, affected stable requirement IDs, retryability, safe message and uncertainty scope.

Tanush's registrar validates hashes/ownership/quantity validity/mode/lineage, moves bytes into the content store, allocates persisted UUIDs and resolves local keys. It then produces real EvidenceRecord/ToolReceipt/domain objects in one fenced transaction. Only these persisted references go to agents/frontend. If registration fails, no scientific success is announced. Do not make Ayan write database rows just to return candidate features.

Large arrays live in artifacts; do not send multi-megabyte pixel lists through the model or ordinary JSON API. Scientific modules may use shared domain value types but must not import FastAPI, SQLAlchemy, OpenAI or the application policy to perform math.

## Scientific operation map

| ScienceService operation | Public agent tool caller | Required computed output |
| --- | --- | --- |
| RESOLVE_COVERAGE | resolve_dataset_coverage | Actual approved metadata selections, spatial/valid coverage/access limitations. |
| FETCH_SOURCE | fetch_dataset | Checksummed bytes and validated source metadata; acquisition is not qualification. |
| CHARACTERIZE_TARGET | characterize_target | Body-aware target profile and scale-labeled metrics. |
| SCREEN_CANDIDATES | screen_earth_candidates | Bounded coarse shortlist, exclusions and stop/search extent. |
| ANALYZE_CANDIDATE | analyze_earth_candidate | Earth metrics/source evidence and detailed valid masks. |
| COMPARE_REQUIREMENT | compare_requirement | Predicate/status proposal, exact rule/evidence/scale/uncertainty. |
| ASSESS_COMPATIBILITY | assess_rover_compatibility | Constraint rows, missing capabilities and unsupported physical claims. |
| DESIGN_BENCHMARK | design_test | Frozen constraints proposal and task/exposure mappings; no threshold relaxation. |
| SEARCH_ROUTE | search_route | Search termination/counters and route or no route; no PASS based on search alone. |
| VERIFY_ROUTE | verify_route | Independent result, benchmark residuals, telemetry and evidence. |
| DIAGNOSE_RESULT | diagnose_verification | Supported violation categories and permissible repair kinds. |
| OPTIMIZE_PORTFOLIO | optimize_portfolio | Assignments, site-count objective, co-location checks and residual gaps. |
| BUILD_DISPLAY_LAYERS | platform rendering helper | Image/legend/affine/CRS manifest drafts derived from existing evidence. |

Ayan implements the numerical audit helpers used by review_evidence_bundle where scientific checks are needed; Tanush owns evidence reference/workspace/mode/contract-integrity audit and combines their findings. Tools get_run_snapshot/inspect_contract/validate_mission_draft/validate_rover_profile/get_evidence/compare_evidence/build_passport_manifest/submit_role_result are platform-owned, with scientific helpers called as appropriate. There is exactly one tool registry, owned by Tanush.

## Boundary C Passport assembly to rendering

Tanush assembles an immutable `PassportExportBundle`: AnalogPassport, accepted mission/optional rover snapshots, selected candidate/target summaries, qualification rows, compatibility, critiques, complete attempt history, portfolio, evidence appendix, final acquired-asset/build/config hashes and authorized embedded map images. The bundle includes its manifest_sha256 computed with RFC8785. References must resolve before rendering.

Aradhya implements `render_passport(bundle, assets, format) -> RenderedExport` under `rendering/passport/`, where format is html/json/csv. Assets are caller-provided validated bytes plus declared MIME; renderer has no network, database, secret or mutable run lookup. Return bytes, exact MIME, safe filename, byte SHA256, renderer version and a list of contained source/evidence references. File hash is separate from manifest digest. JSON export must preserve the canonical scientific snapshot, not recreate it from DOM text. HTML escapes content and is self-contained/printable; CSV prevents formula injection.

Tanush exposes authenticated asynchronous export endpoints/storage/header behavior. Aradhya handles download polling/Retry-After and presents frozen revision/digests. Ayan supplies display layers and scientific captions; renderer never recomputes slope, energy or qualification.

## Compatibility tests and F0 contract change handling

Tanush publishes operation input/output models and ports. Ayan's facade is checked against them with synthetic example calls; Aradhya's renderer is checked with a complete immutable fixture. Each branch tests both happy and rejection/missing-data paths without pretending the fake collaborator is implemented. At integration replace collaborator doubles with real modules and rerun the same case.

When an exact field is missing, record a contract change rather than inventing a private cross-branch convention. Public statuses/units/ID/null behavior must agree with architecture05/07. Proposed private envelope names above become real typed models at F0; they do not override public wire contracts.

## C1 assurance and claim boundary

Architecture33 and the [assurance schema](../architecture%20files/contracts/scientific-assurance.schema.json) define the shared artifact. Ayan returns observable-policy/adequacy/uncertainty/independent-verifier evidence through ScienceService drafts; Tanush resolves UUIDs, enforces SC gates and compiles permitted statements. The final passport has required assurance_evidence_id; its DERIVED record resolves by existing evidence/artifact endpoints. Tanush passes the resolved immutable report through PassportExportBundle to Aradhya. The renderer/browser never computes or upgrades scientific disposition. No new service process is required.
