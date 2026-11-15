# Fundamental merge and repairs — 2026-11-14

This is the baseline checkpoint before the additional mission-control, provider,
weather-context and specialist-shortlist work. It is not the final release report.

## Inputs and ownership

The isolated branch `codex/merge-baseline-20261114` starts from `origin/main`
`1721844` and combines these pushed heads through ordinary merge commits:

- Tanush: `05c79b88266268f739999ee567a531aa64bd8ad7`.
- Aradhya: `a1e1944`.
- Ayan: `ba22a4a`, already an ancestor of main.

The unmodified combined source was `78535249fbbceb41ad004860e8efb3f544195c80`.
No contributor worktree, personal file, original live dataset or accepted result
was reset or overwritten.

## Repairs

- Revalidate current workspace membership on each authenticated request. A removed
  membership or downgraded role takes effect immediately. Reject an explicitly
  unauthenticated browser session and clear stale CSRF state.
- Bind portfolio coverage and exports to current per-site verification, run,
  mission, rover, constraints, route and evidence ancestry. Coupled requirements
  require one site and the same verified route. Missing or stale proof cannot
  establish full coverage. Keep explicit failures and unknowns distinct.
- Reuse one isolated science child across candidate qualification requests. Each
  request retains independent receipts, authorization, deadline, cancellation and
  memory limits. Dispose of failed or mismatched children; sending a request must
  not block cancellation on a full pipe or cold process start.
- Make two rehearsal/capability tests specify the configuration they actually
  assert against. `_env_file=None` does not disable environment variables. The
  isolation rejection test had accidentally bound its private test-profile live
  slot; restore only that test slot, leaving browser and genuine NASA profiles
  separate. Runtime isolation guards remain intact.
- Permit only the three existing reviewed globe JPEGs above 1 MiB, pinned by exact
  path, length and SHA-256. Unknown, changed, enlarged or symlinked assets remain
  rejected. No data-directory, build-output or secret exception was introduced.
  Provenance for NASA deliveries remains in `public/globe/data/preparation.v1.json`
  and `catalog.v1.json`; the older Earth fallback retains its source notice.

## Verification receipts

Artifacts are ignored local outputs under the baseline application's `out/` and
`data/out/`. Counts below overlap; do not add focused and complete-suite counts.

- Complete platform pass attempt: **896 passed, two failures** in 898 tests. Both
  failures were the configuration-inheritance test and its side effect described
  above; no runtime assertion failed. After the explicit test-input correction,
  both containing files passed: **15 tests**. Two additional asset-guard tests pass.
- Science, property, replay, renderer and UI contracts: **1,194 passed**.
- Frozen kit: **20 passed**, in its own Python process; materialization unchanged.
- Frontend: **154 unit tests**, plus **3 contract tests**; typecheck, lint and
  production build pass. Existing bundle-size warning remains advisory.
- Complete old real-backend browser gate: **17/17 passed**, 30.7 minutes, original
  readiness limits. `out/e2e-results-baseline-repaired-real.json` records the run.
- Four new real-backend Mission Control journeys: **4/4 passed**, 2.5 minutes;
  receipt `out/e2e-results-baseline-repaired-mc-moon-boundary-real.json`. Tests
  import a rover and bind its exact server revision, wait for analysis using the
  existing 180-second backend boundary, and keep 15-second UI assertions. Moon
  checks prove unsupported Apollo geometry blocks with NO_COVERAGE, then exercise
  the documented workbench practice preset and its natural GAP in the tour.
- Platform mutation gate: **20/20 killed**, no setup failures or survivors.
- Ruff, strict mypy (244 source files), generated-client equality, stream audits,
  frozen wiring and all three forbidden-pattern scans pass.

These checks establish the fundamental merge checkpoint. The integration branch
must still test its final combined source, new browser journeys, genuine NASA
workflow and science/UI mutation gates, and obtain a fresh design review before
publication. Test-harness live-slot journeys are explicitly labelled synthetic
test infrastructure; they do not establish NASA-source validation.
