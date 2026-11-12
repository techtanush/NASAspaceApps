# API-FIXTURES: practice data, mock NASA drop, in-memory fixture loaders

All under `analogforge.science.fixtures` (pure; writes only below the `out_dir` it is given). Everything is SYNTHETIC: provider
`SYNTHETIC_PRACTICE` / `SYNTHETIC_MOCK_NASA_DROP`, product ids `SYNTHETIC_*`, never labelled NASA/NASADEM/MOLA/LOLA.
CLI: `python scripts/science/generate_practice.py --out DIR [--mock-nasa-drop] [--seed N]` prints `{dataset: {file: sha256}}`.

## practice.py
* `generate_all(out_dir, *, seed=20261105, only=None, **kwargs) -> list[str]` writes `out_dir/<dataset_id>/{manifest.yaml, *.tif}` for
  `practice-mars-target-v1`, `practice-moon-target-v1`, `practice-moon-thermal-v1`, `practice-earth-grid-v1` (+ `-water.tif`, role MASK),
  `practice-earth-minerals-v1`; returns the dataset ids written. **Byte-deterministic** (uncompressed untagged GeoTIFF, fixed YAML order,
  manifests carry file sha256). `only=[ids]` restricts. Unknown kwargs -> `TypeError`, bad fractions -> `ValueError`.
* kwargs (perturbations): every `EarthGridParams` field - `moat_cells` (window A, default 4), `ramp_slope_deg` (B, 15), `ramp_width_cells` (10),
  `roof_slope_deg`, `mesa_slope_deg`, `mesa_rows/first_col/last_col`, `known_moat_cells`, `known_radius_cells`, `rolling_*_radius_cells`,
  `gentle_radius_cells`, `stripe_first_col/width`, `mineral_valid_fractions`, `noise_m` - plus `target_fractions` (= `mars_fractions`,
  `((slope_deg, fraction), ...)`, default `((3,.4),(7,.3),(14,.2),(22,.1))`) and `moon_fractions` (`((2,.5),(6,.3),(13,.15),(20,.05))`).
* `make_options(seed, **kwargs) -> PracticeOptions`, `build_product(dataset_id, options) -> PracticeProduct(manifest, rasters)` (no I/O),
  `write_product`, `write_geotiff`, `manifest_yaml`, `sha256_file`.

## Geometry of the practice Earth grid (192x192, EPSG:32612, 60 m, SW corner 494240, north edge 3900000)
Features are compactly supported, so the grid is continuous; slopes come only from computing on the rasters.
| window | construction (generator) | measured (independent checker) |
| --- | --- | --- |
| r0c0 B | plateau, 10-cell wide 15 deg ramp running the full window height (the narrowing wedge where the 5.5 deg roof meets it lies in r1c0), lowland east | f_band 0.143, ramp extent 63 cells, inscribed diameter 10 cells, loop exposure 0 m, band edge 7560 m |
| r0c1 A | 15 deg tilted slab (foot on its south side), water moat 4 cells, grid-edge on the north | f_band 0.28, valid 0.824, moat 4.0 cells, start component 0 band cells |
| r0c2 C | flat | f_band 0, max slope 0.03 |
| r1c0 | receives B's wedge (band), no extra cone (`rolling_1_radius_cells=0`) | f_band 0.029 |
| r1c1 | water except a 4x5 land patch | water 0.999 |
| r1c2 | nodata band 25 columns wide | valid 0.547 |
| r2c0 / r2c1 | isolated 15 deg cones R 6.6 / 4.1 cells | 0.025 / 0.007 |
| r2c2 KNOWN | 15 deg cone R 11, moat 4 | f_band 0.074, valid 0.814, moat 4.1 |
Targets: Mars strips 51/38/26/13 columns, alternating sign (measured 0.42/0.30/0.19/0.087); Moon rings by `rho^2` area shares (measured
0.499/0.299/0.150/0.052 over 1042 wedge cells); Moon heights stored as int16 `round(h/0.5)` (radius = raw*0.5 + 1737400), no GDAL scale tags.

## graph.py (in-memory loaders)
* `load_fixture_arrays(fixture_id, options=None) -> FixtureArrays(manifest, grid: AnalysisGridSpec, values, missing, water, native_resolution_m)`
  where `values` are physical units after `science.raster.normalize.normalize_elevation` (scale/offset once, radius -> height once) - the same
  step a `LOCAL_DATASET` read performs, so both give bit-identical rasters. `physical_values(manifest, raw)` exposes the step.
* `load_source_raster(fixture_id, options=None) -> SourceRaster` (terrain fixtures; `synthetic=True`, product id `SYNTHETIC_*`, water mask).
* `load_canonical_graph(drop_edges=()) -> GraphSpec` (the `canonical-graph-v1` regression graph). `FIXTURE_IDS`, `RASTER_FIXTURE_IDS`,
  `UnknownFixtureError` (KeyError).

## mock_nasa_drop.py
`generate(out_dir, *, seed=20261105, only=None) -> list[str]` writes the nine datasets of arch 39 section 5 (`GOOD_IDS`, `BAD_IDS`,
`BAD_EXPECTED_CHECK = {mock-nasa-bad-no-crs: crs_resolved, mock-nasa-bad-html: html_login_page, mock-nasa-bad-double-scale:
scale_offset_once, mock-nasa-bad-units: units_and_quantity}`). Good: HGT (two 1201x1201 big-endian tiles, shared seam column, 400-cell void),
GeoTIFF float32 with GDAL scale 0.25/offset -1000 (`scale_already_applied: true`, geographic Mars, lon 200-201), PDS3 `.lbl`+`.img`
(int16, SCALING_FACTOR 0.0005 / OFFSET 1737.4 km, RADIUS, simple cylindrical), NetCDF `mineral_metadata/group_1_mineral_id` (fill -9999,
root `crs` grid mapping), Esri ASCII grid + `.prj` (EPSG:32612, NODATA_value -9999). Verified with the dataset ingest: the five good ones
have no FAIL and are usable; each bad one fails exactly its named check.

## Tests
`tests/fixtures/science/window_checker.py` (independent: own 3x3 plane fit, scipy.ndimage components, own Dijkstra/auto-waypoints, never
imports `science.routing`; `check_window`, `check_all_windows`, `mars_target_fractions`, `moon_wedge_fractions`),
`tests/integration/science/test_practice_windows.py`, `test_mock_nasa_drop.py`, `tests/unit/science/test_fixtures_determinism.py`.
