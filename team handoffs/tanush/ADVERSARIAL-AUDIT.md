# Tanush adversarial audit — 2026-11-06

Independent, read-only review of `analogforge` on `tanush/platform-agents-integration` while builders were active. Five required reviewer surfaces were covered. No production or test file was edited, committed, or pushed. Findings are snapshot-specific; rerun affected checks after fixes.

## Re-audit after builder updates

The five reviewers rechecked their findings against the updated source. The **hosted auth route gap** and **graph passport evidence failure** are fixed; the remaining findings below are still open at this snapshot. New checks found an unhandled OIDC issuer-outage path and loss of scientific issue codes at the HTTP error boundary. The source is changing concurrently, so this is a review handoff, not a final gate result.

## CR001 independent contract decision

The frozen export `200 application/json` schema requires a JSON **string**, while architecture 35 §4 requires a top-level JSON **object** with manifest and bundle fields. Direct Draft 2020-12 validation confirms the object fails the schema; double-encoding it as a string passes the schema but fails the export and verifier requirements. Architecture 07 also requires 404, 422 and 413 for the relevant failures; affected frozen operations omit those response declarations and have no default response. No truthful local response can satisfy both documents and PLT-02. The platform's proper JSON object and unchanged kit are the honest branch choice. [CR001](CHANGE-REQUEST-001.json) needs the **merging agent's central contract-change checkpoint** under architecture 35 §8; full PLT-02 and `ready_to_merge=true` cannot truthfully be claimed before that decision and regenerated-consumer tests. The separate artifact download mismatch has been fixed locally: whole-object `200 application/octet-stream`, including for ignored Range requests; its focused HTTP test passed.

## Fix first

| Priority | Finding | Evidence / next check |
| --- | --- | --- |
| P1 | Role policy accepts schema-valid forged/foreign nested evidence, inflated PASS/HIGH qualification claims, and contradictory contract/rover summaries; scheduler records them as successful role results. The forged row does not currently overwrite the science table, but the policy acceptance boundary is bypassed. | [Policy review](audits/policy-bypass.md), `agents/runtime/invocation.py:15-21`, `domain/policy.py:27-51`, `application/scheduler.py:551-598`; isolated reproductions passed through both validators. Validate nested references and authoritative values before publication. |
| P1 | A science deadline/cancellation escapes `Worker.run_once()` and can stop the sole worker, leaving a job RUNNING. | [Recovery review](audits/concurrency-recovery.md), `jobs/worker.py:58-63,100-102`, `jobs/cpu.py:70-73`; reproduced with a persisted random-workspace job. |
| P1 | Run state transition and successor job enqueue are separate commits; a crash between them can strand an active run. | [Recovery review](audits/concurrency-recovery.md), `application/scheduler.py:791-808`; static transaction trace and crash-point reproduction plan. |
| P1 | Frozen response contract disagrees with the required JSON passport export object; no truthful local serialization satisfies both. | [Contract review](audits/contract-audit.md), [CR001](CHANGE-REQUEST-001.json), architecture 35 §4/§8; central merge checkpoint required. |
| P1 | Live role submissions are accepted and stored, but their validated disposition/payload/next action never drives the scheduler transition. | [Hardcoding review](audits/hardcoding.md), `application/scheduler.py:462,491,551-583,1225-1265`; exercise changed live role decisions in an integration test. |

## Also address

- Max-attempt reaping leaves runs/preparations active or pending without a claimable job; cancellation and publication take job/run locks in opposite order and can deadlock. See [recovery review](audits/concurrency-recovery.md).
- The seeded scale defect is inserted and resolved inside one scheduler step rather than a proposal/review/repair cycle. See [hardcoding review](audits/hardcoding.md).
- Registrar accepts `javascript:`/`file:` as `source_uri` and exposes the value in evidence; this is a stored unsafe link value, with browser exploitation dependent on how the UI renders it. See [security review](audits/security.md).
- Several routine API errors (unknown scenario 404, invalid parameter 422, oversize POST 413) are absent from the frozen response declarations. The earlier artifact 206/416 issue is fixed. Current conformance tests register all 43 routes but exercise only a subset of response paths. See [contract review](audits/contract-audit.md).
- `ScientificClaimRejected.issue_codes` are discarded by the generic HTTP error mapping, leaving `details: {}`. OIDC upstream HTTP failures are not mapped to a stable sanitized API error and can return 500. See [contract review](audits/contract-audit.md) and [security review](audits/security.md).
- Guide 09's changed-storyline perturbation proof is not represented in the reviewed platform tests. See [hardcoding review](audits/hardcoding.md).

## Verified controls and test results

- 43 registered `(method, path, operationId)` tuples match the frozen OpenAPI. Existing contract suite: **11 passed**.
- Focused identity, workspace, storage and secret tests: **10 passed** at first review. New auth HTTP plus identity tests: **8 passed**; the four `/auth/*` routes now exist outside the frozen contract and exercise PKCE, membership, cookie flags, CSRF and logout.
- Focused recovery/idempotency/lease tests: **12 passed**. They do not cover the failure paths above.
- Policy/budget unit tests: **42 passed** at first review; focused policy/budget/live-provider checks: **58 passed** at re-audit. An unlisted role tool call was separately reproduced as `FORBIDDEN_TOOL`. No silent live-to-scripted fallback was found in the reviewed runtime path.
- Graph journey integration: **now passed** (`1 passed in 13.64 s`); scheduler filters the passport role's citations to receipt-supported evidence. The prior failure is fixed at this snapshot.

Reports: [policy bypass](audits/policy-bypass.md), [concurrency/recovery](audits/concurrency-recovery.md), [HTTP contract](audits/contract-audit.md), [security](audits/security.md), [hardcoding/outcome](audits/hardcoding.md).
