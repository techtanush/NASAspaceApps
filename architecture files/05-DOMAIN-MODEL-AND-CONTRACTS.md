# Domain model and contracts

`contracts/domain.schema.json` defines the starting wire types using JSON Schema Draft 2020-12. Implement matching Pydantic models with `extra='forbid'`, finite numeric validation, and explicit validators below. Schema validation is necessary but not sufficient: referenced IDs, dimensional consistency, authorization, and scientific interpretation require service checks.

## Common fields and conventions

Persisted run artifacts contain `schema_version`, `id`, `workspace_id`, `run_id`, `mode`, and `created_at`. The run snapshot's `id` equals `run_id`. UUIDs are opaque; never encode coordinates or status in IDs. Timestamps carry UTC offsets and serialize as UTC. Content hashes are lowercase SHA-256 hex. Human labels are separate from identifiers. Null means unavailable; zero is an actual value.

Store percentages on the 0–100 scale only in fields explicitly ending `_pct`; fractions are 0–1. Wh and W are explicit energy/power units. Coordinates carry body, longitude convention, latitude type, horizontal CRS, and vertical datum. Earth API geometry is WGS84 longitude,latitude; planetary AOIs are body-aware bounding boxes with their original reference system.

Public AreaOfInterest inputs always use normalized positive-east longitude, in the declared NEG180_180 or ZERO_360 domain. Preserve original positive-east/positive-west direction, native frame identifier, reference radii and source latitude definition in source/normalized-asset manifests. An unresolved source frame blocks analysis; longitude-domain normalization alone is not sufficient. Native product geometry is never overwritten by public-input conventions.

## Principal records

| Record | Ownership and important behavior |
| --- | --- |
| MissionTestContract | Accepted revision of objective, target AOI, requirements, assumptions. Immutable after acceptance. Contract content hash excludes IDs, timestamps, and acceptance metadata. |
| RoverProfile | Immutable revision of physical limits, capabilities, energy assumptions. No missing numeric capability is imputed as zero. |
| PlanetaryTargetProfile | Computed target features and evidence; scale-specific context, not an assertion that the Earth must reproduce the entire planet. |
| EarthAnalogCandidate | One bounded Earth AOI with discovery origin, data coverage, metrics, evidence, and limitations. Candidate origin is immutable even if later recognized as a known analog. |
| QualificationDimension | One candidate × one requirement × one evaluation version. Status from policy engine, evidence and rule version required. |
| CompositePortfolio | A selected set of candidates and explicit per-requirement site assignments; residual gaps remain visible. |
| VerificationTest | Frozen mission/rover/candidate references, exposure constraints, waypoint/route artifacts, solver configuration and assumptions. |
| TestResult | Independent verifier outcome and telemetry, violations, search status, evidence. Does not imply physical rover execution. |
| EvidenceRecord | Source or derived artifact with lineage, product/algorithm/parameters/version/scale/limitations. Append-only. |
| ToolReceipt | Result of one tool invocation, including failure or cache hit. Receipt is not itself a scientific PASS. |
| AgentAction | Sanitized public operation attached to a run; supports the activity timeline. |
| AnalogPassport | Immutable export manifest joining the exact accepted inputs, qualifications, tests, evidence, unknowns and next steps. |
| RunSnapshot | Current read model, input revision references, result IDs, pending review, event cursor, blocked dependencies and effective-config hash. |

## Requirement semantics

Every requirement has a stable within-contract ID such as `R-SLOPE-EXPOSURE`. It defines dimension, observable, operator, numeric bounds where applicable, unit, mandatory flag, priority weight, evidence scope, accepted scale bounds, origin, and acceptance note. `minimum_support_scale_m` is the smallest acceptable analysis window; `maximum_support_scale_m` is the coarsest acceptable window. Both may be null when nonspatial; if present require minimum ≤ maximum.

`regional_context` describes landscape evidence. `terrain_model` describes the route benchmark at the available Earth DEM scale. `field_validation` requires physical/fine-scale evidence the baseline product may not possess. A terrain_model PASS cannot satisfy a field_validation requirement. A physical gap can be recorded as an acknowledged external-test obligation; it cannot be counted as an Earth-covered mandatory requirement.

For BETWEEN require lower and upper finite with lower ≤ upper. GTE requires lower; LTE requires upper. EQUALS may be categorical through observable metadata but cannot compare unrelated units. PRESENT requires a documented detection/evidence rule. NOT_NATURALLY_REPRODUCIBLE is only valid for the gap registry. Model proposals never define new scientific observables outside the server metric/rule registry.

Requirement.parameters stores structured slope_band_deg, exposure_counting, task_ids, co_location_group, comparison_rule_id and temporal_support. Fields not applicable to that observable are null/empty. Validate allowed combinations through the registered observable schema. For an exposure requirement, lower is the required distance and slope_band_deg is the angle interval; do not overload lower/upper with both meanings. Co-location IDs keep simultaneous requirements in the same site/experiment. These parameters are accepted contract content and included in its hash.

## Drafts and accepted contracts

`POST /missions` creates a mission header and draft from user intent. The draft may have no requirements. It is a `MissionDraft`, not an invalid empty MissionTestContract. A preparation job runs the Requirements role and writes a proposed immutable contract revision containing all required fields. Human acceptance sets acceptance metadata in a separate acceptance record; scientific content is not edited in place. `accepted_at` on the wire is joined from that record.

The preparation role uses a PreparationInvocation with `preparation_id` and nullable `run_id`; run-specific agent schemas are not reused with fabricated run IDs. Accepting a contract requires the user to inspect proposed defaults and confirms only that contract revision. Changing thresholds afterwards creates a new revision with acceptance pending.

Rover JSON import has a dedicated input model without database IDs. It rejects unknown units, duplicate sensors, impossible slopes, nonpositive mass/energy/speed, and reserve outside 0–100. Clearance and max obstacle height are distinct fields. A nullable energy model makes energy feasibility UNKNOWN until the user supplies or accepts coefficients.

## Referential and scientific invariants

- All referenced entities belong to the same workspace and permitted run lineage. Reused evidence records are linked through new lineage references rather than changing their original run IDs.
- A candidate AOI has body EARTH. A planetary target has body MOON or MARS. Earth-only geometry columns reject other bodies.
- Qualification PASS/PARTIAL/FAIL requires evidence IDs, an applicable rule version, and appropriate support scale. GAP requires a matching gap-registry reason. UNKNOWN requires an actionable missing-data or uncertainty explanation.
- HIGH/MEDIUM/LOW confidence is evidence strength under the qualification rubric, not a probability of mission success. UNASSESSED is explicit.
- TestResult PASS requires a verified route artifact, no mandatory violation, adequate inputs, and a successful independent verifier receipt. Failure category is null only on PASS; INCONCLUSIVE uses DATA, REQUIREMENT, SEARCH_LIMIT, or SYSTEM as appropriate.
- Search BUDGET_EXHAUSTED cannot produce exhaustive infeasibility or site rejection by itself. A route proposal with a known violation can produce FAIL for that proposal without proving every route fails.
- Passport qualified uses must be derived from qualified requirements and supported test scope. Unreviewed/challenged required evidence cannot be described as settled.
- A run without a rover has null rover_revision_id. VerificationTest always has a rover. No-rover compatibility and energy numbers remain absent.

## Versioning and reproducibility

Domain schema starts at 1.0. Additive optional changes can remain compatible; enum changes and field meaning changes need explicit version handling. An immutable `RunInputManifest` includes mission hash, rover hash or null, dataset lock hash, effective config hash, algorithm versions, source revision and mode. Deterministic result fingerprints include every numeric parameter and raster checksum; display labels and LLM wording are excluded.

Canonical hashes use RFC 8785 JSON Canonicalization Scheme through a pinned Python implementation. Reject nonfinite numbers and integers outside the interoperable JSON safe range. Hash UTF-8 canonical bytes. A passport `manifest_sha256` excludes that field, signatures and export file bytes from its own input; export artifacts each have a separate byte hash. Source identities, accepted input hashes, selected evidence/result IDs and limitations remain in the manifest hash. Store the exact canonical manifest bytes as an artifact. Frontends display the server digest rather than inventing their own serialization. See [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785).

IDs in example files are fixed for tests only. Production generates fresh UUIDs. Examples label assumptions and synthetic mode, and never contain actual NASA observations. The architecture validation script checks their schema compatibility; the implementation must add the semantic checks above.

## C1 scientific assurance invariant

AnalogPassport requires assurance_evidence_id referencing DERIVED scientific-assurance/1.0 evidence in its own workspace/run/mode, also included in evidence_ids and the canonical manifest. Its application/json artifact validates against [the assurance schema](contracts/scientific-assurance.schema.json). The report pins current upstream hashes and SC gate outcomes; invalid/stale/blocked audits cannot publish a final passport. Public scientific statuses remain unchanged. [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) defines applicability, permitted statements and acyclic hashing.
