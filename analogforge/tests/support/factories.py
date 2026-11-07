"""The single explicit seam switch used by platform and eventual merge tests."""

from __future__ import annotations

import importlib
import os
from typing import cast

from analogforge.ports.passport_renderer import RENDERER_ENTRY_POINT, PassportRenderer
from analogforge.ports.science import SCIENCE_FACADE_ENTRY_POINT, ScienceOperation, ScienceService


def _load(entry_point: str, failure: str) -> object:
    module, name = entry_point.split(":", 1)
    try:
        return getattr(importlib.import_module(module), name)()
    except (ImportError, AttributeError, TypeError) as exc:
        raise RuntimeError(failure) from exc


def science_factory() -> ScienceService:
    choice = os.environ.get("AF_SCIENCE_IMPL", "fake")
    if choice == "fake":
        from tests.support.fake_science import FakeScienceService

        return FakeScienceService()
    if choice != "real":
        raise ValueError("AF_SCIENCE_IMPL must be fake or real")
    service = _load(SCIENCE_FACADE_ENTRY_POINT, "SCIENCE_FACADE_MISSING")
    if not isinstance(service, ScienceService) or service.supported_operations() != frozenset(ScienceOperation):
        raise RuntimeError("SCIENCE_FACADE_NONCONFORMING")
    return cast(ScienceService, service)


def renderer_factory() -> PassportRenderer:
    choice = os.environ.get("AF_RENDERER_IMPL", "fake")
    if choice == "fake":
        from tests.support.fake_renderer import FakePassportRenderer

        return FakePassportRenderer()
    if choice != "real":
        raise ValueError("AF_RENDERER_IMPL must be fake or real")
    renderer = _load(RENDERER_ENTRY_POINT, "RENDERER_MISSING")
    if not isinstance(renderer, PassportRenderer):
        raise RuntimeError("RENDERER_NONCONFORMING")
    return cast(PassportRenderer, renderer)


# Explicit aliases help downstream suites use the same factory without a new fixture.
create_science_service = science_factory
create_passport_renderer = renderer_factory
