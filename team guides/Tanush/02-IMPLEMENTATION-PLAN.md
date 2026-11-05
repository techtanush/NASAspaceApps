# Tanush — implementation plan (phases with exit gates)

Follow `team coordination/05-PARALLEL-ONE-SHOT-EXECUTION-PLAN.md`. Parallelize inside a phase with subagents (single writer per file). Record each phase's completion (SHA, date) in `PROGRESS.md`.

## T0 Orient and bootstrap
Read everything named in the prompt. Materialize + verify the kit, run `tests/contracts/kit`. Bootstrap per architecture 38 §4: Python 3.12 venv, **PostgreSQL 16 + PostGIS** (try Docker, then native install, record which), Node not required. `uv lock` (you own the lock; resolve the kit's dependency set; commit `uv.lock`). **Exit:** kit PASS; `psql` can `CREATE EXTENSION postgis` (or the exact blocked evidence is recorded); `uv sync` succeeds.

## T1 Foundation
`settings.py` + validators, `main.py` (health/ready/capabilities), `db` base/models/migrations 0001–0007 (can be created incrementally but all exist at the gate), `adapters/storage/cas.py` (write→fsync→hash→atomic rename), idempotency, revision CAS, workspace-scoped unit of work, local identity, error envelope. **Exit:** PLT-01, PLT-03 (partial), PLT-04, PLT-15 skeleton, PLT-16 (no-key startup) pass; `make dev` boots DB+API+worker idle.

## T2 Durable domain
Missions (drafts/autosave/revisions/acceptance), rovers (import validation, revisions), run creation (`validate_run_inputs`, scenario/lock checks), run snapshot/read endpoints for every pointer in `RunSnapshot`, events table + SSE, jobs queue/leases/heartbeat/reaper/fencing/cancel, `PREPARE_FINGERPRINT` with the scripted Requirements role. **Exit:** PLT-02 for authoring/read endpoints, PLT-03 complete, PLT-05, PLT-06 (cancel), PLT-07 pass.

## T3 Registrar, tools, scheduler, scripted roles
`application/registrar.py` (all rejection rules), tool registry/allowlists/receipts, `scheduler.py` state machine (data-driven transitions), policy + confidence rules + budgets, scripted provider with the seeded scale-defect loop, all ten roles' task kinds and payload schemas, `tests/support/fake_science.py` reproducing S-RASTER-1/S-GRAPH-1 through the kit models. **Exit:** PLT-08, PLT-09, PLT-10, PLT-11 pass; journey J1's API-level equivalent (create→accept→run→PROVE_IT→3 attempts→passport) runs against `fake_science` with all assertions of architecture 39 J1 that do not need real science (attempt order/outcomes/categories, replans 1+1, hashes unchanged).

## T4 Assurance, passport, exports
`assurance.py` (SC-01…15 audit, claim compiler, publication), `passports.py` (assembly, acyclic hashing, bundle), `exports.py` + `EXPORT_PASSPORT` job, export endpoint behavior (202→200), `tests/support/fake_renderer.py`, entry-point loader. **Exit:** PLT-12, PLT-13, PLT-14, PLT-15 complete pass; independent re-canonicalization reproduces `manifest_sha256`.

## T5 Live providers, datasets, preflight, CLI
OpenAI provider + probe + `fake_openai_server.py`; live-path rehearsal (PLT-21); dataset CLI (`scaffold/validate/lock/bind/generate-*` calling the science entry points through doubles in tests), scenario binding rules incl. `MODE_MISMATCH`, lock tamper detection; preflight stages; capabilities; Makefile targets; Compose profiles; README. **Exit:** PLT-16, PLT-17, PLT-18, PLT-19, PLT-20, PLT-21 pass.

## T6 Hardening
Recovery (kill API/worker mid-run), cancellation during CPU subprocess, quota/limits, RLS tests under a non-superuser role, OIDC fake-issuer tests, SSE proxy notes, backup/restore-check script, secrets scan, performance targets recorded (not claimed). **Exit:** all PLT rows pass; ruff + mypy strict clean on `src/analogforge` (excluding `ports/`).

## T7 Self-audit
`09` complete: forbidden-pattern scan, mutation checks, adversarial reviewers, perturbation of the fake-science storylines. **Exit:** all green.

## T8 Report and push
`materialize.py --verify`, ownership check, full gate, fill `STATUS.json`, commit (including `uv.lock`), push, print summary.
