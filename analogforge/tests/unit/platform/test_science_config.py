"""Application science seams use the configuration pinned by their Settings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from analogforge.application import datasets, preflight
from analogforge.application.scheduler import WorkflowEngine
from analogforge.application.seed import seed_synthetic
from analogforge.ports import catalog
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.science_payloads import CharacterizeTargetInput, CharacterizeTargetPayload, SourceSelector
from analogforge.settings import Settings
from tests.unit.platform.test_scientific_invocations import WorkerStoreDouble

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def configured_settings(tmp_path):
    config = tmp_path / "config"
    shutil.copytree(ROOT / "config", config)
    algorithms_path = config / "algorithms.yaml"
    algorithms = yaml.safe_load(algorithms_path.read_text())
    algorithms["measurement_specs"][catalog.MEASUREMENT_SPEC_TARGET]["comparison_support"]["default_requested_m"] = 960
    algorithms["algorithm_lock"][catalog.ALGORITHM_IDS["INGEST_LOCAL_DATASET"]] = "custom-config-version"
    algorithms_path.write_text(yaml.safe_dump(algorithms))
    return Settings(_env_file=None, data_root=tmp_path / "data", config_dir=config)


def test_worker_executes_configured_support_with_its_pinned_hash(configured_settings, monkeypatch):
    settings = configured_settings
    seed_synthetic(None, settings)
    workspace_id, run_id = str(uuid4()), str(uuid4())
    store = WorkerStoreDouble(workspace_id, run_id)
    engine = WorkflowEngine(store, settings)
    run = store.require("runs", run_id)
    run.update({
        "state": "CHARACTERIZING", "mode": "synthetic", "scenario_config_id": "synthetic-mars-mobility-v1",
        "config_sha256": "0" * 64, "dataset_lock_id": catalog.DATASET_LOCK_SYNTHETIC,
        "runtime": {"algorithm_lock_sha256": engine._algorithm_lock()},
    })
    monkeypatch.setattr(engine, "_load", lambda *_: (run, {}, None))
    monkeypatch.setattr(engine, "_charge", lambda *_: None)
    # Keep the actual subprocess and facade; isolate unrelated persistence/publication.
    engine.registrar = SimpleNamespace(register=lambda _request, result, **_: result)
    target = json.loads((ROOT / "config/presets/missions/mission-mars-mobility.json").read_text())["target"]
    result = engine._compute(CharacterizeTargetInput(
        target=AreaOfInterest.model_validate(target),
        source=SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id=catalog.FIXTURE_MARS_TARGET),
        measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET,
        requested_dimensions=["TERRAIN"],
    ), run_id, workspace_id)
    assert result.status in {"SUCCEEDED", "LIMITED"}, result.issues
    assert isinstance(result.payload, CharacterizeTargetPayload)
    assert result.payload.metrics
    coverage = next(metric for metric in result.payload.metrics if metric.metric_id == "valid_fraction")
    assert coverage.support_scale_m == 960
    assert result.payload.slope_histogram is not None
    assert result.payload.slope_histogram.support_scale_m == 960


def test_science_preflight_rejects_invalid_configured_algorithms(configured_settings):
    path = configured_settings.config_dir / "algorithms.yaml"
    algorithms = yaml.safe_load(path.read_text())
    algorithms["grid"]["cell_size_m"] = -1
    path.write_text(yaml.safe_dump(algorithms))
    passed, code, _ = preflight._science_check(configured_settings)
    assert not passed
    assert code == "SCIENCE_PROBE_FAILED"


def test_operator_validation_executes_its_configured_algorithm_version(configured_settings, monkeypatch):
    from analogforge.science import facade

    settings = configured_settings
    datasets.generate_practice(settings)
    factory = facade.create_science_service
    results = []

    def record_service(config_dir=None):
        service = factory(config_dir=config_dir)

        def execute(request, context):
            result = service.execute(request, context)
            results.append(result)
            return result

        return SimpleNamespace(supported_operations=service.supported_operations, execute=execute)

    monkeypatch.setattr(facade, "create_science_service", record_service)
    report = datasets.validate_dataset(settings, catalog.FIXTURE_MARS_TARGET)
    assert report["status"] == "PASS"
    assert results[0].algorithm_version == "custom-config-version"
