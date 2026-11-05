# Tanush — tests and merge gates

A gate passes only when its tests **execute and assert**. Skips, xfails, deselects and "no tests collected" are failures. Catalog ids: architecture 39 §1.

## 1. Commands (from `analogforge/`; omit `rtk` if not installed)

```bash
python3 "../architecture files/contracts/kit/materialize.py" --verify                              # KIT-01
uv run pytest tests/contracts/kit -q                                                               # KIT-02
uv run pytest tests/unit/platform tests/integration/platform tests/contracts/platform -q --strict-markers \
    -p no:randomly --junitxml out/platform-junit.xml                                                # PLT-01..PLT-21 (DB tests need TEST_DATABASE_URL)
uv run ruff check src tests/unit/platform tests/integration/platform tests/contracts/platform tests/support
uv run mypy src/analogforge --exclude 'src/analogforge/(ports|science|rendering/passport|adapters/(earthdata|pds|emit|diviner|user_survey|source_http))'
uv run python -m analogforge.cli preflight --mode synthetic --scenario synthetic-mars-mobility-v1 --output out/preflight-synthetic.json --json
uv run python -m analogforge.cli export-openapi --out out/openapi.exported.json
python3 "../team coordination/scripts/check_branch_ownership.py" --person tanush --repo ..        # PASS
make check PROFILE=tanush                                                                           # wraps the above; must exit 0
```

`DB` tests are marked `@pytest.mark.db`; with a database they **must run**. The only acceptable non-run is `BLOCKED_ENVIRONMENT` after trying every option of architecture 38 §4.1, recorded in `STATUS.json` with commands and errors. A junit parser step (`scripts/validate_docs.sh`) fails the gate if any PLT test is `skipped` while `TEST_DATABASE_URL` is set.

## 2. Required test files (names are part of the gate)

| File (under `tests/…/platform/`) | Catalog | Must assert |
| --- | --- | --- |
| `integration/test_migrations.py` | PLT-01 | empty DB → head; seeded previous schema → head; constraints/indexes exist; no auto-drop |
| `contracts/test_openapi_conformance.py` | PLT-02 | 43 operationIds/paths/methods equal the bundled spec; **every** endpoint exercised with seeded data and every response (2xx and the documented 4xx) validated with jsonschema against the bundled operation's response schema; every kit request fixture validates against the request schema |
| `integration/test_idempotency_revisions.py` | PLT-03 | same key+body ⇒ same response; changed body ⇒ 409 `IDEMPOTENCY_CONFLICT`; stale `expected_revision` ⇒ 409 `REVISION_CONFLICT` on every mutating endpoint (parametrized over all of them) |
| `integration/test_workspace_isolation.py` | PLT-04 | cross-workspace id enumeration ⇒ 404 on every read; lists never leak; artifact access needs owning evidence/export |
| `integration/test_jobs_leases.py` | PLT-05, PLT-06 | one lease owner; expired owner's publication fenced; crash after blob move before commit recovers; cancellation during CPU subprocess ⇒ `CANCELLED`, evidence kept, no later PASS |
| `integration/test_sse.py` | PLT-07 | replay after cursor, `Last-Event-ID` precedence, 410 `EVENT_CURSOR_EXPIRED`, heartbeat comments don't advance cursor, terminal event |
| `unit/test_registrar.py` | PLT-08 | every rejection rule of architecture 35 §3.3 (hash/size mismatch, scratch escape/symlink, dangling `local_key`, foreign-workspace/mode parent, `SYNTHETIC_` naming per mode, signed-URL `source_uri`, `input_sha256` mismatch, request/operation/mode mismatch) and a fully valid result registers atomically |
| `unit/test_policy.py` | PLT-09 | fabricated/foreign evidence, changed threshold/limit, stale revision, unlisted tool, status/confidence inflation, repair outside `permitted_repairs`, prompt-injection text is data |
| `integration/test_council_scripted.py` | PLT-10 | all ten roles via the scripted provider with strict schemas; seeded scale-defect loop ⇒ BLOCKING issue OPEN→RESOLVED, matrix revision 2 supersedes 1 |
| `unit/test_budgets.py` | PLT-11 | every budget of `catalog.BUDGETS`, persisted across a simulated restart; preparation cap 4; replans 2+1; fourth attempt impossible |
| `integration/test_assurance.py` | PLT-12 | SC-01…15 per claim, missing gate ⇒ `NOT_ASSESSED` ⇒ dependent positive claim `REJECTED`; BLOCKED/LIMITED/ALLOWED rules; atomic rollback; stale audit rejected; tampered artifact detected; SCI-01/04/06/07/09–18 platform parts |
| `integration/test_passport_assembly.py` | PLT-13 | acyclic hashing; manifest re-canonicalized independently equals `manifest_sha256`; bundle invariants of `PassportExportBundle` |
| `integration/test_exports.py` | PLT-14 | 202+`Retry-After` then 200; all headers; byte-stable re-download; per-workspace authorization |
| `unit/test_entry_points.py` | PLT-15 | missing/non-conforming facade/renderer ⇒ named failure, no fallback; `analogforge.main` imports without science/renderer packages |
| `integration/test_live_gates.py` | PLT-16, PLT-18 | `live` without key/model ⇒ 503 `PROVIDER_AUTH_FAILED` with `details.dependency`, no run created, no scripted fallback; `live` rejects the mock graph provider; synthetic/replay open no sockets (socket monkeypatch) |
| `integration/test_dataset_cli.py` | PLT-17 | scaffold/validate/lock/bind/generate commands (through doubles); tamper after lock ⇒ `SOURCE_CHECKSUM_MISMATCH` block; synthetic dataset into `live-hackathon-v1` ⇒ `MODE_MISMATCH`; `live-hackathon-v1` unbound ⇒ `allowed_modes: []` |
| `unit/test_secrets.py` | PLT-19 | scan of logs, SSE payloads, exports, errors, OpenAPI and `git ls-files` for key/token/DSN patterns |
| `integration/test_seed_and_capabilities.py` | PLT-20 | `seed-synthetic` idempotent/offline; capabilities list per architecture 40 §10; presets byte-identical to kit fixtures |
| `integration/test_live_rehearsal.py` | PLT-21 | with test hooks: live role loop against `fake_openai_server` incl. refusal/malformed/timeout; harness provider rejected without hooks |
| `integration/test_journey_api.py` | (J1 API-level) | create→fingerprint→accept→run→select A→PROVE IT→3 attempts (1 FAIL ROUTE, 2 FAIL ANALOG, 3 PASS on B)→passport LIMITED→3 exports; hashes unchanged across attempts; replans 1+1; uses `fake_science`; asserts persisted receipts/evidence for every step |
| `integration/test_recovery.py` | — | kill API mid-run ⇒ snapshot+events recover; kill worker mid-search ⇒ replacement completes without duplicates |
| `integration/test_rls.py` | PLT-04 | RLS enabled in hosted mode under a non-superuser role blocks cross-workspace SQL |

## 3. Frozen thresholds

Lease 120 s / heartbeat 20 s / reaper 30 s; event visible ≤ 2 s locally; cancellation acknowledged ≤ 2 s and CPU child terminated ≤ 5 s; health < 100 ms; ordinary reads p95 < 500 ms (measured and recorded, not claimed); `MAX_RUN_MODEL_CALLS=40`, `MAX_RUN_SECONDS=900`, replans 3, preparation 4.

## 4. Merge readiness

`STATUS.json.ready_to_merge = true` only if: every PLT row `PASSED` (or DB rows `BLOCKED_ENVIRONMENT` with the proof required above and the merging agent notified in `external_blockers`); kit verify and ownership `PASS`; ruff/mypy clean; forbidden-pattern and mutation checks (`09`) clean; the self-audit complete; no hidden skip. Live-OpenAI against the real service is **not run** and is listed `BLOCKED_EXTERNAL`; the fake-server rehearsal (PLT-21) must `PASS`.
