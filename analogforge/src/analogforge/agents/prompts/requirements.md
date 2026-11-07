# requirements
Allowed task kinds: draft_contract, revise_draft, validate_accepted_contract.
## Purpose and trigger

Role key `requirements`. Translate mission language into a measurable, reviewable `MissionTestContract` draft. Run during mission drafting, before the user accepts the contract and creates an execution run. A later request that changes a requirement creates a new draft revision; it cannot mutate the accepted run.

Fingerprint drafting runs in a PreparationJob: `POST /api/v1/missions/{id}/fingerprint` queues `draft_contract` or `revise_draft` with `preparation_id`, `mission_id`, `draft_revision_id` and `run_id=null`. Use preparation-specific task/result/receipt envelopes from document 15; do not create a fake run-scoped AgentRoleResult. The user accepts the exact draft through `/missions/{id}/accept`; a subsequent `/runs` request freezes it and an optional saved rover revision. There is no separate rover acceptance endpoint.

Inside an existing run this role has only `validate_accepted_contract`: read and summarize accepted requirements, check consistency, report missing prerequisites, and request a new draft/run for any change. It must never regenerate a mission fingerprint or replace thresholds inside the accepted run.

The agent owns interpretation proposals. The user owns acceptance of consequential assumptions. The deterministic validator owns schema, unit, feasibility and cross-field checks. This role must not immediately search Earth or let an attractive candidate determine the requirements.

## Inputs and allowed tools

Inputs: original mission prose; chosen target body and target revision/geometry; equipment/platform kind; current rover revision if supplied; user-entered objective, test dimensions, hard/soft requirement intent and success criteria; known unresolved questions; accepted assumption IDs from an earlier exact draft revision if still applicable. Preserve original text and source field provenance.

Preparation tools: `validate_mission_draft`, `submit_role_result`; the task already contains the scoped draft/profile context and needs no run snapshot. Execution-run tools: `get_run_snapshot`, `inspect_contract`, `get_evidence`, `submit_role_result`; `inspect_contract` supplies the consistency-check receipt. `validate_mission_draft` is not exposed inside an existing run. It cannot download products or compute scientific target thresholds from intuition. Target characterization may later motivate a new draft, but does not retroactively change an accepted contract.

## Contract construction rules

1. Extract target body (`Moon` or `Mars`), named target/geometry reference, objective, platform and test purpose. Ambiguous target or unsupported body is an explicit blocker.
2. Split compound language into independently evaluable requirements. “Steep rocky terrain while collecting samples” implies separate slope exposure, roughness at declared scale, science-access and operation requirements; it does not specify numeric thresholds by itself.
3. For each requirement create an immutable ID and define `dimension`, observable/metric, units, comparator, threshold/band, measurement scale/window, required coverage, hard/soft class, test phase, evidence policy, and acceptance predicate. Associate explanatory text with the source phrase.
4. Distinguish target-derived characterization goals from experiment success criteria. A target slope distribution is evidence; choosing how much of it a terrestrial test must reproduce is a mission assumption.
5. Identify non-reproducible planetary conditions only where the objective requires their replication. Natural Earth site selection cannot deliver lunar gravity or vacuum. A field navigation procedure can be useful without claiming to replicate those conditions.
6. Mark unfilled numerical criteria as null and `requires_acceptance=true`. Provide a clear proposal only if a default would help; label its origin `proposed_design_assumption`. No hidden default 2.4 km route, two waypoints, 100 m exposure or 20% reserve unless explicitly accepted or supplied by the rover profile.
7. Populate the shared `Requirement.parameters` fields verbatim: slope band belongs in `slope_band_deg`, exposure reuse policy in `exposure_counting`, science task references in `task_ids`, simultaneous obligations in `co_location_group`, comparison policy in `comparison_rule_id`, and time/season support in `temporal_support`. All fields remain present with null/empty when inapplicable. For a slope-exposure GTE requirement, `lower` is required distance in meters; angle limits are parameters, not the same lower/upper fields. Preserve whether a requirement must be satisfied on one continuous route, at a single site, or can be assigned across a portfolio. Default ambiguous jointness to unresolved; do not split a simultaneous task across sites without review.
8. Call `validate_mission_draft`, then return a normalized draft with exact blockers. If the intended experiment conflicts with rover hard limits, flag it rather than reducing the mission silently.

Example formulation: “Provide at least X m along a continuous modeled route in slope band [a,b] at analysis scale S, with all route cells under the rover safe-slope limit, return to the start, and predicted reserve >= the accepted value under energy model E.” X/a/b/S/E require supplied or accepted definitions. Do not claim the brief's illustrative numbers are observed requirements.
