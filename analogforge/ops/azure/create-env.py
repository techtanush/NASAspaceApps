#!/usr/bin/env python3
"""Create the VM's private runtime file; never displays credential values."""
import argparse
import json
import os
import re
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("hostname", help="Actual verified Azure DNS hostname, without https://")
parser.add_argument("--output", type=Path, default=Path("/etc/analogforge/runtime.env"))
args = parser.parse_args()
labels = args.hostname.split(".")
if len(args.hostname) > 253 or len(labels) < 2 or any(
    not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
):
    parser.error("A real DNS hostname is required")
password = secrets.token_hex(32)
admin_password = secrets.token_hex(32)
database_file = args.output.with_name("database.env")
if args.output.exists() or database_file.exists():
    parser.error("Existing private configuration must not be overwritten")
origin = "https://" + args.hostname
lines = {
    "APP_HOST": args.hostname,
    "PUBLIC_BASE_URL": origin,
    "ALLOWED_ORIGINS": json.dumps([origin], separators=(",", ":")),
    "DATABASE_URL": "postgresql+psycopg://analogforge:" + password + "@db:5432/analogforge",
    "SESSION_SECRET": secrets.token_hex(48),
    "AUTH_MODE": "public",
    "ANALOGFORGE_MODE": "synthetic",
    "ANALOGFORGE_VISUALIZATION": "1",
    "ANALOGFORGE_API_DOCS": "0",
    "WORKER_CPU_CONCURRENCY": "2",
    "PUBLIC_MAX_WORKSPACES": "100",
    "PUBLIC_RUNS_PER_WORKSPACE": "4",
    "MAX_RUN_SECONDS": "900",
    "LOG_LEVEL": "INFO",
    "PROFILE": "azure",
    "SCENARIO_DEFAULT": "synthetic-mars-mobility-v1",
    "MODEL_FALLBACK_ORDER": "[]",
}
args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as output:
    for key, value in lines.items():
        output.write(key + "=" + value + "\n")
admin_fd = os.open(database_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(admin_fd, "w", encoding="utf-8") as output:
    output.write("POSTGRES_PASSWORD=" + admin_password + "\n")
    output.write("DATABASE_ADMIN_URL=postgresql+psycopg://af_admin:" + admin_password + "@db:5432/analogforge\n")
print("Created private runtime and database configuration in " + str(args.output.parent)
      + "; credentials were not displayed.")
