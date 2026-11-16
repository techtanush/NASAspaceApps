#!/usr/bin/env bash
# Consistent DB + evidence backup. Stops only this stack's writers and restarts on exit.
set -euo pipefail
umask 077
if [[ $EUID -ne 0 ]]; then echo "Run with sudo." >&2; exit 1; fi
cd "$(dirname "$0")/../.."
export AF_ENV_FILE=${AF_ENV_FILE:-/etc/analogforge/runtime.env}
export AF_DB_ENV_FILE=${AF_DB_ENV_FILE:-/etc/analogforge/database.env}
export RELEASE_ID=${RELEASE_ID:?Set RELEASE_ID to the active source commit}
compose=(docker compose --env-file "$AF_ENV_FILE" --env-file "$AF_DB_ENV_FILE" -f ops/azure/compose.yaml)
if [[ -n ${AF_COMPOSE_OVERRIDE:-} ]]; then compose+=(-f "$AF_COMPOSE_OVERRIDE"); fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="/srv/analogforge/backups/$stamp"
install -d -m 0700 "$backup"
"${compose[@]}" stop proxy api worker
restart_services() { "${compose[@]}" start api worker proxy; }
trap restart_services EXIT
"${compose[@]}" exec -T db pg_dump -U af_admin -d analogforge -Fc --no-owner --no-privileges > "$backup/database.dump"
# Reuse the exact runtime image and the data owner; no ownership or permissions change.
"${compose[@]}" run --rm --no-deps --entrypoint tar api -czf - -C /data . > "$backup/evidence.tar.gz"
install -m 0600 "$AF_ENV_FILE" "$backup/runtime.env"
install -m 0600 "$AF_DB_ENV_FILE" "$backup/database.env"
printf '%s\n' "$RELEASE_ID" > "$backup/source-commit.txt"
sha256sum "$backup/database.dump" "$backup/evidence.tar.gz" > "$backup/SHA256SUMS"
printf 'Backup completed at %s (contains private data; protect/encrypt before off-machine storage).\n' "$backup"
