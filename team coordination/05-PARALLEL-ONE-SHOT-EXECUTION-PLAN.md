# Parallel one-shot execution plan

There is no 48-hour hand-off schedule: each agent works unattended from one prompt until its definition of done. This plan fixes the **internal phase gates** every agent follows so that the three results are compatible without live coordination. Phases are ordered; an agent may parallelize *within* a phase using subagents (single writer per file) but must pass the phase gate before the next.

| Phase | Gate (all must hold before continuing) | Tanush | Ayan | Aradhya |
| --- | --- | --- | --- | --- |
| **0 Orient** | Branch/clone verified; guide, 34, 35, 36, 39, 40 read; kit materialized (`--verify` PASS); kit tests pass; environment bootstrapped | environment incl. Postgres/PostGIS | environment incl. GDAL drivers | Node/pnpm/Playwright |
| **1 Core** | Pure deterministic core works with its own analytic/unit tests | settings, domain wrappers, DB models+migrations, idempotency/revision, storage | geometry, raster, features, energy, graph solver, verifier, practice generators | app shell, generated client, API layer, query keys, SSE controller, renderer skeleton |
| **2 Port implementation** | The branch's kit port is **fully** implemented against a double of the other side | registrar, jobs/leases/events, tool registry, scripted+live role runtime | `ScienceService` facade (all 15 ops), dataset validation/scaffold, display layers | pure renderer (html/json/csv), MSW fixtures encoding the storylines |
| **3 Full scope** | Every deliverable-manifest file exists and every product screen/endpoint/operation works | all endpoints, policy, assurance, passport assembly/export, CLI, preflight | discovery, qualification, compatibility, routing, diagnosis, portfolio, live adapters (recorded fixtures) | all screens, maps, journeys J1–J13 in mock mode, a11y |
| **4 Hardening** | Adversarial and failure-path tests pass; performance/limits behave | recovery, cancellation, quotas, secrets, mode guard, fake-OpenAI live rehearsal | perturbations, determinism, cancellation, mock NASA drop | WebGL fallback, 390 px/keyboard/zoom, escaping |
| **5 Self-audit** | `09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md` fully executed; mutation checks fail as expected; forbidden-pattern scan clean | same | same | same |
| **6 Report** | `STATUS.json` complete; `kit --verify` PASS; committed and pushed | | | |

Interface timing is irrelevant because the seams are frozen. If a phase gate cannot pass because an external dependency is unavailable (database, browser, network), the agent records the exact blocker, completes every independent item, and continues to the next phase for everything that does not depend on it.

When behind on effort, preserve in this order: kit conformance → deterministic core → port implementation → practice storylines → UI truthfulness → breadth. Never trade away honesty gates, tests, or the self-audit.
