#!/usr/bin/env bash
# Disposable GitHub-hosted CI stack only; never run cleanup against a real deployment.
set -euo pipefail
umask 077
[[ ${CI:-} == true && -n ${RUNNER_TEMP:-} && ${GITHUB_RUN_ID:-} =~ ^[0-9]+$ ]] || {
  echo "This smoke runner is restricted to a disposable GitHub CI environment." >&2; exit 1;
}
export RELEASE_ID=${GITHUB_SHA:?An exact built source commit is required}
[[ $RELEASE_ID =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid source commit." >&2; exit 1; }
cd "$(dirname "$0")/../.."
private=$(mktemp -d "$RUNNER_TEMP/af-container-check.XXXXXX")
export AF_ENV_FILE="$private/runtime.env"
export AF_DB_ENV_FILE="$private/database.env"
python3 ops/azure/create-env.py af-ci.invalid --output "$AF_ENV_FILE"
project="af-ci-$GITHUB_RUN_ID-${GITHUB_RUN_ATTEMPT:-1}"
compose=(docker compose -p "$project" --env-file "$AF_ENV_FILE" --env-file "$AF_DB_ENV_FILE" -f ops/azure/compose.yaml)
cleanup() {
  status=$?
  # Service status is safe; raw application/DB logs and interpolated env are not dumped.
  "${compose[@]}" ps || true
  "${compose[@]}" down --volumes --remove-orphans --timeout 20 || true
  rm -rf "$private"
  exit "$status"
}
trap cleanup EXIT
"${compose[@]}" config --quiet
"${compose[@]}" up -d --wait --wait-timeout 180 db
"${compose[@]}" run --rm --no-deps --pull never initialize-volume
"${compose[@]}" run --rm --no-deps --pull never migrate
"${compose[@]}" run --rm --no-deps --pull never provision-runtime-role
"${compose[@]}" run --rm --no-deps --pull never seed
"${compose[@]}" up -d --no-build --wait --wait-timeout 240 api worker
"${compose[@]}" exec -T api python - < ops/azure/ci-probe.py
