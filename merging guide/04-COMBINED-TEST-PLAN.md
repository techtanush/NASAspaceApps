# 04 — Combined test plan (offline suites, real-browser journeys, recovery, rebuild)

Run on the merged `integration/rc` after wiring (`03`). Every row records command, exit code, counts and output path in `MERGE-REPORT.json` (`catalog.MRG-xx`). Outputs go to `out/` (git-ignored). A row passes only if it **executed and asserted**; skipped/xfailed/deselected tests are failures.

## 1. Bring the system up (real mode, profile `integration`)

```bash
cd analogforge
cp .env.example .env          # edit: POSTGRES_PASSWORD (random local), SESSION_SECRET unused in local mode; keep ANALOGFORGE_MODE=synthetic; no keys needed
make bootstrap                 # venv, deps, pnpm install --frozen-lockfile
make dev                       # DB (docker or native per architecture 38), migrations, API :8000, worker, web :5173
make seed-synthetic
curl -fsS localhost:8000/api/v1/health/ready ; curl -fsS localhost:8000/api/v1/capabilities | python3 -m json.tool
analogforge preflight --mode synthetic --scenario synthetic-mars-mobility-v1 --output ../out/preflight.json
```
Confirm: ready, worker healthy, five scenarios listed, `live-hackathon-v1` unavailable, no keys configured. If `make dev` does not start all services, fix the wiring (W-14) before continuing.

## 2. Offline suites (MRG-02)

```bash
AF_SCIENCE_IMPL=real AF_RENDERER_IMPL=real uv run pytest tests/contracts/kit tests/unit/platform tests/integration/platform tests/contracts/platform \
   --junitxml ../out/junit-platform.xml -q
uv run pytest tests/unit/science tests/property/science tests/integration/science tests/replay/science tests/contracts/science --junitxml ../out/junit-science.xml -q
uv run pytest tests/unit/passport_renderer tests/contracts/ui --junitxml ../out/junit-renderer.xml -q
pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run test:contracts && pnpm run build
uv run ruff check src tests ; uv run mypy src/analogforge
python3 "../merging guide/scripts/collect_status.py" --junit ../out/junit-*.xml --json ../out/suites.json     # fails on any skipped/xfail in required suites
```

## 3. Real-backend browser journeys J01…J13 (MRG-03)

The specs are Aradhya's `tests/e2e/journeys/J01…J13*.spec.ts` (exact click scripts: architecture 39 §3), now run against the real stack with mocks off:

```bash
cd analogforge
E2E_TARGET=real E2E_BASE_URL=http://localhost:5173 E2E_API_URL=http://localhost:8000/api/v1 pnpm run test:e2e \
   --reporter=json,html --output ../out/playwright
```

Preconditions found in the 2026-11-12 trial merge (all three branches, real science and renderer, mocks off):
* **J13** needs a scenario whose `allowed_modes` contains `live`; otherwise `live` is correctly not offered and the journey cannot select it. Bind one first, through the MRG-05b TEST_HARNESS rehearsal (§05 4) or real NASA data. Do not edit `config/scenarios.yaml` to fake a binding.
* **J11** creates and locks the practice datasets itself (`datasets generate-practice`, `validate` ×3, `lock --datasets …`); point `ANALOGFORGE_CLI` at the merged venv if it is not `analogforge/.venv/bin/analogforge`.
* A full real run takes about 1–1.5 h on 4 vCPU (workers 1, 900 s per-test budget, 1200 s for J11). Pass `--trace off`.
* Trial result: J01–J13 all passed once the fixes listed in `06` §C were made. Re-run them; do not rely on the trial.

Requirements while running:
* The mock banner must be **absent**; every request goes to `E2E_API_URL`; assert in the harness that `window.__MSW__` is undefined.
* For each journey also execute the **real-only assertions** behind `isMock()` (persisted job/receipt/evidence ids retrievable via the API; exports' digests; SSE sequence integrity; no secret strings in network logs).
* **Added assertions** you write in `tests/e2e/integration/merge-assertions.spec.ts` (merging-owned; commit it): after J01 completes, query the API directly and assert: `attempt` count = 3 with the order and outcomes of architecture 40 §6; contract/rover hashes identical across attempts (`GET /tests` → `mission_revision_id`, rover id same; `GET /missions/{id}`/`/mission-revisions/{id}` hash unchanged); the assurance artifact validates against `scientific-assurance.schema.json`; the passport has `assurance_evidence_id` ∈ `evidence_ids`; `manifest_sha256` reproduces; the three exports' bytes hash to their `X-Artifact-SHA256`; every UI-readable artifact parses (architecture 35 §5b).
* Run each journey **twice** (second run on a fresh mission) to catch order/idempotency dependence.
* Failures: save the Playwright trace and DOM; triage with `06`; fix the root cause at the owner's code; re-run the whole journey set after any fix.

### J-matrix (what must be observed; ids from `ui-testids.json`)

| Journey | Scenario / rover | Key observations in the real UI |
| --- | --- | --- |
| J01 | `synthetic-mars-mobility-v1`, ARES-1 | the 16 steps of architecture 39 §3, three attempts, LIMITED assurance, three downloads verified |
| J02 | `synthetic-graph-regression-v1` | 120 m/26 Wh/0 m FAIL then 230 m/30 Wh/150 m PASS visible in `benchmark-row`s |
| J03 | `synthetic-moon-gap-v1`, no rover | planetary Moon panel; thermal UNKNOWN; gravity/vacuum GAP; PROVE IT disabled with reason; LIMITED passport |
| J04 | rover authoring | invalid JSON/field errors; nothing persisted; input preserved |
| J05 | `PRACTICE-LITE` | ROVER failure; no relaxation; next step `NEW_CONTRACT_REQUIRED` |
| J06 | `PRACTICE-NO-ENERGY-MODEL` | INCONCLUSIVE/DATA; `unknown-value` for energy |
| J07 | cancel | `CANCELLED`, evidence kept, no passport/PASS |
| J08 | offline/online | paused→resync; unique increasing `data-seq`; final = API snapshot |
| J09 | 390 px, keyboard, 200 % zoom | all reachable; axe clean |
| J10 | immutability | new draft revision; old run unchanged; direct API mutation attempts rejected |
| J11 | `local-dataset-practice-v1` | parity with J01 |
| J12 | `live-hackathon-v1` unbound | disabled with `AWAITING_DATASETS` |
| J13 | `live` without key | 503 `PROVIDER_AUTH_FAILED`, `remediation-hint`, no run, no fallback |

### Additional scenario runs (API or UI)

`PRACTICE-SMALL-BATTERY` (ROVER, `C-ENERGY-RESERVE`), search-limit run with `ANALOGFORGE_TEST_HOOKS=1 ANALOGFORGE_OPERATOR_LIMITS_JSON='{"search_max_expansions":1}'` (INCONCLUSIVE/SEARCH_LIMIT, `empty-state[data-reason=SEARCH_LIMIT]`), portfolio build after J01 (`BUILD_PORTFOLIO` over the shortlist: selected `[Practice grid-r0c0]` only, residuals = unknown/gap rows, coupled group verified at B), nomination of a user AOI (`NOMINATE_CANDIDATE` ⇒ origin `USER_SUPPLIED`).

## 4. Hands-on click-through (supplement, not replacement)

If your environment provides a browser/computer-use tool, open `http://localhost:5173` and perform J01 manually: create the mission, import the ARES-1 file, build the fingerprint, accept, start, inspect each tab, select candidate A, press PROVE IT, watch the three attempts, open the passport, download the three files. Record anything that looks wrong or confusing (misleading label, missing unit, hidden unknown) in the report even if tests pass; screenshots to `out/screens/`.

## 4b. Professional-quality verification of the merged build (MRG-11)

The product must look like a delivered mission-operations tool (architecture 41). Mechanical audits on the Aradhya branch prove it in mock mode; you must prove it on the **merged, real-backend** build.

1. **Assets intact:** `python3 "merging guide/scripts/purity_check.py" --person merging --repo . ` shows `D-01` PASS (design assets equal the guide copies, tokens verified, no slop patterns).
2. **Re-run the visual audit against the merged app:** `pnpm run audit:visual` (mock mode) must still pass after wiring edits; then run the same crawl with mocks off against `http://localhost:5173` during the J01 real journey and collect screenshots of S01–S12 plus empty/error/loading/disabled states, dark and light, 1440×900 and 390×844, into `out/visual/`.
3. **Check the mock-vs-real gap:** real data produces strings the mocks did not (long names, big numbers, unexpected nulls, many requirements). Look for overflow, truncated values, un-tabular numerals, unit-less numbers, raw enum names, `undefined`/`null` text, console errors. Fix in the cheapest correct place (usually a formatter) and record each as a wiring edit.
4. **Independent design review of the real-backend screenshots:** spawn **three fresh reviewer subagents** (HMI operator / accessibility+typography / slop detector) and give them only architecture 41, the screenshots and the rubric of 41 §20; require ≥ 5 concrete, selector-level defects each (or an evidenced statement that fewer exist). Fix every blocker/major, re-shoot, re-review with new subagents until every criterion ≥ 3 and mean ≥ 3.5. Paste verbatim reports into `team handoffs/merging/DESIGN-REVIEW-MERGED.md`.
5. **Your own judgment pass:** answer the §6 checklist of `team guides/Aradhya/10-DESIGN-SYSTEM-AND-VISUAL-QA.md` yourself from the screenshots. Any "no" is a defect: repair it (replace the offending code; do not layer overrides).
6. **Print:** print the real passport route to PDF; confirm page 1 shows mode badge, headline, manifest digest; no clipped tables.

MRG-11 is `PASSED` only when 1–6 are evidenced in `MERGE-REPORT.json.visual_review`.

## 5. Recovery and resilience (MRG-07)

```bash
# 1. kill API during a run, restart; snapshot and events recover (no duplicate attempts)
# 2. kill the worker mid-SEARCH_ROUTE (kill -9 the CPU child and the worker); a replacement worker completes within lease expiry (120 s) + retry; one result per attempt
# 3. two workers against one DB (explicit recovery test): only one owns a lease at a time
# 4. restart Postgres container mid-idle; API/worker reconnect
```
Expected: committed state preserved; budgets not reset; no late PASS after cancellation; SSE resumes from the cursor.

## 6. Adversarial acceptance on the merged API (architecture 39 §4)

Fabricated evidence ids, foreign-workspace evidence, threshold lowering to 13 % reserve, replan with a changed contract hash, unlisted tool, stale revision, replayed idempotency key with a new body, late publish after lease loss, tampered replay blob, tampered export, expired SSE cursor — each produces exactly the specified rejection. Use your own `httpx` scripts against the running server.

## 7. Security and hygiene scans (MRG-08)

```bash
python3 "merging guide/scripts/purity_check.py" --person merging --repo . --base origin/main --json out/purity-merged.json    # forbidden patterns, secrets, big files on the merged tree
python3 "team coordination/scripts/validate_team_setup.py"     # guides/baseline integrity (should still pass on the merged tree)
git ls-files | xargs grep -nE "(sk-[A-Za-z0-9]{20,}|BEGIN (RSA|PRIVATE)|postgresql://[^:]+:[^@ ]{8,}@)" | grep -v ".env.example"   # none
grep -r "OPENAI_API_KEY\|EARTHDATA_TOKEN" apps/web/dist | head                                        # none in the built frontend
```

## 8. Clean-checkout rebuild (MRG-06)

```bash
rm -rf ../af-clean && git clone --branch integration/rc <repo-or-local> ../af-clean && cd ../af-clean/analogforge
make bootstrap && make migrate && make seed-synthetic && make check          # then the J01 journey in real mode
```
Must pass using committed files only (no leftover `.env`, caches, data, `node_modules`).

## 9. Requirements ledger and scientific report (MRG-09, MRG-10)

* Copy `architecture files/contracts/requirements-traceability.csv` to `team handoffs/merging/requirements-ledger.csv`; for each of the 58 `PR-*` rows fill `status` (`VERIFIED` only with an executed test; else `IMPLEMENTED`/`BLOCKED_EXTERNAL`/`NOT_IMPLEMENTED`), `implementation_paths`, `test_names`, `observed_evidence` (journey/test id and output path). Use architecture 30's coverage map to find owners. Any `NOT_IMPLEMENTED` row is a defect to repair (or a documented, justified exception that blocks "complete").
* Fill `team handoffs/merging/scientific-validation-report.json` from `team coordination/templates/scientific-validation-report.template.json` with the exact merged SHA, locks (schema, science port, assurance policy, algorithm lock, dataset policy lock, acquired manifest), SCI-01…SCI-18 each with test path, command, exit code, mode, evidence ids; S0–S4 stages only as far as executed (synthetic ⇒ S0/S1 and the synthetic S4 analogue is **not** real S4); real-source, live-model and physical gates remain `BLOCKED_EXTERNAL`/`NOT_IMPLEMENTED`, never passed.

## 10. Exit criteria for this plan

All MRG-01…MRG-11 rows `PASSED` (or an honestly blocked row with an explicit reason that the merge-report summary lists first and that does not involve an environment you could have obtained). Then proceed to `05`.
