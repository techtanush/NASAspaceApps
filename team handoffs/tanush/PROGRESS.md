# Tanush build progress

Base: `825d204b3e8cee8ade01db40ca8fb4020d0ec943`. This is a chronological record; earlier pending/failure notes are superseded by the final checkpoint below.

- Frozen kit materialized; 20 unchanged kit tests pass. Ownership check passes.
- Python3.12 dependencies locked; private PostgreSQL17/PostGIS3.7 fallback works. Final databases use UTF8.
- All43 HTTP operations execute against real ASGI, PostgreSQL and workers; consumer tests detect the export schema conflict explicitly.
- OIDC sign-in, PKCE, signed tokens, roles, cookies, CSRF, workspace isolation, artifacts and SSE tests pass.
- Six scientific-double API journeys have passed across focused runs. The first combined candidate had217passes/5failures while code changed; those failures are being repaired and require a fresh final run.
- Audit found and builders fixed nested policy references, worker timeout/cancellation recovery, lock ordering, atomic successor enqueue and unsafe provenance URLs.
- Actual API and separate worker processes started. Measured health p95<2ms and capabilities p95<7ms across30 warmed local requests. Raw measurements: analogforge/out/process-latency.json.
- Production preflight reports missing Ayan configuration/science and Aradhya renderer by name, as required; test doubles never conceal missing production components.
- Central merge-owner chat evaluates CR001 for the incompatible frozen JSON-export schema. No feature-branch kit edit is permitted.
- Remaining: durable preparation role records, final policy hash checks, all20 mutation kills, final independent audit, fresh whole-suite checks, status and commit/push.

Chats: CLI/ops `01a1b470-3d69-7840-8870-1ef5f627ad7c`; audit `01a1b47b-0a38-7633-85c3-3b3d907c98c9`; central contract `01a1b487-b6d4-7082-8b12-b9a2bd62cbad`.

## Final verification checkpoint

Production checkpoint: `737102a17fdb0ed15c7f7350aa88dc231d2824ec`. Final test checkpoint: `a5fc6c51de4a1c98f6cd4acaed7747131f65d070` (two bounded novelty tests; production unchanged).

- Final audit P1/P2 repairs passed focused rechecks, including actual local HTTP model-provider choices changing the persisted repair/candidate/strategy.
- Actual API SIGKILL/restart and worker SIGKILL during CPU science both recover; two process tests passed in12.84s.
- All20 deliberate source mutants are killed, including the actual wall-clock renderer handoff mutation.
- Fresh frozen run254/254 passed before the final audit additions. An overlapping Make run loaded a temporary invalid test enum while builders edited it (262 passed,1 failed); a fresh all-files-frozen gate supersedes it.
- Central C3 checkpoint `4c9897c96dc082b82b654988ff6898f85b90e504` is accepted and undergoing final tests in an isolated integration preview. Tanush's original C2 kit stays byte-identical.
- Native empty-database/empty-data bootstrap, migrations and seed passed. Container image static checks passed; an actual Docker build is blocked by the unavailable daemon.
- Source is committed locally; no push has occurred. Final full gates and reports are pending.

- Final frozen Make run exposed a cancellation timing assertion (3.8s total). The guide has separate2s command acknowledgement and5s child termination bounds. The test is being split to measure both after the child actually starts, and cleanup escalation is tightened from a possible6s to bounded1s+1s. No scientific outcome or model budget changes.

## Final completed implementation and validation

- Final frozen production/test checkpoint: `eb4cd4c63e4477a050370c8084c89c596e9ea1af`.
- Fresh final whole suite:278 passed in445.10s, zero failures/errors/skips. Separate kit20 passed. All six API journey variants execute together successfully. This supersedes earlier partial, transient and interrupted candidates.
- Docs, Ruff and strict mypy123 files pass. Locked86-package environment, frozen kit verification,20/20 assertion-killed mutants and zero-finding scans pass.
- Final security probe exposed an actual subprocess stderr leak for unexpected errors. The safe type-only transport fix and three real spawned regressions close it;22 focused CPU/worker/lease checks pass.
- Central C3 preceding full275 pass plus final22 affected tests,3 strict43-operation/81-response transport tests,20 kit tests, and root final full-source equivalence close CR001. Exact SHAs and raw proofs are in `validation/c3-preview.json`.
- Aggregate `make check` exits2 at the required truthful production preflight: missing Ayan configurations/science and Aradhya renderer. No test double is injected into production preflight. The remaining checks were executed separately.
- Full SCI01–18 remains NOT_RUN; S1–S4 NOT_RUN, S5 NOT_IMPLEMENTED. Only the declared S0 platform software scope is ready; no real-source, numerical, physical, renderer/browser or external-live validation is claimed.
- Publication follows final handoff/ownership/source-equivalence checks. No source change is planned; delivery receipts are recorded separately after the push succeeds.

## Verified publication

Atomic push succeeded: Tanush feature checkpoint `2ca4d15d0abfdedf9ce5b6f2d1d353eeb5deada0` and central C3/evidence checkpoint `635df8de41b838b69369e21a6c814ce1889178cf`. Remote refs were verified. This delivery-receipt-only follow-up preserves final tested source `eb4cd4c63e4477a050370c8084c89c596e9ea1af`; no main or teammate branch was modified.
