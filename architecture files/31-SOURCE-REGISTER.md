# Source register and verification boundaries

The original supplied files are retained byte-for-byte in `references/`, with hashes in `references/source-manifest.json`. Product examples are design intent, not measurements. External documentation informed integration details; actual products, footprints, downloads, checksums and configured model access require implementation preflight. Review date is November3,2026 in America/Los_Angeles.

## Original material

- `references/AnalogForge_Final_Research_Build_Brief.docx`: original24-section brief. The11-page document was read and rendered during initial review.
- `references/original-concept.txt`: original44-section pasted specification.
- `references/docx-text-extract.txt`: ordered paragraph/table-cell extraction for searchable implementation context; original DOCX remains the layout authority.

Source document directives do not authorize deploying software, buying services, sending messages, or controlling hardware. The user's request authorizes creating this local architecture bundle. Baseline0.20m rover clearance follows the DOCX; uploaded profiles always govern actual runs.

## Official research references

| Source | Role and verification status |
| --- | --- |
| [NASA Analog Missions](https://www.nasa.gov/analog-missions/) | Official context that analog operations already exist; retrieved. |
| [Planetary Analog Explorer](https://science.nasa.gov/solar-system/analog-explorer/) | Known-reference sites and field context; retrieved. Not a replacement for analysis or a complete worldwide catalog. |
| [2026 challenge URL supplied in brief](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/) | Fetch returned502 during this task. Challenge wording/track intent retained from supplied material; current official rules, resource tab, eligibility and judging details need rechecking before submission. |
| [Earthdata Login user tokens](https://urs.earthdata.nasa.gov/documentation/for_users/user_token) | Official token-management/access setup; retrieved. Compatibility must be checked per data endpoint. |
| [CMR Search API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html) | Collection/granule metadata discovery and supported metadata formats; retrieved. No actual granule lock created. |
| [NASADEM product DOI](https://doi.org/10.5067/MEASURES/NASADEM/NASADEM_HGT.001) and [user guide](https://lpdaac.usgs.gov/documents/2237/NASADEM_User_Guide_V13.pdf) | Scientific source identity, encoding and support; research detailed in08. Actual tile/quality checks pending. |
| [MOLA MEGDR archive](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html) | Maintained Mars topography products and labels; research detailed in08. Exact selected asset/CRS/checksum pending. |
| [LOLA archive](https://pds-geosciences.wustl.edu/missions/lro/lola.htm) and [FAQ](https://pds-geosciences.wustl.edu/missions/lro/lola_faq.htm) | Lunar product families/scaling/frame cautions; research detailed in08. No downloaded lunar product validated. |
| [EMIT L2BMIN DOI](https://doi.org/10.5067/EMIT/EMITL2BMIN.001), [guide](https://lpdaac.usgs.gov/documents/1660/EMITL2BMIN_User_Guide_V1.pdf), [NASA resource repository](https://github.com/nasa/EMIT-Data-Resources) | Mineral/quality/geolocation integration references; actual valid pixel coverage pending. |
| [Diviner archive](https://pds-geosciences.wustl.edu/missions/lro/diviner.htm) and [science-team data](https://www.diviner.ucla.edu/data) | Thermal product selection and interpretation; actual variable/time/geometry lock pending. |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) | Official strict tool-call interface; retrieved. Runtime account/model support not tested here. |
| [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) | Official structured result interface; retrieved. Backend semantic validation still required by our design. |
| [PostgreSQL16 SELECT](https://www.postgresql.org/docs/16/sql-select.html) | Queue claim locking basis; retrieved. Our lease/fencing policy is an architectural design choice. |
| [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) | Separation of request-bound small tasks from independent heavy work; retrieved. PostgreSQL queue choice is our design. |
| [MapLibre Map API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/) | Frontend map implementation reference; retrieved. Planetary panel geometry remains explicitly separate. |
| [RFC8785](https://www.rfc-editor.org/rfc/rfc8785) | Canonical JSON for manifest hashing; retrieved. A digest is not scientific certification or a digital signature. |

Scientific docs08–13/29 carry additional precise references beside claims. Preserve citations when implementing help text and product metadata. No current model pricing, guaranteed account access, live service quota, sponsor benefit or challenge award is assumed by this blueprint.

## Assumptions versus established results

Chosen stack, default budgets, interface structure, status policy, algorithms and fixture values are explicit design choices. Mission slope exposures and baseline rover numbers are illustrative engineering assumptions requiring accepted input revisions. Named product families and metadata selectors are discovery seeds until preflight verifies their current versions and source artifacts.

No real source granules were downloaded for this architecture task. No source-derived candidate ranking, route success, battery prediction, mineral match or thermal match is asserted. Synthetic examples are labeled and only establish expected software behavior.

## Research maintenance during implementation

If a source moved, follow the official archive/catalog and create a new policy-lock revision rather than guessing a URL. If a source cannot support a claim at the needed scale, downgrade the requirement or propose an explicitly accepted different experiment; do not increase apparent resolution by resampling. Event submissions require a separate official rules review; building this architecture does not constitute registration or submission.
