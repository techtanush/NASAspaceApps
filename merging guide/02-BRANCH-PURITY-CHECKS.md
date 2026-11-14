# 02 — Branch purity checks

A branch is **pure** when it can be merged without bringing hidden defects: it follows its ownership, keeps the kit frozen, implements what its guide demands, passes its own gates with *executed* assertions, contains no shortcuts, and its claims in `STATUS.json` are true. Builders were told to self-audit; **you verify from scratch**. Run every check in a throwaway worktree of the pushed SHA. Record results in `team handoffs/merging/purity-<person>.json` (template `templates/purity-report.json`).

```bash
python3 "merging guide/scripts/purity_check.py" --person <tanush|ayan|aradhya> --repo ../af-verify-<person> --base origin/main --json out/purity-<person>.json
```
`purity_check.py` automates the structural checks (G-01…G-09 and the design check D-01 below). The rest you run and judge yourself.

## 1. Generic checks (every branch)

| ID | Check | How | Pass criterion |
| --- | --- | --- | --- |
| G-01 | Right branch, pushed, SHA recorded; `STATUS.json` + `DECISIONS.md` + `PROGRESS.md` exist under `team handoffs/<person>/` | `git rev-parse`, file existence | all present; `STATUS.json.ready_to_merge == true`; `pushed_sha` equals the branch tip |
| G-02 | Kit frozen | `python3 "architecture files/contracts/kit/materialize.py" --verify --app <worktree>/analogforge` | `PASS` (no DRIFT/FOREIGN/MISSING) |
| G-03 | Ownership | `python3 "team coordination/scripts/check_branch_ownership.py" --person <p> --repo <worktree> --base origin/main` | `PASS`; no violations |
| G-04 | Forbidden patterns | `purity_check.py` + the builder's own `forbidden_scan.py` | zero findings (see §2 patterns) |
| G-05 | No secrets/data/build output committed | `git ls-files` scans: key patterns, `.env`, `data/`, `node_modules`, `dist`, `*.tif/*.hgt/*.nc` larger than 1 MiB, signed URLs | none |
| G-06 | Dependency hygiene | `pyproject.toml` differs from kit only in own `extra-<person>`; `uv.lock` only on Tanush's branch; `pnpm-lock.yaml` only Aradhya's | true |
| G-07 | Install from scratch | fresh venv (`uv venv && uv pip install -e ".[dev,extra-<p>]"`) / `pnpm install --frozen-lockfile` | succeeds without network surprises at import time |
| G-08 | Builder's gate re-run | the exact commands of the guide's `05-TEST-AND-MERGE-GATES.md` | all pass; junit/Playwright reports have **0 skipped / 0 xfailed / 0 fixme** in required suites |
| G-09 | Claims vs reality | compare `STATUS.json` counts/exit codes with your re-run | match; any discrepancy is S1 |
| G-10 | Mutation re-run | run the builder's `mutation_check.py`; then apply **three mutations of your own** (choose from §3 or invent) and confirm tests fail | all builder mutants killed; your three killed |
| G-11 | Hardcoding hunt | perturb inputs (§3.2) and confirm outputs change | outputs follow inputs |
| G-12 | Contradictions/defects review | read `contradictions_found`, `defects_in_other_areas`, `change_requests`, `DECISIONS.md` | each is understood; defects in others' areas are queued for the wiring phase or repaired; contradictions are resolved consistently with `34` |
| G-13 | Truthful reporting | read the final printed summary / `STATUS.json` | no `PASSED` for unexecuted rows; blocked rows have proof |

## 2. Forbidden-pattern details (what `purity_check.py` flags)

In **owned production and test code** of the branch: `NotImplementedError`, `TODO`, `FIXME`, `HACK`, `XXX`; bare-`pass` bodies; `except Exception: pass`; `pytest.skip|xfail|importorskip` (required suites), `test.skip|fixme|only`, `it.skip`, `xit`; `os.environ|getenv` in science code and in the renderer; imports forbidden for the branch (see §3.x); string literals of practice window ids (`grid-r0c…`) in decision code; `"PASS"` assigned to a result outside payload-derived code; `dangerouslySetInnerHTML`, `eval(`; absolute external URLs in UI/renderer code; `sk-…` style literals; `localStorage` for server state.

## 3. Per-branch specifics

### 3.1 Tanush (platform) — `P-T`

| ID | Check |
| --- | --- |
| P-T-01 | **Database tests really ran:** start PostGIS (architecture 38 §4.1), set `TEST_DATABASE_URL`, run `uv run pytest tests/unit/platform tests/integration/platform tests/contracts/platform -q` with `AF_SCIENCE_IMPL=fake AF_RENDERER_IMPL=fake`; junit shows PLT-01…PLT-21 executed (0 skipped). |
| P-T-02 | **OpenAPI truth:** `analogforge export-openapi`; compare operationIds/paths/methods with `contracts/openapi.bundled.json` (43); run PLT-02; additionally hit every endpoint manually with `httpx` against a seeded server and validate responses against the bundled spec in your own script (do not reuse theirs). |
| P-T-03 | **Entry-point discipline:** `grep -rn "analogforge.science\|analogforge.rendering.passport" src | grep -v "importlib\|ports\|entry"` empty; `AF_SCIENCE_IMPL=real` run on this branch alone fails with the named missing-entry-point error (not a fallback, not a pass). |
| P-T-04 | **No science in the platform:** read `application/*` for any computation of slope/energy/exposure/coverage from rasters/routes; only comparisons of payload values are allowed. |
| P-T-05 | **Registrar rules:** craft bad `ScienceComputationResult`s yourself (hash mismatch, dangling `local_key`, path escape, wrong mode naming, signed `source_uri`) and confirm rejection with no domain row. |
| P-T-06 | **Policy:** submit schema-valid role results with fabricated/foreign evidence, a lowered threshold, an unlisted tool; all rejected. |
| P-T-07 | **State machine is data:** inspect `domain/state_machine.py` — the table matches architecture 14; a mutated transition breaks tests. |
| P-T-08 | **Live gates:** run with `ANALOGFORGE_MODE=live` and no key: 503 `PROVIDER_AUTH_FAILED` naming the dependency; `ScriptedProvider` never constructed (add a log/assert yourself). |
| P-T-09 | **Replan limits:** with `fake_science` configured so attempts keep failing, the run stops after 1 route repair + 1 candidate switch (3 attempts) and publishes an honest FAIL passport; with the diagnosis changed to recommend nothing, it stops immediately. |
| P-T-10 | **Assurance:** change one evidence hash after audit ⇒ publication blocked; remove a gate ⇒ `NOT_ASSESSED` ⇒ positive claim rejected; `assurance_evidence_id` is non-null at the DB level. |
| P-T-11 | **Exports:** two downloads byte-identical; `X-Artifact-SHA256` equals the SHA-256 of the bytes; manifest digest differs from file digest and reproduces with an independent `rfc8785`. |
| P-T-12 | **Security:** workspace enumeration returns 404; secrets absent from logs/SSE/exports (`grep`); test-hook env vars rejected without `ANALOGFORGE_TEST_HOOKS=1`. |
| P-T-13 | **Dataset CLI:** scaffold/validate/lock/bind work through the doubles; tamper after lock ⇒ block; synthetic into `live-hackathon-v1` ⇒ `MODE_MISMATCH`. |
| P-T-14 | **Recovery:** kill API mid-run and worker mid-job; state/events recover with no duplicates. |

Imports forbidden in platform production code: top-level `analogforge.science.*`, `analogforge.rendering.passport.*`.

### 3.2 Ayan (science) — `P-A`

| ID | Check |
| --- | --- |
| P-A-01 | `uv run pytest tests/unit/science tests/property/science tests/integration/science tests/replay/science tests/contracts/science -q` — 0 skipped; `scripts/science/run_oracles.py` output saved. |
| P-A-02 | **Independent oracle:** write your own 30-line brute-force of the canonical graph (or use the kit test) and confirm the facade's search returns exactly `catalog.GRAPH_EXPECTED` routes (120/26/0 FAIL; 230/30/150 PASS) and the verifier on the supplied 340 m route returns PASS/34 Wh/150 m. |
| P-A-03 | **Verifier independence:** read `routing/verify.py` and `routing/search.py`; confirm the verifier does not import the solver's graph/exposure modules for its decisive computation and that `solver_claimed` is never read; mutate a route node and a claimed total — verifier outcome follows the route. |
| P-A-04 | **Practice data:** run `generate_all` twice into two dirs — byte-identical; run an **independent** window checker of your own (scipy connected components) on the Earth grid: properties of architecture 40 §4 hold; regenerate with `moat_cells=0`, `ramp_slope_deg=10` and confirm PERT-01/02 outcomes flip. |
| P-A-05 | **Hardcoding hunt:** `grep -rn "grid-r0c\|grid-r1c\|grid-r2c" src/analogforge/science | grep -v "fixtures/"` empty; change `config/algorithms.yaml` `min_valid_fraction` in a temp copy and see outcomes change. |
| P-A-06 | **All 15 operations** callable through `create_science_service().execute(...)` with a `LocalScienceContext`; every result validates as `ScienceComputationResult`; evidence `algorithm_id`s equal `catalog.ALGORITHM_IDS`; UI-readable artifacts parse back into payload models. |
| P-A-07 | **Dataset slot:** `generate_mock_nasa_drop`; validate each good dataset (PASS), each bad dataset fails with exactly its named check; `draft_manifest` output validates after filling TODOs; scale applied once (Moon dataset), radius→height once, polar wedge AOI works, longitude wrap works. |
| P-A-08 | **Import hygiene:** `python -X importtime -c "import analogforge.science.facade"` imports none of `fastapi, sqlalchemy, psycopg, openai`; `grep -rn "os.environ\|getenv"` in science empty; sockets blocked in synthetic (run under a socket-blocking wrapper). |
| P-A-09 | **Determinism:** run the oracle suite under `PYTHONHASHSEED=1` and `=2`; artifact hashes identical. |
| P-A-10 | **Adapters:** read the adapters for redirect/auth handling (no `Authorization` across hosts), HTML-login detection, archive safety; confirm tests use `httpx.MockTransport` (no real server). |

Imports forbidden in science: `fastapi`, `sqlalchemy`, `psycopg`, `openai`, `analogforge.api|db|jobs|application|agents|tools|rendering.passport`.

### 3.3 Aradhya (UI + renderer) — `P-R`

| ID | Check |
| --- | --- |
| P-R-01 | `pnpm install --frozen-lockfile && pnpm run generate:client && git diff --exit-code apps/web/src/generated && pnpm run typecheck && pnpm run lint && pnpm run test && pnpm run test:contracts && pnpm run build` all pass. |
| P-R-02 | `pnpm run test:e2e:mock` — J01…J13 all executed, **0 skipped/fixme**; open the Playwright report and confirm each journey asserts the ids of architecture 39 §3. |
| P-R-03 | **Test-id contract:** every id in `contracts/ui-testids.json` appears in `apps/web/src`; remove one in a scratch copy ⇒ the contract test fails. |
| P-R-04 | **Mock guard:** `VITE_API_MOCK=1 NODE_ENV=production pnpm run build` fails; the production bundle contains no `msw`; the banner exists in mock mode only. |
| P-R-05 | **No science in the browser:** read feature code for arithmetic on measured values; the forbidden scan's allow-list contains only layout arithmetic with reasons. |
| P-R-06 | **Renderer purity/determinism:** `uv run pytest tests/unit/passport_renderer -q` (0 skipped); render all 9 fixtures × 3 formats under `PYTHONHASHSEED` 1/2/3 — identical bytes; subprocess import shows no network/DB/model modules. |
| P-R-07 | **Renderer attack:** your own hostile bundle (`<script>`, `javascript:`, `=cmd`, RTL, huge strings, zero attempts, 50 attempts, null everything) renders safely and completely, or raises the documented `RendererError`. |
| P-R-08 | **Export correctness:** `scripts/ui/verify_exports.py` on rendered fixtures: file digest, canonical manifest digest, CSV header = `CSV_COLUMNS`, HTML free of external loads/scripts, every attempt and GAP/UNKNOWN present. |
| P-R-09 | **Truthfulness:** in mock mode J01, confirm GAP vs FAIL vs UNKNOWN vs PENDING differ in label/icon/`data-status`; null measurements show `Unknown`; no similarity percentages anywhere. |
| P-R-10 | **Accessibility:** run the a11y suite; manual keyboard pass over J01 steps 1–4 and 8–9. |
| P-R-11 | **Mock fidelity:** mock fixtures validate against the bundled spec; mock exports are produced by the real renderer (re-run `scripts/build_mock_exports.py` and `git diff` is empty). |
| P-R-12 | **Design assets (automated D-01):** `analogforge/apps/web/design/tokens.json`, `scripts/ui/verify_tokens.py`, `scripts/ui/gen_tokens_css.py` equal `team guides/Aradhya/design/` (tokens may differ only with a `DECISIONS.md` entry **and** a passing verifier); `python3 scripts/ui/verify_tokens.py` prints 150/150 (or all checks pass if tokens were changed); `src/styles/tokens.css` equals the regenerated output. |
| P-R-13 | **Slop scan (automated D-01):** no hex/rgb literal outside tokens/maps, gradient, backdrop-filter, text-shadow, radius > 6 px, emoji, placeholder copy, font CDN, banned UI/animation library, NASA insignia (architecture 41 §2). Lines tagged `allowed:` are exempt — **read every one** and judge it. The single exception is `apps/web/src/styles/glass.css` (decision D-2026-11-13-GLASS, architecture 41 §5.5): gradient, backdrop-filter and radius above 6 px are permitted there, and only while `scripts/ui/forbidden_scan.py` validates it against `design/glass-surfaces.json`; a failing contract is reported here as `GLASS_CONTRACT`. |
| P-R-14 | **Visual audit:** `pnpm run audit:visual` exits 0; open `out/visual/report.json` (0 findings, 0 skipped checks, both themes, 6 viewports) and confirm the script's constants equal architecture 41 §20 (C20). Weakened thresholds or wholesale allow-lists ⇒ S1. |
| P-R-15 | **Look at it:** run `pnpm run dev:mock`, open `/__styleguide` and S01, S06, S07, S10, S12 in dark and light at 1440×900 and 390×844 with your own eyes (browser tool/screenshots). Apply the §20 rubric of architecture 41; read `team handoffs/aradhya/DESIGN-REVIEW.md` and check the reviewer reports are verbatim and from separate rounds. |

Imports forbidden in the renderer: anything but stdlib, `jinja2`, `markupsafe`, `pydantic`, kit modules.

## 4. Three mutations of your own (examples)

Platform: make the registrar accept a wrong `request_id`; remove lease fencing; make `PROVE_IT` ignore the missing rover. Science: invert the diagnosis ANALOG/ROVER rule; make the verifier accept a diagonal across nodata; apply the Moon scale factor twice. UI/renderer: swap NW/SE corners; render GAP with the FAIL icon; drop the last attempt from the HTML. Each must be caught by the branch's existing tests; if not, add a test (repair) before proceeding.

## 5. Verdict

Write `purity-<person>.json` with every ID and `PASS`/`FAIL`/`BLOCKED_ENVIRONMENT`. **Pure = every G and P row PASS** (an environment-blocked row means the branch is not yet proven pure; resolve the environment first). Impure ⇒ repair protocol (`01` §6) ⇒ re-run the affected rows and G-08/G-09.
