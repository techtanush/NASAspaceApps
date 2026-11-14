#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! uv run python -c 'from analogforge.settings import Settings; s=Settings(); raise SystemExit(0 if s.openai_api_key and s.openai_model else 1)'; then
  echo 'BLOCKED_EXTERNAL: SKIP live preflight; OPENAI_API_KEY and OPENAI_MODEL are required.'
  exit 0
fi
exec uv run pytest tests/live/check_preflight.py -m live -q
