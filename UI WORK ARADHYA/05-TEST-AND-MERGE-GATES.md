# Aradhya test and handoff gates

## Fast commands (from analogforge)

Run each separately and record exit/count; all shell commands use rtk. Ensure supported Node on PATH first.

```sh
rtk proxy corepack pnpm install --frozen-lockfile
rtk proxy corepack pnpm --filter @analogforge/web typecheck
rtk proxy corepack pnpm --filter @analogforge/web lint
rtk proxy corepack pnpm --filter @analogforge/web test
rtk proxy corepack pnpm --filter @analogforge/web test:contracts
rtk proxy corepack pnpm --filter @analogforge/web build
rtk proxy uv run --locked python scripts/ui/forbidden_scan.py --json out/ui-forbidden.json
rtk proxy corepack pnpm --filter @analogforge/web verify:tokens
rtk proxy corepack pnpm audit --prod
```

If audit identifies a dependency issue, investigate direct exposure and fix narrowly; preserve pinned reproducibility. Do not upgrade broadly or ignore a real failure. Do not hand-edit a lockfile.

## Meaningful unit/component coverage

| Group | Required cases |
|---|---|
| Coordinates | Angle parsing, 0/360/seam/pole, body radius/display-only bounds, invalid array/finite checks |
| Wizard | Back/edit invalidation, refresh/direct routes, no rover, library return/import failure, duplicate/uncertain mutation, abort/unmount and stale job completion |
| Scenario | Actual body/mode/lock eligibility; no installed live data; explicit operator-selected source mode |
| Tour | Pinned order; zero candidates; mixed statuses; missing rows; long labels; cluster expansion; selection stability on update |
| Claims | No invented margins/measurements; correct units/origins/support; assurance Pending/LIMITED; per-site attempts never borrowed |
| Streams | Old response ignored, workspace/run switch, gap/resync, terminal and blocked-with-candidates states |
| Detail | Wrong-body/mismatched-candidate manifests rejected; known affine control points; no-data transparent; late fetch cannot cross site; optional seam absent/malformed/version mismatch |
| UI/report | No WebGL/context loss, keyboard parity, reduced motion, tiny viewport/long labels, missing report/site, unpublished exports, real print layout |

Mock globe.gl in component tests; test real WebGL separately in browser. Never make all browser tests mock the globe and claim camera rendering is tested.

## Browser commands and environments

From analogforge/apps/web, an isolated mock journey uses matching server/base URL:

```sh
rtk proxy env WEB_PORT=5300 E2E_BASE_URL=http://127.0.0.1:5300 E2E_TARGET=mock E2E_RUN_NAME=ui-split corepack pnpm exec playwright test
```

The checked config defaults to 5176 and uses strictPort; match both WEB_PORT and E2E_BASE_URL. Verify that an existing process on the port is the correct preview before reuse. New Mission Control journeys must cover rover/no-rover, Moon, FAIL and UNKNOWN sites, blocked preparation/run, report, individual clustered-site drill-down, regional data unavailable, keyboard and mobile. Retain all old workbench journeys; update their starting route only where the workspace is intended.

For real backend: use isolated DB/data/config, real science+renderer, seeded synthetic scenario, no model key and no live hooks. Follow `merging guide/04-COMBINED-TEST-PLAN.md` and `05-PRACTICE-RUNS-AND-DATASET-REHEARSAL.md` for server isolation, seeded journeys and the separate dataset rehearsal. Set E2E_TARGET=real and E2E_BASE_URL to that server, then run journeys + integration. A genuine LIVE inspection uses separately validated datasets and operator setup; no hand-seeded fixtures or test hooks there. Do not borrow the original developer's private running DB.

## Merge readiness

Run existing visual-audit CLI with its supported options (read `scripts/ui/visual_audit.mjs`); extend screens without lowering thresholds. Run UI mutation gate: `rtk proxy uv run --locked python scripts/ui/mutation_check.py --json out/ui-mutations.json`. Required final integration also runs `rtk make check`, real browser journeys and platform/science mutation gates against the actual merged source. The old main results do not count for the new feature.

Handoff records: branch/head/base, owned files, commands/counts, labelled mock vs real, screenshot manifest, dependency/license notices, known limitations, delivered schema version and unavailable behavior. Keep bulky transient artifacts under ignored out/; commit compact public status/review evidence only. `git diff --check`, no secrets/data/private env, no weakened scans, no changed frozen contracts, no hidden foreign-file edits. Leave unimplemented items explicitly incomplete rather than fabricating a green status.
