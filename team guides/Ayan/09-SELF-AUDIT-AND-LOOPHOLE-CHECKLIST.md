# Ayan — self-audit and loophole checklist

Run this entire file before you declare done (phase A6). Its purpose: prove your tests can fail, your outcomes are computed, and no shortcut slipped in. Record the result of each step in `STATUS.json.self_audit`.

## 1. Automated scans (you must implement and run both scripts)

```bash
python3 scripts/science/forbidden_scan.py --json out/forbidden.json     # exit 0 required
python3 scripts/science/mutation_check.py --json out/mutations.json     # exit 0 required (every mutant killed)
```

**`forbidden_scan.py`** scans your owned production and test paths and fails on: `NotImplementedError`, `TODO`, `FIXME`, `HACK`, `XXX`; bare `pass` as a function body; `except Exception: pass` / `except: pass`; `pytest.skip`, `pytest.mark.skip`, `xfail`, `pytest.importorskip` of a *required* package in SCN tests; `os.environ`, `os.getenv`, `getenv(`; imports of `fastapi`, `sqlalchemy`, `psycopg`, `openai`, `analogforge.api|db|jobs|application|agents|tools|rendering.passport`; any literal `"NASADEM"`, `"MOLA"`, `"LOLA"` used as a `dataset_product_id`/`provider` value in a synthetic generator; string literals equal to expected practice outcomes inside `routing/`, `comparison/`, `qualification.py` (e.g. a dict mapping `"grid-r0c1"` to a status); comparisons of `window_id`/`dataset_id`/`fixture_id` to practice constants inside decision logic (`if window_id == …`).

**`mutation_check.py`** applies each mutation below to a temporary copy of the source, runs the named test selection, and requires **failure**. A surviving mutant means a missing or weak test — fix the test, not the script.

| # | Mutation | Must be killed by |
| --- | --- | --- |
| M1 | search tie-break uses reverse lexicographic order | `test_graph_oracle.py` |
| M2 | verifier copies `solver_claimed` instead of recomputing | `test_verifier_independence.py` |
| M3 | band upper bound made inclusive for non-final bands | `test_features.py` / `test_graph_oracle.py` |
| M4 | slope cap check removed from the grid graph | `test_storylines.py` (S-ROVER-LITE) and `test_perturbations.py` (PERT-03) |
| M5 | nodata cells filled with 0 before slope | `test_features.py` (halo) |
| M6 | scale/offset applied twice for the Moon dataset | `test_geometry.py` / `test_parity.py` |
| M7 | status for `grid-r0c0` forced to PASS | `test_perturbations.py` |
| M8 | network allowed in synthetic mode | `test_import_hygiene.py` |
| M9 | lossy pruning not counted | `test_search_limits.py` |
| M10 | gravity constant changed to 3.71 | `test_energy.py` |
| M11 | repeated edge earns extra unique exposure | `test_verifier_independence.py` |
| M12 | `EXHAUSTIVE_INFEASIBLE` returned whenever the queue empties | `test_search_limits.py` |
| M13 | categorical mineral ids bilinearly interpolated | `test_optional_layers.py` |
| M14 | `UNKNOWN` mapped to 0 in a metric | `test_truth_table.py` / `test_port_conformance.py` |
| M15 | analysis grid writer embeds a timestamp | `test_determinism.py` |
| M16 | ANALOG/ROVER rule inverted | `test_storylines.py` |

## 2. Manual perturbation proof

For each of PERT-01…PERT-09: run the perturbation, paste the before/after outcomes into `STATUS.json.self_audit.perturbations`. If an outcome does not change, the engine is not computing it — find the hardcoding.

## 3. Adversarial reviewers (spawn at least four subagents; each reports findings, you fix)

1. **Hardcoding hunter:** read `routing/`, `comparison/`, `qualification.py`, `compatibility.py`, `portfolio.py`; try to find any path whose output does not depend on the raster/graph/requirement inputs; propose a failing perturbation for each suspicion.
2. **Verifier breaker:** craft routes that a sloppy verifier would accept (corner cutting, nodata bridge, same-edge oscillation, wrong return, teleport between non-adjacent nodes, task within tolerance by 1 cell, energy margin sign error); add them as tests.
3. **Spec auditor:** compare every item of `08` §4 and architecture 10–13, 29, 33 line by line against the code; list deviations; fix or record as contradictions.
4. **Data-slot attacker:** craft manifests/files that should fail (traversal, symlink, wrong CRS body, Earth EPSG on Mars, radius labeled elevation, double scale, HTML page, all-zero border, 0–360 vs −180–180 mismatch) and confirm each fails with the named check and none crashes with a traceback.
5. (optional) **Determinism tester:** run twice under different `PYTHONHASHSEED`, different CPU counts and a different working directory; outputs must be byte-identical.

## 4. Final truth checks

* `grep -rn "grid-r0c\|grid-r1c\|grid-r2c" src/analogforge/science | grep -v "fixtures/\|config"` returns nothing (window ids appear only in generators/config).
* The facade works when `config/algorithms.yaml` thresholds are changed in a temp copy (e.g. `min_valid_fraction: 0.99`) — outcomes change accordingly (proves thresholds are read, not baked in).
* Running with `PYTHONHASHSEED=1` and `=2` yields identical `run_oracles.py` output.
* `python -X importtime -c "import analogforge.science.facade"` finishes under 2 s and opens no sockets.
* Delete `out/` caches and re-run the whole gate from a fresh venv: identical results.

Only after every box is true: fill `STATUS.json`, commit, push.
