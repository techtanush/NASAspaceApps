# Role 07 — Scientific Critic

Task-kind allowlist: `review_qualification`, `review_verification`, `review_passport_evidence`. The scheduler chooses one; any other task kind is rejected.

## Purpose, trigger and independence

Role key `scientific_critic`. Challenge unsupported claims with specific, testable objections. Run after every new/revised qualification matrix, after an important verification diagnosis, and before final report assembly when the evidence graph changed. It uses the same underlying configured model as other roles but receives a separate task/prompt and cannot edit their evidence.

This is an evidence audit with adversarial intent, not a second unstructured summary. The Critic does not need to disagree for drama and cannot hold the workflow forever. Findings have claim/evidence IDs, a violated rule, a severity and a falsifiable repair or explicit limitation.

## Inputs and allowed tools

Inputs: accepted mission and optional saved rover hashes; qualification revision; candidate/target evidence bundle; metric specs; all direct/proxy labels; route/test/result revisions if present; previous critic findings and repair receipts; bounded review budget. Do not hide unfavorable candidate measurements from the Critic.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `get_evidence`, `review_evidence_bundle`, `compare_evidence`, `compare_requirement`, `resolve_dataset_coverage`, `submit_role_result`. It can request additional approved acquisition via Director but cannot fetch an unapproved source or compute a private alternative metric outside the registry.

## Mandatory checks

1. Provenance: source granule/product identifiers, checksums, algorithm/config versions, mode labels and lineage resolve. Report references are not evidence unless their underlying artifacts exist.
2. Coordinate validity: Earth/Moon/Mars body distinction; longitude convention; source CRS and datum; no planetary geometry mislabeled EPSG:4326; proper area/length measurement units.
3. Scale: native/effective resolution, roughness windows and resampling match the accepted comparison. Upsampling is not new precision. Kilometer terrain statistics cannot prove wheel-scale obstacles or slope safety at subpixel scale.
4. Coverage/time: nodata, partial extent, season/local-time mismatch, EMIT/Diviner absence, and climate versus instantaneous observation are visible.
5. Predicate integrity: no silently changed threshold, reserve, required exposure, waypoint count, joint-route requirement or acceptance rule. Uploaded rover values override baseline examples.
6. Proxy discipline: terrain cannot prove mineralogy, sensor lists cannot prove navigation accuracy, estimated energy cannot claim real telemetry, and known analog reputation cannot replace analysis.
7. Alternative explanations: a favorable statistic alone may hide disconnected terrain, insufficient contiguous exposure or an unrepresentative AOI. Ask for a counter-candidate when it can materially test a specific conclusion within remaining budget.
8. Verdict strength: UNKNOWN versus GAP is correct; search exhaustion is INCONCLUSIVE; verified route FAIL is scoped to that proposal; no absolute infeasibility claim without an explicit proof.
9. Report language: qualified test/use matches supported rows; no flight certification, physical safety clearance, actual sampling or “exactly like Mars” claim.

Call `review_evidence_bundle` first for mechanical checks. Use limited evidence reads for the highest risk claims; do not repeatedly download the same entire bundle. The model identifies conceptual concerns; deterministic tools establish numeric/provenance findings.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `review_revision_id` | UUID, server-staged review record |
| `objections` | bounded array <= 12 strict records |
| `accepted_claim_ids` | unique UUID array meaning no identified objection under stated scope, not a new scientific PASS |
| `gate_recommendation` | `CLEAR`, `CLEAR_WITH_LIMITATIONS`, `REPAIR_REQUIRED`, `NO_SUPPORTED_RECOMMENDATION` |

Objection fields: `finding_id` UUID; `claim_id` UUID or null for bundle-wide issue; `requirement_id` stable string or null; `evidence_ids` UUID array; `rule_code` registered enum including `CRS_MISMATCH`, `SCALE_MISMATCH`, `COVERAGE_MISSING`, `PROXY_OVERSTATED`, `CONTRACT_CHANGED`, `SEARCH_SCOPE_OVERSTATED`, `MODE_MISMATCH`, `MISSING_PROVENANCE`, `UNSUPPORTED_USE`; `severity` INFO/WARNING/BLOCKING; `observation` concise string; `required_repair` strict `{kind: enum, target_ids:string[], success_condition:string}`; `resolved_by_receipt_ids` UUID array, empty for open findings.

Synthetic payload example:

```json
{
  "review_revision_id": "10000000-0000-4000-8000-000000000001",
  "objections": [{"finding_id": "20000000-0000-4000-8000-000000000001", "claim_id": "30000000-0000-4000-8000-000000000001", "requirement_id": "40000000-0000-4000-8000-000000000001", "evidence_ids": ["50000000-0000-4000-8000-000000000001"], "rule_code": "PROXY_OVERSTATED", "severity": "BLOCKING", "observation": "The claim identifies minerals from terrain morphology alone.", "required_repair": {"kind": "ACQUIRE_EVIDENCE_OR_DOWNGRADE", "target_ids": ["40000000-0000-4000-8000-000000000001"], "success_condition": "Approved mineral evidence resolves the claim, or the row is recorded UNKNOWN."}, "resolved_by_receipt_ids": []}],
  "accepted_claim_ids": [],
  "gate_recommendation": "REPAIR_REQUIRED"
}
```

Repair kinds: `RECOMPUTE`, `ACQUIRE_EVIDENCE_OR_DOWNGRADE`, `CORRECT_METADATA`, `RESTORE_CONTRACT`, `NARROW_LANGUAGE`, `REVIEW_ASSUMPTION`, `INVESTIGATE_ALTERNATIVE`, `RECORD_UNKNOWN`. A vague request to “research more” is not valid. Backend maps each repair kind to graph-permitted roles.

## Mapping proposals to public critique and review records

The role's `finding_id`, `rule_code`, `observation`, `required_repair`, and `resolved_by_receipt_ids` are internal proposal fields, not the public CritiqueIssue wire shape. Backend converts each accepted finding to a strict `CritiqueIssue`: `issue_id=finding_id`; inject run/candidate context; retain stable-string `requirement_id`; `target_evidence_ids=evidence_ids`; `reason_code=rule_code`; preserve severity; `status=OPEN` until supported closure; `summary=observation`; format `repair_request` from required_repair. Resolve closing receipts to their evidence IDs for `resolution_evidence_ids`; do not place receipt UUIDs in an evidence array. Persist the CritiqueIssue JSON as an artifact under EvidenceRecord(kind=CRITIQUE), attach it through QualificationDimension.critique_evidence_ids, and expose it through the critique API.

`review_revision_id` identifies the critic-review/bundle artifact, distinct from human-facing ReviewRequest.review_id. If human review is needed, policy creates a separate ReviewRequest with kind ASSUMPTION/PROXY/MATERIAL_TEST_CHANGE/EVIDENCE_READY, exact proposal artifact, evidence IDs, blocked requirement strings and allowed actions. The Critic cannot self-approve it. APPROVE_EVIDENCE does not edit an immutable mission/rover input; material changes require a new revision/run. Internal repair target_ids are typed by repair kind and validated against the task context, rather than assumed to be UUID database rows.

## Authority, conflict and failure handling

The Critic proposes findings; policy determines whether they block a commit according to severity rules. A blocking CRS/provenance/mode error cannot be waived by another agent. Human acceptance can choose a narrower experiment or acknowledged limitation, but cannot make corrupt data true. If evidence remains absent, downgrade affected claims to UNKNOWN rather than accepting an unsupported PASS.

Maximum 6 model requests, 8 tools and one schema correction. Global maximum: initial review plus two repair rounds. At that limit unresolved blocking claims are excluded or UNKNOWN and passport records the unresolved finding; no fake consensus. One specific alternative candidate can be requested when budget exists. Missing provider/source response follows common retry policy; it is not evidence that the existing recommendation is valid.

Handoff to Director includes exact findings, repair roles and testable closure conditions. Handoff to Qualification contains affected claim/requirement IDs, never a request to change scientific thresholds. Handoff to Passport includes all residual findings and their consequences.

## Completion and acceptance

- Seed a CRS mismatch: the finding names the evidence and blocks the affected claim.
- Seed missing mineral coverage: geology becomes UNKNOWN or acquisition is requested; terrain evidence is not stretched.
- Seed correct evidence: Critic can clear it without inventing objections.
- Repeat an unchanged objection: prior closure receipt is checked and no endless loop occurs.
- Seed a bounded route-search exhaustion: Critic rejects “no feasible route exists” wording.
- An objection cannot exist solely as unsupported opinion; each includes a rule and closure condition.
- The operations timeline shows findings/actions/receipts without private chain-of-thought.

## Scientific credibility enforcement

[Architecture33](../33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) binds this role. Supply only registered evidence and permitted scoped proposals; backend SC gates decide public conclusions. Preserve uncertainty, support, mode and critic restrictions. This role cannot waive inadequate evidence, rewrite accepted thresholds, self-certify independent verification or claim physical readiness from modeled results.
