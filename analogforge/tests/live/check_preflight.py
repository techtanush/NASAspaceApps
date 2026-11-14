"""Explicit-file live readiness check; the filename keeps it out of default pytest discovery."""

from __future__ import annotations

import pytest

from analogforge.application.preflight import run_preflight
from analogforge.db.store import Store
from analogforge.settings import Settings

pytestmark = pytest.mark.live


def test_configured_live_preflight():
    settings = Settings()
    if not settings.openai_api_key or not settings.openai_model:
        pytest.fail("BLOCKED_EXTERNAL: OPENAI_API_KEY and OPENAI_MODEL are required.", pytrace=False)
    if settings.fake_openai_url or settings.allow_test_harness_provider:
        pytest.fail("Real live preflight requires the real model provider and source datasets.", pytrace=False)
    try:
        store = Store(settings.database_url)
        try:
            report = run_preflight(settings, mode="live", scenario_id="live-hackathon-v1", store=store)
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001 - operator errors must not disclose connection or provider secrets
        pytest.fail(f"Live preflight could not complete ({type(exc).__name__}).", pytrace=False)
    failures = [f"{gate['stage']}:{gate['code']}" for gate in report["gates"] if gate["severity"] == "FAIL"]
    if report["status"] != "PASS" or failures:
        pytest.fail("Live preflight failed: " + (", ".join(failures) or "readiness not confirmed"), pytrace=False)
    assert report["mode"] == "live"
    assert report["scenario_id"] == "live-hackathon-v1"
