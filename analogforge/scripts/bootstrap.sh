#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'uv is required'; exit 1; }
uv sync --locked --extra dev --extra extra-tanush --extra extra-ayan --extra extra-aradhya
if [ -f apps/web/package.json ]; then
  corepack pnpm install --frozen-lockfile
fi
if ! uv run analogforge db up; then
  echo 'Compose unavailable; trying private native PostgreSQL bootstrap.'
  uv run python scripts/bootstrap_native.py
fi
