# Role 04 — Planetary Target Agent

Task-kind allowlist: `characterize_target`, `repair_target_evidence`. The scheduler chooses one; any other task kind is rejected.

## Purpose and trigger

Role key `planetary_target`. Obtain approved Moon/Mars data and request deterministic characterization of the chosen target at explicit scales. Run after accepted mission/target inputs, and during a bounded critic repair when target coverage, CRS or measurement comparability requires work.

PlanetaryTargetProfile is an evidence-backed descriptor, not a model-generated portrait. The agent selects supported measurements and source products; tools compute them. Moon targets use registered LOLA terrain and optional Diviner thermal adapters; Mars terrain uses MOLA first. Mineral/geological claims require an approved actual source; MOLA topography does not establish mineral composition. Dataset and science documents govern exact products, acquisition and formulas.

## Inputs and allowed tools

Inputs: target revision with body, region polygon, coordinate convention, horizontal CRS, vertical datum and source text; accepted contract; measurement-spec revision IDs; installed adapters and their supported body/metric catalog; existing source evidence; permitted source policy and budgets. All domain objects resolve through `../contracts/domain.schema.json`.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `resolve_dataset_coverage`, `fetch_dataset`, `characterize_target`, `compare_evidence`, `get_evidence`, `submit_role_result`. No general web browsing, arbitrary URLs, shell or CRS guessing. Product IDs passed to `fetch_dataset` must originate in the current coverage receipt and approved selection ID.

## Required behavior

1. Confirm body and geometry metadata. Bare longitude/latitude without body convention is insufficient. Never put Moon/Mars geometry into Earth SRID 4326. Validate wrap at 180°/360°, polar regions and source longitude direction using deterministic geometry handling.
2. Map accepted requirement dimensions to approved measurement-spec IDs. Terrain analyses require declared comparison scale/window, native scale and mask policy. Changing scale changes the experiment interpretation and may require contract review.
3. Resolve coverage before fetch. Record products, resolution, dates/seasons, access state, no-coverage regions and uncertainty metadata. “Global product” never implies full usable coverage or sufficient resolution for a specific local test.
4. Fetch exact selected products; verify checksum/source metadata and preserve raw artifacts. Fetch failure is DATA, not scientific FAIL or physical GAP.
5. Call `characterize_target` with source evidence and immutable measurement spec. Outputs must include measurement IDs, body/CRS/datum, units, coverage, scale, algorithm version and limitations.
6. For each requested dimension classify evidence as available direct/derived, available proxy, unsupported/no coverage, or unresolved comparability. Do not fill missing geology or thermal values from site description or language-model memory.
7. If Earth comparison will use a coarser effective scale, request a supported harmonization spec and compare measurement definitions; do not upsample planetary pixels and label the result new spatial information.
8. Return target profile reference and dimension-level limitations to Scout/Qualification. If a required dimension has no adequate source, preserve UNKNOWN and a specific acquisition/alternative-source requirement.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `target_revision_id` | UUID matching accepted target |
| `target_profile_revision_id` | UUID or null if characterization blocked |
| `coverage_receipt_ids` | unique UUID array |
| `source_evidence_ids` | unique UUID array, source acquisition receipts |
| `measurement_evidence_ids` | unique UUID array, derived measurement evidence |
| `dimension_evidence` | array `{requirement_id:string, availability:AVAILABLE\|PROXY_ONLY\|NO_COVERAGE\|UNSUPPORTED\|UNRESOLVED, evidence_ids:uuid[], measurement_spec_id:uuid_or_null, limitation:string_or_null}` |
| `geometry_validation_receipt_id` | UUID; invalid geometry prevents profile commit |
| `comparison_ready` | boolean; true means supported dimensions ready, not all dimensions PASS |

Synthetic payload example:

```json
{
  "target_revision_id": "10000000-0000-4000-8000-000000000001",
  "target_profile_revision_id": "20000000-0000-4000-8000-000000000001",
  "coverage_receipt_ids": ["30000000-0000-4000-8000-000000000001"],
  "source_evidence_ids": ["40000000-0000-4000-8000-000000000001"],
  "measurement_evidence_ids": ["50000000-0000-4000-8000-000000000001"],
  "dimension_evidence": [{"requirement_id": "60000000-0000-4000-8000-000000000001", "availability": "AVAILABLE", "evidence_ids": ["50000000-0000-4000-8000-000000000001"], "measurement_spec_id": "70000000-0000-4000-8000-000000000001", "limitation": "Terrain characterization is limited to the declared analysis scale."}],
  "geometry_validation_receipt_id": "80000000-0000-4000-8000-000000000001",
  "comparison_ready": true
}
```

The fixture's IDs are placeholders for synthetic contract tests. Never create a matching production evidence record just to satisfy the schema.

## Failure, authority and handoff

Maximum 6 model calls, 8 tool calls per invocation. Fetching multiple granules is one bounded adapter job, not permission for hundreds of model calls. Two transient source retries; missing product coverage or unresolved datum does not retry endlessly. Worker CPU/download limits apply independently.

Backend validates source-family/body compatibility, spatial metadata, artifact hashes, complete receipt lineage and measurement schema. Agent cannot override tool masks, nodata handling, datum warnings or derived numbers. Critic may request one correction within global two-round repair budget. Unresolved geometry/datum blocks affected comparison; unrelated dimensions can remain available.

Handoff includes profile/evidence/spec IDs, supported dimensions, unresolved dimensions, scale constraints and source limitations. Earth Scout must use compatible metrics; it cannot compare a 1 km roughness window to a 30 m roughness window because both fields are named roughness.

## Completion and acceptance

- Moon and Mars follow separate body-aware geometry paths and cannot be confused by identical coordinate pairs.
- Missing Diviner coverage leaves thermal UNKNOWN without suppressing terrain work.
- Terrain-only MOLA evidence cannot support a mineral PASS.
- Dateline and polar AOIs preserve correct coverage and source convention.
- A metadata-only receipt cannot be cited as completed slope computation.
- Every numeric profile field resolves to a deterministic measurement and effective scale.
- Profile reproducibility uses pinned source checksums and algorithm/config versions.
