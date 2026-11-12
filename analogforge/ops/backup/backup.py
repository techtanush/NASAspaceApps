"""Create a PostgreSQL custom-format backup without exposing the password in argv."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from analogforge.settings import Settings


def main() -> int:
    settings = Settings()
    parsed = urlsplit(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    destination = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else settings.data_root / "backups" / f"analogforge-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    environment = settings.pg_subprocess_environment()
    command = [
        settings.postgres_tool("pg_dump"),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host",
        parsed.hostname or "127.0.0.1",
        "--port",
        str(parsed.port or settings.db_port),
        "--username",
        unquote(parsed.username or "analogforge"),
        "--dbname",
        parsed.path.lstrip("/"),
        "--file",
        str(destination),
    ]
    result = subprocess.run(command, env=environment, check=False)  # noqa: S603 - fixed pg_dump argv
    if result.returncode:
        destination.unlink(missing_ok=True)
        return result.returncode
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
