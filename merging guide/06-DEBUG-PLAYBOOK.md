# 06 — Debug playbook (symptom → likely cause → owner → fix)

Always: reproduce with the smallest case, read the actual payload/receipt/log, classify the owner, fix the root cause with a regression test in the owner's test directory, re-run the owner's gate and the failing journey. Never weaken a test or special-case a scenario.

## A. Seam B (platform ↔ science)

| Symptom | Likely cause | Owner | Fix |
| --- | --- | --- | --- |
| Startup/preflight `SCIENCE_FACADE_MISSING` | wrong dotted path; facade import error (circular/forbidden import); optional dep missing in merged lock | Ayan (import) / Tanush (path) | run `python -c "import analogforge.science.facade"`; fix import; ensure `extra-ayan` in the lock |
| Registrar rejects every result with `input_sha256` mismatch | one side hashes a different dump of the request | whichever deviates from `canonical_sha256(request)` | both must use the kit hashing on the same `ScienceRequest` object |
| Registrar: media type rejected | facade emits an unlisted media type (e.g. `application/x-npy`) | Ayan | use `application/x-npz` for the grid; JSON artifacts `application/json` |
| Registrar: scratch path escape/symlink | facade writes outside `context.scratch_dir()` or returns absolute `scratch_relpath` | Ayan | write under scratch, relative paths |
| Registrar: dangling `local_key` | payload `EvidenceRef` points at a key not in `evidence_drafts` | Ayan | close the key set; add the stub-registrar test |
| `SYNTHETIC_` naming rejection | synthetic evidence lacks the prefix, or live evidence has it | Ayan | use `SYNTHETIC_PRACTICE_<id>` only in synthetic mode |
| UI cannot find histogram/benchmark rows | evidence `algorithm_id` not from `catalog.ALGORITHM_IDS`, or artifact not the payload JSON, or platform did not attach the evidence id | Ayan (ids/artifact) / Tanush (attachment 35 §5b) | align; add the discoverability test |
| Journey attempt 3 is on the wrong candidate | picker rule not implemented per architecture 40 §4, or `connected_zones.contains_start/band_area_m2` wrong | Tanush / Ayan | picker orders by start-zone band area desc, then screening rank, then `window_id`; verify analysis payload |
| A's attempt 2 reports `ROVER` instead of `ANALOG` | diagnosis certificate relaxation removed water masks or kept the slope cap | Ayan | rule of architecture 40 §6: remove rover-dependent constraints only, keep masks |
| Attempt 1 passes (should FAIL) | `WAYPOINT_RETURN` search accidentally enforces exposure, or verifier mis-counts exposure | Ayan | strategy semantics `science_payloads.RouteStrategy`; verify independent recompute |
| TestResult category missing for infeasible | platform did not call `DIAGNOSE_RESULT` (E-08) | Tanush | take category from diagnosis |
| Run stalls in `QUALIFYING`/`CHARACTERIZING` | `BLOCKED`/`LIMITED` science result treated as exception; worker lease expires on long CPU | Tanush | handle statuses; heartbeat during subprocess; check budgets |
| Cancel does not stop search | facade not calling `check_cancelled()`; child not terminated | Ayan / Tanush | loop checks; terminate escalation |
| Practice data differs between fixture and file source | generator parameters/seed differ; scale applied twice in the file path | Ayan | parity test SCN-13; single normalization path |

## B. Seam C (platform ↔ renderer)

| Symptom | Likely cause | Owner | Fix |
| --- | --- | --- | --- |
| `RendererError MANIFEST_DIGEST_MISMATCH` | platform hashed a different manifest than `canonical_manifest_json` | Tanush | hash exactly the stored canonical bytes with `ports.hashing`; exclude own digest field |
| `RendererError UNRESOLVED_REFERENCE` | bundle lacks evidence in `evidence_appendix` that `passport.evidence_ids` lists | Tanush (assembly) | include all referenced evidence except the assurance pointer rule |
| Renderer output differs on repeat | timestamp/env/unsorted dict in output | Aradhya | pure determinism; sorted keys; `generated_at` only |
| CSV has 0 where UNKNOWN expected | metric lookup default 0 | Aradhya | empty string when absent |
| Export header digest ≠ file hash | platform stored different bytes than returned, or re-rendered | Tanush | store the renderer's `content` once and serve it |
| HTML shows no attempts | bundle `attempts` empty because assembly omitted failed attempts | Tanush | include every attempt ordered |

## C. Seam A (frontend ↔ platform)

| Symptom | Likely cause | Owner | Fix |
| --- | --- | --- | --- |
| CORS errors / blank data | web origin not in `ALLOWED_ORIGINS`; Vite proxy not pointing at `API_PORT` | Tanush / Aradhya | env wiring (W-14) |
| TypeScript/runtime shape error on a response | server deviates from the bundled spec (null vs absent, enum value, extra field) | Tanush | conform to spec; PLT-02 should have caught it — add the failing endpoint case |
| UI asks for a field the server never sends | UI assumes beyond spec | Aradhya | use only spec fields/§5b artifacts |
| `qual-cell` stays `PENDING` forever | event not applied / snapshot stale / SSE blocked by proxy buffering | Aradhya / Tanush | check cursor logic; disable proxy buffering for `/runs/*/events` |
| 409 loops on actions | stale `expected_revision` reused | Aradhya | refetch snapshot then new decision; same idempotency key only for a *lost-response retry* |
| Duplicate `operation-row` | dedupe by `run_id+seq` missing | Aradhya | fix controller |
| `mode-badge` missing after reload | derived from local state instead of snapshot | Aradhya | read `snapshot.mode` |
| Mock banner present in real mode | `VITE_API_MOCK` leaked | Aradhya | env; guard |
| Playwright cannot find a test id | renamed/never rendered in real data path | Aradhya | restore; ensure real-data branch sets `data-*` |

## D. Data slot

| Symptom | Likely cause | Owner | Fix |
| --- | --- | --- | --- |
| `datasets validate` passes a bad dataset | missing check/short-circuit | Ayan | add the failing fixture + check |
| `scaffold` leaves nothing to fill | provenance fields auto-filled with guesses | Ayan | `TODO_FILL_IN` for provider/license/citation/vertical reference |
| `lock` succeeds for failing datasets | CLI ignores validation state | Tanush | require PASS/WARN-only |
| `bind` marks scenario AVAILABLE with missing roles | role coverage rule not enforced | Tanush | architecture 36 §3 |
| Synthetic data bound to live scenario | `MODE_MISMATCH` check missing | Tanush | enforce |
| Locked file edited, run continues | runtime hash re-verification absent | Tanush | `local_dataset_root` verifies lock hashes every access |

## E. Environment

| Symptom | Fix |
| --- | --- |
| No Docker/Postgres | architecture 38 §4.1 ladder (native install, private cluster in `analogforge/.runtime/pg`); do not mark DB gates passed without it |
| Missing GDAL driver (`PDS`, `PDS4`, `HGT`, `netCDF`) | use rasterio wheels with bundled GDAL or install system GDAL; preflight `RUNTIME` lists drivers |
| Playwright cannot launch | install Chromium (`pnpm exec playwright install chromium`) or use `/opt/pw-browsers/chromium` with `--no-sandbox` |
| Port in use | pick the next profile ports; update `API_PORT/WEB_PORT/DB_PORT`, CORS and Vite proxy together; do not kill unknown processes |
| `uv lock` conflicts after merging extras | resolve by relaxing only the conflicting *extra* dependency pins in the owner's list; never touch kit dependencies |

## F. Escalation rule

If a defect needs a kit change, follow `01` §2: reproduce, minimal change request, `tools/build_kit.py`, kit tests, update all consumers, re-run **everything** (purity rows G-02, wiring W-01…W-15, journeys), and record it in the report under `kit_changes`.
