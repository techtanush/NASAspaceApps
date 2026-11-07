from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from analogforge import cli
from analogforge.api.errors import ApiError
from analogforge.application.capabilities import get_capabilities, get_scenarios
from analogforge.application.exports import validate_rendered
from analogforge.application.preflight import STAGES, run_preflight
from analogforge.application.runs import require_live
from analogforge.application.seed import seed_synthetic
from analogforge.db.schema import TABLES
from analogforge.db.store import PersistenceError
from analogforge.domain.budgets import BudgetExceeded, BudgetLedger
from analogforge.ports import catalog
from analogforge.settings import Settings
from tests.integration.platform.test_passport_assembly import passport_case
from tests.support.factories import renderer_factory
from tests.support.fake_openai_server import fake_responses_server


class MemoryUnit:
    def __init__(self):
        self.records = {}

    def get(self, kind, entity_id):
        return self.records.get((kind, entity_id))

    def create(self, kind, doc):
        self.records[(kind, doc["id"])] = doc


class MemoryStore:
    def __init__(self):
        self.unit = MemoryUnit()
        self.workspace_count = 0

    def ensure_workspace(self, *_args):
        self.workspace_count += 1

    @contextmanager
    def transaction(self, _workspace_id):
        yield self.unit

    def health(self):
        return True


def test_seed_is_idempotent_and_capabilities_are_wire_valid(tmp_path):
    settings = Settings(_env_file=None, data_root=tmp_path)
    store = MemoryStore()
    first = seed_synthetic(store, settings)
    second = seed_synthetic(store, settings)
    assert first["created"]
    assert second["created"] == []
    assert first["dataset_lock_id"] == catalog.DATASET_LOCK_SYNTHETIC
    capabilities = get_capabilities(settings, store)
    assert capabilities["dataset_locks"] == [catalog.DATASET_LOCK_SYNTHETIC]
    assert capabilities["scenario_config_ids"] == list(catalog.ALL_SCENARIOS)
    assert not capabilities["live_ai_configured"]
    assert len(get_scenarios(settings)) == 5


def test_live_unbound_preflight_names_missing_dependencies(tmp_path):
    settings = Settings(_env_file=None, data_root=tmp_path)
    seed_synthetic(None, settings)
    report = run_preflight(settings, mode="live", scenario_id="live-hackathon-v1")
    assert report["status"] == "FAIL"
    assert {gate["stage"] for gate in report["gates"]} == set(STAGES)
    codes = {gate["code"] for gate in report["gates"]}
    assert {"MODEL_KEY_MISSING", "MODEL_NAME_MISSING", "DATASETS_UNBOUND"} <= codes


def test_cli_live_probe_uses_local_strict_responses_server(tmp_path, monkeypatch, capsys):
    class HealthyStore:
        def health(self):
            return True

        def close(self):
            return None

    with fake_responses_server() as (url, requests):
        settings = Settings(
            _env_file=None,
            data_root=tmp_path,
            analogforge_mode="live",
            test_hooks=True,
            allow_test_harness_provider=True,
            fake_openai_url=url,
            openai_api_key="local-test-key",
            openai_model="local-test-model",
        )
        monkeypatch.setattr(cli, "Settings", lambda: settings)
        monkeypatch.setattr(cli, "_store", lambda _: HealthyStore())
        exit_code = cli.main(["preflight", "--mode", "live", "--scenario", "live-hackathon-v1", "--json"])
    assert exit_code == 1  # the scenario remains unbound
    report = json.loads(capsys.readouterr().out)
    assert any(gate["code"] == "MODEL_CAPABILITY_READY" for gate in report["gates"])
    assert len(requests) == 2
    assert requests[0]["tools"][0]["strict"] is True
    assert requests[1]["text"]["format"]["type"] == "json_schema"


def test_live_run_requires_each_model_dependency():
    for overrides, dependency in (
        ({"openai_api_key": None, "openai_model": None}, "OPENAI_API_KEY"),
        ({"openai_api_key": "local-test-key", "openai_model": None}, "OPENAI_MODEL"),
    ):
        settings = Settings(_env_file=None, **overrides)
        with pytest.raises(ApiError) as caught:
            require_live(settings, "live")
        assert caught.value.status == 503
        assert caught.value.details["dependency"] == dependency


def test_replan_limit_preserves_both_counters_when_exhausted():
    ledger = BudgetLedger(limits={"candidate_switches": 4, "route_repairs_same_candidate": 4, "replans_total": 3})
    ledger.replan("NEW_CANDIDATE")
    ledger.replan("SAME_CANDIDATE")
    ledger.replan("SAME_CANDIDATE")
    before = ledger.document()
    with pytest.raises(BudgetExceeded):
        ledger.replan("NEW_CANDIDATE")
    assert ledger.document() == before


def test_renderer_digest_is_stable_under_export_validation():
    from analogforge.application.passports import assemble_bundle

    bundle = assemble_bundle(passport_case())
    renderer = renderer_factory()
    result = renderer.render(bundle, [], "json")
    try:
        validate_rendered(bundle, result, "json", renderer.renderer_version)
    except PersistenceError:
        pytest.fail("A deterministic renderer result failed its digest check")


def test_passport_metadata_requires_assurance_evidence():
    assert TABLES["passports"].c.assurance_evidence_id.nullable is False
