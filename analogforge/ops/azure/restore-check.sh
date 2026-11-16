#!/usr/bin/env bash
# Verify a backup in a disposable DB; never overwrites the active database or evidence.
set -euo pipefail
if [[ $EUID -ne 0 || $# -ne 1 ]]; then echo "Usage: sudo restore-check.sh BACKUP_DIRECTORY" >&2; exit 1; fi
backup=$(realpath "$1")
cd "$(dirname "$0")/../.."
export AF_ENV_FILE=${AF_ENV_FILE:-/etc/analogforge/runtime.env}
export AF_DB_ENV_FILE=${AF_DB_ENV_FILE:-/etc/analogforge/database.env}
export RELEASE_ID=${RELEASE_ID:?Set RELEASE_ID to an available runtime image commit}
compose=(docker compose --env-file "$AF_ENV_FILE" --env-file "$AF_DB_ENV_FILE" -f ops/azure/compose.yaml)
if [[ -n ${AF_COMPOSE_OVERRIDE:-} ]]; then compose+=(-f "$AF_COMPOSE_OVERRIDE"); fi
(cd "$backup" && sha256sum -c SHA256SUMS)
database="af_restore_$(date +%s)_$$"
"${compose[@]}" exec -T db createdb -U af_admin "$database"
cleanup() { "${compose[@]}" exec -T db dropdb -U af_admin --if-exists "$database"; }
trap cleanup EXIT
"${compose[@]}" exec -T db pg_restore -U af_admin -d "$database" --no-owner --no-privileges < "$backup/database.dump"
[[ $("${compose[@]}" exec -T db psql -U af_admin -d "$database" -Atc "SELECT extname FROM pg_extension WHERE extname='postgis'") == postgis ]]
python3 - "$backup/evidence.tar.gz" <<'PYCODE'
import hashlib, re, sys, tarfile
count = 0
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for member in archive:
        if not member.isfile() or not re.fullmatch(r'./blobs/[a-f0-9]{2}/[a-f0-9]{64}', member.name):
            continue
        stream = archive.extractfile(member)
        assert stream is not None
        if hashlib.file_digest(stream, 'sha256').hexdigest() != member.name.rsplit('/', 1)[-1]:
            raise SystemExit('Evidence checksum mismatch')
        count += 1
print('PASS: restored PostGIS database and checked', count, 'content-addressed evidence blobs; live data unchanged.')
PYCODE
