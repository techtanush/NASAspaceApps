"""Typed process configuration. This is the sole production environment reader."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from analogforge.ports.hashing import canonical_sha256

APP_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=APP_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    database_url: str = Field(
        default="postgresql+psycopg://analogforge:change-me-local-only@127.0.0.1:5432/analogforge", repr=False
    )
    test_database_url: str | None = Field(default=None, repr=False)
    postgres_user: str = "analogforge"
    postgres_password: SecretStr | None = None
    postgres_db: str = "analogforge"
    data_root: Path = APP_ROOT / "data"
    config_dir: Path = APP_ROOT / "config"
    analogforge_mode: Literal["synthetic", "replay", "live"] = "synthetic"
    auth_mode: Literal["local", "oidc"] = "local"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_port: int = Field(default=5173, ge=1, le=65535)
    db_port: int = Field(default=5432, ge=1, le=65535)
    public_base_url: str = "http://localhost:8000"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    session_secret: SecretStr | None = None
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    earthdata_token: SecretStr | None = None
    map_tile_url: str | None = Field(default=None, repr=False)
    log_level: str = "INFO"
    worker_cpu_concurrency: int = Field(default=2, ge=1, le=8)
    job_lease_seconds: int = Field(default=120, ge=4)
    job_heartbeat_seconds: int = Field(default=20, ge=1)
    max_download_bytes: int = Field(default=2147483648, ge=1)
    max_aoi_area_km2: float = Field(default=2500, gt=0)
    max_raster_cells: int = Field(default=4000000, ge=1)
    max_run_model_calls: int = Field(default=40, ge=1)
    max_replans: int = Field(default=3, ge=0)
    max_run_seconds: int = Field(default=900, ge=1)
    vite_api_base_url: str = "/api/v1"
    compose_project_name: str = "af-integration"
    profile: str = "integration"
    scenario_default: str = "synthetic-mars-mobility-v1"
    test_hooks: bool = Field(default=False, validation_alias="ANALOGFORGE_TEST_HOOKS")
    operator_limits_json: str | None = Field(default=None, validation_alias="ANALOGFORGE_OPERATOR_LIMITS_JSON")
    fake_openai_url: str | None = Field(default=None, repr=False, validation_alias="ANALOGFORGE_FAKE_OPENAI_URL")
    allow_test_harness_provider: bool = Field(default=False, validation_alias="ANALOGFORGE_ALLOW_TEST_HARNESS_PROVIDER")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _origins_input(cls, value: object) -> object:
        if isinstance(value, str):
            return json.loads(value)
        return value

    @field_validator(
        "openai_api_key", "earthdata_token", "session_secret", "oidc_client_secret", "postgres_password", mode="before"
    )
    @classmethod
    def _empty_secret(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "openai_model", "oidc_issuer_url", "oidc_client_id", "map_tile_url", "test_database_url", mode="before"
    )
    @classmethod
    def _empty_string(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _validate_process(self) -> Settings:
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.auth_mode == "local" and self.api_host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("AUTH_MODE=local requires a loopback API_HOST")
        if self.job_heartbeat_seconds * 3 >= self.job_lease_seconds:
            raise ValueError("JOB_HEARTBEAT_SECONDS must be less than one third of JOB_LEASE_SECONDS")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("ALLOWED_ORIGINS must contain exact HTTP(S) origins")
            if "*" in origin or parsed.username or parsed.password:
                raise ValueError("ALLOWED_ORIGINS cannot contain wildcards or credentials")
        if self.auth_mode == "oidc":
            if not all((self.session_secret, self.oidc_issuer_url, self.oidc_client_id, self.oidc_client_secret)):
                raise ValueError("OIDC requires SESSION_SECRET and complete OIDC settings")
            assert self.session_secret is not None
            if len(self.session_secret.get_secret_value()) < 32 or not self.public_base_url.startswith("https://"):
                raise ValueError("OIDC requires a 32-character session secret and HTTPS PUBLIC_BASE_URL")
            for label, url in (("PUBLIC_BASE_URL", self.public_base_url), ("OIDC_ISSUER_URL", self.oidc_issuer_url)):
                assert url is not None
                parsed = urlsplit(url)
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(f"{label} must be an HTTPS URL without credentials, query, or fragment")
        hook_used = bool(self.operator_limits_json or self.fake_openai_url or self.allow_test_harness_provider)
        if hook_used and (not self.test_hooks or self.auth_mode != "local"):
            raise ValueError("test hooks require ANALOGFORGE_TEST_HOOKS=1 and local auth")
        if self.analogforge_mode == "live" and hook_used and not self.allow_test_harness_provider:
            raise ValueError("live test hooks require ANALOGFORGE_ALLOW_TEST_HARNESS_PROVIDER=1")
        if self.operator_limits_json is not None:
            limits = json.loads(self.operator_limits_json)
            if not isinstance(limits, dict) or any(not isinstance(v, (int, float)) or v <= 0 for v in limits.values()):
                raise ValueError("ANALOGFORGE_OPERATOR_LIMITS_JSON must be a map of positive numbers")
        return self

    def public_config(self) -> dict[str, object]:
        """Effective settings eligible for hashes and diagnostics; never contains credentials."""
        excluded = {
            "database_url",
            "test_database_url",
            "postgres_password",
            "session_secret",
            "oidc_client_secret",
            "openai_api_key",
            "earthdata_token",
            "operator_limits_json",
            "fake_openai_url",
            "map_tile_url",
        }
        return self.model_dump(mode="json", exclude=excluded)

    def pg_subprocess_environment(self) -> dict[str, str]:
        """Pass the selected DB password to PostgreSQL tools without placing it in argv."""
        from urllib.parse import unquote

        parsed = urlsplit(self.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
        return {**os.environ, "PGPASSWORD": unquote(parsed.password or "")}

    def postgres_tool(self, name: str) -> str:
        """Choose a client matching the private native server when Homebrew exposes several versions."""
        if name not in {"pg_dump", "pg_restore", "psql", "createdb", "dropdb", "pg_ctl"}:
            raise ValueError("Unsupported PostgreSQL tool")
        version_file = APP_ROOT / ".runtime" / "pg" / "PG_VERSION"
        pid_file = version_file.with_name("postmaster.pid")
        active_port = None
        if pid_file.is_file():
            lines = pid_file.read_text(encoding="ascii").splitlines()
            active_port = int(lines[3]) if len(lines) > 3 and lines[3].isdecimal() else None
        if version_file.is_file() and (
            active_port == self.db_port or (active_port is None and self.profile == "tanush")
        ):
            major = version_file.read_text(encoding="ascii").strip()
            if major.isdecimal():
                candidate = Path(f"/opt/homebrew/opt/postgresql@{major}/bin/{name}")
                if candidate.is_file():
                    return str(candidate)
        return name

    def effective_config_sha256(self) -> str:
        import yaml

        def _read(name: str) -> object:
            path = self.config_dir / name
            return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None

        return canonical_sha256(
            {
                "settings": self.public_config(),
                "scenarios": _read("scenarios.yaml"),
                "algorithms": _read("algorithms.yaml"),
            }
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
