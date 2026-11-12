#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/bootstrap.sh
uv run analogforge migrate
uv run analogforge seed-synthetic
uv run analogforge preflight --mode synthetic --scenario synthetic-mars-mobility-v1
children=()
cleanup() { for child in "${children[@]}"; do kill "$child" 2>/dev/null || true; done; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM
uv run analogforge serve & children+=("$!")
uv run analogforge worker & children+=("$!")
if [ -f apps/web/package.json ]; then
  # Vite runs two directories below the server's .env. Pass only its public
  # routing settings; do not source or expose server credentials to the browser.
  read -r API_PORT WEB_PORT < <(uv run python -c 'from analogforge.settings import Settings; s=Settings(); print(s.api_port, s.web_port)')
  export API_PORT WEB_PORT
  (cd apps/web && VITE_API_MOCK=0 corepack pnpm dev --host 127.0.0.1) & children+=("$!")
fi
echo 'AnalogForge development services started. Ctrl-C stops API, worker, and web.'
while :; do
  for child in "${children[@]}"; do
    if ! kill -0 "$child" 2>/dev/null; then
      wait "$child" || true
      echo "Development service exited: $child" >&2
      exit 1
    fi
  done
  sleep 2
done
