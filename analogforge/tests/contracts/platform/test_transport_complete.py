"""PLT-02 consumer proof: all frozen operations over real ASGI, SQL and worker boundaries."""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from analogforge.api.dependencies import Principal
from analogforge.application.seed import seed_synthetic
from analogforge.db.store import Store
from analogforge.jobs.worker import Worker
from analogforge.main import create_app
from analogforge.ports.domain_models import CompositePortfolio, ReviewRequest
from analogforge.settings import Settings
from tests.integration.platform.test_journey_api import FIXTURES, drain, journey_store
from tests.integration.platform.test_migrations import platform_store
from tests.support.factories import renderer_factory, science_factory

__all__ = ["journey_store", "platform_store"]
SPEC = json.loads((Path(__file__).parents[3] / "contracts" / "openapi.bundled.json").read_text())
OPERATIONS = {
    operation["operationId"]: (method.upper(), path, operation)
    for path, methods in SPEC["paths"].items()
    for method, operation in methods.items()
    if method in {"get", "post"}
}


def validate_document(value: Any, schema: dict[str, Any]) -> None:
    Draft202012Validator({"components": SPEC["components"], **schema}, format_checker=FormatChecker()).validate(value)


class Transport:
    """Independent consumer validator; no application validator or endpoint mock is used."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.covered: set[str] = set()
        self.observations: list[dict[str, Any]] = []

    def call(
        self,
        operation_id: str,
        path: str,
        *,
        status: int = 200,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        extra_status: bool = False,
    ) -> httpx.Response:
        method, template, operation = OPERATIONS[operation_id]
        route = path.split("?", 1)[0]
        assert re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), route), (operation_id, route)
        sent_headers = headers or ({"Idempotency-Key": str(uuid4())} if method == "POST" else {})
        if body is not None and status < 400:
            validate_document(body, operation["requestBody"]["content"]["application/json"]["schema"])
        response = self.client.request(method, "/api/v1" + path, json=body, headers=sent_headers)
        assert response.status_code == status, (operation_id, status, response.status_code, response.text)
        definition = operation["responses"].get(str(status))
        if definition is None:
            assert extra_status, (operation_id, "Undocumented response", status)
            validate_document(response.json(), {"$ref": "#/components/schemas/ErrorEnvelope"})
            return response
        contents = definition.get("content", {})
        if not contents and status >= 400:
            validate_document(response.json(), {"$ref": "#/components/schemas/ErrorEnvelope"})
            self.covered.add(operation_id)
            self.observations.append({"operation_id": operation_id, "status": status, "schema": "ErrorEnvelope"})
            return response
        response_type = response.headers.get("content-type", "").split(";", 1)[0]
        selected = contents.get(response_type) or contents.get("application/octet-stream")
        assert selected is not None, (operation_id, response_type, contents)
        schema = selected["schema"]
        if operation_id == "getPassportExport" and status == 200 and response_type == "application/json":
            # Architecture 35 requires the JSON export object; the frozen OpenAPI
            # incorrectly declares a JSON string. Keep the mismatch observable,
            # never validate response.text to conceal it. Root records the kit CR.
            exported = response.json()
            assert isinstance(exported, dict) and exported["export_schema_version"] == "1.0"
            assert {"manifest_sha256", "canonical_manifest", "bundle"} <= exported.keys()
            if schema == {"type": "string"}:
                with pytest.raises(ValidationError):
                    validate_document(exported, schema)
            else:
                # The central C3 correction can now be tested unchanged in the
                # integration checkout; no response is exempted from validation.
                validate_document(exported, schema)
        elif schema.get("type") == "string":
            validate_document(response.text, schema)
        else:
            validate_document(response.json(), schema)
        for header, requirement in definition.get("headers", {}).items():
            assert header in response.headers, (operation_id, "Missing header", header)
            value: Any = response.headers[header]
            if requirement["schema"].get("type") == "integer":
                value = int(value)
            validate_document(value, requirement["schema"])
        self.covered.add(operation_id)
        self.observations.append(
            {
                "operation_id": operation_id,
                "status": status,
                "schema": "KNOWN_JSON_EXPORT_CONTRACT_CONFLICT"
                if operation_id == "getPassportExport"
                and status == 200
                and response_type == "application/json"
                and schema == {"type": "string"}
                else "PASSED",
            }
        )
        return response

    def repeatable(self, operation_id: str, path: str, body: dict[str, Any], status: int) -> dict[str, Any]:
        headers = {"Idempotency-Key": str(uuid4())}
        original = self.call(operation_id, path, body=body, status=status, headers=headers)
        duplicate = self.call(operation_id, path, body=body, status=status, headers=headers)
        assert duplicate.json() == original.json()
        changed = copy.deepcopy(body)
        if "expected_revision" in changed:
            changed["expected_revision"] += 100
        elif "name" in changed:
            changed["name"] += " changed"
        else:
            changed["dataset_lock_id"] = "another-valid-lock"
        conflict = self.call(operation_id, path, body=changed, status=409, headers=headers)
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
        return dict(original.json())


@pytest.mark.db
def test_all_43_operations_have_real_validated_responses(journey_store: Store, tmp_path: Path) -> None:
    store = journey_store
    workspace, subject = str(uuid4()), str(uuid4())
    store.ensure_workspace(workspace, "All operations consumer")
    settings = Settings(
        _env_file=None, database_url=store.engine.url.render_as_string(hide_password=False), data_root=tmp_path / "data"
    )
    seed_synthetic(None, settings)
    application = create_app(
        settings=settings,
        store=store,
        science=science_factory(),
        renderer=renderer_factory(),
        identity_provider=lambda _request: Principal(workspace, subject),
    )
    worker = Worker(store, application.state.runtime.handle_job)
    content = json.loads((FIXTURES / "missions" / "mission-graph-regression.json").read_text())
    draft = {field: content[field] for field in ("name", "objective", "target", "requirements", "assumptions")}
    rover_input = json.loads((FIXTURES / "rovers" / "ares-1.json").read_text())
    with TestClient(application) as client:
        transport = Transport(client)
        for operation, path in (
            ("healthLive", "/health/live"),
            ("healthReady", "/health/ready"),
            ("getCapabilities", "/capabilities"),
            ("getScenarioConfig", "/configuration/scenarios/synthetic-graph-regression-v1"),
        ):
            transport.call(operation, path)
        header = transport.repeatable("createMission", "/missions", draft, 201)
        saved = transport.repeatable(
            "saveMissionDraft",
            f"/missions/{header['id']}/drafts",
            {"expected_revision": header["revision"], "draft": draft},
            201,
        )
        transport.call(
            "saveMissionDraft",
            f"/missions/{header['id']}/drafts",
            body={"expected_revision": header["revision"], "draft": draft},
            status=409,
        )
        transport.call("getMissionDraft", f"/mission-drafts/{saved['id']}")
        header = transport.call("getMission", f"/missions/{header['id']}").json()
        revision = transport.repeatable(
            "createMissionRevision",
            f"/missions/{header['id']}/revisions",
            {"expected_revision": header["revision"], "contract": content},
            201,
        )
        transport.call(
            "createMissionRevision",
            f"/missions/{header['id']}/revisions",
            body={"expected_revision": header["revision"], "contract": content},
            status=409,
        )
        header = transport.call("getMission", f"/missions/{header['id']}").json()
        preparation_body = {"expected_revision": header["revision"], "mode": "synthetic", "rover_revision_id": None}
        preparation = transport.repeatable(
            "prepareMissionFingerprint", f"/missions/{header['id']}/fingerprint", preparation_body, 202
        )
        assert worker.run_once()
        job = transport.call("getJob", f"/jobs/{preparation['job_id']}").json()
        assert job["state"] == "SUCCEEDED", job
        transport.call(
            "prepareMissionFingerprint", f"/missions/{header['id']}/fingerprint", body=preparation_body, status=409
        )
        # The fingerprint uses the body's standard preset. Propose the graph contract
        # explicitly so this consumer path stays the small canonical graph experiment.
        header = transport.call("getMission", f"/missions/{header['id']}").json()
        revision = transport.call(
            "createMissionRevision",
            f"/missions/{header['id']}/revisions",
            status=201,
            body={"expected_revision": header["revision"], "contract": content},
        ).json()
        header = transport.call("getMission", f"/missions/{header['id']}").json()
        acceptance_body = {"expected_revision": header["revision"], "revision_id": revision["id"]}
        accepted = transport.repeatable(
            "acceptMissionRevision", f"/missions/{header['id']}/accept", acceptance_body, 200
        )
        transport.call("acceptMissionRevision", f"/missions/{header['id']}/accept", body=acceptance_body, status=409)
        transport.call("getMissionRevision", f"/mission-revisions/{accepted['id']}")
        rover = transport.repeatable("createRover", "/rovers", rover_input, 201)
        revised_profile = {**rover_input, "name": rover_input["name"] + " revision two"}
        revision_body = {"expected_revision": rover["revision"], "profile": revised_profile}
        rover = transport.repeatable(
            "createRoverRevision", f"/rovers/{rover['rover_id']}/revisions", revision_body, 201
        )
        transport.call("createRoverRevision", f"/rovers/{rover['rover_id']}/revisions", body=revision_body, status=409)
        transport.call("getRover", f"/rovers/{rover['rover_id']}")
        transport.call("getRoverRevision", f"/rover-revisions/{rover['id']}")
        command = transport.repeatable(
            "createRun",
            "/runs",
            {
                "mission_revision_id": accepted["id"],
                "rover_revision_id": rover["id"],
                "mode": "synthetic",
                "dataset_lock_id": "synthetic-policy-v1",
                "scenario_config_id": "synthetic-graph-regression-v1",
            },
            202,
        )
        run_id = command["run_id"]
        ready = drain(worker, store, workspace, run_id, "AWAITING_REVIEW")
        candidates = transport.call("listEarthAnalogCandidate", f"/candidates?run_id={run_id}&limit=100").json()[
            "items"
        ]
        action_body = {
            "action_type": "PROVE_IT",
            "expected_revision": ready["revision"],
            "payload": {"candidate_id": candidates[0]["id"]},
        }
        transport.repeatable("submitRunAction", f"/runs/{run_id}/actions", action_body, 202)
        transport.call("submitRunAction", f"/runs/{run_id}/actions", body=action_body, status=409)
        final = drain(worker, store, workspace, run_id, "COMPLETED")
        transport.call("getRun", f"/runs/{run_id}")
        for operation, path in (
            ("listMissions", "/missions"),
            ("listRovers", "/rovers"),
            ("listRuns", "/runs"),
            ("listQualificationDimension", f"/qualifications?run_id={run_id}&limit=100"),
            ("listVerificationTest", f"/tests?run_id={run_id}"),
            ("listAgentActions", f"/agent-actions?run_id={run_id}"),
            ("listCritiques", f"/critiques?run_id={run_id}"),
            ("listDisplayLayers", f"/display-layers?run_id={run_id}"),
        ):
            transport.call(operation, path)
        for identifier in final["candidate_ids"]:
            transport.call("getEarthAnalogCandidate", f"/candidates/{identifier}")
        for identifier in final["qualification_ids"]:
            transport.call("getQualificationDimension", f"/qualifications/{identifier}")
        for identifier in final["test_ids"]:
            transport.call("getVerificationTest", f"/tests/{identifier}")
        for identifier in final["test_result_ids"]:
            transport.call("getTestResult", f"/test-results/{identifier}")
        transport.call("getTargetProfile", f"/target-profiles/{final['target_profile_id']}")
        transport.call("getCompatibility", f"/compatibility?run_id={run_id}&candidate_id={candidates[0]['id']}")
        with store.transaction(workspace) as unit:
            receipts = unit.list("tool_receipts", {"run_id": run_id})
            evidence = unit.list("evidence", {"run_id": run_id})
            review_id = str(uuid4())
            review = ReviewRequest(
                review_id=review_id,
                kind="EVIDENCE_READY",
                summary="Reviewable evidence",
                evidence_ids=[evidence[0]["id"]],
                proposal_artifact_sha256=None,
                blocked_requirement_ids=[],
                allowed_actions=["PROVE_IT"],
                created_at=datetime.now(UTC),
                status="APPROVED",
            ).model_dump(mode="json")
            unit.create("reviews", {**review, "id": review_id, "run_id": run_id})
            portfolio = CompositePortfolio(
                schema_version="1.0",
                id=uuid4(),
                workspace_id=workspace,
                run_id=run_id,
                mode="synthetic",
                created_at=datetime.now(UTC),
                candidate_ids=final["candidate_ids"],
                requirement_assignments=[],
                objective_value=0,
                algorithm_id="consumer-read-model-fixture",
                residual_requirement_ids=[row["id"] for row in content["requirements"]],
                limitations=["Read transport fixture; no scientific optimization is claimed."],
            ).model_dump(mode="json")
            unit.create("portfolios", portfolio)
        assert receipts and evidence
        transport.call("getToolReceipt", f"/tool-receipts/{receipts[0]['id']}")
        transport.call("getEvidenceRecord", f"/evidence/{evidence[0]['id']}")
        transport.call("getReview", f"/reviews/{review_id}")
        transport.call("getCompositePortfolio", f"/portfolios/{portfolio['id']}")
        passport = transport.call("getAnalogPassport", f"/passports/{final['passport_id']}").json()
        assurance = transport.call("getEvidenceRecord", f"/evidence/{passport['assurance_evidence_id']}").json()
        artifact = transport.call("getArtifact", f"/artifacts/{assurance['artifact_sha256']}")
        assert artifact.headers["X-Artifact-SHA256"] == assurance["artifact_sha256"]
        pending = transport.call("getPassportExport", f"/passports/{passport['id']}/exports/json", status=202)
        assert pending.json()["state"] in {"QUEUED", "RUNNING"}
        for _ in range(20):
            if not worker.run_once():
                break
        for extension in ("html", "json", "csv"):
            transport.call("getPassportExport", f"/passports/{passport['id']}/exports/{extension}")
        event_response = transport.call("streamRunEvents", f"/runs/{run_id}/events?after=0")
        events = [
            json.loads(line.removeprefix("data:"))
            for line in event_response.text.splitlines()
            if line.startswith("data:")
        ]
        assert events and events[-1]["state"] == "COMPLETED"
        assert [event["seq"] for event in events] == sorted({event["seq"] for event in events})
        for event in events:
            validate_document(event, {"$ref": "#/components/schemas/RunEvent"})
        assert transport.covered == set(OPERATIONS), sorted(set(OPERATIONS) - transport.covered)
        report = {
            "operation_count": len(transport.covered),
            "covered_operation_ids": sorted(transport.covered),
            "responses": transport.observations,
            "known_contract_conflicts": [
                "OpenAPI JSON passport export declares string; architecture 35 requires the actual JSON object."
            ],
        }
        out = Path("out")
        out.mkdir(exist_ok=True)
        (out / "transport-coverage.json").write_text(json.dumps(report, indent=2) + "\n")


@pytest.mark.db
def test_every_object_read_missing_id_is_validated_not_found(journey_store: Store, tmp_path: Path) -> None:
    workspace, subject = str(uuid4()), str(uuid4())
    journey_store.ensure_workspace(workspace)
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    seed_synthetic(None, settings)
    app = create_app(
        settings=settings,
        store=journey_store,
        science=science_factory(),
        renderer=renderer_factory(),
        identity_provider=lambda _request: Principal(workspace, subject),
    )
    with TestClient(app) as client:
        transport = Transport(client)
        for operation_id, (method, path, _) in OPERATIONS.items():
            if method == "GET" and "{id}" in path and operation_id != "getScenarioConfig":
                path = path.replace("{id}", str(uuid4())).replace("{format}", "json")
                response = transport.call(operation_id, path, status=404)
                assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.db
def test_failed_job_response_has_complete_safe_error_envelope(journey_store: Store, tmp_path: Path) -> None:
    from tests.integration.platform.test_migrations import seed_run

    workspace, run = seed_run(journey_store)
    with journey_store.transaction(workspace) as unit:
        job = unit.enqueue("ADVANCE_RUN", {"stage": "failure-path"}, run_id=run["id"])
        unit.replace("jobs", job["id"], {**job, "state": "FAILED", "error": {"code": "TOOL_TIMEOUT"}})
    settings = Settings(
        _env_file=None,
        database_url=journey_store.engine.url.render_as_string(hide_password=False),
        data_root=tmp_path / "data",
    )
    app = create_app(
        settings=settings, store=journey_store, identity_provider=lambda _request: Principal(workspace, "operator")
    )
    with TestClient(app) as client:
        response = Transport(client).call("getJob", f"/jobs/{job['id']}").json()
        assert response["state"] == "FAILED" and response["error"]["error"]["code"] == "TOOL_TIMEOUT"
