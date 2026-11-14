# Policy bypass adversarial audit

Scope: read-only source/test review of the Tanush branch, plus isolated Python reproductions; reviewed architecture 33–40 and Tanush guide 09. No production files or tests were changed. Findings below reflect the source at review time while other builders were active.

## Final re-audit status

**Both original findings are FIXED for the adversarial cases below.** The scheduler now supplies an authoritative role proposal, registered receipt summaries and rover facts in the task (`application/scheduler.py:615–640`). `validate_submission` invokes `validate_authoritative_payload` (`agents/runtime/invocation.py:15–21`), which checks nested evidence and receipt references, frozen contract fields, rover limits, qualification status/confidence and citation scope (`invocation.py:24–110`). The scheduler also locks and rechecks the current run immediately before publishing a role result (`scheduler.py:751–776`).

Fresh isolated probes against the updated source returned: nested foreign/fabricated UUID → `NESTED_REFERENCE_NOT_AUTHORIZED`; inflated `PASS` → `STATUS_INFLATION`; inflated `HIGH` → `CONFIDENCE_INFLATION`; altered contract hash/revision → `FROZEN_ROLE_INPUT_CHANGED`; lowered rover reserve summary → `ROVER_LIMIT_SUMMARY_CHANGED`; unlisted `search_route` → `FORBIDDEN_TOOL`; stale revision passed explicitly to `evaluate_transition` → `STALE_REVISION`. Every probe exited 0 after observing the intended rejection. Focused tests passed: `tests/unit/platform/test_policy.py` **19 passed** and `tests/integration/platform/test_runtime_journey.py` **4 passed** with the UTF8 test database; no database reset was performed.

**Remaining test gap:** `test_policy.py` still checks foreign evidence at the top level and calls `validate_comparison` directly; it does not assert the new nested-payload rejections. The isolated probes above demonstrate the current behavior, but dedicated regression tests would protect it. Prompt-injected source text was not exercised end to end in this audit.

## Finding 1 — schema-valid forged and foreign role evidence passed policy (historical; fixed)

At the initial review, `RoleSubmission` validated UUID syntax for nested references but not their authority, and `validate_submission` checked only role/task identity and the next action. `evaluate_transition` checked only **top-level** `proposal.evidence_ids` (`domain/policy.py:32–42`). A qualification role could submit `evidence_ids: []` at the top level, with an arbitrary foreign UUID under `payload.rows[0].evidence_ids` and `measurement_evidence_ids`, `proposed_status: PASS`, and `confidence: HIGH`. Both validators returned normally, even with `evidence={}` and `receipts=[]`; the scheduler stored the result as `SUCCEEDED`. This violated PLT-09 and guide 09 §3. The updated `validate_authoritative_payload` now rejects the same nested reference and inflated values before persistence.

Initial reproduction with `.venv/bin/python -B` produced `ACCEPTED qualification row with forged foreign evidence UUID, PASS and HIGH, while no evidence exists` (exit 0). The final re-audit probes above use the same class of schema-valid role submissions with an authoritative task payload and observe rejection.

Follow-up test still recommended: submit valid foreign and fabricated UUIDs in nested fields through `validate_submission`, then assert rejection before `role_results` or `agent.completed` publication.

## Finding 2 — altered accepted contract and rover limit passed role validation (historical; fixed)

At the initial review, the frozen-input check in `evaluate_transition` examined only root keys `mission_content_sha256` and `rover_content_sha256` (`domain/policy.py:27–29`). These are not fields of `RoleSubmission`, so a Requirements submission with a foreign `contract_revision_id`, different `contract_hash`, arbitrary `validation_receipt_id`, and `unchanged: true` passed both validators. A Rover Systems submission with a foreign `rover_revision_id` and a forged `hard_limit_summary` entry `min_reserve_pct = 13.0` likewise passed. The updated `validate_authoritative_payload` now rejects those changed fields.

Reproduction executed in the same isolated Python process as Finding 1, with task hash `"a" * 64` and Requirements payload hash `"b" * 64`. Observed outputs: `ACCEPTED requirements` and `ACCEPTED rover_systems` (exit 0). No database mutation was needed.

Follow-up test still recommended: assert the rejection of altered reserve, threshold, contract hash and revision through the full role-submission path.

## Checks that held and coverage gap

`ToolRegistry.execute` rejects an unlisted `search_route` invocation under the Requirements role with `FORBIDDEN_TOOL` before dispatch (`tools/registry.py`; `tools/allowlist.py`). I reproduced that rejection in both audits. Live provider offers only allowed tool schemas and handles malformed tool calls (`agents/runtime/openai_provider.py`). `get_evidence` in the scheduler filters to loaded run evidence. Terminal payload validation now has separate authoritative checks in `invocation.py`.

The current test tree has `tests/unit/platform/test_policy.py`, but it does not test nested role-payload references through `validate_submission`; `test_runtime_journey.py` asserts all ten roles appear, but does not adversarially alter their submissions. `test_workspace_isolation.py` exercises repository references rather than nested role payload references. Prompt-injected source text was not exercised end to end: the scheduler currently sends `untrusted_sources: []` in role tasks (`application/scheduler.py:635`). The targeted PLT-09 probes now reject as intended; the broader adversarial catalog still needs its dedicated automated tests.

Related concurrency observation: the scheduler still does not pass `expected_revision` to `evaluate_transition`, but now locks the current run and checks cancellation and scientific snapshot fields before publishing (`application/scheduler.py:751–776`). A revision-only concurrent event is outside this policy audit; the concurrency reviewer should determine whether it needs stricter fencing.
