from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from analogforge.application import datasets
from analogforge.cli import main
from analogforge.ports.hashing import canonical_sha256, file_sha256
from analogforge.ports.science import ScienceComputationResult
from analogforge.ports.science_payloads import IngestLocalDatasetPayload, ValidationCheck
from analogforge.settings import Settings


def _dataset(
    settings: Settings, dataset_id: str, synthetic: bool = True, body: str = "MARS", role: str = "TARGET_TERRAIN"
) -> Path:
    root = settings.data_root / "incoming" / dataset_id
    root.mkdir(parents=True)
    (root / "terrain.tif").write_bytes(b"fixture bytes")
    manifest = {
        "manifest_version": "1.0",
        "dataset_id": dataset_id,
        "title": "Test terrain",
        "provider": "SYNTHETIC_TEST" if synthetic else "NASA PDS",
        "is_synthetic": synthetic,
        "body": body,
        "role": role,
        "format": "GEOTIFF",
        "files": [{"path": "terrain.tif", "role": "DATA", "sha256": file_sha256(root / "terrain.tif")}],
        "primary_file": "terrain.tif",
        "quantity": "ELEVATION",
        "units": "m",
        "vertical_reference": "Mars synthetic sphere",
        "crs": {"wkt": 'GEOGCS["Mars 2000"]'} if body == "MARS" else {"epsg": 4326},
        "longitude_convention": "NEG180_180",
        "latitude_type": "PLANETOCENTRIC" if body == "MARS" else "GEODETIC",
        "license_note": "test",
        "citation": "test fixture",
    }
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    return root


def test_validation_uses_facade_and_lock_detects_byte_tamper(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, data_root=tmp_path)
    root = _dataset(settings, "test-mars-terrain")
    called = []

    class Science:
        def supported_operations(self):
            return {"INGEST_LOCAL_DATASET"}

        def execute(self, request, context):
            called.append((request.operation, context.local_dataset_root("test-mars-terrain")))
            payload = IngestLocalDatasetPayload(
                dataset_id="test-mars-terrain",
                body="MARS",
                role="TARGET_TERRAIN",
                usable_for_quantitative_claims=True,
                normalized_evidence=None,
                checks=[ValidationCheck(check_id="manifest_schema", status="PASS", message="valid")],
                native_resolution_m=60,
                bbox_lonlat=None,
            )
            return ScienceComputationResult(
                request_id=request.request_id,
                operation=request.operation,
                mode=request.mode,
                status="SUCCEEDED",
                algorithm_id="ingest-local-dataset",
                algorithm_version="test",
                parameters_sha256="0" * 64,
                input_sha256=canonical_sha256(request),
                payload=payload,
            )

    monkeypatch.setattr(datasets, "_entrypoint", lambda module, name: lambda: Science())
    report = datasets.validate_dataset(settings, "test-mars-terrain")
    assert report["status"] == "PASS"
    assert called == [("INGEST_LOCAL_DATASET", root)]
    lock = datasets.create_lock(settings, "test-policy-v1", ["test-mars-terrain"])
    assert datasets.read_lock(settings, "test-policy-v1")["policy_sha256"] == lock["policy_sha256"]
    (root / "terrain.tif").write_bytes(b"tampered")
    with pytest.raises(datasets.DatasetError, match="changed"):
        datasets.read_lock(settings, "test-policy-v1")


def test_cli_reports_machine_readable_error(capsys):
    code = main(["datasets", "validate", "nonexistent-id", "--json"])
    assert code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["status"] == "FAIL"
    assert error["code"] == "MANIFEST_INVALID"


def test_live_slot_rejects_synthetic_lock(tmp_path):
    from argparse import Namespace

    from analogforge.cli import _bind

    settings = Settings(_env_file=None, data_root=tmp_path)
    _dataset(settings, "synthetic-target-v1")
    validation = tmp_path / "validation" / "synthetic-target-v1.json"
    validation.parent.mkdir()
    manifest = datasets.load_manifest(settings, "synthetic-target-v1")
    validation.write_text(
        json.dumps(
            {"status": "PASS", "manifest_sha256": canonical_sha256(manifest), "usable_for_quantitative_claims": True}
        )
    )
    datasets.create_lock(settings, "live-hackathon-policy-v1", ["synthetic-target-v1"])
    args = Namespace(
        scenario_id="live-hackathon-v1",
        policy_id=None,
        target_terrain="synthetic-target-v1",
        earth_terrain="synthetic-target-v1",
        earth_mineral=None,
        lunar_thermal=None,
    )
    with pytest.raises(datasets.DatasetError) as caught:
        _bind(settings, args)
    assert caught.value.code == "MODE_MISMATCH"


@pytest.mark.parametrize("operator_limits", [None, '{"search_max_expansions":1}'])
def test_complete_practice_lock_enables_scenario(tmp_path, operator_limits):
    from shutil import copyfile

    config = tmp_path / "config"
    config.mkdir()
    source = Settings(_env_file=None).config_dir / "scenarios.yaml"
    copyfile(source, config / "scenarios.yaml")
    settings = Settings(
        _env_file=None, data_root=tmp_path / "data", config_dir=config,
        test_hooks=operator_limits is not None, operator_limits_json=operator_limits,
    )
    specs = (
        ("practice-mars-target-v1", "MARS", "TARGET_TERRAIN"),
        ("practice-earth-grid-v1", "EARTH", "EARTH_TERRAIN"),
        ("practice-earth-minerals-v1", "EARTH", "EARTH_MINERAL"),
    )
    for dataset_id, body, role in specs:
        _dataset(settings, dataset_id, body=body, role=role)
        manifest = datasets.load_manifest(settings, dataset_id)
        state = settings.data_root / "validation" / f"{dataset_id}.json"
        state.parent.mkdir(exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "manifest_sha256": canonical_sha256(manifest),
                    "usable_for_quantitative_claims": True,
                }
            )
        )
    datasets.create_lock(settings, "local-practice-policy-v1", [item[0] for item in specs])
    from analogforge.application.capabilities import get_scenarios

    assert get_scenarios(settings)["local-dataset-practice-v1"]["status"] == "AVAILABLE"

    # Enabling a dataset must not persist an ephemeral process-only budget override.
    disabled = Settings(_env_file=None, config_dir=config)
    defaults = get_scenarios(disabled)
    assert all(row["operator_limits"]["search_max_expansions"] == 200_000 for row in defaults.values())
    if operator_limits is not None:
        assert get_scenarios(settings)["local-dataset-practice-v1"]["operator_limits"]["search_max_expansions"] == 1
