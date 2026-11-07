# 07 — Release candidate, report and the finish line

## 1. Definition of done (all must be true and evidenced)

1. All three branches proven **pure** (`purity-<person>.json`), with the Repair Log complete (or "no repairs needed" with evidence of the checks run).
2. `integration/rc` contains the three merges (and any repair branches), the kit verifies (`materialize --verify` PASS), and the lock is consistent.
3. Wiring W-01…W-15 PASS; `wire_check.py --stage final` PASS.
4. MRG-01…MRG-11 `PASSED` (or an explicitly justified `BLOCKED_ENVIRONMENT`/`BLOCKED_EXTERNAL` that is listed first in the summary and is not something you could have obtained).
5. Journeys J01–J13 pass in real mode with mocks off, run twice; recovery tests pass; clean-checkout rebuild passes.
6. Practice matrix P1–P10, perturbations, mock NASA drop, live-path rehearsal done; NASA-READY checklist N-1…N-10 all evidenced.
7. Requirements ledger: all 58 `PR-*` rows with module/test/observed result; none left `NOT_IMPLEMENTED` without a recorded exception.
8. Scientific validation report filled for the exact merged SHA, no unexecuted gate marked passed.
9. `integration/rc` pushed; tag `rc-<yyyymmdd>-<sha7>` created and pushed; `MERGE-REPORT.json` committed on `merging-branch`.
10. **`main` is NOT advanced** (a human fast-forwards it after reading the report).

## 2. Artifacts you must produce (all under `team handoffs/merging/` on `merging-branch`)

| File | Content |
| --- | --- |
| `MERGE-REPORT.json` | from `templates/merge-report.json`, every field filled |
| `REPAIR-LOG.md` | each defect: id, severity, owner, evidence, root cause, fix commit, regression test, re-verification |
| `purity-tanush.json`, `purity-ayan.json`, `purity-aradhya.json`, `purity-merged.json` | from `templates/purity-report.json` |
| `requirements-ledger.csv` | 58 rows filled |
| `scientific-validation-report.json` | exact SHA, locks, SCI-01…18, S-levels reached |
| `DECISIONS.md` | your judgment calls and any contradictions resolved |
| `out/` summaries referenced by path (suites, playwright report, preflight, screenshots) — commit only small text/JSON summaries, not binaries over 1 MiB |

## 3. Git steps at the end

```bash
git checkout integration/rc && git status --short           # clean
git tag -a "rc-$(date +%Y%m%d)-$(git rev-parse --short HEAD)" -m "AnalogForge release candidate (merge report on merging-branch)"
git push -u origin integration/rc --follow-tags              # retry up to 4x on network errors only; never --force
git checkout merging-branch
git add "team handoffs/merging"                              # report, logs, ledgers (no secrets/data/binaries)
git commit -m "Merge report for integration/rc <sha7>" -m "Co-Authored-By: <your attribution lines>"
git push -u origin merging-branch
```

## 4. Final printed summary (exact order)

1. **Unmet gates / blockers** (or "none").
2. Repair Log summary (count by severity; one line each for S1).
3. NASA-READY checklist N-1…N-10 with PASS/FAIL.
4. Journey results J01–J13 (real mode) and suite counts (passed/failed/skipped per suite).
5. `integration/rc` SHA and tag; branch SHAs merged; kit version.
6. What a human must still provide: **(a)** `OPENAI_API_KEY` + `OPENAI_MODEL` in `analogforge/.env`; **(b)** the NASA dataset files + manifests (runbook 37).
7. Anything that looked wrong or confusing in the hands-on click-through even though tests passed.

## 5. What "complete" never means

Not "the merge succeeded", not "the builders' tests pass", not "the UI renders". It means the product, merged, behaves as architecture 34–40 specify under executed tests and real clicks — and states honestly what is not yet verified (real NASA data, live OpenAI, physical performance).
