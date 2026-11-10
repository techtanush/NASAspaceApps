"""``BUILD_DISPLAY_LAYERS`` (guide 08 section 4.14): wraps :mod:`analogforge.science.display`.

Terrain layers use cited ANALYSIS_GRID artifacts. Optional layers use validated,
immutable normalized sources. Missing data is reported explicitly.
"""

from __future__ import annotations

import numpy as np

from analogforge.ports.common import EvidenceRef, ScienceIssue
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import BuildDisplayLayersInput, SourceSelector
from analogforge.science.display.layers import LayerRaster, build_display_layers, layer_from_analysis_grid
from analogforge.science.features.roughness import detrended_rms_height_m
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.ops.source import resolve_source
from analogforge.science.raster.store import decode_analysis_grid

NPZ = "application/x-npz"


def run_display(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, BuildDisplayLayersInput)
    algo = "build-display-layers"
    handles = [env.handle(i) for i in inp.evidence_ids]
    if any(h.mode != env.request.mode for h in handles):
        raise OpBlocked("Display evidence mode differs from the request", detail_code="MODE_MISMATCH")
    if len({h.body for h in handles}) != 1:
        raise OpBlocked("Display layers must belong to one body", detail_code="BODY_MISMATCH")
    grids = [h for h in handles if h.artifact_media_type == NPZ and h.kind != "SOURCE"]
    sources = [h for h in handles if h.artifact_media_type == NPZ and h.kind == "SOURCE"]
    if not grids and not sources:
        raise OpBlocked(
            "none of the cited evidence carries an analysis grid to display",
            code="NO_COVERAGE",
            detail_code="NO_DISPLAYABLE_EVIDENCE",
        )
    if len(grids) > 1:
        raise OpBlocked("one analysis-grid evidence per call", detail_code="MULTIPLE_GRIDS")
    grid = None
    synthetic = False
    attribution: tuple[str, ...] = ()
    ref = None
    if grids:
        handle = grids[0]
        grid = decode_analysis_grid(env.artifact_path(handle).read_bytes())
        if grid.meta.body != handle.body:
            raise OpBlocked("Display grid body differs from its evidence", detail_code="BODY_MISMATCH")
        synthetic = handle.mode == "synthetic" or "Source provenance: SYNTHETIC" in handle.limitations
        attribution = tuple(
            value.split(": ", 1)[1] for value in handle.limitations
            if value.startswith(("Source citation: ", "Source license: "))
        )
        if not synthetic and not attribution:
            raise OpBlocked("Actual source citation and license are required for display", code="METADATA_INCOMPLETE")
        ref = EvidenceRef(evidence_id=handle.evidence_id)
    normalized = []
    for handle in sources:
        src = resolve_source(
            env, SourceSelector(kind="ADAPTER_EVIDENCE", evidence_ids=[handle.evidence_id]),
            roles=("TARGET_TERRAIN", "EARTH_TERRAIN", "EARTH_MINERAL", "LUNAR_THERMAL"),
        )
        normalized.append((handle, src))
    layers: list[LayerRaster] = []
    issues: list[ScienceIssue] = []
    for kind in dict.fromkeys(inp.layer_kinds):
        env.check()
        if kind in ("ELEVATION", "SLOPE") and grid is not None and ref is not None:
            layers.append(
                layer_from_analysis_grid(
                    grid, kind, source_evidence=[ref], synthetic=synthetic, attribution=attribution
                )
            )
        elif kind == "ROUGHNESS" and grid is not None and ref is not None:
            rms, ok = detrended_rms_height_m(grid.elevation_m, grid.valid, 3)
            base = layer_from_analysis_grid(
                grid, "ELEVATION", source_evidence=[ref], synthetic=synthetic, attribution=attribution
            )
            layers.append(
                LayerRaster(
                    kind="ROUGHNESS",
                    grid=base.grid,
                    values=np.where(ok & grid.valid, rms, np.nan),
                    unit="m",
                    support_scale_m=grid.meta.cell_size_m,
                    source_evidence=(ref,),
                    synthetic=synthetic,
                    attribution=attribution,
                    limitations=("Detrended RMS height over a 3x3-cell window.",),
                )
            )
        else:
            wanted = {
                "THERMAL": ("LUNAR_THERMAL",), "MINERAL": ("EARTH_MINERAL",),
                "ELEVATION": ("EARTH_TERRAIN", "TARGET_TERRAIN"),
            }.get(kind, ())
            available = [(h, source) for h, source in normalized if source.manifest.role in wanted]
            if len(available) > 1:
                raise OpBlocked("Multiple normalized sources for one display layer", detail_code="MULTIPLE_SOURCES")
            if available:
                h, source = available[0]
                layers.append(LayerRaster(
                    kind=kind, grid=source.raster.grid, values=source.raster.values,
                    unit="m" if kind == "ELEVATION" else source.manifest.units,
                    support_scale_m=source.raster.support_scale_m,
                    source_evidence=(EvidenceRef(evidence_id=h.evidence_id),),
                    synthetic=source.manifest.is_synthetic,
                    attribution=(source.manifest.citation, source.manifest.license_note),
                    categorical=kind == "MINERAL",
                    limitations=("Product values at native support; no visual inference of absent retrievals.",),
                ))
                continue
            issues.append(
                ScienceIssue(
                    code="NO_COVERAGE",
                    detail_code="LAYER_DATA_MISSING",
                    message=f"{kind} layer: the cited evidence carries no {kind.lower()} raster",
                    scope=kind,
                )
            )
    if not layers:
        raise OpBlocked(issues[0].message, code="NO_COVERAGE", detail_code="LAYER_DATA_MISSING")
    built = build_display_layers(layers, env.scratch)
    params = env.params_hash(algo, env.operation_params())
    payload_art = json_artifact(env, params_sha=params, key="display-json", name="display.json", payload=built.payload)
    ev = derived_evidence(
        env,
        key="display",
        kind="DERIVED",
        body=layers[0].grid.body,
        algorithm_id=algo,
        params_sha=params,
        artifact=payload_art,
        parent_evidence_ids=sorted({r.evidence_id for layer in layers for r in layer.source_evidence}, key=str),
        limitations=["Display smoothing adds no resolution; display images are never analysis inputs."],
    )
    status = ComputationStatus.LIMITED if issues else ComputationStatus.SUCCEEDED
    return OpOutcome(status, built.payload, algo, params, [*built.artifacts, payload_art], [ev], issues)
