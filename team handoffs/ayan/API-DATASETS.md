# API-DATASETS: dataset slot (`analogforge.science.datasets`)

Pure library for `INGEST_LOCAL_DATASET` (guide 08 section 4.1, architecture 36). No environment, network, clock or
randomness. The dataset directory is read-only; the only writes are ZIP extractions below the `scratch_dir` you pass.
Evidence/artifact packaging is the facade's job: this layer returns pure results.

## `ingest.ingest_local_dataset(dataset_dir, manifest, scratch_dir, *, max_download_bytes=2 GiB, check_cancelled=noop) -> IngestResult`
* `manifest` may be a `DatasetManifest` or the raw mapping from `registry.load_manifest_file` (strictly re-validated;
  unknown keys fail `manifest_schema`). `dataset_dir` is `context.local_dataset_root(dataset_id)`.
* Raises `DatasetUnreadableError` (code `SOURCE_UNAVAILABLE`) only when the directory does not exist -> facade returns
  `BLOCKED`. Everything else (including an invalid manifest, unreadable raster, HTML page) is a SUCCEEDED computation
  with failing checks. Manifest file unreadable/not a mapping: `registry.load_manifest_file` raises the same error.
* All 15 `check_id`s of architecture 36 section 4 are always returned, in `checks.CHECK_IDS` order. A check whose input
  does not exist (no readable raster, invalid manifest) is `WARN` with message `NOT_EVALUATED: ...` (never PASS, never
  a duplicate FAIL); such a WARN blocks quantitative use.
* `IngestResult`: `payload: IngestLocalDatasetPayload | None` (None only if dataset_id/body/role are unrecoverable from
  a broken manifest), `checks`, `failed` (check ids), `usable_for_quantitative_claims`, `manifest`, `manifest_sha256`
  (canonical hash of the validated manifest), `file_hashes` (path -> sha256 of every present file), `raster`
  (`NormalizedRaster`: float64 `values` in metres of height for ELEVATION/RADIUS, scaled values otherwise, NaN = missing,
  `missing` mask, `geotransform` (GDAL order, north-up), `crs_wkt`, `native_resolution_m`, `values_sha256`,
  `source_driver`), `applied` (`AppliedTransform`: scale, offset, `scale_applied_by` NONE|ANALYSIS|READER, unit factor,
  reference radius, `radius_subtracted`), `scale_decision`, `product_id` (`SYNTHETIC_<ID>` when synthetic, else
  `product_identity.product_id` or dataset_id), `limitations` (for the evidence draft).
* `payload.normalized_evidence = EvidenceRef(local_key="source-<dataset_id>")` exactly when a raster was normalised
  (`result.local_key`); `bbox_lonlat` = (west, south, east, north) degrees (polar rasters containing a pole span all
  longitudes; antimeridian-spanning geographic rasters may exceed 360/180 on the east side); `valid_fraction` = non-missing
  cells / all cells of the (mosaicked) grid.
* `source_evidence_draft(result, *, mode, algorithm_version, algorithm_config_sha256, seed=0) -> EvidenceDraft`: the one
  `SOURCE` draft (no artifact), `parameters_sha256` includes manifest hash, every file hash, applied transform and check
  statuses; raises `ScienceError` for a synthetic dataset in `live` mode (and a non-synthetic one in `synthetic`), or when
  there is no raster. The facade supplies versions/config hash.
* Formats: GEOTIFF/COG (GTiff), HGT (SRTMHGT, multiple tiles mosaicked on one lattice, shared border sample once, seam
  conflict/registration offset -> `format_readable` FAIL), HGT_ZIP (hardened extraction from `adapters.source_http.archive`:
  traversal, symlink, nested archive, >20x expansion, member/size caps -> `format_readable` FAIL), PDS3_IMG (opens the
  LABEL `.lbl`), PDS4_IMG (opens the LABEL `.xml`; GDAL needs a label with Cartography to georeference), NETCDF (GDAL
  subdataset by `variable`; falls back to h5netcdf EMIT-style global `geotransform` + `spatial_ref` when GDAL cannot
  georeference), HDF5 (h5netcdf only), ASCII_GRID (`.prj` sibling = file CRS). `OTHER` is unreadable by design.
* Scale/offset: `decide_scale` compares manifest and GDAL-reported values; exactly one is applied, once, and the side
  is recorded. Ambiguity (`SCALE_DOUBLE_APPLICATION_RISK` text in the message) => `scale_offset_once` FAIL.
  RADIUS => height = value*unit - `reference_radius_m`, once. Nodata is matched on the raw values; NaN for missing.

## `checks` (pure per-check functions, `CheckOutcome`, `usable`)
`usable` = manifest valid, role != CONTEXT_ONLY and every check PASS, except WARNs flagged non-blocking:
`resolution_cross_check` (5-50 %), `valid_fraction` (0.05-0.5) and `transform_sane` for `pixel_registration=UNKNOWN`.
SLOPE_DEG products WARN (blocking) in `units_and_quantity`.

## `inspect.draft_manifest(dataset_dir, body, role, *, scratch_dir=None) -> dict`
Never writes. Infers format, file roles, primary file, variable, CRS (epsg for Earth when known, else WKT), nodata,
reader scale/offset (`scale_already_applied: true`), declared resolution, longitude convention, quantity/units (RADIUS when
values look like radii). `provider`, `license_note`, `citation` (and `vertical_reference` for height products) are the
literal `TODO_FILL_IN`, so `lineage_fields` FAILs until completed. Unreadable files => unknown required keys are omitted
and a note explains. HGT_ZIP needs `scratch_dir` to be inspected. `dump_draft_yaml(draft)` gives YAML text.

## `registry`
`validate_dataset_id`, `resolve_dataset_dir(incoming_root, id)` (traversal/symlink-escape safe), `list_dataset_ids`,
`load_manifest_file(dir)` (`yaml.safe_load`, 1 MiB cap), `DatasetRegistry(incoming_root, locks_root)`,
`assert_scratch_write_allowed(target, scratch, incoming_root)`. Locks (architecture 36 section 3): `lock_entry(result,
dataset_dir)` (refuses any dataset with a FAIL), `build_lock(policy_id, created_at, entries, allow_network=False)` ->
`SourcePolicyLock` with `policy_sha256` = canonical hash without that key, entries sorted by id; `lock_is_consistent`,
`lock_to_bytes` (canonical JSON; persisting under `data/locks` is the CLI's job), `verify_lock_integrity(lock,
incoming_root) -> [LockMismatch(reason=SOURCE_CHECKSUM_MISMATCH|MISSING)]`.

## Tests
`tests/integration/science/test_dataset_validation.py` (SCN-11, SCN-14: 101 tests), `test_parity.py` (SCN-13, uses
`science.fixtures.practice`), builders in `tests/fixtures/science/datasets/dataset_builders.py`.
