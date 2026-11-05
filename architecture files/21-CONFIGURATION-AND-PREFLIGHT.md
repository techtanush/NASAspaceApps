# Configuration and preflight

Configuration is typed, validated at startup, and snapshotted per run. Defaults below are engineering choices, not measured rover or mission facts. User-visible mission assumptions require acceptance in a contract; operational resource limits do not change scientific requirements.

## Environment variables

| Setting | Default or requirement | Validation |
| --- | --- | --- |
| DATABASE_URL | Required | PostgreSQL psycopg URL; redact credentials. |
| DATA_ROOT | /data in containers | Writable server-owned volume; no symlink escape. |
| ANALOGFORGE_MODE | synthetic | One of live/replay/synthetic; default for new work only. |
| OPENAI_API_KEY | Empty | Required for live AI; server only. |
| OPENAI_MODEL | Empty | Required and capability-tested for live; explicit model ID. |
| EARTHDATA_TOKEN | Empty | Required only for selected protected compatible downloads. |
| AUTH_MODE | local | local or oidc; local binds loopback only and is rejected for public deployment. |
| PUBLIC_BASE_URL | http://localhost:8000 | HTTPS required for oidc hosted profile. |
| ALLOWED_ORIGINS | ["http://localhost:5173"] | JSON list of exact origins; no credentialed wildcard. |
| SESSION_SECRET | Empty | At least 32 random bytes for oidc; required outside local mode. |
| OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET | Empty | All required for oidc. |
| LOG_LEVEL | INFO | DEBUG redacts exactly as INFO; never dump environment. |
| WORKER_CPU_CONCURRENCY | 2 | Integer 1–8, memory budget checked. |
| JOB_LEASE_SECONDS | 120 | Heartbeat 20 seconds; long tasks extend lease. |
| JOB_HEARTBEAT_SECONDS | 20 | Positive and < lease/3 or explicitly validated equal boundary. |
| MAX_DOWNLOAD_BYTES | 2147483648 | Per asset 2 GiB initial cap; large archives need explicit operator override. |
| MAX_AOI_AREA_KM2 | 2500 | Limits live detailed Earth analysis; larger coarse screening uses its own registry policy. |
| MAX_RASTER_CELLS | 4000000 | Per in-memory analysis window/allocation; source files may be larger and must be read in bounded windows. |
| MAX_RUN_MODEL_CALLS | 40 | Hard per-run call cap including retries. Preparation cap separately 4. |
| MAX_REPLANS | 3 | Then finish with remaining failures/unknowns; no endless loop. |
| MAX_RUN_SECONDS | 900 | End active computation budget excluding human review wait. |
| MAP_TILE_URL | Empty | Optional allowlisted licensed source; not a credential store. |
| VITE_API_BASE_URL | /api/v1 | Public frontend URL only; no secret VITE variables. |

Settings not listed here require a documented addition. Files `config/datasets.yaml`, `algorithms.yaml`, and `scenarios.yaml` contain nonsecret settings. Hash their canonical effective forms into the run manifest. Environment overrides cannot alter a running contract or source lock.

## Preflight stages

Implement `analogforge preflight --mode <mode> --scenario <id> --output <path>`. It produces JSON and readable summary, nonzero if required gates fail. Gate outputs contain code, severity, dependency, checked_at, safe explanation, and remediation. Do not print keys or raw auth headers.

1. RUNTIME: Python/native scientific libraries import; GDAL drivers and projection database available; frontend build and schema versions compatible.
2. STORAGE: DATA_ROOT has write/atomic-rename capability and sufficient free space (initial 10 GiB floor); database migration current; worker heartbeat healthy.
3. IDENTITY: local interface loopback or hosted identity valid; callback/base URLs match; development identity never public.
4. MODEL: live key+model capability probe; synthetic/replay assert no provider client will be invoked.
5. METADATA: resolve actual chosen dataset collections/products. Inspect product labels, body/CRS, units, native resolution, vertical reference and access method.
6. DOWNLOAD: download actual selected tiles/granules or validate already-cached checksums; detect HTML/error bodies, corrupt archives, expired credentials and unavailable coverage.
7. SCIENCE: compute small terrain feature probe, compare at permitted scale, ensure no-data mask survives, verify planetary longitude/latitude conventions, route synthetic plane test.
8. SCENARIO: accepted requirement scales are supported; mandatory waypoints and energy assumptions available; at least one discovered candidate plus controls configured for discovery acceptance.
9. LOCK: write immutable `dataset-policy-lock.json`, a seed `acquired-assets.json` and `build-lock.json`. Policy records exact permitted product versions, query/search bounds and quality/decoder policy; acquired assets record real IDs/checksums; build lock records exact package/image versions and algorithm/config hashes.

Global geometry or data download is not a preflight prerequisite. Resolve a small target and bounded Earth tiles. Model availability alone does not pass science gates; metadata availability alone does not pass download gates.

## Lock rules

There are two levels of locking. `dataset_lock_id` on POST /runs refers to the frozen source-policy lock: allowed product families/exact versions, approved search extents, quality masks, decoders and any existing seed assets. The scout can discover and acquire new granules within that policy during the run. Each acquisition appends a new immutable entry to the per-run acquired-asset manifest; each derivation pins the exact source hashes it used. The passport freezes the final manifest hash. Replacing a source-policy version or reinterpreting already-used source bytes creates a new lock/run, not an in-place rewrite. Merely adding an allowed granule does not require a new run.

The provided dataset-lock template is intentionally unresolved and cannot serve as a validated live policy. Resolve actual product versions, source identities, body, supported source frame and access protocol before freezing it. Each acquired-asset entry separately requires real granule/product ID, stable source URI, bytes/checksum, CRS, vertical reference, native scale and retrieval status before becoming scientific evidence. A signed temporary URL must be stripped to stable identity plus separately protected short-lived access metadata.

Record optional unavailable sources as UNAVAILABLE with reason and affected requirements. The run may continue only if its mandatory claimed scope does not depend on them. Appended evidence never changes the byte hashes or meanings of earlier evidence. Requalification creates a superseding evaluation that names its expanded input set.

## Startup and capability reporting

Liveness can pass without external services. Readiness requires DB/schema and storage; capabilities expose whether each run mode and adapter can actually start. The UI disables dependent actions with specific remediation, while retaining access to past results. Configuration errors must be reported before a long run begins.

## Acceptance

No-key offline preflight passes for synthetic fixtures. Live preflight fails clearly with missing key, missing model, unsupported EDL endpoint, absent mandatory tile, corrupted checksum, unsupported CRS, insufficient space, or inconsistent scale. Optional missing mineral coverage yields a limitation and UNKNOWN rather than a global infrastructure failure.
