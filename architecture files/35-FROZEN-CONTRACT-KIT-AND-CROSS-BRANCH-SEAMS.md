# Frozen contract kit and cross-branch seams

Three agents build three parts in parallel and the merged result must work on the first try. That is only possible if the **seams are code, not prose**. The *frozen contract kit* is that code: typed Python ports, domain models, JSON schemas, a bundled OpenAPI, shared fixtures and shared test oracles, identical byte-for-byte on every branch.

## 1. The kit

Location in the repository: `architecture files/contracts/kit/`.

```text
kit/
  materialize.py        stdlib-only: copy kit into analogforge/, or --verify, or (merging agent only) --repair
  kit-manifest.json     SHA-256 of every kit file
  tools/build_kit.py    regenerates kit/files from the authoritative contracts (contract-change process only)
  files/                the exact files that appear under analogforge/
    pyproject.toml                       canonical dependencies, ruff/mypy/pytest config (3 editable extra lists)
    .env.example   .gitignore
    src/analogforge/__init__.py  adapters/__init__.py  rendering/__init__.py
    src/analogforge/ports/               common, domain_models, assurance_models, datasets, hashing, catalog,
                                         science, science_payloads, passport_renderer
    contracts/                           openapi.bundled.json, domain/assurance schemas, scientific-gates.json,
                                         error-codes.json, algorithm-ids.json, route/telemetry/constraints/
                                         dataset-manifest/passport-export-bundle schemas, ui-testids.json
    tests/contracts/kit/test_kit_contracts.py
    tests/fixtures/kit/                  rovers/, missions/, canonical-graph-v1.json, expected/, blueprint-*.json
```

### 1.1 Rules (binding for every branch)

1. **First command of every session:** `python3 "architecture files/contracts/kit/materialize.py"` (creates `analogforge/…`; never overwrites a differing file).
2. **Last command of every session and the first of every merge check:** `python3 "architecture files/contracts/kit/materialize.py" --verify` must print `"status": "PASS"`.
3. Kit files are **read-only for everyone**. The only permitted edits are inside the three marked `extra-tanush`, `extra-ayan`, `extra-aradhya` lists of `pyproject.toml`, each by its own person.
4. `src/analogforge/ports/` is a kit-only package: no other file may be added to it. Put additional shared helpers in your own owned package.
5. If a kit file blocks you, **do not edit it**. Write a contract-change request (§8) in your handoff directory, implement a local workaround inside your owned paths that does not change the wire contract, and continue.
6. Install without creating `uv.lock` unless you are Tanush: `uv venv && uv pip install -e ".[dev,extra-<you>]"`. Only Tanush commits `uv.lock`.
7. `tests/contracts/kit` must pass unchanged on every branch before every commit that touches Python.

### 1.2 What the kit gives each person

| Person | Imports from the kit | Gets from the kit |
| --- | --- | --- |
| Tanush | all ports, `hashing`, `catalog` | The exact `ScienceService`/`PassportRenderer` signatures he calls; the domain models his Pydantic layer must match; the bundled OpenAPI his API must conform to |
| Ayan | `science`, `science_payloads`, `datasets`, `common`, `hashing`, `catalog`, `domain_models` (value types) | The exact request/result/payload types he returns; the dataset manifest he validates; canonical graph oracle and energy oracle |
| Aradhya | `passport_renderer`, `domain_models`, `assurance_models`, `science_payloads` (artifact types), `hashing`, `catalog`; `contracts/openapi.bundled.json` and `ui-testids.json` for TypeScript | The exact bundle she renders; the OpenAPI her client is generated from; the test-id contract her UI must satisfy |

## 2. Entry points (how the merged app finds each other's code)

Fixed dotted paths, loaded by the platform with `importlib` at startup. A missing or non-conforming entry point is a **startup/preflight failure with a named error**, never a silent fallback to a test double.

| Entry point | Owner | Signature | Loaded by |
| --- | --- | --- | --- |
| `analogforge.science.facade:create_science_service` | Ayan | `() -> ScienceService` | Tanush's worker (`ports.science.SCIENCE_FACADE_ENTRY_POINT`) |
| `analogforge.rendering.passport:create_passport_renderer` | Aradhya | `() -> PassportRenderer` | Tanush's export service (`ports.passport_renderer.RENDERER_ENTRY_POINT`) |
| `analogforge.science.fixtures.practice:generate_all` | Ayan | `(out_dir: Path) -> list[str]` writes every practice dataset of [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §3 (data + `manifest.yaml`) under `out_dir/<dataset_id>/` and returns the dataset ids | `analogforge datasets generate-practice` |
| `analogforge.science.fixtures.mock_nasa_drop:generate` | Ayan | `(out_dir: Path) -> list[str]` writes the mock NASA drop of [39](39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) §5 | `analogforge datasets generate-mock-nasa-drop` |
| `analogforge.science.datasets.inspect:draft_manifest` | Ayan | `(dataset_dir: Path, body: Body, role: str) -> dict` inspects the files with GDAL/netCDF and returns a **draft** manifest dict (inferable fields filled; `provider`, `license_note`, `citation`, `vertical_reference` set to `TODO_FILL_IN` so validation fails until a human/agent completes them) | `analogforge datasets scaffold <dataset_id> --body … --role …` |
| `analogforge.main:app` | Tanush | FastAPI instance | uvicorn |
| `analogforge.cli:main` | Tanush | CLI | `analogforge` script |

Import hygiene (tested): importing `analogforge.science.facade` must not import `fastapi`, `sqlalchemy`, `psycopg`, `openai`; importing `analogforge.rendering.passport` must not import any of those nor `httpx`/`requests`/`socket`-using modules at import time. Both entry points are cheap to import (no data download, no model load, no network).

Tanush's production code must not import `analogforge.science.*` or `analogforge.rendering.passport.*` except through the entry points above, so branches that lack the other side still pass their own tests with test doubles that live **only under `tests/`**.

## 3. Seam B — platform ↔ science (the main Lego joint)

### 3.1 Call pattern

```text
worker job -> application service builds ScienceRequest from frozen persisted records
          -> context = WorkerScienceContext(scratch, deadline, cancel token, authorized artifact reader, dataset roots)
          -> result = science_service.execute(request, context)        # in a CPU subprocess, never in the HTTP process
          -> registrar.register(request, result)                       # one fenced transaction
          -> application service turns validated payload into domain rows + events
```

* `request.request_id` is a fresh UUID per attempt. The cache key is `canonical_sha256(request minus request_id)`; the result's `input_sha256` **must equal** `canonical_sha256(request)` with `request_id` retained (the platform recomputes and rejects a mismatch).
* The science library is pure with respect to the request: same request ⇒ same payload and artifact bytes (wall-clock fields such as `SearchCounters.elapsed_ms` and `counters["elapsed_ms"]` are excluded from determinism assertions and from any hash).
* In `synthetic`/`replay` mode `source_policy.allow_network` is `False` (the model validator enforces it) and `context.http_client()` returns `None`.
* The platform sets `deadline_monotonic` from remaining active-run time; science calls `context.check_cancelled()` at least every 250 ms of CPU work and at every outer-loop iteration of search/screen/analysis.

### 3.2 Which stage calls which operation, and what feeds it

The scheduler (code) decides the sequence; roles only choose among allowed actions. This table is normative; the platform builds each `ScienceRequest` from the listed records.

| Run state | Operation | Request built from | Platform registers | Platform then produces |
| --- | --- | --- | --- | --- |
| `VALIDATING` | `INGEST_LOCAL_DATASET` (only for `LOCAL_DATASET` sources) | dataset manifest from the dataset lock | SOURCE evidence + normalized raster artifact | dataset readiness (E-06) |
| `CHARACTERIZING` | `RESOLVE_COVERAGE`, then `CHARACTERIZE_TARGET` | target `AreaOfInterest` from the frozen mission; `SourceSelector` from scenario config | SOURCE/DERIVED evidence | `PlanetaryTargetProfile` |
| `CHARACTERIZING` | `BUILD_DISPLAY_LAYERS` (TARGET) | target evidence ids | display image artifacts | `DisplayLayerManifest` rows |
| `DISCOVERING` | `SCREEN_CANDIDATES` | target metrics+histogram, requirements, `search_region_set_id`, `reference_set_id` | screening evidence | `EarthAnalogCandidate` rows for shortlist **and** persisted exclusion/cap records |
| `DISCOVERING` | `ANALYZE_CANDIDATE` (each shortlisted window; also `NOMINATE_CANDIDATE`) | `CandidateRef`, source selector | DERIVED evidence + `ANALYSIS_GRID` artifact | candidate metrics, connected zones |
| `DISCOVERING` | `BUILD_DISPLAY_LAYERS` (CANDIDATE) | analysis evidence ids | image artifacts | `DisplayLayerManifest` rows |
| `QUALIFYING` | `COMPARE_REQUIREMENT` (each requirement × candidate) | requirement, candidate, target/candidate evidence handles, policy id from `catalog.OBSERVABLE_POLICY_BY_OBSERVABLE` | COMPARISON evidence | `QualificationDimension` rows (status/confidence **proposed**; policy commits) |
| `QUALIFYING` | `ASSESS_COMPATIBILITY` (rover present) | rover, requirements, candidate evidence | DERIVED evidence | compatibility rows (`preliminary=true`) |
| `CRITIQUING` | `AUDIT_EVIDENCE` | claim scopes derived from the matrix | DERIVED evidence | science gate evidence consumed by `application.assurance` |
| `DESIGNING_TEST` | `DESIGN_BENCHMARK` | frozen mission+rover, candidate, analysis evidence id, strategy, prior attempts | CONSTRAINTS artifact (JSON) | `VerificationTest` (constraints hash = canonical hash of the artifact) |
| `DESIGNING_TEST` | `SEARCH_ROUTE` | frozen `ConstraintsArtifact` + its hash | ROUTE artifact | search record |
| `VERIFYING` | `VERIFY_ROUTE` | constraints, route, hashes, search status | VERIFICATION evidence, TELEMETRY artifact | `TestResult`; final `COMPARE_REQUIREMENT` for route-dependent rows (`verification` supplied) and final `ASSESS_COMPATIBILITY` |
| `DIAGNOSING` | `DIAGNOSE_RESULT` | constraints, search status, verification summary, attempt history, remaining repair budgets | DERIVED evidence | permitted repairs → Verification/Replanning role proposal validated against them |
| `REPLANNING` | `DESIGN_BENCHMARK` again | same frozen mission+rover; new strategy/candidate/blocked mask; `prior_attempts` | as above | next attempt |
| `QUALIFYING` (action) | `OPTIMIZE_PORTFOLIO` | requirements, candidates, qualification rows, verification summaries | evidence | `CompositePortfolio` |
| `BUILDING_PASSPORT` | `AUDIT_EVIDENCE` (final) | all claims | evidence | final assurance (see 33) |

### 3.3 The registrar (platform) — algorithm and rejection rules

For every `ScienceComputationResult`, in **one fenced transaction** (lease token + run revision checked):

1. Validate the result against the pydantic model; `request_id`, `operation`, `mode` equal the request's; `input_sha256` recomputed and equal. Reject otherwise (`MODEL_OUTPUT_INVALID`-class receipt, run continues bounded).
2. For every `ArtifactDraft`: resolve `scratch_dir()/scratch_relpath` (no symlinks, inside scratch), re-hash, compare to `sha256` and `size_bytes`, enforce the media-type allow-list (`application/json`, `image/png`, `image/tiff`, `application/x-npz` (the deterministic ANALYSIS_GRID container, see Ayan's `08-MODULE-SPECIFICATION.md` §3), `text/csv`, `application/octet-stream` only for `SOURCE_BYTES`), then atomically move into content-addressed storage.
3. Topologically order `EvidenceDraft`s by `parent_local_keys`; allocate UUIDs; resolve `parent_evidence_ids` (must be authorized in this workspace, run lineage and mode). Create `EvidenceRecord`s (`mode` = request mode; `body` per draft; `artifact_sha256` from the resolved artifact).
4. Replace every `EvidenceRef(local_key=…)` in the payload by the allocated UUID **before** any domain row stores it; a dangling `local_key` rejects the whole result.
5. Source-naming rules: in `synthetic` mode every `dataset_product_id` starts with `SYNTHETIC_` and `source_uri` is `null`; in `live` mode none may start with `SYNTHETIC_`; `source_uri` must contain no query string, credentials or signed-URL parameters.
6. Insert the `ToolReceipt` (`SUCCEEDED` for `SUCCEEDED|LIMITED`, `BLOCKED` for `BLOCKED`, `FAILED` for `FAILED`; `cache_hit` when the input hash was already satisfied).
7. Hand the validated payload to the application service for that operation (builds domain rows) and append the run events in the same transaction.

A rejected result registers **nothing** except a diagnostic receipt/event. `status=LIMITED|BLOCKED` results are valid and drive `UNKNOWN`/`INCONCLUSIVE` outcomes — they are never converted into success, retries without a changed input, or `FAIL`.

### 3.4 Error and issue mapping

`ScienceIssue.code` is a code from `contracts/error-codes.json` **or** a qualification `reason_code` (e.g. `SCALE_UNSUPPORTED`). Mapping: `NO_COVERAGE`, `INSUFFICIENT_VALID_DATA`, `SCALE_INCOMPATIBLE`, `UNSUPPORTED_CRS`, `ENERGY_UNCALIBRATED` ⇒ affected requirements `UNKNOWN`; `SOURCE_UNAVAILABLE`, `PROVIDER_RATE_LIMITED`, `TOOL_TIMEOUT` ⇒ retryable infrastructure block, never scientific FAIL; `SEARCH_LIMIT` ⇒ `INCONCLUSIVE/SEARCH_LIMIT`; `SOURCE_CHECKSUM_MISMATCH`, `SOURCE_CONTENT_INVALID` ⇒ quarantine, dependent claims `UNKNOWN`. A science exception that is not a `ScienceCancelled`/`ScienceDeadlineExceeded` becomes `ComputationStatus.FAILED` with code `SYSTEM`-class and **never** a scientific verdict.

### 3.5 Facade obligations (Ayan)

`create_science_service().supported_operations()` returns all fifteen operations. `execute` dispatches on `request.operation`, validates that `request.inputs` and `context` satisfy the operation's preconditions, and returns `BLOCKED` (with an issue) rather than raising for missing data, missing coverage, unresolved CRS/frame, or missing policy. It writes only under `context.scratch_dir()`. It never reads environment variables, never opens a socket in `synthetic`/`replay`, never imports platform code.

## 4. Seam C — platform ↔ renderer

```text
application.passports: assemble frozen PassportExportBundle  ->  renderer.render(bundle, assets, "html"|"json"|"csv")
                      -> RenderedExport: platform stores bytes (file SHA-256), serves headers, caches by (passport, format, renderer_version)
```

Assembly (Tanush) guarantees before calling: all references resolve; `manifest_sha256 == sha256(canonical_manifest_json bytes)`; `attempts` are ordered and contain *every* attempt including failures; `assurance` present for non-draft; every requirement of the accepted mission has at least one `QualificationDimension` per assessed candidate or a visible `not_run_reason`; `assets` contain only validated PNG/SVG produced by the platform from stored display/route artifacts.

Renderer (Aradhya) guarantees: pure (see port docstring); deterministic (same inputs ⇒ same bytes); escaping of every string field; no external URL loads in HTML (no `<script src>`, `<link href>`, `<img src="http…">`); every requirement row, every attempt, every GAP/UNKNOWN, mode, manifest digest and assurance publication appear in **HTML**, are present in **JSON**, and CSV has exactly `CSV_COLUMNS` in that order, formula-escaped (`=`,`+`,`-`,`@`, tab, CR prefix ⇒ leading `'`). Filenames: `analogforge-passport-<mode>-<first8(passport.id)>-<first8(manifest_sha256)>.<ext>`.

JSON export object (UTF-8, `sort_keys`, 2-space indent, trailing newline):

```json
{
  "export_schema_version": "1.0",
  "manifest_sha256": "<64 hex>",
  "canonical_manifest": {"...": "parsed canonical_manifest_json"},
  "bundle": {"...": "every PassportExportBundle field except canonical_manifest_json and assets"}
}
```

An independent check must hold: `sha256(rfc8785(export["canonical_manifest"])) == export["manifest_sha256"]`.

## 5. Seam A — frontend ↔ platform

* **One OpenAPI.** `contracts/openapi.bundled.json` (43 operations) is the single source of truth. Aradhya generates `apps/web/src/generated` from it (`pnpm exec openapi-typescript contracts/openapi.bundled.json -o apps/web/src/generated/schema.d.ts` and a thin typed fetch client). Tanush's FastAPI must satisfy it; the platform **contract test** hits every endpoint with seeded data and validates each response body against the bundled operation's declared response schema (jsonschema, Draft 2020-12), and validates every request fixture from `tests/fixtures/kit`. Aradhya's MSW fixtures are validated against the same spec in a Vitest test.
* **Server-owned state.** Statuses, selection pointers, snapshots, cursors come from responses. See [16](16-USER-JOURNEYS-AND-SCREENS.md)/[17](17-FRONTEND-COMPONENTS-AND-STATE.md).
* **Scenario and lock ids** come from `GET /capabilities` (`scenario_config_ids`, `default_scenario_config_id`, `dataset_locks`) and `GET /configuration/scenarios/{id}`; the UI never hardcodes them. The ids themselves are fixed in `ports.catalog`.
* **SSE** exactly as [07](07-HTTP-API-AND-EVENTS.md).
* **Mock mode** is a build-time switch (`VITE_API_MOCK=1`), shows a permanent `MOCK PREVIEW` banner, and is impossible to enable in a production build (build fails if both `NODE_ENV=production` and `VITE_API_MOCK=1`).

### 5b. UI-readable artifacts (how the frontend gets histograms, screening tables, benchmark rows, telemetry)

The wire models carry scalar metrics only. The rich data lives in **evidence artifacts** the UI fetches through existing endpoints (`GET /evidence/{id}` then authorized `GET /artifacts/{sha256}`). Contract: every payload-bearing science operation emits an `EvidenceDraft` whose `algorithm_id` is `catalog.ALGORITHM_IDS[...]` and whose artifact is the operation payload serialized with `ports.hashing.canonical_json_bytes` (`application/json`). Special cases: `ANALYZE_CANDIDATE` emits the ANALYSIS_GRID evidence (`analyze-candidate`) **and** a child `analysis-summary` evidence holding the payload JSON; `VERIFY_ROUTE` emits the `verify-route` VERIFICATION evidence (payload JSON) **and** a `route-telemetry` evidence (`TelemetryArtifact`). Platform rules that make these discoverable: every shortlisted `EarthAnalogCandidate.evidence_ids` includes the screening evidence and its analysis evidences; `PlanetaryTargetProfile.evidence_ids` includes the `characterize-target` evidence; every `TestResult.evidence_ids` includes the `verify-route` and `route-telemetry` evidences; every `VerificationTest` stores its route/constraints artifact hashes (`route_artifact_sha256`, `constraints_sha256`/`waypoints_artifact_sha256`); `QualificationDimension.evidence_ids` includes its `compare-requirement` evidence; compatibility rows are exposed through `GET /compatibility`. The frontend must treat these artifacts as authoritative display data and **must not** recompute anything from them.

## 6. UI test-id contract

`contracts/ui-testids.json` lists every `data-testid` (and the `data-*` attributes each must carry) that the workbench must expose. Aradhya's UI implements all of them; her Playwright suite asserts that each id appears in the journey where it should; the merging agent's browser tests drive the product exclusively through these ids. A missing or renamed id is a failed merge gate. Values: `data-status` is a `QualificationStatus` or `PENDING`; `data-mode` is a `RuntimeMode`; `data-state` is a `RunState`; null measurements render the text `Unknown` inside an element with `data-testid="unknown-value"`.

## 7. Configuration files and their cross-branch keys

| File | Owner | Cross-branch contract (all keys required) |
| --- | --- | --- |
| `config/scenarios.yaml` | Tanush | Per scenario id in `catalog.ALL_SCENARIOS`: `name`, `body`, `description`, `allowed_modes`, `default_dataset_lock_id`, `status` (`AVAILABLE` \| `AWAITING_DATASETS`), `mission_preset`, `rover_presets` (names from `catalog.PRACTICE_ROVER_FILES`), `target_source` and `earth_source` (`SourceSelector` shape), `search_region_set_id`, `reference_set_id`, `graph_fixture_id` (graph scenario only), `operator_limits`. Maps to the `ScenarioConfig` wire object. |
| `config/presets/{missions,rovers}/*.json` | Tanush | **Byte-identical copies** of the kit fixtures; a test enforces equality. Used by "Load example" and `seed-synthetic`. |
| `config/algorithms.yaml` | Ayan | `algorithm_lock`, `measurement_specs` (ids `catalog.MEASUREMENT_SPEC_TARGET`/`_EARTH`), `observable_policies` (one entry for every value of `catalog.OBSERVABLE_POLICY_BY_OBSERVABLE`), `grid`, `route_search`, `energy_defaults`, `thresholds`, `fixtures`. Platform pins `algorithm_lock_sha256 = canonical_sha256(parsed algorithms.yaml)` and passes it as `ScienceOptions.algorithm_config_sha256`. |
| `config/candidates.yaml` | Ayan | `search_region_sets` (id `catalog.SEARCH_REGION_PRACTICE` plus the generated-grid recipe for local datasets), `reference_sets` (id `catalog.REFERENCE_SET_PRACTICE`; real entries need a citation URL and `georeference_quality`). |
| `config/datasets.yaml` | Ayan | Adapter registry entries for the seven adapter ids in [08](08-DATASET-CATALOG.md) plus `local_dataset` and `synthetic_practice`. |

A missing required key makes `analogforge preflight` fail with the key path. Preflight is owned by Tanush; it parses all four files with strict models.

## 8. Contract-change process

Nothing in the kit or the 43-operation OpenAPI changes during a one-shot build. If a branch agent proves a change is unavoidable:

1. Write `team handoffs/<person>/CHANGE-REQUEST-<n>.json` using `team coordination/templates/contract-change-request.json` (field paths, before/after, reason, consumers, tests).
2. Continue with a compatible local workaround inside owned paths. Do not edit the kit.
3. The merging agent decides, applies the change to the kit on `merging-branch` via `tools/build_kit.py`, updates all three consumers, re-runs every gate, and records it in the merge report.

## 9. Determinism and hashing rules shared by all branches

* Canonical hashing is exclusively `analogforge.ports.hashing` (RFC 8785 + SHA-256). Never `json.dumps(sort_keys=True)` for a contract hash.
* Quantities are SI; angles degrees; energy Wh; percentages only in `*_pct`; unknown is `None`/`null`, never `0`/`NaN`.
* Tie-breaks are deterministic and specified (search: minimum distance, then minimum conservative energy, then lexicographically smallest `node_sequence`; shortlist: [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) §4).
* Random generators are seeded from `ScienceOptions.seed`; the generator type and seed are recorded in evidence parameters.
