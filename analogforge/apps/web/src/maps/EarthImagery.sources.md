# Earth regional visual context — source verification

Verified on 2026-11-14. This is a display-source receipt, not scientific qualification evidence. No image enters terrain measurements, route verification, matching, weather inference or passport claims.

## Close inspection: public USGS aerial layer

Production Earth maps prefer USDA / USGS The National Map Imagery Only for eligible local continental-US footprints (conservative geographic source-selection bounds −125 to −66 longitude, 25 to 49 latitude). This preference selects a display provider; it never selects, ranks or qualifies a candidate. Other footprints retain global EOX. A source selector exposes the global layer for wider context or explicit recovery after an unavailable aerial tile. Both remain historical imagery, not live video or terrain measurements.

The [official service metadata](https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer?f=pjson) identifies EPSG:3857, 256-pixel tiles, mostly NAIP aerial inputs for the continental United States, source dates 2017–2021, nominal 1 m input, and a service refresh in June 2024. It advertises maximum scale 1:9,028, corresponding to source level 16. Date and resolving power vary by location. Global overview imagery is coarser; Alaska SPOT has separate license restrictions. The app does not claim global aerial coverage or universal public-domain rights.

A bounded public request at 35.42° N, 111.5° W verified level 16 / row 25865 / column 12470: HTTP 200, JPEG, CORS *, 24,945 bytes, SHA-256 `c0a36fd05245129d96ede59d21a97d86f6b61961aed5b0b6859f352a91d01ea3`. Its level-17 child returned HTTP 404 HTML. Therefore source zoom stops at 16 and camera zoom at 15. Approximate ground sampling is 1.95 m/pixel near this footprint, eight times finer than EOX level 13; sampling does not guarantee resolved features of the same size.

The native large-display rehearsal exhausted the former 64-request allowance after three zoom steps. The selected-view allowance is now **256** requests, still only four simultaneous, eight seconds per active request and 512 KiB per response, with explicit restart after exhaustion and no automatic retry or prefetch. All provider URL, credential, cancellation, body-size and image checks remain enforced. This bounded allowance supports several genuine zoom levels on a large map without repeatedly dropping back to coarse measurements.

The exact fixed aerial URL is `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}`. Arbitrary hosts, redirects, queries, credentials, unsupported levels and non-JPEG responses are rejected. Candidate footprints, scale bars and scientific raster support are unchanged by provider selection.

## Global EOX layer

The provider is EOX IT Services GmbH. The fixed public layer is `s2cloudless_3857`, identified as the 2016 layer in the [official WMTS capabilities](https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml). Its matrix set is `GoogleMapsCompatible`, EPSG:3857, north-origin row/column order, with 256 × 256 JPEG tiles. The HTTPS endpoint returned HTTP 200 and CORS permission for the local application origin without credentials. No account, API key or billable service is used.

The publisher's [current vintage-specific license](https://cloudless.eox.at/license-non-commercial) and [FAQ](https://cloudless.eox.at/documentation/faq) identify the 2016 vintage as CC BY 4.0 and permit embedded use of the public endpoint with attribution and reasonable traffic, without an availability guarantee. The later vintages have different terms and are not selected. The attribution displayed by the component is: EOxCloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016 & 2017), linked to the publisher and CC BY 4.0. The [publisher's introduction](https://cloudless.eox.at/documentation/introduction) describes nominal 10 m Sentinel-2 input. That is not a guarantee that every delivered display tile resolves 10 m surface features.

## Actual Flagstaff tile comparison

The point used for this bounded check was 35.1983° N, 111.6513° W. All three URLs returned HTTP 200, `image/jpeg`, and 256 × 256 pixels:

| WMTS level | Official tile | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| 12 | [12/1619/777](https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/GoogleMapsCompatible/12/1619/777.jpg) | 16881 | `45b38be31e71071f3fce42f889d8274c5407e242891ad1170ba14506a1eea443` |
| 13 | [13/3239/1555](https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/GoogleMapsCompatible/13/3239/1555.jpg) | 19860 | `0f95b49aad84a1dbb77d4148a7fa5349f33b9af2ea493c99c2e7541017448267` |
| 14 | [14/6478/3110](https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/GoogleMapsCompatible/14/6478/3110.jpg) | 11754 | `f8fac2d7a9485984c29cbceffdcd8362ccc8913369ae49591e104ef3c49d42ba` |

For each child, compare its RGB array with the corresponding 128 × 128 quadrant of its parent resized to 256 × 256 using Pillow bilinear resampling. The z13 child uses the southeast quadrant of z12; z14 uses the northwest quadrant of z13. Mean absolute differences across RGB channels were **7.931** (z13 versus enlarged z12) and **1.418** (z14 versus enlarged z13). Fractions of pixels whose largest channel difference exceeded 16 were **0.168** and **0.000**, respectively. The visible z13 urban features add detail; z14 is consistent with interpolation of that existing detail. JPEG differences alone do not prove a ground resolving power, so this comparison is an empirical guard against advertising an interpolated level.

The application therefore conservatively stops requests at **WMTS 13**. At Flagstaff this grid samples approximately **15.6 m/pixel**, computed from the EPSG:3857 tile grid and latitude. The UI labels approximate sampling near the selected footprint separately from nominal 10 m input. The global shared capabilities matrix lists finer levels, which does not establish independent finer source information for this layer.

MapLibre 6.18.0 uses a 512-pixel camera world. Its installed `src/geo/projection/covering_tiles.ts` computes source level from camera zoom plus `log2(512 / tileSize)`. For these 256-pixel tiles, the satellite camera ceiling is therefore **12**, corresponding to source level 13. This prevents further camera enlargement of the last accepted level. The measured-terrain camera constraints are restored when satellite context is closed. The [MapLibre raster source specification](https://maplibre.org/maplibre-style-spec/sources/) documents source zoom bounds and the use of the final tile at higher camera zooms.

## Runtime bounds and checks

The reusable map defaults to offline; production regional and analog views require an explicit Load satellite imagery click. Opening a run, choosing a site, or changing camera positions before that click makes no external tile requests. Geographic Earth footprints must be local, geodetic, positive-east in NEG180_180, west-to-east, within ±85° latitude and no more than 2° across. The CRS must be exactly EPSG:4326 or the explicit null used for canonical Earth API geometry. Missing/empty/unknown CRS values, explicit projected CRS values, planetary/unknown axes, and projected/out-of-range coordinate numbers remain ineligible. The eligibility check remains local, but visual-source bounds are the latitude-safe world [-180, -85, 180, 85], and the camera retains MapLibre's native Mercator extent without a custom maxBounds constraint, allowing country/global context without changing the selected outline or authorizing numeric coverage elsewhere. Only tiles demanded by the current camera are loaded; no world preload occurs. Each bounded view permits at most 256 requests, four concurrent, eight seconds per active request, and 512 KiB per response. Credentials, referrers, redirects, automatic retries and bulk prefetch are excluded. Closing the view, changing sites, removing the map, the first failure, or reaching the request cap aborts remaining work. The 257th tile request terminates the imagery session, restores measured terrain, and shows the explicit 256-tile-limit message. An explicit retry creates a new bounded view.

The nullable-CRS case is based on the frozen contract and the actual scientific normalization path, not a browser CRS guess. Architecture `05-DOMAIN-MODEL-AND-CONTRACTS.md`, common conventions, defines Earth API geometry as WGS84 longitude,latitude. Frozen `ports/domain_models.py:26–36` allows a null `crs_wkt`. `science/ops/screen.py:272` calls `science/ops/terrain.py:aoi_for_bounds`, which transforms projected bounds and emits EARTH / GEODETIC / NEG180_180 / null. In `science/geometry.py`, `BodyGeometry.geographic_crs` chooses EPSG:4326 for Earth (lines 72–75), `_inverse_transformer` explicitly uses `always_xy=True` (208–209), and `projected_bounds_to_bbox` uses that inverse transform (476–501). Candidate AOI metadata and all numeric evidence/support are preserved unchanged by this display eligibility check.

The satellite layer is fully opaque, candidate fill is transparent, and prepared scientific rasters/legends are hidden while it is active. Outlines and site markers remain. Measured terrain view restores the original selected rasters and opacity. Unit/component checks cover these transitions, offline behavior, malformed tile identity, latitude-specific sampling, caps, concurrency, cancellation, timeout, provider/decode failure, stale selection cleanup and exact URL allowlist boundaries. Native browser verification of actual displayed Flagstaff tiles remains a separate integration check.


Production selected Earth views (regional inspector and analog candidate view) keep `autoLoad` disabled. An operator must explicitly start each selected site’s external imagery session. Failures and tile-budget exhaustion never automatically restart loading. Prepared raster colors and opaque candidate fills remain hidden only during an opted-in satellite view.


Native MapLibre verification found that applying a full 360-degree `setMaxBounds` constraint caused a camera matrix TypeError before any tile request in the installed version. The satellite view therefore does not call `setMaxBounds` or alter existing camera-bound settings; public source bounds still clip tile coverage to ±85°. Its temporary zoom ceiling is restored when returning to measured terrain.


Historical verification on 2026-11-14, before explicit opt-in was restored, showed automatic EOX imagery on the actual registered Flagstaff candidate, with finer roads/new source tiles appearing across two zoom-in steps and the outline expanding over the same geography. Review receipts: `out/native-review/earth-satellite-ready-r5.png` and `out/native-review/earth-satellite-zoom-r5.png`. This visual check does not add quantitative terrain evidence or enlarge the locked dataset coverage.


Camera movement may cancel obsolete raster requests. The installed MapLibre `util/abort_error.ts` identifies cancellation by `error.name === 'AbortError'`; the imagery map-error listener ignores that specific case while keeping genuine load/decode errors fatal to the bounded session. The loader also distinguishes caller cancellation from timeouts, provider failures and budget exhaustion. A focused component/protocol regression cancels one tile, emits the corresponding source AbortError, then successfully loads the next visible tile in the same session.


On 2026-11-15 the Comet review explicitly clicked **Load satellite imagery** before any external imagery session. USDA/USGS aerial tiles then loaded, and two zoom-in steps showed roads and terrain at a 500 m scale bar. Receipt: `out/demo-review/satellite-comet.png`. Production auto-load is disabled; the current browser regression also blocks both external sources to verify graceful failure only after the click.
