# Backend module implementation contracts

Implement small testable modules behind typed application services. Routers translate HTTP to commands; agents request approved tools; neither reimplements scientific rules. The following entry points are required internal interfaces. Names may be idiomatic Python but responsibilities and ownership must remain distinct.

## Domain and application services

| Module | Entry point | Required behavior |
| --- | --- | --- |
| domain.hashing | canonical_hash(value, exclusions) | JCS canonical bytes, exclusions explicit per entity, deterministic SHA-256; no float NaN. |
| application.missions | create_draft, prepare_fingerprint, propose_revision, accept_revision | Preserve original intent; label proposed defaults; compare parent revision; acceptance creates immutable content/actor record. |
| application.rovers | import_profile, create_revision | Validate units/capabilities; no magic inference of consumption from battery size. |
| application.runs | start_run, apply_action, get_snapshot | Enforce workspace, accepted inputs, preflight, legal transition and idempotency; schedule jobs transactionally. |
| domain.policy | evaluate_transition(snapshot, proposal, receipts) | Reject fabricated evidence, missing mandatory data, unapproved contract changes, and illegal state transitions. |
| application.qualification | evaluate_candidate(contract, target, candidate, rules) | Deterministic per-requirement status, confidence/limitations and evidence references. |
| application.compatibility | assess(rover, test_zone, evidence) | Evaluate available modeled constraints; mark unsupported clearance/traction/autonomy claims UNKNOWN. |
| application.verification | design, solve, independently_verify, diagnose | Freeze constraints, separate route proposal from verifier, preserve actual violations and bounded-search uncertainty. |
| application.passports | assemble_manifest, validate_claims, export | Derived claims only; verify all referenced inputs/results; hash manifest and produce immutable exports. |
| application.evidence | register_source, derive, supersede, trace | Verify artifacts, lineage DAG, algorithm/parameter hashes; never overwrite evidence. |

## Scientific modules

`science.raster.open_source(manifest)` returns a typed raster handle, mask, CRS/body metadata and units after validating checksums and dimensions. `normalize_aoi` and `reproject` cannot default planetary data into Earth coordinates. `science.features.characterize` computes only registered metrics at explicit support windows. `science.comparison.compare` first establishes scale/quantity compatibility, then evaluates the declared rule. Missing compatibility yields UNKNOWN, not a forced interpolated match.

`science.routing.search` takes processed Earth grid artifacts, frozen constraints artifact, rover energy model and solver budget. It returns SearchResult with FOUND/EXHAUSTIVE_INFEASIBLE/BUDGET_EXHAUSTED/ERROR, candidate route hash, counters, seed and limitations. `science.routing.verify` independently loads the raw/normalized source grid, interpolates/samples route at documented spacing, and calculates constraints without trusting solver counters. See 12 for exact algorithms and arithmetic.

`science.energy.estimate` returns modeled consumption, reserve, sensitivity envelope and assumptions. Use Earth gravity for the actual Earth test energy model. An analogy to Mars does not make an Earth rover use Martian weight. `science.portfolio.optimize` solves coverage with an explicit site-count penalty and residual gaps, preserving per-site evidence and the distinction between additive and joint requirements. Monetary/travel costs are an optional extension requiring actual supplied values; do not invent them.

## Adapters

Define protocols `MetadataCatalog`, `ProductDownloader`, `RasterDecoder`, `ModelClient`, `BlobStore`, `IdentityVerifier`, `Clock` and `JobQueue`. Inject these in tests. Production model and source adapters are never selected implicitly when mode is synthetic. `ModeGuard` wraps network clients and rejects external calls for synthetic/replay runs.

Earthdata adapter resolves metadata then downloads only approved advertised links; PDS adapter resolves labels/data pairs and verifies type/length/checksum. EMIT decoder resolves the actual product's variables, nodata flags, geolocation and uncertainty; no generic `mineral` JSON endpoint is invented. Diviner follows its product geometry/time/statistics. Provider-specific parsing code belongs in the adapters; all outputs normalize into the shared evidence contract.

## Error taxonomy

Infrastructure errors include PROVIDER_AUTH_FAILED, PROVIDER_RATE_LIMITED, SOURCE_UNAVAILABLE, SOURCE_CHECKSUM_MISMATCH, UNSUPPORTED_PRODUCT, UNSUPPORTED_CRS, RESOURCE_LIMIT, TOOL_TIMEOUT, WORKER_LOST and MODEL_OUTPUT_INVALID. Scientific uncertainty includes NO_COVERAGE, SCALE_INCOMPATIBLE, INSUFFICIENT_VALID_DATA, ENERGY_UNCALIBRATED, SEARCH_LIMIT and REQUIREMENT_NOT_NATURALLY_REPRODUCIBLE. These are distinct paths: failed HTTP is not a terrain FAIL; missing mineral coverage is not evidence of absence.

Adapters return typed failures with dependency ID, retryability, safe message, and evidence/receipt references. Exceptions are mapped once at service boundaries; never catch every exception and return an empty list or numeric zero. A source download with HTTP 200 and text/html is SOURCE_CONTENT_INVALID. Deserialization rejects unexpected fields and units before analysis.

## Generated contracts and serialization

Pydantic model fields follow 05 and domain.schema.json. Explicitly serialize UTC, finite values and enums. OpenAPI export is deterministic. Export artifacts cannot leak internal paths, secret-bearing URLs, database DSNs, raw untrusted HTML or hidden model reasoning. A GeoJSON route is Earth-only and has documented coordinate order; route telemetry uses meters and seconds plus per-sample support scale.

## Acceptance

Each row above has one happy-path contract test and a meaningful failure test. Science can run without API/model imports. A backend router test substitutes a fake queue and proves no CPU analysis occurs inside the request. A malicious model proposal cannot directly set PASS, reference another workspace's evidence, select an unapproved source host, alter a threshold, or execute arbitrary code.

## Mandatory scientific assurance service

Implement application.assurance.audit(snapshot, proposed_claims, registered_receipts), deterministic SC gate evaluators and claim compiler before public scientific commits. Consume Ayan's scientific adequacy/uncertainty/verifier evidence rather than duplicating algorithms. Audit again before passport publication; persist immutable DERIVED scientific-assurance/1.0 artifact and enforce required assurance_evidence_id. Verify all frozen hashes and no unresolved claim contradictions. Same-workspace/mode and lease/revision fencing apply. Synchronous invalid claims yield SCIENTIFIC_CLAIM_REJECTED; limited/negative honest findings remain publishable. Full field, pipeline, hash and failure specification: [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md).
