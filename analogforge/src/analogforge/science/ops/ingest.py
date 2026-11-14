"""``INGEST_LOCAL_DATASET`` (guide 08 section 4.1): wraps :mod:`analogforge.science.datasets.ingest`."""

from __future__ import annotations

from analogforge.ports import catalog
from analogforge.ports.science import ArtifactRole, ComputationStatus
from analogforge.ports.science_payloads import IngestLocalDatasetInput
from analogforge.science.datasets.ingest import DatasetUnreadableError, ingest_local_dataset, source_evidence_draft
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, bytes_artifact, derived_evidence, json_artifact
from analogforge.science.ops.source import _water
from analogforge.science.raster.normalized import MEDIA_TYPE, encode_source


def run_ingest(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, IngestLocalDatasetInput)
    algo = catalog.ALGORITHM_IDS["INGEST_LOCAL_DATASET"]
    dataset_id = inp.manifest.dataset_id
    if env.request.source_policy.local_dataset_ids and dataset_id not in env.request.source_policy.local_dataset_ids:
        raise OpBlocked(f"dataset {dataset_id} is not authorized by the source policy", detail_code="POLICY_DENIED")
    try:
        root = env.context.local_dataset_root(dataset_id)
    except KeyError as exc:
        raise OpBlocked(
            f"dataset {dataset_id} is not registered", code="NO_COVERAGE", detail_code="DATASET_UNKNOWN"
        ) from exc
    try:
        result = ingest_local_dataset(root, inp.manifest, env.scratch, check_cancelled=env.check)
    except DatasetUnreadableError as exc:
        raise OpBlocked(exc.message, code="SOURCE_UNAVAILABLE", detail_code="DATASET_UNREADABLE") from exc
    if result.payload is None:
        raise OpBlocked("dataset identity could not be recovered from the manifest", detail_code="MANIFEST_INVALID")
    evidence = []
    artifacts = []
    params = env.params_hash(algo, env.operation_params(), list(result.file_hashes.values()))
    if result.raster is not None:
        draft = source_evidence_draft(
            result,
            mode=env.request.mode,
            algorithm_version=env.algorithm_version(algo),
            algorithm_config_sha256=env.cfg.algorithm_config_sha256,
            seed=env.seed,
        )
        params = draft.parameters_sha256
        if result.usable_for_quantitative_claims and result.manifest is not None:
            assert result.payload.bbox_lonlat is not None
            data = encode_source(
                result.raster, result.manifest, dict(result.file_hashes), result.payload.bbox_lonlat,
                _water(result.manifest, root, result.raster.values.shape),
            )
            art = bytes_artifact(
                env, params_sha=params, key="normalized-source", name="normalized-source.npz", data=data,
                media_type=MEDIA_TYPE, role=ArtifactRole.NORMALIZED_RASTER, body=result.manifest.body,
                crs_wkt=result.raster.crs_wkt, support_scale_m=result.raster.native_resolution_m,
            )
            artifacts.append(art)
            draft = draft.model_copy(update={"artifact_key": art.local_key, "artifact_media_type": MEDIA_TYPE})
        evidence.append(draft)
    report = json_artifact(env, params_sha=params, key="ingest-json", name="ingest.json", payload=result.payload)
    artifacts.append(report)
    evidence.append(derived_evidence(
        env, key="ingest-report", kind="DERIVED", body=result.payload.body, algorithm_id=algo,
        params_sha=params, artifact=report, parent_keys=[e.local_key for e in evidence],
    ))
    return OpOutcome(ComputationStatus.SUCCEEDED, result.payload, algo, params, artifacts, evidence)
