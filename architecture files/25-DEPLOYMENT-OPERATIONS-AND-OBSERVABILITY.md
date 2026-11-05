# Deployment operations and observability

Ship the same API/worker/database topology locally and in a hosted container environment. Select an actual hosting account only when deployment is requested; this specification does not authorize buying services or publishing the app.

## Compose services

- `db`: pinned PostgreSQL16/PostGIS3.4 image digest, healthcheck, named data volume, port bound to loopback for development only.
- `api`: Python image with matched native science dependencies, HTTP port8000, DB connection and read access to artifact volume, health/ready endpoint.
- `worker`: same package/image, worker entry point, writable artifact volume, bounded CPU/memory, lease heartbeat.
- `web`: Vite development server on5173 for development; production build is static assets served by reverse proxy or API.
- `proxy`: hosted-only HTTPS terminator, frontend routing and /api,/auth proxy. Disable SSE buffering and allow long-lived connections/15-second heartbeat.

Initial developer machine budget: 4 CPU cores, 8 GiB RAM and 20 GiB disk for small scenarios. Hosted worker starts with 2 CPU/4 GiB memory and 20 GiB persistent storage; these are planning assumptions validated with real raster workloads. API remains separately limited so worker pressure cannot kill all request handling. Workers gracefully stop claiming jobs on SIGTERM and either finish within grace period or release/requeue by lease expiry.

## Release sequence

1. Build immutable images and frontend assets from dependency locks and source commit.
2. Run offline checks, contract diff and database migration test.
3. Snapshot DB and referenced artifact manifest; verify a recent restore drill exists.
4. Apply backward-compatible migration using separate migration credentials.
5. Deploy API and worker with matching schema/algorithm versions; readiness checks before traffic.
6. Run synthetic smoke test, then selected opt-in live adapter probe if credentials/quotas permit.
7. Record release ID, image digests, source revision, schema version, config hash and test report. Rollback application image only when schema compatibility permits; never blindly downgrade data.

## Observability

Structured logs: timestamp, severity, request_id, workspace_id, run_id/preparation_id, job_id, invocation_id, tool_name, duration_ms, outcome, safe error code. Exclude prompts containing secrets, authorization headers and private chain-of-thought. Correlation IDs flow from HTTP command through job, receipt, result and event.

Metrics: API latency/error rate; ready/active/blocked jobs; oldest queued job; lease losses; worker heartbeats; source download failures/bytes; raster cells/time/peak memory; cache hit rate; route expansions/labels/time/search status; verifier violations; role/model calls/token usage and configured cost estimates; run completion/block/failure counts; SSE connection/reconnect/cursor-expiry counts. Qualification FAIL is a scientific outcome, not an infrastructure error alert.

Initial operational targets for bounded synthetic/reference scenarios: health<100ms, ordinary reads p95<500ms, queued command acceptance<1s, committed event visible<2s, cancellation acknowledged<2s and worker stopping within5s at tool checkpoints. Live source/network latency is measured separately. Do not advertise these targets as achieved until measured on the chosen hardware.

## Backup and retention

Nightly encrypted database backup plus content-addressed artifact manifest and new blobs; preserve all blobs referenced by retained passports. Record backup verification status. Restore test weekly in deployment rehearsal and before destructive migrations. A DB-only backup is insufficient because evidence points to external blobs.

Default retained runs/evidence30days minimum, passports retained until explicit workspace deletion or configured longer policy. Log retention14days, temporary files24hours, orphan blobs24-hour grace before GC. Do not delete source products still referenced by any retained run. Provider source availability may change; local locks/checksums and permitted cached copies preserve reproducibility within licensing constraints.

## Runbooks

Provider auth failure: disable retry storm, mark dependency blocked, rotate in secret manager, re-preflight, resume. Worker lost: inspect heartbeat/resource metrics, fence old lease, requeue bounded work. Corrupt source: quarantine hash/path, invalidate only derived artifacts depending on it, fetch verified source into new lock. Storage full: stop new downloads/jobs, preserve committed evidence, add space/approved GC, retry. SSE gaps: snapshot resync; do not replay user mutations. Model budget exhausted: finish honest blocked/inconclusive report, never switch to an unlabelled synthetic answer.

## Acceptance

Run a restore into an empty environment and verify random evidence checksums and one passport lineage. Restart API/worker under load without losing committed state. Confirm frontend deep links work after reload, SSE passes through proxy unbuffered, database is private, live keys stay server-side, and all release metadata is visible to operators.
