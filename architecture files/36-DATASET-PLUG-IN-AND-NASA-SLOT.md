# Dataset plug-in: the "last Lego piece" slot for NASA data

The only thing intentionally missing from the pre-hackathon build is the NASA-provided dataset. This document defines the one socket that dataset plugs into, so that on the day it is *drop files, write a manifest, run three commands*. The socket is exercised before the hackathon with practice rasters of the same shape ([40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md)) and a mock NASA drop ([39](39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) §5).

Related: adapters for network discovery/download of NASADEM, MOLA, LOLA, EMIT and Diviner ([08](08-DATASET-CATALOG.md), [09](09-DATA-INGESTION-AND-PROVENANCE.md)) are still built and tested against recorded fixtures. The drop-in path described here **is the primary hackathon path** because event data is usually supplied as files and needs no credentials ([34](34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md) E-16).

## 1. Directory layout

```text
analogforge/data/                       # git-ignored, persistent
  incoming/<dataset_id>/                # one directory per product (or product family)
    manifest.yaml                       # REQUIRED, validated against ports.datasets.DatasetManifest
    <data/label/metadata files...>      # exactly the files listed in manifest.files
  locks/<policy_id>.json                # written by `datasets lock`; the source-policy lock
  blobs/ ...                            # content-addressed store (platform)
```

`dataset_id` matches `^[a-z0-9][a-z0-9-]{2,63}$`. A dataset directory is **read-only input**: no code writes into `incoming/` except `datasets validate --write-checksums` (fills `files[].sha256`).

## 2. Manifest

`manifest.yaml` has exactly the fields of `DatasetManifest` (strict; unknown keys are errors). Field semantics:

| Field | Meaning and rules |
| --- | --- |
| `dataset_id`, `title`, `provider`, `is_synthetic` | `provider` starts with `SYNTHETIC` **iff** `is_synthetic`. NASA products use their real provider (e.g. `NASA LP DAAC`, `NASA PDS Geosciences Node`). |
| `body`, `role` | `body ∈ {EARTH, MOON, MARS}`. `role` is the only thing that decides how the dataset is used: `TARGET_TERRAIN` (Moon/Mars elevation), `EARTH_TERRAIN`, `EARTH_MINERAL`, `LUNAR_THERMAL`, `CONTEXT_ONLY`. Incompatible body/role pairs are rejected by the model. |
| `format`, `files`, `primary_file`, `band`, `variable` | `files[].path` relative, no `..`. Multiple `DATA` files of one product (tiles) are mosaicked in lexicographic path order with seam checks ([09](09-DATA-INGESTION-AND-PROVENANCE.md) §6). `variable` selects a NetCDF/HDF variable. |
| `quantity`, `units` | What the numbers *mean*: `ELEVATION` (m or km), `RADIUS` (m or km; requires `reference_radius_m`), `TEMPERATURE_K`, `MINERAL_CLASS` (units `class`), `BAND_DEPTH`, `SLOPE_DEG` (pre-derived; allowed but flagged), `OTHER` (CONTEXT_ONLY only). |
| `scale_factor`, `offset`, `scale_already_applied` | Value = raw × `scale_factor` + `offset` applied **exactly once**. Set `scale_already_applied: true` when the reader already applies it (GDAL honors GeoTIFF/PDS3/PDS4 scale/offset metadata). The validator detects double application by comparing declared and GDAL-reported scale/offset and fails with `SCALE_DOUBLE_APPLICATION_RISK` when ambiguous. |
| `nodata_value` | Required unless the format carries a nodata value the reader reports; masks are never inferred from value 0. |
| `vertical_reference`, `reference_radius_m` | Free text identity of the vertical surface (`EGM96 geoid`, `Mars areoid`, `1737400 m lunar reference sphere`, …). Required. For `RADIUS` quantity, relative height = radius − `reference_radius_m`, once. |
| `crs` | `epsg` (Earth only) **or** `wkt` (required for Moon/Mars). Exactly one. |
| `longitude_convention`, `longitude_direction`, `latitude_type`, `pixel_registration` | Preserved in the normalized asset metadata. `PROJECTED` is allowed when the CRS is projected. Unknown registration is allowed but recorded; it blocks only sub-pixel control-point claims. |
| `declared_native_resolution_m` | Human-declared posting for cross-checking against the GDAL transform (difference > 5 % ⇒ validation `WARN`; > 50 % ⇒ `FAIL`). |
| `acquisition`, `product_identity`, `license_note`, `citation` | Provenance. `license_note` and `citation` are mandatory (they appear in the passport). `product_identity.source_url` must be a stable URL, never signed or token-bearing. |

### Example 1 — Earth terrain tile set (NASADEM-like `.hgt`)

```yaml
manifest_version: "1.0"
dataset_id: nasadem-example-tiles
title: NASADEM merged elevation, 1 arc-second tiles (example layout)
provider: NASA LP DAAC
is_synthetic: false
body: EARTH
role: EARTH_TERRAIN
format: HGT
files:
  - {path: N36W112.hgt, role: DATA}
  - {path: N36W111.hgt, role: DATA}
primary_file: N36W112.hgt
quantity: ELEVATION
units: m
nodata_value: -32768
vertical_reference: EGM96 geoid
crs: {epsg: 4326}
longitude_convention: NEG180_180
latitude_type: GEODETIC
pixel_registration: CENTER
declared_native_resolution_m: 30
product_identity: {product_id: NASADEM_HGT, version: "001", source_url: "https://doi.org/10.5067/MEASURES/NASADEM/NASADEM_HGT.001"}
license_note: NASA open data; cite per LP DAAC guidance.
citation: NASA JPL (2020). NASADEM Merged DEM Global 1 arc second V001. NASA EOSDIS LP DAAC.
```

### Example 2 — Lunar terrain as radius (LOLA-like PDS image)

```yaml
manifest_version: "1.0"
dataset_id: lola-example-region
title: LOLA gridded data record, regional crop (example layout)
provider: NASA PDS Geosciences Node
is_synthetic: false
body: MOON
role: TARGET_TERRAIN
format: PDS3_IMG
files:
  - {path: LDEM_example.lbl, role: LABEL}
  - {path: LDEM_example.img, role: DATA}
primary_file: LDEM_example.img
quantity: RADIUS
units: km
reference_radius_m: 1737400
scale_already_applied: true
nodata_value: null
vertical_reference: Lunar reference sphere radius 1737.4 km
crs: {wkt: 'GEOGCS["Moon 2000",DATUM["D_Moon_2000",SPHEROID["Moon_2000_IAU_IAG",1737400,0]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]'}
longitude_convention: ZERO_360
longitude_direction: POSITIVE_EAST
latitude_type: PLANETOCENTRIC
pixel_registration: CENTER
product_identity: {product_id: LRO-L-LOLA-4-GDR-V1.0, version: "1.0"}
license_note: NASA PDS open data.
citation: Smith, D. E. et al. LRO LOLA Gridded Data Record. NASA PDS Geosciences Node.
```

### Example 3 — Mars terrain (MOLA-like)

```yaml
manifest_version: "1.0"
dataset_id: mola-example-region
title: MOLA MEGDR topography, regional crop (example layout)
provider: NASA PDS Geosciences Node
is_synthetic: false
body: MARS
role: TARGET_TERRAIN
format: GEOTIFF
files: [{path: mola_example.tif, role: DATA}]
primary_file: mola_example.tif
quantity: ELEVATION
units: m
nodata_value: -32768
vertical_reference: Mars areoid
crs: {wkt: 'GEOGCS["Mars 2000",DATUM["D_Mars_2000",SPHEROID["Mars_2000_IAU_IAG",3396190,169.8944472]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]'}
longitude_convention: ZERO_360
latitude_type: PLANETOCENTRIC
product_identity: {product_id: MGS-M-MOLA-5-MEGDR-L3-V1.0}
license_note: NASA PDS open data.
citation: Smith, D. E. et al. MGS MOLA MEGDR. NASA PDS Geosciences Node.
```

### Example 4 — Earth mineral (EMIT-like categorical) and Example 5 — lunar thermal (Diviner-like)

```yaml
manifest_version: "1.0"
dataset_id: emit-example-minerals
title: EMIT L2B estimated mineral identification (example layout)
provider: NASA LP DAAC
is_synthetic: false
body: EARTH
role: EARTH_MINERAL
format: NETCDF
files: [{path: EMIT_L2B_MIN_example.nc, role: DATA}]
primary_file: EMIT_L2B_MIN_example.nc
variable: mineral_metadata/group_1_mineral_id
quantity: MINERAL_CLASS
units: class
nodata_value: -9999
vertical_reference: not applicable
crs: {epsg: 4326}
longitude_convention: NEG180_180
latitude_type: GEODETIC
declared_native_resolution_m: 60
product_identity: {product_id: EMITL2BMIN, version: "001"}
license_note: NASA open data.
citation: NASA EMIT L2B Estimated Mineral Identification and Band Depth V001. LP DAAC.
```

```yaml
manifest_version: "1.0"
dataset_id: diviner-example-tmin
title: Diviner polar cumulative minimum bolometric temperature (example layout)
provider: NASA PDS Geosciences Node
is_synthetic: false
body: MOON
role: LUNAR_THERMAL
format: GEOTIFF
files: [{path: diviner_tmin_example.tif, role: DATA}]
primary_file: diviner_tmin_example.tif
quantity: TEMPERATURE_K
units: K
nodata_value: 0
vertical_reference: not applicable
crs: {wkt: 'PROJCS["Moon South Polar Stereographic",GEOGCS["Moon 2000",DATUM["D_Moon_2000",SPHEROID["Moon_2000_IAU_IAG",1737400,0]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]],PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1]]'}
longitude_convention: PROJECTED
latitude_type: PLANETOCENTRIC
acquisition: {description: multi-year cumulative minimum}
license_note: NASA PDS open data.
citation: Paige, D. A. et al. LRO Diviner global cumulative products. NASA PDS Geosciences Node.
```

These examples show *shape and semantics*; granule names, versions and WKT must come from the real product's label. Never copy example values into a real manifest without checking the product label.

## 3. Operator commands (implemented by Tanush's CLI; science by Ayan's `INGEST_LOCAL_DATASET`)

```bash
analogforge datasets list                              # every incoming/<id> with validation state
analogforge datasets validate <dataset_id> [--write-checksums]   # manifest + file + semantic checks; exit 1 on FAIL
analogforge datasets lock --policy-id live-hackathon-policy-v1 --datasets <id> [<id> ...]
analogforge scenario bind live-hackathon-v1 --target-terrain <id> --earth-terrain <id> \
        [--earth-mineral <id>] [--lunar-thermal <id>]
analogforge preflight --mode live --scenario live-hackathon-v1 --output data/preflight-live.json
analogforge datasets generate-practice                 # writes the practice datasets of 40 into incoming/
analogforge datasets generate-mock-nasa-drop           # writes the mock NASA drop of 39 §5 into incoming/
```

* `validate` runs `INGEST_LOCAL_DATASET` in a CLI `LocalScienceContext`, prints each `ValidationCheck`, and exits non-zero on any `FAIL`. `WARN` is allowed and recorded.
* `lock` refuses datasets whose last validation was not `PASS`/`WARN`-only, and writes `data/locks/<policy_id>.json` (below). The file is the **source-policy lock** referenced by `dataset_lock_id` on `POST /runs`.
* `bind` edits the named scenario in `config/scenarios.yaml` (Tanush-owned; value-only change), sets `status: AVAILABLE` only if the lock exists and its datasets cover the roles the scenario's mission requires; otherwise leaves `AWAITING_DATASETS` and prints why.

Lock file shape (the platform pins `policy_sha256` = `canonical_sha256` of the object without that key):

```json
{
  "schema_version": "1.0",
  "policy_id": "live-hackathon-policy-v1",
  "policy_sha256": null,
  "created_at": "2026-11-05T00:00:00Z",
  "allow_network": false,
  "datasets": [
    {
      "dataset_id": "example-dataset",
      "role": "EARTH_TERRAIN",
      "body": "EARTH",
      "manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "files": [{"path": "example.tif", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "size_bytes": 1}],
      "validation": "PASS",
      "usable_for_quantitative_claims": true
    }
  ]
}
```

(`policy_sha256` is `null` in the template and filled when written; the example hashes above are placeholders, not evidence.)

## 4. Validation checks (`ValidationCheck.check_id`)

`INGEST_LOCAL_DATASET` must implement at least these checks, each `PASS`/`WARN`/`FAIL` with a message naming the file/field:

| check_id | FAIL when |
| --- | --- |
| `manifest_schema` | manifest does not parse/validate |
| `files_present` | a listed file is missing, outside the dataset dir, a symlink escaping it, or exceeds `MAX_DOWNLOAD_BYTES` |
| `checksums` | a recorded `sha256` differs from the file |
| `format_readable` | the declared format cannot be opened by GDAL/netCDF/ASCII reader, or an archive has traversal/expansion/nested members |
| `html_login_page` | a "data" file begins with `<html`/`<!DOCTYPE` (an auth/error page saved as data) |
| `crs_resolved` | CRS cannot be parsed, or contradicts `body` (Earth EPSG on a Moon/Mars body or vice versa) |
| `body_consistent` | the CRS ellipsoid radius is inconsistent with `body` (> 1 % off the body's mean radius) |
| `units_and_quantity` | `RADIUS`/`ELEVATION` magnitudes are physically absurd for the declared unit (e.g. 1.7e6 declared `km`) |
| `scale_offset_once` | scale/offset ambiguity (§2); the check records the single transformation it applied |
| `nodata_declared` | no nodata declared/readable and the raster contains the sentinel values −32768, −9999 or all-zero border rows |
| `transform_sane` | non-invertible or rotated transform that the normalizer does not support; positive y pixel size (flip is handled explicitly) |
| `resolution_cross_check` | declared vs GDAL-derived posting differ > 50 % (FAIL) or > 5 % (WARN) |
| `valid_fraction` | valid fraction < 0.05 (FAIL), < 0.5 (WARN) |
| `longitude_convention` | longitude range in the raster contradicts the declared convention |
| `lineage_fields` | `license_note`/`citation` empty |

`usable_for_quantitative_claims` is `true` only if every check above passed with at most the `WARN`s listed as non-blocking (`resolution_cross_check`, `valid_fraction` at 0.05–0.5, `pixel_registration=UNKNOWN`). If `false` the dataset may be previewed but every requirement depending on it is `UNKNOWN` (reason `METADATA_INCOMPLETE`), never PASS/FAIL.

## 5. How roles are consumed

| Role | Consumed by | If no dataset has the role |
| --- | --- | --- |
| `TARGET_TERRAIN` | `CHARACTERIZE_TARGET`; target histogram for screening | run blocks at `CHARACTERIZING` with `NO_COVERAGE`; affected requirements `UNKNOWN`; unrelated work continues |
| `EARTH_TERRAIN` | `SCREEN_CANDIDATES`, `ANALYZE_CANDIDATE`, route graph | discovery cannot run; `empty-state[data-reason=NO_COVERAGE]`; passport still publishes a limited report |
| `EARTH_MINERAL` | mineral requirements | mineral rows `UNKNOWN / EARTH_EVIDENCE_MISSING` |
| `LUNAR_THERMAL` | thermal requirements (Moon) | thermal rows `UNKNOWN / EARTH_EVIDENCE_MISSING` or `TARGET_EVIDENCE_MISSING` |
| `CONTEXT_ONLY` | display layers only | n/a — never evidence |

## 6. Window grid for dataset-backed discovery

For `earth_source.kind = LOCAL_DATASET`, `SCREEN_CANDIDATES` generates a deterministic window grid across the dataset's valid bbox: window edge = `grid.window_cells × analysis cell size` (defaults `64 × 60 m`), step = window edge (no overlap), row-major from the **north-west**, ids `grid-r<row>c<col>`, cap `coarse_windows_max` (30 default; the practice grid has 9). A dataset smaller than one window yields one window covering it. User nominations (`NOMINATE_CANDIDATE`) analyze the nominated AOI directly. Windows overlapping `known_analog` entries of the reference set are `KNOWN_ANALOG`; others `NOT_IN_REFERENCE_LIST` — never "new discovery".

## 7. Integrity at run time

Before every read of an `incoming/` file the platform's `ScienceContext.local_dataset_root` re-verifies the file hashes against the lock; a mismatch raises a named error and the dependent work becomes `BLOCKED` with `SOURCE_CHECKSUM_MISMATCH` (quarantine; no scientific FAIL). Datasets are never executed, imported or interpreted as code. Free-text manifest fields are untrusted data for prompts ([24](24-SECURITY-IDENTITY-AND-DATA-POLICY.md)).

## 8. Data is not assumed to be NASADEM/MOLA/LOLA

The slot is format- and product-agnostic. Whatever NASA supplies is described by role + quantity + units + CRS. If the supplied product is imagery or a quantity the application has no role for, the correct outcome is `CONTEXT_ONLY` plus a clearly worded `UNKNOWN`, **not** a silent reinterpretation as elevation ([37](37-HACKATHON-DAY-RUNBOOK.md) §4 lists the decision tree).
