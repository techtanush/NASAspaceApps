# Local real-data rehearsal — 14 November 2026

This profile exercises real NASA terrain and a real model provider on one computer. It is a regional, terrain-only demonstration. Its proposed 5° Wasserstein-distance acceptance limit is an operator-reviewed demonstration constraint, not a universal scientific threshold. No rover experiment, physical validation, historical discovery, mineralogical match, or thermal match follows from it.

## Local services and private configuration

The validation checkout runs web `http://127.0.0.1:5200`, API `http://127.0.0.1:8020`, and a dedicated PostgreSQL/PostGIS instance on port 5440. Other checkouts and services are independent. These ports are local choices; the normal project defaults remain unchanged.

Credentials belong in ignored server-side `.env`, with restrictive file permissions. Live mode requires `OPENAI_API_KEY` and an explicit `OPENAI_MODEL`; the initial checks used `gpt-5.4-mini`. That model later reported zero remaining requests under its 50-request provider limit, so the subsequent rehearsal explicitly selected `gpt-4.1-mini` after verifying real strict serial tool calling. The final local configuration explicitly selects `gpt-5.4`, also checked with a real strict serial call, after a passport-review request returned `PROVIDER_RATE_LIMITED`. Availability of a small request does not establish capacity for a full role request. Select an available model explicitly; the app does not silently change providers or models. It also requires the real science and renderer implementations. Never place credentials in browser settings, frontend environment variables, fixtures, screenshots, Git, or a shared command transcript. Actual live services must have fake-provider and test-harness hooks disabled.

`CONFIG_DIR` points at an ignored copy of `config/` for this rehearsal. Keep the canonical configuration unchanged. Set top-level `live_terrain_support_m: 500` in the operator copy of `algorithms.yaml` and configure the generated search region to 24 cells at 500 m: 12 km candidate windows. Leave the base grid and measurement support values unchanged so that synthetic practice still uses its original 60 m Earth grid. The live setting requests a minimum support scale; coarser native terrain is never upsampled. The generated region must have no synthetic negative controls. Use an explicitly empty, unreviewed reference set; absence from that set establishes no historical novelty. Keep validity thresholds, scientific rules, and resource budgets unchanged. The actual configuration digest is pinned when a run starts.

The live preflight requires at least **10 GiB free**. Preserve this guard. `make test-live` runs one opt-in, real readiness test and reports missing credentials as `BLOCKED_EXTERNAL`; it does not substitute for a complete browser investigation.

Live requests use a reversible model-facing representation: repeated audit values become catalogs, homogeneous records become column tables, and client-owned aliases replace long identifiers. Every finding, gate outcome, scope, null, and evidence link remains reconstructible. The canonical task, tool results, stored evidence and publication validators retain authority; aliases are decoded before validation and are never published as evidence IDs. Unknown aliases and unauthorized evidence remain invalid. The adapter requires serial tool calls, caps output at 4,096 tokens, and retains the existing request/correction budgets. Short provider cooldowns are honored for at most 60 seconds per retry; oversized requests remain controlled failures, never truncated reports.

Input token counting alone does not prove rate-limit admission. The observed provider reservation included 367 tokens beyond the token-count endpoint's input result: a 9,664-input request was rejected for requesting 10,031 against a 10,000 TPM limit. This observed overhead is diagnostic, not a universal constant to hardcode. Measure the initial request and cumulative read-tool follow-ups, retain headroom for new receipts and corrections, and verify an actual complete run. No quota, billing or scientific threshold was changed for this rehearsal. A larger investigation can still exceed the configured account's capacity and must remain honestly blocked until its context or external capacity is addressed.

## Earth source: NASADEM through Microsoft Planetary Computer

- Collection `nasadem`, granule `NASADEM_HGT_n35w112`, product NASADEM HGT version 001.
- Stable unsigned asset: <https://nasademeuwest.blob.core.windows.net/nasadem-cog/v001/NASADEM_HGT_n35w112.tif>.
- Original source SHA-256: `cadd538384ed3d007c46e934523818d8d814b6676dcffd52ec9e2cbe41b54564`.
- The local `nasadem-flagstaff-v002` subset covers approximately `[-111.65, 35.25, -111.35, 35.55]`. Its zero-based native-pixel window is column offset 1260, row offset 1620, width 1081, height 1081; it preserves the native posting without resampling. Original source and STAC metadata remain recorded in its provenance. The validated local terrain file has SHA-256 `233057278b302fdbac5312d93e3cbe4e5a00e0107d4144292b4fe2f6f5335bc0`.
- Merged integer elevations use the EGM96 geoid; nominal posting is approximately 30 m. They are void-filled terrain data, not obstacle measurements or contemporary field validation.
- NASA/JPL produces the data; Microsoft hosts this catalog asset. Planetary Computer is an Earth-data source and does not supply the Mars target. Preserve the recorded source licensing notices and citations rather than inventing redistribution rights or NASA endorsement.

Planetary Computer asset signing may be required to download the original. Obtain short-lived signing material only when needed; preserve the unsigned URI in provenance and never persist a signed URL in a manifest. See the [Planetary Computer signing documentation](https://planetarycomputer.microsoft.com/docs/concepts/sas/) and [NASA's NASADEM user guide](https://lpdaac.usgs.gov/documents/2237/NASADEM_User_Guide_V13.pdf).

## Mars source: MOLA MEGDR and explicit frame preparation

The source is NASA PDS product `MGS-M-MOLA-5-MEGDR-L3-V1.0`, product version 2.0, granule `MEGT00N090HB.IMG`, with its original PDS3 and PDS4 labels:

<https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg128/megt00n090hb.img>

Original source SHA-256: `764946162d4c650abfb22aa284595a15374a7185f302a639c19e6602c67a1d6e`.

MOLA's source map sphere is 3,396,000 m; the app's supported Mars analysis sphere is 3,396,190 m. PDS also documents the rounded `MAP_SCALE` and pixel-origin problem. A source can be on the correct planet while requiring explicit analysis-frame preparation. Intake must reject unsupported quantitative frames early; do not relax the body-geometry guard or overwrite a CRS label to make the source pass.

The offline [preparation utility](scripts/data/prepare_mola_analysis.py) verifies the raw source hash and parent labels, reconstructs precise 128-pixel/degree coordinates from the documented source corners, and executes an explicit coordinate warp into a congruent canonical Mars grid. It checks that elevations and nodata do not change. Original angular posting is approximately 463.057667 m on the source map sphere; the corresponding canonical map posting is approximately 463.083574 m. Neither posting is a claim of effective measurement resolution. Elevations retain their MOLA GMM-3 degree/order 50 areoid reference; no vertical transformation or new observations are introduced.

For the existing local acquisition, reproduce into a **new** output directory and dataset ID:

```bash
uv run python scripts/data/prepare_mola_analysis.py \
  --source-image data/source-cache/MEGT00N090HB.IMG \
  --source-label data/incoming/mola-gale-v2/source-pds3.lbl \
  --pds4-label data/incoming/mola-gale-v2/source-pds4.xml \
  --parent-dataset data/incoming/mola-gale-v2 \
  --expected-source-sha256 764946162d4c650abfb22aa284595a15374a7185f302a639c19e6602c67a1d6e \
  --bbox 137.2 -5.0 137.6 -4.6 \
  --dataset-id mola-gale-new \
  --output-dir data/incoming/mola-gale-new
```

The utility requires an existing verified acquisition and refuses to overwrite a dataset. For a new acquisition, retain the raw IMG, labels, unsigned source URI, source checksum, citation, height reference, and derivation metadata following architecture document 36. See the [PDS georeferencing guidance](https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/extras/mola_envi.htm).

## Validate, lock, bind, and run

Validate both datasets with `analogforge datasets validate <dataset-id>`. Create a fresh policy with `analogforge datasets lock --policy-id <new-policy-id> --datasets <mars-id> <earth-id>`, then bind it with `analogforge scenario bind live-hackathon-v1 --target-terrain <mars-id> --earth-terrain <earth-id> --policy-id <new-policy-id>`. Apply these commands to the intended isolated `CONFIG_DIR`. Never edit an existing lock or modify its dataset files. Start a new run when changing the source policy.

The checked local policy is `live-earth-mars-20261114-v3`, binding `mola-gale-v3` and `nasadem-flagstaff-v002`, with lock SHA-256 `866fde89c1f2cd79a65e7a7c0085d1ac9dc3476a47b5c00a4bc6da67e7721539`. Earlier failed rehearsal runs and dataset versions remain historical records; they are not successful demonstrations.

In the workbench, select the live scenario and **LIVE** mode. Use custom Mars bounds `[137.25, -4.95, 137.55, -4.65]`, planetocentric latitude, positive-east longitudes, and the documented MOLA areoid height reference. Review the proposed terrain requirement and its exact 500 m minimum and maximum support before accepting. A custom target's height reference starts as `Unknown`; source evidence must establish it.

Check target measurements, candidate provenance, qualification rows, gaps, assurance, and final passport exports. No rover is supplied for this regional demonstration, so route verification remains unavailable. Verify all downloaded bytes against the published artifact digests. A failed or blocked run must remain visibly failed or blocked; do not rewrite history or substitute synthetic results.

## Explicit operator criteria and review outcomes

The [example draft](examples/live-regional-terrain-draft.json) supplies a single terrain requirement at exactly the same 5° Wasserstein-1 limit and 500 m support used above. Its `USER` origin means the criterion is supplied as an input by the local rehearsal operator; it does not mean NASA established or scientifically calibrated it. The limitations are part of the accepted draft. The example contains public geometry and demonstration criteria, with no credentials or raster data.

Create a new mission through the normal local API with this file as the `POST /api/v1/missions` body, `Content-Type: application/json`, and a fresh `Idempotency-Key`. Open the returned mission in the workbench with `?scenario=live-hackathon-v1`, select LIVE, build the fingerprint, review the exact proposed revision, accept it, and start the run. The real provider must preserve the supplied requirements, assumptions, and target. This path tests explicit criteria independently of inferred proposal review.

An earlier objective-only proposal was formally accepted but the model still stopped to question its proposed-threshold provenance. Preserve such stopped runs and their summaries as outcomes; never relabel them as completed demonstrations or silently alter their accepted contract. An operator may supply clarified criteria in a new draft/run. Provider limits and missing data are also honest blocking conditions. Neither model completion nor formal operator acceptance is scientific validation.

## Completed local rehearsal

The real-data run `d30ed2f9-3474-401a-933e-9b60af09e782` reached `COMPLETED` on 14 November 2026 after recorded debugging retries, using the real science engine, renderer, NASADEM/MOLA sources and explicitly selected `gpt-5.4`. Its final provider review succeeded with the existing 10,000-token-per-minute limit. No quota or billing change was made. Earlier blocked attempts remain part of its history; completion does not make those attempts successful.

The accepted mission revision is `1bd2e6f3-b917-45c3-a923-862868e8cd55`, with contract digest `6e6cddbe0f885f3f0953909a2036634ad9fe7c6b0beeba3397e4700b6ed4983b`. The pinned candidate order and nominal Wasserstein-1 slope distances are:

| Candidate | Distance | Support | Requirement outcome |
| --- | ---: | ---: | --- |
| `grid-r1c0` | 2.9065566378° | 500 m | PASS |
| `grid-r1c1` | 3.6823164683° | 500 m | PASS |
| `grid-r0c0` | 5.7223402860° | 500 m | FAIL |
| `grid-r0c1` | 6.5384559885° | 500 m | FAIL |

The final passport carries `LIMITED` assurance and manifest digest `f4aa8604d2d84cbd3b016737d6ca3676cefad86248ad1742f457fb0cb9d91b73`. The two failures remain visible. This is a regional qualification report at the accepted operator-supplied 5° limit, with rover compatibility `NOT_ASSESSED` and verification `NOT_RUN`; it establishes neither field validation nor universal site suitability. Open `/runs/d30ed2f9-3474-401a-933e-9b60af09e782/passport` on the local web service to inspect it. All three immutable exports returned HTTP 200; their exact bytes matched their SHA-256 headers and ETags, and an independent RFC 8785 digest check matched the published manifest. The report also survived a full Comet reload and a native JSON download. Local HTML/JSON/CSV bytes and their digest-verification receipts belong under ignored `out/`, alongside the native Comet screenshots, rather than in the source repository.

## Weather and verification boundaries

Meteomatics uses the supplied username/password through HTTP Basic authentication; a separate API key is not needed for that API. Access and a Flagstaff weather query were checked. Weather remains optional Earth context in this build, outside the qualification evidence pipeline. A current forecast does not establish climatic analogy, Mars temperature behavior, or long-term site suitability.

`make check` covers the offline merged suite and build. Real-backend browser journeys, three mutation gates, and the real live readiness check are separate. Run synthetic browser verification in an isolated database/configuration without model credentials; any J13 test-harness binding belongs only there. Keep actual live verification free of test hooks. Local receipts and acquisition metadata belong under ignored `out/` and `data/`; large source rasters, credentials, database files, and temporary profiles must remain outside Git.

The final local release verification on 14 November 2026 passed 1,994 tests, all 17 real-backend browser journeys, and all 72 mutation checks (20 platform, 16 science, 36 UI), including their passing baselines. All five gate receipts recorded the same unchanged application/test fingerprint, `a005f3df14ea226e33dffacaab7cb913e352dcd9b2339d06bc26d7b0c783e4bb`. These isolated browser regressions are separate from the genuine LIVE rehearsal described above. The live rehearsal, export integrity checks, and native Comet inspection provide additional evidence; none replaces scientific or field validation.
