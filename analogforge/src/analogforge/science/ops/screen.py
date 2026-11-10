"""``SCREEN_CANDIDATES`` (guide 08 section 4.5, architecture 40 section 4.1)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import MeasuredMetric
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import (
    Histogram,
    ScreenCandidatesInput,
    ScreenCandidatesPayload,
    ScreenedWindow,
)
from analogforge.science.comparison.w1 import w1_from_histograms
from analogforge.science.errors import ScienceError
from analogforge.science.features.coverage import coverage_summary, is_water_only
from analogforge.science.features.histogram import band_area_fraction, slope_area_metric_id, to_port_histogram
from analogforge.science.geometry import ProjectedFrame, frame_from_crs_wkt
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.ops.source import resolve_source
from analogforge.science.ops.terrain import Prepared, aoi_for_bounds, hist_of, metric, prepare
from analogforge.science.ops.windows import WindowSpec, region_windows


@dataclass
class _Row:
    spec: WindowSpec
    excluded: bool
    reason: str | None
    valid_fraction: float | None
    f_bands: dict[tuple[float, float], float | None]
    deficit: float | None
    w1: float | None
    hist: Histogram | None


def _w1_for_window(
    prep_s: Prepared | None, spec: WindowSpec, factor_ratio: int, target: Histogram | None, edges: tuple[float, ...]
) -> tuple[float | None, Histogram | None]:
    if prep_s is None or target is None or factor_ratio < 1:
        return None, None
    n = spec.height
    if spec.r0 % factor_ratio or spec.c0 % factor_ratio or n % factor_ratio:
        return None, None
    h = n // factor_ratio
    r0, c0 = spec.r0 // factor_ratio, spec.c0 // factor_ratio
    rs = (slice(r0, r0 + h), slice(c0, c0 + h))
    if r0 + h > prep_s.grid.height or c0 + h > prep_s.grid.width:
        return None, None
    valid = prep_s.surf.valid[rs]
    slope = prep_s.surf.slope_deg[rs]
    data = hist_of(slope, valid, prep_s.grid.cell_area_m2, edges)
    if data.valid_area_m2 <= 0 or list(edges) != list(target.edges):
        return None, None
    hist = to_port_histogram(data, support_scale_m=prep_s.support_m)
    return w1_from_histograms(target, hist).w1_deg, hist


def run_screen(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, ScreenCandidatesInput)
    algo = catalog.ALGORITHM_IDS["SCREEN_CANDIDATES"]
    cfg = env.cfg
    th = cfg.algorithms.thresholds
    rs_cfg = cfg.candidates.search_region_sets.get(inp.search_region_set_id)
    if rs_cfg is None:
        raise OpBlocked(f"unknown search_region_set_id {inp.search_region_set_id!r}", detail_code="REGION_SET_UNKNOWN")
    ref_set = cfg.candidates.reference_sets.get(inp.reference_set_id)
    if ref_set is None:
        raise OpBlocked(f"unknown reference_set_id {inp.reference_set_id!r}", detail_code="REFERENCE_SET_UNKNOWN")
    known = {e.window_id for e in ref_set.entries}
    src = resolve_source(env, inp.source, roles=("EARTH_TERRAIN",))
    cell = float(cfg.algorithms.grid.cell_size_m)
    prep = prepare(src.raster, cell, th.flat_gradient_tolerance)
    specs = region_windows(rs_cfg, prep.grid)
    stop_reason = "GRID_EXHAUSTED"
    limitations = [
        "Bounded search over the declared window grid; no global-optimality claim.",
        f"reference_set={inp.reference_set_id} (membership is not a claim of historical novelty).",
        "Feature scores are mission deficits and a distribution distance, not similarity percentages.",
    ]
    if len(specs) > rs_cfg.coarse_windows_max:
        specs = specs[: rs_cfg.coarse_windows_max]
        stop_reason = "WINDOW_CAP_REACHED"
        limitations.append(f"Only the first {rs_cfg.coarse_windows_max} windows were screened (coarse window cap).")
    edges = tuple(float(e) for e in cfg.measurement_spec(catalog.MEASUREMENT_SPEC_EARTH).slope_hist_edges_deg)
    target = inp.target_histogram
    prep_s: Prepared | None = None
    ratio = 0
    if target is None:
        limitations.append("No target slope histogram supplied: the distribution distance is unavailable.")
    elif target.support_scale_m < cell - 1e-9:
        limitations.append("Target support is finer than the Earth analysis cell; no upsampling, distance unavailable.")
    else:
        ratio = round(target.support_scale_m / cell)
        if abs(ratio * cell - target.support_scale_m) > 1e-6:
            limitations.append("Target support is not a whole multiple of the analysis cell; distance unavailable.")
            ratio = 0
        else:
            prep_s = prep if ratio == 1 else prepare(src.raster, target.support_scale_m, th.flat_gradient_tolerance)
    bands: list[tuple[float, float]] = []
    for req in inp.requirements:
        b = req.parameters.slope_band_deg
        if b is not None and len(b) == 2 and (float(b[0]), float(b[1])) not in bands:
            bands.append((float(b[0]), float(b[1])))
    slope_reqs = [
        r
        for r in inp.requirements
        if r.observable == "slope_band_area_fraction"
        and r.lower is not None
        and r.parameters.slope_band_deg is not None
        and len(r.parameters.slope_band_deg) == 2
    ]
    rows: list[_Row] = []
    cell_area = prep.grid.cell_area_m2
    for i, spec in enumerate(specs):
        env.check()
        env.context.report_progress("screen", i, len(specs))
        if not spec.inside_source:
            rows.append(_Row(spec, True, "NO_COVERAGE", None, {}, None, None, None))
            continue
        rs = (slice(spec.r0, spec.r0 + spec.height), slice(spec.c0, spec.c0 + spec.width))
        summary = coverage_summary(prep.surf.quality[rs])
        if is_water_only(summary, th.water_only_fraction):
            rows.append(_Row(spec, True, "WATER_ONLY", summary.valid_fraction, {}, None, None, None))
            continue
        if summary.valid_fraction < th.min_valid_fraction:
            rows.append(_Row(spec, True, "INSUFFICIENT_VALID_DATA", summary.valid_fraction, {}, None, None, None))
            continue
        valid, slope = prep.surf.valid[rs], prep.surf.slope_deg[rs]
        f_bands = {b: band_area_fraction(slope, valid, b[0], b[1], cell_area) for b in bands}
        deficits = []
        for rq0 in slope_reqs:
            assert rq0.lower is not None and rq0.parameters.slope_band_deg is not None
            bk = (float(rq0.parameters.slope_band_deg[0]), float(rq0.parameters.slope_band_deg[1]))
            frac = f_bands.get(bk)
            deficits.append(max(0.0, rq0.lower - (frac if frac is not None else 0.0)))
        w1, hist = _w1_for_window(prep_s, spec, ratio, target, edges)
        rows.append(_Row(spec, False, None, summary.valid_fraction, f_bands, max(deficits, default=0.0), w1, hist))

    ranked = sorted(
        (r for r in rows if not r.excluded),
        key=lambda r: (
            r.deficit if r.deficit is not None else math.inf,
            r.w1 if r.w1 is not None else math.inf,
            r.spec.window_id,
        ),
    )
    rank_of = {r.spec.window_id: i + 1 for i, r in enumerate(ranked)}
    controls = [r for r in ranked if r.spec.negative_control]
    others = [r for r in ranked if not r.spec.negative_control]
    take = max(0, inp.max_detailed - len(controls))
    shortlist_ids = {r.spec.window_id for r in others[:take]} | {r.spec.window_id for r in controls}
    shortlist = [r.spec.window_id for r in ranked if r.spec.window_id in shortlist_ids]
    shortlist = shortlist[: inp.max_detailed]
    shortlist_ids = set(shortlist)

    frame: ProjectedFrame = frame_from_crs_wkt("EARTH", prep.grid.crs_wkt)
    params = env.params_hash(algo, env.operation_params(), [src.draft.parameters_sha256, *src.raster.source_hashes])
    evidence = [src.draft]
    windows_out: list[ScreenedWindow] = []
    support_for_w1 = prep_s.support_m if prep_s is not None else None
    for r in rows:
        spec = r.spec
        g = prep.grid.window(spec.r0, spec.c0, spec.height, spec.width) if spec.inside_source else None
        bounds = g.bounds if g is not None else (0.0, 0.0, 1.0, 1.0)
        aoi = aoi_for_bounds(frame, bounds, src.manifest.vertical_reference)
        is_known = spec.window_id in known
        origin = "KNOWN_CONTROL" if is_known else "SYNTHETIC_CONTROL" if spec.negative_control else "DISCOVERED"
        novelty = "KNOWN_ANALOG" if is_known else "NOT_IN_REFERENCE_LIST"
        scores: dict[str, float | None] = {}
        for rq in slope_reqs:
            assert rq.lower is not None and rq.parameters.slope_band_deg is not None
            bk = (float(rq.parameters.slope_band_deg[0]), float(rq.parameters.slope_band_deg[1]))
            frac = r.f_bands.get(bk)
            scores[f"deficit:{rq.id}"] = (
                None if r.excluded else max(0.0, rq.lower - (frac if frac is not None else 0.0))
            )
        scores["slope_w1_deg"] = r.w1
        ev_ref: EvidenceRef | None = None
        reason = r.reason
        if not r.excluded:
            key = f"window-{spec.window_id}"
            ms: list[MeasuredMetric] = []
            if r.valid_fraction is not None:
                ms.append(
                    metric(
                        "valid_fraction", r.valid_fraction, "fraction", cell, r.valid_fraction, "analysis-grid-npz-v1"
                    )
                )
                for (lo, hi), frac in r.f_bands.items():
                    ms.append(
                        metric(
                            slope_area_metric_id(lo, hi),
                            frac,
                            "fraction",
                            cell,
                            r.valid_fraction,
                            "slope-lsq-plane-3x3-v1",
                        )
                    )
            if r.w1 is not None and support_for_w1 is not None:
                ms.append(
                    metric("slope_w1_deg", r.w1, "deg", support_for_w1, r.valid_fraction or 0.0, "slope-w1-binned-v1")
                )
            w_params = env.params_hash(algo, {"window": spec.window_id, **env.operation_params()}, [params])
            evidence.append(
                derived_evidence(
                    env,
                    key=key,
                    kind="DERIVED",
                    body="EARTH",
                    algorithm_id=algo,
                    params_sha=w_params,
                    artifact=None,
                    parent_keys=[src.draft.local_key],
                    metrics=ms,
                    limitations=[f"Coarse screening summary of {spec.window_id} at {cell:g} m support."],
                    native_resolution_m=src.raster.native_resolution_m,
                    comparison_scale_m=support_for_w1 if support_for_w1 is not None else cell,
                    aoi_bbox=(aoi.bbox[0], aoi.bbox[1], aoi.bbox[2], aoi.bbox[3]),
                    dataset_product_id=src.product_id,
                )
            )
            ev_ref = EvidenceRef(local_key=key)
            if spec.window_id not in shortlist_ids:
                reason = "BELOW_SHORTLIST_CUTOFF"
        windows_out.append(
            ScreenedWindow(
                window_id=spec.window_id,
                name=catalog.PRACTICE_CANDIDATE_NAME_PREFIX + spec.window_id,
                aoi=aoi,
                origin=origin,
                novelty_status=novelty,
                rank=None if r.excluded else rank_of[spec.window_id],
                excluded=r.excluded,
                exclusion_reason=reason,
                feature_scores=scores,
                is_negative_control=spec.negative_control,
                evidence=ev_ref,
            )
        )
    xs = [w.aoi.bbox for w in windows_out]
    extent = windows_out[0].aoi.model_copy(
        update={"bbox": [min(b[0] for b in xs), min(b[1] for b in xs), max(b[2] for b in xs), max(b[3] for b in xs)]}
    )
    payload = ScreenCandidatesPayload(
        screened_count=len(rows),
        windows=windows_out,
        shortlist_window_ids=shortlist,
        stop_reason=stop_reason,
        search_extent=extent,
        limitations=limitations,
    )
    art = json_artifact(env, params_sha=params, key="screening-json", name="screening.json", payload=payload)
    evidence.append(
        derived_evidence(
            env,
            key="screening",
            kind="DERIVED",
            body="EARTH",
            algorithm_id=algo,
            params_sha=params,
            artifact=art,
            parent_keys=[e.local_key for e in evidence if e.local_key != src.draft.local_key] + [src.draft.local_key],
            limitations=limitations,
            native_resolution_m=src.raster.native_resolution_m,
            comparison_scale_m=support_for_w1,
            dataset_product_id=src.product_id,
        )
    )
    if not windows_out:
        raise ScienceError("no windows were produced", code="NO_COVERAGE")
    counters: dict[str, int | float] = {"windows_screened": len(rows), "windows_ranked": len(ranked)}
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], evidence, [], counters)
