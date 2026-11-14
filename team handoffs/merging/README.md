# AnalogForge release candidate

The local synthetic/generated-data application is ready for review. Real NASA-source and external-model validation still require actual product files with completed provenance manifests, plus `OPENAI_API_KEY` and an explicitly chosen `OPENAI_MODEL` in the ignored server environment. Physical validation is outside this baseline. Preflight also records a low disk-space warning; free space before acquiring large datasets.

Release: tested source `02a67f6720a5d431ba79bf55ad66f5d746d3225a` · tag `rc-20261114-02a67f6` · branch `integration/rc` (previous candidate `5e08b80`, tag `rc-20261112-5e08b80`, preserved).

This candidate contains all three contributor merges and 39 documented integration repairs (21 S1 and 18 S2), including the backend hardening, dependency security upgrade and premium glass interface. The original contributor refs were preserved. Use this candidate: merging those original refs again would omit the integration repairs.

## Verification

| Check | Passed | Failed / skipped |
|---|---:|---:|
| Owned Python tests, real platform/science/renderer integration (366 platform, 1165 science/renderer/UI-contract) | 1531 | 0 / 0 |
| Isolated frozen contract-kit tests | 20 | 0 / 0 |
| Frontend unit tests | 134 | 0 / 0 |
| Frontend contract tests | 3 | 0 / 0 |
| Stream-audit protocol tests | 8 | 0 / 0 |
| Real-backend browser cases (17 per pass, two passes) | 34 | 0 / 0 |
| Preview browser cases, including the full visual audit | 41 | 0 / 0 |

Every J01–J13 journey ran twice on fresh databases and missions, with the two merge-specific checks. Mutation checks all pass: 36 frontend, 6 API/display, 9 renderer, 16 science and 20 platform mutants were killed. Failed, interrupted, superseded and setup-invalid invocations remain documented separately; none is counted as a final pass.

The full visual audit checks 501 records with zero findings and zero skipped checks, including glass-surface contrast. Full details, exact commits, excluded invocations and one open observation are in [out/final-integration.json](out/final-integration.json).

Every gate ran on the combined source; older results are historical.

One reviewer worked in this chat, as requested. Three independent reviewers are not claimed. The design rubric meets the guide's threshold; remaining minor observations are technical compatibility metric names and a dense printed route diagram with its numeric sample table retained.

## Review evidence

Read [the merge report](MERGE-REPORT.json), [all repairs](REPAIR-LOG.md), [scientific validation](scientific-validation-report.json), [the 58-row requirements ledger](requirements-ledger.csv), [design review](DESIGN-REVIEW-MERGED.md) and [decisions](DECISIONS.md). Small evidence summaries are in [out/](out/). The final bundle verifier cross-checks these records and their hashes.

Existing contributor preview logs in this folder are preserved as history. Current release evidence is MERGE-REPORT.json and the named out/ summaries; historical logs do not establish final gates.

The full screenshot/PDF archives remain at the local paths in the visual summaries. Only small summaries and current styleguide assets are committed. Local environment files and raw logs containing connection details are excluded.

## Scientific scope and external inputs

The demonstrated scope is local software integrity and nominal modeled terrain feasibility on generated/replay fixtures, capped at S0/S1. Actual NASA source acquisition/comparison, external OpenAI quality and real-source S2–S4 remain blocked. Physical S5 is not implemented. A local fake Responses server and format-faithful fixtures do not replace these stages.

Energy coefficients are assumed, uncertainty is not calibrated, and native terrain support cannot resolve sub-cell rover obstacles. Unknown/GAP and LIMITED disclosures remain visible. No NASA approval, global novelty or physical rover readiness is claimed.

## Human handoff

`main` was at `36cd52c85b8dd19ab1abd6e23f8a94bb82f6bca0` before this candidate; the user explicitly authorized merging it. History was never force-pushed. The original contributor branches remain available for attribution and comparison.

For local use, check out `integration/rc` and follow architecture 38 for bootstrap and architecture 37 for the real-data runbook. Keep test hooks disabled during the actual live run. Complete each NASA manifest; validate the actual bytes, checksums, units, CRS and support; create a new dataset lock; bind the scenario; and run preflight before investigation. Missing dimensions must remain Unknown/GAP. Passing software checks does not upgrade scientific validation levels.
