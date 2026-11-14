"""Preparation preserves user-authored requirements and configured-only production inputs."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from analogforge.application.scheduler import WorkflowEngine, WorkflowError
from analogforge.ports import catalog

ROOT = Path(__file__).resolve().parents[3]


def live_drafting(tmp_path, monkeypatch):
    proposal = json.loads((ROOT / "tests/fixtures/kit/blueprint-mission-contract.json").read_text())
    terrain = json.loads((ROOT / "config/presets/missions/mission-mars-mobility.json").read_text())
    proposal["requirements"] = [terrain["requirements"][0]]
    proposal["requirements"][0]["acceptance_note"] = "Proposed threshold for review, not a measurement"
    proposal["assumptions"] = ["Proposed terrain comparison scope for review"]
    mission = {
        "id": str(uuid4()), "name": "Measured Mars terrain comparison",
        "objective": "Compare terrain at the source's documented support",
        "target": {**proposal["target"], "vertical_datum": "MOLA areoid"},
    }
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(proposal)},
        ]}]}

    engine = WorkflowEngine(None, SimpleNamespace(
        data_root=tmp_path, config_dir=ROOT / "config", openai_api_key="local-test-only", openai_model="test-model",
    ))
    monkeypatch.setattr(engine, "_provider_client", lambda: SimpleNamespace(create=create))
    return engine, mission, proposal, calls


def test_live_preparation_context_has_supported_policies_without_synthetic_examples(tmp_path, monkeypatch):
    engine, mission, _, calls = live_drafting(tmp_path, monkeypatch)
    prepared = engine.prepare(mission, str(uuid4()), mode="live")
    prompt = json.loads(calls[0]["input"])
    assert "example_structure" not in prompt
    assert prompt["mode"] == "live"
    assert prompt["draft"] == mission
    policy = prompt["observable_policy_catalog"]["slope_band_area_fraction"]
    assert policy["policy_id"] == catalog.OBSERVABLE_POLICY_BY_OBSERVABLE["slope_band_area_fraction"]
    assert policy["units"] == "fraction" and policy["operators"] == ["GTE"]
    assert prompt["algorithm_config_version"] == "1.0"
    assert "generated from documented formulas" not in calls[0]["input"]
    assert "W1/W2" not in calls[0]["input"]
    assert prepared["accepted_at"] is None
    assert all(row["origin"] == "PROPOSED_DEFAULT" for row in prepared["requirements"])


def test_live_preparation_does_not_require_a_synthetic_mission_preset(tmp_path, monkeypatch):
    engine, mission, _, _ = live_drafting(tmp_path, monkeypatch)
    monkeypatch.setattr(engine, "_scenario", lambda _: {"body": "MARS", "mission_preset": None})
    assert engine.prepare(mission, str(uuid4()), mode="live")["target"] == mission["target"]


@pytest.mark.parametrize("assumptions", [[], ["User source scope", "User source scope"]])
def test_live_preparation_preserves_supplied_assumptions_without_supplied_requirements(
    tmp_path, monkeypatch, assumptions
):
    engine, mission, _, _ = live_drafting(tmp_path, monkeypatch)
    mission["assumptions"] = assumptions
    assert engine.prepare(mission, str(uuid4()), mode="live")["assumptions"] == mission["assumptions"]


def test_synthetic_preparation_keeps_preset_assumptions_for_an_empty_draft(tmp_path):
    engine = WorkflowEngine(None, SimpleNamespace(data_root=tmp_path, config_dir=ROOT / "config"))
    mission = json.loads((ROOT / "tests/fixtures/kit/blueprint-mission-contract.json").read_text())
    mission.update(requirements=[], assumptions=[])
    preset = json.loads((ROOT / "config/presets/missions/mission-mars-mobility.json").read_text())
    prepared = engine.prepare(mission, str(uuid4()), mode="synthetic")
    assert prepared["assumptions"] == preset["assumptions"]


def test_live_preparation_preserves_explicit_unknown_user_requirements(tmp_path, monkeypatch):
    engine, mission, proposal, _ = live_drafting(tmp_path, monkeypatch)
    requirement = {
        **proposal["requirements"][0], "observable": "user_instrument_observable", "origin": "USER",
        "parameters": {**proposal["requirements"][0]["parameters"], "comparison_rule_id": "user-rule-v1"},
    }
    mission["requirements"] = [requirement]
    mission["assumptions"] = ["Preserve the user's unknown measurement for later review"]
    prepared = engine.prepare(mission, str(uuid4()), mode="live")
    assert prepared["requirements"] == mission["requirements"]
    assert prepared["assumptions"] == mission["assumptions"]


@pytest.mark.parametrize("unsupported", ["observable", "comparison_rule"])
def test_live_preparation_rejects_unsupported_generated_measurements(tmp_path, monkeypatch, unsupported):
    engine, mission, proposal, _ = live_drafting(tmp_path, monkeypatch)
    row = proposal["requirements"][0]
    if unsupported == "observable":
        row["observable"] = "no_rover_experiment"
    else:
        row["parameters"]["comparison_rule_id"] = "scope-exclusion-v1"
    with pytest.raises(WorkflowError) as error:
        engine.prepare(mission, str(uuid4()), mode="live")
    assert error.value.code == "MODEL_OUTPUT_INVALID"


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
