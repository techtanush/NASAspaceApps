"""MRG-05b rehearsal data must never masquerade as an ordinary live source."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from analogforge.application.datasets import DatasetError, load_manifest
from analogforge.settings import Settings
from tests.integration.platform.test_dataset_cli import _dataset


def test_test_harness_manifest_requires_both_explicit_local_hooks(tmp_path):
    plain = Settings(_env_file=None, data_root=tmp_path)
    root = _dataset(plain, 'harness-target', synthetic=False)
    path = root / 'manifest.yaml'
    manifest = yaml.safe_load(path.read_text())
    manifest['provider'] = 'TEST_HARNESS'
    path.write_text(yaml.safe_dump(manifest))
    for hooks, allow in [(False, False), (True, False)]:
        settings = Settings(_env_file=None, data_root=tmp_path, test_hooks=hooks, allow_test_harness_provider=allow)
        with pytest.raises(DatasetError, match='TEST_HARNESS'):
            load_manifest(settings, 'harness-target')
    enabled = Settings(_env_file=None, data_root=tmp_path, test_hooks=True, allow_test_harness_provider=True)
    assert load_manifest(enabled, 'harness-target').provider == 'TEST_HARNESS'


def test_rehearsal_binds_through_validated_lock_and_restores_only_its_scenario(tmp_path):
    from analogforge.application.capabilities import get_scenarios, save_scenarios
    from analogforge.application.rehearsal import bind_live_slot, restore_live_slot

    config = tmp_path / 'config'
    shutil.copytree(Path(__file__).parents[3] / 'config', config)
    settings = Settings(_env_file=None, data_root=tmp_path / 'data', config_dir=config,
                        test_hooks=True, allow_test_harness_provider=True)
    original = get_scenarios(settings)['live-hackathon-v1']
    receipt = bind_live_slot(settings)
    assert receipt['label'] == 'TEST HARNESS — not NASA data'
    assert get_scenarios(settings)['live-hackathon-v1']['allowed_modes'] == ['live']
    scenarios = get_scenarios(settings)
    scenarios['local-dataset-practice-v1']['description'] = 'Unrelated binding retained'
    save_scenarios(settings, scenarios)
    assert bind_live_slot(settings) == receipt
    restore_live_slot(settings)
    restored = get_scenarios(settings)
    assert restored['live-hackathon-v1'] == original
    assert restored['local-dataset-practice-v1']['description'] == 'Unrelated binding retained'


def test_rehearsal_requires_hooks_and_an_isolated_config(tmp_path):
    from analogforge.application.rehearsal import bind_live_slot

    with pytest.raises(DatasetError, match='TEST_HARNESS'):
        bind_live_slot(Settings(_env_file=None, data_root=tmp_path))
    with pytest.raises(DatasetError, match='isolated'):
        bind_live_slot(Settings(_env_file=None, data_root=tmp_path, test_hooks=True,
                                allow_test_harness_provider=True))


def test_harness_cannot_establish_real_source_validation_or_unlabelled_claims():
    from analogforge.application.assurance import _mode_and_level, _statement, restrict_rehearsal_claim
    from tests.integration.platform.test_assurance import audit_case

    snapshot, claim, _ = audit_case()
    evidence = {key: value.model_copy(update={'mode': 'live', 'dataset_product_id': 'TEST_HARNESS_EARTH'})
                for key, value in snapshot.evidence.items()}
    snapshot = replace(snapshot, mode='live', evidence=evidence)
    for level in ('S2', 'S3', 'S4'):
        promoted = replace(claim, validation_level=level)
        assert _mode_and_level(snapshot, promoted)[0] is False
        restricted = restrict_rehearsal_claim(snapshot, promoted)
        assert restricted.validation_level == 'S1'
        assert _mode_and_level(snapshot, restricted)[0] is True
        assert _statement(restricted, 'LIMITED').startswith('TEST HARNESS — not NASA data:')


def test_rehearsal_cli_and_newer_binding_protection(tmp_path, monkeypatch, capsys):
    import json

    from analogforge import cli
    from analogforge.application.capabilities import get_scenarios, save_scenarios

    config = tmp_path / 'config'
    shutil.copytree(Path(__file__).parents[3] / 'config', config)
    settings = Settings(_env_file=None, data_root=tmp_path / 'data', config_dir=config,
                        test_hooks=True, allow_test_harness_provider=True)
    monkeypatch.setattr(cli, 'Settings', lambda: settings)
    assert cli.main(['rehearsal', 'bind-live-slot', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['label'] == 'TEST HARNESS — not NASA data'
    bound = get_scenarios(settings)
    newer = get_scenarios(settings)
    newer['live-hackathon-v1']['description'] = 'Newer operator configuration'
    save_scenarios(settings, newer)
    assert cli.main(['rehearsal', 'restore-live-slot', '--json']) == 1
    assert json.loads(capsys.readouterr().err)['code'] == 'REVISION_CONFLICT'
    assert get_scenarios(settings) == newer
    save_scenarios(settings, bound)
    assert cli.main(['rehearsal', 'restore-live-slot', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['restored_scenario'] == 'live-hackathon-v1'


def test_mock_nasa_drop_binds_to_local_practice_without_entering_live(tmp_path):
    from argparse import Namespace

    from analogforge.application.capabilities import get_scenarios
    from analogforge.application.datasets import create_lock, generate_mock_nasa_drop, validate_dataset
    from analogforge.cli import _bind

    config = tmp_path / 'config'
    shutil.copytree(Path(__file__).parents[3] / 'config', config)
    settings = Settings(_env_file=None, data_root=tmp_path / 'data', config_dir=config)
    generate_mock_nasa_drop(settings)
    identifiers = ['mock-nasa-mars-dem', 'mock-nasa-earth-dem']
    for identifier in identifiers:
        assert validate_dataset(settings, identifier, write_checksums=True)['status'] == 'PASS'
    create_lock(settings, 'mock-drop-policy-v1', identifiers)
    args = Namespace(scenario_id='local-dataset-practice-v1', policy_id='mock-drop-policy-v1',
                     target_terrain=identifiers[0], earth_terrain=identifiers[1],
                     earth_mineral=None, lunar_thermal=None)
    receipt = _bind(settings, args)
    assert receipt['status'] == 'AVAILABLE'
    bound = get_scenarios(settings)['local-dataset-practice-v1']
    assert bound['allowed_modes'] == ['synthetic']
    assert bound['target_source'] == {'kind': 'LOCAL_DATASET', 'dataset_id': identifiers[0]}
    assert bound['earth_source'] == {'kind': 'LOCAL_DATASET', 'dataset_id': identifiers[1]}
    assert bound['search_region_set_id'] == 'local-dataset-grid-v1'
    args.scenario_id = 'live-hackathon-v1'
    with pytest.raises(DatasetError, match='Synthetic'):
        _bind(settings, args)
    assert get_scenarios(settings)['live-hackathon-v1']['allowed_modes'] == []
    args.scenario_id = 'local-dataset-practice-v1'
    args.target_terrain = None
    args.earth_terrain = None
    with pytest.raises(DatasetError) as missing:
        _bind(settings, args)
    assert missing.value.code == 'DATASETS_UNBOUND'
