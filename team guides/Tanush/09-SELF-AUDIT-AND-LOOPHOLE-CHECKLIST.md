# Tanush — self-audit and loophole checklist

Run this entire file before you declare done (phase T7). It proves your tests can fail, nothing is hard-coded, and no shortcut slipped in. Record each result in `STATUS.json.self_audit`.

## 1. Automated scans (you must implement and run both scripts under `scripts/`)

```bash
python3 scripts/forbidden_scan.py --json out/forbidden.json      # exit 0 required
python3 scripts/mutation_check.py --json out/mutations.json      # exit 0 required: every mutant killed
```

**`forbidden_scan.py`** scans `src/analogforge` (excluding `ports/`, `science/`, `rendering/passport/`, science adapters) and your tests; fails on: `NotImplementedError`, `TODO`, `FIXME`, `HACK`, `XXX`; bare-`pass` function bodies; `except Exception: pass`/`except: pass`; `pytest.skip`/`xfail`/`importorskip` of a *required* package in PLT tests; any top-level `import analogforge.science`, `from analogforge.science`, `import analogforge.rendering.passport`, `from analogforge.rendering.passport` (entry points load by string via `importlib`); `os.environ`/`os.getenv` outside `settings.py`; literal practice window ids (`grid-r0c`, `grid-r1c`, `grid-r2c`) or `graph-zone` in `src/` decision code; assignments of `"PASS"` to an outcome/status variable in `scheduler.py`, `policy.py`, `qualification`/`verification` application modules unless derived from a payload field; `ScriptedProvider(` constructed anywhere reachable from a `live`-mode code path; secret-looking literals (`sk-`, `Bearer `, `postgresql://…:…@` with a non-example password) in tracked files; `print(` in `src` (use structured logging).

**`mutation_check.py`** applies each mutation to a temporary copy, runs the named tests, and requires **failure**. A surviving mutant means a missing/weak test — fix the test, not the script.

| # | Mutation | Must be killed by |
| --- | --- | --- |
| M1 | registrar skips re-hashing artifacts | `test_registrar.py` |
| M2 | idempotency ignores the request-body hash | `test_idempotency_revisions.py` |
| M3 | lease-token fencing check removed from publication | `test_jobs_leases.py` |
| M4 | policy accepts evidence from another workspace | `test_policy.py` / `test_workspace_isolation.py` |
| M5 | scheduler allows a fourth attempt | `test_budgets.py` / `test_journey_api.py` |
| M6 | assurance treats `NOT_ASSESSED` as `SATISFIED` | `test_assurance.py` |
| M7 | manifest hash includes its own digest field | `test_passport_assembly.py` |
| M8 | live mode falls back to scripted when the key is missing | `test_live_gates.py` |
| M9 | SSE heartbeat advances the cursor | `test_sse.py` |
| M10 | export renderer receives a wall-clock time | `test_exports.py` (byte stability) |
| M11 | `PROVE_IT` accepted without a rover | `test_journey_api.py` / `test_policy.py` |
| M12 | replan skips the mission/rover hash assertion | `test_budgets.py` / `test_journey_api.py` |
| M13 | synthetic dataset accepted for `live-hackathon-v1` | `test_dataset_cli.py` |
| M14 | DSN written to a log line | `test_secrets.py` |
| M15 | workspace filter removed from a list repository | `test_workspace_isolation.py` |
| M16 | unknown observable mapped to a default policy instead of `UNKNOWN` | `test_policy.py` |
| M17 | OPEN BLOCKING critic issue no longer excludes its claims | `test_assurance.py` / `test_council_scripted.py` |
| M18 | cancellation ignored at publication | `test_jobs_leases.py` |
| M19 | `input_sha256` mismatch accepted | `test_registrar.py` |
| M20 | `passports.assurance_evidence_id` nullable | `test_migrations.py` / `test_assurance.py` |

## 2. Manual perturbation proof

Run the journey API test with `fake_science` storylines altered (e.g. attempt 3 returns FAIL; diagnosis recommends no repair; mission hash changed between attempts). The scheduler/policy must follow the new facts (stop honestly / reject). Paste before/after outcomes in `STATUS.json.self_audit.perturbations`. If the platform still ends in `COMPLETED` with a PASS passport for a failing storyline, something is hard-coded.

## 3. Adversarial reviewers (spawn at least five subagents; each reports findings, you fix)

1. **Policy bypass attacker:** craft schema-valid role submissions with fabricated/foreign evidence, inflated status/confidence, lowered thresholds, unlisted tools, injected instructions in source text; every one must be rejected without committing.
2. **Concurrency/recovery tester:** two workers, lease expiry, killed worker mid-search, double-delivered events, duplicate commands, simultaneous `PROVE_IT`; no duplicate attempts, no lost evidence, no late PASS after cancel.
3. **Contract auditor:** diff your served OpenAPI against the bundled spec (paths, operationIds, enums, error codes, status codes, headers), exercise every operation including error paths; list deviations.
4. **Security reviewer:** workspace enumeration, CSRF/Origin, header injection, path traversal in artifacts/exports, SSRF via dataset/source URLs, secrets in logs/errors/SSE/exports, test hooks reachable in production configuration.
5. **Hardcoding hunter:** read `scheduler.py`, `policy.py`, `application/*`, `agents/runtime/scripted_provider.py`; prove outcomes depend on receipts/payloads, not scenario ids; find any special-casing of `synthetic-mars-mobility-v1`, window ids, or attempt numbers outside the documented seeded defect.

## 4. Final truth checks

* Start the app with no keys: synthetic journey works; `live` is refused with the exact dependency named; nothing silently downgrades.
* Delete `data/` and the DB, run `make bootstrap && make migrate && make seed-synthetic && make check` — identical results.
* `grep -rn "analogforge.science\|analogforge.rendering.passport" src | grep -v "importlib\|entry_point\|ports"` returns nothing.
* `git ls-files | xargs grep -nE "(sk-[A-Za-z0-9]{20,}|BEGIN (RSA|PRIVATE))"` returns nothing.
* The exported `openapi.json` and the kit's `openapi.bundled.json` agree on all 43 operationIds.
* Re-run `materialize.py --verify`; ownership check; then fill `STATUS.json`, commit with `uv.lock`, push.
