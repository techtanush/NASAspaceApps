# Common builder protocol (all three branch agents)

Every branch prompt tells you to read this file first. It defines how a coding agent (Claude Code or Codex) works **unattended for hours** on one branch and finishes with a result that merges cleanly. Your person-specific files then say *what* to build; this file says *how to behave*.

## 1. Mindset

* You have **one prompt and no human to ask**. Make the conservative choice that is consistent with the architecture, record the decision in `team handoffs/<person>/DECISIONS.md`, and continue. Ask nothing; stop only at the definition of done or at a genuine external impossibility (then finish everything independent of it).
* You are one of three builders. The others cannot see your work until the merge. The frozen **contract kit** and the **entry points** are the only things you share. Anything not in the kit is yours alone to design — but your design must respect the ownership map and the behaviors specified in `architecture files/`.
* "Done" means *every gate in your `05-TEST-AND-MERGE-GATES.md` passed with executed assertions, the self-audit in `09-…` passed, `STATUS.json` is truthful, and the work is pushed*. It does not mean "the code exists" or "my tests pass". Your tests are not the only judge: the merging agent will run tests you did not write, with the real other branches, in a real browser.

## 2. Session start (do these in order; each is cheap)

1. `pwd`; `git rev-parse --show-toplevel`; `git branch --show-current` must equal your branch (see your README). If not, `git checkout <your-branch>` (never create a different branch). `git status` must be clean or contain only your own work.
2. `git fetch origin` (do not merge other branches).
3. Read, in order: this file; your `README.md`; `architecture files/34`, `35`, `36`, `39`, `40`; your guides `01`–`09`; then the architecture documents named in your `03-ARCHITECTURE-READING-MAP.md`. Reading 00–33 selectively is expected; reading 34–40 and your guides completely is mandatory.
4. **Materialize the frozen kit:** `python3 "architecture files/contracts/kit/materialize.py"` then `… --verify` (must print `"status": "PASS"`).
5. Bootstrap the environment per `architecture files/38` §4 for the services *you* need (try every option in order before declaring anything blocked). Record versions in `STATUS.json.environment`.
6. Create `team handoffs/<person>/PROGRESS.md` (resume notes) and copy `STATUS-TEMPLATE.json` to `team handoffs/<person>/STATUS.json`.
7. Run `uv run pytest tests/contracts/kit -q` (Python branches) — it must pass before you write any feature code.

## 3. Using subagents (encouraged)

You may spawn as many subagents as help, under these rules:

* **Single writer per file.** Give each worker a disjoint set of files/modules from your `08-MODULE-SPECIFICATION.md`. Never let two workers edit the same file concurrently.
* **Brief every worker completely:** the guide paths, the kit rules (read-only), the ownership boundary, the exact module contract, the tests it must write first from the catalog rows, and "do not modify files outside your assignment".
* **Separate builders from breakers.** In phase 5 spawn at least one *adversarial reviewer* per major area whose only task is to break the work: find hardcoded outcomes, unreachable branches, weak assertions, missing failure-path tests, spec deviations. Fix what they find.
* **Trust nothing a subagent claims.** Re-run the tests yourself and inspect diffs. You are accountable for every file on the branch.
* Subagents never push, never touch git history, never edit the kit, `STATUS.json` or another person's paths.

## 4. Working loop for every module

1. Re-read the spec for that module (`08-…`, plus the architecture section it cites).
2. Write the tests from the catalog rows first (they define done); include at least one **failure-path** test and one **perturbation** test per behavior.
3. Implement until they pass. Run the **whole** owned suite, lint (`ruff`), types (`mypy` strict on your package), not just the new test.
4. Mutation check: deliberately break the behavior (flip a comparison, hardcode an output) and confirm a test fails. Revert.
5. Commit with a message naming the module and the catalog ids covered. Commit early and often on your branch.

## 5. Git protocol

* Only your branch. Only your owned paths plus exact kit copies. `git add` specific paths (never `git add -A` blindly; never add `.env`, `data/`, `node_modules`, caches, `uv.lock` unless you are Tanush).
* Push at every phase gate: `git push -u origin <your-branch>`. Retry up to four times with 2, 4, 8, 16 s back-off on network errors only. Never `--force`, never `reset --hard` shared history, never rebase pushed commits.
* Before the final push run `python3 "team coordination/scripts/check_branch_ownership.py" --person <you>` — it must print `"status": "PASS"`.

## 6. Forbidden shortcuts (each one fails the merge)

1. Returning fixed PASS/FAIL/numbers for the practice scenarios instead of computing them. (Perturbation tests exist precisely to catch this.)
2. Relaxing a requirement, a rover limit, a reserve, a tolerance or a test to obtain a pass.
3. Turning unknown into `0`, `NaN`, `false` or an empty result that is shown as a value.
4. Treating missing optional data as absence/FAIL or as success.
5. Mixing modes: synthetic data labeled NASA; replay presented as live; live falling back to scripted/synthetic.
6. Computing qualification/energy/slope/exposure in the browser or in the platform's policy layer (science belongs to Ayan's library).
7. A UI control with no real behavior; a mock response in production mode; a hidden mock fallback.
8. Editing kit files, another person's files, or the original architecture documents.
9. Weakening, skipping, deleting, xfailing, deselecting or special-casing a test; changing an expected value to match your output without an independent derivation.
10. Reporting a gate as passed that did not execute. `BLOCKED_ENVIRONMENT` / `BLOCKED_EXTERNAL` are honest outcomes; fabricated `PASSED` is not.
11. `TODO`/`FIXME`/`HACK`/`NotImplementedError`/`pass`-bodied production functions; `except Exception: pass`; swallowed errors that return plausible values.
12. Committing secrets, signed URLs, large data, or generated caches.

## 7. When something blocks you

* **Spec contradiction:** do not pick silently. Record in `STATUS.json.contradictions_found` (files, your choice, reasoning) and continue with the choice most consistent with `architecture files/34`'s precedence rules.
* **Kit prevents progress:** write `team handoffs/<person>/CHANGE-REQUEST-<n>.json`; use a compatible local workaround inside your owned paths; continue.
* **Defect in another owner's area:** write it in `STATUS.json.defects_in_other_areas` with a reproduction; never fix their files.
* **Missing environment (database, browser, GDAL driver, network):** try every option in `architecture files/38` §4; if still impossible, mark the dependent rows `BLOCKED_ENVIRONMENT` with the commands tried and errors, and complete everything else, including offline equivalents.
* **Missing credentials:** build the offline system completely; report live gates as `BLOCKED_EXTERNAL`. Never invent a key, model name, granule or checksum.

## 8. Resuming after context loss

Keep `PROGRESS.md` current after every phase: what is done (with commit SHAs), what is in flight, the next three actions, open contradictions. If your context resets, re-read this file, your README, `PROGRESS.md` and `STATUS.json`, run `git log --oneline -20` and the test suite, and continue from the first unmet gate. Do not restart finished work.

## 9. Final steps (in this order)

1. Run your full gate suite from your `05-…` file; fix failures; rerun until green or honestly blocked.
2. Execute your `09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md` completely (including the adversarial reviewers and mutation checks).
3. `materialize.py --verify`, ownership check, forbidden-pattern scan (`09`), secret scan.
4. Fill `STATUS.json` (every catalog id with status, command, exit code, counts; `ready_to_merge` only if all required rows are `PASSED`). A row marked `BLOCKED_ENVIRONMENT` or `BLOCKED_EXTERNAL` must carry a `"proof"` field (every command tried and its error output, or the exact missing credential); without it the merging agent treats the row as unproven.
5. Commit; push; verify with `git log origin/<branch> -1`.
6. Print a final summary: unmet gates first, then passed gates, the pushed SHA, and the three things the merging agent should check first.
