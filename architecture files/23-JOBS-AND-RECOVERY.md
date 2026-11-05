# Durable jobs events and recovery

PostgreSQL is the durable scheduler. CPU subprocesses and model calls are replaceable execution attempts. The database records the accepted command, its input hash, lease owner, committed outputs and the run-local event sequence.

## Job state and claim

Job states: QUEUED, RUNNING, SUCCEEDED, FAILED, BLOCKED, CANCELLED. A job references either a run or a preparation, exactly one. Queued jobs have `available_at`, priority and max attempts. Claim one inside a short transaction with SELECT FOR UPDATE SKIP LOCKED, update to RUNNING, create a fresh random lease_token, set lease_expires_at and increment attempt, then commit before doing external work.

```sql
WITH picked AS (
  SELECT id FROM jobs
  WHERE state = 'QUEUED' AND available_at <= now()
  ORDER BY priority DESC, available_at ASC, id ASC
  FOR UPDATE SKIP LOCKED LIMIT 1
)
UPDATE jobs j SET state='RUNNING', lease_token=:token,
  lease_expires_at=now()+interval '120 seconds',
  heartbeat_at=now(), attempt=attempt+1
FROM picked WHERE j.id=picked.id RETURNING j.*;
```

This pattern uses PostgreSQL's documented queue-oriented locking behavior; see [SELECT locking](https://www.postgresql.org/docs/16/sql-select.html). Keep transactions short and never retain a row lock across a model/download/raster computation.

## Heartbeats and fencing

Coordinator heartbeats every 20 seconds with `UPDATE ... WHERE id=? AND state='RUNNING' AND lease_token=?`. Extend by 120 seconds. A zero-row update means lease lost: stop and refuse publication. Final publication transaction locks the job and run, checks token and cancellation, inserts receipts/results, transitions state, and completes job. A stale worker must not commit even if it finished first in wall-clock terms.

A reaper scans expired RUNNING jobs every 30 seconds. If attempts remain, reset to QUEUED with backoff and clear old token; otherwise mark FAILED and commit a SYSTEM/WORKER_LOST event. Existing immutable evidence is reused by input hash; partial temp files are discarded. If an external model request may already have been billed, record the uncertain attempt and do not claim exactly-once provider execution.

## Retry policy

- HTTP transient/connectivity/429/5xx: up to 3 total attempts including the initial request, with 2- and 4-second retry delays plus bounded jitter; honor provider Retry-After up to configured run budget.
- Invalid model JSON/schema: one schema-correction attempt within role budget; persistent failure blocks that role rather than bypassing validation.
- 401/403: no automatic key guessing or password retry; dependency BLOCKED.
- Source checksum/content/CRS mismatch: quarantine input; no blind retry of scientific interpretation.
- Scientific FAIL: do not retry the same deterministic input hoping for PASS. Diagnose and generate a different permitted route/zone/site.
- Search budget exhausted: preserve INCONCLUSIVE and counters; a permitted retry may increase operational search budget but cannot alter mission constraints.

Default MAX_REPLANS 3 and MAX_RUN_MODEL_CALLS 40 are operational caps. Record all budget charges including failed/retried calls. Human review wait does not consume active computation wall time. User RETRY after repairing a dependency resumes from the last committed checkpoint.

## Cancellation

CANCEL sets `cancel_requested_at` transactionally and appends event. Coordinator checks before each network call, at each tool boundary, and periodically during CPU work via a shared cancellation token. Ask subprocess to stop, then terminate after 5 seconds if needed. Preserve completed artifacts/receipts, mark incomplete attempts cancelled through job/invocation events, and do not commit late scientific results after cancellation. A cancelled job is not a failed experiment.

## Event publication

Lock run row and compute `seq = last_event_seq + 1`. Insert event and update last_event_seq/revision in the same transaction as the result causing it. An event type cannot announce a result that is only in memory. Event payloads contain IDs, revisions, measured summaries and safe explanatory text, not raster arrays or provider credentials. Payload size target <16 KiB; link detailed artifacts.

SSE handlers replay the table, not a worker process's memory. On client reconnect refetch snapshot and replay after its cursor. Notifications, if added, merely wake a polling reader. Completed run events remain available for inspection and replay.

## Checkpoints

Checkpoint after input validation, target characterization, candidate batch, qualification batch, critic disposition, frozen test design, each route search, independent verification, diagnosis, replan selection, and passport assembly. A checkpoint stores selected IDs and input hashes. Resume computes only missing/invalidated steps. Replacing a source-policy lock or contract creates a different run. Acquiring a new granule already permitted by that policy appends immutable asset/evidence records; existing derivations remain pinned to their exact inputs, as specified in21.

FastAPI BackgroundTasks are not the implementation of this durable scientific queue; expensive independent work belongs in the worker. This choice follows the separation described in [FastAPI background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/), while our database lease policy supplies durability.

## Acceptance

Use two workers to prove only one owns a lease at a time. Let a lease expire and attempt late publication from the old token. Crash after blob creation before DB commit; repeat and deduplicate. Disconnect SSE during verification; reload and recover the complete state. Cancel during route search and confirm no PASS is published afterwards.
