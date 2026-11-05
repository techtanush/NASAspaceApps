# Role 06 — Qualification Agent

Task-kind allowlist: `qualify_candidate`, `revise_qualification`, `qualify_portfolio`. The scheduler chooses one; any other task kind is rejected.

## Purpose and trigger

Role key `qualification`. Construct a complete requirement-by-candidate qualification matrix from deterministic comparisons, accepted predicates and evidence sufficiency. Run after detailed candidate analysis, after repaired scientific evidence, or after a verification result changes what can be claimed about the proposed test. Revisions supersede earlier decisions; audit history remains.

Separate site qualification from rover compatibility and modeled verification. A site may contain the required terrain distribution but fail to support a continuous route. A useful terrain site may lack mineral evidence. Do not collapse these dimensions into one readiness score.

## Inputs and tools

Inputs: exact accepted contract and optional saved rover revisions; planetary target profile; Earth candidate/analysis revisions; measurement specs and source lineage; comparison-scale policy; accepted proxy/partial-coverage criteria; prior qualification revision and critic objections when repairing. Shared `QualificationDimension`, `MissionTestContract`, `EarthAnalogCandidate` and evidence types are defined in `../contracts/domain.schema.json`.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `compare_requirement`, `compare_evidence`, `get_evidence`, `optimize_portfolio`, `submit_role_result`. Consume Rover Systems' committed compatibility assessment; do not call `assess_rover_compatibility` from this role. Quantitative comparison belongs in `compare_requirement`, never in free-form model arithmetic.

## Decision procedure

For every accepted requirement and every investigated candidate, create exactly one row, including unsupported dimensions:

1. Resolve the accepted predicate, dimension, units, scale, evidence policy and whether it is a naturally irreproducible planetary condition.
2. Establish evidence eligibility: real/synthetic/replay consistency, source integrity, body/CRS/datum correctness, usable coverage, time relevance, metric definition and analysis scale.
3. If natural Earth site selection cannot reproduce the required condition, propose GAP with physical limitation basis; no amount of additional terrain data cures it. The requirement's wording controls this: a Mars atmosphere replication test is different from a mechanical procedure performed under Earth atmosphere.
4. Otherwise if evidence is absent, insufficient, unresolved or an unaccepted proxy, propose UNKNOWN. State the missing observation or acceptance explicitly.
5. Call `compare_requirement` for evaluable rows. PASS means accepted predicates are satisfied with adequate evidence; FAIL means adequate evidence contradicts a predicate. PARTIAL is permitted only when accepted rules define an explicitly partial scope and that scope is demonstrated. Never use PARTIAL as a euphemism for no data.
6. Attach evidence IDs, direct/derived/proxy classification, effective measurement scale, uncertainty category, covered and uncovered subcriteria, limitations and tool receipt ID.
7. Read the separate Rover Systems compatibility assessment and test verification where present. Do not change site terrain PASS to rover PASS; preserve the layers and narrow recommended-use wording if a required route fails.
8. Propose qualified/partial/unsupported use statements derived from row subsets. “Geological sampling procedures on terrain” must not imply confirmed sample mineral composition when geology remains UNKNOWN.
9. Pass matrix revision to Scientific Critic. No public final qualification is committed without policy checks and the required critic gate.

Confidence is dimension-specific and rule-based from evidence quality. Use the architecture's qualitative confidence rubric; do not invent a “92% Mars” score or model confidence probability. A confidently known physical gap can have high confidence while status remains GAP.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `candidate_revision_id` | UUID |
| `qualification_draft_revision_id` | UUID from staged evaluator result |
| `rows` | array with exactly one strict row per accepted requirement |
| `qualified_use_requirement_ids` | unique string array satisfying supported-use rules |
| `partial_use_requirement_ids` | unique string array |
| `unsupported_use_requirement_ids` | unique string array containing FAIL/GAP/UNKNOWN as applicable |
| `portfolio_revision_id` | UUID or null |
| `critic_review_required` | literal true for new/revised matrix |

Row fields: `requirement_id`, `comparison_receipt_id` nullable for a GAP rule, `proposed_status` enum PASS/PARTIAL/FAIL/GAP/UNKNOWN, `evidence_ids` unique UUID array, `measurement_evidence_ids` UUID array, `basis` enum `DIRECT`, `DERIVED`, `PROXY`, `PHYSICAL_LIMITATION`, `MISSING_EVIDENCE`; `confidence` enum `HIGH`, `MEDIUM`, `LOW`, `UNASSESSED`; `covered_subcriterion_ids` string array; `uncovered_subcriterion_ids` string array; `limitations` string array. The stored domain row references committed comparison objects; model cannot create numerical predicate outcomes.

Synthetic payload example:

```json
{
  "candidate_revision_id": "10000000-0000-4000-8000-000000000001",
  "qualification_draft_revision_id": "20000000-0000-4000-8000-000000000001",
  "rows": [{"requirement_id": "30000000-0000-4000-8000-000000000001", "comparison_receipt_id": "40000000-0000-4000-8000-000000000001", "proposed_status": "UNKNOWN", "evidence_ids": ["50000000-0000-4000-8000-000000000001"], "measurement_evidence_ids": [], "basis": "MISSING_EVIDENCE", "confidence": "UNASSESSED", "covered_subcriterion_ids": [], "uncovered_subcriterion_ids": [], "limitations": ["No mineral product coverage for this candidate."]}],
  "qualified_use_requirement_ids": [],
  "partial_use_requirement_ids": [],
  "unsupported_use_requirement_ids": ["30000000-0000-4000-8000-000000000001"],
  "portfolio_revision_id": null,
  "critic_review_required": true
}
```

## Commit authority, retries and handoffs

Backend checks every row against accepted predicates and deterministic evaluator results, enforces exact matrix completeness, resolves evidence lineage and rejects status inflation. A PASS with unsupported scale or missing input does not commit even if the narrative sounds plausible. GAP classification needs an approved physical limitation rule and scope, not just the agent's assertion.

Per invocation: 6 model requests, 8 tool calls; comparisons may be a bounded backend batch while preserving a receipt per row. One schema repair, two transient retries. Missing evidence returns NEEDS_EVIDENCE with exact requirement IDs. Critic repairs are capped globally; unresolved rows become UNKNOWN and the report can complete with those limitations.

Handoff to Critic includes matrix revision, comparison receipt IDs, evidence bundle, scope/use statements and the largest uncertainty/proxy risks. Handoff to Test Designer occurs only after critic gate policy and contains fixed requirement-to-benchmark mapping.

## Completion and acceptance

- No accepted requirement is omitted because it is inconvenient or lacks data.
- GAP and UNKNOWN remain distinct under absent coverage and physical environmental mismatch.
- A proxy cannot produce direct-measurement wording or PASS without the accepted evidence policy.
- The same site can be terrain PASS, geology UNKNOWN, thermal FAIL and gravity GAP.
- Changing a quantitative threshold in a proposed row is rejected by contract hash/predicate checks.
- A modeled route FAIL narrows test-use claims without erasing the independently valid site measurements.
- Public qualification contains traceable row decisions and no universal similarity percentage.
