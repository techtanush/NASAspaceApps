# Aradhya frontend handoff

Implementation checkpoint: `106c91d` on `aradhya/frontend-experience`, based on `36cd52c85b8dd19ab1abd6e23f8a94bb82f6bca0`.

The branch implements S01–S12, the component styleguide, typed API/session transport, revision-safe commands, SSE recovery, a persistent synthetic preview, planetary and Earth display panels, and the pure Python passport renderer. Development exports call the real renderer. The production build rejects mock mode and excludes the worker and styleguide.

Observed checks at this checkpoint:

- 128 Python kit/renderer/contract tests pass.
- 71 frontend unit tests and the dedicated 3-test client/mock contract suite pass.
- TypeScript, ESLint, Ruff and strict mypy pass.
- Production build and production resource audit pass.
- Frozen kit verification and branch ownership pass.
- Tokens pass 150/150; generated CSS and API client regenerate identically.
- Export self-test verifies 27 files and rejects 27 tampered files.
- A fresh clone with no node_modules/dist/out installs with the frozen lockfile. Its Python suite passes 128 tests; remaining clean-clone results are recorded in STATUS when complete.

Independent adversarial reviews found and prompted fixes for canonical JSON validation, dangling evidence references, SVG processing instructions, stale assurance binding, event replay/reload isolation, publication single-flight, scientific mock truth, asynchronous heading focus, field labels and drawer behavior. Five independent truth attacks pass after the fixes. Renderer attacks now raise typed errors for malformed/noncanonical manifests, unresolved evidence, unsafe SVG and stale audit identity; 50 supplied attempts remain visible.

The final serial browser gate, full visual audit, full 36-mutant catalog and three fresh design reviews are in progress. STATUS.json remains the authoritative completion record. All reports are generated beneath analogforge/out and excluded from Git; the six permitted styleguide screenshots are committed.

Real backend journeys belong to the merging agent's MRG-03 gate. This branch has no real backend, dataset credentials or physical rover evidence. Synthetic success is not a claim of scientific validation or production readiness.

See DECISIONS.md for frozen-contract contradictions and audit measurement decisions. No other owner's implementation or frozen architecture/kit source was changed.
