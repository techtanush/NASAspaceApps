# Private native PostgreSQL fallback

Use PostgreSQL 16/PostGIS 3.4 or a compatible newer local pair when Docker is unavailable. On macOS, install PostgreSQL and PostGIS with Homebrew. Set `DATABASE_URL`, `DB_PORT`, and `PROFILE=tanush` in this app's `.env`, then run `make bootstrap`. The fallback initializes `.runtime/pg` with UTF8 encoding, starts it on the configured loopback port, creates the database with `--encoding=UTF8 --template=template0`, and enables PostGIS. The existing private PostgreSQL 17.11/PostGIS 3.7 cluster has passed migration and restore tests. Keep `.runtime/` outside Git; then run `make migrate`, `make seed-synthetic`, and `make preflight`.

Do not stop an existing PostgreSQL process you did not start. Check the selected port before starting the private cluster. Use `pg_ctl -D .runtime/pg stop` to stop this cluster only.

The app's `db up|down|status` commands operate the Compose database. For a native cluster, use `pg_ctl` and this runbook; API and worker use the same `DATABASE_URL`.
