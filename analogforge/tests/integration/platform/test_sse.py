"""PLT-07: committed replay, cursor expiry and non-advancing heartbeat frames."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from analogforge.db.store import PersistenceError, Store
from analogforge.jobs.events import event_cursor, frame_event, heartbeat
from analogforge.ports.domain_models import RunEvent
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
def test_durable_events_replay_and_terminal_frame(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        first = unit.append_event(run["id"], "evidence.created", {"evidence_ids": []}, "synthetic")
        current = unit.require("runs", run["id"])
        current["state"] = "COMPLETED"
        unit.replace("runs", run["id"], current, current["revision"])
        terminal = unit.append_event(run["id"], "run.state_changed", {"summary": "Complete"}, "synthetic")
    assert first["seq"] == 1 and terminal["seq"] == 2
    assert platform_store.events(workspace, run["id"], after=1) == [terminal]
    RunEvent.model_validate(terminal)
    encoded = frame_event(terminal)
    assert encoded.startswith("id:2\nevent:run.state_changed\n")
    assert json.loads(encoded.split("data:")[1]) == terminal
    assert terminal["state"] == "COMPLETED"


def test_cursor_header_max_precedence_and_heartbeat_no_cursor() -> None:
    assert event_cursor(4, "8") == 8
    assert event_cursor(9, "8") == 9
    assert event_cursor(2) == 2
    for invalid in ("abc", "-1", "1\nid:999"):
        with pytest.raises(PersistenceError):
            event_cursor(0, invalid)
    assert heartbeat() == ": heartbeat\n\n"
    assert "id:" not in heartbeat() and "data:" not in heartbeat()


@pytest.mark.asyncio
async def test_actual_stream_heartbeat_does_not_skip_next_committed_event(monkeypatch) -> None:
    from analogforge.api import sse

    clock = iter([0.0, 16.0, 16.0, 16.0])
    monkeypatch.setattr(sse, "monotonic", lambda: next(clock))

    async def no_wait(seconds):
        return None

    async def connected():
        return False

    monkeypatch.setattr(sse.asyncio, "sleep", no_wait)
    cursors = []

    class StoreView:
        def events(self, workspace_id, run_id, after):
            cursors.append(after)
            return [] if len(cursors) == 1 else [{"seq": 1, "event_type": "run.state_changed", "state": "COMPLETED"}]

        @contextmanager
        def transaction(self, workspace_id):
            state = "RUNNING" if len(cursors) == 1 else "COMPLETED"
            yield SimpleNamespace(require=lambda kind, run_id: {"state": state, "last_event_seq": len(cursors) - 1})

    frames = [frame async for frame in sse.stream(SimpleNamespace(is_disconnected=connected), StoreView(), "w", "r", 0)]
    assert frames[0] == ": heartbeat\n\n"
    assert len(frames) == 2 and frames[1].startswith("id:1\nevent:run.state_changed\n")
    assert cursors == [0, 0]


@pytest.mark.db
def test_cursor_before_retention_fails_before_streaming(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        unit.create("run_events", {"run_id": run["id"], "seq": 10, "event_type": "run.state_changed"})
    with pytest.raises(PersistenceError) as error:
        platform_store.events(workspace, run["id"], after=2)
    assert error.value.code == "EVENT_CURSOR_EXPIRED"
