# Independent debug review of the Ayan science branch (2026-11-11)

Environment: clean Linux container, Python 3.13, `uv pip install -e ".[dev,extra-ayan]"` (rasterio 1.4 / GDAL 3.12), PostgreSQL 16 + PostGIS 3.4 for the trial merge. No Docker, no network data.

## 1. Standalone gates (re-executed, not copied from STATUS.json)
| Gate | Result |
| --- | --- |
| KIT-01 `materialize.py --verify` / KIT-02 kit tests | PASS / 20 passed |
| Ownership vs `origin/main` | PASS (258 paths, 0 violations) |
| SCN offline suite (unit, property, integration, contracts) | **802 passed, 0 skipped, 0 failed** (800 before the fix + 2 new regression tests) |
| Replay suite | 200 passed |
| `run_oracles.py` | 1000 oracles, 0 skipped |
| ruff / strict mypy (74 files) | clean |
| `forbidden_scan.py` | 0 findings |
| `mutation_check.py` | 16/16 killed (matches guide 09's M1–M16) |
| Hard-coded machine paths, DSNs, usernames | none in `src`, `tests`, `scripts`, `config` |
| Merging-guide `wire_check --stage after-ayan` (Ayan-owned checks) | facade 15/15, all four entry points, import hygiene, characterize smoke PASS |

## 2. Defect found and fixed (replaced, not layered)
**SCREEN_CANDIDATES emitted per-window DERIVED evidence with `artifact=None`.** Ayan's own COMPARE_REQUIREMENT then (correctly, per architecture 33 SC-02) marks any derived evidence without artifact bytes as `SC-02 UNSATISFIED`, yet still proposed `PASS`. The platform hands COMPARE the candidate's screening evidence (architecture 35 §5b), so in a real merge every positive terrain row was rejected with `POSITIVE_CLAIM_ADEQUACY_MISSING` and the Mars and Moon runs crashed at QUALIFYING. The branch's tests missed it because their `compare` helper passes only analysis handles, never the screening handles the platform passes.

Fix (`science/ops/screen.py`): each window's evidence now carries its own canonical JSON artifact (`WindowScreeningSummary`: window id, cell, native resolution, comparison scale, valid fraction, metrics); the `artifact=None` line is gone. Regression test `tests/integration/science/test_evidence_artifact_integrity.py` (fails on the original code with exactly this defect, passes now) asserts (a) every non-SOURCE draft of every operation references an artifact in the same result and (b) with platform-shaped evidence, no PASS/PARTIAL proposal carries a gate the platform rejects.

Result in a trial merge (main + Tanush + Ayan, real PostgreSQL, `AF_SCIENCE_IMPL=real`): `synthetic-mars-mobility-v1` and `synthetic-moon-gap-v1` now run with real science from DRAFT to AWAITING_REVIEW.

## 3. Cross-branch seam gaps found in the trial merge, now fixed (2026-11-11, second pass)
The first pass listed two open gaps; both are resolved on the owning branches (this branch for science, Tanush's branch for platform). Trial merge `main + Tanush + Ayan` with real PostgreSQL and `AF_SCIENCE_IMPL=real`: **all 10 platform journey tests pass with the real science engine** (`test_runtime_journey.py` 4/4, `test_journey_api.py` 6/6: Mars mobility with ARES-1, PRACTICE-LITE, PRACTICE-NO-ENERGY-MODEL and PRACTICE-SMALL-BATTERY, graph regression, Moon gap), each ending COMPLETED with an audited passport.

Science-side fixes on this branch (each replaces the defective behavior; regression tests fail on the old code):

| Defect | Fix | Guard |
| --- | --- | --- |
| Route-level VERIFICATION claims (one per test, `requirement_id=None`; the per-requirement statements are separate QUALIFICATION claims per E-09) left SC-03/SC-04/SC-06 `NOT_ASSESSED` because no observable policy/requirement window resolves, so the platform refused every verified PASS | `audit.py`: such claims are judged on their own evidence: SC-03 body consistency + unit/id agreement; SC-04 one consistent route support on the analysis grid, `NOT_APPLICABLE` only for the abstract synthetic graph (no spatial support; refused outside synthetic mode); SC-06 `NOT_APPLICABLE` (static terrain) | `test_audit_route_verification.py` |
| SC-07: the verifier used ASSUMED energy parameters (uncalibrated rover model or the graph's mock edge energies) but cited no acceptance, so every positive verification was unsupported | `ops/route.py`: VERIFY_ROUTE emits an `ASSUMPTION` evidence (`AcceptedEnergyAssumption`: constraints hash, mission/rover revision + content hashes, provider, energy spec) recording the basis the user accepted in the contract; appended after telemetry so artifact order is unchanged | same file, incl. a negative control: without that record SC-07 is still `NOT_ASSESSED` |
| Positive QUALIFICATION claims cite the COMPARISON + requirement records, which carried only policy metrics, so the final audit found no value for SC-05/SC-08 and rejected them before the passport | `comparison/compare.py`: the COMPARISON evidence carries the decisive metrics (policy metrics plus the consulted subcriteria values), the same set COMPARE's own SC-05/SC-08 judged | `test_evidence_artifact_integrity.py::test_positive_qualification_claims_are_fully_assessable_by_the_audit` |

Platform-side fixes (Tanush's branch): graph scenario terrain sources now point at the practice rasters (the graph stays the PROVE IT fixture), and a refused claim now ends the run `BLOCKED` with `SCIENTIFIC_CLAIM_REJECTED` and the issue codes instead of an unhandled exception.

Gates after these changes: 1006 tests passed (0 skipped), 1006 oracles, mutations 16/16, ruff and strict mypy clean, forbidden scan 0, ownership PASS.

## 4. Third pass (2026-11-12): real-backend browser journeys against the merged stack
Aradhya's Playwright journeys run with mocks off against Tanush's API/worker and this science engine exposed two evidence-identity defects (the UI loads "the" artifact of an evidence carrying an operation's catalog algorithm id as that operation's payload, architecture 35 §5b):

| Defect | Fix | Guard |
| --- | --- | --- |
| Per-window screening records (pass 1) carried their own summary artifacts under the `screen-candidates` id, so the Analogs view could load a summary instead of the screening table and crashed (`windows` undefined) | each window record now points at the screening payload artifact itself (content-addressed, stored once); its metrics stay per window | `test_every_screening_tagged_record_carries_the_screening_payload` |
| The accepted-requirement `ASSUMPTION` record shared the `compare-requirement` id (and the verifier's accepted-energy record shared `verify-route`), so the matrix loaded the requirement JSON and showed every stage as PENDING | own sub-algorithm ids `accepted-requirement-record` / `accepted-energy-assumption` (added to the algorithm lock); the audit reads requirements from the new id | `test_catalog_algorithm_ids_always_point_at_the_operation_payload` (fails on the old code) |

Gates after the change: 1008 passed / 0 skipped, mutations 16/16, ruff + strict mypy clean, forbidden scan 0, ownership PASS.
