# AnalogForge release candidate

The local synthetic/generated-data application is ready for review. Real NASA-source and external-model validation still require actual product files with completed provenance manifests, plus `OPENAI_API_KEY` and an explicitly chosen `OPENAI_MODEL` in the ignored server environment. Physical validation is outside this baseline. Preflight also records a low disk-space warning; free space before acquiring large datasets.

Release: `5e08b801f84625bc930b2be43974766a7f6c08ca` · tag `rc-20261112-5e08b80` · branch `integration/rc`.

This candidate contains all three contributor merges and 32 documented integration repairs (20 S1 and 12 S2). The original contributor refs were preserved. Use this candidate: merging those original refs again would omit the integration repairs.

## Verification

| Check | Passed | Failed / skipped |
|---|---:|---:|
| Owned Python tests, including the real platform/science/renderer integration | 1434 | 0 / 0 |
| Isolated frozen contract-kit tests | 20 | 0 / 0 |
| Frontend unit tests | 134 | 0 / 0 |
| Frontend contract tests | 3 | 0 / 0 |
| Stream-audit protocol tests | 8 | 0 / 0 |
| Real-backend browser cases | 34 | 0 / 0 |
| Preview browser cases, including the full visual audit | 41 | 0 / 0 |

Every J01–J13 journey ran twice on fresh missions. J08 and J09 include additional recovery/zoom cases; two merge-specific checks also ran twice. All 36 frontend mutation cases and nine additional merger mutations were caught, with passing unchanged controls. Failed, interrupted, superseded and setup-invalid invocations remain documented separately; none is counted as a final pass.

The real visual audit checks 501 records. The preview suite retains 120 earlier focused checks plus the identical 501-record full catalog: 621 records in total. All have zero findings and zero skipped checks. Every screenshot manifest entry verifies against its PNG: 504 real and 623 preview entries. The 33-page real passport was inspected, including the full manifest, mode and headline on page one, page numbers and table bounds.

The complete backend matrix executed at `ed903b6`; all backend, configuration, contract, lock and Python-test bytes match the final product. The frontend-only pagination repair has its own complete current-source frontend, browser, mutation and visual gates at `c263d2affedfcb17b9e9adb69765f832019650a7`. The release adds two refreshed styleguide images and a test-only J12 repair afterward. J12 now reopens its own newly accepted mission, rather than an unrelated older mission from the first collection page. It retains all unavailable-slot assertions; focused real and preview counterexamples pass twice, and the full affected 24-case real batch is repeated. See [source equivalence](out/source-equivalence.json) for exact component boundaries and hashes.

One reviewer worked in this chat, as requested. Three independent reviewers are not claimed. The design rubric meets the guide's threshold; remaining minor observations are technical compatibility metric names and a dense printed route diagram with its numeric sample table retained.

## Review evidence

Read [the merge report](MERGE-REPORT.json), [all repairs](REPAIR-LOG.md), [scientific validation](scientific-validation-report.json), [the 58-row requirements ledger](requirements-ledger.csv), [design review](DESIGN-REVIEW-MERGED.md) and [decisions](DECISIONS.md). Small evidence summaries are in [out/](out/). The final bundle verifier cross-checks these records and their hashes.

Existing contributor preview logs in this folder are preserved as history. Current release evidence is MERGE-REPORT.json and the named out/ summaries; historical logs do not establish final gates.

The full screenshot/PDF archives remain at the local paths in the visual summaries. Only small summaries and current styleguide assets are committed. Local environment files and raw logs containing connection details are excluded.

## Scientific scope and external inputs

The demonstrated scope is local software integrity and nominal modeled terrain feasibility on generated/replay fixtures, capped at S0/S1. Actual NASA source acquisition/comparison, external OpenAI quality and real-source S2–S4 remain blocked. Physical S5 is not implemented. A local fake Responses server and format-faithful fixtures do not replace these stages.

Energy coefficients are assumed, uncertainty is not calibrated, and native terrain support cannot resolve sub-cell rover obstacles. Unknown/GAP and LIMITED disclosures remain visible. No NASA approval, global novelty or physical rover readiness is claimed.

## Human handoff

`main` remains unchanged at `36cd52c85b8dd19ab1abd6e23f8a94bb82f6bca0`. Review the candidate and this report before advancing it. If main changes, integrate and retest rather than forcing history. The original contributor branches remain available for attribution and comparison.

For local use, check out `integration/rc` and follow architecture 38 for bootstrap and architecture 37 for the real-data runbook. Keep test hooks disabled during the actual live run. Complete each NASA manifest; validate the actual bytes, checksums, units, CRS and support; create a new dataset lock; bind the scenario; and run preflight before investigation. Missing dimensions must remain Unknown/GAP. Passing software checks does not upgrade scientific validation levels.
