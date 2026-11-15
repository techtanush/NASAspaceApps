# Tanush data and imagery plan

## T0 — Inventory without mutating sources

Record selected product/granule/version, exact raw bytes checksum, usage terms/attribution, acquisition/product time, body, horizontal frame, vertical reference, nominal posting, effective resolution when known, nodata and analysis support. Distinguish raw source, quantitative prepared grid, display derivative and global context image. Never relabel one as another. Keep source rasters private/ignored; publish only intentionally redistributable visual assets with bounded size.

Known validated local sources: NASADEM near Flagstaff from Microsoft Planetary Computer and MOLA Gale from NASA PDS. Follow LOCAL-LIVE-RUNBOOK exact hashes/recipes; private data/profile are not on GitHub. Earth coverage is not global simply because a global Blue Marble texture exists. Moon scientific terrain is not available until a real source passes intake/lock/bind. Meteomatics is optional Earth context, outside qualification evidence; credentials remain backend-only.

## T1 — Surface context catalog

Deliver public/globe/data/catalog.v1.json and versioned public/globe/deliveries/* files conforming to the shared imagery schema. Aradhya loads them without Tanush editing TS.

1. Select a documented, permitted global Earth/Mars/Moon source. Examples for evaluation: NASA Blue Marble, USGS Mars mosaics/shaded relief and LROC/LOLA products. Verify exact product availability, terms, coordinates and attribution using primary product documentation before downloading; names here are candidates, not verified installed sources.
2. Verify equirectangular2:1, north up, source longitude convention and seam orientation; resample/roll explicitly when needed and record the operation. A Mercator Earth tile mosaic is not an equirectangular Mars texture.
3. Prefer4096x2048 context image when justified and hardware-safe. Keep compressed assets reasonably bounded; never exceed GitHub file limits or commit giant scientific rasters. Record actual bytes/dimensions/hash. Further detail belongs in regional artifacts/tiles, not an enormous global image.
4. Set placeholder=false only for a verified real source; keep generated Mars/Moon fallback honestly labelled otherwise. Relief texture is shading, not authoritative elevations. Attribution must survive UI and export.
5. No browser provider keys/external basemap dependency. Source URIs in catalog are citations only. No Google scraping, streetview capture or unreviewed user screenshots in public assets.

## T2 — Regional source-to-display pipeline

Use existing immutable registered terrain datasets, locks, body-aware analysis grids and build_display_layers. For Earth prepare authorized WebMercator display images/corners; for Mars/Moon use named body-specific planar display frame. Keep truthful no-data masks, affine pixel/corner convention, units, height datum and source/support metadata. Validate known corners/interior independently.

The MOLA recipe explicitly distinguishes source sphere3396000m from app sphere3396190m and rounded source map scale. Use the committed checksum-verified preparation utility; no CRS string substitution, undocumented vertical shift or native resolution inflation. Preserve earlier source versions and failure history.

For a selected candidate, create only artifacts justified by its pinned evidence. Fine-grained context may be visually useful but cannot change500m comparison results or bypass intake. New more-detailed source changes require a new dataset version/lock and, if used scientifically, a new run. Display-only resampling remains tagged with parent checksum and derivation.

Optional future open Terrain Tiles/OSM from Aleph are independent acquisitions, never an automatic NASA-backed source. They need their own terms, height-reference validation and source chain. Keep P0 on the existing trusted NASADEM/MOLA flow.
