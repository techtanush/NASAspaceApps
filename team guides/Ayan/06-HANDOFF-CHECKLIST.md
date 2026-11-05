# Ayan handoff checklist

Create checkpoint report under `team handoffs/ayan/` using the shared template. The integrator should be able to reproduce your results without understanding every implementation detail.

- [ ] Correct branch/worktree/profile and accepted F0/base SHA recorded.
- [ ] Only owned science/source/display/config/test paths changed; dependency/contract requests are separate.
- [ ] Typed facade and all supported operation examples match accepted port version.
- [ ] Analytic expected values, masks/body/CRS/scale handling and property tests pass.
- [ ] Graph FAIL→repair→PASS arithmetic is computed with unchanged accepted thresholds.
- [ ] Production energy tested separately; mock energy cannot enter live mode.
- [ ] Independent verifier rejects falsified solver totals and unsafe/unknown traversal.
- [ ] Search limits/approximation create INCONCLUSIVE rather than false infeasibility.
- [ ] Scientific evidence/artifacts have complete draft lineage, hashes, quantity kinds and limitations.
- [ ] Earth/Mars/Moon actual source validation listed separately from synthetic/replay tests.
- [ ] Optional-layer/no-coverage/error states and physical unknowns remain honest.
- [ ] Discovery controls, mission sensitivity, bounded novelty scope and portfolios/co-location tested.
- [ ] Display manifests/images/route telemetry can be consumed by the actual platform/UI.
- [ ] No secrets, bulk data, hidden models, SQL/FastAPI dependencies in pure math or unapproved lock edits.
- [ ] Exact tested commit, commands/counts, tolerances, source/algorithm hashes and blockers included.

Deliver S0 as soon as the pure facade/regression works, then S1 for complete scientific source/discovery/portfolio behavior. Do not wait for a perfect final app before exposing your actual integration shapes.

## Scientific credibility handoff

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
