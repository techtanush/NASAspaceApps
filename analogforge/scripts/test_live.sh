#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! uv run python -c 'from analogforge.settings import Settings; s=Settings(); raise SystemExit(0 if s.openai_api_key and s.openai_model else 1)'; then
  echo 'BLOCKED_EXTERNAL: OPENAI_API_KEY and OPENAI_MODEL are required for live tests.'
  exit 0
fi
uv run analogforge preflight --mode live --scenario live-hackathon-v1
uv run pytest -m live -q
