# Dataset catalog and scientific access contracts

Read [00-ARCHITECTURE-DECISIONS.md](00-ARCHITECTURE-DECISIONS.md) first. This document specifies required adapters and what each source can establish. It does not certify any downloaded granule: no granules were downloaded or inspected while writing this blueprint. Product availability and exact identifiers must pass [21-CONFIGURATION-AND-PREFLIGHT.md](21-CONFIGURATION-AND-PREFLIGHT.md). Official documentation was checked on November 3, 2026.

## 1. Registry rather than hardcoded URLs

Implement `science/datasets/registry.py`. Each adapter registers `adapter_id`, version, body, provider, discovery method, supported product families, official documentation URLs, authentication method, expected metadata, decoder, quality-mask builder, and permitted claim types. A registry entry is a proposed source; a `DatasetAsset` is a real, downloaded, checksummed source. Never present registry coverage as acquired evidence.

Initial registry keys are application identifiers, not provider collection IDs:

| Adapter ID | Source selector | Required behavior |
|---|---|---|
| `earth_nasadem_hgt_v001` | CMR short name `NASADEM_HGT`, version `001` | Primary Earth terrain adapter |
| `earth_srtmgl1_v003` | CMR short name `SRTMGL1`, version `003` | Explicit alternate Earth adapter; never silently substituted |
| `mars_mola_megdr` | Maintained PDS MOLA topography derived bundle; MEGDR topography plus counts | Regional Mars terrain characterization |
| `moon_lola_gdr` | Maintained PDS LOLA derived archive, GDR products | Lunar terrain characterization at product-specific scale |
| `earth_emit_l2bmin_v001` | CMR short name `EMITL2BMIN`, version `001` | Earth mineral-context adapter with quality and coverage states |
| `moon_diviner_derived` | PDS Diviner derived products selected by science variable | Lunar thermal-context adapter |
| `earth_user_survey` | User-uploaded GeoTIFF plus metadata and provenance | Optional higher-resolution Earth evidence; distinct from NASA evidence |

The provider's allowed collection/family and exact version belong in the immutable source-policy lock; actual acquired product/granule IDs, download identities, publication revisions, and checksums belong in immutable seed-asset records or the append-only per-run acquired-asset manifest. This distinction permits bounded discovery to acquire previously permitted granules during a run without changing its source policy. Do not copy a CMR concept ID from a search result and assume it remains authoritative. Resolve the selector, verify collection title/DOI/version, then lock the policy and actual seed assets.

## 2. NASADEM: Earth terrain, not wheel-contact geometry

The NASADEM merged elevation product is distributed at one arc-second posting. The product documentation specifies tile encoding, height datum, and auxiliary source codes. Preserve the merged height's EGM96 geoid reference, WGS84 horizontal reference, source classification, and water mask. Its radar-based origins and merging mean that its surface cannot automatically be treated as surveyed bare ground. Read the [NASADEM product record](https://doi.org/10.5067/MEASURES/NASADEM/NASADEM_HGT.001) and [January 2025 user guide](https://lpdaac.usgs.gov/documents/2237/NASADEM_User_Guide_V13.pdf).

Use source metadata for exact footprint; the initial discovery filter can exclude latitudes beyond approximately 60° N and 56° S before requesting granules. Do not offer Icelandic or polar NASADEM terrain merely because a named analog is famous. One arc-second is angular spacing, approximately 31 m north–south near the equator, not globally square 30 m pixels and not equivalent to independent 30 m measurement resolution.

Required decoder checks:

1. Locate and retain all archive members and provider metadata. Reject archive path traversal, excessive expansion, or unexpected files; ingestion details are in [09](09-DATA-INGESTION-AND-PROVENANCE.md).
2. Decode the selected height member according to documented byte order, shape, units, and sample registration. Do not infer height type from filename alone.
3. Distinguish height, source/NUM, and water arrays. NUM is a coded provenance indicator with different ranges; it is not a per-pixel meter uncertainty and must not be divided by 100 to manufacture one.
4. Mask nodata before numerical transformations. Water is excluded from terrestrial rover test zones even if its height is numerically valid.
5. Validate adjoining degree-tile shared borders; deduplicate shared samples during mosaic construction.
6. Record source-dependent effective support and uncertainty limitations. Interpolated fill can remain available for display while failing the contract's evidence-quality gate.

Permitted claims: regional relief, broad terrain slope distribution, detrended relief at stated support, modeled terrain-route feasibility. Unsupported claims: 20 cm clearance, 30 cm wheel contact, rock distribution, soil bearing strength, wheel slip, actual obstacle avoidance, autonomous navigation performance, sample mineral identity. The latter remain `UNKNOWN` unless separate adequate evidence is supplied.

Earthdata catalog search and file download are different operations. Public CMR metadata discovery generally needs no token; protected file download can require Earthdata Login. A generic `NASA_API_KEY` does not unlock these products. Use [20-CREDENTIALS-AND-EXTERNAL-SERVICES.md](20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) for actual credential configuration.

## 3. SRTM alternate and source independence

SRTMGL1 V003 is a separate supported selector, documented in NASA's [SRTM product guide](https://www.earthdata.nasa.gov/s3fs-public/2025-05/SRTM_Quick_Guide.pdf). It can support the same broad terrain calculations after its own metadata checks. An unavailable NASADEM tile may prompt an explicit SRTM analysis revision if that alternate is already permitted by the run's source-policy lock; otherwise a new policy and run are required. This changes source IDs, checksums, provenance, derived metrics, and qualification revision. Recompute; do not leave NASADEM labels attached.

NASADEM and SRTM are related. Agreement between them is a processing consistency check, not two independent observations proving accuracy. A comparison that includes a NASADEM fill source and that same source as the supposed independent reference must report dependence.

## 4. MOLA: mandatory Mars regional context

Use MEGDR topography, not planetary radius mislabeled elevation, with the matching observation-count product. The official node documents a maintained PDS4 archive introduced in August 2026. The 128-pixel-per-degree collection is currently described by `urn:nasa:pds:mgs_mola_topography_derived:data_meg128::1.0`; this is a discovery seed, not a validated local asset. Lock the actual collection/product LIDVID and label after download. See [MOLA MEGDR archive](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html) and [PDS collection record](https://pds.nasa.gov/ds-view/pds/viewCollection.jsp?identifier=urn%3Anasa%3Apds%3Amgs_mola_topography_derived%3Adata_meg128).

At 128 pixels per degree, equatorial spacing is about 463 m using a Mars radius near 3,396 km. The calculation is `2*pi*R/(360*128)`; exact scale comes from the product geometry. Denser posting can include interpolation between tracks, as described by [Mars ODE MOLA documentation](https://ode.rsl.wustl.edu/mars/pagehelp/Content/Missions_Instruments/MGS/MOLA/Intro.htm). Therefore this adapter establishes kilometer-scale terrain context and scale-labeled slopes. It cannot establish the 8–18° slopes encountered by a wheel or a meter-scale rover.

Inputs include detached label, image, counts, and available projection/header documentation. Verify byte order, scaling, nodata, longitude domain, positive-east/positive-west convention, latitude definition, areoid/radius interpretation, projection, and cell centers. Preserve counts as observational support, not as an automatically calibrated confidence probability. Zero-count interpolated cells require a policy decision recorded in the analysis manifest.

The first Mars scenario has two honest layers: target regional terrain comparison at common support, and Earth modeled terrain exposure at Earth DEM support. The UI and passport must not imply the regional target measurements directly established the rover test's fine-scale stresses. Fine-scale mission bands are accepted engineering assumptions unless a higher-resolution planetary source supports them.

## 5. LOLA: mandatory Moon adapter

Discover products through the [PDS LOLA archive](https://pds-geosciences.wustl.edu/missions/lro/lola.htm). Prefer the maintained product labels rather than guessing an old directory from a blog. Global, polar, and regional grids are different products with different posting, coverage, interpolation, and frame metadata. A polar grid is not evidence for an arbitrary lunar target.

LOLA decoding must distinguish center-to-surface radius from height relative to a reference sphere. The [LOLA FAQ](https://pds-geosciences.wustl.edu/missions/lro/lola_faq.htm) documents scaling and offset for legacy GDR images. Apply the current selected product's label once, retain that transformation, and subtract its documented reference radius only when constructing relative elevation. Reading raw integer samples directly as meters, or applying the scale twice through both GDAL and custom code, is a release-blocking error.

The adapter returns `NO_COVERAGE` for unsupported regional products, `UNSUPPORTED_FORMAT` for a product it cannot decode, and `METADATA_INCOMPLETE` for missing frame information. It must not substitute an Earth CRS to make a map appear. Moon terrain metrics use the source body's geometry and a body-specific projected grid; see [10](10-TERRAIN-AND-PLANETARY-COMPARISON.md).

## 6. EMIT: mineral context with explicit limits

The intended product is estimated mineral identification, band depth, and uncertainty at nominal 60 m sampling. Its source arrays are not an already orthorectified regular Earth map. Use the geolocation/geometric lookup information associated with the actual product and apply its quality masks. Consult the [EMIT L2BMIN record](https://doi.org/10.5067/EMIT/EMITL2BMIN.001), [product user guide](https://lpdaac.usgs.gov/documents/1660/EMITL2BMIN_User_Guide_V1.pdf), and [NASA EMIT data resources](https://github.com/nasa/EMIT-Data-Resources).

CMR granule intersection only proves a swath footprint overlaps the requested area. The adapter must then calculate valid mineral retrieval area after cloud, water, instrument, and retrieval masks supported by the product. Product extent is not continuous mineral coverage. Never interpret no identification as proof a mineral is absent without the documented retrieval semantics and detection limits.

Output includes mineral class identifiers and their product dictionary, valid-area fractions, uncertainty/band-depth fields where available, acquisition time, usable sampling, and restrictions. Mineral identities are categorical; use nearest-neighbor assignment or explicit area fractions, never bilinear interpolation of IDs. Band depth is not automatically mineral abundance, rock strength, or geological age. Earth mineral evidence alone does not establish a Mars mineral match: the target needs its own supported source. With MOLA alone, cross-world mineral qualification is `UNKNOWN`. A user-designated sampling waypoint remains a task location rather than a remotely proven collectible sample.

## 7. Diviner: thermal variable selection is part of science

The [PDS Diviner archive](https://pds-geosciences.wustl.edu/missions/lro/diviner.htm) includes multiple derived product families. The adapter chooses a variable and aggregation deliberately: brightness temperature, modeled/derived temperature, local-time statistics, and seasonal extrema are not interchangeable. The science team's [temperature data page](https://www.diviner.ucla.edu/data) supplies context and citations for global and polar maps.

Use kelvin internally. Retain latitude, longitude, frame, time/local-time/season support, observation counts, missing-value semantics, channel information where relevant, and the interpretation of extrema. Do not compare a lunar multi-year minimum to an Earth afternoon air temperature. A compatible Earth thermal adapter is not included in the required terrain sources; absent compatible Earth surface-temperature evidence, the thermal comparison remains `UNKNOWN`. Physical vacuum and gravity remain `GAP` regardless of any temperature match.

The initial adapter supports selected documented derived products only; arbitrary raw radiometer reduction is outside version 1. If an unsupported variable is requested, return the unsupported capability explicitly. Do not average thermal bands into a convenient new variable without a documented model.

## 8. User evidence and future adapters

The full product accepts user-survey Earth DEMs only with body, horizontal/vertical reference, units, acquisition time, cell support, validity mask, provenance, rights declaration, and stated uncertainty. These are labeled user data. A high-resolution filename cannot establish survey quality. Without metadata, permit preview but prohibit quantitative qualification.

CRISM, HiRISE/CTX stereo DTMs, HRSC, THEMIS, higher-resolution Earth surveys, and compatible Earth thermal records require new adapter contracts and validation cases. Do not add a raw image and call it elevation. Do not claim any future adapter is implemented because its product is listed here.

## 9. Required adapter acceptance

For every required adapter implement discovery, deterministic metadata parsing, fetch/cache, decode, geometry validation, quality masking, normalized asset output, and failure mapping. Acceptance requires one tiny real product/crop per adapter family where licensing and size permit, expected metadata assertions, checksum locking, and an offline replay fixture derived from the verified download. Secrets never enter fixtures.

Live terrain acceptance requires actual Earth NASADEM or explicitly selected SRTM, actual MOLA, and actual LOLA, with checked geometry and derived artifacts. EMIT and Diviner acceptance requires either a validated selected product or a correctly demonstrated no-coverage/unsupported state; those states do not count as mineral or thermal scientific success. Validation procedures are in [29-SCIENTIFIC-VALIDATION.md](29-SCIENTIFIC-VALIDATION.md).
