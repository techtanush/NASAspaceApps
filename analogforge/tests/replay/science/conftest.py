"""Shared fixtures for the SCN-18 adapter replay tests (mocked transport only; no real server is contacted)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from adapter_synth import World

from analogforge.adapters.source_http import HttpPolicy

_FIX = str(Path(__file__).resolve().parents[2] / "fixtures" / "science")
if _FIX not in sys.path:
    sys.path.insert(0, _FIX)


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def policy_for(world: World):  # type: ignore[no-untyped-def]
    def make(hosts: set[str], auth_hosts: set[str] | None = None, **kw: object) -> HttpPolicy:
        return HttpPolicy(
            allowed_hosts=frozenset(hosts), auth_hosts=frozenset(auth_hosts or ()), sleep=world.sleep, **kw
        )  # type: ignore[arg-type]

    return make
