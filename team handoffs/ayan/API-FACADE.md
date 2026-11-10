# API-FACADE: `analogforge.science.facade:create_science_service`

```python
from analogforge.science.facade import create_science_service
svc = create_science_service()              # optional: create_science_service(config_dir=Path(...)) for a config copy
svc.supported_operations()                  # all 15 ScienceOperation values
result = svc.execute(request, context)      # ScienceComputationResult
```

## Behaviour
* `execute` never raises for expected problems: unknown/missing coverage, unresolved CRS, stale hash, missing evidence/artifact, policy denial, an
  invalid dataset, a mock provider outside synthetic mode -> `BLOCKED` with exactly one `ScienceIssue` (`code` canonical, `detail_code` fine).
  Partial-but-valid -> `LIMITED` (+issues; e.g. window valid fraction 0.05-0.80, `ENERGY_UNCALIBRATED`, a requested display layer without data).
  Unexpected exception -> `FAILED` (`code="SYSTEM"`, `detail_code=<exception type>`). `ScienceCancelled`/`ScienceDeadlineExceeded` propagate untouched.
* Result envelope: `algorithm_id` = `catalog.ALGORITHM_IDS[op]` (`resolve-coverage`, `fetch-source`, `build-display-layers` from `algorithm_lock`),
  `input_sha256 = canonical_sha256(request)`, `parameters_sha256` per DECISIONS F-02, `counters` (search: expansions, labels, elapsed_ms; screening: windows).
* Writes only below `context.scratch_dir()` at `<operation>/<parameters_sha256[:16]>/<name>`; no environment reads; no network in synthetic/replay.
* `ScienceOptions.algorithm_config_sha256` pins the configuration (mismatch -> BLOCKED `ALGORITHM_CONFIG_MISMATCH`). `max_expansions/max_seconds/max_labels_per_node` can only lower the frozen solver budgets.

## Evidence and artifacts per operation (local keys)
| Operation | Evidence drafts (algorithm id) | Artifacts |
| --- | --- | --- |
| INGEST_LOCAL_DATASET | `source-<dataset_id>` SOURCE (`ingest-local-dataset`), only when a raster was read | none |
| RESOLVE_COVERAGE | `coverage` (`resolve-coverage`) | JSON payload |
| FETCH_SOURCE (live) | `source-<i>` SOURCE per asset | SOURCE_BYTES per asset |
| CHARACTERIZE_TARGET | SOURCE, `profile` (`characterize-target`), `target-grid` (`characterize-target`, ANALYSIS_GRID of the AOI) | profile JSON, `target-grid.npz` |
| SCREEN_CANDIDATES | SOURCE, `window-<id>` per non-excluded window (no artifact, `comparison_scale_m` = common support), `screening` (`screen-candidates`) | screening JSON |
| ANALYZE_CANDIDATE | SOURCE (+mineral SOURCE if bound), `analysis` (`analyze-candidate`, ANALYSIS_GRID), `analysis-summary` child (`analysis-summary`) | `analysis-grid.npz`, summary JSON |
| COMPARE_REQUIREMENT | `requirement` ASSUMPTION (Requirement JSON), `comparison` COMPARISON (`compare-requirement`) | requirement JSON, comparison JSON |
| ASSESS_COMPATIBILITY | `compatibility` (`assess-compatibility`) | JSON |
| DESIGN_BENCHMARK | `design` (`design-benchmark`) | CONSTRAINTS JSON (`constraints`; `constraints_sha256 = canonical_sha256(artifact)`) |
| SEARCH_ROUTE | `search` (`search-route`) | ROUTE JSON (`route`) when a route exists |
| VERIFY_ROUTE | `verification` VERIFICATION (`verify-route`), `route-telemetry` child | verification JSON, TELEMETRY JSON (`telemetry`) |
| DIAGNOSE_RESULT | `diagnosis` (`diagnose-result`) | JSON |
| OPTIMIZE_PORTFOLIO | `portfolio` (`optimize-portfolio`) | JSON |
| BUILD_DISPLAY_LAYERS | `display` (`build-display-layers`) | one PNG per layer + payload JSON |
| AUDIT_EVIDENCE | `audit` (`audit-evidence`) | JSON |

## Request conventions the platform must follow
* SYNTHETIC_FIXTURE sources need `source_policy.synthetic_fixture_ids` to contain the fixture (or be empty); LOCAL_DATASET sources need the id in `local_dataset_ids`
  and `context.local_dataset_root(id)`. A bound `LUNAR_THERMAL` / `EARTH_MINERAL` dataset is "bound" by being listed in `local_dataset_ids`.
* `ANALYZE_CANDIDATE`: the window is found by `candidate.window_id` in `config/candidates.yaml` (fixed practice grid first, else the generated grid).
* `COMPARE_REQUIREMENT`: `target_evidence_ids` / `candidate_evidence_ids` must be in `input_evidence`; candidate side should contain the `analysis` and
  `analysis-summary` handles (W1 is re-derived from the ANALYSIS_GRID at the target's support). Target handles are only consulted by policies that read the target
  (`slope-w1-common-support-v1`, `mineral-presence-v1`, `thermal-min-v1`).
* `AUDIT_EVIDENCE`: include the `requirement` ASSUMPTION handle(s) among `input_evidence` so SC-04 can read the requirement window; otherwise SC-04 is NOT_ASSESSED.
* `DESIGN_BENCHMARK` raster: `analysis_evidence_id` must be in `input_evidence` with its ANALYSIS_GRID artifact readable via `context.read_artifact`.
  `SEARCH_ROUTE`/`VERIFY_ROUTE`/`DIAGNOSE_RESULT` read `constraints.grid.analysis_grid_sha256` via `context.read_artifact` (the platform must authorize that blob).
* Dataset-slot `LOCAL_DATASET` rasters must be north-up, square-cell, projected (UTM/planetary); geographic rasters are BLOCKED `UNSUPPORTED_CRS` (no reprojection in this build).

## Known limitations (honest)
* ADAPTER_EVIDENCE sources, live RESOLVE_COVERAGE/FETCH_SOURCE are wired to the adapters but only exercised with mocked transports (SCN-18); not validated against real servers.
* Display THERMAL/MINERAL layers: no evidence artifact carries those rasters, so they are reported as issues.
* The kit `ClaimScope` has no requirement window: see DECISIONS A-02 / F-06.

## Tests
`tests/contracts/science/test_port_conformance.py`, `tests/integration/science/test_{screening,truth_table,storylines,perturbations,optional_layers,determinism,cancellation,budgets}.py`,
`tests/unit/science/test_import_hygiene.py`; helpers `tests/support/{registrar_stub,builders,graph_flow,practice}.py`; scripts `scripts/science/{forbidden_scan,mutation_check,run_oracles}.py`
(+`mutants.json`).
