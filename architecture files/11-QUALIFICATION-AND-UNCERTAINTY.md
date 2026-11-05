# Requirement qualification, uncertainty, and scientific claims

Qualification answers whether a site supplies a condition needed for an accepted mission test. Rover compatibility and proposed-route verification are separate results. Read [05-DOMAIN-MODEL-AND-CONTRACTS.md](05-DOMAIN-MODEL-AND-CONTRACTS.md), [10](10-TERRAIN-AND-PLANETARY-COMPARISON.md), and [12](12-ROUTE-ENERGY-AND-VERIFICATION.md) together. Agents propose interpretations; the deterministic policy engine commits statuses.

## 1. Requirement contract

Each requirement needs a stable ID, human explanation, dimension, mandatory/optional priority, accepted revision, observable, units, operator, threshold/range, required spatial/temporal support, evidence scope, minimum valid coverage, permitted proxy types, success criterion, uncertainty decision rule, and reproducibility class. The public `Requirement` wire object uses the exact fields in `contracts/domain.schema.json`; extended gate settings live in a versioned policy artifact bound through the qualification's `rule_id`/`rule_version` and evidence parameters, with accepted assumptions recorded in the mission contract. Do not add undeclared wire fields. A natural-language sentence alone cannot be marked PASS.

Example requirement concepts:

```text
R_SLOPE_EXPOSURE:
  measured_quantity: unique route distance in surface-slope band
  band: [12,18] degrees, lower inclusive, upper inclusive at final band
  threshold: >= 100 m
  evidence_scope: terrain_model
  source_scale: selected Earth DEM and derivative support
  continuity: same route with required tasks and return
R_CLEARANCE:
  measured_quantity: obstacle height relative to rover underbody clearance
  evidence_scope: field_validation
  required_support: appropriate surveyed geometry and rover footprint
```

These examples are not accepted mission thresholds. They become executable only after a user accepts a full mission revision. If scale, comparison rule, or success threshold is absent, the Requirements Agent requests clarification or proposes explicit assumptions for review. The engine returns `REQUIREMENT_UNDERSPECIFIED` and cannot compute a final qualification.

## 2. Evidence adequacy precedes numerical comparison

For each requirement, run an ordered gate sequence:

1. Verify requirement revision and source lineage match the run.
2. Determine whether site selection can physically reproduce the requested condition. A natural-site lunar gravity or vacuum requirement becomes `GAP` with a physical explanation and facility/simulation recommendation.
3. Verify observable identity, body, units, datum/frame, spatial support, temporal support, acquisition relevance, valid-area coverage, and approved proxy policy.
4. Verify evidence mode and integrity. A live qualification cannot consume synthetic measurements.
5. Calculate the deterministic metric/comparison and uncertainty range.
6. Apply the accepted status decision rule.
7. Persist metric evidence, gate outcomes, limitations, policy version, and a concise explanation template. The model may improve readability but cannot change these facts.

Insufficient data and physical impossibility are different. `UNKNOWN` means more appropriate evidence might resolve the question; `GAP` means natural Earth site selection cannot directly supply the required planetary condition. A lack of Diviner data is never a thermal GAP by itself.

## 3. Exact state meanings

| State | Required basis | Examples |
|---|---|---|
| `PASS` | Adequate accepted evidence meets the defined criterion under the selected uncertainty rule | Required modeled slope exposure exists and an accepted route independently verifies it |
| `PARTIAL` | Explicitly defined subcondition/proxy is supported, but the full condition is not | Adequate regional terrain proxy exists while finer target support is unavailable |
| `FAIL` | Adequate evidence establishes the criterion is not met at the stated scope | Verified route reaches only 60 m of a required 100 m exposure |
| `GAP` | Condition cannot be directly reproduced by natural site selection | Lunar gravity for a physical mobility experiment |
| `UNKNOWN` | Evidence is missing, incompatible, insufficient, or the decision straddles a threshold without an accepted probabilistic rule | NASADEM used to request 20 cm obstacle clearance |

`PARTIAL` must name exactly which subcondition is supported and the residual. It is not a euphemism for low confidence or missing evidence. A supported proxy can justify PARTIAL only when the contract permits it; otherwise the original requirement remains UNKNOWN and the proxy appears as contextual evidence.

Preliminary site availability and route-dependent sufficiency are separate claims. A terrain histogram may support an availability row before route design. A requirement that includes continuity cannot become final PASS until the route is verified. Store `evaluation_stage` and display "preliminary" until that gate completes.

## 4. Interval decision policy

Use intervals only when their derivation is defensible. For a lower-bound requirement `x >= T`, a conservative interval `[L,U]` yields PASS when `L >= T`, FAIL when `U < T`, and UNKNOWN when it straddles T. For `x <= T`, PASS when `U <= T`, FAIL when `L > T`, otherwise UNKNOWN. For an acceptable range `[A,B]`, PASS requires the whole evidence interval inside; a disjoint interval fails; overlap without containment is UNKNOWN unless the contract explicitly defines partial coverage.

If no quantitative uncertainty model exists, do not fabricate an interval. A deterministic nominal metric may support `terrain_model` conclusions with a plainly stated "uncertainty not quantified" limitation if that scope and rule were accepted. It cannot be described as a high-confidence field prediction. Physical hardware claims requiring calibrated uncertainty remain UNKNOWN until supported.

For route energy, compute nominal and conservative scenarios using accepted parameter bounds. The reserve gate uses conservative consumption. Unknown rolling resistance cannot be fixed by picking a favorable number after a failing route. A new calibrated parameter revision invalidates dependent results and requires a new benchmark analysis.

## 5. Confidence representation

Return structured confidence dimensions, not one invented probability:

```text
source_quality: documented | mixed | unsupported
scale_match: direct | permitted_proxy | incompatible
coverage: sufficient | partial | missing
temporal_match: applicable | limited | incompatible | not_applicable
uncertainty: quantified | bounded_sensitivity | not_quantified
independence: independent | shared_source | not_assessed
limitations: issue-code list
```

The wire summary `confidence` uses `HIGH`, `MEDIUM`, `LOW`, or `UNASSESSED` exactly as specified in the shared schema. HIGH requires documented compatible evidence, sufficient coverage, applicable timing, no unresolved blocking issue, and uncertainty adequate for the accepted decision scope. MEDIUM permits declared model sensitivity or an accepted proxy with explicit limitations. LOW flags supported but strongly limited context; it does not authorize PASS on an inadequately evidenced criterion. UNASSESSED is used before review. The detailed rubric is stored in the comparison evidence artifact. These labels are not probabilities of mission success. Models cannot set confidence based on writing fluency or familiarity with a famous analog.

Spatial bootstrap or perturbation ensembles are allowed as sensitivity tools only with declared error correlation, source support, distribution assumptions, seeds, and limitations. Do not add independent Gaussian noise to every resampled pixel and call the result calibrated uncertainty. Bootstrap over meaningful spatial blocks, not individual correlated pixels. Without adequate source-error information, report model sensitivity rather than a statistical confidence interval.

## 6. Qualification matrix and coverage

Produce one row per requirement per candidate. Each row includes status, evaluation stage, metric and units, criterion, measured/support scale, valid coverage, evidence IDs, proxy type, confidence rubric, limitations, critic issues, and next evidence action. Persist `reason_code` values such as `MEETS_CRITERION`, `INSUFFICIENT_EXPOSURE`, `SCALE_UNSUPPORTED`, `TARGET_EVIDENCE_MISSING`, `EARTH_EVIDENCE_MISSING`, `TEMPORAL_MISMATCH`, `PHYSICAL_GAP`, and `THRESHOLD_UNRESOLVED`.

The mission may show coverage summaries, but always expose denominators:

```text
strict_coverage = sum(weight_i * I(status_i==PASS)) / sum(weight_i for reproducible requirements)
```

GAP requirements are excluded from reproducible coverage only when a separate gap count/weight is shown. UNKNOWN remains in the denominator so missing data cannot improve the score. A separate optional planned-coverage measure may credit explicit PARTIAL fractions only if those fractions are contract-defined; arbitrary `PARTIAL=0.5` is forbidden. Coverage is coverage of requirements, not percent resemblance to a world.

If any mandatory reproducible requirement is FAIL or UNKNOWN, the passport cannot state that the entire mission is qualified. If all reproducible mandatory requirements pass but physical gaps remain, say "qualified for the listed Earth-test requirements; residual planetary gaps remain." An accepted terrain-model benchmark can PASS while hardware clearance remains UNKNOWN; both must appear together.

## 7. Rover compatibility

Compare capability fields against explicit task needs: maximum surface slope at the modeled scale, battery and reserve, supported task/instrument capabilities, modeled route duration, and source-supported physical obstacle constraints. Lack of a required instrument is `FAIL` when the profile explicitly excludes it; a missing instrument field is `UNKNOWN`, not absence. Maximum slope is a user/manufacturer profile assumption until calibrated.

Navigation sensors make a task eligible to be proposed; they do not prove autonomous navigation performance from terrain raster analysis. Geological sampling capability permits a sampling task; it does not prove collectible material exists at the waypoint. A field-test readiness recommendation must preserve these distinctions.

## 8. Critic and revisions

The critic receives the matrix, source/scale table, requirement contract, model assumptions, and relevant evidence. It emits structured issues with requirement/evidence IDs, severity, defect code, and requested action. Typical blocking codes are `SCALE_MISMATCH`, `UNSUPPORTED_PROXY`, `PROVENANCE_MISSING`, `FALSE_NOVELTY`, `ROUTE_NOT_VERIFIED`, and `UNJUSTIFIED_THRESHOLD`.

Policy automatically downgrades affected claims when a blocking issue is substantiated. The critic does not directly write a new metric. Resolving an issue means obtaining evidence, fixing a transformation and recomputing, narrowing a claim to its accepted scope, or explicitly retaining UNKNOWN/GAP. A mandatory physical requirement cannot be removed merely because it spoils a successful demo.

All recomputation creates new qualification revisions. The accepted mission and rover remain immutable within a run. Threshold changes require a new user-accepted mission revision and new run under [00](00-ARCHITECTURE-DECISIONS.md).

## 9. Acceptance criteria

Test all five statuses independently and threshold equality boundaries. Test missing data versus physical gap, permitted versus forbidden proxy, direct versus coarse-scale slope, nominal versus conservative energy, preliminary availability versus verified continuity, and explicit versus unknown rover capabilities. A fabricated citation, unresolved evidence ID, incompatible mode, or unsupported clearance PASS must be rejected by policy even when proposed by an agent.

Mandatory acceptance: the same target with terrain and thermal mission contracts produces different evidence requests and different qualification coverage when supported data differ. Missing thermal data must produce UNKNOWN rather than an unchanged terrain-driven recommendation disguised as a thermal result. Scientific evaluation cases are detailed in [29](29-SCIENTIFIC-VALIDATION.md).
