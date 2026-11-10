# Aradhya frontend handoff

Application source `4c801f40ca86751fc16f0557d14bd0d160892a34` on `aradhya/frontend-experience` builds and passes functional verification. Independent visual acceptance remains failed, so `ready_to_merge` is false.

Verified on the final application source:

- 33 browser tests pass, with zero failures, skips or flaky results. This includes J01–J13, reload/reconnect recovery, keyboard use, 200% reflow, declared unknown rover values, scientific display, rapid worker reloads, and WebGL-disabled exports.
- 84 frontend tests in 19 files and 131 Python kit/renderer/contract tests pass.
- TypeScript, ESLint, Ruff and strict mypy pass. Production builds reject mock mode and exclude the mock worker and component guide.
- All 36 required mutations are detected by their intended assertions. Export verification accepts 27 files and rejects 27 tampered files.
- The automated visual report has 407 reports and 409 screenshots with zero findings or skipped checks. Direct text-range assertions now protect matrix value ownership and Run context under expanded spacing.
- Frozen-kit verification, branch ownership and all 150 token checks pass. The supplied contract/design assets remain unchanged.

The branch implements S01–S12, authenticated workspace bootstrap, typed API transport, revision-safe commands, SSE recovery/replay, a persistent synthetic preview, Earth/planetary displays and the pure Python passport renderer. Development exports call that renderer. The preview worker survives document replacement without an unregister/update race. Selecting Known for an absent optional measurement never inserts zero. Saved times come from the API; absent actor/duration information remains Unknown.

Three fresh image reviewers inspected the exact final captures. Their means were HMI 3.333, accessibility 3.167 and slop 3.167, below the required 3.5. Remaining findings concern mobile density, caption/table presentation and other visual details. All six rounds are preserved verbatim in DESIGN-REVIEW.md; no pass is inferred from automated checks.

The component guide has 12 native-resolution images, two contiguous parts per theme/density with 48 px overlap. The largest is 283,202 bytes; together they show the complete guides. Other screenshots and reports remain under analogforge/out and are excluded from Git.

Original-workspace dependencies are restored. The final checks use Node 22.21.1, pnpm 10.22.0, Python 3.12.13 and matching Playwright Chromium. No other owner's implementation or frozen architecture/kit files were changed. Main was not modified.

Real-backend MRG-03 validation remains the merging agent's integration gate. The synthetic preview and fixture exports establish frontend/contract behavior, not live terrain, model access, physical rover validation or production readiness.
