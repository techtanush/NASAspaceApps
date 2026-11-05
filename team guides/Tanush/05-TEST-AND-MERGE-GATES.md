# Tanush testing and merge gates

Implement the tests below and record actual results. Commands describe the future app once scaffolded. Run from your `analogforge/` directory, with the selected isolated profile. Missing targets/tests are unfinished work, not success.

## F0 foundation gate

- Python3.12/native science imports work inside the built worker image, not only on your laptop.
- Fresh Postgres/PostGIS migration succeeds; API/worker readiness and capabilities are accurate.
- Public domain shapes/units/statuses match C1; OpenAPI/client-generation input is stable; port models serialize real fixture requests/results.
- Local mode binds safely; isolated profile ports/volumes/CORS point to the right worktree.
- Synthetic seed is idempotent/offline. Missing external keys do not break offline startup or pretend live is available.

## Domain API and persistence tests

Test mission draft save/reload/conflict, preparation lifecycle, proposed assumptions, explicit contract acceptance, rover import validation, optional rover and immutable input revisions. Verify public retrieval for every pointer in RunSnapshot, including target profile, selected candidates/portfolio, pending review, evidence and test results. New rover/threshold requires a new run.

Test idempotent retry returns same business object; changed body with reused key409; stale expected_revision409; unauthorized workspace404/403 according to policy; HTTP202 queued work versus synchronous errors; proper422 validation; no hidden enum/string drift. An invalid/missing secret yields a safe actionable error without a raw token/DSN.

Test blob atomicity and hash, orphan handling, lineage cycle rejection, local-key resolution, source-policy append-only acquisition, mode mismatch and missing referenced evidence. A label claiming a source exists cannot replace checksum/decoder validation.

## Queue events and policy tests

Two workers cannot own one lease. Expired worker publication is fenced. Crash after blob move/before DB commit resumes without duplicate result. Cancellation during a CPU tool prevents later success publication. Uncommitted output cannot appear as a committed SSE event. Cursor replay/expiry and snapshot after reconnect are consistent. Active-time and model/replan budgets survive process restart.

Supply malicious role output: invented evidence ID, wrong workspace/mode, unsupported tool, untrusted prompt injection, nonfinite numeric quantity, hidden changed contract, stale revision, fabricated pass. Policy must reject it. Schema-valid prose cannot bypass evidence or override Ayan's independent verifier result. A model refusal/incomplete output is a typed failed/blocked invocation with bounded retry.

## Agent gate

Exercise all ten roles with scripted provider fixtures, actual registered tool receipts and explicit task kinds. Requirements preparation is not a fake run. The critic must create one exact material challenge and request evidence repair or leave UNKNOWN. PROVE_IT launches design+verification only after the accepted contract/rover context. Replanning preserves hashes, prior failures and caps. Budget exhaustion ends honestly without a forced PASS.

With authorized configured credentials run a minimal actual provider capability/strict-call probe and one live role/tool journey. Preserve sanitized request/receipt/version evidence. If absent, `live_model_gate=BLOCKED_EXTERNAL`; offline agent tests can still pass.

## Cross-branch gate

Use Ayan's actual facade and Aradhya's actual UI/renderer. The baseline graph must compute120m/26Wh/0m exposure FAIL then340m/34Wh/150m exposure PASS, with fixed contract and actual persisted receipts. These are synthetic test energies, not calibrated live rover predictions. Reject test-only mock resource provider in live mode.

Full browser path: create draft→fingerprint→accept→rover→run→target/candidates→critic/matrix→PROVE_IT→failed attempt→diagnose/replan→verified result→passport/export→reload. Also no-rover, invalid scale, missing optional data, negative candidate, search INCONCLUSIVE, cancellation and reconnect. Disabled MSW and actual database evidence must prove this is integration, not a browser-only fixture.

## Command contract

Provide and run these or documented equivalent exact targets:

```bash
rtk proxy uv run pytest tests/unit/platform tests/integration/platform tests/contracts/platform
rtk proxy uv run ruff check src tests
rtk proxy uv run mypy src/analogforge
rtk proxy make check PROFILE=tanush
rtk proxy make build PROFILE=tanush
```

At integration run the complete Python suite plus Aradhya's frontend checks/browser suite and Ayan's actual data tests. Global mypy/ruff failures in a producer module are coordinated fixes, not grounds to delete that module from checking. Do not keep expanding identical test runs after unchanged successful results; repeat when new changes/failures justify it.

## Merge report

Record exact tested source SHA, accepted main/base SHA, runtime/profile/build lock, schema/port hashes, commands/exit codes/counts, observed live/source probes and blockers. `ready_to_merge` requires no unexplained failing tests, unauthorized files, runtime secrets, fake fixtures or unresolved contract mismatch. Record platform readiness separately from integrated product acceptance. Final main only advances to the tested integration candidate; no deployment follows automatically.

## Mandatory credibility tests

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
