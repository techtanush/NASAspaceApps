#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'uv is required'; exit 1; }
uv sync --extra dev --extra extra-tanush
if ! uv run analogforge db up; then
  echo 'Compose unavailable; trying private native PostgreSQL bootstrap.'
  uv run python scripts/bootstrap_native.py
fi
