"""Local analysis may reuse validation ancestry only for the exact source it actually revalidated."""

from dataclasses import replace
from uuid import uuid4

import pytest
import yaml
from support.builders import make_request, run
from support.practice import make_practice_context, mars_target_aoi

from analogforge.ports.science import ScienceOptions
from analogforge.ports.science_payloads import CharacterizeTargetInput, IngestLocalDatasetInput, SourceSelector
from analogforge.science.datasets.ingest import ingest_local_dataset, source_evidence_draft
from analogforge.science.facade import create_science_service
from analogforge.science.ops.base import OpEnv
from analogforge.science.ops.source import _validated_source_parents, _water


@pytest.fixture
def source_case(tmp_path):
    context = make_practice_context(tmp_path)
    dataset = "practice-mars-target-v1"
    root = context.dataset_roots[dataset]
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    service = create_science_service()
    _, registered = run(service, IngestLocalDatasetInput(manifest=manifest), context, datasets=[dataset])
    handle = registered.handles["source-" + dataset]
    result = ingest_local_dataset(root, manifest, context.scratch_dir())
    draft = source_evidence_draft(result, mode=context.mode, algorithm_version=handle.algorithm_version,
                                  algorithm_config_sha256=service.cfg.algorithm_config_sha256)
    request = make_request(IngestLocalDatasetInput(manifest=manifest), evidence=[handle], datasets=[dataset])
    env = OpEnv(request, context, service.cfg)
    water = _water(result.manifest, root, result.raster.values.shape)
    return env, draft, result, water, handle


@pytest.mark.parametrize("defect", [None, "bytes", "normalization", "config", "seed", "version", "body", "mode",
                                   "kind", "artifact", "media", "missing_artifact", "not_supplied"])
def test_validation_parent_requires_exact_scoped_fingerprint_and_normalized_artifact(source_case, defect):
    env, draft, result, water, handle = source_case
    if defect == "bytes":
        result = replace(result, file_hashes={name: "f" * 64 for name in result.file_hashes})
    elif defect == "normalization":
        result = replace(result, applied=replace(result.applied, offset=result.applied.offset + 1))
    if defect in {"bytes", "normalization", "config", "seed", "version"}:
        draft = source_evidence_draft(
            result, mode=env.request.mode,
            algorithm_version="different" if defect == "version" else handle.algorithm_version,
            algorithm_config_sha256="b" * 64 if defect == "config" else env.cfg.algorithm_config_sha256,
            seed=1 if defect == "seed" else env.seed,
        )
    fields = {"body": {"body": "EARTH"}, "mode": {"mode": "live"}, "kind": {"kind": "DERIVED"},
              "artifact": {"artifact_sha256": "e" * 64}, "media": {"artifact_media_type": "application/json"},
              "missing_artifact": {"artifact_sha256": None}}
    handle = handle.model_copy(update=fields.get(defect, {}))
    request = env.request.model_copy(update={"input_evidence": [] if defect == "not_supplied" else [handle]})
    parents = _validated_source_parents(replace(env, request=request), draft, result, water)
    assert parents == ([handle.evidence_id] if defect is None else [])


def test_local_characterization_retains_exact_ingest_ancestry_without_changing_science(source_case, monkeypatch):
    from analogforge.science.ops import source

    env, _draft, result, _water_mask, handle = source_case
    inputs = CharacterizeTargetInput(target=mars_target_aoi(), source=SourceSelector(kind="LOCAL_DATASET",
                                      dataset_id=result.manifest.dataset_id), measurement_spec_id="terrain-target-v1",
                                      requested_dimensions=["TERRAIN"])
    service = create_science_service()
    with monkeypatch.context() as baseline:
        baseline.setattr(source, "_validated_source_parents", lambda *_args: [])
        before, _ = run(service, inputs, env.context, evidence=[handle], datasets=[result.manifest.dataset_id])
    after, _ = run(service, inputs, env.context, evidence=[handle], datasets=[result.manifest.dataset_id])
    assert before.status == after.status == "SUCCEEDED"
    assert before.payload.model_dump(mode="json") == after.payload.model_dump(mode="json")
    assert before.parameters_sha256 == after.parameters_sha256
    assert {artifact.local_key: artifact.sha256 for artifact in before.artifacts} == {
        artifact.local_key: artifact.sha256 for artifact in after.artifacts
    }
    source = next(item for item in after.evidence_drafts if item.kind == "SOURCE")
    assert source.parent_evidence_ids == [handle.evidence_id]
    assert all(handle.evidence_id not in item.parent_evidence_ids for item in before.evidence_drafts)


def test_unrelated_equally_shaped_source_and_different_seed_are_not_grafted(source_case):
    env, draft, result, water, handle = source_case
    unrelated = handle.model_copy(update={"evidence_id": uuid4(), "parameters_sha256": "c" * 64})
    request = env.request.model_copy(update={"input_evidence": [unrelated], "options": ScienceOptions(seed=7)})
    assert _validated_source_parents(replace(env, request=request), draft, result, water) == []
