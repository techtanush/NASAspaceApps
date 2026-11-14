"""Preparation preserves user-authored requirements and configured-only production inputs."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from analogforge.application.scheduler import WorkflowEngine, WorkflowError

ROOT = Path(__file__).resolve().parents[3]


def test_preparation_preserves_user_requirements_and_marks_only_defaults(tmp_path):
    settings = SimpleNamespace(data_root=tmp_path, config_dir=ROOT / "config")
    engine = WorkflowEngine(None, settings)
    mission = json.loads((ROOT / "tests/fixtures/kit/blueprint-mission-contract.json").read_text())
    mission["requirements"][0].update(lower=321, origin="USER")
    mission["assumptions"] = ["User supplied fixed model assumption"]
    prepared = engine.prepare(mission, str(uuid4()))
    assert prepared["requirements"] == mission["requirements"]
    assert prepared["assumptions"] == mission["assumptions"]
    assert prepared["accepted_at"] is None
    assert prepared["content_sha256"] != mission["content_sha256"]
    mission["requirements"] = []
    default = engine.prepare(mission, str(uuid4()))
    assert all(r["origin"] == "PROPOSED_DEFAULT" for r in default["requirements"])


def test_missing_preset_is_a_setup_failure_without_test_fixture_fallback(tmp_path):
    settings = SimpleNamespace(data_root=tmp_path, config_dir=tmp_path)
    engine = WorkflowEngine(None, settings)
    engine._scenario = lambda _: {"mission_preset": "missing.json"}
    with pytest.raises(WorkflowError, match="Configured mission preset is missing"):
        engine.prepare({"target": {"body": "MARS"}}, str(uuid4()))


def test_live_client_unwraps_secret_and_requires_local_explicit_test_hook(tmp_path):
    settings = SimpleNamespace(
        data_root=tmp_path,
        config_dir=ROOT / "config",
        openai_api_key=SecretStr("local-probe-credential"),
        openai_model="explicit-configured-model",
        fake_openai_url=None,
    )
    engine = WorkflowEngine(None, settings)
    assert engine._provider_client().client.api_key == "local-probe-credential"
    settings.fake_openai_url = "https://unapproved.example/v1"
    with pytest.raises(WorkflowError, match="not explicitly enabled"):
        engine._provider_client()
    settings.test_hooks = True
    settings.auth_mode = "local"
    settings.allow_test_harness_provider = True
    with pytest.raises(WorkflowError, match="loopback"):
        engine._provider_client()
