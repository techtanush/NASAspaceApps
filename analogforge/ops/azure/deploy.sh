#!/usr/bin/env bash
# Build and activate the exact commit on this VM. Existing DB/data volumes are retained.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo." >&2; exit 1; fi
if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then echo "Usage: deploy.sh EXACT_40_CHARACTER_COMMIT" >&2; exit 1; fi
commit=$1
export AF_ENV_FILE=${AF_ENV_FILE:-/etc/analogforge/runtime.env}
export AF_DB_ENV_FILE=${AF_DB_ENV_FILE:-/etc/analogforge/database.env}
for private_file in "$AF_ENV_FILE" "$AF_DB_ENV_FILE"; do
  [[ -f $private_file ]] || { echo "A private configuration file is missing." >&2; exit 1; }
  [[ $(stat -c '%a' "$private_file") == 600 ]] || { echo "Private files must have permissions 0600." >&2; exit 1; }
done
repo=/srv/analogforge/repository
git -C "$repo" fetch origin --prune
git -C "$repo" cat-file -e "$commit^{commit}"
release="/var/lib/analogforge/releases/$commit"
if [[ ! -d $release ]]; then git -C "$repo" worktree add --detach "$release" "$commit"; fi
cd "$release/analogforge"
export RELEASE_ID=$commit
compose=(docker compose --env-file "$AF_ENV_FILE" --env-file "$AF_DB_ENV_FILE" -f ops/azure/compose.yaml)
if [[ -n ${AF_COMPOSE_OVERRIDE:-} ]]; then compose+=(-f "$AF_COMPOSE_OVERRIDE"); fi
"${compose[@]}" config --quiet
# Build before stopping an active release; failure leaves the current app available.
"${compose[@]}" build --pull api proxy
"${compose[@]}" run --rm --no-deps --entrypoint python api -c \
  "import h5py, numpy, pyproj, rasterio, reportlab, scipy, shapely; import analogforge.rendering.evidence_brief"
"${compose[@]}" run --rm --no-deps --entrypoint caddy proxy validate --config /etc/caddy/Caddyfile --adapter caddyfile
if [[ -L /srv/analogforge/current ]]; then
  active_commit=$(basename "$(readlink -f /srv/analogforge/current)")
  RELEASE_ID="$active_commit" "$release/analogforge/ops/azure/backup.sh"
elif docker volume inspect analogforge_postgres >/dev/null 2>&1; then
  if [[ -f /srv/analogforge/staged-commit ]]; then
    active_commit=$(cat /srv/analogforge/staged-commit)
    RELEASE_ID="$active_commit" "$release/analogforge/ops/azure/backup.sh"
  else
    echo "Existing database has no release record; inspect it and take a backup before retrying." >&2
    exit 1
  fi
fi
# Gracefully drain an existing worker before migrations; no new jobs during the short switch.
"${compose[@]}" stop proxy api worker
# Explicitly recreate one-shot jobs on EVERY release. Never cache an old successful migration.
"${compose[@]}" rm -f seed migrate provision-runtime-role initialize-volume
printf '%s\n' "$commit" > /srv/analogforge/staged-commit
"${compose[@]}" up -d --wait --wait-timeout 180 db
"${compose[@]}" run --rm --no-deps initialize-volume
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" run --rm --no-deps provision-runtime-role
"${compose[@]}" run --rm --no-deps seed
"${compose[@]}" up -d --wait --wait-timeout 300 api worker proxy
python3 "$release/analogforge/ops/azure/receipt.py" "$commit" "$AF_ENV_FILE"
ln -sfn "$release" /srv/analogforge/current
printf 'Activated source commit %s. Run the public browser journey before declaring the release ready.\n' "$commit"
