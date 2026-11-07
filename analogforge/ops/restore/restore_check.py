"""Restore a backup into a disposable database, verify PostGIS, then remove it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from analogforge.settings import Settings


def main() -> int:
    settings = Settings()
    backups = sorted((settings.data_root / "backups").glob("*.dump"))
    backup = Path(sys.argv[1]) if len(sys.argv) > 1 else (backups[-1] if backups else None)
    if backup is None or not backup.is_file():
        print("No backup to restore-check", file=sys.stderr)
        return 1
    parsed = urlsplit(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    env = settings.pg_subprocess_environment()
    flags = [
        "--host",
        parsed.hostname or "127.0.0.1",
        "--port",
        str(parsed.port or settings.db_port),
        "--username",
        unquote(parsed.username or "analogforge"),
    ]
    database = "af_restore_check_" + uuid4().hex[:12]

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, env=env, text=True, capture_output=True, check=False)  # noqa: S603 - fixed pg argv

    created = run([settings.postgres_tool("createdb"), *flags, database])
    if created.returncode:
        print(created.stderr.strip(), file=sys.stderr)
        return 1
    try:
        restored = run(
            [
                settings.postgres_tool("pg_restore"),
                *flags,
                "--dbname",
                database,
                "--no-owner",
                "--no-privileges",
                str(backup),
            ]
        )
        if restored.returncode:
            print(restored.stderr.strip(), file=sys.stderr)
            return 1
        checked = run(
            [
                settings.postgres_tool("psql"),
                *flags,
                "--dbname",
                database,
                "--tuples-only",
                "--no-align",
                "--command",
                "SELECT extname FROM pg_extension WHERE extname='postgis'",
            ]
        )
        if checked.returncode or checked.stdout.strip() != "postgis":
            print("Restored database lacks PostGIS", file=sys.stderr)
            return 1
        print(f"restore_check: PASS ({backup.name})")
        return 0
    finally:
        dropped = run([settings.postgres_tool("dropdb"), *flags, database])
        if dropped.returncode:
            print("Disposable restore database requires cleanup: " + database, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
