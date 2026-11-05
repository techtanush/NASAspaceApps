# Requirements traceability and completion evidence

The product requirements in02 are testable obligations. Implementation is complete only when each obligation maps to code and observed validation. The CSV in `contracts/requirements-traceability.csv` starts that ledger with exact PR IDs; populate implementation paths, test names and result references while building. Do not replace a requirement with a screenshot of its label.

## Coverage map

| Product requirements | Specification authority | Implementation responsibility | Minimum evidence |
| --- | --- | --- | --- |
| PR001–005 workspace and recovery | 06,07,17,23,24 | Scoped repositories, drafts, snapshots, queue, frontend recovery | Isolation, autosave conflict, reload, cancellation tests. |
| PR010–017 mission | 05,07,14,agents02,16 | Mission drafts/preparation, accepted revisions, fingerprint UI | Proposed-default provenance, explicit acceptance, immutable-history tests. |
| PR020–025 rover | 05,07,agents03,16 | Manual/import model, revisions, no-rover flow | Round-trip/invalid units, known baseline, pinned revisions, no-rover verification block. |
| PR030–036 target/discovery | 08,09,10,agents04/05,18,29 | Source adapters, coarse screening/refinement, maps | Real Earth/Mars/Moon adapter report, controls, beyond-reference candidate and scale refusal. |
| PR040–046 qualification | 10,11,15,agents06,16 | Deterministic rule engine, evidence UI | Complete requirement matrix, all five statuses, evidence/reference and proxy rules. |
| PR050–054 critic/review | 14,15,agents07,16,24 | Issue records, review actions, bounded repair | Exact criticized evidence, superseded matrix, retained unknowns, no threshold mutation. |
| PR060–066 verification | 12,agents03/08/09,16,17 | Frozen test design, route solver, independent verifier | Analytic/graph tests, route telemetry, distinct outcomes, retained attempts. |
| PR070–076 diagnosis/composites | 12,13,agents09,19,28 | Diagnosis, bounded replans, set-cover and co-location constraints | Unchanged contract hash, computed repair, stop reason and portfolio tests. |
| PR080–085 operations/passports | 07,14,15,19,23,25 | Durable actions/receipts/SSE, manifest, exports | Replay/reload, no secret/chain-of-thought, export integrity and provenance. |

Ranges above use abbreviated numeric IDs; exact IDs include hyphens, e.g. PR-001. Requirements not present in a numeric gap are not invented. The CSV contains the actual rows extracted from02.

## Nonfunctional gates

Scientific integrity: no unsupported physical claims; source scale attached; dataset/algorithm hashes pinned; model cannot create numeric truth. Reliability: idempotent commands, fenced leases, atomic events, cancellation and recoverable provider failures. Security: workspace isolation, server-only secrets, controlled downloads, escaped outputs and hosted identity. Usability: accessible statuses/review, mobile layout, map-independent tables and resumable deep links. Operational readiness: dependency locks, measured resource budgets, backups/restores and clear live setup blockers.

Each maps to a named test suite in26. A requirement is VERIFIED only when its observed evidence exists. IMPLEMENTED means code exists but validation may be pending. BLOCKED_EXTERNAL identifies exact credentials/product/access missing while independent implementation continues. NOT_IMPLEMENTED cannot be renamed optional unless00 explicitly says optional.

## Do not game completion

An optional-layer adapter's honest no-coverage result can satisfy its software failure-handling requirement, but cannot satisfy a mineral/thermal scientific test. A synthetic PASS demonstrates software behavior, not NASA dataset integration. A live model response demonstrates account/capability access, not scientific validity. A model-generated itinerary is not deterministic route verification. Portfolio coverage does not imply co-located conditions or actual site access permission.

## Handoff ledger

For every final claimed feature include PR IDs, module paths, unit/integration/e2e test names, runtime mode, dataset/model probe evidence where applicable, and remaining limitations. Attach the release verification report and source/build locks. Completion claims must remain consistent with passport language and the actual reports.
