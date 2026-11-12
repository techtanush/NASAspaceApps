# Adapter library API (`analogforge.adapters.*`)

Owner: Ayan (science library). Validated only against `httpx.MockTransport` and format-faithful synthetic files
(`tests/replay/science/test_adapters.py`, SCN-18). **Nothing here has been validated against a real server.** Host names,
index URLs and product/variable names in the default configs are unverified proposals; every one is overridable.

## Common contract

Every adapter package exposes (all keyword-only extras are optional):

```python
discover(request: ResolveCoverageInput, client: httpx.Client | None, *, policy: HttpPolicy | None = None, ...) -> list[CoverageSelection]
fetch(selection: CoverageSelection, client: httpx.Client | None, scratch: Path, *, policy: HttpPolicy | None = None, ...) -> list[AcquiredAsset]
decode(path: Path, params: <AdapterParams>) -> DecodedRaster
asset_path(scratch: Path, asset: AcquiredAsset) -> Path        # where fetch() put the bytes (deterministic)
```

* `client` is injected by the platform (`context.http_client()`); adapters never read the environment, never build a
  client and never import platform packages. Credentials are whatever the client carries (`Authorization` header or
  `auth=`). `client=None` (synthetic/replay) => `access_state="UNAVAILABLE"`; no network is ever attempted.
* Expected states are returned as data: `CoverageSelection.access_state` in
  `AVAILABLE | AUTH_REQUIRED | NO_COVERAGE | UNSUPPORTED | UNAVAILABLE`. Unknown fractions are `None`, never 0.
* Failures raise `AdapterError` (`analogforge.adapters.source_http.AdapterError`): `.code` is a canonical code from
  `contracts/error-codes.json`, `.detail_code` the architecture-09 operation code (`HTML_LOGIN_PAGE`, `AUTH_REQUIRED`,
  `TRUNCATED_TRANSFER`, `ARCHIVE_PATH_TRAVERSAL`, `BAD_ARCHIVE`, `SHAPE_MISMATCH`, `METADATA_INCOMPLETE`,
  `BODY_MISMATCH`, `GEOMETRY_MISMATCH`, `UNSUPPORTED_FORMAT`, `NO_GRANULES`, `HOST_NOT_ALLOWED`, ...), `.retryable`,
  and `.to_issue() -> ScienceIssue`. The facade maps: `PROVIDER_AUTH_FAILED/AUTH_REQUIRED` -> `AUTH_REQUIRED`;
  `SOURCE_CHECKSUM_MISMATCH` and `SOURCE_CONTENT_INVALID` -> quarantine (dependent claims UNKNOWN);
  `PROVIDER_RATE_LIMITED`, `SOURCE_UNAVAILABLE`, `TOOL_TIMEOUT` -> retryable infrastructure block.
* `AcquiredAsset.source_uri` is the redacted URL (scheme+host+path only; signed query strings dropped).
  `validation_status="VERIFIED"` only when a provider checksum matched; otherwise `"PENDING"` (local SHA-256 is still
  computed and archive/format safety was still enforced). `artifact_key` = `source-bytes:<adapter_id>:...` (the
  registrar needs a SOURCE_BYTES artifact whose scratch path is `asset_path(scratch, asset)`).
* Bytes land under `scratch/source_bytes/<adapter_id>/...`; nothing is written elsewhere.
* Discovery truncation is disclosed: when a page/product cap stops the listing, every returned selection carries a note
  starting `DISCOVERY_TRUNCATED:` and `coverage_fraction` is a lower bound. `coverage_fraction` is planar-degree
  footprint overlap (not valid-pixel coverage).
* Downloads are always resolved from provider metadata (CMR concept ids / PDS index paths). A selection carries ids only;
  an agent-supplied URL is never fetched.

## `source_http` (shared layer)

* `HttpPolicy(allowed_hosts, auth_hosts=(), max_attempts<=3, backoff_s=(2.0, 4.0), max_retry_after_s=60, max_redirects=5,
  max_download_bytes, max_metadata_bytes, allow_insecure=False, sleep=time.sleep)` - inject `sleep` in tests.
* `SafeHttp(client, policy)`: `get_bytes`, `get_json`, `download(url, dest, expected=ExpectedChecksum|None, max_bytes,
  accept_content_types, expected_magic)` -> `DownloadResult`. https only, allow-listed hosts on every redirect hop,
  Authorization/Cookie stripped on any hop whose host is neither the initial host nor in `auth_hosts`, Retry-After
  honoured (capped), HTML login detection (content-type and body sniff), declared+streamed byte limits, truncation
  detection (retried as transient), SHA-256 always, provider sha256/md5 compare (mismatch deletes the bytes, never retried).
* `safe_extract_zip(archive, dest, ArchiveLimits(max_members, max_total_bytes, max_expansion_ratio=20, allowed_suffixes), extract=True)`:
  rejects traversal/absolute/backslash paths, symlinks and special files, nested archives, duplicates, unexpected members,
  expansion > 20x (also enforced while copying), corrupt CRC.
* `DecodedRaster(data, valid, metadata: RasterMetadata, aux, dictionary)`: float64 `data` with NaN where invalid for
  continuous quantities (never 0); categorical rasters are integer with `-1` where invalid and `valid` authoritative.
  `RasterMetadata` carries body, quantity, units, vertical_reference, body-specific `crs_wkt`, pixel-edge `transform`,
  longitude domain, source scale/offset (+`scale_applied`), notes (user-facing limitations), `quantitative_use_allowed`/`issues`.
* `cmr.py`: `search_granules`, `lookup_granule`, `discover_cmr_selection`, `fetch_cmr_assets` (CMR `granules.umm_json`,
  `sort_key[]=producer_granule_id`, `CMR-Search-After`/`CMR-Hits`, client-side sort by `(granule_ur, concept_id)`).
* `geo.py`: `split_bbox(bbox, source_convention, target_convention)` (seam splitting), `coverage_fraction`.

## Adapters

| Package | `adapter_id` | discover | fetch | decode params |
| --- | --- | --- | --- | --- |
| `earthdata` | `earth_nasadem_hgt_v001`, `earth_srtmgl1_v003` (explicit alternate, never substituted) | CMR; 56S-60N pre-filter -> `NO_COVERAGE`; `AUTH_REQUIRED` when the client has no credential | zip via CMR url, provider checksum, archive validated | `NasademParams(expected_samples, work_dir)`; `mosaic(tiles)` |
| `pds` | `mars_mola_megdr`, `moon_lola_gdr` | PDS3 INDEX_TABLE (label-described fixed width), longitude-convention aware | label + detached image per product | `PdsDecodeParams(adapter_id, expected_body, quantity="height"\|"radius"\|"count", reference_radius_m, units_override, vertical_reference)` |
| `emit` | `earth_emit_l2bmin_v001` | CMR `EMITL2BMIN` v001 | `.nc` with HDF5 magic check | `EmitDecodeParams(group_prefix, mask_variable, mask_array, mask_bad_values, ...)`; `retrieval_in_bbox`, `class_area_fractions` |
| `diviner` | `moon_diviner_derived` | per explicit variable; unsupported -> `UNSUPPORTED` selection | via PDS machinery | `DivinerDecodeParams(variable)`; unsupported -> `UNSUPPORTED_PRODUCT` |
| `user_survey` | `earth_user_survey` | `uploads=[UserSurveyUpload(path, SurveyMetadata)]`, no network | copy + hash into scratch | `SurveyDecodeParams(metadata)`; incomplete metadata => preview only (`quantitative_use_allowed=False`) |

Decoder behaviours worth knowing: NASADEM `.hgt` big-endian int16, void -32768 -> NaN/invalid, NUM and water kept as
separate arrays (`aux["num"]`, `aux["water"]`, `aux["land"]`), EGM96 in `vertical_reference`; MOLA/LOLA scale/offset applied
exactly once with raw numpy (no GDAL), `quantity` must be stated (`radius` is converted to height by subtracting the label
`A_AXIS_RADIUS` or the given reference), CRS is a body-specific sphere (never an Earth datum); PDS4 labels containing a
DOCTYPE/ENTITY are refused (`XML_DTD_FORBIDDEN`); EMIT keeps categorical ids un-interpolated and reports the valid-retrieval fraction.

## Dependency note

EMIT NetCDF decoding uses `h5netcdf` with the **`h5py`** backend. `h5py` is not declared in `pyproject.toml`
(see `CHANGE-REQUEST-adapters-h5py.json`); the build venv needed `uv pip install h5py`.
