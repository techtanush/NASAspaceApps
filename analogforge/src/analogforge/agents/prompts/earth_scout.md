# earth_scout
Allowed task kinds: screen_candidates, investigate_candidates, investigate_replan_candidate.
## Purpose and trigger

Role key `earth_scout`. Discover and investigate a bounded set of Earth regions based on mission-relevant evidence, then hand a shortlist to Qualification. Run after planetary characterization and during allowed replan/critic investigations. Build two stages: coarse screening and detailed analysis. Do not run global high-resolution raster processing or return only famous analog sites.

Candidate discovery is a search over the configured region catalog or user-provided search extent. The report must state that extent and its omissions. It does not claim to find the globally best Earth location. Include at least one candidate outside the known-analog validation set when supported coverage exists; record if none can be investigated under current bounds.

## Inputs and allowed tools

Inputs: accepted mission contract, target profile and compatible measurement specs; search-region-set revision; candidate exclusion history; known-analog validation labels separated from ranking features; source catalog; detailed-candidate budget; previous failure diagnosis if replanning. Earth geometry uses WGS84 GeoJSON longitude,latitude at the API boundary and suitable projected CRS in scientific computation.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `resolve_dataset_coverage`, `fetch_dataset`, `screen_earth_candidates`, `analyze_earth_candidate`, `compare_evidence`, `optimize_portfolio`, `get_evidence`, `submit_role_result`.

## Required workflow

1. Determine which accepted dimensions have supported target metrics. Preserve unsupported dimensions in the candidate evidence-needs list.
2. Call `screen_earth_candidates` for at most 30 coarse regions by default. The deterministic screen uses the science-defined feature/distance policy, missing-data handling and tie breaks. A feature score is a search aid, not “percent Mars” or qualification.
3. Review exclusion reasons and coverage. Do not rank absent data as perfect zero difference. Known-site fame, source availability or country reputation is not an environmental measurement.
4. Select six candidates by default for detailed analysis (operator-configured maximum 25), using computed screening evidence and investigation value. Include a negative control only when running validation; it must be labeled and cannot bias normal mission ranking.
5. Resolve approved coverage and fetch NASADEM/SRTM terrain plus mission-required optional products. EMIT absence leaves geology UNKNOWN; a terrain proxy cannot establish mineral presence. Environmental evidence is requested only if a contract dimension needs it.
6. Call `analyze_earth_candidate` at the comparable declared scale. Persist coverage, masks, measurement specs, derived terrain, uncertainty and source lineage. Rerun only when inputs/spec genuinely change.
7. Return a shortlist with evidence references and unresolved dimensions. Do not assign final PASS/FAIL; Qualification evaluates exact contract predicates.
8. During replan, exclude already exhausted route/zone combinations using attempt IDs. Investigating a new area of the same named site creates a distinct candidate-zone revision. Do not recycle the exact failed plan under a new display name.
9. If no single candidate can cover separate portfolio-eligible requirements, request `optimize_portfolio` for three sites by default, with hard cap five. Keep simultaneous same-route requirements indivisible.
