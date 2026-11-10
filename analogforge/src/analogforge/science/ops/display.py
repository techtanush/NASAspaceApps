"""``BUILD_DISPLAY_LAYERS`` (guide 08 section 4.14): wraps :mod:`analogforge.science.display`.

Layers are built from the ANALYSIS_GRID artifacts of the cited evidence.  Kinds with no data in the cited evidence
(THERMAL, MINERAL: their rasters are not carried by any evidence artifact) are reported as issues, never faked.
"""

from __future__ import annotations

import numpy as np

from analogforge.ports.common import EvidenceRef, ScienceIssue
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import BuildDisplayLayersInput
from analogforge.science.display.layers import LayerRaster, build_display_layers, layer_from_analysis_grid
from analogforge.science.features.roughness import detrended_rms_height_m
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.raster.store import decode_analysis_grid

NPZ = "application/x-npz"
GENERIC_ATTRIBUTION = (
    "Derived by AnalogForge from NASA source evidence; see the evidence lineage for citation and licence."
)


def run_display(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, BuildDisplayLayersInput)
    algo = "build-display-layers"
    handles = [env.handle(i) for i in inp.evidence_ids]
    grids = [h for h in handles if h.artifact_media_type == NPZ and h.artifact_sha256 is not None]
    if not grids:
        raise OpBlocked(
            "none of the cited evidence carries an analysis grid to display",
            code="NO_COVERAGE",
            detail_code="NO_DISPLAYABLE_EVIDENCE",
        )
    if len(grids) > 1:
        raise OpBlocked("one analysis-grid evidence per call", detail_code="MULTIPLE_GRIDS")
    handle = grids[0]
    grid = decode_analysis_grid(env.artifact_path(handle).read_bytes())
    synthetic = handle.mode == "synthetic"
    attribution = () if synthetic else (GENERIC_ATTRIBUTION,)
    ref = EvidenceRef(evidence_id=handle.evidence_id)
    layers: list[LayerRaster] = []
    issues: list[ScienceIssue] = []
    for kind in dict.fromkeys(inp.layer_kinds):
        env.check()
        if kind in ("ELEVATION", "SLOPE"):
            layers.append(
                layer_from_analysis_grid(
                    grid, kind, source_evidence=[ref], synthetic=synthetic, attribution=attribution
                )
            )
        elif kind == "ROUGHNESS":
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
        body=grid.meta.body,  # type: ignore[arg-type]
        algorithm_id=algo,
        params_sha=params,
        artifact=payload_art,
        parent_evidence_ids=[handle.evidence_id],
        limitations=["Display smoothing adds no resolution; display images are never analysis inputs."],
    )
    status = ComputationStatus.LIMITED if issues else ComputationStatus.SUCCEEDED
    return OpOutcome(status, built.payload, algo, params, [*built.artifacts, payload_art], [ev], issues)
