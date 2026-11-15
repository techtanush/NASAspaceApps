# Visual reference and exact-location experience

Reference supplied by user on 14 November: Fable's dark Earth-tour screenshot. Preserve its large globe/stage left, calm glass panel right, top navigation, readable Earth-sites title, status/mode labels, requirement coverage, bottom step rail and previous/next controls. The six-site count in the screenshot is sample data, not a hardcoded product requirement. The earlier Google Earth example shows desired globe-to-place orientation, not a requirement to use Google assets or imitate unsupported street-level detail.

## Required interaction
1. Whole Earth shows the actual run's candidate footprints/markers. Cluster nearby sites but expose each individually in the equivalent list; four adjacent Flagstaff windows remain four candidates.
2. Select a candidate by marker OR list. Fit its true bbox with panel padding. Global marker, panel, URL and selected evidence use the identical canonical ID. A click must not choose a nearby representative site by accident.
3. Offer `Inspect location` to enter regional detail. Crossfade/switch the stage from global context to the existing Earth detail renderer or body-specific planetary panel. Retain the site/requirement panel; add `Back to globe`, fit/reset, north indication, layers/legend and scale.
4. Show real prepared terrain/imagery layers, boundary, valid mask and existing route/violation overlays only when the matching artifacts exist. Source/acquisition context, CRS/height datum, effective resolution, comparison support and attribution stay reachable; a resolution notice stays visible while overzoomed.
5. Layer changes do not change measured results. Point inspection labels display pixel vs analysis cell; unsampled values show Unknown. Optional terrain exaggeration is display only with a visible factor, never a silently stronger slope.
6. Next/Previous in regional mode loads the next site's metadata and removes the previous site's layers before any new imagery appears. Fast repeated selection, offline missing detail and a failed tile cannot mix sites.
7. Return to Whole Earth preserves selected site and user-controlled view preferences. A valid direct link opens the correct site; an invalid/foreign ID fails safely.

## What exact means

Correct registered place, true footprint, aligned layers and honest source detail. It does not mean street-level, centimetre detail or photogrammetric buildings when only coarse DEM/Blue Marble exists. For the current real run, comparison support is 500m; NASADEM/MOLA source postings and the prepared display grid have separate meanings. Zoom cannot increase effective measurement resolution. No global Mars placeholder is evidence of the actual landing-site terrain.

Global globe motion is navigation; source imagery and regional scientific display are separately labelled. No external Google requests or direct browser credential exposure. Offline/no-WebGL users retain coordinates, detailed metadata, lists, evidence tables and report; unavailable imagery is clearly explained.

Acceptance screenshots: whole-Earth tour; one adjacent-window cluster opened; selected Earth site detail; target Mars detail; missing-data detail; FAIL site; LIMITED/no-rover; 390px bottom sheet; keyboard focus; reduced motion; printable report. New Mars/Moon real textures stay placeholder-labelled until their source catalog passes validation.
