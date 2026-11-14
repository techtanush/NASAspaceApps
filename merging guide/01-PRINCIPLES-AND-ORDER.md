# 01 — Principles, authority, setup and order

## 1. Mission and success definition

Deliver `integration/rc`: three branches fused so that the product behaves exactly as architecture 34–40 specify, proven by executed tests and real browser clicks — with only the NASA dataset (and live-model credentials) absent. Success is **observed**, never inferred from "merge succeeded" or "the builders said so".

## 2. Authority and judgment

* You may edit any file, but every edit is classified by **owner** (platform/science/UI/shared) and logged. Prefer fixing a defect in the owner's own area following their guide's intent.
* The frozen kit is read-only by default. A kit change is allowed only if a real, reproducible defect makes the three branches unable to interoperate, and then only via: change request → `tools/build_kit.py` → kit tests → update all consumers → re-run everything. Record it prominently.
* Use your own reasoning: if a guide's instruction would produce a worse outcome than the architecture requires, follow the architecture (`34` precedence) and record the decision. Never trade away honesty gates.

## 3. Environment (merging agent needs everything)

Python 3.12 + uv; **PostgreSQL 16 + PostGIS** (mandatory; use the ladder of architecture 38 §4.1); Node 22 + pnpm 10; headless Chromium + Playwright; GDAL drivers `GTiff, HGT, PDS, PDS4, netCDF, AAIGrid` (preflight lists them). Profile `integration` (ports 8000/5173/5432, project `af-integration`). Record every version in the merge report. If the database or browser cannot be obtained after trying every option, the affected gates are **not passed**; report them as `BLOCKED_ENVIRONMENT` and say the merge is incomplete.

## 4. Setup commands

```bash
git clone <repo> af && cd af && git fetch --all --prune
git checkout merging-branch
for b in tanush/platform-agents-integration ayan/science-data-verification aradhya/frontend-experience; do git rev-parse origin/$b; done   # record SHAs
mkdir -p "team handoffs/merging" out
git worktree add ../af-verify-tanush origin/tanush/platform-agents-integration   # clean checkouts for purity checks
git worktree add ../af-verify-ayan   origin/ayan/science-data-verification
git worktree add ../af-verify-aradhya origin/aradhya/frontend-experience
```

Purity checks run in those throwaway worktrees; merging happens on `integration/rc`.

## 5. Fixed merge order and why

1. **Tanush** — the application skeleton: settings, DB, API, worker, CLI, Makefile, Compose, `uv.lock`, tests/support doubles. Every other piece plugs into it.
2. **Ayan** — adds `science/**`, science adapters, `config/{datasets,algorithms,candidates}.yaml`; plugs in through one entry point. Mostly additive paths; the only shared file is `pyproject.toml` (kit + `extra-ayan`).
3. **Aradhya** — adds `apps/web/**`, `rendering/passport/**`, `package.json`/`pnpm-*`, `tests/e2e`; plugs in through the OpenAPI/UI-testid/renderer seams; shared files: `pyproject.toml` (`extra-aradhya`).

Each merge: `git merge --no-ff <tested-purity-checked-sha> -m "Merge <branch> (purity-checked <sha7>)"`.

## 6. Repair protocol for a branch that is not pure

1. Reproduce the defect in the branch's verify worktree; write a failing test that captures it **in the owner's test directory**.
2. Create `repair/<person>-<n>` from the branch tip; fix the root cause in the owner's code; run that branch's whole gate; commit with `Repair(<person>): <defect> [<catalog id>]`.
3. Merge the repair branch into `integration/rc` right after that person's branch (or before their merge, as a pre-merge step) — never edit the person's pushed branch.
4. Append to the **Repair Log** (`team handoffs/merging/REPAIR-LOG.md`): defect, evidence, root cause, owner, fix, commit, tests added, re-verification result.
5. Severity: **S1 blocking** (contract violation, hardcoded outcome, security/secret, silent fallback, missing entry point, unsafe import) — must be fixed before merging; **S2 must-fix** (failing/skipped required test, missing required file/behavior, spec deviation affecting an acceptance row); **S3 note** (style, optional polish) — log only.
6. If the same root cause appears in more than one place, fix all instances and add a regression test.

## 7. What never to do

Force-push; reset shared branches; delete another person's tests; change expected values without independent derivation; use `--strategy ours/theirs` wholesale; run destructive commands against a profile you did not start; commit `.env`, `data/`, caches, `node_modules`, build output; declare done with unexecuted gates.

## 8. Stop conditions

Stop and report (do not paper over) only if: a builder branch is absent/unpushed; the kit itself is internally inconsistent in a way you cannot repair under §2; or a mandatory environment (database/browser) is impossible to obtain. In every other case keep repairing and re-verifying.
