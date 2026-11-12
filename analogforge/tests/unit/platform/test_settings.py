from __future__ import annotations

import pytest
from pydantic import ValidationError

from analogforge.settings import Settings

# The all-interface literal below is a negative validation case.
# ruff: noqa: S104


def test_defaults_are_local_and_typed(tmp_path):
    settings = Settings(_env_file=None, data_root=tmp_path)
    assert settings.api_host == "127.0.0.1"
    assert settings.job_lease_seconds == 120
    assert settings.job_heartbeat_seconds == 20
    assert settings.data_root == tmp_path
    assert settings.analogforge_mode == "synthetic"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"api_host": "0.0.0.0"}, "loopback"),
        ({"allowed_origins": ["*"]}, "origins"),
        ({"allowed_origins": ["http://localhost:5173/path"]}, "origins"),
        ({"job_heartbeat_seconds": 40}, "one third"),
        ({"auth_mode": "oidc"}, "OIDC"),
        ({"operator_limits_json": '{"search_max_expansions":1}'}, "test hooks"),
        ({"test_hooks": True, "auth_mode": "oidc", "operator_limits_json": '{"search_max_expansions":1}'}, "OIDC"),
    ],
)
def test_rejects_unsafe_process_configuration(override, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **override)


def test_live_hooks_need_explicit_harness_flag():
    with pytest.raises(ValidationError, match="live test hooks"):
        Settings(
            _env_file=None,
            analogforge_mode="live",
            test_hooks=True,
            fake_openai_url="http://127.0.0.1:9999",
        )


@pytest.mark.parametrize(
    ("field", "url"),
    [
        ("public_base_url", "https://user:secret@example.test/app"),
        ("public_base_url", "https://example.test/app?token=secret"),
        ("public_base_url", "https://example.test/app#secret"),
        ("oidc_issuer_url", "https://user:secret@example.test/issuer"),
        ("oidc_issuer_url", "https://example.test/issuer?token=secret"),
        ("oidc_issuer_url", "https://example.test/issuer#secret"),
    ],
)
def test_oidc_urls_reject_embedded_credentials_and_fragments(field, url):
    options = {
        "auth_mode": "oidc",
        "session_secret": "a" * 32,
        "public_base_url": "https://example.test/app",
        "oidc_issuer_url": "https://identity.example.test/issuer",
        "oidc_client_id": "client",
        "oidc_client_secret": "client-secret",
    }
    options[field] = url
    with pytest.raises(ValidationError, match=field.upper()):
        Settings(_env_file=None, **options)


def test_effective_hash_changes_with_scenario_config(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "scenarios.yaml").write_text("example: 1\n")
    first = Settings(_env_file=None, config_dir=config).effective_config_sha256()
    (config / "scenarios.yaml").write_text("example: 2\n")
    second = Settings(_env_file=None, config_dir=config).effective_config_sha256()
    assert first != second
