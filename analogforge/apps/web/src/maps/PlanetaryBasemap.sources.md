# Planetary surface imagery

This is a visual context layer for the exact operator-selected Mars or Moon bounding box. It is independent of every numeric raster, mission contract, run, qualification result and rover verifier. No image implies scientific coverage, route safety, current weather, or physical validation. The main measured-terrain view retains its original affine, units, support, source receipts and native-coordinate inspector.

## Verified primary sources — 2026-11-14

- NASA Trek WMTS API: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars and https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon
- Mars capabilities: https://trek.nasa.gov/tiles/Mars/EQ/CTX_beta01_uncontrolled_5m_Caltech/1.0.0/WMTSCapabilities.xml
- Mars actual published ResourceURL/metadata: https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer?f=pjson
- Moon capabilities: https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml
- Caltech beta01 context: https://murray-lab.caltech.edu/CTX/

The Mars service is the **preliminary uncontrolled beta01** mosaic, not the newer V01 semi-controlled product. Source metadata explicitly grants free use for all purposes and requests NASA/JPL/MSSS/The Murray Lab credit. Esri hosts the exact public tile endpoint to which NASA Trek capabilities point. Source photographs are approximately5m/pixel; the capped NASA WMTS matrix11 delivers approximately10.17m equatorial sampling, so the UI does not promise5m delivered detail. No extra API key, account or paid service is required for these public image requests. No terms or billing settings were changed.

Moon uses NASA Trek LRO WAC global mosaic v2, approximately100m source pixels. Matrix8 has256px tiles,512columns and256rows. Equatorial delivery sampling is approximately83.3m/pixel; this sampling does not establish finer physical resolution than the source mosaic. Credit NASA/GSFC/Arizona State University and NASA Trek.

## Georeferencing and detail caps

Both selected services have equirectangular planetary longitude/latitude tiles, origin(-180,90),2^(z+1) columns and2^z rows. Mars uses512px tiles and Mars2000 reference sphere3396190m; Moon uses256px tiles and lunar sphere1737400m. Never use Earth Web Mercator or an Earth distance scale for either body. Input must explicitly declare the correct body, planetocentric latitude, east-positive NEG180_180 longitude and finite, ordered degree bounds. Null CRS follows the canonical API axis declaration; an explicit projected/unknown CRS is rejected. Image display arithmetic never changes the AOI or computes qualification.

Source levels cap at11 Mars and8 Moon. Buttons request different tiles as the camera changes and stop at those ceilings. The selected AOI rectangle is registered in the same degree frame. Pan and zoom alter only the display. Region editing remains in the separately labelled coordinate/region tools; raster-backed measured views retain their existing evidence lineage.

## Actual transport receipts

- Mars matrix8,row134,column451: HTTP200,image/png,CORS*,98692bytes; SHA256 9688ed0228fe292861657e3f3264bd0d2c433f429d23779d5a4e8b0a9fe81b15.
- Moon matrix8,row160,column289: HTTP200,image/jpeg,CORS*,33838bytes; SHA256 d5e094fe94a09e1a6ccafaeefb64e77ec4cd9295c6a016ad574a14b9dde75f0a.

These receipts prove source availability at inspection time, not future uptime, full planetary coverage or a completed app run. NASA Trek's Mars proxy tile path returns404; the client therefore uses its verified published ResourceURL directly, rather than pretending that the broken proxy works.

## Resource and privacy bounds

At most16tiles per camera view,4concurrentrequests,64requests per exploration session,8seconds per tile and1MiB of streamed bytes per tile. Each request permits only the fixed provider URL generated from validated body/level/row/column; credentials and referrer omitted, redirects rejected, content type/signature checked. A failure cancels sibling work and presents an explicit retry; unmount or view changes abort work and revoke object URLs. No automatic retries or synthetic terrain replacements. Reload imagery explicitly starts a new bounded budget. Public historical imagery is never labelled live video.

## Checks

Meaningful tests cover changed arbitrary target coordinates selecting different source tiles, exact matrix order, invalid axes/CRS/geometry/levels, source zoom ceilings, source failure without retry loop, abort/revocation, byte/type bounds and timeout. Native Comet visual verification and final source-frozen gate results are recorded in the integration receipt, not inferred from these unit tests.
