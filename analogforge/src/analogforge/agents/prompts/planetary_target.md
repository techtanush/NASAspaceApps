# planetary_target
Allowed task kinds: characterize_target, repair_target_evidence.
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
