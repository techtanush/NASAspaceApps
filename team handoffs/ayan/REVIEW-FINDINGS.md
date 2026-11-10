# Ayan branch review, 9 November 2026

The review began from the pushed branch at `6856046`, after reading Ayan's guides 01–09, architecture 34–40, the relevant science/provenance/verification architecture and the shared scientific release gate. All work was done in this chat, without subagents, as requested.

## Baseline first

A fresh Python 3.12 environment reproduced the existing result before production edits: 973 science/replay tests, 20 kit tests, Ruff, strict mypy and ownership checks passed. The source architecture expected more than those passing assertions established. Five new source-path regressions then failed before their fixes. Raw baseline records remain under `analogforge/data/out/ayan-review-baseline/`; selected durable records accompany the final review report.

## Confirmed defects and corrections

1. Geographic and non-metric rasters ingested but could not reach characterization. Body-specific metric projection now preserves physical native support, masks and categorical identity. Earth HGT, Mars GeoTIFF, lunar PDS3 radius, ASCII DEM and mineral NetCDF mock formats execute through the facade, beyond validation alone.
2. Ingestion returned a normalized evidence pointer without reusable raster bytes. It now writes a deterministic, bounded NPZ with typed metadata, original file hashes, physical values and masks, plus the required canonical JSON report. The resolver can reuse authorized immutable source evidence after incoming directories disappear; corruption, wrong kind/body/mode and malformed array headers are rejected.
3. Common-support processing required integer ratios and used declared native size rather than the actual projected cell. Continuous values now support arbitrary coarser area-average grids without upsampling. Analytic fractional-footprint and missing/water tests supplement the existing independent integer-scale oracle.
4. Water-mask alignment checked shape alone. CRS and affine registration are now checked before use; a one-pixel shifted mask is blocked.
5. Lunar thermal metrics omitted their source lineage and used the terrain frame. They now use their own grid frame, include the whole AOI in coverage, and register their consulted source and hashes. Mineral source bytes now affect analysis identity, and CRS equality is required before a retrieval is credited as aligned.
6. Optional normalized THERMAL/MINERAL sources could not render; real terrain could receive generic NASA attribution. Display now uses actual source data/citation/license, transparent missing cells, correct normalized elevation units and single-body/mode checks.
7. Unexpected errors and model validation errors could expose untrusted values. Public diagnostics now retain a safe type/detail without raw exception values.
8. Whole-planet AOI counting could allocate huge arrays before checking limits. Counting has a cell budget before allocation and cancellation checkpoints per chunk.
9. Generated windows could collide with synthetic reference ids or fixed-window ids. Synthetic known-control membership is constrained to synthetic fixed grids; analysis also checks the candidate body/AOI against the selected window.
10. FETCH_SOURCE omitted its canonical JSON payload artifact. It now emits a fetch report linked to acquired assets. Raw download and scientific normalization remain separate stages.
11. The mutation runner treated setup errors as successful defect detection because its temporary package lacked configuration. It now copies configuration, requires a passing unmutated baseline and executed test failures, and refuses errors, skipped tests, empty runs and timeouts. Real child-process acceptance tests prove these distinctions.

The corrected mutation run exposed three ineffective definitions: reversing only heap priority did not reverse the complete tie-break, while removing either node or edge slope protection left the other protection effective. M1 now reverses the node ranking used by the actual tie-break. One M4 overrides the graph's effective slope cap, exercising the guide's single required M4 behavior. There are exactly 16 required mutation behaviors, each with passing baseline and failing invariant test; this replaces the earlier misleading 17/17 claim.

Affected algorithm versions advance from 1.0.0 to 1.1.0 so cached identities and SC-09 detect the change. Thresholds, numerical tolerances, ports and frozen kit bytes remain unchanged. Two unit handle builders now read the locked algorithm version; stale-version rejection remains asserted. The old ingestion budget test's `artifacts == []` contradicted architecture 35, so it now asserts the required normalized raster and JSON artifacts instead. Its five-second limit is unchanged.

## Scope limits for the merge

This is a science-library branch. Its facade and registrar stub exercise the public contract; it has no app server or browser UI of its own. Final cross-branch API, persistence, agent, publication and UI acceptance must run in integration.

Real NASA source acquisition, independent real-product control pixels, held-out real comparative validation and a real modeled experiment have not run in this review. No credentials or real data were invented. S0/S1 offline success cannot be promoted to S2–S5 or field safety. Live model execution is also unrun. Energy outputs remain modeled and uncalibrated; terrain support cannot certify small-obstacle clearance. Optional unaligned mineral data remains unknown, and thermal product semantics remain unresolved.

The full shared SCI cases that involve publication/UI remain unrun here; the scientific validation report lists both the executed science subchecks and the outstanding integration scope. The four-subagent step in guide 09 was superseded by the user's explicit request to conduct this review here without subagents. This single-reviewer work is not represented as four independent reviews.
