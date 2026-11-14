"""``CHARACTERIZE_TARGET`` (guide 08 section 4.4): slope statistics of the Moon/Mars target AOI."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.science import ArtifactRole, ComputationStatus
from analogforge.ports.science_payloads import (
    CharacterizeTargetInput,
    CharacterizeTargetPayload,
    UnavailableDimension,
)
from analogforge.science.features.histogram import to_port_histogram
from analogforge.science.geometry import (
    bbox_to_projected_bounds,
    frame_from_crs_wkt,
    unwrap_bbox,
    xy_to_lonlat,
)
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, bytes_artifact, derived_evidence, json_artifact
from analogforge.science.ops.source import ResolvedSource, find_bound_dataset, resolve_source, source_limitations
from analogforge.science.ops.terrain import (
    hist_of,
    metric,
    prepare,
    roughness_metrics,
    slope_stat_metrics,
)
from analogforge.science.raster.store import MEDIA_TYPE, build_analysis_grid, encode_analysis_grid

MAX_AOI_CELLS = 64_000_000


def _aoi_mask(aoi: AreaOfInterest, frame, x: np.ndarray, y: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
    """Cells whose centre lies inside the lon/lat AOI (wedges and longitude wrap handled in lon/lat space)."""
    lon, lat = xy_to_lonlat(frame, x, y, aoi.longitude_convention)
    lo, south, hi, north = unwrap_bbox(tuple(aoi.bbox), aoi.longitude_convention)  # type: ignore[arg-type]
    rel = (lon - lo) % 360.0
    in_lon = rel <= (hi - lo) + 1e-9
    return np.asarray(in_lon & (lat >= south - 1e-9) & (lat <= north + 1e-9), dtype=bool)


_COUNT_CHUNK_ROWS = 256


def _aoi_cell_count(  # type: ignore[no-untyped-def]
    aoi: AreaOfInterest, frame, g, r0: int, r1: int, c0: int, c1: int, check: Callable[[], None]
) -> int:
    """Cells of the (unclipped) row/column range ``[r0, r1) x [c0, c1)`` whose centre lies inside the AOI.

    The range may extend beyond the dataset: the denominator of the valid fraction is the whole AOI, so the part
    of the AOI outside the dataset counts as missing, never as absent.  Rows are processed in chunks.
    """
    check()
    if max(0, r1 - r0) * max(0, c1 - c0) > MAX_AOI_CELLS:
        raise OpBlocked("The target AOI exceeds the bounded analysis cell budget", code="RESOURCE_LIMIT")
    cols = g.origin_x_m + (np.arange(c0, c1) + 0.5) * g.cell_size_m
    total = 0
    for start in range(r0, r1, _COUNT_CHUNK_ROWS):
        check()
        rows = np.arange(start, min(r1, start + _COUNT_CHUNK_ROWS))
        ys = g.origin_y_m - (rows + 0.5) * g.cell_size_m
        xx, yy = np.meshgrid(cols, ys)
        total += int(_aoi_mask(aoi, frame, xx, yy).sum())
    return total


def run_characterize(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, CharacterizeTargetInput)
    algo = catalog.ALGORITHM_IDS["CHARACTERIZE_TARGET"]
    cfg = env.cfg
    spec = cfg.measurement_spec(inp.measurement_spec_id)
    src = resolve_source(env, inp.source, roles=("TARGET_TERRAIN",))
    if src.body != inp.target.body:
        raise OpBlocked(
            f"source body {src.body} differs from target body {inp.target.body}",
            code="UNSUPPORTED_CRS",
            detail_code="BODY_MISMATCH",
        )
    frame = frame_from_crs_wkt(src.body, src.raster.grid.crs_wkt)
    prep = prepare(src.raster, spec.comparison_support.default_requested_m,
                   cfg.algorithms.thresholds.flat_gradient_tolerance)
    env.check()
    aoi = inp.target
    xmin, ymin, xmax, ymax = bbox_to_projected_bounds(frame, tuple(aoi.bbox), aoi.longitude_convention)  # type: ignore[arg-type]
    g = prep.grid
    uc0 = int(np.floor((xmin - g.origin_x_m) / g.cell_size_m))
    uc1 = int(np.ceil((xmax - g.origin_x_m) / g.cell_size_m))
    ur0 = int(np.floor((g.origin_y_m - ymax) / g.cell_size_m))
    ur1 = int(np.ceil((g.origin_y_m - ymin) / g.cell_size_m))
    c0, c1, r0, r1 = max(0, uc0), min(g.width, uc1), max(0, ur0), min(g.height, ur1)
    if c1 <= c0 or r1 <= r0:
        raise OpBlocked("the target AOI does not intersect the dataset", code="NO_COVERAGE")
    sub = g.window(r0, c0, r1 - r0, c1 - c0)
    x, y = sub.centre_coordinates()
    mask = _aoi_mask(aoi, frame, x, y)
    if not mask.any():
        raise OpBlocked("no cell centre of the dataset lies inside the target AOI", code="NO_COVERAGE")
    rs = (slice(r0, r1), slice(c0, c1))
    surf = prep.surf
    quality = surf.quality[rs]
    valid = surf.valid[rs] & mask
    # denominator: every AOI cell, including the part outside the dataset (outside is missing data, not absent area)
    aoi_cells = max(int(mask.sum()), _aoi_cell_count(aoi, frame, g, ur0, ur1, uc0, uc1, env.check))
    vf = float(valid.sum()) / float(aoi_cells)
    if vf < cfg.algorithms.thresholds.hard_block_valid_fraction:
        raise OpBlocked(
            f"valid fraction {vf:.3f} of the target AOI is below the hard minimum",
            code="INSUFFICIENT_VALID_DATA",
        )
    slope = np.where(valid, surf.slope_deg[rs], 0.0)
    cell_area = sub.cell_area_m2
    edges = tuple(float(e) for e in spec.slope_hist_edges_deg)
    hist_data = hist_of(slope, valid, cell_area, edges)
    hist = to_port_histogram(hist_data, support_scale_m=prep.support_m) if hist_data.valid_area_m2 > 0 else None
    thermal_id = find_bound_dataset(env, "LUNAR_THERMAL", src.body)
    thermal_metrics = []
    thermal_sources: list[ResolvedSource] = []
    if thermal_id is not None and "THERMAL" in inp.requested_dimensions:
        thermal_metrics, thermal_source = _thermal_metric(env, thermal_id, aoi)
        thermal_sources.append(thermal_source)
    params = env.params_hash(
        algo,
        env.operation_params(),
        [
            src.draft.parameters_sha256,
            *src.raster.source_hashes,
            *[value for source in thermal_sources for value in source.raster.source_hashes],
            *[f"bound-dataset:{d}" for d in sorted(env.request.source_policy.local_dataset_ids)],
        ],
    )
    metrics = [metric("valid_fraction", vf, "fraction", prep.support_m, vf, "analysis-grid-npz-v1")]
    metrics += slope_stat_metrics(slope, valid, cell_area, prep.support_m, vf)
    usable = ((quality == 0) | (quality == 3)) & mask
    metrics += roughness_metrics(
        prep.elevation[rs], usable, tuple(spec.roughness_windows_cells), prep.support_m, valid, vf
    )
    unavailable: list[UnavailableDimension] = []
    for dim in dict.fromkeys(inp.requested_dimensions):
        if dim == "THERMAL" and not thermal_metrics:
            unavailable.append(
                UnavailableDimension(
                    dimension=dim, reason_code="NO_COVERAGE", message="No thermal dataset is bound to this target."
                )
            )
        elif dim == "SCIENCE":
            unavailable.append(
                UnavailableDimension(
                    dimension=dim,
                    reason_code="NO_COVERAGE",
                    message="No target mineral dataset is available in this build.",
                )
            )
    metrics += thermal_metrics
    limitations = [
        f"Terrain model at {prep.support_m:g} m support; cannot resolve 0.20 m obstacles.",
        "Statistics are area weighted over valid cells inside the AOI; cells next to nodata are not valid.",
        *source_limitations(src.manifest),
    ]
    grid = build_analysis_grid(
        sub,
        elevation_m=np.where(np.isfinite(prep.elevation[rs]), prep.elevation[rs], 0.0),
        valid=valid,
        land=surf.land[rs],
        slope_deg=slope,
        aspect_deg=surf.aspect_deg[rs],
        quality=quality,
        source_evidence_ids=(src.draft.local_key,),
        algorithm_id=algo,
        algorithm_version=env.algorithm_version(algo),
        parameters_sha256=params,
    )
    payload = CharacterizeTargetPayload(
        profile_evidence=EvidenceRef(local_key="profile"),
        metrics=metrics,
        slope_histogram=hist,
        comparison_support_m=prep.support_m,
        unavailable_dimensions=unavailable,
    )
    json_art = json_artifact(env, params_sha=params, key="profile-json", name="profile.json", payload=payload)
    grid_params = env.params_hash(algo, {"target_grid": True, **env.operation_params()}, [params])
    grid_art = bytes_artifact(
        env,
        params_sha=params,
        key="target-grid",
        name="target-grid.npz",
        data=encode_analysis_grid(grid),
        media_type=MEDIA_TYPE,
        role=ArtifactRole.ANALYSIS_GRID,
        body=src.body,
        crs_wkt=sub.crs_wkt,
        support_scale_m=prep.support_m,
    )
    profile = derived_evidence(
        env,
        key="profile",
        kind="DERIVED",
        body=src.body,
        algorithm_id=algo,
        params_sha=params,
        artifact=json_art,
        parent_keys=[src.draft.local_key, *[source.draft.local_key for source in thermal_sources]],
        metrics=metrics,
        limitations=limitations,
        native_resolution_m=src.raster.native_resolution_m,
        comparison_scale_m=prep.support_m,
        aoi_bbox=(aoi.bbox[0], aoi.bbox[1], aoi.bbox[2], aoi.bbox[3]),
        dataset_product_id=src.product_id,
    )
    target_grid = derived_evidence(
        env,
        key="target-grid",
        kind="DERIVED",
        body=src.body,
        algorithm_id=algo,
        params_sha=grid_params,
        artifact=grid_art,
        parent_keys=["profile"],
        limitations=limitations,
        native_resolution_m=src.raster.native_resolution_m,
        comparison_scale_m=prep.support_m,
    )
    return OpOutcome(
        ComputationStatus.SUCCEEDED, payload, algo, params, [json_art, grid_art],
        [src.draft, *[source.draft for source in thermal_sources], profile, target_grid],
    )


def _thermal_metric(env: OpEnv, dataset_id: str, aoi: AreaOfInterest):  # type: ignore[no-untyped-def]
    from analogforge.ports.science_payloads import SourceSelector

    src = resolve_source(env, SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset_id), roles=("LUNAR_THERMAL",))
    g = src.raster.grid
    frame = frame_from_crs_wkt(src.body, g.crs_wkt)
    x, y = g.centre_coordinates()
    mask = _aoi_mask(aoi, frame, x, y) & ~src.raster.nodata
    if not mask.any():
        return [], src
    bbox = (aoi.bbox[0], aoi.bbox[1], aoi.bbox[2], aoi.bbox[3])
    xmin, ymin, xmax, ymax = bbox_to_projected_bounds(frame, bbox, aoi.longitude_convention)
    c0 = int(np.floor((xmin - g.origin_x_m) / g.cell_size_m))
    c1 = int(np.ceil((xmax - g.origin_x_m) / g.cell_size_m))
    r0 = int(np.floor((g.origin_y_m - ymax) / g.cell_size_m))
    r1 = int(np.ceil((g.origin_y_m - ymin) / g.cell_size_m))
    denominator = max(int(mask.sum()), _aoi_cell_count(aoi, frame, g, r0, r1, c0, c1, env.check))
    vf = float(mask.sum()) / float(denominator)
    value = float(np.min(src.raster.values[mask]))
    return [
        metric(
            "min_temperature_k",
            value,
            "K",
            src.raster.native_resolution_m,
            vf,
            "thermal-min-v1",
            "Product statistic; variable and local time unresolved in v1.",
        )
    ], src
