#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/bootstrap.sh
uv run analogforge migrate
uv run analogforge seed-synthetic
uv run analogforge preflight --mode synthetic --scenario synthetic-mars-mobility-v1
exec uv run --locked python scripts/dev_services.py
