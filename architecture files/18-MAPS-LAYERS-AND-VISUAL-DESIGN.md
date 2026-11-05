# Maps, scientific layers and visual design

Binding decisions: `00-ARCHITECTURE-DECISIONS.md`. This document defines display behavior, not scientific derivation. Source projections, grid alignment, comparison scales and terrain calculations remain server/worker responsibilities. Display smoothing or zoom does not improve scientific resolution.

## 1. Map architecture and body boundary

Use two distinct rendering systems:

1. **Earth analog map:** MapLibre GL JS in its Earth map context, consuming WGS84 candidate/route vectors and prepared Earth display layers. Neutral application-owned style, bundled licensed Earth outline and no paid basemap requirement.
2. **Planetary panel:** an application-owned 2D canvas/SVG image viewport displaying backend-prepared Moon or Mars images in an explicitly named planetary CRS. It is not an Earth slippy map with a renamed planet label. It supports pan, zoom, region selection, evidence overlays and numeric-coordinate alternatives.

The body-specific panel may use a display overview in a documented longitude/latitude layout and a regional projected view for detailed evidence. Use the source-approved body definition/radius and projection, including polar projections where appropriate. Do not reuse Earth's EPSG:4326, Earth radius or Web Mercator tile coordinates for the Moon or Mars. Do not insert planetary geometries into the Earth candidate source.

The backend provides prepared display image(s), extent, body, horizontal CRS definition, longitude convention, vertical datum, raster dimensions, affine transform, no-data mask, units, source/effective resolution and overlaid vector coordinates in the same display CRS. Exact field names are governed by the API/artifact schema. If metadata is absent or contradictory, refuse to display the layer as spatial evidence and show the metadata error.

Planetary geometry storage and tool requests retain body and coordinate metadata. Earth GeoJSON uses longitude,latitude WGS84 only. A UI record may have both a geographic human-readable coordinate and projected display coordinates, but each has an explicit type and unit; never pass an untyped numeric pair between renderers.

## 2. Planetary panel implementation

### 2.1 Overview and region entry

Load a low-resolution application-generated body overview from an approved source; show its source and display scale. The overview is navigation context. Detailed quantitative statistics come from the region evidence, not from sampling the overview image in the browser.

Provide supported named target presets and numeric bounding-box entry matching `AreaOfInterest`. The initial drawing control is a rectangle; arbitrary polygon input is deferred until the schema supports it. Numeric fields display units and coordinate convention. For a longitude/latitude overview, convert pointer position using the declared image extent and longitude direction; constrain latitude to the body's geographic range. For projected regional view, any pointer-derived bounding box uses the provided affine transform and source coordinate system, then is validated/transformed by the backend. Do not estimate inverse projection using an Earth library default.

Before saving a region, display its body, approximate geographic extent, chosen projection and any antimeridian/pole handling. A changed body clears incompatible geometry. A region crossing a longitude seam is split/normalized by the backend geometry adapter; it is not automatically expanded into nearly the entire globe.

### 2.2 Pixel and overlay alignment

Treat prepared image pixels as a grid with a documented corner/center convention. For affine transform coefficients, consistently map raster column/row to projected coordinates using the artifact's convention. Test all four corners and at least one interior control point against the backend reference. Axis direction may be north-up or another approved orientation; do not assume image row increases northward.

Keep viewport transform (pan/zoom) separate from scientific affine transform (pixel/world). On click: screen → viewport-local image position → image pixel → declared world position. Vector overlays use the inverse sequence. Resizing preserves the selected world region rather than resetting a focus point unpredictably. Device-pixel ratio changes sharpness only.

Supported controls: fit target, zoom, pan, toggle layer, opacity, legend, source/CRS metadata, inspect point and reset view. Every point query shows **display pixel** versus **analysis cell** clearly. If no approved sample endpoint exists, point inspection reads only supplied display metadata and does not pretend the image color is an original scientific value.

### 2.3 Supported failure states

- No approved source/granule: show target outline and **Source data unavailable**; no decorative terrain is presented as measured evidence.
- Region outside layer coverage: hatched no-coverage panel; retain target coordinates and alternate supported layer choices.
- Invalid projection or transform: block overlay alignment and show a diagnostic reference ID.
- Partial coverage: show valid mask and fraction; leave masked pixels transparent/hatched, never zero-filled.
- Data resolution too coarse: show the evidence with limitation; prevent visual zoom from implying centimeter measurements.

## 3. Earth map style and network policy

Default style contains an offline-capable neutral background, bundled licensed Earth outline/borders where provided, and application-owned overlay sources. No Mapbox token, commercial satellite service or unexplained public tile dependency is necessary. A bundled outline is optional geographic context, not elevation evidence. Store its license, attribution, version and checksum with static asset metadata.

Optional licensed basemap configuration is a deployment setting, disabled by default. It must specify tile URL/provider, permitted use, attribution, credential handling and network disclosure. A failed external basemap falls back to the neutral style while application evidence remains usable. Do not make scientific success contingent on a decorative basemap.

Application raster imagery/tiles come from the artifact service, with access checks appropriate to the workspace. Map fetch errors are reflected in the layer panel, not swallowed by the renderer. A layer can be enabled only if its artifact manifest matches Earth body, expected CRS/display format and current evidence revision.

Use backend-prepared WGS84 GeoJSON for Earth candidate extents, routes and waypoints. Dateline-crossing regions are supplied as valid split geometries. Scientific measurements such as route length and slope use worker calculations, not MapLibre screen distances.

## 4. Layer registry

Maintain one typed registry that owns label, body eligibility, required artifact kind, source revision, legend, units, attribution, opacity range and render order. A toggle cannot refer to an uncomputed layer. When switching candidates, remove stale candidate layers before adding the new artifact; keep a small “Loading candidate evidence” indicator rather than showing one candidate's terrain under another candidate's name.

| Layer | Display content | Guardrails |
|---|---|---|
| Geographic context | Earth outline, labels or planetary overview | Not measurement evidence. |
| Source/analysis coverage | Source extent and valid/no-data masks | Must remain inspectable above other fills. |
| Elevation | Prepared DEM display raster | Vertical datum, units, source/effective resolution shown. |
| Slope | Deterministically derived angle raster | Degrees, kernel/comparison scale and reference method link. |
| Roughness | Defined roughness statistic | Never label a coarse roughness proxy as boulder height. |
| Local relief | Derived windowed relief | Window footprint and units visible. |
| Mineral context | Approved product classes/values | Source coverage/uncertainty; no visual inference beyond product support. |
| Thermal | Approved temperature/statistic/time condition | Units, season/local-time/aggregation context; not generic “cold”. |
| Candidate boundary | Analyzed and nominated extents | Distinguish nomination extent from actual analyzed extent. |
| Test zone and forbidden areas | Accepted test proposal geometry | Hard exclusions visibly labeled; planned versus committed version. |
| Route | Computed route or proposed route artifact | Different dash/style per status/attempt; no fictional live rover trace. |
| Waypoints | Base, task and evidence-supported science points | Icon encodes type; tooltip states evidentiary basis. |
| Violations | Failed slope/energy/exposure segments | Derived from receipt; never recalculated by color threshold alone. |

Render order: context → imagery/terrain → coverage masks → candidate/test boundaries → exclusions → route alternatives → active route → waypoints/violations → selection/focus. Keep labels legible without obscuring the selected route. A legend describes the selected requirement/measurement rather than an invented site-wide quality color.

## 5. Candidate and route symbology

Candidate default uses neutral outlines with a clear selected state. Optional coloring is **by one selected requirement**, whose name/status is in the legend. A candidate with terrain `PASS` and geology `UNKNOWN` cannot receive a generic all-green marker. A small status summary can show counts with a visible denominator and scope.

Routes distinguish: proposed (dashed), current computed attempt (solid), prior attempt (muted), violated segment (strong red pattern + label), forbidden area (hatched), required exposure segment (band color + legend). Do not overload the same color to mean both slope value and outcome without a clear mode/legend switch. Route tooltip includes attempt ID and measurement scale.

For replanning, show before/after with an explicit attempt legend and changed candidate/test-zone text. A playhead follows modeled cumulative route distance/time. Energy, slope and task readouts come from committed route series. At playback start label **Modeled route playback**. A replay run also keeps **Recorded replay** visible; double meaning must be resolved in the labels.

## 6. Scientific chart rules

Target and Earth charts share bin definitions/axes only when the comparison method explicitly makes them comparable. Otherwise render separate labeled axes and show the incompatibility. Slope distributions use defined bin edges with units; roughness plots include statistic/window. Show sample/valid-cell counts and no-data fraction. Do not compare an unsmoothed high-resolution Earth DEM with a coarse planetary DEM and call the result equivalent.

Charts include:

- Target versus candidate slope-band distribution at the selected comparison scale.
- Roughness/local-relief distribution with definition and uncertainty where available.
- Required versus achieved route exposure per band; exact band edge semantics in receipt.
- Modeled energy consumed/reserve along route, with required reserve line and model assumptions.
- Waypoint/task checklist linked to map locations.
- Portfolio requirement-to-site matrix, preserving unresolved and physically unavailable dimensions.

Every graph has a table equivalent. Do not animate a passing curve before measurements exist. Avoid smoothing away discontinuities or violations; aggregated display data links to the full receipt and documents its aggregation.

## 7. Visual system

The workbench should feel focused and readable: clear hierarchy, generous panel spacing, compact informative tables and a dark terrain canvas balanced with high-contrast surfaces. Choose one coherent token system; do not imitate a dense cinematic cockpit at the cost of legibility. These are proposed design tokens, to verify in implementation:

| Token | Intended role |
|---|---|
| Background | Deep neutral workspace, e.g. `#0B1220` |
| Surface | Raised panel, e.g. `#132033` |
| Primary text | Near-white, e.g. `#F2F6FC` |
| Muted text | Legible secondary text, e.g. `#B5C4D9` |
| Accent | Cyan/blue action/focus, e.g. `#66D9EF` |
| PASS | Green + check icon + text |
| PARTIAL | Amber + half/limited icon + text |
| FAIL | Red + cross icon + text |
| GAP | Violet + unavailable-condition icon + text |
| UNKNOWN | Slate + question icon + text |
| Pending | Neutral spinner/clock + “Pending” |

Measure contrast on actual backgrounds; suggested colors are not an assertion of compliance in every combination. Provide a light/print presentation using the same semantic hierarchy. Use system fonts, normal letterspacing for body text, tabular numerals for comparable measurements and readable minimum sizes. Avoid all-caps paragraph text. Reserve large uppercase **PROVE IT** for the primary experiment action and a limited report treatment.

Spacing scale: 4/8/12/16/24/32 px. Controls need comfortable touch targets and distinct focus outlines. Tables align units and decimal values, wrap descriptions and preserve readable row heights. Use simple icons with adjacent labels; no decorative animation that appears to be scientific progress.

## 8. Layout and responsive behavior

Desktop reference: top run header; left context 240–280 px; central flexible map/data area; right evidence 320–380 px; collapsible bottom operations 180–260 px. These are preferred ranges, not fixed requirements that cause horizontal page overflow. Qualification can expand across the central/right area for comparison.

At tablet width collapse context to a summary strip and use one detail drawer. At mobile width use sequential tabs/stacked cards: mission summary, main content, candidate list, evidence, operations. Maps retain a useful aspect ratio but never force a user to interact with a tiny viewport before accessing the equivalent list/form.

Do not place essential controls only in map corners hidden under browser UI. Dialogs and drawers respect safe viewport height and scroll independently. Panel resize controls, if implemented, have keyboard equivalents. Save harmless panel preferences per user/workspace; do not persist a misleading selected old artifact over a new run.

## 9. Accessibility and evidence integrity

Provide numeric coordinate/extent entry, candidate lists and table views as alternatives to map actions. A selected feature is announced by name and status; a screen reader need not parse hundreds of canvas points. Legends include text and patterns. Colorblind users can distinguish result states and route attempts. Tooltips are reachable through focus/click and do not disappear before reading.

Attribution remains visible on-screen and in exports. Source NASA/partner attribution is drawn from the actual manifest; a synthetic layer carries synthetic attribution. Do not place NASA insignia as a certification badge or imply endorsement. Projection, measurement scale, source resolution, acquisition/context time and no-data coverage are scientific context, not optional debug information.

## 10. Map/design acceptance criteria

- MAP-001: Earth displays without any paid key or external basemap request in the default deployment.
- MAP-002: Moon/Mars panel refuses Earth CRS metadata and Earth panel refuses planetary geometry.
- MAP-003: Known raster control points align with overlaid geometry at multiple zoom levels and device-pixel ratios.
- MAP-004: A target crossing a longitude seam or near a pole retains its intended extent and body metadata through save/reload.
- MAP-005: No-data pixels remain explicitly masked; zero elevation and no-data are visually and semantically different.
- MAP-006: Zooming beyond effective resolution never changes measurement values or removes scale warnings.
- MAP-007: Switching candidates cannot show a prior candidate's raster under the new selection.
- MAP-008: Requirement coloring identifies the selected dimension and does not imply overall site approval.
- MAP-009: A failed route segment and later replan retain distinct labeled attempt geometry and receipt links.
- MAP-010: Reduced motion disables auto-play and all map actions have non-pointer alternatives.
- MAP-011: Offline/blocked optional basemap leaves application-owned vectors/rasters and legends usable.
- MAP-012: Source attribution, mode, body, projection and scale are available in both interactive evidence and the exported report.
