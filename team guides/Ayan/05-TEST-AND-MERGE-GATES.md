# Ayan — tests and merge gates

A gate passes only when its tests **execute and assert**. Skips, xfails, deselects and "no tests collected" are failures. Catalog ids are in architecture 39 §1.

## 1. Commands (from `analogforge/`; omit `rtk` if not installed)

```bash
python3 "../architecture files/contracts/kit/materialize.py" --verify                        # KIT-01
uv run pytest tests/contracts/kit -q                                                          # KIT-02 (19+)
uv run pytest tests/unit/science tests/property/science tests/integration/science tests/contracts/science -q --strict-markers \
    -p no:randomly --timeout=600                                                              # SCN-01..SCN-21 offline
uv run pytest tests/replay/science -q                                                         # recorded/format-faithful fixtures
uv run ruff check src/analogforge/science src/analogforge/adapters/earthdata src/analogforge/adapters/pds \
    src/analogforge/adapters/emit src/analogforge/adapters/diviner src/analogforge/adapters/user_survey \
    src/analogforge/adapters/source_http src/analogforge/rendering/tiles tests/unit/science tests/property/science
uv run mypy src/analogforge/science                                                           # strict
python3 scripts/science/run_oracles.py --json out/oracles.json                                # prints every oracle and exit code
python3 "../team coordination/scripts/check_branch_ownership.py" --person ayan --repo ..      # PASS
```

`uv run pytest … -q` must report **0 skipped, 0 xfailed, 0 deselected** for SCN tests; a final `scripts/science/run_oracles.py` run asserts the same by parsing the junit XML (`--junitxml out/science-junit.xml`) and failing if any `skipped` element exists in SCN tests.

## 2. Required test files (names are part of the gate)

| File (under `tests/…/science/`) | Catalog | Must assert |
| --- | --- | --- |
| `unit/test_geometry.py` | SCN-01, SCN-14 | GEO-01…GEO-10 oracles; polar wedge AOI; longitude 359.9/0.1 wrap; planetary radius→height once; scale applied once; no Earth CRS for planets |
| `unit/test_features.py` | SCN-01 | flat/inclined (10°,20°)/bump/anisotropic/rotated/nodata-halo oracles with stated tolerances |
| `unit/test_energy.py` | SCN-02 | `ENERGY_ORACLE_FLAT_1000M` ≤ 1e-8 Wh; doubling mass/distance/speed relations; no downhill credit; dwell/task accounting; invalid efficiency; missing model ⇒ unknown; Earth gravity only |
| `unit/test_graph_oracle.py` | SCN-03 | every `catalog.GRAPH_EXPECTED` entry **through the real search and verifier**, brute-force oracle equality, lexicographic tie-break, mock provider rejected in `live` |
| `unit/test_verifier_independence.py` | SCN-04 | falsified solver totals, diagonal-corner/nodata traversal, stale hash, repeated-edge gaming, missing return, unreachable/too-far-snapped waypoint, non-adjacent step, mutated route |
| `unit/test_search_limits.py` | SCN-05 | one expansion ⇒ `BUDGET_EXHAUSTED`; lossy pruning never `EXHAUSTIVE_INFEASIBLE`; certificate lossless; cancellation within 1 s |
| `integration/test_practice_windows.py` | SCN-06 | independent checker: every property of 40 §4 |
| `integration/test_screening.py` | SCN-07 | 40 §4.1 exactly |
| `integration/test_truth_table.py` | SCN-08 | 40 §5 incl. oracle rule for the context row |
| `integration/test_storylines.py` | SCN-09 | S-RASTER-1 (3 attempts), S-GRAPH-1, S-ROVER-LITE, S-NO-ENERGY, S-SMALL-BATTERY at science level, through `facade.execute` only |
| `integration/test_perturbations.py` | SCN-10 | PERT-01…PERT-09 each flips as specified |
| `integration/test_dataset_validation.py` | SCN-11 | one failing fixture per `check_id`; `usable_for_quantitative_claims` rules; PASS for each good fixture |
| `integration/test_mock_nasa_drop.py` | SCN-12 | 5 good datasets validate and run end-to-end; 4 bad datasets fail with exactly the named check |
| `integration/test_parity.py` | SCN-13 | fixture-id source ≡ LOCAL_DATASET source (identical metrics/evidence parameters) |
| `integration/test_optional_layers.py` | SCN-15 | absent/partial mineral & thermal ⇒ specified reasons; categorical ids never interpolated |
| `integration/test_portfolio.py` | SCN-16 | architecture 13 §6 fixtures 1–7; input-order stability |
| `integration/test_display_layers.py` | SCN-17 | corners order, affine round-trip, legend, transparency, attribution |
| `replay/test_adapters.py` | SCN-18 | decoders and failure modes with mocked HTTP (HTML login, bad archive, checksum, redirect auth leak, 429 Retry-After, truncation disclosure) |
| `unit/test_import_hygiene.py` | SCN-19 | subprocess import of `analogforge.science.facade` loads none of `fastapi, sqlalchemy, psycopg, openai`; AST scan finds no `os.environ`/`getenv`; no network in synthetic (monkeypatched `socket`) |
| `integration/test_determinism.py` | SCN-20 | two executions produce identical payload JSON and artifact SHA-256 (excluding elapsed fields) |
| `integration/test_cancellation.py` | SCN-21 | search/screening/analysis honor cancel and deadline within 1 s |
| `contracts/test_port_conformance.py` | all | every operation returns a kit-valid `ScienceComputationResult`; `registrar_stub` accepts it and rejects crafted bad results (hash mismatch, dangling key, path escape) |
| `property/test_properties.py` | — | (hypothesis) non-negative distance/energy; no invalid-cell traversal; monotone reserve with added work; no duplicate exposure credit; deterministic hashes |

## 3. Tolerances (frozen; do not loosen)

Slope interior of planar facets ≤ 1e-6°; energy oracle ≤ 1e-8 Wh; histogram area fractions of the practice targets ±0.03 of design; analytic roughness of a pure plane ≤ 1e-9 m; affine round-trip ≤ 0.5 pixel; reserve percent ≤ 1e-9; W1 vs independent implementation ≤ 1e-9°.

## 4. Performance budgets (offline, 4 CPU cores)

`INGEST_LOCAL_DATASET` ≤ 5 s per practice dataset; `CHARACTERIZE_TARGET` ≤ 5 s; `SCREEN_CANDIDATES` ≤ 20 s; `ANALYZE_CANDIDATE` ≤ 5 s per window; `COMPARE_REQUIREMENT` ≤ 1 s; `DESIGN_BENCHMARK` ≤ 2 s; `SEARCH_ROUTE` ≤ 10 s (practice grid, default budgets); `VERIFY_ROUTE` ≤ 3 s; `OPTIMIZE_PORTFOLIO` ≤ 1 s; `BUILD_DISPLAY_LAYERS` ≤ 5 s. A test asserts each budget (`pytest.mark.slow` is allowed only for the full-suite timing test, which still runs by default).

## 5. Merge readiness

`STATUS.json.ready_to_merge = true` only if: every SCN row `PASSED`; kit verify and ownership `PASS`; ruff and mypy clean; no forbidden pattern (`09`); the self-audit complete; no hidden skip. External-network gates (`SCN-18` against real servers) are **not run** and must be listed as `BLOCKED_EXTERNAL` (the mocked-transport rows still must `PASS`).
