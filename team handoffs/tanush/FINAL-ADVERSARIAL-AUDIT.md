# Final focused adversarial audit — 2026-11-06

Read-only recheck of `tanush/platform-agents-integration` after the platform fixes. Five reviewers inspected current source and tests; no auditor edited production code, tests, or the frozen kit. Results describe this branch snapshot while builders may still be writing.

## Latest follow-up on P1/P2 fixes

The malformed OIDC discovery, scientific issue-code HTTP, registrar source-URI, and bounded live role choice findings are **FIXED** in current source. Endpoint values are now bounded strings with URL parse errors mapped to a safe 503 (`adapters/identity/oidc.py:55-67`, `main.py:126-139`); `ScientificClaimRejected.issue_codes` now populate `details.issue_codes` in the 422 envelope (`main.py:130-140`). The malformed registrar URI raises `RegistrationRejected`, writes one failed receipt, publishes zero evidence, and quarantines the run. A combined focused rerun of live choice, HTTP error, OIDC failure, and registrar tests passed **23 tests in 4.03 s**. Four invalid role-choice mutations passed separately (**4 tests in 0.84 s**). CR001 remains a central merge checkpoint.

## Finding before central resolution (closed below)

| Priority | Finding | Evidence and action |
| --- | --- | --- |
| Merge blocker | **CR001:** required JSON passport export is a top-level object, while this branch's frozen 200 `application/json` schema requires a string. Several required 404/422/413 paths have no operation response declaration. No truthful local response satisfies both architecture 07/35 and PLT-02 under this branch's kit. | [Contract audit](audits/contract-audit.md), [CR001](CHANGE-REQUEST-001.json). Central contract resolution is being previewed outside this audit; merge the approved kit change, regenerate consumers, and rerun conformance before clearing the blocker. The 43-operation transport test on this branch explicitly expects the JSON schema failure; its green result is **not** proof of PLT-02 for this response. |

## Previously reported defects now fixed in the examined paths

- **Policy:** schema-valid foreign/fabricated nested evidence, inflated PASS/HIGH, altered contract hash/revision, lowered rover reserve, unlisted tool, and explicit stale revision probes now reject with specific policy codes. The focused policy and runtime journey tests passed (19 and 4). [Policy audit](audits/policy-bypass.md).
- **Recovery:** deadline/cancellation no longer kills the worker; run checkpoint, successor enqueue and current-job completion share one fenced transaction; exhausted retries settle the parent; cancellation/publication use consistent lock order. The focused PostgreSQL suite passed (19), and direct deadline and enqueue-boundary rollback/retry checks passed. [Recovery audit](audits/concurrency-recovery.md).
- **Security:** hosted OIDC HTTP login/callback/session/logout, cookie flags, membership, CSRF, workspace isolation and source URI scheme/host restrictions pass the focused checks. The combined HTTP/identity/registrar/settings/secrets/workspace/RLS suite passed (42). [Security audit](audits/security.md).
- **HTTP error mapping:** malformed OIDC discovery endpoint types now return a sanitized 503, and scientific claim rejection retains structured issue codes in a valid 422 error envelope. Seven issuer negative cases plus both actual HTTP boundary tests passed (9). [Security audit](audits/security.md), [contract audit](audits/contract-audit.md).
- **Registrar source URI:** malformed bracketed URL input now follows the rejected registration path: one failed receipt, no published evidence, and quarantine. The isolated repro and the parameterized registrar regression passed (13 tests). [Security audit](audits/security.md).
- **Bounded live choices:** role proposals are checked against permitted candidate, strategy, repair-kind, and repair-target lists, and the scheduler consumes selected values. The new actual Responses-protocol integration test runs `OpenAIProvider` against a local fake server. It changes `NEW_ROUTE` to `NEW_CANDIDATE`, selects the second eligible candidate and `MINIMUM_FEASIBLE_ROUTE`, and verifies those choices in the persisted next attempt while retaining the prior FAIL verdict and mission/rover hashes. Four invalid-choice mutations reject. [Hardcoding audit](audits/hardcoding.md).
- **Contract transport:** all 43 frozen operations are registered and exercised by the new transport suite; artifact downloads now send whole-object `200 application/octet-stream`, including when Range is supplied. Contract suites passed (14), subject to the explicit CR001 expected failure. [Contract audit](audits/contract-audit.md).
- **Outcome integrity:** graph journey passes; the seeded scale defect is rejected, remains OPEN after one job, and resolves after a later repair job; changed verifier and no-repair diagnosis yield FAIL/FAIL and no verified-route claim; live does not fall back to scripted roles. Focused suite passed (26). [Hardcoding audit](audits/hardcoding.md).

## Remaining proof limits

The policy's new nested-payload rejection has isolated adversarial probes but lacks a dedicated automated regression test. The perturbation test covers verifier failure and no repair, not every geometry or mission-hash mutation in guide 09. Recovery's checkpoint boundary was fault-injected with an exception and rolled back correctly in PostgreSQL; a real process-kill test was not part of this focused pass. These limits should be recorded in the broader self-audit rather than treated as failures of the checks above.

No real external OpenAI, NASA-source, or physical scientific validation is claimed by these platform-focused tests. Full PLT-02 and branch merge readiness remain conditional on the central CR001 resolution and conformance rerun.

## Final CPU and process-recovery closure

Production code is frozen at `eb4cd4c63e4477a050370c8084c89c596e9ea1af`. A spawned-child probe reproduced a raw token URL in stderr when an ordinary child exception escaped. After the fix, `cpu._child` catches exceptions after the typed cancellation and deadline paths and sends only the exception type name. Three spawned normal-exit stderr regressions for `KeyError`, `AttributeError`, and `AssertionError` pass. The cancellation bound fix is at `5465009`; **22 focused CPU, worker, and lease tests pass**.

Actual API and worker process `SIGKILL` recovery tests are now committed and tested. This supersedes the earlier proof-limit statement that a real process-kill test was absent. The earlier exception-injection evidence remains valid but is no longer the only process-boundary evidence.

The central CR001 kit change at `4c9897c` has been accepted. Its final strict conformance and full-suite results are still pending from the root run; the merge blocker above remains open until those results are recorded. No further production changes are part of this audit pass.

## Final central-contract and frozen-source closure

Source `eb4cd4c63e4477a050370c8084c89c596e9ea1af` passed278 platform tests with zero failures/errors/skips; separate kit20 passed. All20 mutations are killed and scans/lint/strict typing pass. The final C3 preview `ceda96f049607abc33a453966fa367fb9f5541bd` incorporates central correction `4c9897c96dc082b82b654988ff6898f85b90e504`: all43 operations and81 responses validate strictly, with zero schema exceptions or stale conflict notes. C3 preceding full baseline275, final affected22+transport3+kit20, and final root278 source-equivalence proof are recorded in [the integration report](validation/c3-preview.json).

CR001 is closed for integration into that accepted C3 checkpoint. The feature preserves its original C2 bytes and explicitly records C2's remaining incompatible declaration; no C2 conformance claim is made. No remaining owned implementation blocker was found. Real science/renderer/browser/source/model integration is outside this platform acceptance and remains unrun. Aggregate `make check` fails the named production dependency preflight truthfully.
