# Data ingestion, normalization, and evidence provenance

This specification implements the catalog in [08](08-DATASET-CATALOG.md), storage in [06-DATABASE-AND-STORAGE.md](06-DATABASE-AND-STORAGE.md), and immutable records in [05-DOMAIN-MODEL-AND-CONTRACTS.md](05-DOMAIN-MODEL-AND-CONTRACTS.md). Build deterministic ingestion before agents are allowed to request numerical science tools.

## 1. Module boundaries and operation types

Create the dataset protocols and registry in `science/datasets/{base,registry}.py`, provider-specific clients/decoders under `adapters/{earthdata,pds,emit,diviner}/`, normalization helpers in `science/ingestion/{archive,metadata,normalize,quality,manifest}.py`, and `science/provenance.py`. Earthdata owns NASADEM/SRTM discovery and downloads; PDS owns MOLA/LOLA/Diviner archive discovery; dedicated product decoders remain under the relevant adapter. Keep one downloader protocol/implementation rather than duplicate competing clients. Provider clients discover assets; decoders interpret them; normalizers create internal rasters; analysis tools consume only validated normalized assets. An HTTP response body must never go directly from an agent-selected URL into raster processing.

`discover_assets(request)` returns metadata candidates. `fetch_asset(asset_request)` returns immutable downloaded blobs and a fetch receipt. `normalize_asset(source_asset_id, normalization_spec)` returns a normalized asset revision. `characterize_target` and `analyze_earth_candidate` consume asset IDs and analysis specs. Tool names and authorization are governed by [15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md](15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md).

Each science operation takes `workspace_id`, `run_id`, immutable mission revision, mode, input IDs, algorithm version, and bounded limits. Its output contains result status, evidence IDs, artifact IDs, normalized parameters, checksums, warnings, and machine-readable failure codes. Inputs and outputs are validated against `contracts/domain.schema.json`; models may request these operations but cannot populate the computed fields themselves.

## 2. Data job state machine

The data operation has a narrower state than a run: `REQUESTED -> DISCOVERING -> FETCHING -> VALIDATING -> NORMALIZING -> READY`. Terminal alternatives are `NO_COVERAGE`, `AUTH_REQUIRED`, `UNAVAILABLE`, `REJECTED`, `UNSUPPORTED`, `FAILED`, and `CANCELLED`. These are ingestion states, not additional run states.

Persist a checkpoint after each transition. A worker restart reuses completed content-addressed blobs and resumes the missing step. A failed decode never marks the asset ready. A scientific operation may complete with missing evidence and cause qualification `UNKNOWN`; infrastructure failure does not become scientific `FAIL`. Parent run state transitions follow [23-JOBS-AND-RECOVERY.md](23-JOBS-AND-RECOVERY.md).

Suggested mapping:

| Operation code | Meaning | Qualification effect |
|---|---|---|
| `NO_GRANULES` | No catalog overlap for locked query | Affected observable `UNKNOWN` |
| `NO_VALID_PIXELS` | Assets overlap, quality masks remove required support | `UNKNOWN`, not evidence of absence |
| `AUTH_REQUIRED` | File access requires valid credentials/consent | Block required acquisition; retain unrelated completed evidence |
| `RATE_LIMITED` | Provider requested backoff | Retry boundedly, then `UNAVAILABLE` |
| `CHECKSUM_MISMATCH` | Download does not match expected bytes/checksum | Quarantine, fail ingestion |
| `METADATA_INCOMPLETE` | Units, CRS, body, frame, nodata, or scale unresolved | No numerical use |
| `BODY_MISMATCH` | Source and target body differ unexpectedly | Reject operation |
| `UNSUPPORTED_FORMAT` | Registry decoder lacks this product encoding | Explicit adapter gap |
| `BUDGET_EXCEEDED` | Bytes, pixels, wall time, or granules exceed approved budget | Request smaller AOI or bounded follow-up; no silent crop |

## 3. Discovery queries and locks

Use NASA's [CMR Search API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html) to resolve Earthdata collections and search granules by locked collection, AOI, time, and needed variables where supported. Supply an application client identifier, deterministic sort, bounded page size, and Search After pagination when needed. Store the normalized query, provider response metadata, time, and collection revision. Stop at the configured cap and disclose truncation; do not label a capped response complete.

Resolve PDS products through official archive indexes and detached labels. Store original index entry and label alongside image data. PDS4 LIDVIDs and legacy PDS3 IDs are separate metadata fields. The fetcher accepts only official provider locations from approved adapters, not arbitrary URLs proposed by a language model. URL redirects are checked at every hop and credentials are forwarded only according to approved provider authentication behavior.

The immutable `dataset-lock.json` freezes allowed source families/collections, exact versions, discovery extents, decoder/quality policies, and any verified seed assets. A separately revisioned acquired-asset manifest records actual product/granule IDs, member identities, SHA-256, byte length, stable source URL, provider checksum if supplied, citation, acquisition epoch, validation status, and source-policy lock ID. Appending a previously permitted granule creates a new manifest revision and source evidence; it does not mutate the policy lock or rewrite old manifest bytes. The final passport pins the final asset-manifest hash. Replacing an existing product/version, changing allowed extent/policy, or changing locked interpretation requires a new run. Unresolved setup templates may use `validation_status: PENDING`; live analyses may use only verified assets, and invented placeholder hashes are forbidden.

## 4. Download contract

Downloads are streamed into a workspace-scoped temporary directory. Enforce timeouts, connection limits, maximum decoded bytes, maximum archive members, maximum expansion ratio, and accepted content types. Check that a successful HTTP status actually contains the expected binary product rather than an HTML login page. Store both HTTP content length and observed byte count when available; disagreement fails validation unless documented transfer semantics explain it.

Compute SHA-256 while streaming, optionally resume only when the server's range/ETag behavior is verified, then atomically move the complete blob into `DATA_ROOT/blobs/sha256/<prefix>/<hash>`. Never overwrite an existing hash with differing bytes. Do not treat an ETag as universally equal to an MD5. Provider checksums add an integrity check but do not replace the local content address.

Archive extraction rejects absolute paths, `..`, symbolic links to outside the staging root, device files, nested archives unless explicitly supported, and excessive expansion. XML readers disable external entities/network resolution. PDS labels are parsed as data, never executable expressions. HDF/NetCDF subdataset selection uses registry-declared variable paths; unsupported group layouts fail cleanly.

Retry transient network failures at most three attempts, with bounded exponential backoff and `Retry-After` handling. Do not retry invalid credentials, malformed products, body mismatch, or schema errors. A later retry is a new fetch receipt linked to the same source request. All secrets and signed URL parameters are redacted from logs and exported manifests.

## 5. Canonical raster metadata

Every normalized raster records:

```text
body: EARTH | MOON | MARS
native_crs_wkt, analysis_crs_wkt
longitude_domain, longitude_direction, latitude_type, reference_frame
vertical_quantity: orthometric_height | ellipsoid_height | areoid_height | radius | relative_height
vertical_reference, vertical_units, source_scale, source_offset
width, height, affine_transform, pixel_registration
source_posting, effective_resolution_description, resampling_history
valid_mask_id, quality_mask_ids, uncertainty_asset_ids
acquisition_start/end, product_publication_time
source_asset_ids, source_label_ids, normalization_version
```

Units inside numerical arrays are meters, kelvin, or the documented dimensionless/categorical quantity. Never label a categorical raster in meters. Unknown metadata is null with an issue code, not guessed from a familiar instrument name. The affine transform must map cell centers consistently; keep GDAL's pixel-edge transform separately when required by its API.

Store normalized continuous rasters as tiled GeoTIFF/COG when practical, with explicit masks and overviews for display. Artifact IDs point to blobs; database rows hold metadata and access scope, not raster bytes. Categorical quality rasters remain separate or explicitly typed bands. Compute scientific statistics from the intended full-resolution analysis grid, never a convenient display overview.

## 6. Crop, mosaic, and resample

The requested AOI and computed AOI are separate fields. Acquire an exterior halo sufficient for the largest analysis window and interpolation footprint. If the halo is unavailable, mark affected edge cells invalid instead of padding with zeros or wrapping across the array.

Mosaic only compatible quantities with matching datum/frame or an explicit registered transformation. A vertical datum transformation must name its grids/model/version. Do not merge raw lunar radius into a height grid. Check overlap seams and nodata boundaries. Resolve tile precedence by a deterministic registry policy and expose affected areas.

Use area aggregation for coarsening a continuous elevation surface into a declared comparison grid; retain the fine source and conservative quality fractions. Use bilinear interpolation only for documented reprojection of continuous variables. Use nearest neighbor for IDs and masks, or a documented fractional coverage transform. Do not invent independent detail by upsampling. A 463 m source stored on 30 m pixels still has coarse source support.

The normalization manifest contains all source and destination transforms, resolutions, resampling methods, support windows, nodata handling, quality thresholds, and exact library/runtime versions. Scientific operations are keyed by these parameters; changing a threshold invalidates cached downstream evidence.

## 7. Evidence lineage and reproducibility

Maintain a directed acyclic evidence graph: source receipt -> decoded asset -> normalized asset -> metric -> comparison -> qualification -> verification -> passport. Each derived node includes input IDs/hashes, algorithm ID/version, canonical JSON parameters, result hash, execution environment digest, mode, timestamps, and responsible tool operation. Nodes are immutable. Newly acquired permitted assets create additional source/analysis revisions. Replacement of a locked source version, interpretation policy, or algorithm creates a new run. Do not edit a previously exported passport's evidence in place.

For cache identity use `SHA256(canonical(operation_name, version, input_hashes, parameters, mode))`. Sort map keys, normalize units before hashing, reject NaN/Infinity, and specify numeric serialization. Workspace access checks still apply when bytes are deduplicated across workspaces. Never let content-addressing bypass authorization.

Deterministic CPU operations should reproduce numerical results within declared tolerances on the locked runtime. Exact source bytes and provenance hashes must match. For stochastic uncertainty calculations, persist generator type and seed. For model explanations, persist the sanitized response and linked evidence rather than promising token-identical generation.

## 8. Modes and contamination protection

`synthetic`, `replay`, and `live` propagate into every asset and evidence node. Synthetic source names start `SYNTHETIC_` and have no NASA provider ID. Replay assets identify the original verified run and captured tool operations. Mixed-mode dependencies are rejected unless the output is explicitly a synthetic validation artifact; a live passport cannot depend on a synthetic mineral map.

In replay mode all necessary bytes and recorded agent operations must already exist. If an artifact is missing or corrupt, fail replay with `REPLAY_ASSET_MISSING` or `REPLAY_INTEGRITY_ERROR`; do not quietly make a network/model call. In live mode an absent credential creates an actionable acquisition state; do not silently switch to replay.

## 9. Acceptance criteria

Automated fixtures must demonstrate interrupted download recovery, duplicate fetch idempotency, HTML-login rejection, archive traversal rejection, checksum mismatch quarantine, missing label rejection, body mismatch, nodata halo propagation, cross-tile seam handling, categorical resampling, and mode contamination rejection. A provenance traversal from any displayed number must reach source bytes or an explicitly synthetic generator.

A human opening an exported passport must be able to identify the source product, measured quantity, support scale, derivation, assumptions, and why a dimension is unknown without access to private agent reasoning. Passing download tests alone does not validate science; see [29-SCIENTIFIC-VALIDATION.md](29-SCIENTIFIC-VALIDATION.md).
