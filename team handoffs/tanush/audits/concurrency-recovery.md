# Concurrency and recovery audit — final recheck, 2026-11-06

Scope: read-only adversarial review of worker leases, cancellation, recovery, state checkpoints, CAS, and idempotency on `tanush/platform-agents-integration`. No production or test files changed. Rechecked architecture 23 and 33–40 and Tanush guide 09.

## Final status

**The four previously reported recovery defects are fixed in current source.** Focused PostgreSQL suite: **19 passed in 3.95 s** with `TEST_DATABASE_URL=postgresql+psycopg://tanushchokshi@127.0.0.1:5433/analogforge_test` and `PGCLIENTENCODING=UTF8`. This suite covers lease fencing, cancellation, worker exceptions, exhausted retries, concurrent cancel/publication, CAS, and idempotency. There is no remaining actionable finding from this audit.

| Previous finding | Status | Evidence |
| --- | --- | --- |
| Deadline/cancellation exception kills worker | **Fixed** | `jobs/worker.py:58–66` handles `ScienceCancelled` and `ScienceDeadlineExceeded`. A fresh random-workspace reproduction of a deadline returned normally from `run_once()`; job and run both became `BLOCKED`. `tests/unit/platform/test_persistence_worker.py:41–67` also proves the worker handles another job after either exception. |
| Run checkpoint and successor enqueue are separate commits | **Fixed** | `application/scheduler.py:151–191, 1056–1068` now updates run/event, enqueues successor, and completes current job in one lease-fenced transaction. Injecting an exception at `UnitOfWork.enqueue` rolled the whole transaction back: run remained `VALIDATING` revision 1 and current job `RUNNING`. Retrying without the exception atomically produced `CHARACTERIZING`, current job `SUCCEEDED`, successor `QUEUED`. |
| Exhausted retry leaves parent active | **Fixed** | `jobs/queue.py:83–149` settles an exhausted run or preparation in the same transaction as the failed job. `tests/integration/platform/test_recovery.py:16–53` exercises both parent kinds and checks the run failure event. |
| Cancel/publication lock inversion | **Fixed** | `db/store.py:383–396` locks run/preparation before job; `cancel_run` uses run then job. The reaper uses parent then job as well. `tests/integration/platform/test_jobs_leases.py:157–197` runs concurrent cancellation/publication and verifies cancellation completes without a late result. |

## Checks retained

- Lease token, expiry, state, and cancellation are checked before and after publication (`db/store.py:398–422`). The stale-owner and cancel tests passed.
- Queue claims use `FOR UPDATE SKIP LOCKED` with a fresh lease token (`jobs/queue.py:29–58`); the two-worker test passed.
- Idempotency compares body hashes under an advisory transaction lock (`db/store.py:277–309`), and run replacements check `expected_revision` under a row lock (`db/store.py:173–219`). Concurrent duplicate, changed-body, and CAS tests passed.
- The reaper now runs as an independent component through `jobs/reaper.py`; worker polling invokes it via `jobs/worker.py:47`.

Limit: the checkpoint crash check injected an exception at the enqueue boundary rather than killing a real worker process. Transaction rollback and successful retry were both observed in PostgreSQL. The existing focused tests do not themselves include this exact injected boundary test.
