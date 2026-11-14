#!/usr/bin/env python3
"""Initialize a private UTF8 PostgreSQL/PostGIS cluster when Docker is unavailable."""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from analogforge.settings import Settings


def _tool(settings: Settings, name: str) -> str:
    if (Path(__file__).resolve().parents[1] / ".runtime" / "pg" / "PG_VERSION").is_file():
        return settings.postgres_tool(name)
    for major in (17, 16):
        candidate = Path(f"/opt/homebrew/opt/postgresql@{major}/bin/{name}")
        if candidate.is_file():
            return str(candidate)
    return name


def main() -> int:
    settings = Settings()
    parsed = urlsplit(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Native bootstrap requires a loopback DATABASE_URL")
    port = parsed.port or settings.db_port
    if port != settings.db_port:
        raise RuntimeError("DB_PORT and DATABASE_URL port must agree")
    root = Path(__file__).resolve().parents[1] / ".runtime"
    cluster = root / "pg"
    root.mkdir(parents=True, exist_ok=True)
    environment = settings.pg_subprocess_environment()
    username = unquote(parsed.username or settings.postgres_user)
    database = parsed.path.lstrip("/")
    if not database:
        raise RuntimeError("DATABASE_URL needs a database name")
    if not (cluster / "PG_VERSION").exists():
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} is already in use; choose an unused DB_PORT")
        password = unquote(parsed.password or "")
        if not password:
            raise RuntimeError("Native bootstrap needs a DATABASE_URL password")
        with tempfile.NamedTemporaryFile("w", dir=root, delete=False) as handle:
            handle.write(password)
            password_path = Path(handle.name)
        password_path.chmod(0o600)
        try:
            init = subprocess.run(  # noqa: S603 - fixed native initdb argv
                [
                    _tool(settings, "initdb"),
                    "-D",
                    str(cluster),
                    "-U",
                    username,
                    "--encoding=UTF8",
                    "--locale=C",
                    "--auth-host=scram-sha-256",
                    "--auth-local=trust",
                    "--pwfile",
                    str(password_path),
                ],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )  # noqa: S603 - fixed initdb argv
        finally:
            password_path.unlink(missing_ok=True)
        if init.returncode:
            print(init.stderr.strip(), file=sys.stderr)
            return 1
    ctl = [settings.postgres_tool("pg_ctl"), "-D", str(cluster)]
    status = subprocess.run([*ctl, "status"], env=environment, capture_output=True, check=False)  # noqa: S603
    if status.returncode:
        started = subprocess.run(  # noqa: S603 - fixed private pg_ctl argv
            [*ctl, "-l", str(root / "postgres.log"), "-o", f"-h 127.0.0.1 -p {port}", "start"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )  # noqa: S603 - fixed pg_ctl argv
        if started.returncode:
            print(started.stderr.strip(), file=sys.stderr)
            return 1
    flags = ["--host", "127.0.0.1", "--port", str(port), "--username", username]
    created = subprocess.run(  # noqa: S603 - fixed createdb argv
        [settings.postgres_tool("createdb"), *flags, "--encoding=UTF8", "--template=template0", database],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )  # noqa: S603 - fixed createdb argv
    if created.returncode and "already exists" not in created.stderr:
        print(created.stderr.strip(), file=sys.stderr)
        return 1
    extension = subprocess.run(  # noqa: S603 - fixed psql argv
        [
            settings.postgres_tool("psql"),
            *flags,
            "--dbname",
            database,
            "--command",
            "CREATE EXTENSION IF NOT EXISTS postgis",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )  # noqa: S603 - fixed psql argv
    if extension.returncode:
        print(extension.stderr.strip(), file=sys.stderr)
        return 1
    print(f"Native PostgreSQL/PostGIS ready on port {port} with UTF8 database {database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
