"""``SCREEN_CANDIDATES`` (guide 08 section 4.5, architecture 40 section 4.1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import partial

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import (
    Histogram,
    ScreenCandidatesInput,
    ScreenCandidatesPayload,
    ScreenedWindow,
)
from analogforge.science.comparison.scale import check_support_window
from analogforge.science.comparison.w1 import w1_from_histograms
from analogforge.science.errors import ScienceError
from analogforge.science.features.coverage import coverage_summary, is_water_only
from analogforge.science.features.histogram import band_area_fraction, slope_area_metric_id, to_port_histogram
from analogforge.science.geometry import ProjectedFrame, frame_from_crs_wkt
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.ops.source import resolve_source
from analogforge.science.ops.terrain import Prepared, aoi_for_bounds, hist_of, metric, prepare
from analogforge.science.ops.windows import WindowSpec, region_windows

SHORTLIST_POLICY_ID = "requirement-diversity-greedy-v1"


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


def _supported_requirement(req: Requirement, support_m: float, w1_support_m: float | None = None) -> bool:
    if req.observable == "slope_distribution_w1_deg":
        return (req.operator == "LTE" and req.upper is not None and req.unit == "deg"
                and w1_support_m is not None and check_support_window(
                    w1_support_m, req.minimum_support_scale_m, req.maximum_support_scale_m
                ).supported)
    band = req.parameters.slope_band_deg
    return (req.observable == "slope_band_area_fraction" and req.operator == "GTE"
            and req.lower is not None and req.unit == "fraction" and band is not None and len(band) == 2
            and 0 <= band[0] < band[1] <= 90 and check_support_window(
                support_m, req.minimum_support_scale_m, req.maximum_support_scale_m
            ).supported)


def _shortlist(
    ranked: list[_Row], requirements: list[Requirement], cap: int, support_m: float,
    w1_support_m: float | None = None,
) -> list[str]:
    """Retain complementary measured screening advice within the existing detail cap.

    This greedy policy is not qualification or a coverage-optimal portfolio.
    Declared negative controls retain their existing reserved slots. Remaining
    slots prefer new mandatory then optional threshold representation, followed
    by the distinct observed deficits improved, then the existing rank/id order.
    Improvement magnitudes in degrees and fractions are never added together.
    A coupled item is represented only when all its reproducible members have
    supported screening quantities in the same window.
    """
    reqs = sorted((r for r in requirements if r.operator != "NOT_NATURALLY_REPRODUCIBLE"), key=lambda r: r.id)
    groups: dict[str, list[Requirement]] = {}
    items: list[list[Requirement]] = []
    for req in reqs:
        group = req.parameters.co_location_group
        if group is not None:
            groups.setdefault(group, []).append(req)
        elif _supported_requirement(req, support_m, w1_support_m):
            items.append([req])
    items += [members for _, members in sorted(groups.items())
              if all(_supported_requirement(member, support_m, w1_support_m) for member in members)]
    supported = [req for req in reqs if _supported_requirement(req, support_m, w1_support_m)]

    def deficit(row: _Row, req: Requirement) -> float | None:
        if req.observable == "slope_distribution_w1_deg":
            assert req.upper is not None
            return (max(0.0, row.w1 - req.upper)
                    if row.w1 is not None and math.isfinite(row.w1) and row.w1 >= 0 else None)
        band = req.parameters.slope_band_deg
        assert band is not None and req.lower is not None
        value = row.f_bands.get((float(band[0]), float(band[1])))
        return (max(0.0, req.lower - value)
                if value is not None and math.isfinite(value) and 0 <= value <= 1 else None)

    deficits = {(row.spec.window_id, req.id): deficit(row, req) for row in ranked for req in supported}
    represented = {row.spec.window_id: {i for i, members in enumerate(items)
        if all(deficits[(row.spec.window_id, req.id)] == 0.0 for req in members)} for row in ranked}
    selected = [row for row in ranked if row.spec.negative_control][:cap]
    remaining = [row for row in ranked if not row.spec.negative_control]
    order = {row.spec.window_id: i for i, row in enumerate(ranked)}

    def gain(
        row: _Row, *, covered: set[int], best_observed: dict[str, float],
    ) -> tuple[float, float, float, float, int]:
        newly = [req for i in sorted(represented[row.spec.window_id] - covered) for req in items[i]]
        improved = {req.id for req in supported if req.id in best_observed
            and (value := deficits[(row.spec.window_id, req.id)]) is not None and value < best_observed[req.id]}
        return (
            math.fsum(req.weight for req in newly if req.mandatory),
            math.fsum(req.weight for req in newly if not req.mandatory),
            math.fsum(req.weight for req in supported if req.mandatory and req.id in improved),
            math.fsum(req.weight for req in supported if not req.mandatory and req.id in improved),
            -order[row.spec.window_id],
        )

    while remaining and len(selected) < cap:
        covered: set[int] = set().union(*(represented[row.spec.window_id] for row in selected)) if selected else set()
        best_observed: dict[str, float] = {}
        for req in supported:
            known = [value for row in selected if (value := deficits[(row.spec.window_id, req.id)]) is not None]
            if known:
                best_observed[req.id] = min(known)

        chosen = max(remaining, key=partial(gain, covered=covered, best_observed=best_observed))
        selected.append(chosen)
        remaining.remove(chosen)
    selected_ids = {row.spec.window_id for row in selected}
    return [row.spec.window_id for row in ranked if row.spec.window_id in selected_ids]


def _w1_for_window(
    prep_s: Prepared | None, spec: WindowSpec, fine_cell: float, target: Histogram | None, edges: tuple[float, ...]
) -> tuple[float | None, Histogram | None]:
    if prep_s is None or target is None:
        return None, None
    ratio = prep_s.support_m / fine_cell
    # Only complete coarse footprints contained in this window contribute.
    r0, c0 = math.ceil(spec.r0 / ratio - 1e-9), math.ceil(spec.c0 / ratio - 1e-9)
    r1 = math.floor((spec.r0 + spec.height) / ratio + 1e-9)
    c1 = math.floor((spec.c0 + spec.width) / ratio + 1e-9)
    rs = (slice(r0, r1), slice(c0, c1))
    if r1 <= r0 or c1 <= c0 or r1 > prep_s.grid.height or c1 > prep_s.grid.width:
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
    src = resolve_source(env, inp.source, roles=("EARTH_TERRAIN",))
    # Practice window ids also occur in generated grids; those ids alone do not
    # establish that real terrain is a known analog or a synthetic control.
    known = {e.window_id for e in ref_set.entries if not e.synthetic or src.manifest.is_synthetic
             and rs_cfg.kind == "FIXED_GRID"}
    cell = float(cfg.algorithms.grid.cell_size_m)
    prep = prepare(src.raster, cell, th.flat_gradient_tolerance)
    cell = prep.support_m
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
    if not specs:
        raise ScienceError("No complete candidate windows fit the declared source grid.", code="NO_COVERAGE",
                           detail_code="NO_COMPLETE_WINDOWS")
    limitations += [
        f"shortlist_policy={SHORTLIST_POLICY_ID}: greedy retention of complementary measured requirements; "
        "not an optimal portfolio or a qualification result.",
        "Supported GTE slope-area fractions and LTE slope-W1 requirements at their actual common support guide "
        "shortlist diversity; degree and fraction deficit magnitudes are never added. Other observables "
        "receive no requirement representation credit from this policy, and unresolved quantities remain unknown.",
        "Declared negative controls retain their reserved detail slots within the same candidate cap.",
    ]
    edges = tuple(float(e) for e in cfg.measurement_spec(catalog.MEASUREMENT_SPEC_EARTH).slope_hist_edges_deg)
    target = inp.target_histogram
    prep_s: Prepared | None = None
    if target is None:
        limitations.append("No target slope histogram supplied: the distribution distance is unavailable.")
    elif target.support_scale_m < cell - 1e-9:
        limitations.append("Target support is finer than the Earth analysis cell; no upsampling, distance unavailable.")
    else:
        prep_s = prep if abs(target.support_scale_m - cell) < 1e-9 else prepare(
            src.raster, target.support_scale_m, th.flat_gradient_tolerance)
    bands: list[tuple[float, float]] = []
    for req in inp.requirements:
        b = req.parameters.slope_band_deg
        if b is not None and len(b) == 2 and (float(b[0]), float(b[1])) not in bands:
            bands.append((float(b[0]), float(b[1])))
    slope_reqs = [
        r
        for r in inp.requirements
        if r.observable == "slope_band_area_fraction" and _supported_requirement(r, cell)
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
            if frac is not None:
                deficits.append(max(0.0, rq0.lower - frac))
        w1, hist = _w1_for_window(prep_s, spec, cell, target, edges)
        deficit = max(deficits, default=0.0) if len(deficits) == len(slope_reqs) else None
        rows.append(_Row(spec, False, None, summary.valid_fraction, f_bands, deficit, w1, hist))

    ranked = sorted(
        (r for r in rows if not r.excluded),
        key=lambda r: (
            r.deficit if r.deficit is not None else math.inf,
            r.w1 if r.w1 is not None else math.inf,
            r.spec.window_id,
        ),
    )
    rank_of = {r.spec.window_id: i + 1 for i, r in enumerate(ranked)}
    shortlist = _shortlist(ranked, inp.requirements, inp.max_detailed, cell,
                           prep_s.support_m if prep_s is not None else None)
    shortlist_ids = set(shortlist)

    frame: ProjectedFrame = frame_from_crs_wkt("EARTH", prep.grid.crs_wkt)
    params = env.params_hash(algo, env.operation_params(), [src.draft.parameters_sha256, *src.raster.source_hashes])
    evidence = [src.draft]
    # Window evidence records are created after the payload artifact exists: architecture 35 s5b requires every
    # evidence carrying this operation's algorithm id to hold the operation payload as its artifact (content-addressed,
    # stored once); its own metrics stay per-window. This also gives every derived record real bytes (SC-02).
    pending_windows: list[dict[str, object]] = []
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
                None if r.excluded or frac is None else max(0.0, rq.lower - frac)
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
            w_scale = support_for_w1 if support_for_w1 is not None else cell
            pending_windows.append(
                dict(
                    key=key,
                    kind="DERIVED",
                    body="EARTH",
                    algorithm_id=algo,
                    params_sha=w_params,
                    parent_keys=[src.draft.local_key],
                    metrics=ms,
                    limitations=[f"Coarse screening summary of {spec.window_id} at {cell:g} m support."],
                    native_resolution_m=src.raster.native_resolution_m,
                    comparison_scale_m=w_scale,
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
                name=(catalog.PRACTICE_CANDIDATE_NAME_PREFIX if src.manifest.is_synthetic else "Terrain ")
                + spec.window_id,
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
    for spec_kwargs in pending_windows:
        evidence.append(derived_evidence(env, artifact=art, **spec_kwargs))  # type: ignore[arg-type]
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
    artifacts = [art]
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, artifacts, evidence, [], counters)
