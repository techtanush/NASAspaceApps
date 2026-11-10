"""Route operations: DESIGN_BENCHMARK, SEARCH_ROUTE, VERIFY_ROUTE, DIAGNOSE_RESULT (guide 08 4.9-4.12)."""

from __future__ import annotations

from collections.abc import Callable

from analogforge.ports import catalog
from analogforge.ports.hashing import bytes_sha256
from analogforge.ports.science import ArtifactRole, ComputationStatus
from analogforge.ports.science_payloads import (
    ConstraintsArtifact,
    DesignBenchmarkInput,
    DiagnoseResultInput,
    GridSpec,
    SearchRouteInput,
    VerifyRouteInput,
)
from analogforge.science.geometry import frame_from_crs_wkt, xy_to_lonlat
from analogforge.science.ops.base import OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.raster.store import decode_analysis_grid
from analogforge.science.routing import GridArrays, grid_arrays_from_analysis, load_grid_arrays
from analogforge.science.routing.constraints import RouteDesignDefaults
from analogforge.science.routing.diagnose import diagnose_result
from analogforge.science.routing.search import search_route
from analogforge.science.routing.verify import verify_route
from analogforge.science.routing.waypoints import design_benchmark


def _defaults(env: OpEnv) -> RouteDesignDefaults:
    d, r = env.cfg.algorithms.design_defaults, env.cfg.algorithms.route_search
    return RouteDesignDefaults(
        max_route_m=float(d.max_route_m),
        task_dwell_s=float(d.task_dwell_s),
        max_expansions=r.max_expansions,
        max_seconds=int(r.max_seconds),
        max_labels_per_node=r.max_labels_per_node,
        seed=env.seed,
        footprint_dilation_m=float(d.footprint_dilation_m),
    )


def _constraint_grid(env: OpEnv, constraints: ConstraintsArtifact) -> GridArrays | None:
    if constraints.grid is None:
        return None
    path = env.read_artifact_by_sha(constraints.grid.analysis_grid_sha256)
    return load_grid_arrays(path, expected_sha256=constraints.grid.analysis_grid_sha256)


def _to_lonlat(constraints: ConstraintsArtifact) -> Callable[[float, float], tuple[float, float]] | None:
    if constraints.grid is None:
        return None
    frame = frame_from_crs_wkt("EARTH", constraints.grid.crs_wkt)

    def convert(x: float, y: float) -> tuple[float, float]:
        lon, lat = xy_to_lonlat(frame, x, y)
        return float(lon), float(lat)

    return convert


def run_design(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, DesignBenchmarkInput)
    algo = catalog.ALGORITHM_IDS["DESIGN_BENCHMARK"]
    grid: GridArrays | None = None
    spec: GridSpec | None = None
    parents: list[object] = []
    if inp.graph_fixture_id is None and inp.analysis_evidence_id is not None:
        handle = env.handle(inp.analysis_evidence_id)
        data = env.artifact_path(handle).read_bytes()
        decoded = decode_analysis_grid(data)
        grid = grid_arrays_from_analysis(decoded)
        spec = GridSpec(
            analysis_evidence_id=inp.analysis_evidence_id,
            analysis_grid_sha256=bytes_sha256(data),
            crs_wkt=decoded.meta.crs_wkt,
            cell_size_m=decoded.meta.cell_size_m,
            width=decoded.meta.width,
            height=decoded.meta.height,
        )
        parents.append(inp.analysis_evidence_id)
    payload = design_benchmark(
        inp,
        mode=env.request.mode,
        grid=grid,
        grid_spec=spec,
        defaults=_defaults(env),
        constraints_artifact_key="constraints",
        check_cancelled=env.check,
    )
    params = env.params_hash(algo, env.operation_params())
    art = json_artifact(
        env,
        params_sha=params,
        key="constraints",
        name="constraints.json",
        payload=payload.constraints,
        role=ArtifactRole.CONSTRAINTS,
        body="EARTH",
    )
    ev = derived_evidence(
        env,
        key="design",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        parent_evidence_ids=parents,
        limitations=list(payload.constraints.limitations),
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], [ev])


def run_search(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, SearchRouteInput)
    algo = catalog.ALGORITHM_IDS["SEARCH_ROUTE"]
    c = inp.constraints
    grid = _constraint_grid(env, c)
    opts = env.request.options
    out = search_route(
        c,
        inp.constraints_sha256,
        grid=grid,
        mode=env.request.mode,
        check_cancelled=env.check,
        max_expansions=opts.max_expansions,
        max_seconds=opts.max_seconds,
        max_labels_per_node=opts.max_labels_per_node,
        route_key="route",
        route_artifact_key="route",
        to_lonlat=_to_lonlat(c),
    )
    params = env.params_hash(algo, env.operation_params(), [inp.constraints_sha256])
    artifacts = []
    art = None
    if out.route is not None:
        art = json_artifact(
            env,
            params_sha=params,
            key="route",
            name="route.json",
            payload=out.route,
            role=ArtifactRole.ROUTE,
            body="EARTH",
        )
        artifacts.append(art)
    ev = derived_evidence(
        env,
        key="search",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        limitations=[out.payload.termination_reason],
    )
    status = ComputationStatus.LIMITED if out.issues else ComputationStatus.SUCCEEDED
    counters: dict[str, int | float] = {
        "expansions": out.payload.counters.expansions,
        "labels_created": out.payload.counters.labels_created,
        "labels_pruned_lossy": out.payload.counters.labels_pruned_lossy,
        "elapsed_ms": out.payload.counters.elapsed_ms,
    }
    return OpOutcome(status, out.payload, algo, params, artifacts, [ev], list(out.issues), counters)


def run_verify(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, VerifyRouteInput)
    algo = catalog.ALGORITHM_IDS["VERIFY_ROUTE"]
    c = inp.constraints
    grid = _constraint_grid(env, c)
    out = verify_route(
        c,
        inp.constraints_sha256,
        inp.route,
        inp.route_sha256,
        inp.search_status,
        grid=grid,
        mode=env.request.mode,
        verification_evidence_key="verification",
        telemetry_artifact_key="telemetry",
        check_cancelled=env.check,
        to_lonlat=_to_lonlat(c),
    )
    params = env.params_hash(algo, env.operation_params(), [inp.constraints_sha256, inp.route_sha256])
    payload_art = json_artifact(
        env, params_sha=params, key="verification-json", name="verification.json", payload=out.payload, body="EARTH"
    )
    artifacts = [payload_art]
    evidence = [
        derived_evidence(
            env,
            key="verification",
            kind="VERIFICATION",
            body="EARTH",
            algorithm_id=algo,
            params_sha=params,
            artifact=payload_art,
            metrics=out.payload.metrics,
            limitations=list(out.payload.limitations),
        )
    ]
    if out.telemetry is not None:
        tel_algo = catalog.ALGORITHM_IDS["ROUTE_TELEMETRY"]
        tel_params = env.params_hash(tel_algo, env.operation_params(), [inp.constraints_sha256, inp.route_sha256])
        tel_art = json_artifact(
            env,
            params_sha=tel_params,
            key="telemetry",
            name="telemetry.json",
            payload=out.telemetry,
            role=ArtifactRole.TELEMETRY,
            body="EARTH",
        )
        artifacts.append(tel_art)
        evidence.append(
            derived_evidence(
                env,
                key="route-telemetry",
                kind="DERIVED",
                body="EARTH",
                algorithm_id=tel_algo,
                params_sha=tel_params,
                artifact=tel_art,
                parent_keys=["verification"],
            )
        )
    status = ComputationStatus.LIMITED if out.issues else ComputationStatus.SUCCEEDED
    return OpOutcome(status, out.payload, algo, params, artifacts, evidence, list(out.issues))


def run_diagnose(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, DiagnoseResultInput)
    algo = catalog.ALGORITHM_IDS["DIAGNOSE_RESULT"]
    grid = _constraint_grid(env, inp.constraints)
    out = diagnose_result(
        inp, grid=grid, mode=env.request.mode, diagnosis_evidence_key="diagnosis", check_cancelled=env.check
    )
    params = env.params_hash(algo, env.operation_params())
    art = json_artifact(env, params_sha=params, key="diagnosis-json", name="diagnosis.json", payload=out.payload)
    ev = derived_evidence(
        env,
        key="diagnosis",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        limitations=[out.payload.proof_scope],
    )
    status = ComputationStatus.LIMITED if out.issues else ComputationStatus.SUCCEEDED
    return OpOutcome(status, out.payload, algo, params, [art], [ev], list(out.issues))
