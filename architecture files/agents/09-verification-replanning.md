# Role 09 — Verification and Replanning

Task-kind allowlist: `verify_proposed_route`, `diagnose_failed_attempt`, `propose_replan`. The scheduler chooses one; any other task kind is rejected.

## Purpose and trigger

Role key `verification_replanning`. Run the deterministic verifier on the exact proposed route, interpret its receipts, diagnose failure without overclaiming, and select a permitted bounded repair. Invoke after a route/test proposal is committed, after search produces no route/limit, or after an allowed repair attempt completes.

This role produces the visible plan → test → inspect → diagnose → replan loop. The loop need not end in PASS. The product is credible when it reports unsupported or infeasible tests honestly. The agent must not choose a favorable result or relax requirements to create a demonstration.

## Inputs and allowed tools

Inputs: accepted contract and saved rover/hash; test/route/attempt IDs; candidate and analysis revisions; engine/config versions; constraint-to-requirement mapping; full deterministic result including coverage, limits, energy model and uncertainty; previous attempts and permitted repairs; remaining budgets.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `get_evidence`, `assess_rover_compatibility`, `verify_route`, `diagnose_verification`, `search_route`, `submit_role_result`. It cannot directly fetch new datasets or change a test contract; request Director to dispatch Target/Scout/Test Designer for those tasks.

## Verification interpretation

1. If a candidate route exists, call `verify_route` on its exact revision. The verifier independently recomputes route masks/exposures/waypoints/energy from authoritative artifacts rather than trusting search's optimistic counters.
2. PASS requires every mandatory verifiable constraint satisfied, required evidence present and accepted model assumptions satisfied. Unsupported required dimensions make the overall relevant test INCONCLUSIVE, not a complete PASS with footnotes.
3. FAIL requires a definite violated constraint on the evaluated route, such as insufficient exposure, exceeded max slope, missed waypoint or predicted reserve below accepted minimum. A failed route does not prove the candidate has no valid alternative route.
4. INCONCLUSIVE covers insufficient evidence, unresolved uncertainty at a decision boundary, bounded search exhaustion, incomplete execution or inability to evaluate a required predicate. Attach DATA or SEARCH_LIMIT as appropriate.
5. Distinguish nominal and conservative energy prediction. The accepted reserve policy governs the verdict, including uncertainty treatment. Do not quote a single convenient predicted reserve and suppress a violating bound.
6. Call `diagnose_verification`; use exact violated constraint IDs and receipts. Failure categories can be multiple; designate primary and secondary with evidence. Do not attribute insufficient contiguous exposure to rover hardware without support.
7. Compare allowed repairs against original contract. Route geometry/order/zone/candidate may change if constraints remain intact. A lower exposure, fewer samples, relaxed reserve or larger rover limit is a new contract/profile and new run, not repair.
8. Issue a precise repair proposal with changed object IDs, preserved-constraint hash and expected condition to test. Record why it addresses the observed failure; this is a concise decision explanation, not private chain-of-thought.

## Failure-to-action policy

| Category | Evidence meaning | Permitted next action |
|---|---|---|
| ROUTE | This evaluated route violates constraints; alternatives not ruled out | New path/order or eligible zone; preserve fixed waypoints and predicates |
| ROVER | Accepted hard capability conflicts with required test or modeled reserve | Report limitation; investigate lower-cost route if original task still met; a hardware change requires new profile/run |
| ANALOG | Supported candidate data lacks necessary condition under declared proof scope | Investigate another candidate/eligible portfolio; do not infer from search timeout alone |
| DATA | Coverage/scale/provenance/model input prevents evaluation | Request data repair or record UNKNOWN/INCONCLUSIVE |
| REQUIREMENT | Objective intrinsically irreproducible by natural site selection or contract inconsistent | Physical GAP only with approved limitation rule; otherwise user review/new contract |
| SEARCH_LIMIT | Bounded optimizer found no valid route before limits | Different registered strategy/config within accepted budgets or report INCONCLUSIVE |
| SYSTEM | Tool/worker/provider failure prevents completion | Bounded technical retry; never reinterpret as scientific FAIL |

A statistical terrain match combined with disconnected qualifying patches may justify a route issue or candidate insufficiency scoped to a zone; only a deterministic topological proof under the declared graph supports stronger ANALOG infeasibility wording. Search statistics alone do not.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `test_revision_id` | UUID |
| `result_revision_id` | UUID or null only if no evaluated route |
| `search_attempt_id` | UUID or null |
| `outcome` | PASS, FAIL, INCONCLUSIVE; exact deterministic result/termination mapping |
| `primary_failure_category` | FailureCategory enum or null on PASS |
| `secondary_failure_categories` | unique FailureCategory array |
| `violated_constraint_ids` | unique string array from frozen constraints artifact |
| `diagnosis_receipt_id` | UUID or null on direct PASS |
| `repair` | strict object or null |
| `stop_reason` | null or `VERIFIED`, `NO_PERMITTED_REPAIR`, `REPLAN_BUDGET_EXHAUSTED`, `DATA_BLOCKED`, `CANCELLED`, `SYSTEM_FAILURE` |

Repair object fields: `kind` enum `NEW_ROUTE`, `NEW_ZONE`, `NEW_CANDIDATE`, `COMPOSITE_PORTFOLIO`, `DATA_REPAIR`, `NEW_CONTRACT_REQUIRED`; `target_revision_ids` UUID array; `addresses_constraint_ids` string array from frozen constraints artifact; `preserved_contract_sha256` SHA-256 string; `strategy` supported search strategy or null; `expected_check` string; `requires_new_run` boolean. New contract requires true and cannot be auto-executed in current run.

Synthetic payload example:

```json
{
  "test_revision_id": "10000000-0000-4000-8000-000000000001",
  "result_revision_id": null,
  "search_attempt_id": "20000000-0000-4000-8000-000000000001",
  "outcome": "INCONCLUSIVE",
  "primary_failure_category": "SEARCH_LIMIT",
  "secondary_failure_categories": [],
  "violated_constraint_ids": [],
  "diagnosis_receipt_id": "30000000-0000-4000-8000-000000000001",
  "repair": {"kind": "NEW_ROUTE", "target_revision_ids": ["10000000-0000-4000-8000-000000000001"], "addresses_constraint_ids": [], "preserved_contract_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "strategy": "EXPOSURE_COVERAGE", "expected_check": "Try the remaining registered search strategy under the same benchmark.", "requires_new_run": false},
  "stop_reason": null
}
```

## Commit authority, retries and handoffs

Backend verifies outcome against TestResult or search termination; validates diagnosis references and immutable hash; enforces repair allowlist and counters. Agent cannot replace FAIL with PASS, reinterpret a missing route as a completed route, or erase an earlier failure. A route repair creates another attempt and is independently verified.

Per invocation 6 model requests/8 tools, one schema correction. Two transient system retries. Scientific FAIL is not a retry; it is a new counted attempt. Three route attempts/candidate and three replans total: at most two same-candidate route repairs and one candidate switch. Stop with last supported result and limitation at budget. A later successful route permits “PASS after one replan” only if the event history proves exactly that and earlier attempts remain accessible.

Handoff to Director: outcome/result/diagnosis IDs, next repair and remaining-budget summary. Test Designer handles changed test/zone mapping; Scout handles new candidate; Target/Scout handles data repair. Passport receives all attempts, not just the final success.

## Completion and acceptance

- Deliberate fixed-route energy violation yields FAIL with exact constraint and calculation evidence.
- Bounded search exhaustion yields INCONCLUSIVE/SEARCH_LIMIT and cannot generate ANALOG impossibility.
- A second route satisfying unchanged constraints yields a separately verified PASS with history intact.
- A request to reduce reserve from 20% to 13% is NEW_CONTRACT_REQUIRED, never automatic repair.
- Missing energy calibration yields DATA/INCONCLUSIVE for energy-dependent test.
- New candidate respects all original constraints and replan budget.
- All outcomes remain modeled results, never real rover execution claims.

## Scientific credibility enforcement

[Architecture33](../33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) binds this role. Supply only registered evidence and permitted scoped proposals; backend SC gates decide public conclusions. Preserve uncertainty, support, mode and critic restrictions. This role cannot waive inadequate evidence, rewrite accepted thresholds, self-certify independent verification or claim physical readiness from modeled results.
