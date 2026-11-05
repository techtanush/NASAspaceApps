# Hackathon-day runbook: plugging in the NASA dataset

Assumes tier P and tier R are complete and merged ([34](34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md)). Goal: from "we have the NASA files" to "a real passport" in the shortest honest path. The operator (or one coding-agent session using the prompt in §7) performs these steps. **The dataset is the only new input; no contract, kit file, threshold or requirement changes.**

## 1. Receive and stage

1. Put each product in its own directory: `analogforge/data/incoming/<dataset_id>/` (lowercase, hyphens). Tiled products of one family go in one directory.
2. Do not rename inside archives; unpack archives into the directory (the validator rejects path traversal/nested archives).
3. Note, for each product, the provider's own product page/label/README — you will copy provenance from it.

## 2. Identify what each product *is*

For every product determine, from its label/metadata (not from its file name): **body**, **quantity** (elevation vs radius vs temperature vs class vs imagery), **units**, **CRS/projection and ellipsoid radius**, **longitude convention and direction**, **latitude type**, **nodata**, **scale/offset and whether the reader applies them**, **vertical reference**, **posting**, **acquisition**. Tools: `gdalinfo`, `rio info`, the PDS label, `ncdump -h`. Then use the decision tree:

| What the product is | Action |
| --- | --- |
| Earth elevation (DEM) | `role: EARTH_TERRAIN`, `quantity: ELEVATION` |
| Mars/Moon elevation or radius | `role: TARGET_TERRAIN`, `quantity: ELEVATION` or `RADIUS` (+`reference_radius_m`) |
| Earth categorical mineral map | `role: EARTH_MINERAL`, `quantity: MINERAL_CLASS` |
| Lunar surface temperature | `role: LUNAR_THERMAL`, `quantity: TEMPERATURE_K`, kelvin |
| Imagery, albedo, geology map, anything else | `role: CONTEXT_ONLY`, `quantity: OTHER`. It is display context. Requirements depending on it stay `UNKNOWN`. Do **not** reinterpret imagery as elevation. |
| A product that covers none of the mission's bodies/regions | bind nothing; the affected dimensions become `UNKNOWN / NO_COVERAGE` and the passport says so |

## 3. Write manifests

```bash
cd analogforge
analogforge datasets scaffold <dataset_id> --body <EARTH|MOON|MARS> --role <ROLE>   # drafts manifest.yaml
# open data/incoming/<dataset_id>/manifest.yaml, replace every TODO_FILL_IN from the product label, add citation/license
analogforge datasets validate <dataset_id> --write-checksums
```

`scaffold` fills what GDAL can read (format, CRS, transform, nodata, dtype, scale/offset, posting) and leaves provenance/vertical reference for a human. `validate` must end with every check `PASS` (a few `WARN`s are allowed, §[36](36-DATASET-PLUG-IN-AND-NASA-SLOT.md) §4). **Fix the manifest, never the check.**

Troubleshooting map:

| Validation message | Meaning / fix |
| --- | --- |
| `crs_resolved` FAIL | Label/WKT missing or Earth EPSG on a planetary body. Get the planetary WKT from the PDS label (`A_AXIS_RADIUS`, `B_AXIS_RADIUS`, `C_AXIS_RADIUS`, projection keywords). Never use EPSG:4326 for Moon/Mars. |
| `scale_offset_once` FAIL | Compare `gdalinfo` `Scale`/`Offset` with the label `SCALING_FACTOR`/`OFFSET`. If gdalinfo shows them, set `scale_already_applied: true` and leave `scale_factor/offset` at 1/0 (or equal to them). If it does not, put the label values in the manifest with `false`. |
| `units_and_quantity` FAIL | Values like `1.7e6` in `m` mean the file is *radius* (m) or km; set `quantity: RADIUS`, correct `units`, `reference_radius_m`. |
| `nodata_declared` FAIL | Read the label's missing-constant; set `nodata_value`. |
| `longitude_convention` FAIL | Raster spans 0–360 but manifest says −180–180 (or vice versa). |
| `html_login_page` / `format_readable` FAIL | You downloaded a login/error page. Re-download with Earthdata Login. |
| `resolution_cross_check` WARN | Declared posting disagrees with the transform; correct `declared_native_resolution_m`. |

## 4. Lock, bind, preflight

```bash
analogforge datasets lock --policy-id live-hackathon-policy-v1 --datasets <id1> <id2> ...
analogforge scenario bind live-hackathon-v1 --target-terrain <id> --earth-terrain <id> \
    [--earth-mineral <id>] [--lunar-thermal <id>]
analogforge preflight --mode live --scenario live-hackathon-v1 --output data/preflight-live.json
```

Expected: scenario `AVAILABLE`, lock `PASS`, `MODEL` pass, `SCIENCE` pass. Anything else is the exact remaining blocker. Synthetic datasets are rejected for `live-hackathon-v1` with `MODE_MISMATCH` — by design.

## 5. Run

1. `make dev` (or `docker compose up`), open the web app, **New mission**.
2. Enter the objective (or load the Mars/Moon example), choose the real target region **inside the bound target dataset's extent** (the target picker shows the dataset bbox), pick/upload the rover (ARES-1 or the team's), **Build Mission Fingerprint**, review every proposed threshold and assumption, **Accept**, choose scenario `live-hackathon-v1`, mode `live`, **Start**.
3. Watch Operations; at **AWAITING_REVIEW** inspect the qualification matrix, critic cards and evidence; select a candidate; **PROVE IT**.
4. Open the Passport; export HTML/JSON/CSV; note the manifest digest.

## 6. Honest-results rules for the day

* The outcome may be FAIL, UNKNOWN, INCONCLUSIVE or "no supported recommendation". That is a valid, presentable result. **Do not edit masks, waypoints, thresholds, energy parameters, the rover or the contract after seeing a result to get a pass.** A different assumption is a new accepted revision and a new run, shown as such.
* For the live demo's failure→replan story, use the real run if it produced one; otherwise present the **synthetic regression** (scenario `synthetic-graph-regression-v1` or `synthetic-mars-mobility-v1`) explicitly introduced as synthetic, or a labeled replay of an earlier real run.
* Missing mineral/thermal data stays `UNKNOWN`. Gravity/atmosphere/vacuum stay `GAP`. Coarse DEM never certifies 0.20 m clearance.
* "Candidate beyond the reference set" is the strongest novelty wording.

## 7. The one prompt for a hackathon-day coding-agent session

Use only if the operator wants an agent to do §2–§4:

```text
You are plugging the NASA-provided dataset into AnalogForge (repository root = this checkout, branch integration/rc or main).
Read architecture files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md, 37-HACKATHON-DAY-RUNBOOK.md and 38-RUNTIME-KEYS-AND-LOCAL-SETUP.md first.
The datasets are in analogforge/data/incoming/. For each, determine body/quantity/units/CRS/nodata/scale from its label (not its filename),
scaffold and complete manifest.yaml, run `analogforge datasets validate`, and fix manifests until every check passes.
Then lock, bind scenario live-hackathon-v1, run preflight and report exactly what remains.
You MAY NOT: edit anything under architecture files/contracts/kit, change any requirement/threshold/rover limit, add code paths for a specific dataset,
relabel imagery as elevation, label synthetic data as NASA, weaken any validator, or fabricate provenance.
If a product needs a decoder or format the science code lacks, STOP and report: format, label excerpt, and the smallest missing capability.
Finish by running `python3 "architecture files/contracts/kit/materialize.py" --verify` and the offline suites (`make check`), and print the preflight JSON.
```

## 8. Time budget (planning guide, not a promise)

| Step | Typical effort |
| --- | --- |
| Stage + identify | 5–15 min |
| Manifests + validate loop | 10–30 min per product family |
| Lock + bind + preflight | 2 min |
| First live run | 10–15 min active compute budget (cap 900 s) + review time |
| Passport + exports | 1–2 min |

## 9. Safeguards if something is unexpectedly missing

| Situation | Response |
| --- | --- |
| A needed GDAL driver/format is unsupported | STOP; report; the practice/mock-drop suites already cover GeoTIFF, COG, HGT, PDS3, PDS4 (GDAL), NetCDF, ASCII grid. For anything else convert once with `gdal_translate` to GeoTIFF **keeping a copy of the original and recording the conversion in `notes`** |
| Dataset larger than memory | No action: analysis is windowed (`MAX_RASTER_CELLS` per window); keep the target AOI/search extent inside the bound extent |
| Only an Earth DEM supplied (no Moon/Mars) | Bind `--earth-terrain` only; target dimensions are `UNKNOWN / NO_COVERAGE`; Earth-side qualification and PROVE IT still run; passport is `LIMITED` |
| Only Moon/Mars supplied (no Earth) | Target profile works; discovery blocked with `NO_COVERAGE`; passport `LIMITED`; nominate Earth AOIs only after an Earth DEM is bound |
| No OpenAI key at the event | `live` runs are unavailable by design. Use synthetic/replay for demos, clearly labeled |
