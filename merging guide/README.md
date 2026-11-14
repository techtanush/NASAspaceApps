# Merging guide — fuse three pure branches into one working AnalogForge

**Branch:** `merging-branch` (this branch = `main`'s full specification + this guide). **Agent:** Claude Code or Codex, one prompt, unattended. **Result:** branch `integration/rc` — the three builders' work, each proven pure, wired through the frozen seams, tested in a real browser, with a merge report. Hackathon data is the only thing still missing.

In hackathons the merge is where time dies. This guide removes the guesswork: it says **what to check in each branch before merging**, **how to repair a branch that is not pure**, **exactly how the three Lego pieces connect**, and **which tests, including real browser clicks, prove the result**.

## What you receive

Three pushed branches, each built from one prompt by an agent following `team guides/<Name>/`:

| Branch | Provides | Entry points it must expose |
| --- | --- | --- |
| `tanush/platform-agents-integration` | API, DB, worker, roles, policy, assurance, passport assembly, CLI, Compose/Make, `uv.lock` | `analogforge.main:app`, `analogforge.cli:main` |
| `ayan/science-data-verification` | scientific library, dataset slot, route verifier, generators | `analogforge.science.facade:create_science_service`, `…fixtures.practice:generate_all`, `…fixtures.mock_nasa_drop:generate`, `…datasets.inspect:draft_manifest` |
| `aradhya/frontend-experience` | React workbench, mock backend, journeys, pure renderer | `analogforge.rendering.passport:create_passport_renderer`, `apps/web` build |

The shared **frozen contract kit** (`architecture files/contracts/kit/`) is byte-identical on all three.

## How to run this session

1. Clone the repository, check out `merging-branch`.
2. Paste **only** [MERGING-AGENT-PROMPT.md](MERGING-AGENT-PROMPT.md).
3. Leave it running; it produces `integration/rc`, `team handoffs/merging/MERGE-REPORT.json` and a printed summary.

## Files

| File | Purpose |
| --- | --- |
| [MERGING-AGENT-PROMPT.md](MERGING-AGENT-PROMPT.md) | The single prompt |
| [01-PRINCIPLES-AND-ORDER.md](01-PRINCIPLES-AND-ORDER.md) | Mission, authority, setup, merge order, repair protocol |
| [02-BRANCH-PURITY-CHECKS.md](02-BRANCH-PURITY-CHECKS.md) | What "pure" means and exactly how to verify each branch |
| [03-INTEGRATION-WIRING.md](03-INTEGRATION-WIRING.md) | Merge commands, conflict table, the three seams step by step |
| [04-COMBINED-TEST-PLAN.md](04-COMBINED-TEST-PLAN.md) | Suites, real-browser journeys, recovery, clean-checkout rebuild |
| [05-PRACTICE-RUNS-AND-DATASET-REHEARSAL.md](05-PRACTICE-RUNS-AND-DATASET-REHEARSAL.md) | Practice rovers/scenarios, mock NASA drop, NASA-ready checklist |
| [06-DEBUG-PLAYBOOK.md](06-DEBUG-PLAYBOOK.md) | Symptom → cause → owner → fix |
| [07-RELEASE-CANDIDATE-AND-REPORT.md](07-RELEASE-CANDIDATE-AND-REPORT.md) | Finish line, ledger, report, what to push |
| `scripts/purity_check.py` | Automated structural purity checks per branch |
| `scripts/wire_check.py` | Automated seam/config/entry-point checks on the merged tree |
| `scripts/collect_status.py` | Aggregates the three `STATUS.json` files and the test outputs |
| `templates/merge-report.json`, `templates/purity-report.json` | Reports you fill |

Context you must read first: [architecture 34](../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md), [35](../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md), [36](../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md), [37](../architecture%20files/37-HACKATHON-DAY-RUNBOOK.md), [38](../architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md), [39](../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md), [40](../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md); all three `team guides/<Name>/` directories; `team coordination/`.
