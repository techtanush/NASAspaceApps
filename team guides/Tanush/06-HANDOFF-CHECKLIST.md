# Tanush handoff checklist

Use a checkpoint directory under `team handoffs/tanush/`. Copy the common handoff template, fill actual values and include a readable report. Null/unrun is valid when explained; invented success/SHAs are not.

- [ ] Correct branch/worktree/profile recorded; no code written into the root integration checkout by accident.
- [ ] F0 contract/ports/dependencies/OpenAPI delivered early with tested commit SHA.
- [ ] Ayan/Aradhya can consume foundation without importing private implementation details.
- [ ] Migrations, idempotency/revision guards, storage/lineage, queue/fencing/cancellation and SSE tests pass.
- [ ] All role task kinds/tools/results are strict, scoped and bounded; no numeric truth comes from prose.
- [ ] Unknown/gap/fail/inconclusive/blocked distinctions are preserved.
- [ ] Exact API/schema/config version and all approved changes are documented.
- [ ] Contributor checkpoints are reviewed and tested on isolated combined candidate commits.
- [ ] Real Ayan facade and Aradhya UI/renderer replace collaborator doubles in integrated tests.
- [ ] Original failed test and unchanged mission/rover hashes survive replan/export.
- [ ] Setup/run/check/build commands work from a clean checkout and each runtime profile is isolated.
- [ ] Secrets/data/caches absent from tracked diff; raw provider reasoning absent from output.
- [ ]58 product requirements have code/test/evidence status in the final ledger.
- [ ] Actual downloaded data/live AI gates are distinguished from synthetic tests and missing external setup.
- [ ] Final accepted main SHA and report match the tested candidate; no forced update or publication.

The handoff should tell each teammate exactly which main checkpoint to merge and which port/client version changed. Do not claim that a clean Git merge means the product works; attach the combined test evidence.

## Scientific credibility handoff

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
