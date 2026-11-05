# Tanush — definition of done (checklist)

Tick only with observed evidence recorded in `STATUS.json`.

- [ ] Correct branch/clone; kit materialized and `--verify` PASS at start and end; `tests/contracts/kit` green; `uv.lock` committed and consistent with `pyproject.toml`.
- [ ] Only owned paths changed; `extra-tanush` is the only `pyproject.toml` edit; ownership checker PASS.
- [ ] PostgreSQL/PostGIS obtained (method recorded) and all `db` tests executed — or `BLOCKED_ENVIRONMENT` with every attempted command/error.
- [ ] All 43 operations implemented; PLT-02 validates real responses against the bundled OpenAPI.
- [ ] Missions/rovers/runs/drafts/idempotency/revisions/workspace isolation/jobs/leases/fencing/cancellation/events/SSE pass their tests.
- [ ] Registrar enforces every rule of architecture 35 §3.3 and rejects crafted bad results atomically.
- [ ] State machine is data-driven; scheduler sequence of `08` §5 implemented; replan limits (2+1, 3 total) persisted; mission/rover hashes asserted unchanged on every replan.
- [ ] Ten roles, 21 tools with allowlists, strict schemas, scripted provider (seeded scale defect loop works), OpenAI provider + probe + fake server rehearsal.
- [ ] Policy rejects fabricated evidence, status/confidence inflation, threshold changes, stale revisions, unlisted tools/repairs; budgets enforced and persisted.
- [ ] Assurance SC-01…15, claim compiler, publication rules, acyclic hashing, `manifest_sha256` independently reproduced; `assurance_evidence_id` enforced by DB + app.
- [ ] Exports: 202→200, headers, byte stability, authorization; renderer loaded only via entry point.
- [ ] Dataset CLI (scaffold/validate/lock/bind/generate-*), lock tamper detection, `MODE_MISMATCH`, scenario availability rules.
- [ ] Preflight (10 stages) truthful offline and for `live` (names exactly what is missing); capabilities correct; no key needed for synthetic.
- [ ] Journey J1 API-level test passes with `fake_science` and asserts persisted receipts.
- [ ] No platform code computes a scientific metric; no science/renderer import at top level; no secrets/signed URLs anywhere; test hooks inert by default.
- [ ] No `NotImplementedError`/`TODO`/`FIXME`/`HACK`; no hard-coded storyline outcomes in `src/`; no weakened/skipped tests; mutation checks demonstrate tests can fail.
- [ ] `STATUS.json` complete and truthful; contradictions and cross-area defects listed; committed (with `uv.lock`); pushed to `origin tanush/platform-agents-integration`.

Push at every phase gate, but the branch is only mergeable at the end.
