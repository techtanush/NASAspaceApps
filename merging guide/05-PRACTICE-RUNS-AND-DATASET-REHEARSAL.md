# 05 — Practice runs, mock NASA drop and the NASA-ready checklist

Goal: prove that **every piece except the real NASA dataset** is present and working, and that the dataset slot works for any product described by a manifest. You are rehearsing the hackathon day ([37](../architecture%20files/37-HACKATHON-DAY-RUNBOOK.md)) with synthetic data of the same shape.

## 1. Practice rover and scenario matrix (run all; real API; record outcomes)

| # | Scenario | Rover | Candidate path | Expected final result (architecture 40 §6) |
| --- | --- | --- | --- | --- |
| P1 | `synthetic-mars-mobility-v1` | ARES-1 | select `Practice grid-r0c1` (A), PROVE IT | attempts: A/`WAYPOINT_RETURN` FAIL ROUTE `EXPOSURE_SHORTFALL`; A/`EXPOSURE_COVERAGE` `EXHAUSTIVE_INFEASIBLE` FAIL ANALOG; `Practice grid-r0c0` (B)/`EXPOSURE_COVERAGE` PASS; passport LIMITED; replans 1+1 |
| P2 | same | ARES-1 | select B directly | attempt 1 (`WAYPOINT_RETURN`) FAIL ROUTE; attempt 2 (`EXPOSURE_COVERAGE`) PASS on B; one route repair |
| P3 | same | `PRACTICE-LITE` | select B | FAIL ROUTE then `EXHAUSTIVE_INFEASIBLE` ⇒ **ROVER**; `NEW_CONTRACT_REQUIRED`; contract unchanged |
| P4 | same | `PRACTICE-NO-ENERGY-MODEL` | select B | exposure attempt route found; **INCONCLUSIVE / DATA** (`ENERGY_UNCALIBRATED`); `DATA_REPAIR`; stop `DATA_BLOCKED` |
| P5 | same | `PRACTICE-SMALL-BATTERY` | select B | `EXHAUSTIVE_INFEASIBLE` by lossless energy bound ⇒ **ROVER**, `C-ENERGY-RESERVE` |
| P6 | `synthetic-graph-regression-v1` | ARES-1 (blueprint) | — | 120 m/26 Wh/0 m FAIL then 230 m/30 Wh/150 m PASS |
| P7 | `synthetic-moon-gap-v1` | none | — | site-only LIMITED passport; thermal UNKNOWN; gravity/vacuum GAP; PROVE IT blocked |
| P8 | `synthetic-mars-mobility-v1` | ARES-1 | search-limit hook (`search_max_expansions=1`) | INCONCLUSIVE / SEARCH_LIMIT |
| P9 | `local-dataset-practice-v1` | ARES-1 | A then PROVE IT | identical to P1 (parity), `R-MINERAL` reason `TARGET_EVIDENCE_MISSING` |
| P10 | P1 with the perturbations PERT-01…PERT-09 of architecture 40 §8 | — | — | each changes the outcome as specified (run via regenerated practice data / modified missions) |

For P1–P9 also: verify each result in UI **and** via the API; download exports; verify digests with `analogforge/scripts/ui/verify_exports.py`.

## 2. Perturbation proof on the merged system (anti-hardcoding)

Re-run at least PERT-01 (moat 0 ⇒ A passes after the route repair, no candidate switch), PERT-03 (rover cap 14° ⇒ ROVER), PERT-04 (battery) and PERT-07 (mineral binding) end to end through the merged app (generate perturbed practice data with the generator keyword arguments, lock, bind, run). If any outcome does not change, something is hard-coded: find and repair (S1).

## 3. Mock NASA drop rehearsal (MRG-05) — exactly architecture 39 §5.1

1. `analogforge datasets generate-mock-nasa-drop`.
2. For each good dataset: `datasets scaffold` (verify the inferred fields), complete the `TODO_FILL_IN` provenance/vertical-reference fields, `datasets validate --write-checksums` ⇒ all checks PASS.
3. Each bad dataset fails with exactly its named check (`crs_resolved`, `html_login_page`, `scale_offset_once`, `units_and_quantity`).
4. `datasets lock --policy-id local-practice-policy-v1 --datasets mock-nasa-earth-dem mock-nasa-mars-dem`, `scenario bind local-dataset-practice-v1 --target-terrain mock-nasa-mars-dem --earth-terrain mock-nasa-earth-dem`, `preflight --mode synthetic --scenario local-dataset-practice-v1`.
5. Run J01 steps 5–16 on that scenario: completes with a passport; the outcome (whatever it is) is truthful and consistent across UI/API/exports.
6. `scenario bind live-hackathon-v1 --target-terrain mock-nasa-mars-dem …` ⇒ rejected `MODE_MISMATCH`.
7. Flip a byte in a locked file ⇒ the next run is blocked `SOURCE_CHECKSUM_MISMATCH` (no scientific FAIL).
8. Restore bindings to defaults (`scenario bind local-dataset-practice-v1` with the practice datasets) and re-run P9 to confirm nothing leaked.

Also run the **one-product-at-a-time variants** the hackathon may force: Earth-only binding (target dimensions UNKNOWN/NO_COVERAGE, Earth-side flow works, passport LIMITED) and target-only binding (discovery blocked `NO_COVERAGE`, limited passport).

## 4. Live-path rehearsal with test hooks (PLT-21 / MRG-05b)

```bash
ANALOGFORGE_TEST_HOOKS=1 ANALOGFORGE_ALLOW_TEST_HARNESS_PROVIDER=1 ANALOGFORGE_FAKE_OPENAI_URL=http://127.0.0.1:<port> \
  uv run pytest tests/integration/platform/test_live_rehearsal.py -q
```
Confirm: with the hooks the **live** role loop (strict tool calls, refusal/malformed/timeout handling, budgets) runs against the local fake Responses server; outputs are labeled `TEST HARNESS — not NASA data`; without the hooks the harness provider is rejected. Then run `analogforge preflight --mode live --scenario live-hackathon-v1` **without** keys/datasets and confirm it fails listing *exactly* `DATASETS_UNBOUND`, `MODEL_KEY_MISSING`, `MODEL_NAME_MISSING` (and nothing about the application itself).

## 5. NASA-READY checklist (print this in the final summary with evidence pointers)

| # | Statement | Evidence |
| --- | --- | --- |
| N-1 | Every non-data component works end to end on practice data in the real browser | J01–J13 pass (mock off) |
| N-2 | `datasets scaffold/validate/lock/bind/generate-*` work for GeoTIFF/COG, HGT, PDS3/PDS4 (GDAL), NetCDF, ASCII grid | mock drop rehearsal |
| N-3 | Bad data is rejected with a named check; synthetic data cannot enter live | mock drop steps 3, 6 |
| N-4 | Tampered locked data blocks truthfully | step 7 |
| N-5 | Live code path (roles, registrar, budgets) works against a fake Responses server | PLT-21 |
| N-6 | Preflight for the live scenario names exactly the missing items | §4 |
| N-7 | Perturbations change outcomes (no hardcoding) | §2 |
| N-8 | Honest results: FAIL/UNKNOWN/INCONCLUSIVE/GAP publish as limited/negative passports with full exports | P3–P8 |
| N-9 | Clean checkout rebuilds and passes | MRG-06 |
| N-10 | No secrets, data, or mock code in production paths | MRG-08, P-R-04 |

**What remains for the hackathon (and nothing else):** (1) the NASA product files + their `manifest.yaml`s; (2) `OPENAI_API_KEY` and `OPENAI_MODEL` in `analogforge/.env`; then run `37`.

## 6. If a rehearsal step fails

Do not adjust the rehearsal to pass. Triage with `06`; repair root causes with regression tests; re-run the affected rehearsal steps **and** J01. A failing slot step is an S1 defect because the hackathon cannot absorb it.
