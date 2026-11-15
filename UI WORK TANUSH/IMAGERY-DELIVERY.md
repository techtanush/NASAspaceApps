# Global context imagery delivery — 14 November 2026

T1 is implemented as a static, versioned delivery for Aradhya's catalog adapter. It requires no account, key, paid provider, external browser imagery request or Aleph runtime. The existing fallback files and all frontend source remain unchanged. This delivery becomes visible when Aradhya's owned adapter loads the catalog; it does not itself replace `GLOBE_ASSETS`.

## Files to consume

- `analogforge/apps/web/public/globe/data/catalog.v1.json`: the frozen shared v1 shape, three real visual assets, all `placeholder:false`, all `relief_path:null`.
- `analogforge/apps/web/public/globe/data/preparation.v1.json`: complete source identities, raw/delivered hashes, dimensions, bytes, temporal context, encoding, operations, aesthetic processing disclosures and geographic controls.
- `analogforge/apps/web/public/globe/deliveries/{earth-bmng-july2004,mars-viking-nasa,moon-lroc-2019}.v1.jpg`: same-origin image bytes.
- `analogforge/scripts/data/globe_context_sources.v1.json`: pinned acquisition recipe. Source originals remain ignored beneath `.runtime/visual-context-sources/` and are not application datasets.
- `analogforge/scripts/data/prepare_globe_context.py`: opt-in bounded acquisition, preparation, complete staged validation and immutable publication. Reads do not download anything.
- `analogforge/tests/unit/platform/test_visualization_catalog.py`: offline integrity, negative/security, explicit orientation and real image landmark checks.

The optional-relief schema correction is owned and recorded by the integration owner: `relief_path.not` must constrain its pattern to strings so that the explicitly permitted `null` value actually validates. No fake relief image was created to bypass that schema defect.

## Actual imagery and limits

| Body | Official product | Delivered dimensions / bytes | Delivered SHA-256 |
|---|---|---|---|
| Earth | [NASA Blue Marble Next Generation base map, July 2004](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/) | 4096×2048 / 1,133,187 | `6194c0eccf55411adad6ec4bbb0857a8e3eedd700d729bd0a5980a27814693db` |
| Mars | [NASA 3D Resources Viking texture](https://science.nasa.gov/3d-resources/mars/) | 1440×720 / 972,896 | `12ec6bf02ebd42a246edc778cb2ce8c595b4d9f0892badf0bfff8abb2303c780` |
| Moon | [NASA SVS CGI Moon Kit, original 2019 color map](https://svs.gsfc.nasa.gov/4720/) | 4096×2048 / 2,110,895 | `98f512b2a9b90584805b8c44400ff91474559dfe22077f004cd13b72ddccfd43` |

Total public image payload is **4,216,978 bytes**. The Mars download is natively 1440×720. It is preserved byte for byte rather than upscaled to suggest additional detail. Part F's aspirational ≥4K Mars texture is therefore not claimed delivered by this particular asset. Fine regional inspection must use the registered MOLA/other approved detailed source and display artifacts. Global textures never establish scientific source coverage or mission PASS.

The Earth source is a monthly visual composite, not current imagery. Mars is a Viking-based context map, with source shading baked into the image; the NASA download does not supply an effective scientific resolution or validity mask. The Moon source is explicitly optimized for appearance: its publisher adjusted color/exposure, filled high-latitude dropouts and used lower-resolution LOLA albedo in the polar regions beyond 70°N/S. Those inherited source operations are disclosed in the receipt. AnalogForge adds no fill, inpainting, vertical shift or terrain measurement. Source image darkness is not a nodata mask. No height datum or scientific analysis support is asserted for any RGB texture.

## Coordinate orientation and renderer agreement

All delivered files are 2:1 equirectangular, east-positive longitude −180° at the left edge through 0° at image center to +180° at the right; +90° latitude is the top and −90° the bottom. No source needed a longitude roll or vertical flip. Earth is downsampled 5400×2700→4096×2048 with LANCZOS. Moon dimensions are retained and TIFF RGB is encoded to JPEG. Earth/Moon use JPEG quality90, 4:4:4, optimize enabled, nonprogressive; no source EXIF/GPS payload is copied. Mars source bytes are unchanged.

Orientation was checked against the texture itself and independent known positions: Sahara/Pacific/Amazon/Antarctica; [Olympus Mons](https://planetarynames.wr.usgs.gov/Feature/4453) at approximately 133.80°W,18.65°N, [Hellas Planitia](https://planetarynames.wr.usgs.gov/Feature/2432) at70.50°E,42.43°S, and dark Syrtis Major; [Tycho](https://science.nasa.gov/resource/tycho-craters-central-peak-on-the-moon/) at11.32°W,43.37°S, with northern maria. These are visual orientation checks, not accuracy certification or scientific coordinate intake.

The inherited `GlobeStage.tsx` passes `surface` straight to `globeImageUrl`, without an extra per-body rotation. The pinned `three-globe@2.45.6` implementation [rotates its sphere −π/2 around Y](https://github.com/vasturiano/three-globe/blob/v2.45.6/src/layers/globe.js) and uses [the matching longitude translation](https://github.com/vasturiano/three-globe/blob/v2.45.6/src/utils/coordTranslate.js). Combined with Three's standard sphere UVs, image center longitude0 faces +Z; longitude90E faces +X and north faces +Y, matching the marker equations. Aradhya should not add a 180° roll to these files. Rendered final landmark inspection still belongs in the merged browser gate after the adapter lands.

## Reproduction and validation

From `analogforge`, using the existing locked environment:

```sh
rtk proxy uv run --locked python scripts/data/prepare_globe_context.py prepare --cache-dir .runtime/visual-context-sources --download
rtk proxy uv run --locked python scripts/data/prepare_globe_context.py verify
rtk proxy uv run --locked pytest tests/unit/platform/test_visualization_catalog.py -q --strict-markers
rtk proxy uv run --locked ruff check scripts/data/prepare_globe_context.py tests/unit/platform/test_visualization_catalog.py
```

`--download` is optional; omitting it requires the three checksum-verified originals in the private cache. Only reviewed HTTPS NASA hosts are permitted, redirects/environment proxies are disabled, each download is bounded to20MB/120seconds with30second connection/read timeouts, and raw dimensions are checked before decoding. Sources and public output may not overlap. Public output is at most8MB per file and16million decoded pixels. Schema, byte count, SHA, RGB, EXIF orientation, 2:1 layout, citations/attribution, paths and symlink boundaries are validated before the catalog is published. Files are immutable by version; a different existing destination fails rather than replacing a public release. Atomic complete-file linking prevents partial image/catalog publication.

The recipe's committed receipt records Pillow13.0.0/libjpeg6.2, which are already installed in the verified local environment; no dependencies were added. Encoder version changes may produce different JPEG bytes. Reproduce with the recorded encoder, or deliberately create a reviewed new delivery version rather than overwriting these hashes. The original sources are pinned by SHA, so upstream changes stop acquisition until reviewed.

Focused verification completed: **48 tests passed**, Ruff passed, catalog verification passed. A separate clean temporary output reproduced **all three asset files, the catalog and the preparation receipt byte for byte**. Tests additionally verify complete offline preparation, unchanged originals, no partial release on version collision and metadata symlink rejection. This does not claim the unmerged frontend adapter or new live backend/browser integration gates have passed.

## Usage and Aradhya integration

The [NASA imagery usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) permit factual educational/informational use with appropriate source acknowledgement and without implied endorsement; third-party protected content and NASA identifiers have separate restrictions. These selected product pages identify the relevant NASA/JPL-Caltech/USGS/GSFC/ASU contributors. Preserve each full `attribution` and `usage_terms` field in the app's source details and any exported presentation. No NASA insignia, logo, private source raster or unreviewed screenshot is included. This delivery does not claim a license for unrelated Google/Aleph downloads.

Aradhya owns fetching `${BASE_URL}globe/data/catalog.v1.json`, validating its schema/version and same-origin paths, resolving BASE_URL-relative `surface_path`, mapping each body's real attribution and `placeholder:false`, and keeping the old truthful fallback if the catalog or a body entry is missing/invalid. `relief:null` must clear the old generated fallback bump image; do not retain synthetic relief on a real surface. No frontend file was changed by Tanush's imagery delivery. Continue to display source-mode/LIMITED/UNKNOWN labels from the actual run independently of the real-looking globe texture.
