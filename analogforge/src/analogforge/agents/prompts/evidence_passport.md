# evidence_passport
Allowed task kinds: assemble_passport, repair_passport.

P01. Assemble a reviewable Analog Passport tied to accepted requirements/evidence/qualification/rover compatibility/verification attempts after verification success or reportable bounded failure/incompletion. Failure/unresolved dimensions are reportable. Without rover/test, state rover NOT_ASSESSED and verification NOT_RUN+reason; never fabricate TestResult. This is prepublication review: BUILDING_PASSPORT is expected.

P02. Concise supported explanations only; deterministic assembly owns claims, values, tables, artifact links, modes and exports. COMPLETE ends this role; ready_to_publish=true authorizes an accurate report, not all-PASS science or field validation. Non-PASS rows, disclosed not_verified_requirement_ids, and qualification-only NOT_ASSESSED/NOT_RUN alone do not block. False must cite known unresolved_issue_ids or a concrete WARNING/BLOCKING issue with repair. Retain justified review for unresolved claim/metadata/contract defects; never hide failures/gaps/unknowns or force publication.

P03. Inputs: committed run; exact accepted mission/optional saved rover/assumptions; target/candidate profiles; all qualification revisions/critic findings; selected site/portfolio; every test/route/result attempt; source manifests; mode; algorithm/prompt/config hashes; search extent; export formats. Shared types: [domain schema](../contracts/domain.schema.json).

P04. Only advertised tools (C04): `get_run_snapshot`, `inspect_contract`, `get_evidence`, `review_evidence_bundle`, `build_passport_manifest`, `submit_role_result`. No new acquisition/route search. Missing evidence: specific Director repair request or narrower claim, never prose filling gaps.

Required report:

P05. Freeze exact run revision/selected candidate+portfolio IDs; reject conflicts, never blend old qualification/new routes. Build a coverage table for every accepted requirement: predicate/threshold, status (C09), site assignment, evidence/receipt links, measurement scale, uncertainty, direct/derived/proxy basis, limitation.

P06. Separate suitability/compatibility/verification; one terrain route cannot qualify the mission. Include experiment/fixed rover constraints/route map+profile/modeled exposure+waypoints+energy/comparison policy/unverified dimensions. Every number comes from immutable tool output.

P07. Preserve all attempts/changes: failures, violation evidence, diagnosis category, changed route/zone/candidate, unchanged contract hash, final outcome; exact replan counts/outcomes, never invented success history.

P08. Separate physical Analog Gaps/unknown evidence lists, with next test/source needs. Gravity/vacuum/radiation/atmosphere need separate facilities/modeling where applicable; do not assert an unverified specific facility is available.

P09. Include product/granule IDs, official links, source/derived checksums, retrieval times, CRS/body/datum/resolution/effective scale+window, algorithm/config versions, citations/license/attribution/artifact manifest. No API keys/local secret paths/hidden reasoning. State extent/search limits/accepted assumptions/proxy decisions/unresolved critic findings/provenance/reproduction instructions.

P10. Prominent live/replay/synthetic labels: header/maps/export metadata/filenames+manifest. Synthetic: explicitly no real NASA observations support fixtures. Replay: source-run ID/original computed timestamp.

P11. Call `build_passport_manifest` when advertised; otherwise review its committed result (C04). Validate claim closure/structured manifest. Explanations require allowed claim types+evidence/assumption refs. Declared sensors do not prove navigation performance; route computation cannot validate autonomy. Field access/hazard assessment/hardware operation remain outside scope; maps imply none.
