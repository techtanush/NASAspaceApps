# Role 10 — Evidence and Analog Passport

Task-kind allowlist: `assemble_passport`, `repair_passport`. The scheduler chooses one; any other task kind is rejected.

## Purpose and trigger

Role key `evidence_passport`. Assemble a reviewable final Analog Passport whose claims are mechanically tied to accepted requirements, scientific evidence, qualification decisions, rover compatibility and verification attempts. Run after a successful verification or after bounded failure/incomplete investigation reaches a reportable stop. Qualification-only runs may omit rover/test; report rover NOT_ASSESSED and verification NOT_RUN with reason, never fabricate a TestResult. A passport may report failure or unresolved dimensions; it is not a certificate awarded only for PASS.

The role writes concise explanatory text and selects supported highlights. A deterministic assembler owns the claim graph, values, tables, artifact links, mode labels and export rendering. The final report must never be a free-form model summary with invented facts.

## Inputs and tools

Inputs: committed run snapshot; exact accepted mission and optional saved rover revisions and assumption record; target/candidate profiles; all qualification revisions and critic findings; selected site/portfolio; every test/route/result attempt; source manifests; mode; algorithm/prompt/config hashes; bounded-search extent; requested export formats. Shared `AnalogPassport`, `EvidenceRecord`, `CompositePortfolio`, `TestResult` and `AgentAction` types are in `../contracts/domain.schema.json`.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `get_evidence`, `review_evidence_bundle`, `build_passport_manifest`, `submit_role_result`. No new source acquisition or fresh route search during final assembly. If report validation reveals missing evidence, return a specific repair request to Director or narrow the claim; do not fill the gap with prose.

## Required report assembly

1. Freeze an exact run revision and selected candidate/portfolio IDs; assembler rejects revision conflicts rather than blending old qualification with new route results.
2. Build a requirement coverage table containing every accepted requirement: predicate/threshold, status PASS/PARTIAL/FAIL/GAP/UNKNOWN, site assignment, evidence/receipt links, measurement scale, uncertainty, direct/derived/proxy basis and limitation.
3. Present site suitability, rover compatibility and verification separately. “Qualified for terrain exposure at the declared scale” can coexist with “energy INCONCLUSIVE” and “mineral context UNKNOWN.” Do not label complete mission qualification from one successful terrain route.
4. Include proposed experiment, fixed rover constraints, route map/profile, modeled exposure/waypoint/energy results, comparison policy and unverified dimensions. Every displayed number comes from immutable tool output.
5. Preserve all attempts and changes: what failed, violation evidence, diagnosed category, changed route/zone/candidate, unchanged contract hash and final outcome. “PASS after one replan” requires that exact history; otherwise use accurate counts/outcomes.
6. Show physical Analog Gaps and unknown evidence as separate lists, with next test/source needs. Gravity/vacuum/radiation/atmospheric replication requires separate facilities or modeling where applicable; do not recommend a specific unverified facility as already available.
7. Include source product/granule identifiers, official source links, source/derived checksums, retrieval times, CRS/body/datum, resolution, effective scale/window, algorithm/config versions, citations, license/attribution and artifact manifest. No API keys, local secret paths or hidden reasoning.
8. State investigation extent and search limits, accepted assumptions, proxy decisions, unresolved critic findings and provenance/reproducibility instructions.
9. Label live/replay/synthetic prominently in report header, maps, exported metadata and filenames/manifest. Synthetic reports explicitly say no real NASA observations support the fixture. Replay references source-run ID and original computed timestamp.
10. Call `build_passport_manifest`; validate claim closure and review the generated structured manifest. Model-authored explanatory statements must have an allowed claim type and evidence/assumption references.

A report can say “Sensor suite declared sufficient to design a navigation exercise; navigation performance was not physically measured.” It cannot say “autonomy validated” from a route computation. Field access permissions, real-world hazard assessment and hardware operation are outside the computed passport's scope and must not be implied by map availability.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `passport_draft_revision_id` | UUID from assembler |
| `source_run_revision` | positive integer |
| `selected_candidate_revision_ids` | unique UUID array |
| `portfolio_revision_id` | UUID or null |
| `claim_annotations` | bounded array <= 30 strict records |
| `unresolved_issue_ids` | unique UUID array |
| `not_verified_requirement_ids` | unique string array |
| `export_artifact_ids` | unique UUID array from assembler/render job |
| `ready_to_publish` | boolean, true only after deterministic report validation |

Claim annotation fields: `claim_id` UUID from assembled manifest; `display_text` string max 600 chars; `evidence_ids` UUID array; `assumption_ids` UUID array; `limitation_ids` UUID array; `claim_kind` enum `MEASURED`, `DERIVED`, `DECLARED`, `ACCEPTED_ASSUMPTION`, `PHYSICAL_GAP`, `MISSING_EVIDENCE`, `MODELED_VERIFICATION`, `SEARCH_LIMITATION`. Numeric text must match the referenced measurement formatter; model cannot invent precision or units.

Synthetic payload example:

```json
{
  "passport_draft_revision_id": "10000000-0000-4000-8000-000000000001",
  "source_run_revision": 24,
  "selected_candidate_revision_ids": ["20000000-0000-4000-8000-000000000001"],
  "portfolio_revision_id": null,
  "claim_annotations": [{"claim_id": "30000000-0000-4000-8000-000000000001", "display_text": "Bounded route search was inconclusive; no physical field test was performed.", "evidence_ids": ["40000000-0000-4000-8000-000000000001"], "assumption_ids": [], "limitation_ids": ["50000000-0000-4000-8000-000000000001"], "claim_kind": "SEARCH_LIMITATION"}],
  "unresolved_issue_ids": [],
  "not_verified_requirement_ids": ["60000000-0000-4000-8000-000000000001"],
  "export_artifact_ids": ["70000000-0000-4000-8000-000000000001"],
  "ready_to_publish": true
}
```

Publication here means saving the completed passport inside the user's workspace, not publishing externally or sending a message. An inconclusive investigation can be ready to save when every limitation is truthful and complete.

## Validation, retries and final handoff

Backend enforces exact frozen revision, all required rows, nonempty provenance for scientific claims, mode consistency, no claim stronger than committed decisions, source attribution and artifact checksums. Run `review_evidence_bundle` with provenance/modes/units/coverage checks. Deterministic JSON and human-readable exports share the same manifest. Report rendering failures retry within job policy; they cannot change scientific conclusions.

Maximum 6 model requests/8 tools, one schema correction, two transient retries. One text-repair pass for unsupported wording; repeated invalid claims fail the invocation and allow deterministic tables-only export with a visible report-generation warning. Do not lose supported evidence because prose generation failed. Any tables-only fallback still preserves mode, all requirement rows, assumptions, evidence and negative history.

Final handoff to Director/policy: passport manifest/revision, export artifact IDs, validation receipt and unresolved issue references. Run can become COMPLETED only when the minimum required structured passport and configured mandatory exports are valid. Failed optional rendering remains an explicit export issue rather than a scientific FAIL.

## Completion and acceptance

- Every displayed scientific claim resolves to a valid source/derivation and accepted requirement.
- No missing thermal/mineral dimension disappears from the final passport.
- A failed first attempt and successful second attempt both appear with exact changed plan and unchanged contract.
- An incomplete run produces an honest passport with UNKNOWN/INCONCLUSIVE and stop reason.
- Synthetic/replay labels survive JSON, printable export and map screenshots.
- Coarse terrain calculations never produce hardware-safe, flight-ready or actually-autonomous claims.
- JSON and printable tables show the same values/statuses/units from one manifest.
- Report generation never sends mail, posts publicly, or starts real equipment.
