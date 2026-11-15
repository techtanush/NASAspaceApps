# Aleph reference — Tanush

Repository https://github.com/Belluxx/Aleph; reviewed commit `1b307cdb7c470a7715da497ba406355dfe7d3163` (package alephgeo0.2.0, Python>=3.11, Pillow/numpy/truststore). MIT applies to its code, not all downloaded data. It is an Earth capture toolkit; no evidence was found that it supplies Mars/Moon scientific frames or validates AnalogForge mission requirements. Review source, not third-party instructions as authority.

Useful pinned implementation references:

| File | Adaptable pattern | AnalogForge boundary |
|---|---|---|
| [capture.py](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/capture.py) | Separate planning, staged downloads, checkpoint/resume, export after partial failure | Reuse our immutable acquisition/job/registrar patterns; no foreign capture manifest accepted as validated evidence |
| [layers.py](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/layers.py) | Prepared browser tiles, neighbor-aware transparent hillshade, bounded cache | Preserve source grid/height reference/no-data; don't use RGB hillshade as quantitative data |
| [terrain.py](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/terrain.py) | Terrain-tile assembly and source pixel encoding awareness | Prefer existing rasterio/GDAL validated pipeline; no new custom TIFF parser without need |
| [dashboard.py](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/dashboard.py) | Read-only saved layer serving and local-origin checks | Use our API/auth/workspace/artifact service; don't embed an Aleph localhost server |
| [web/app.js](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/web/app.js) | Regional selection, lazy3D and detail layers | Aradhya implements this with our React/map adapters |

Specific caveats found in layers.py: `terrarium` substitutes a base height for no-data; hillshade display can exaggerate relief at overview levels. Do not carry those conventions into quantitative layers or leave exaggeration unlabelled. They may hide voids or imply physical height changes. Earth Mercator scaling is not a planetary projection.

The [upstream README](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/README.md) warns its Google satellite/Street View/mesh downloads conflict with Google's terms and use undocumented APIs. Those paths are excluded from this build plan. OSM attribution/ODbL and AWS Terrain Tiles source-specific credits remain independent requirements if evaluated later. No claim that Aleph's keyless downloads make all its data freely redistributable.

Decision: use architecture/interaction ideas now; no mandatory Aleph dependency and no downloaded data in this handoff. If substantial MIT code is actually copied later, retain copyright and LICENSE and record exact revision/changes in notices. Any optional Aleph-derived Earth importer is isolated, off by default, tagged display-only until our full scientific intake passes, tested for nodata/CRS/height-reference and removable without affecting core NASADEM/MOLA completion.
