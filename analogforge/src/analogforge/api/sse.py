"""Committed event streaming; heartbeat comments have no event identity."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic
from typing import Any

from fastapi import Request

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


async def stream(request: Request, store: Any, workspace_id: str, run_id: str, after: int) -> AsyncIterator[str]:
    cursor = after
    heartbeat_at = monotonic()
    while not await request.is_disconnected():
        events = store.events(workspace_id, run_id, after=cursor)
        for event in events:
            if event["seq"] <= cursor:
                continue
            yield f"id:{event['seq']}\nevent:{event['event_type']}\ndata:{json.dumps(event, separators=(',', ':'))}\n\n"
            cursor = event["seq"]
            heartbeat_at = monotonic()
        with store.transaction(workspace_id) as uow:
            snapshot = uow.require("runs", run_id)
        if snapshot["state"] in TERMINAL and cursor >= snapshot["last_event_seq"]:
            return
        if monotonic() - heartbeat_at >= 15:
            yield ": heartbeat\n\n"
            heartbeat_at = monotonic()
        await asyncio.sleep(1)
