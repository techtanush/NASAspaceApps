from __future__ import annotations

import json
import logging
from pathlib import Path

from analogforge.agents.runtime.sanitize import sanitize
from analogforge.api.errors import ApiError
from analogforge.application.capabilities import get_capabilities
from analogforge.jobs.events import heartbeat
from analogforge.settings import Settings

# Literal marker values are deliberately fake and used only to assert redaction.
# ruff: noqa: S106


def test_public_config_and_effective_hash_exclude_secrets(tmp_path):
    first = Settings(
        _env_file=None,
        data_root=tmp_path,
        database_url="postgresql+psycopg://user:first@127.0.0.1/db",
        openai_api_key="first-key",
        earthdata_token="first-token",
        session_secret="first-session",
    )
    second = Settings(
        _env_file=None,
        data_root=tmp_path,
        database_url="postgresql+psycopg://user:second@127.0.0.1/db",
        openai_api_key="second-key",
        earthdata_token="second-token",
        session_secret="second-session",
    )
    public = str(first.public_config())
    assert all(value not in public for value in ("first-key", "first-token", "first-session", "first@"))
    assert first.effective_config_sha256() == second.effective_config_sha256()


def test_secret_values_absent_from_public_surfaces(tmp_path, caplog):
    credentials = (
        "postgresql+psycopg://user:dsn-secret@127.0.0.1/db",
        "sk-private-openai-token",
        "private-earthdata-token",
        "private-session-token",
        "private-map-token",
    )
    settings = Settings(
        _env_file=None,
        data_root=tmp_path,
        database_url=credentials[0],
        openai_api_key=credentials[1],
        earthdata_token=credentials[2],
        session_secret=credentials[3],
        map_tile_url=f"https://tiles.example.test?key={credentials[4]}",
    )
    with caplog.at_level(logging.DEBUG):
        public = settings.public_config()
        capabilities = get_capabilities(settings)
    root = Path(__file__).resolve().parents[3]
    openapi = (root / "contracts" / "openapi.bundled.json").read_text(encoding="utf-8")
    error = ApiError("REQUEST_INVALID", "Request rejected").envelope("request-id")
    safe_event = sanitize({"database_url": credentials[0], "api_key": credentials[1], "event": "run.started"})
    surfaces = (
        repr(settings),
        json.dumps(public),
        json.dumps(capabilities),
        json.dumps(error),
        json.dumps(safe_event),
        heartbeat(),
        openapi,
        caplog.text,
    )
    assert all(secret not in surface for surface in surfaces for secret in credentials)
