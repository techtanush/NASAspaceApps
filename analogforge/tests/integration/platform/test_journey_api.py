"""The same persisted API journey runs with fake or real external seams.

Set AF_SCIENCE_IMPL=real AF_RENDERER_IMPL=real at merge. This file does not mock
an endpoint, write a verdict or replace any scheduler/registrar implementation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
import rfc8785
import sqlalchemy as sa
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.jobs.worker import Worker
from analogforge.main import create_app
from analogforge.ports.hashing import bytes_sha256
from analogforge.settings import Settings
from tests.integration.platform.test_migrations import platform_store
from tests.support.factories import renderer_factory, science_factory

__all__ = ["platform_store"]
FIXTURES = Path(__file__).parents[2] / "fixtures" / "kit"


@pytest.fixture
def journey_store(platform_store):
    # Worker claiming is intentionally global. A disposable database prevents an API
    # journey from claiming another test's deliberately incomplete lease fixture.
    name = "journey_" + uuid4().hex
    with platform_store.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            sa.text(f"CREATE DATABASE \"{name}\" TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'")
        )
    store = Store(platform_store.engine.url.set(database=name).render_as_string(hide_password=False))
    store.migrate()
    try:
        yield store
    finally:
        store.close()
        with platform_store.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(sa.text(f'DROP DATABASE "{name}"'))


def post(client, path, payload, expected):
    response = client.post("/api/v1" + path, json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == expected, response.text
    return response.json()


def get(client, path):
    response = client.get("/api/v1" + path)
    assert response.status_code == 200, response.text
    return response.json()


def drain(worker, store, workspace_id, run_id, target):
    for _ in range(300):
        with store.transaction(workspace_id) as unit:
            run = unit.require("runs", run_id)
        if run["state"] == target:
            return run
        assert run["state"] not in {"FAILED", "BLOCKED", "CANCELLED"}, run
        assert worker.run_once(), f"No queued work before {target}; state={run['state']}"
    pytest.fail(f"Run did not reach {target} within the finite worker-step budget")


@pytest.mark.db
@pytest.mark.parametrize(
    "scenario,mission_file,rover_file,expected_outcomes",
    [
        ("synthetic-mars-mobility-v1", "mission-mars-mobility.json", "ares-1.json", ["FAIL", "FAIL", "PASS"]),
        ("synthetic-graph-regression-v1", "mission-graph-regression.json", "ares-1.json", ["FAIL", "PASS"]),
        ("synthetic-moon-gap-v1", "mission-moon-gap.json", None, []),
        ("synthetic-mars-mobility-v1", "mission-mars-mobility.json", "practice-lite.json", ["FAIL", "FAIL"]),
        (
            "synthetic-mars-mobility-v1",
            "mission-mars-mobility.json",
            "practice-no-energy-model.json",
            ["FAIL", "INCONCLUSIVE"],
        ),
        ("synthetic-mars-mobility-v1", "mission-mars-mobility.json", "practice-small-battery.json", ["FAIL"]),
    ],
)
def test_full_accepted_contract_to_immutable_passport_and_downloads(
    journey_store, tmp_path, scenario, mission_file, rover_file, expected_outcomes
):
    platform_store = journey_store
    workspace_id = str(uuid4())
    platform_store.ensure_workspace(workspace_id, "Journey workspace")
    settings = Settings(
        _env_file=None,
        database_url=platform_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    seed_synthetic(None, settings)
    subject_id = str(uuid4())
    application = create_app(
        settings=settings,
        store=platform_store,
        science=science_factory(),
        renderer=renderer_factory(),
        identity_provider=lambda _request: Principal(workspace_id, subject_id),
    )

    def checked_handler(job):
        try:
            application.state.runtime.handle_job(job)
        except (RuntimeError, ValueError, TypeError, KeyError, sa.exc.SQLAlchemyError) as error:
            raise AssertionError(f"Unexpected worker failure: {type(error).__name__}: {error}") from error

    worker = Worker(platform_store, checked_handler)
    content = json.loads((FIXTURES / "missions" / mission_file).read_text())
    with TestClient(application) as client:
        header = post(
            client,
            "/missions",
            {key: content[key] for key in ("name", "objective", "target", "requirements", "assumptions")},
            201,
        )
        revision = post(
            client,
            f"/missions/{header['id']}/revisions",
            {"expected_revision": header["revision"], "contract": content},
            201,
        )
        current = get(client, f"/missions/{header['id']}")
        accepted = post(
            client,
            f"/missions/{header['id']}/accept",
            {"expected_revision": current["revision"], "revision_id": revision["id"]},
            200,
        )
        rover = (
            post(client, "/rovers", json.loads((FIXTURES / "rovers" / rover_file).read_text()), 201)
            if rover_file
            else None
        )
        run_cmd = post(
            client,
            "/runs",
            {
                "mission_revision_id": accepted["id"],
                "rover_revision_id": rover["id"] if rover else None,
                "mode": "synthetic",
                "dataset_lock_id": "synthetic-policy-v1",
                "scenario_config_id": scenario,
            },
            202,
        )
        run_id = run_cmd["run_id"]
        pre = drain(worker, platform_store, workspace_id, run_id, "AWAITING_REVIEW" if rover else "COMPLETED")
        if rover:
            candidates = get(client, f"/candidates?run_id={run_id}&limit=25")["items"]
            if scenario == "synthetic-mars-mobility-v1":
                assert len(candidates) == 6
                assert sum(candidate["origin"] == "KNOWN_CONTROL" for candidate in candidates) == 1
                assert any(
                    candidate["origin"] == "DISCOVERED" and candidate["novelty_status"] == "NOT_IN_REFERENCE_LIST"
                    for candidate in candidates
                )
                assessed = [get(client, f"/qualifications/{row_id}") for row_id in pre["qualification_ids"]]
                a = next(candidate for candidate in candidates if candidate["name"] == "Practice grid-r0c1")
                for requirement_id, status in (
                    ("R-SLOPE-AVAILABILITY", "PASS"),
                    ("R-EXPOSURE", "UNKNOWN"),
                    ("R-CLEARANCE", "UNKNOWN"),
                    ("R-GRAVITY", "GAP"),
                ):
                    assert any(
                        row["candidate_id"] == a["id"]
                        and row["requirement_id"] == requirement_id
                        and row["status"] == status
                        for row in assessed
                    )
                compatibility = get(client, f"/compatibility?run_id={run_id}&candidate_id={a['id']}")
                assert any(
                    row["metric_id"] == "ground_clearance_m" and row["status"] == "UNKNOWN"
                    for row in compatibility["dimensions"]
                )
                with platform_store.transaction(workspace_id) as unit:
                    assessments = unit.list("compatibility", {"run_id": run_id, "candidate_id": a["id"]})
                    assert assessments[-1]["payload"]["preliminary"] is True
                    issues = unit.list("critiques", {"run_id": run_id})
                    assert any(
                        issue["severity"] == "BLOCKING"
                        and issue["status"] == "RESOLVED"
                        and issue["resolution_evidence_ids"]
                        for issue in issues
                    )
            candidate = next(
                (candidate for candidate in candidates if candidate["name"] == "Practice grid-r0c1"), candidates[0]
            )
            if "practice-lite" in rover_file or "practice-no-energy" in rover_file or "practice-small" in rover_file:
                candidate = next(candidate for candidate in candidates if candidate["name"] == "Practice grid-r0c0")
            post(
                client,
                f"/runs/{run_id}/actions",
                {
                    "action_type": "PROVE_IT",
                    "expected_revision": pre["revision"],
                    "payload": {"candidate_id": candidate["id"]},
                },
                202,
            )
            final = drain(worker, platform_store, workspace_id, run_id, "COMPLETED")
        else:
            final = pre
            compatibility = client.get(
                f"/api/v1/compatibility?run_id={run_id}&candidate_id={final['candidate_ids'][0]}"
            )
            assert compatibility.status_code == 409
            assert compatibility.json()["error"]["code"] == "ROVER_REQUIRED"
        public_run = get(client, f"/runs/{run_id}")
        assert public_run["state"] == "COMPLETED"
        assert public_run["mission_revision_id"] == accepted["id"]
        results = [get(client, f"/test-results/{result_id}") for result_id in public_run["test_result_ids"]]
        assert [row["outcome"] for row in results] == expected_outcomes
        if scenario == "synthetic-graph-regression-v1":
            values = [{metric["metric_id"]: metric["value"] for metric in row["metrics"]} for row in results]
            assert values[0]["route_distance_m"] == 120
            assert values[0]["energy_conservative_wh"] == 26
            assert values[1]["route_distance_m"] == 230
            assert values[1]["energy_conservative_wh"] == 30
        for test_id in public_run["test_ids"]:
            test = get(client, f"/tests/{test_id}")
            constraints_response = client.get(f"/api/v1/artifacts/{test['constraints_sha256']}")
            assert constraints_response.status_code == 200
            constraints = constraints_response.json()
            assert constraints["mission_content_sha256"] == accepted["content_sha256"]
            assert constraints["rover_content_sha256"] == rover["content_sha256"]
        passport = get(client, f"/passports/{public_run['passport_id']}")
        assurance = get(client, f"/evidence/{passport['assurance_evidence_id']}")
        report_response = client.get(f"/api/v1/artifacts/{assurance['artifact_sha256']}")
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["publication"] == "LIMITED"
        assert all(
            {gate["gate_id"] for gate in claim["gates"]} == {f"SC-{number:02}" for number in range(1, 16)}
            for claim in report["claims"]
        )
        assert len(passport["test_result_ids"]) == len(expected_outcomes)
        assert passport["assurance_evidence_id"] in passport["evidence_ids"]
        assert report["mission_content_sha256"] == accepted["content_sha256"]
        # Publication is a real 202 -> job -> 200 flow, not request-inline rendering.
        pending = client.get(f"/api/v1/passports/{passport['id']}/exports/json")
        assert pending.status_code == 202
        assert "Retry-After" in pending.headers
        for _ in range(20):
            if not worker.run_once():
                break
        for fmt in ("html", "json", "csv"):
            first = client.get(f"/api/v1/passports/{passport['id']}/exports/{fmt}")
            second = client.get(f"/api/v1/passports/{passport['id']}/exports/{fmt}")
            assert first.status_code == 200, first.text
            assert first.content == second.content
            assert first.headers["X-Artifact-SHA256"] == bytes_sha256(first.content)
            assert first.headers["ETag"] == f'"{bytes_sha256(first.content)}"'
            assert first.headers["X-Content-Type-Options"] == "nosniff"
            assert "attachment" in first.headers["Content-Disposition"]
            assert b"OPENAI_API_KEY" not in first.content
            assert b"EARTHDATA_TOKEN" not in first.content
            if fmt == "json":
                exported = first.json()
                assert (
                    hashlib.sha256(rfc8785.dumps(exported["canonical_manifest"])).hexdigest()
                    == passport["manifest_sha256"]
                )
                assert len(exported["bundle"]["attempts"]) == len(expected_outcomes)
        with platform_store.transaction(workspace_id) as unit:
            persisted = unit.require("runs", run_id)
            assert persisted["mission_revision_id"] == accepted["id"]
            assert all(row["input_sha256"] for row in unit.list("tool_receipts", {"run_id": run_id}))
