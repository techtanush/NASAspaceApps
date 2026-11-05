# Tanush: backend enforcement of scientific credibility

Mandatory references: [architecture33](../../architecture%20files/33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md), [shared credibility gate](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md), architecture05/06/11/12/19/22/26/29 and the [assurance schema](../../architecture%20files/contracts/scientific-assurance.schema.json). This is implementation work in your platform/integration scope, not just prompt text.

## F0 contract and T2 persistence

Use C1 including required `AnalogPassport.assurance_evidence_id`. Export the updated public schema and shared private types so Ayan and Aradhya do not invent audit formats. Add typed observable-policy, adequacy receipt, gate outcome, audited claim and resolved passport-bundle models. Pydantic must reject nonfinite quantities, unexpected IDs and fields. Missing applicability/policy cannot default to success.

Persist immutable assurance artifacts as DERIVED evidence with algorithm `scientific-assurance/1.0`; keep parent DAG, exact source/parameter/algorithm/policy/snapshot hashes and visible limitations. Resolve Ayan's local evidence keys atomically before auditing. Source names or model citations without acquired/decoded bytes cannot satisfy source integrity. The passport's assurance pointer must resolve in its workspace/run/mode and be included in its evidence list and canonical manifest.

## T4 deterministic enforcement

Implement `application.assurance.audit` and a deterministic claim compiler. Apply SC-01–SC-15 before scientific result commit and again at passport assembly. Ayan owns scientific mathematics; call his typed adequacy and independent verification results, then enforce authoritative identities, revision, mode, frozen policy, issue resolution and permitted statements. Do not replace a missing scientific result with your own estimate or an LLM judgment.

The model can propose, cite registered evidence and request tools. It cannot issue PASS, erase a failure, adjust thresholds, waive an unresolved issue, fabricate measured uncertainty, approve itself as independently verified or promote synthetic/replay to live. User review can accept an explicit allowed assumption, but cannot repair invalid source bytes or certify a physical claim. Material changes follow accepted-revision/new-run rules.

An audit containing missing data should allow a truthful UNKNOWN/limited report. A mathematically supported FAIL is publishable. Publication BLOCKED is reserved for invalid/inconsistent included claims or integrity defects; do not equate a negative science result with an application crash. Essential unknowns/failures forbid blanket mission qualification. Preserve the full attempt/critic/repair history.

## T5 publication and consumer handoff

Compile all conclusion-bearing strings from audited scope. Pass resolved assurance JSON through the existing pure renderer bundle. Serve it using evidence/artifact endpoints; expose no raw secrets/internal paths. No passport-created event or final export may precede successful final audit/transaction. Lost lease, cancellation, stale snapshot or changed policy prevents late publication. Persist safe rejection receipts using `SCIENTIFIC_CLAIM_REJECTED` and structured SC issue codes.

Draft/incomplete assurance is visible in UI data. Ayan/Aradhya need exact valid LIMITED, supported-negative and rejected examples alongside a positive synthetic example. Do not hardcode a second attempt to pass, nor require real terrain to follow the graph's narrative. Keep final manifest hashing acyclic: upstream snapshot → audit evidence byte hash → passport manifest → exported file byte hash.

## Tests and final evidence

Own SCI-01/04/06/07/09–18 platform enforcement and combined tests, particularly malicious schema-valid model output, missing gates, stale hashes, invalid evidence IDs/modes, review bypass, critic downgrade, atomic rollback, audit tampering and truthful negative publication. Use actual Ayan science and Aradhya UI/renderer at integration, with mock handlers disabled. Verify same run/inputs/outcomes in DB, API, assurance, browser and exports.

Add these tests within your owned `tests/unit/platform`, `tests/integration/platform` and `tests/contracts/platform` directories; keep the existing test command contract. The command must execute assertions, not merely validate fixture JSON. Provide an application science-check target and assemble [the scientific report template](../../team%20coordination/templates/scientific-validation-report.template.json) for the exact integration SHA.

Final handoff includes implemented gate IDs, failed/downgraded-claim examples, policy/schema/port hashes, reproduced manifest/audit links, actual test receipts and external blockers. Record S0–S4 actually demonstrated and S5 unavailable. Advance main only after applicable combined gates pass. No claim that the architecture itself validates NASA data or rover performance.

## Concrete mapping to this branch (one-shot build)

* Implementation: `application/assurance.py`, `application/passports.py`, `domain/policy.py`, `application/registrar.py` per `08` §6 and §10. Persistence: passports table requires `assurance_evidence_id` (composite FK, same workspace/run/mode) and the id appears in `evidence_ids` and the canonical manifest.
* SCI tests you own (platform parts, named tests in `05` §2): SCI-01 (invalid evidence excluded, fabricated lineage rejected), SCI-04 (masking/denominator tamper), SCI-06 (nominal vs robust wording), SCI-07 (wrong gravity rejected), SCI-09 (solver false totals ⇒ verifier outcome wins), SCI-10 (graph FAIL→PASS through the app), SCI-11 (review/model PASS despite absent evidence denied), SCI-12 (stale/changed hashes/lost lease/cross-workspace/mode), SCI-13 (mode/level laundering), SCI-14 (bounded novelty wording), SCI-15 (hidden unknown/GAP/FAIL rejected), SCI-16 (honest FAIL/LIMITED/GAP publish; PROVE IT blocked without rover), SCI-17 (reproducibility of a result from frozen hashes), SCI-18 (manifest/audit tampering). List them in `STATUS.json.sci_tests` with test ids.
* The assurance policy hash is the canonical hash of Ayan's parsed `config/algorithms.yaml` `observable_policies` plus the gate registry; changing either changes the audit identity.
