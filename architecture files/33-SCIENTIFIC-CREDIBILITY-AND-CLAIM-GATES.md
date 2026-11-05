# Scientific credibility and enforceable claim gates

This is a binding implementation specification. Scientific credibility must come from appropriate evidence, reproducible calculations, independent checks and accurate claims. Agent agreement, a successful build, a polished map and a user accepting assumptions cannot supply missing scientific evidence. Implement this document with [11 qualification](11-QUALIFICATION-AND-UNCERTAINTY.md), [12 verification](12-ROUTE-ENERGY-AND-VERIFICATION.md) and [29 scientific validation](29-SCIENTIFIC-VALIDATION.md); their detailed scientific rules still apply.

The team controls source handling, algorithms, tests, assumptions, uncertainty treatment, reporting and honesty. External coverage, source accuracy, physical field performance and competition outcomes remain facts to establish. The baseline supports validation levels S0–S4 from29; it cannot award itself S5 physical validation. No part of this planning update claims those implementation gates have already passed.

## 1. Claims are backend decisions

Every persisted qualification, verification conclusion, recommendation and discovery statement needs a structured claim audit. A claim is a specific statement about an observable, requirement, location, scale, time context and accepted model. “This site is Mars-like” is too broad. “Under the accepted terrain model, this route supplies the required unique slope exposure” is testable.

`application.assurance.audit(snapshot, proposed_claims, registered_receipts)` loads authoritative stored inputs and returns a report validating against [scientific-assurance.schema.json](contracts/scientific-assurance.schema.json). It invokes deterministic gate evaluators from [scientific-gates.json](contracts/scientific-gates.json). It does not ask an LLM to decide whether the gates passed. Ayan provides scientific measurements and adequacy/verification results through the existing ScienceService port; Tanush enforces identity, provenance, revision, claim and publication rules around them. Do not implement a second scientific engine in the policy layer.

Each claim contains its stable claim ID, applicable requirement ID, candidate scope, qualification/verification status where relevant, evidence and assumption IDs, validation level, every gate outcome, limitations and an exact permitted statement. `SUPPORTED` describes support for the statement; a well-supported statement that a route **fails** remains a supported negative finding. Claim disposition is separate from the public qualification and verification enums.

The claim compiler constructs `qualified_uses`, `partial_uses`, `unsupported_uses`, unknowns and report conclusions from the audited rows. The model may propose wording, but it cannot set the audited result or add a conclusion outside that permitted scope. UI summaries, map tooltips, CSV, JSON, HTML and demo narration follow the same claims. Avoid an unconstrained model-generated executive summary that contradicts the table below it.

## 2. Required execution order

1. Load accepted mission, optional pinned rover, policy/config/algorithm locks and the current acquired-asset manifest. Verify workspace, mode and hashes. Material assumption changes create a new accepted revision/run according to00; never reinterpret an old result under new inputs.
2. Acquire approved exact assets, validate advertised and locally computed checksums where available, decode labels and masks, and register immutable source receipts. Metadata search hits alone are not analyzed sources.
3. Evaluate quantity/body/frame/datum/unit/time/scale/coverage compatibility for each requested observable. Unsupported observables stop before a positive metric is produced. Persist why the requirement is UNKNOWN, GAP or an expressly accepted proxy.
4. Compute only registered metrics with versioned parameters, actual support windows, nodata policy and error/sensitivity treatment. Store numerical outputs and input lineage before a role can cite them.
5. Evaluate requirements through frozen rules, then independently verify proposed experiments against source/normalized grids and frozen constraints. Search output is a proposal, not its own proof.
6. Apply critic findings. A material evidence challenge triggers repair, recomputation or downgrade. An unresolved challenge cannot coexist with a positive claim that relies on the challenged evidence.
7. Audit the complete claim set against the exact current snapshot. Persist gate failures and limitations even when they make the recommendation negative. Refuse invalid positive claims; retain the attempted proposal/receipt for diagnosis.
8. Atomically publish allowed domain results and their evidence references. Before final passport assembly, rerun the audit over the complete frozen manifest inputs. Hash/register the assurance artifact, then hash the passport manifest including its assurance pointer. Renderer consumes this frozen bundle.

Assurance must run before publishing scientific result rows, and again before final export. Do not show provisional PASS while an audit runs. A stale worker, changed input hash or lost lease cannot commit an older successful audit. Retries are idempotent for the same snapshot and policy; a different snapshot creates a new audit.

## 3. Mandatory gates

These IDs are stable test and handoff identifiers. Every claim includes every ID once. NOT_APPLICABLE requires an observable-specific reason; it cannot disable a gate required by that claim type. Missing gates are NOT_ASSESSED and forbid dependent positive claims.

| Gate | Backend must establish | If evidence is insufficient or invalid |
| --- | --- | --- |
| SC-01 Frozen scope | Exact accepted mission/rover, requirement/rule version, current snapshot and policy hashes; no changed thresholds to rescue a result. | Reject stale/tampered publication. New assumptions follow review/revision rules. |
| SC-02 Source integrity | Real analyzed bytes, asset identity/version, local checksum, decoder receipt, complete lineage and authorized evidence references. | Exclude invalid source; dependent finding becomes UNKNOWN. Invented lineage blocks publication. |
| SC-03 Physical semantics | Correct body, coordinate frame, axis/longitude conventions, vertical reference, units and measured quantity. | UNKNOWN until resolved; never default Mars/Moon to Earth CRS or compare unlike variables. |
| SC-04 Spatial support | Native and effective resolution, footprint, derivative window and common comparison support are adequate for the stated observable. | Restrict scope or UNKNOWN. Upsampling and visual smoothing cannot improve information support. |
| SC-05 Coverage and quality | Explicit AOI/route denominator, valid/invalid/quality masks, coverage fraction and observable-specific minimum coverage in the accepted rule. | UNKNOWN or defined PARTIAL; never fill nodata with zero or silently change the denominator. |
| SC-06 Temporal support | Acquisition/time-of-day/season/statistical interval and change sensitivity are compatible where relevant. | Limit the finding or UNKNOWN; do not equate thermal products with unrelated air temperatures. |
| SC-07 Assumptions and proxies | Direct measurement versus proxy is identified; required material assumptions/proxies were accepted at the correct scope. | Pause for review or UNKNOWN/PARTIAL. Acceptance cannot turn a proxy into direct physical proof. |
| SC-08 Uncertainty and decision | Error model, interval or unquantified limitation is explicit; frozen decision rule and sensitivity analysis support the precise wording. | Ambiguous threshold crossing cannot earn robust PASS. Nominal modeled results need the permitted scoped wording in11. |
| SC-09 Numerical reproducibility | Algorithm/build/parameter/input hashes, finite values, unit conversions, tolerance rationale and deterministic reproduction. | Reject invalid output; do not round across a threshold or use snapshot outputs as their own oracle. |
| SC-10 Source independence | Shared ancestry and common processing are recorded; corroboration claims use truly distinct evidence where required. | Downgrade corroboration/confidence; related NASADEM/SRTM agreement is not independent replication. |
| SC-11 Independent experiment check | Applicable route constraints are recomputed independently, including continuous traversal, masks, tasks/return, unique exposure and resource assumptions. | Preserve FAIL/INCONCLUSIVE. Solver success is not verifier success; search caps are not proof of infeasibility. |
| SC-12 Challenge resolution | Every material critic issue has a linked repair/recomputed result or a visible restriction on dependent claims. | Block challenged positive claim; honest limited/negative output may still be published. |
| SC-13 Discovery and controls | Search extent, nomination origin, reference-list membership, tuning versus held-out controls and mission sensitivity are recorded. | Describe only the demonstrated search result; no “world first” or independently validated discovery assertion. |
| SC-14 Mode and validation level | synthetic/replay/live is immutable; S0–S4 level is backed by actual executed validation receipts. | Reject mode laundering and invented validation. Replay of real data remains replay. |
| SC-15 Claim and export consistency | Public statement, matrix, confidence, limitations, denominator, history and manifest agree with the audited evidence. | Reject inconsistent recommendation/export; no hidden failed mandatory row or flight-readiness assertion. |

The registry defines applicability and consequences. Numerical cutoffs belong in observable-specific versioned scientific policy, not in a universal hidden “credibility score”. Before a rule can support PASS, its policy specifies units, support, valid coverage denominator/minimum, comparison and uncertainty treatment, threshold inclusivity, permitted proxy, applicable gates and exact limitations. Freeze its hash with the run. If a policy is missing, return UNKNOWN with remediation; do not invent a convenient cutoff.

## 4. Non-negotiable evidence limits

- Broad DEM terrain can support only metrics at adequate declared support. It cannot demonstrate wheel-scale obstacle clearance, bearing strength, traction, autonomous navigation or successful sample collection. Those require appropriate additional measurements or physical tests. A declared rover capability is not observed performance.
- Earth test energy uses Earth gravity. Rolling resistance, drivetrain efficiency, roughness, speed, idle/task power and reserve assumptions carry their source and calibration status. A sensitivity envelope is not a calibrated confidence interval. An accepted nominal model may be reported within its modeled scope; unmeasured coefficients do not prove actual reserve.
- Planetary regional context and Earth route feasibility are separate findings. Publish comparison only at compatible quantity/support. Fine Earth data cannot create missing planetary detail.
- Natural Earth site selection cannot reproduce lunar/Martian gravity, vacuum or every radiation condition. Preserve GAP and any engineered-simulation requirement. A portfolio cannot join separate places into one continuous traversal or satisfy a co-located requirement by adding unrelated sites.
- Absent mineral/thermal retrievals and absent compatible target/Earth evidence remain UNKNOWN. Missing coverage is not a measured absence. A failed provider request is not terrain FAIL.
- A “new candidate” may mean NOT_IN_REFERENCE_LIST within a declared search and versioned reference set. Publish that bounded statement and its evidence. Establishing global historical novelty is outside the baseline.

Use the concrete product handling and scale checks in08–12. This document does not replace source-label inspection with nominal product names or authorize invented real-source fixtures.

## 5. Uncertainty and confidence implementation

Persist three distinct things: numerical measurement uncertainty when justified, sensitivity to accepted model parameters, and qualitative evidence strength using11's rubric. A HIGH/MEDIUM/LOW label is not a probability or statistical confidence interval. Record `UNASSESSED` when the rubric has not been evaluated. Never manufacture ± values from product resolution or source NUM counts.

For a maximum-limit rule, the chosen policy must state whether a supported uncertainty interval must stay below the limit. If it straddles the boundary, it cannot earn a robust pass. If only a nominal modeled comparison is permitted under11, retain the unquantified uncertainty and use a qualified nominal statement. Do not silently promote it to physical validation. Analogous explicit rules apply to minimum exposure and reserve thresholds.

Run policy-defined sensitivity to support/window, masks, threshold boundaries, accepted energy parameters and justified spatial perturbations. Preserve both conclusions and changed conclusions. Report sensitivity where the recommendation is fragile. If no justified perturbation/error model exists, report that limitation instead of inventing one. Freeze tolerances before looking at a desired demo outcome.

## 6. Audit persistence and API contract

The report uses the existing evidence/artifact system: `EvidenceRecord.kind=DERIVED`, `algorithm_id=scientific-assurance`, `algorithm_version=1.0`, `artifact_media_type=application/json`, and a content-addressed artifact validating against the assurance schema. Its `input_evidence_ids` are all actually consulted upstream evidence/assumption/critique records. Each claim has the subset it uses. Never include the assurance record as its own parent.

The artifact pins the snapshot digest, mission/rover content hashes, dataset policy, acquired manifest, algorithm lock and assurance policy. The snapshot digest covers input/result/critique selections before adding this audit/passport; exclude generated audit/passport pointers to avoid a hash cycle. Source lock and final acquired manifest remain separate. Outer EvidenceRecord owns the byte hash; the report does not self-hash.

Every final `AnalogPassport` has required `assurance_evidence_id`, also present in its `evidence_ids`. It resolves to this report in the same workspace/run/mode and is included in the canonical manifest. Retrieve through the existing `/evidence/{id}` and authorized `/artifacts/{sha256}` endpoints; no competing API is needed. Draft previews explicitly expose incomplete assurance. The pure renderer port includes the resolved report and all referenced display data in `PassportExportBundle`; it performs no DB/network lookup.

Audit publication decisions are ALLOWED, LIMITED and BLOCKED. They describe whether this specific report can be issued truthfully, not whether a mission succeeded. ALLOWED can contain a scientifically supported FAIL. LIMITED can contain visible UNKNOWN/GAP or nominal/proxy restrictions. BLOCKED means an integrity defect, unsupported included claim or contradictory report must be fixed. A report containing an essential unknown cannot make a blanket positive mission recommendation.

Return `SCIENTIFIC_CLAIM_REJECTED` for a synchronous claim/publication policy violation, retaining structured issue codes and evidence IDs. Existing asynchronous202 responses stay202; subsequent receipts/events report the rejection without a passport-created event. A rejected proposal may have a diagnostic audit, but cannot become a published final passport. Review can accept a disclosed assumption; it cannot waive bad checksums, unsupported claims, failed constraints or missing independent verification.

## 7. Validation and release evidence

Implement every case in [the shared credibility gate](../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Keep independent analytic expectations, verified-source replay, actual source acquisition, live model behavior and physical validation separate. Real source release evidence requires actual analyzed Earth, Moon and Mars assets with labels, checksums, masks and derived metrics; a URL catalog, a successful login or a synthetic raster named after NASA does not satisfy it.

Use positive controls and negative controls selected before tuning. Freeze a tuning set and a held-out set in the scenario manifest with dataset/mission hashes and expected qualitative behavior. Do not tune thresholds on the held-out result, duplicate related sources across a claimed independent split, or choose only visually convincing regions. Report the finite coverage and selection limitations. The product should change shortlist/ranking when accepted mission requirements materially change, for documented reasons rather than a hardcoded scenario name.

A useful local demo may show a fully disclosed synthetic regression and a separate real-data investigation. Label both. The real-data outcome is allowed to be FAIL or INCONCLUSIVE. A fail→replan→pass narrative is demonstrated by the canonical computed synthetic graph; never force real terrain into that sequence, relax a requirement, or discard a failed attempt to fit the pitch.

Before a release or final merge claim, create `scientific-validation-report.json` using the shared template. It includes exact tested commit/locks, actual checks/receipts and unrun gates. Assertions about S3/S4 cannot be made unless corresponding real analysis/independent modeled experiment ran. Missing external credentials may limit release scope; they cannot turn an unrun gate green. Scientific integrity tests and honest UI/export propagation are mandatory even for an offline build.

## 8. Completion criteria

The implementation is complete only when: gates execute in backend code; required audits persist; schema/client contracts agree; the actual science engine supplies traceable measurements; an independent verifier catches corrupted solver claims; a material critic challenge changes allowed conclusions; UI/exports preserve the same limitations; and the combined app rejects the adversarial cases. Written warnings alone do not satisfy these requirements.

Team responsibilities: [Tanush backend enforcement](../team%20guides/Tanush/07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md), [Ayan scientific evidence](../team%20guides/Ayan/07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md), [Aradhya truthful presentation](../team%20guides/Aradhya/07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md). Shared contract revision C1 records this addition before any app code exists. All three branches must implement the same C1 contracts.
