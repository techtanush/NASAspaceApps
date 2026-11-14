"""One real bound product must yield an honest limited result without inventing the other."""

import json
import shutil
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.application import datasets
from analogforge.application.capabilities import get_scenarios
from analogforge.application.seed import seed_synthetic
from analogforge.cli import _bind
from analogforge.jobs.worker import Worker
from analogforge.main import create_app
from analogforge.settings import Settings
from tests.integration.platform.test_journey_api import FIXTURES, drain, get, journey_store, post
from tests.integration.platform.test_migrations import platform_store
from tests.support.factories import renderer_factory, science_factory

__all__ = ["journey_store", "platform_store"]


@pytest.mark.db
@pytest.mark.parametrize("side", ["earth", "target"])
def test_single_product_keeps_missing_side_unknown_and_publishes_limited(journey_store, tmp_path, side):
    config = tmp_path / "config"
    shutil.copytree(Path("config"), config)
    settings = Settings(
        _env_file=None, database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data", config_dir=config,
    )
    datasets.generate_practice(settings)
    identifier = "practice-earth-grid-v1" if side == "earth" else "practice-mars-target-v1"
    assert datasets.validate_dataset(settings, identifier, True)["status"] == "PASS"
    datasets.create_lock(settings, "partial-data-policy-v1", [identifier])
    _bind(settings, Namespace(
        scenario_id="local-dataset-practice-v1", policy_id="partial-data-policy-v1",
        target_terrain=identifier if side == "target" else None,
        earth_terrain=identifier if side == "earth" else None, earth_mineral=None, lunar_thermal=None,
    ))
    scenario = get_scenarios(settings)["local-dataset-practice-v1"]
    assert scenario["target_source" if side == "earth" else "earth_source"] is None
    seed_synthetic(None, settings)
    workspace, subject = str(uuid4()), str(uuid4())
    journey_store.ensure_workspace(workspace)
    app = create_app(settings=settings, store=journey_store, science=science_factory(), renderer=renderer_factory(),
                     identity_provider=lambda _: Principal(workspace, subject))
    worker = Worker(journey_store, app.state.runtime.handle_job)
    content = json.loads((FIXTURES / "missions/mission-mars-mobility.json").read_text())
    with TestClient(app) as client:
        mission = post(client, "/missions", {k: content[k] for k in (
            "name", "objective", "target", "requirements", "assumptions")}, 201)
        revision = post(client, f"/missions/{mission['id']}/revisions",
                        {"expected_revision": mission["revision"], "contract": content}, 201)
        mission = get(client, f"/missions/{mission['id']}")
        accepted = post(client, f"/missions/{mission['id']}/accept",
                        {"expected_revision": mission["revision"], "revision_id": revision["id"]}, 200)
        command = post(client, "/runs", {
            "mission_revision_id": accepted["id"], "rover_revision_id": None, "mode": "synthetic",
            "dataset_lock_id": "partial-data-policy-v1", "scenario_config_id": "local-dataset-practice-v1",
        }, 202)
        final = drain(worker, journey_store, workspace, command["run_id"], "COMPLETED")
        assert not final["test_ids"] and not final["test_result_ids"]
        target = get(client, f"/target-profiles/{final['target_profile_id']}")
        if side == "earth":
            assert target["metrics"] == [] and target["unavailable_dimensions"]
            assert final["candidate_ids"]
        else:
            assert not final["candidate_ids"] and final["runtime"]["stop_reason"] == "NO_COVERAGE"
        passport = get(client, f"/passports/{final['passport_id']}")
        audit = get(client, f"/evidence/{passport['assurance_evidence_id']}")
        report = get(client, f"/artifacts/{audit['artifact_sha256']}")
        assert report["publication"] == "LIMITED"
        if side == "target":
            assert all(row["qualification_status"] == "UNKNOWN" for row in report["claims"])
        for _ in range(20):
            if not worker.run_once():
                break
        for extension in ("html", "json", "csv"):
            assert client.get(f"/api/v1/passports/{passport['id']}/exports/{extension}").status_code == 200
