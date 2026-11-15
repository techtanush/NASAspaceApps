"""Activity is an authorized, bounded projection of real transitions, without provider internals."""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analogforge.api.dependencies import Principal
from analogforge.api.errors import ApiError
from analogforge.application.activity import decode_cursor, encode_cursor, page
from analogforge.db.store import NotFound


class ActivityStore:
    def __init__(self):
        self.workspace, self.run, self.mission = (str(uuid4()) for _ in range(3))
        self.rows = {
            "runs": {
                self.run: {
                    "id": self.run,
                    "workspace_id": self.workspace,
                    "mission_revision_id": self.mission,
                    "mode": "live",
                    "state": "QUALIFYING",
                    "last_event_seq": 0,
                }
            },
            "mission_revisions": {
                self.mission: {
                    "id": self.mission,
                    "workspace_id": self.workspace,
                    "name": "Lunar ice prospecting",
                    "requirements": [{"id": "ICE-SUPPORT"}],
                }
            },
        }
        self.events, self.queries = [], []
        self.on_query = None

    @contextmanager
    def transaction(self, workspace):
        def get(kind, identifier, **_kwargs):
            row = self.rows.get(kind, {}).get(identifier)
            return deepcopy(row) if row and row["workspace_id"] == workspace else None

        def require(kind, identifier, **kwargs):
            row = get(kind, identifier, **kwargs)
            if row is None:
                raise NotFound()
            return row

        def activity_events(run_id, *, after, limit, through):
            self.queries.append((run_id, after, limit))
            if self.on_query is not None:
                callback, self.on_query = self.on_query, None
                callback()
            events = [e for e in self.events if e["run_id"] == run_id and after < e["seq"] <= through]
            return sorted(events, key=lambda e: e["seq"])[:limit]

        yield SimpleNamespace(get=get, require=require, activity_events=activity_events)

    def record(self, kind, **fields):
        row = {"id": str(uuid4()), "workspace_id": self.workspace, "run_id": self.run, **fields}
        self.rows.setdefault(kind, {})[row["id"]] = row
        return row

    def event(self, event_type, **payload):
        seq = len(self.events) + 1
        event = {
            "run_id": self.run,
            "seq": seq,
            "event_type": event_type,
            "state": "QUALIFYING",
            "created_at": "2026-11-14T01:02:03Z",
            "summary": "reasoning sk-providersecret",
            "evidence_ids": payload.get("evidence_ids", []),
            "payload": payload,
        }
        self.events.insert(0, event)  # Equal timestamps and reversed storage must never affect sequence order.
        self.rows["runs"][self.run]["last_event_seq"] = seq
        return event


def test_paging_and_reload_preserve_append_only_sequence_and_event_times():
    store = ActivityStore()
    store.event("tool.started", operation="CHARACTERIZE_TARGET")
    store.event("tool.completed", operation="CHARACTERIZE_TARGET", status="LIMITED")
    store.event("run.blocked")
    first = page(store, store.workspace, store.run, limit=2)
    second = page(store, store.workspace, store.run, limit=2, cursor=first["next_cursor"])
    assert [i["seq"] for i in first["items"] + second["items"]] == [1, 2, 3]
    assert [i["status"] for i in first["items"] + second["items"]] == ["RUNNING", "COMPLETED", "BLOCKED"]
    assert "limited evidence" in first["items"][1]["summary"]
    assert all(i["created_at"] == "2026-11-14T01:02:03Z" for i in first["items"] + second["items"])
    assert second["next_cursor"] is None
    store.event("run.failed")
    assert page(store, store.workspace, store.run, limit=2)["items"] == first["items"]
    resumed = page(store, store.workspace, store.run, limit=2, cursor=first["next_cursor"])
    assert [i["status"] for i in resumed["items"]] == ["BLOCKED", "FAILED"]
    assert resumed["last_event_seq"] == 4
    assert store.queries == [(store.run, 0, 3), (store.run, 2, 3), (store.run, 0, 3), (store.run, 2, 3)]


def test_summary_adapts_to_actual_mission_candidate_requirement_and_status():
    store = ActivityStore()
    candidate = store.record("candidates", name="Polar basalt ridge")
    invocation = store.record(
        "invocations",
        role="scientific_worker",
        task_kind="COMPARE_REQUIREMENT",
        candidate_id=candidate["id"],
        requirement_id="ICE-SUPPORT",
    )
    evidence = store.record("evidence")
    receipt = store.record("tool_receipts", invocation_id=invocation["id"], status="BLOCKED")
    store.event("tool.completed", receipt_id=receipt["id"], evidence_ids=[evidence["id"]])
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["status"] == "BLOCKED"
    assert "ICE-SUPPORT" in item["summary"] and "Polar basalt ridge" in item["summary"]
    assert item["invocation_id"] == invocation["id"] and item["tool_receipt_id"] == receipt["id"]
    assert item["evidence_ids"] == [evidence["id"]]
    store.event("tool.started", operation="SCREEN_CANDIDATES")
    item = page(store, store.workspace, store.run)["items"][-1]
    assert "Lunar ice prospecting" in item["summary"]
    store.rows["mission_revisions"][store.mission]["name"] = "Martian dune mobility"
    assert "Martian dune mobility" in page(store, store.workspace, store.run)["items"][-1]["summary"]
    assert "PASS" not in item["summary"]  # A completed/blocked computation is never a scientific verdict.


def test_activity_page_watermark_cannot_lag_an_event_committed_during_the_read():
    store = ActivityStore()
    store.event("tool.started", operation="CHARACTERIZE_TARGET")
    store.on_query = lambda: store.event("tool.completed", operation="CHARACTERIZE_TARGET", status="SUCCEEDED")
    loaded = page(store, store.workspace, store.run)
    assert loaded["last_event_seq"] == 1 and [item["seq"] for item in loaded["items"]] == [1]
    refreshed = page(store, store.workspace, store.run)
    assert refreshed["last_event_seq"] == 2 and [item["seq"] for item in refreshed["items"]] == [1, 2]


@pytest.mark.parametrize(
    "event_type,code,expected_status,explanation",
    [
        ("run.failed", "MODEL_OUTPUT_INVALID", "FAILED", "model response failed required format or evidence checks"),
        ("run.blocked", "PROVIDER_RATE_LIMITED", "BLOCKED", "provider's request or token rate limit"),
        ("run.failed", "NO_COVERAGE", "FAILED", "approved sources do not cover"),
        ("run.failed", "RESOURCE_LIMIT", "FAILED", "available size or resource budget"),
    ],
)
def test_terminal_failure_explains_only_the_actual_persisted_event_code(event_type, code, expected_status, explanation):
    store = ActivityStore()
    event = store.event(event_type, code=code, summary="PRIVATE_PROVIDER_TEXT", failed_generation="PRIVATE_REASONING")
    event["state"] = expected_status
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["failure_code"] == code and item["status"] == item["state"] == expected_status
    assert explanation in item["summary"]
    assert item["id"] == f"{store.run}:1" and item["created_at"] == event["created_at"]
    assert "PRIVATE_" not in str(item)


@pytest.mark.parametrize(
    "code",
    [None, True, 42, {}, ["MODEL_OUTPUT_INVALID"], "PRIVATE_ERROR_TOKEN", "model_output_invalid",
     "MODEL_OUTPUT_INVALID token=PRIVATE_SECRET", "RESOURCE_LIMIT\nPRIVATE_SECRET", "https://private.test/key"],
)
def test_unknown_or_untrusted_failure_identifiers_are_never_exposed(code):
    store = ActivityStore()
    store.event("run.failed", code=code, summary="PRIVATE_SUMMARY")
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["failure_code"] is None
    assert item["summary"] == "Execution failed; completed evidence retained"
    assert "PRIVATE" not in str(item) and "private.test" not in str(item)


@pytest.mark.parametrize(
    "event_type,event_state,payload_status",
    [("tool.started", "FAILED", "FAILED"), ("agent.started", "BLOCKED", "BLOCKED"),
     ("tool.completed", "QUALIFYING", "SUCCEEDED"), ("agent.completed", "COMPLETED", "SUCCEEDED"),
     ("run.state_changed", "COMPLETED", "FAILED"), ("run.cancelled", "CANCELLED", "FAILED"),
     ("unknown.event", "FAILED", "FAILED")],
)
def test_error_identifier_cannot_relabel_a_started_successful_cancelled_or_unknown_transition(
    event_type, event_state, payload_status,
):
    store = ActivityStore()
    event = store.event(event_type, code="MODEL_OUTPUT_INVALID", status=payload_status)
    event["state"] = event_state
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["failure_code"] is None and "model response failed" not in item["summary"]
    if event_type.endswith(".started"):
        assert item["status"] == "RUNNING" and item["summary"].startswith("Started:")
    if event_type == "run.state_changed":
        assert item["status"] == "COMPLETED"


def test_failure_projection_keeps_task_scope_and_does_not_infer_missing_codes_from_other_records():
    store = ActivityStore()
    candidate = store.record("candidates", name="Polar basalt ridge")
    invocation = store.record("invocations", task_kind="COMPARE_REQUIREMENT", role="scientific_worker",
                              candidate_id=candidate["id"], requirement_id="ICE-SUPPORT")
    receipt = store.record("tool_receipts", invocation_id=invocation["id"], status="FAILED",
                           error_code="PROVIDER_AUTH_FAILED")
    store.event("tool.completed", receipt_id=receipt["id"], code="NO_COVERAGE")
    first = page(store, store.workspace, store.run)["items"][0]
    assert first["failure_code"] == "NO_COVERAGE" and first["status"] == "FAILED"
    assert "Polar basalt ridge" in first["summary"] and "ICE-SUPPORT" in first["summary"]
    assert first["candidate_id"] == candidate["id"] and first["invocation_id"] == invocation["id"]
    assert first["tool_receipt_id"] == receipt["id"]
    store.rows["runs"][store.run]["blocked_dependencies"] = ["RESOURCE_LIMIT"]
    store.event("run.blocked", error_code="SOURCE_UNAVAILABLE", error={"code": "MODEL_OUTPUT_INVALID"})
    second = page(store, store.workspace, store.run)["items"][-1]
    assert second["failure_code"] is None and second["status"] == "BLOCKED"
    assert "model response" not in second["summary"] and "resource budget" not in second["summary"]
    store.event("tool.completed", receipt_id=receipt["id"])
    assert page(store, store.workspace, store.run)["items"][-1]["failure_code"] is None
    assert page(store, store.workspace, store.run)["items"][0] == first  # Later events cannot rewrite this cause.


def test_failed_background_job_does_not_relabel_a_completed_run():
    store = ActivityStore()
    store.rows["runs"][store.run]["state"] = "COMPLETED"
    event = store.event("job.failed", code="RESOURCE_LIMIT")
    event["state"] = "COMPLETED"
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["failure_code"] == "RESOURCE_LIMIT" and item["status"] == "FAILED" and item["state"] == "COMPLETED"
    assert "background job failed" in item["summary"] and "outcome is unchanged" in item["summary"]
    assert "Investigation stopped" not in item["summary"]


def test_raw_reasoning_secrets_unknown_payloads_and_cross_run_refs_are_not_exposed():
    store = ActivityStore()
    other_run = str(uuid4())
    candidate = store.record("candidates", run_id=other_run, name="Private site")
    evidence = store.record("evidence", run_id=other_run)
    invocation = store.record("invocations", run_id=other_run, role="earth_scout", task_kind="screen_candidates")
    receipt = store.record("tool_receipts", run_id=other_run, invocation_id=invocation["id"], status="SUCCEEDED")
    store.event(
        "tool.completed",
        operation="ANALYZE_CANDIDATE",
        candidate_id=candidate["id"],
        receipt_id=receipt["id"],
        invocation_id=invocation["id"],
        evidence_ids=[evidence["id"]],
        summary="chain_of_thought sk-secret",
        api_key="private",
        reasoning="hidden",
    )
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["candidate_id"] is item["invocation_id"] is item["tool_receipt_id"] is None
    assert item["evidence_ids"] == []
    assert not any(word in str(item) for word in ("secret", "reasoning", "private", "Private site"))
    own_candidate = store.record("candidates", name="Ridge sk-secret token=hidden https://site.test/?signed=private")
    store.event("tool.started", operation="ANALYZE_CANDIDATE", candidate_id=own_candidate["id"])
    item = page(store, store.workspace, store.run)["items"][-1]
    assert "sk-secret" not in str(item) and "hidden" not in str(item) and "signed" not in str(item)
    store.event("unknown.event", operation={"reasoning": "secret"}, role=["secret"])
    assert page(store, store.workspace, store.run)["items"][-1]["summary"] == "Investigation update committed"


@pytest.mark.parametrize("mismatch", ["run_id", "invocation_id", "role", "mode", "workspace_id"])
def test_role_result_reference_cannot_cross_task_run_mode_or_workspace(mismatch):
    store = ActivityStore()
    invocation = store.record("invocations", role="requirements", task_kind="validate_accepted_contract")
    evidence = store.record("evidence")
    fields = {"invocation_id": invocation["id"], "role": "requirements", "mode": "live",
              "evidence_ids": [evidence["id"]]}
    fields[mismatch] = "earth_scout" if mismatch == "role" else "synthetic" if mismatch == "mode" else str(uuid4())
    result = store.record("role_results", **fields)
    store.event("agent.completed", role="requirements", invocation_id=invocation["id"],
                role_result_id=result["id"], evidence_count=9999)
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["role_result_id"] is None and item["evidence_count"] == 0
    assert item["evidence_ids"] == [] and item["evidence_ids_truncated"] is False


def test_role_result_evidence_count_uses_only_unique_authorized_records_and_ignores_claimed_count():
    store = ActivityStore()
    invocation = store.record("invocations", role="requirements", task_kind="validate_accepted_contract")
    evidence = store.record("evidence")
    foreign = store.record("evidence", run_id=str(uuid4()))
    result = store.record("role_results", invocation_id=invocation["id"], role="requirements", mode="live",
                          evidence_ids=[evidence["id"], evidence["id"], foreign["id"], str(uuid4())])
    store.event("agent.completed", role="requirements", invocation_id=invocation["id"],
                role_result_id=result["id"], evidence_count=9999)
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["role_result_id"] == result["id"] and item["evidence_ids"] == [evidence["id"]]
    assert item["evidence_count"] == 1 and item["evidence_ids_truncated"] is False


@pytest.mark.parametrize("cursor", ["not base64!", "[", "=" * 600, "e30="])
def test_invalid_cursors_are_rejected(cursor):
    with pytest.raises(ApiError):
        decode_cursor(cursor, str(uuid4()), str(uuid4()))


def test_cursor_cannot_cross_workspace_or_run_and_unknown_run_is_inaccessible():
    store = ActivityStore()
    cursor = encode_cursor(store.workspace, store.run, 0)
    for workspace, run_id in [(str(uuid4()), store.run), (store.workspace, str(uuid4()))]:
        with pytest.raises(ApiError):
            page(store, workspace, run_id, cursor=cursor)
    with pytest.raises(NotFound):
        page(store, str(uuid4()), store.run)
    with pytest.raises(ApiError):
        page(store, store.workspace, store.run, cursor=encode_cursor(store.workspace, store.run, 1))


def test_optional_endpoint_authorizes_viewers_bounds_pages_and_never_caches(tmp_path):
    from analogforge.main import create_app
    from analogforge.settings import Settings

    store = ActivityStore()
    store.event("agent.started", role="requirements", task_kind="validate_accepted_contract")
    terminal = store.event("run.failed", code="MODEL_OUTPUT_INVALID", summary="PRIVATE_PROVIDER_BODY")
    terminal["state"] = "FAILED"
    principal = Principal(store.workspace, str(uuid4()), "VIEWER")
    app = create_app(
        settings=Settings(_env_file=None, data_root=tmp_path), store=store, identity_provider=lambda _request: principal
    )
    with TestClient(app) as client:
        url = f"/api/v1/runs/{store.run}/activity"
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["items"][0]["role"] == "requirements"
        assert response.json()["items"][0]["failure_code"] is None
        assert response.json()["items"][1]["failure_code"] == "MODEL_OUTPUT_INVALID"
        assert response.json()["items"][1]["status"] == "FAILED"
        assert "PRIVATE_PROVIDER_BODY" not in response.text
        assert client.get(url, params={"limit": 101}).status_code == 422
        assert client.get(url, params={"limit": 0}).status_code == 422
        assert client.get(url, params={"cursor": "malformed"}).status_code == 422
        app.state.identity_provider = lambda _request: Principal(str(uuid4()), str(uuid4()), "VIEWER")
        assert client.get(url).status_code == 404


def paused_review(store):
    invocation = store.record("invocations", role="qualification", task_kind="qualify_candidate")
    result = store.record("role_results", role="qualification", mode="live", status="BLOCKED",
                          invocation_id=invocation["id"], payload={"summary": "PRIVATE_REASONING", "issues": [
                              {"severity": "BLOCKING", "requirement_id": "ICE-SUPPORT",
                               "message": "The source date needs review. token=private-secret https://private.invalid"}]})
    store.event("agent.completed", invocation_id=invocation["id"], role_result_id=result["id"],
                role="qualification", status="BLOCKED")
    return result


def test_paused_review_exposes_only_sanitized_bounded_concerns_from_the_admitted_record():
    store = ActivityStore()
    result = paused_review(store)
    original = deepcopy(result)
    item = page(store, store.workspace, store.run)["items"][0]
    assert item["review_concerns"] == [{"message": "The source date needs review. [REDACTED] [link omitted]",
        "message_truncated": False, "severity": "BLOCKING", "requirement_label": "ICE-SUPPORT"}]
    assert "PRIVATE_REASONING" not in str(item) and "private-secret" not in str(item)
    assert result == original
    result["payload"]["issues"] = [{"severity": "WARNING", "requirement_id": "FOREIGN",
                                     "message": "x" * 900} for _ in range(12)]
    concerns = page(store, store.workspace, store.run)["items"][0]["review_concerns"]
    assert len(concerns) == 8 and all(len(c["message"]) == 800 and c["message_truncated"] for c in concerns)
    assert all(c["requirement_label"] is None for c in concerns)


@pytest.mark.parametrize("field,value", [
    ("run_id", str(uuid4())), ("workspace_id", str(uuid4())), ("invocation_id", str(uuid4())),
    ("role", "scientific_critic"), ("mode", "synthetic"), ("status", "SUCCEEDED"),
])
def test_review_concerns_do_not_cross_record_identity_or_terminal_boundaries(field, value):
    store = ActivityStore()
    result = paused_review(store)
    result[field] = value
    assert page(store, store.workspace, store.run)["items"][0]["review_concerns"] == []


def test_started_record_cannot_present_a_review_concern_and_malformed_issue_is_omitted():
    store = ActivityStore()
    result = paused_review(store)
    store.events[0]["event_type"] = "agent.started"
    assert page(store, store.workspace, store.run)["items"][0]["review_concerns"] == []
    store.events[0]["event_type"] = "agent.completed"
    result["payload"]["issues"] = [{"severity": {}}, {"severity": "BLOCKING", "message": []}]
    assert page(store, store.workspace, store.run)["items"][0]["review_concerns"] == []
