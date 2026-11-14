"""The opt-in live gate runs real readiness once and cannot turn blockers into passing tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.live import check_preflight as live_gate


@pytest.fixture
def configured_gate(monkeypatch):
    settings = SimpleNamespace(
        openai_api_key="test-only-key", openai_model="test-only-model", database_url="configured-store",
        fake_openai_url=None, allow_test_harness_provider=False,
    )
    store = SimpleNamespace(close=Mock())
    factory = Mock(return_value=store)
    preflight = Mock(return_value={"status": "PASS", "mode": "live", "scenario_id": "live-hackathon-v1", "gates": []})
    monkeypatch.setattr(live_gate, "Settings", lambda: settings)
    monkeypatch.setattr(live_gate, "Store", factory)
    monkeypatch.setattr(live_gate, "run_preflight", preflight)
    return settings, store, factory, preflight


def test_live_gate_executes_one_live_probe_and_closes_its_store(configured_gate):
    settings, store, factory, preflight = configured_gate
    live_gate.test_configured_live_preflight()
    factory.assert_called_once_with(settings.database_url)
    preflight.assert_called_once_with(settings, mode="live", scenario_id="live-hackathon-v1", store=store)
    store.close.assert_called_once_with()


@pytest.mark.parametrize("report_status", ["FAIL", "PASS"])
def test_live_gate_cannot_pass_with_unbound_datasets(configured_gate, report_status):
    _, store, _, preflight = configured_gate
    preflight.return_value = {
        "status": report_status, "mode": "live", "scenario_id": "live-hackathon-v1",
        "gates": [{"stage": "DATASETS", "code": "DATASETS_UNBOUND", "severity": "FAIL"}],
    }
    with pytest.raises(pytest.fail.Exception, match="DATASETS:DATASETS_UNBOUND"):
        live_gate.test_configured_live_preflight()
    store.close.assert_called_once_with()


@pytest.mark.parametrize("field", ["openai_api_key", "openai_model"])
def test_direct_live_gate_reports_missing_credentials_without_a_skip_pass(configured_gate, field):
    settings, _, factory, preflight = configured_gate
    setattr(settings, field, None)
    with pytest.raises(pytest.fail.Exception, match="BLOCKED_EXTERNAL"):
        live_gate.test_configured_live_preflight()
    factory.assert_not_called()
    preflight.assert_not_called()


@pytest.mark.parametrize("field,value", [("fake_openai_url", "http://localhost/v1"),
                                          ("allow_test_harness_provider", True)])
def test_live_gate_rejects_fake_provider_and_test_harness_sources(configured_gate, field, value):
    settings, _, factory, preflight = configured_gate
    setattr(settings, field, value)
    with pytest.raises(pytest.fail.Exception, match="requires the real model provider"):
        live_gate.test_configured_live_preflight()
    factory.assert_not_called()
    preflight.assert_not_called()


def test_live_gate_sanitizes_probe_errors_and_still_closes_store(configured_gate):
    _, store, _, preflight = configured_gate
    preflight.side_effect = RuntimeError("private database connection or provider content")
    with pytest.raises(pytest.fail.Exception) as caught:
        live_gate.test_configured_live_preflight()
    assert "RuntimeError" in str(caught.value)
    assert "private" not in str(caught.value)
    store.close.assert_called_once_with()


@pytest.mark.parametrize("credential_status,test_status", [(1, 0), (0, 0), (0, 1)])
def test_live_script_dispatches_one_explicit_test_or_reports_external_blocker(tmp_path, credential_status, test_status):
    script = Path(__file__).resolve().parents[3] / "scripts/test_live.sh"
    log = tmp_path / "dispatch.log"
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> "$LIVE_GATE_DISPATCH_LOG"\n'
        'if [ "$2" = python ]; then exit "$LIVE_GATE_CREDENTIAL_STATUS"; fi\n'
        'exit "$LIVE_GATE_TEST_STATUS"\n'
    )
    uv.chmod(0o755)
    result = subprocess.run(  # noqa: S603 - fixed script with a local stub; no provider or settings are executed
        ["/bin/bash", str(script)], capture_output=True, text=True, timeout=10,
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "LIVE_GATE_DISPATCH_LOG": str(log),
             "LIVE_GATE_CREDENTIAL_STATUS": str(credential_status), "LIVE_GATE_TEST_STATUS": str(test_status)},
    )
    calls = log.read_text().splitlines()
    if credential_status:
        assert result.returncode == 0
        assert "BLOCKED_EXTERNAL: SKIP" in result.stdout
        assert len(calls) == 1
    else:
        assert result.returncode == test_status
        assert len(calls) == 2
        assert calls[-1] == "run pytest tests/live/check_preflight.py -m live -q"
        assert "BLOCKED_EXTERNAL" not in result.stdout
