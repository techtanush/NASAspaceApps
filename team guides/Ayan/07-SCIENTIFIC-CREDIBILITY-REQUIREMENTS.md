# Ayan: scientific evidence and independent checks

Mandatory references: [architecture33](../../architecture%20files/33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md), [shared credibility gate](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md), architecture08–13/26/29, [gate registry](../../architecture%20files/contracts/scientific-gates.json) and the shared ScienceService boundary. Your deliverable is computed evidence and tests, not a collection of plausible claims.

## S0 scientific adequacy and policy

For each implemented observable create a versioned policy under your owned algorithm config. Specify measured quantity/units, valid bodies/frames/vertical reference, native/effective support, derivative window, coverage denominator/minimum, quality mask, temporal support, threshold inclusivity, uncertainty/nominal decision rule, allowed proxy and accepted-assumption requirements. Missing policy/evidence returns UNKNOWN. Do not invent one universal coverage percentage or confidence score for all science.

Expose typed policy/adequacy results through Tanush's F0/C1 ports, with all consulted source/assumption local evidence keys, algorithm/parameter hashes, gate evidence, measured values, coverage, scale and limitations. Request missing port fields rather than editing shared schemas or returning untyped JSON. Tanush registers real UUIDs and executes the overall audit; you implement the scientific gates/metrics.

Use independent analytic oracles and property checks from29. Freeze tolerances with physical/numerical reasons before demo tuning. A snapshot of your own current output is regression coverage, not independent validation. Source uncertainty, sensitivity envelopes and qualitative evidence strength remain distinct. Do not infer uncertainty from resolution or treat related products as independent measurements.

## S1 actual sources and inference limits

Validate actual approved bytes/labels, checksum/length/type, product version, body/frame/units/scaling, temporal semantics, quality mask and support. Preserve source lineage and exact transformations. Reprojection/resampling cannot upgrade native information; fine display pixels cannot prove wheel-scale clearance or traction. Never fill invalid cells with zero for derivatives or route feasibility. Reject unknown vertical interpretation and Moon/Mars treated as Earth.

Keep absent mineral/thermal evidence UNKNOWN. Natural gravity/vacuum mismatch remains GAP. Earth energy uses Earth gravity and disclosed calibration/parameter assumptions; model-estimated reserve is not physically demonstrated reserve. Provide policy-defined sensitivity and identify threshold-fragile conclusions. If you cannot justify a numerical error distribution, say so and use only the allowed nominal-model scope from11.

Independent verification must reload authoritative grids/constraints and recompute route traversal, masks/corners, slope, length, tasks/return, unique exposure and energy. It cannot trust the searcher's cached totals or “found” flag. Share correct low-level primitives if needed, but use independently structured traversal/check logic and analytic oracles that catch shared mistakes. Budget exhaustion is INCONCLUSIVE. Only an exhaustive exact declared-model search can establish model infeasibility.

## Controls and bounded discovery

Version the reference set and search bounds. Record seed/metadata/generated nomination origin and NOT_IN_REFERENCE_LIST membership. That label does not establish historical global novelty. Select positive, negative and mission-change controls before tuning; keep tuning and held-out sets distinct with locked source/mission hashes. Report actual computed reasons for changed rankings, and source ancestry/leakage limits. Do not select a convenient region solely because it supports the pitch.

Provide a small real-source manifest for Earth/Moon/Mars with actual downloaded/decoded checksums and reproduced observables. Replay is replay; source decoding alone is S2, not S3 comparison or S4 modeled experiment. Real terrain need not pass or show a fail→pass sequence. Preserve its true outcome. The canonical graph separately demonstrates the synthetic repair path with exact known arithmetic.

## Tests and handoff

Own SCI-01–10/14/17 scientific tests and support combined critic/claim/export cases. Implement in your owned science unit/property/integration/replay paths and keep existing commands. Include bad checksum, wrong units/frame/scaling, coarse-clearance/upscale, nodata route, denominator tampering, missing retrievals, uncertain boundary, source dependence, corrupted verifier inputs and exhausted search. Report precise test paths/results and which source probes actually ran.

At handoff supply algorithm/policy hashes, coverage/uncertainty/support semantics, independent expected values/tolerances, per-gate evidence and observed limitations to Tanush. Supply Aradhya representative supported/limited/unknown/failed rows with exact display meanings. Contribute actual source/control/verification receipts to [the scientific validation report](../../team%20coordination/templates/scientific-validation-report.template.json). Missing credentials or coverage remain explicit blockers, never fabricated NASA fixtures. A complete science branch must run without importing FastAPI, DB or model clients.

## Concrete mapping to this branch (one-shot build)

* The science-owned gate evidence (SC-02…SC-11, SC-13) is produced by `COMPARE_REQUIREMENT` (`adequacy`) and `AUDIT_EVIDENCE` per `08` §4.7 and §4.15. The platform adds SC-01, SC-12, SC-14, SC-15 and decides publication.
* SCI tests you own (primary): SCI-01 (checksum/lineage via dataset validation), SCI-02 (frame/scale), SCI-03 (clearance from coarse/upsampled terrain stays UNKNOWN), SCI-04 (nodata stripe on a route), SCI-05 (optional layers), SCI-06 (interval/nominal wording), SCI-07 (Earth gravity only), SCI-08 (NASADEM/SRTM shared ancestry flagged), SCI-09 (falsified solver totals, budget ≠ infeasible), SCI-10 (canonical graph), SCI-14 (bounded novelty, negative control, mission sensitivity), SCI-17 (reproducibility). Each must exist as a named test in the files of `05` §2 and be listed in `STATUS.json.sci_tests`.
* Policy hashes: `config/algorithms.yaml` is hashed by the platform; changing a tolerance or threshold changes the audit identity — never edit it to rescue a result.
