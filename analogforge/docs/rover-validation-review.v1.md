# Saved-rover review validation v1

The local computer journey on 2026-11-15 selected a saved rover, mission/rover source documents and a custom informational feature. Run `1fa9b428-4945-437f-888a-8a628bb01ee8` correctly paused when the reviewer noticed that the supplied validation reference identified `inspect_contract`, not `validate_rover_profile`. That historical result remains unchanged.

Before Rover Systems review, the scheduler now validates the exact pinned profile with the existing `RoverProfile` schema and deterministic field-consistency validator. It verifies workspace, saved revision and pinned hash, charges the run tool budget, persists the actual validation report and its receipt, and supplies both to the reviewer. The receipt input/output hashes bind the exact profile and report. Failed validation records a failed receipt and prevents model admission.

The role can retrieve the same report through the scoped `validate_rover_profile` tool. A foreign profile ID is rejected. Submission admission requires the actual successful profile-validation receipt, the same profile revision/hash and a valid report; contract inspection cannot substitute for it. Requirement-to-capability rows start Unknown until supported declarations/evidence are reviewed.

This validates a declaration, not physical performance. Null obstacle/route limits remain Unknown. Uncalibrated or absent energy models remain explicit limitations. During `validate_profile`, future candidate compatibility, continuous-route and energy-acceptance artifacts are not prerequisites unless an accepted requirement actually depends on them. Real profile errors, changed inputs, accepted-criterion conflicts and scientific review holds still require correction. No accepted terrain predicates, model budgets, rate limits or provider/account settings were weakened.

Regression coverage includes the actual retained report/receipt hashes, report-copy isolation, availability of the validation tool, foreign profile rejection, receipt substitution rejection, changed revision/workspace/hash rejection, invalid-profile failure and absent-energy Unknown behavior. This is separate from rover route verification and the passport assurance decision.

## Complete preparation handoff

The next live attempt, `87dbcbf7-ab82-4e1e-9659-b0c1d6b356d8`, passed Rover Systems validation and exposed a second issue during Planetary Target review: the preparation worker reserved the selected rover revision/hash but omitted the saved profile from the model request. The generated draft consequently described a missing rover and retained transient acceptance-state notes. That accepted historical draft and paused run remain unchanged.

Preparation now supplies the schema-validated exact saved rover profile to the model, rejects a foreign workspace before dispatch, and preserves the reserved revision/hash. The model is instructed to distinguish declared limits from calibrated evidence, avoid unrequested route/obstacle tests, and keep workflow acceptance state out of enduring scientific assumptions. No profile means `null`; a supplied profile is not falsely described as absent. Unit and worker integration regressions verify both the exact request and pinned preparation identity.

The Target reviewer follows the immutable matching contract-acceptance record. Proposal provenance remains provenance; it does not reverse acceptance. A rover profile alone does not add a wheel-scale acceptance criterion to an accepted regional-terrain task. Numeric source support, geometry-validation receipts, missing evidence and actual scope conflicts remain mandatory.

## Acceptance and resume presentation

The shared privileged policy distinguishes operator acceptance of a chosen benchmark from empirical validation of a measurement or physical rover behavior. Proposal origin and immutable drafting notes remain unchanged after acceptance. Missing/foreign/mismatched acceptance, new criteria, unsupported required constraints, data limits and material scientific issues still require review. The modeled-test strategy review cannot turn a terrain-distribution criterion into an invented route distance, exposure task or waypoint.

The guided review exposes every proposed assumption, interpretation note and excluded action in a keyboard-accessible disclosure before acceptance. Reopening a library mission restores its rover from the verified pinned operator-context snapshot, without discarding the accepted contract. Aborted or superseded context reads cannot overwrite a subsequent user edit. Null/missing rover context never fabricates a profile identity.

A budget stop explains the configured research-budget boundary and retains the old work log. Historical role concerns are shown as the current cause only when the current dependency is a review hold, not when a later budget failure stopped the run. A clean run receives its own bounded ledger; no historical budget is reset or raised.
