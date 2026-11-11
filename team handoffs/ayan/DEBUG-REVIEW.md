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

## 3. Cross-branch seam gaps still open (not Ayan-only defects; for the merging agent)
1. **Graph scenario sources.** `config/scenarios.yaml` (Tanush) sets `target_source`/`earth_source` of `synthetic-graph-regression-v1` to the abstract fixture `canonical-graph-v1`; it has no terrain raster, so real CHARACTERIZE_TARGET returns `NO_COVERAGE` and the run blocks. Proven in the trial: pointing them at `practice-mars-target-v1` / `practice-earth-grid-v1` (same Mars AOI as the mobility mission; `graph_fixture_id` unchanged for PROVE IT) reaches AWAITING_REVIEW.
2. **Assurance for VERIFICATION claims.** After PROVE IT, Ayan's AUDIT_ASSURANCE returns SC-03/SC-04/SC-06/SC-07 `NOT_ASSESSED` for the route-verification claim (it carries no `requirement_id`, so no observable policy/requirement window is resolved; mock graph energies are ASSUMED without ASSUMPTION evidence), and Tanush's assurance treats the positive claim as unsupported and raises `ScientificClaimRejected`, aborting the run instead of publishing a LIMITED result. The architecture does not define gate applicability for multi-requirement VERIFICATION claims; the merging agent must decide it (e.g. per-requirement verification claims, or explicit applicability for SC-04/SC-06 with SC-07 accepted via ASSUMPTION evidence, and rejection producing a LIMITED passport rather than an exception) and record it as a contract decision. Fake-science tests on both branches could not reveal this.
