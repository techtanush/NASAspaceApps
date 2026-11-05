# Tanush interfaces and handoffs

Read shared03 as the binding seam. You are the only producer of common domain/API/port changes and the only committer of durable scientific state.

## What Ayan needs from you

Provide F0 domain types, ScienceService request/context/result models, safe artifact read/scratch interfaces, mode guard, cancellation/deadline/progress API and source credential access policy. Give expected operation names and example typed requests; avoid giving him DB IDs with no authorized resolver/materialized input. Include installed science packages and exact worker native-library versions.

Your wrapper calls his facade, registers result-local artifacts/evidence keys atomically and resolves public candidate/profile/test/measurement IDs. His module must never need a SQL session to calculate a slope. If his output suggests PASS with incompatible/missing evidence, policy rejects/marks UNKNOWN rather than trusting the label.

Handoff F0 includes exported contract hashes, source policy identity/version, ports signature hash, safe settings, run profiles, test commands and commit SHA. Future modifications follow a concrete contract-change record. Ayan returns operation coverage, computed fixtures, source validation, numeric tests and typed limitations.

## What Aradhya needs from you

Provide stable OpenAPI export, capabilities/scenario IDs, draft read/save/preparation endpoints, immutable input retrieval, selection pointers, operations/receipts/critiques/reviews, display manifests, TestResult retrieval and SSE semantics. Provide a seed command and deterministic synthetic data she can drive through the real API. Explain actual pending/export202 behavior and local base URL/CORS profile.

She generates client types and owns browser code; do not send undocumented JSON snippets as a substitute for API changes. Use the same schema/error cases in platform contract tests and frontend MSW fixtures. On integration assert MSW is off and server job/receipt IDs exist.

For renderer provide a complete PassportExportBundle plus validated image bytes. Her renderer returns bytes, MIME, safe filename/hash and version; you authorize/store/serve it. File digest and manifest digest are distinct.

## What you receive and how to accept it

Ayan: exact SHA, scientific facade implementation, graph/analytic expected outputs, package requests, source/policy/asset notes, supported/unavailable operations and test report. Accept only if its calculations work without API/model/DB and outputs carry scale/lineage. Aradhya: exact SHA, real/mock startup commands, generated-client schema hash, UI/renderer tests and assets. Accept only if scientific states are server-owned and missing/error/unknown modes are preserved.

Do not accept a handoff with "tests should pass" or an unspecified branch tip. Run producer tests plus actual cross-boundary contract cases in an integration candidate. File conflicts, semantic conflicts and missing interfaces have distinct owners. Return a short exact defect/reproduction to the person; this document itself does not authorize sending external messages through tools.

## Final reporting

Own `team handoffs/tanush/` checkpoint reports and final integration report. Reference other producer reports rather than rewriting their observed results. Declare explicit `platform_ready`, `scientific_modules_integrated`, `frontend_integrated`, `offline_e2e_passed`, `real_data_gates`, `live_model_gate` and `remaining_blockers`. Successful local source merges do not imply all those fields are true.

## C1 scientific assurance seam

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
