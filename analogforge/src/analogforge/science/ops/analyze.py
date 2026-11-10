"""``ANALYZE_CANDIDATE`` (guide 08 section 4.6)."""

from __future__ import annotations

import numpy as np

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef, ScienceIssue
from analogforge.ports.science import ArtifactRole, ComputationStatus
from analogforge.ports.science_payloads import AnalyzeCandidateInput, AnalyzeCandidatePayload
from analogforge.science.features.connected import Band, connected_zones, largest_component, safe_mask, to_port_zone
from analogforge.science.features.coverage import coverage_summary
from analogforge.science.features.histogram import to_port_histogram
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, bytes_artifact, derived_evidence, json_artifact
from analogforge.science.ops.source import find_bound_dataset, resolve_source
from analogforge.science.ops.terrain import (
    band_metrics,
    band_pairs,
    hist_of,
    metric,
    prepare,
    roughness_metrics,
    slope_stat_metrics,
)
from analogforge.science.ops.windows import find_window
from analogforge.science.raster.store import MEDIA_TYPE, build_analysis_grid, encode_analysis_grid


def run_analyze(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, AnalyzeCandidateInput)
    algo = catalog.ALGORITHM_IDS["ANALYZE_CANDIDATE"]
    cfg = env.cfg
    spec = cfg.measurement_spec(inp.measurement_spec_id)
    src = resolve_source(env, inp.source, roles=("EARTH_TERRAIN",))
    cell = float(cfg.algorithms.grid.cell_size_m)
    prep = prepare(src.raster, cell, cfg.algorithms.thresholds.flat_gradient_tolerance)
    win = find_window(cfg, inp.candidate.window_id, prep.grid)
    if not win.inside_source:
        raise OpBlocked(
            f"window {win.window_id} lies outside the source extent", code="NO_COVERAGE", detail_code="WINDOW_OUTSIDE"
        )
    env.check()
    rs = (slice(win.r0, win.r0 + win.height), slice(win.c0, win.c0 + win.width))
    surf = prep.surf
    quality = surf.quality[rs]
    summary = coverage_summary(quality)
    vf = summary.valid_fraction
    th = cfg.algorithms.thresholds
    if vf < th.hard_block_valid_fraction:
        raise OpBlocked(
            f"valid fraction {vf:.3f} of {win.window_id} is below the hard minimum {th.hard_block_valid_fraction}",
            code="INSUFFICIENT_VALID_DATA",
            affected=[],
        )
    wgrid = prep.grid.window(win.r0, win.c0, win.height, win.width)
    valid = surf.valid[rs]
    land = surf.land[rs]
    slope = np.where(valid, surf.slope_deg[rs], 0.0)
    elev = np.where(np.isfinite(prep.elevation[rs]), prep.elevation[rs], 0.0)
    params = env.params_hash(
        algo,
        env.operation_params(),
        [
            src.draft.parameters_sha256,
            *src.raster.source_hashes,
            *[f"bound-dataset:{d}" for d in sorted(env.request.source_policy.local_dataset_ids)],
        ],
    )
    grid = build_analysis_grid(
        wgrid,
        elevation_m=elev,
        valid=valid,
        land=land,
        slope_deg=slope,
        aspect_deg=surf.aspect_deg[rs],
        quality=quality,
        source_evidence_ids=(src.draft.local_key,),
        algorithm_id=algo,
        algorithm_version=env.algorithm_version(algo),
        parameters_sha256=params,
    )
    grid_bytes = encode_analysis_grid(grid)
    edges = tuple(float(e) for e in spec.slope_hist_edges_deg)
    cell_area = wgrid.cell_area_m2
    metrics = [metric("valid_fraction", vf, "fraction", prep.support_m, vf, "analysis-grid-npz-v1")]
    metrics += band_metrics(grid.slope_deg, grid.valid, cell_area, edges, prep.support_m, vf)
    metrics += slope_stat_metrics(grid.slope_deg, grid.valid, cell_area, prep.support_m, vf)
    usable = (quality == 0) | (quality == 3)
    metrics += roughness_metrics(
        prep.elevation[rs], usable, tuple(spec.roughness_windows_cells), prep.support_m, grid.valid, vf
    )
    parents = [src.draft.local_key]
    extra_evidence = []
    mineral_id = find_bound_dataset(env, "EARTH_MINERAL", "EARTH")
    if mineral_id is not None:
        from analogforge.ports.science_payloads import SourceSelector

        msrc = resolve_source(
            env, SourceSelector(kind="LOCAL_DATASET", dataset_id=mineral_id), roles=("EARTH_MINERAL",)
        )
        mg = msrc.raster.grid
        if (
            abs(mg.cell_size_m - cell) < 1e-9
            and abs(mg.origin_x_m - prep.grid.origin_x_m) < 1e-6
            and abs(mg.origin_y_m - prep.grid.origin_y_m) < 1e-6
            and mg.shape == prep.grid.shape
        ):
            ids = np.where(msrc.raster.nodata[rs], 0, np.nan_to_num(msrc.raster.values[rs], nan=0.0)).astype(int)
            present = ids > 0
            mvf = float(present.sum()) / float(present.size)
            metrics.append(
                metric(
                    "mineral_valid_fraction",
                    mvf if mvf > 0.0 else None,  # no retrieval in the window is unknown, never a zero
                    "fraction",
                    cell,
                    mvf,
                    "analysis-grid-npz-v1",
                    "Retrieval coverage; absence of retrieval is not absence of mineral.",
                )
            )
            for cid in sorted({int(v) for v in np.unique(ids[present])}):
                metrics.append(
                    metric(
                        f"mineral_class_fraction:{cid}",
                        float((ids == cid).sum()) / float(ids.size),
                        "fraction",
                        cell,
                        mvf,
                        "analysis-grid-npz-v1",
                        "Categorical area fraction; class ids are never interpolated.",
                    )
                )
            parents.append(msrc.draft.local_key)
            extra_evidence.append(msrc.draft)
            limitations_extra = [
                "Mineral classes are categorical (nearest/area-fraction only); retrievals cover part of the window."
            ]
        else:
            limitations_extra = ["A bound mineral dataset is not aligned with the analysis grid and was not used."]
    else:
        limitations_extra = []
    hist_data = hist_of(grid.slope_deg, grid.valid, cell_area, edges)
    hist = to_port_histogram(hist_data, support_scale_m=prep.support_m) if hist_data.valid_area_m2 > 0 else None

    cap = float(th.default_cap_deg)
    safe = safe_mask(grid.slope_deg, grid.valid, grid.land, cap)
    bands = [Band(lo, hi) for lo, hi in band_pairs(edges)]
    biggest = largest_component(safe)
    start = None
    if biggest is not None:
        rr, cc = np.nonzero(biggest)
        start = (int(rr[0]), int(cc[0]))
    zones, _ = connected_zones(safe, grid.slope_deg, cell_area, bands, start_cell=start, min_cells=4)
    issues: list[ScienceIssue] = []
    limitations = [
        f"Terrain model at {prep.support_m:g} m support; cannot resolve 0.20 m obstacles.",
        "Derivatives computed over the whole source extent and cropped to the window; "
        "cells next to nodata or water are not valid.",
    ]
    if prep.support_m > cell + 1e-9:
        limitations.append(f"Source is coarser than the {cell:g} m analysis cell; it was not upsampled.")
    limitations += limitations_extra
    status = ComputationStatus.SUCCEEDED
    if vf < th.min_valid_fraction:
        status = ComputationStatus.LIMITED
        issues.append(
            ScienceIssue(
                code="INSUFFICIENT_VALID_DATA",
                message=f"valid fraction {vf:.3f} is below the policy minimum {th.min_valid_fraction}",
                scope=win.window_id,
            )
        )
    grid_art = bytes_artifact(
        env,
        params_sha=params,
        key="analysis-grid",
        name="analysis-grid.npz",
        data=grid_bytes,
        media_type=MEDIA_TYPE,
        role=ArtifactRole.ANALYSIS_GRID,
        body="EARTH",
        crs_wkt=wgrid.crs_wkt,
        support_scale_m=prep.support_m,
    )
    payload = AnalyzeCandidatePayload(
        analysis_evidence=EvidenceRef(local_key="analysis"),
        analysis_grid_artifact_key=grid_art.local_key,
        metrics=metrics,
        slope_histogram=hist,
        connected_zones=[to_port_zone(z) for z in zones],
        coverage_fraction=vf,
        limitations=limitations,
    )
    sum_algo = catalog.ALGORITHM_IDS["ANALYSIS_SUMMARY"]
    sum_params = env.params_hash(sum_algo, env.operation_params(), [params])
    sum_art = json_artifact(
        env, params_sha=sum_params, key="analysis-summary-json", name="analysis-summary.json", payload=payload
    )
    ev_grid = derived_evidence(
        env,
        key="analysis",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=grid_art,
        parent_keys=parents,
        metrics=metrics,
        limitations=limitations,
        native_resolution_m=src.raster.native_resolution_m,
        comparison_scale_m=prep.support_m,
        dataset_product_id=src.product_id,
    )
    ev_sum = derived_evidence(
        env,
        key="analysis-summary",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=sum_algo,
        params_sha=sum_params,
        artifact=sum_art,
        parent_keys=["analysis"],
        metrics=metrics,
        limitations=limitations,
        native_resolution_m=src.raster.native_resolution_m,
        comparison_scale_m=prep.support_m,
    )
    return OpOutcome(
        status, payload, algo, params, [grid_art, sum_art], [src.draft, *extra_evidence, ev_grid, ev_sum], issues
    )
