# Earth regional visual context — source verification

Verified on 2026-11-14. This is a display-source receipt, not scientific qualification evidence. No image enters terrain measurements, route verification, matching, weather inference or passport claims.

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

The default map remains offline. Only the selected regional inspector exposes the explicit Load satellite imagery action. Geographic Earth footprints must be local, EPSG:4326 geodetic, west-to-east, within ±85° latitude and no more than 2° across. The source bounds add at most 0.1° around that footprint. Each opt-in permits at most 64 requests, four concurrent, eight seconds per active request, and 512 KiB per response. Credentials, referrers, redirects, automatic retries and bulk prefetch are excluded. Closing the view, changing sites, removing the map, the first failure, or reaching the request cap aborts remaining work. An explicit retry creates a new bounded view.

The satellite layer is fully opaque, candidate fill is transparent, and prepared scientific rasters/legends are hidden while it is active. Outlines and site markers remain. Measured terrain view restores the original selected rasters and opacity. Unit/component checks cover these transitions, offline behavior, malformed tile identity, latitude-specific sampling, caps, concurrency, cancellation, timeout, provider/decode failure, stale selection cleanup and exact URL allowlist boundaries. Native browser verification of actual displayed Flagstaff tiles remains a separate integration check.
