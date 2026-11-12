# 03 — Integration wiring: merging the three branches and connecting the seams

Think of three Lego pieces whose studs were specified in code (the kit). Merging is putting them together; wiring is checking each stud actually clicks. Do these steps in order on `integration/rc`.

## 1. Merge commands

```bash
git checkout main && git pull --ff-only
git checkout -b integration/rc
# only SHAs that passed 02 (or whose repair branches are merged first)
git merge --no-ff <TANUSH_SHA> -m "Merge tanush/platform-agents-integration (purity-checked <sha7>)"
python3 "architecture files/contracts/kit/materialize.py" --verify
git merge --no-ff <AYAN_SHA>   -m "Merge ayan/science-data-verification (purity-checked <sha7>)"
python3 "architecture files/contracts/kit/materialize.py" --verify
git merge --no-ff <ARADHYA_SHA> -m "Merge aradhya/frontend-experience (purity-checked <sha7>)"
python3 "architecture files/contracts/kit/materialize.py" --verify
```

If a repair branch exists for a person, merge `repair/<person>-<n>` immediately after that person's branch (before the next person).

## 2. Conflict resolution table

Expected conflicts are few because paths are disjoint and kit files are byte-identical. If one occurs, resolve by **ownership**, then rerun the owner's tests. Never take a whole side blindly.

| File / area | Resolution |
| --- | --- |
| Kit files (`ports/**`, kit tests/fixtures/contracts, `.env.example`, `.gitignore`) | They must be identical; if not, one branch edited the kit — restore with `materialize.py --repair --app analogforge`, then log an S1 defect against that branch |
| `analogforge/pyproject.toml` | Keep the kit text; **union** the three `extra-*` lists (each person edits only their own). Then re-lock (§3 W-01) |
| `analogforge/uv.lock` | Take Tanush's, then **regenerate** (`uv lock`) because extras changed; commit the new lock |
| `analogforge/package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml` | Aradhya's version only |
| `analogforge/Makefile`, `compose.yaml`, `README.md`, `scripts/*.sh`, `ops/**` | Tanush's version, then add the frontend wiring of §5 (W-14) |
| `analogforge/config/scenarios.yaml`, `config/presets/**` | Tanush's; then run the config cross-check (W-06/W-07) |
| `analogforge/config/{datasets,algorithms,candidates}.yaml` | Ayan's; then the cross-check |
| `team guides/<Name>/**`, `team handoffs/<name>/**` | each person's own; no real conflicts |
| `architecture files/**`, `team coordination/**` | `main`'s version (no builder was allowed to change them); a builder change here is an S1 defect |
| Anything else | classify (platform/science/UI), keep the owner's version, rerun that owner's gate |

After each merge run the **slice check**: `python3 "merging guide/scripts/wire_check.py" --stage <after-tanush|after-ayan|after-aradhya>`.

## 3. Wiring steps (all must pass; commands from `analogforge/`)

| Step | Action | Expected |
| --- | --- | --- |
| **W-01** | Union extras; `uv lock`; `uv sync --extra dev --extra extra-tanush --extra extra-ayan --extra extra-aradhya` (or `uv pip install -e ".[dev,extra-tanush,extra-ayan,extra-aradhya]"`) | lock consistent; imports of rasterio/pyproj/shapely/scipy/numpy/jinja2/fastapi/sqlalchemy/psycopg work; commit `uv.lock` |
| **W-02** | `python3 "../architecture files/contracts/kit/materialize.py" --verify --app .` | PASS |
| **W-03** | `python3 "../merging guide/scripts/wire_check.py" --stage final` (details §4) | all checks PASS |
| **W-04** | `AF_SCIENCE_IMPL=real AF_RENDERER_IMPL=real uv run pytest tests/unit/platform tests/integration/platform tests/contracts/platform -q` | same suites that passed with doubles now pass with the real facade/renderer — this is the **platform↔science↔renderer proof** (triage with `06`) |
| **W-05** | `uv run pytest tests/unit/science tests/integration/science tests/replay/science tests/contracts/science -q` and `tests/unit/passport_renderer tests/contracts/ui` | pass in the merged tree |
| **W-06** | Config cross-keys: every `catalog.ALL_SCENARIOS` id is in `scenarios.yaml`; every `search_region_set_id`/`reference_set_id`/`measurement_spec_id`/observable policy referenced exists in Ayan's YAMLs; every value of `OBSERVABLE_POLICY_BY_OBSERVABLE` has a policy; algorithm ids in `algorithm_lock` cover `ALGORITHM_IDS` | `wire_check` PASS; `analogforge preflight` parses all four YAMLs strictly |
| **W-07** | `config/presets/**` byte-equal to the kit fixtures; practice rover names equal `catalog.PRACTICE_ROVER_FILES` | PASS |
| **W-08** | `analogforge seed-synthetic` twice (idempotent, offline) → `GET /capabilities` lists the scenarios of architecture 40 §10 (`live-hackathon-v1` with `allowed_modes: []`) | PASS |
| **W-09** | OpenAPI: `analogforge export-openapi` vs `contracts/openapi.bundled.json`: 43 operationIds; run PLT-02 with the real app | PASS |
| **W-10** | `pnpm install --frozen-lockfile && pnpm run generate:client && git diff --exit-code apps/web/src/generated && pnpm run typecheck && pnpm run build` | no diff; build OK |
| **W-11** | Data slot: `analogforge datasets generate-practice`; `datasets validate` each; `datasets lock --policy-id local-practice-policy-v1 --datasets practice-mars-target-v1 practice-earth-grid-v1 practice-earth-minerals-v1`; `scenario show local-dataset-practice-v1` | all validate PASS; scenario `AVAILABLE` |
| **W-12** | Parity: run the platform journey API test for `synthetic-mars-mobility-v1` and `local-dataset-practice-v1`; compare qualification rows/attempt outcomes (only `R-MINERAL`'s reason differs per architecture 40 §5) | identical |
| **W-13** | Evidence discoverability: walk only public endpoints of a completed run and parse every UI-readable artifact of architecture 35 §5b into its kit payload model (`wire_check --stage final --run <run_id> --api <url>`) | all parse |
| **W-14** | Frontend ↔ backend: ensure `make dev` (or Compose) serves API and web together: Vite proxy `/api` → `http://localhost:$API_PORT` (read from env), `ALLOWED_ORIGINS` includes `http://localhost:$WEB_PORT`, SSE not buffered; production build servable (API static mount for `apps/web/dist` with SPA fallback, or documented reverse proxy). If missing, **you add it** (platform file edits are allowed during wiring; log them). | the app loads at `http://localhost:$WEB_PORT/` and talks to the real API |
| **W-15** | Mock isolation: real mode never imports `msw`; no `mock-banner` in the DOM | PASS |

## 4. What `wire_check.py` verifies (and what you verify by hand)

`wire_check.py --stage final` checks, importing the merged package:

1. Entry points resolve and conform: `create_science_service()` returns an object with `supported_operations()` equal to all 15 `ScienceOperation`s and a callable `execute`; `create_passport_renderer()` has `renderer_version` and `render`; `analogforge.main:app` is a FastAPI instance with ≥ 43 operations; `analogforge.cli:main` callable; `fixtures.practice:generate_all`, `fixtures.mock_nasa_drop:generate`, `datasets.inspect:draft_manifest` callable.
2. Import hygiene: importing the facade loads none of `fastapi/sqlalchemy/psycopg/openai`; importing the renderer loads no network/DB/model modules; importing `analogforge.main` does **not** import `analogforge.science.*` or the renderer at import time.
3. Config cross-keys (W-06) and presets (W-07).
4. Kit integrity (`materialize --verify`).
5. `ui-testids.json` ids all present in `apps/web/src`.
6. Algorithm ids: `contracts/algorithm-ids.json` equals `catalog.ALGORITHM_IDS`; the facade emits only those ids (checked by running two operations on practice fixtures).
7. A tiny end-to-end **science → registrar-rule → renderer** smoke in memory: runs `CHARACTERIZE_TARGET` on the practice Mars fixture through the real facade and validates the result with the kit models.

You verify by hand: that the web UI renders against the real server (W-14), the exports download with correct digests (journey J01), and that logs contain no secrets.

## 5. Seam-by-seam wiring detail

### Seam B — Platform ↔ Science
1. **Load:** Tanush's loader imports `analogforge.science.facade:create_science_service` by string. Failure modes: module path typo, facade imports platform code (cycle), facade constructed lazily and heavy. Fix in Ayan's code if it violates hygiene; fix in Tanush's loader if the path/signature is wrong.
2. **Request/response symmetry:** the platform computes `canonical_sha256(request)` with `ports.hashing`; the facade must return `input_sha256` computed identically from the **same** `ScienceRequest` instance. Most common mismatch: one side hashes with `exclude_none`/different dump mode. Both must use `canonical_sha256(request)` (kit). Fix whichever deviates.
3. **Context:** Tanush's `WorkerScienceContext` must satisfy the runtime-checkable protocol; `scratch_dir()` is a real directory; `read_artifact(sha)` returns an existing read-only path; `local_dataset_root(id)` returns the dataset dir; `check_cancelled()` raises `ScienceCancelled`; in synthetic mode `http_client()` is `None`.
4. **Artifacts/evidence drafts:** the registrar accepts the facade's real drafts: `scratch_relpath` relative, sizes/hashes right, media types in the allow-list (including `application/x-npz`), `local_key` closure, `SYNTHETIC_` product ids in synthetic mode, no `source_uri` query strings.
5. **Algorithm ids & UI artifacts:** each operation's evidence uses `catalog.ALGORITHM_IDS`; payload JSON artifacts parse back into the kit payload models; platform attaches evidence ids per architecture 35 §5b (discoverability rules).
6. **Storyline equality:** `test_journey_api` with the real facade must produce exactly architecture 40 §6 S-RASTER-1 (attempts 1 FAIL/ROUTE, 2 FAIL/ANALOG, 3 PASS on `Practice grid-r0c0`) and S-GRAPH-1. If not, determine the layer: (a) science payload wrong ⇒ Ayan's area; (b) platform mapping/picker/verification-summary rule (architecture 40 §4/§5) wrong ⇒ Tanush's area; (c) a spec ambiguity ⇒ decide by architecture 34/40 and record.
7. **Budgets/cancel:** a cancel during a real `SEARCH_ROUTE` stops within 2 s (child terminated ≤ 5 s); a real search finishes inside the default budget for the practice grid.

### Seam C — Platform ↔ Renderer
1. **Load:** `analogforge.rendering.passport:create_passport_renderer` by string; renderer imports only allowed modules.
2. **Bundle validity:** the platform-assembled `PassportExportBundle` for the J01 run validates as the kit model **and** passes `renderer.render` for html/json/csv. A `RendererError` here is a bug: decide whether the assembly (Tanush) is inconsistent or the renderer rule (Aradhya) is stricter than architecture 35 §4 — read the rule, fix the wrong side, add a regression test.
3. **Assets:** `ProvidedAsset` PNGs come from the science display/route images; the HTML embeds them as `data:` URIs; no external URLs.
4. **Digests:** `RenderedExport.sha256` equals the platform's stored file hash and `X-Artifact-SHA256`; `manifest_sha256` reproduces independently from `canonical_manifest_json`.
5. **Mode/labels:** `mode` appears in all three formats.

### Seam A — Frontend ↔ Platform
1. **Client:** regenerated from `contracts/openapi.bundled.json`; zero diff.
2. **Real responses vs UI types:** run a Playwright pass in real mode; any TypeScript `unknown`/runtime shape error indicates the server response deviates from the spec (Tanush) or the UI assumes more than the spec (Aradhya) — fix to the spec.
3. **Capabilities/scenarios:** UI options come only from `/capabilities`; `live-hackathon-v1` disabled with the reason.
4. **Artifacts:** UI-readable artifacts (35 §5b) fetched through `/evidence` → `/artifacts`; authorization works (workspace scoped).
5. **SSE:** committed events arrive through the dev proxy without buffering; reload/offline/online (J08) recover; terminal event closes the stream.
6. **Test ids:** all present and carrying their attributes in real-mode DOM (the real data path sets `data-status`, `data-stage`, `data-outcome`, etc., from live responses).

### Seam D — Data slot
Generate practice data → validate → lock → bind → run → compare to synthetic (W-11/W-12). Then the mock NASA drop rehearsal (`05`).

## 6. Wiring edits you are allowed to make (log each)

Add the Compose/Make frontend wiring, Vite proxy env wiring, API static mount for `apps/web/dist`, missing `.dockerignore`s, README run instructions, and fix path/name typos at seams. Do **not** change business logic of a branch to hide a defect — repair per `01` §6 with a regression test.
