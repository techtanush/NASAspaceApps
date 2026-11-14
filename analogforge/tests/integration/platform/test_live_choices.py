"""Actual Responses provider choices drive a persisted next attempt.

Scientific checkpoint data is an explicit test double. This tests orchestration,
not source admission, route physics, or an external OpenAI account.
"""

from copy import deepcopy
from uuid import uuid4

from analogforge.application.discovery import candidate_record
from analogforge.application.registrar import RegisteredResult
from analogforge.application.verification import design, independently_verify
from analogforge.ports.hashing import canonical_sha256
from tests.integration.platform.test_runtime_journey import runtime as runtime
from tests.support.fake_openai_server import fake_responses_server


def test_actual_provider_repair_candidate_and_strategy_drive_next_attempt(runtime, monkeypatch):
    engine, store, ws, make = runtime
    run = make()
    with store.transaction(ws) as tx:
        mission = tx.require("mission_revisions", run["mission_revision_id"])
        rover = tx.require("rover_revisions", run["rover_revision_id"])
        live_id = str(uuid4())
        run = {**run, "id": live_id, "run_id": live_id, "mode": "live"}
        tx.create("runs", run)
    candidates = []
    for rank, name in enumerate(("attempted", "first-eligible", "provider-selected"), 1):
        candidate = candidate_record(
            {
                "name": name,
                "aoi": {**mission["target"], "body": "EARTH"},
                "origin": "USER_SUPPLIED",
                "novelty_status": "NOT_ASSESSED",
                "window_id": name,
                "rank": rank,
            },
            ws,
            run["id"],
            "live",
            [],
        )
        candidate["analysis_payload"] = {"connected_zones": []}
        candidates.append(candidate)
    constraints = {
        "schema_version": "1.0",
        "artifact_kind": "RASTER_ROUTE_TEST",
        "mode": "live",
        "resource_provider": "PHYSICAL_EARTH_MODEL",
        "mission_revision_id": mission["id"],
        "mission_content_sha256": mission["content_sha256"],
        "rover_revision_id": rover["id"],
        "rover_content_sha256": rover["content_sha256"],
        "candidate_window_id": candidates[0]["window_id"],
        "test_revision": 1,
        "strategy": "WAYPOINT_RETURN",
        "grid": {
            "analysis_evidence_id": None,
            "analysis_grid_sha256": "a" * 64,
            "crs_wkt": "TEST HARNESS CRS",
            "cell_size_m": 1,
            "width": 1,
            "height": 1,
        },
        "start": {"node_id": "S"},
        "return_required": True,
        "tasks": [],
        "surface_slope_cap_deg": 18,
        "exposures": [],
        "energy": {
            "model": None,
            "battery_wh": 100,
            "min_reserve_pct": 20,
            "rover_mass_kg": 100,
            "nominal_speed_mps": 1,
        },
        "solver": {"max_expansions": 10, "max_seconds": 1, "max_labels_per_node": 1, "seed": 0},
        "limitations": ["Control-flow fixture; no scientific validation"],
    }

    def design_payload(c):
        return {
            "constraints": c,
            "constraints_sha256": canonical_sha256(c),
            "required_exposures": [],
            "requirement_mapping": [],
            "unverified_requirement_ids": [r["id"] for r in mission["requirements"]],
        }

    first_test = design(
        ws,
        run["id"],
        "live",
        candidates[0]["id"],
        design_payload(constraints),
        parent_test_id=None,
        attempt_number=1,
        changed_elements=[],
    )
    first_test["search_payload"] = {"search_status": "FOUND"}
    failed_result = independently_verify(
        ws,
        run["id"],
        "live",
        first_test["id"],
        {
            "outcome": "FAIL",
            "failure_category": "ROUTE",
            "search_status": "FOUND",
            "verified_route_sha256": "b" * 64,
            "metrics": [],
            "violations": [],
            "limitations": [],
        },
        [],
    )
    receipt_id = str(uuid4())
    diagnosis = {
        "permitted_repairs": ["NEW_ROUTE", "NEW_CANDIDATE"],
        "recommended_repair": "NEW_ROUTE",
        "recommended_strategy": "EXPOSURE_COVERAGE",
        "primary_category": "ROUTE",
        "secondary_categories": [],
        "violated_constraint_ids": [],
        "explanation": "Control-flow fixture diagnosis",
        "proof_scope": "No physical inference",
    }
    with store.transaction(ws) as tx:
        current = tx.require("runs", run["id"])
        current.update(
            mode="live",
            state="DIAGNOSING",
            selected_candidate_id=candidates[0]["id"],
            candidate_ids=[c["id"] for c in candidates],
            test_ids=[first_test["id"]],
            test_result_ids=[failed_result["id"]],
            runtime={"active_test_id": first_test["id"], "mission_content_sha256": mission["content_sha256"]},
        )
        tx.replace("runs", run["id"], current, current["revision"])
        for candidate in candidates:
            tx.create("candidates", candidate)
        tx.create("tests", first_test)
        tx.create("test_results", failed_result)

    computed = []

    def controlled_science(inputs, *args, **kwargs):
        computed.append(inputs)
        if inputs.operation == "DIAGNOSE_RESULT":
            payload = diagnosis
        elif inputs.operation == "DESIGN_BENCHMARK":
            payload = design_payload(
                {
                    **constraints,
                    "strategy": inputs.strategy,
                    "candidate_window_id": inputs.candidate.window_id,
                    "test_revision": 2,
                }
            )
        else:
            assert inputs.operation == "SEARCH_ROUTE"
            payload = {"search_status": "EXHAUSTIVE_INFEASIBLE", "route_sha256": None}
        return RegisteredResult(payload, (), {}, {}, {"id": receipt_id, "mode": "live"}, "SUCCEEDED", ())

    def choose_other_permitted_options(submission, task):
        changed = deepcopy(submission)
        if task["role_key"] == "verification_replanning":
            choices = task["payload"]["allowed_choices"]
            assert choices["repair_target_revision_ids"]["NEW_CANDIDATE"] == [c["id"] for c in candidates[1:]]
            changed["payload"]["repair"].update(
                kind="NEW_CANDIDATE", target_revision_ids=[candidates[2]["id"]], strategy="MINIMUM_FEASIBLE_ROUTE"
            )
        return changed

    monkeypatch.setattr(engine, "_compute", controlled_science)
    with fake_responses_server(transform_submission=choose_other_permitted_options) as (url, requests):
        engine.settings.openai_api_key = "local-test-credential"
        engine.settings.openai_model = "configured-test-model"
        engine.settings.fake_openai_url = url
        engine.settings.test_hooks = True
        engine.settings.auth_mode = "local"
        engine.settings.allow_test_harness_provider = True
        run = engine.advance(run["id"], ws)
        assert run["state"] == "REPLANNING"
        run = engine.advance(run["id"], ws)
        assert run["selected_candidate_id"] == candidates[2]["id"]
        assert run["runtime"]["strategy"] == "MINIMUM_FEASIBLE_ROUTE"
        run = engine.advance(run["id"], ws)
        assert run["state"] == "VERIFYING"
        assert len(requests) == 6  # three real, serial two-turn Responses invocations
    with store.transaction(ws) as tx:
        attempts = tx.list("tests", {"run_id": run["id"]})
        assert len(attempts) == 2
        assert attempts[1]["candidate_id"] == candidates[2]["id"]
        assert attempts[1]["strategy"] == "MINIMUM_FEASIBLE_ROUTE"
        assert attempts[1]["constraints"]["mission_content_sha256"] == mission["content_sha256"]
        assert attempts[1]["constraints"]["rover_content_sha256"] == rover["content_sha256"]
        assert tx.require("test_results", failed_result["id"])["outcome"] == "FAIL"
        decisions = tx.list("role_results", {"run_id": run["id"], "role": "verification_replanning"})
        assert decisions[0]["payload"]["payload"]["repair"]["kind"] == "NEW_CANDIDATE"
    assert str(computed[1].candidate.candidate_id) == candidates[2]["id"]
