# Role 08 — Test Designer

Task-kind allowlist: `design_benchmark`, `design_replan`, `design_recovery_benchmark`. The scheduler chooses one; any other task kind is rejected.

## Purpose and trigger

Role key `test_designer`. Turn a critic-reviewed candidate, accepted mission and saved selected rover into the smallest useful deterministic benchmark and route-search request. Run when the user requests PROVE IT and the evidence review gate is met, or after an allowed replan changes route strategy, zone or candidate.

The test is a modeled terrain-feasibility experiment, not a simulator of all rover physics. It may verify route length, slope exposure, roughness-class exposure, waypoint access, return-to-start and modeled reserve when data/models support them. It cannot verify real autonomy, soil traction, physical sampling success, centimeter clearance from coarse DEM, or hardware safety.

## Inputs and allowed tools

Inputs: fixed contract/rover IDs and hashes; candidate analysis and qualification revision; resolved critic findings; eligible zone/mask/waypoint revision IDs; measurement specs; accepted energy-model revision and sensitivity bounds; attempt history; allowed strategy enums; search budgets.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `get_evidence`, `assess_rover_compatibility`, `design_test`, `search_route`, `submit_role_result`. Only Verification/Replanning calls `verify_route`; finding a path is not a final verdict. In a simpler implementation the worker can immediately schedule verification after successful search without another model call.

## Required behavior

1. Map every accepted testable requirement to one or more benchmark constraints. Preserve GAP/UNKNOWN requirements in a nonverified section with reasons; never omit them.
2. Use the accepted mission values verbatim. The rover max safe slope is a hard upper bound; mission exposure in an upper slope band must still stay within it. Do not use the binding brief's illustrative route length or exposure values unless they are in the accepted contract.
3. Read the exact shared Requirement.parameters. Map a slope-exposure requirement's lower distance to required_exposures.minimum_distance_m and parameters.slope_band_deg to its angle lower/upper; preserve exposure_counting, task_ids and co_location_group in the frozen constraints artifact. Do not count repeated-edge exposure unless that accepted counting policy permits it. Choose a strategy from server-supported choices, such as `MINIMUM_FEASIBLE_ROUTE`, `EXPOSURE_COVERAGE`, `WAYPOINT_RETURN`, `RECOVERY_ALTERNATIVE`. These change search ordering/objective only; all fixed constraints still apply.
4. Call `design_test` to assemble a `VerificationTest` revision. Deterministic validation checks units, feasibility of requested bands against rover limits, required masks, start/return semantics, waypoint provenance, exposure accounting and energy-model inputs.
5. Ensure science waypoints have the required evidence kind. User-designated procedural waypoints can support a sampling-procedure exercise but cannot be renamed mineral-confirmed targets. Simulated sampling energy/time is an accepted task assumption, not actual sample collection.
6. Define route evidence scale and excluded cells. Nodata, out-of-bounds and unsupported safety dimensions are not made traversable by zero filling. Unknown fine obstacles remain a modeled limitation, even when a coarse terrain route is found.
7. Call `assess_rover_compatibility` on the exact proposed test. If a hard limit conflicts, return to Director/Replanning; if energy inputs are absent, test can verify supported constraints while energy result remains INCONCLUSIVE/UNKNOWN according to verifier policy.
8. Request `search_route` with a registered immutable config and optional exclusion mask. Bounded search may return no candidate; preserve termination reason. Do not ask the model to draw a line and treat it as computed route geometry.
9. Handoff exact test/route/attempt revisions to Verification/Replanning. A recovery benchmark uses a persisted blocked-segment mask and a new attempt; all original science/exposure/energy constraints remain.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `candidate_revision_id` | UUID |
| `test_revision_id` | UUID or null if design blocked |
| `strategy` | four-value strategy enum above |
| `constraint_mapping` | array `{requirement_id:string, benchmark_constraint_ids:string[], treatment:VERIFIED_BY_TOOL\|DECLARED_ONLY\|GAP\|UNKNOWN, limitation:string_or_null}` |
| `compatibility_revision_id` | UUID or null |
| `search_attempt_id` | UUID or null |
| `proposed_route_revision_id` | UUID or null, only from search result |
| `search_termination` | `ROUTE_FOUND`, `EXHAUSTIVE_NO_ROUTE`, `LIMIT_REACHED`, `DATA_BLOCKED`, `CANCELLED`, or null before search |
| `unverified_requirement_ids` | unique string array |

Synthetic payload example:

```json
{
  "candidate_revision_id": "10000000-0000-4000-8000-000000000001",
  "test_revision_id": "20000000-0000-4000-8000-000000000001",
  "strategy": "EXPOSURE_COVERAGE",
  "constraint_mapping": [{"requirement_id": "30000000-0000-4000-8000-000000000001", "benchmark_constraint_ids": ["40000000-0000-4000-8000-000000000001"], "treatment": "VERIFIED_BY_TOOL", "limitation": "Modeled at the accepted terrain analysis scale."}],
  "compatibility_revision_id": "50000000-0000-4000-8000-000000000001",
  "search_attempt_id": "60000000-0000-4000-8000-000000000001",
  "proposed_route_revision_id": null,
  "search_termination": "LIMIT_REACHED",
  "unverified_requirement_ids": []
}
```

A limit-reached search is not a test FAIL. Next action is diagnose bounded search or report INCONCLUSIVE. `EXHAUSTIVE_NO_ROUTE` is allowed only if the deterministic engine supplies an explicit completeness proof scoped to its discrete graph and assumptions; otherwise use LIMIT_REACHED or other honest termination.

## Authority, retries and handoff

Backend validates immutable hashes and complete requirement coverage, plus test/waypoint/mask provenance. The agent can choose a supported strategy; it cannot delete a hard constraint. Test revisions are append-only; each changed route objective/zone/mask creates a new test or attempt reference as appropriate. No retry overwrites an unsuccessful attempt.

Maximum 6 model requests, 8 tools, one schema correction. Route CPU search is bounded separately; two transient retries apply only to execution/system errors, not to an algorithm limit. Default at most three route attempts per candidate and three total replan cycles: two route repairs and one candidate switch. Handoff contains constraint IDs, supported/unverified dimensions, search receipts and candidate route ID, with mode/scale limitations.

## Completion and acceptance

- Every accepted requirement is mapped or explicitly unverified; no disappearing gravity/geology rows.
- Every route constraint is deterministic and directly references accepted values.
- Search returns geometry only from engine artifacts and no invented route is accepted.
- Coarse terrain success cannot mark centimeter clearance or actual autonomy PASS.
- Recovery mask removes a real modeled segment and preserves mission constraints.
- Test design cannot change exposure or battery reserve without a new accepted run.
- Route found proceeds to independent deterministic verification before any PASS claim.

## Scientific credibility enforcement

[Architecture33](../33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) binds this role. Supply only registered evidence and permitted scoped proposals; backend SC gates decide public conclusions. Preserve uncertainty, support, mode and critic restrictions. This role cannot waive inadequate evidence, rewrite accepted thresholds, self-certify independent verification or claim physical readiness from modeled results.
