# Integration and merge playbook (summary)

The full, step-by-step procedure with exact commands, purity checks, wiring steps, debug playbook and browser tests lives in the **`merging guide/`** directory on branch `merging-branch`. This page is the summary every builder should know so their branch merges cleanly.

## Order and shape

1. The three builders finish independently (no mid-build hand-offs) and push `STATUS.json` with `ready_to_merge: true`.
2. The merging agent creates `integration/rc` from `main` and verifies **each branch alone** (purity: [39](../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) §2). A branch that is not pure is repaired on that branch's code until it is — never papered over in the merge.
3. Merge order: **Tanush → Ayan → Aradhya**, each with `git merge --no-ff`. Rationale: Tanush's branch is the app skeleton (settings, DB, API, CLI, Makefile, Compose, lock); Ayan's science plugs into it through one entry point; Aradhya's frontend/renderer plug in through the OpenAPI/UI/renderer seams. Kit files are identical on all three, so they never conflict; `pyproject.toml` conflicts are resolved by uniting the three `extra-*` lists.
4. After each merge: kit verify, import hygiene, the merged slice of the catalog, then the next merge.
5. Wiring: replace every test double used by a branch with the real entry points; regenerate the client; run seam tests; run parity.
6. Combined suites and **browser journeys J1–J13 with mocks off**; clean-checkout rebuild; recovery tests; secret/ownership scan; traceability ledger; scientific report.
7. Result: `integration/rc` (tagged, pushed) and a merge report committed under `team handoffs/merging/`.

## What builders do to make that work

* Materialize the kit; never edit it. Use only your owned paths.
* Implement your branch's **entry points** with the exact dotted paths and signatures.
* Write your own tests against typed **test doubles that live only under `tests/`** and are replaced at integration.
* Keep your `STATUS.json` honest: real commands, real counts, real blockers, every contradiction you found.
* Do not fix a defect you find in another owner's area — record it in `STATUS.json.defects_in_other_areas` with a reproduction.

## Conflict policy (also in the merging guide)

| Conflict | Resolution owner |
| --- | --- |
| Shared contract/kit drift | Restore the kit (`materialize.py --repair`); if a branch needs a real change, the change process in 01 §4 |
| `pyproject.toml` | Union of the three extra lists; everything else must equal the kit |
| `config/*.yaml` | Each file has one owner; take the owner's version, then run the cross-key preflight |
| Generated client | Regenerate; never merge by hand |
| `analogforge/README.md`, `Makefile`, `compose.yaml` | Tanush's version, then add the frontend targets from Aradhya's `package.json` scripts |
| Anything else | Classify (platform / science / UI), keep the owner's version, rerun that owner's tests |

Never `reset --hard`, force-push, delete another person's work, or choose a whole side blindly. No deployment or external publication happens automatically.

## Scientific acceptance before the release candidate

Run the shared gate [06](06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md) on the exact merged SHA and record observed results in `templates/scientific-validation-report.template.json` (copied to `team handoffs/merging/`). Unrun source/live gates are `BLOCKED_EXTERNAL`, never passed.
