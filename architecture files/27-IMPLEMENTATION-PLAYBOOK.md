# Implementation playbook with completion gates

Execute the whole application in the order below. Each milestone creates working code and an observable gate; do not skip the deterministic core to build agent animations. Continue through independent work when credentials are absent, then report the exact live gates that remain blocked. This playbook is a build order, not a claim that an arbitrary one-pass implementation can bypass unavailable accounts or scientific evidence.

## Step 0 Read and establish the input manifest

Read README,00,01,02,03,05,07,08,12,14,16,20,21,26, and32; then open specialist documents for the modules being implemented. Treat `references/` as retained intent, with00 resolving conflicts. Inventory existing repository files before scaffolding; this workspace was empty when the blueprint was authored. Preserve user changes.

Create `implementation-status.md` containing each milestone, its tests, state, unresolved dependencies and exact commit/build references. Validate the blueprint's JSON/examples first. Resolve conflicting specifications in the decision register before implementing two incompatible interfaces. No hidden TODO may stand in for an accepted behavior.

## Step 1 Scaffold the runnable system

Create the layout in04, lock dependencies, build native-science container and Compose database/API/worker/frontend. Add settings validation, structured errors, health endpoints, logging and local workspace identity. Verify rasterio/pyproj imports in the actual worker image. Implement migrations through jobs/evidence tables before creating business records.

Gate: clean checkout runs health+DB migration; frontend renders application shell; synthetic mode starts with networking disabled; app-local secrets ignored. Deliver Make commands and a short development README.

## Step 2 Implement contracts and durable state

Create Pydantic models from05/domain schema, semantic validators, JCS hashing, repositories/unit-of-work, revision checks, idempotency service and artifact store. Implement mission draft/manual contract revision/acceptance and rover import/revision. Implement RunSnapshot, events, job leases/fencing and cancellation. Export OpenAPI and generate frontend client.

Gate: invalid units/unknown fields rejected; accepted revisions immutable; duplicate create returns same object; concurrent worker claim and stale-token tests pass; event/result publication is atomic; source artifact checksum round trip works. UI uses generated types.

## Step 3 Build analytic science before fetching real data

Implement normalized raster metadata/masks, metric projection, slope, detrended roughness, relief and common-scale comparisons. Create analytic fixtures from26. Implement quantity registry, qualification rules, confidence rubric and gap registry. Implement compatibility with honest unsupported states.

Gate: analytic expected values, support-scale refusal, no-data propagation, body/CRS and gap-vs-unknown tests pass. A synthetic candidate produces a complete requirement matrix solely from deterministic tools.

## Step 4 Build the actual PROVE IT engine

Implement frozen constraints artifact, tasks/waypoints, graph construction, supercover hazard checks, unique exposure, energy accounting, bounded resource-constrained search and independent verifier. Start with the tiny graph fixture, then analytic rasters. Preserve route geometry and per-edge telemetry artifacts. Add failure classification and permitted-repair policy.

Gate: first graph route fails, repaired route passes with unchanged contract; repeated-edge exploit rejected; false solver totals rejected; return/task/energy constraints enforced; search cap gives INCONCLUSIVE; cancellation stops work. Production live mode rejects test-only mock energy provider.

## Step 5 Complete the useful interface using computed synthetic data

Build screen journeys16, state/components17, maps18 and passport19. Implement mission acceptance, rover upload, candidate selection/evidence drawer, matrix, critic issues, compatibility, route/test lab, attempt comparison, review controls and mode badge. SSE reflects committed events; query snapshot remains authoritative. Export printable HTML, JSON and CSV.

Gate: browser end-to-end synthetic flow reaches a hashed passport with both attempts and all gaps; reload/reconnect retains it; keyboard/mobile/WebGL-failure paths work. The interface shows SYNTHETIC throughout. Do not start with real-looking hardcoded NASA statistics.

## Step 6 Add real Earth and planetary data adapters

Implement dataset registry and source access from08/09, real CMR discovery, protected downloader and PDS label decoders. Resolve actual NASADEM/SRTM Earth, MOLA Mars and LOLA Moon assets; lock hashes/versions/CRS/vertical references. Normalize within bounded AOIs. Compare each target with Earth at a valid common scale. Candidate discovery must search bounded tiles/regions, refine promising windows, and distinguish known controls from discovered candidates.

Gate: one real source path for each Earth/Mars/Moon terrain family passes adapter validation and creates evidence. Known-analog recovery/negative-control/mission-sensitivity checks29 recorded. At least one candidate is generated beyond copying the known-site list; label novelty carefully as not in reference list, not a worldwide discovery claim. If access is blocked, finish decoders with replay/synthetic tests but leave live gate pending.

## Step 7 Add controlled live AI orchestration

Read14/15 and each role file. Implement strict schemas, common policy, tool registry, Responses adapter, provider capability probe, invocation budgets, public operation logs and policy-committed transitions. Begin with Requirements preparation and user acceptance, then target/scout/qualification/critic, then test/replanning/passport. Reuse deterministic services from steps3/4; never ask the model to calculate terrain values.

Gate: actual configured model calls approved tools and submits typed results; receipts resolve; critic can trigger a genuine evidence repair; fabricated evidence and prompt injection rejected; fail/replan is based on verifier evidence. Live missing key remains a clear setup blocker; no silent synthetic fallback.

## Step 8 Implement full-vision coverage

Implement no-rover site qualification, optional EMIT and Diviner integration contracts with real quality/coverage states, complementary site optimizer, per-site tests and portfolio export. Include reviewable assumptions and missing-data repairs. Add manual candidate nomination and bounded candidate search expansion. Both planetary target maps are body-aware. Future physical simulator/hardware integrations remain outside baseline.

Gate: composite cases distinguish co-located conditions from separate campaigns; mandatory unknowns prevent overstated qualification; optional layer unavailable behavior is useful and truthful; different objectives change qualification/search priority. A terrain-only final result cannot claim mineral/thermal equivalence.

## Step 9 Reliability security and deployment readiness

Complete hosted identity, CSRF, workspace isolation, download controls, input resource limits, queue fairness, backup/restore, worker crash recovery, SSE proxy behavior and monitoring. Build production images with locks/digests. Run security and recovery tests24/25. Do not deploy or buy external services unless the user requests deployment.

Gate: full offline CI, real-data adapter evidence, live-agent report where authorized credentials exist, production build, restore test, and no unresolved critical issues. Record actual latency/resource measurements rather than claiming targets met.

## Step 10 Final acceptance and handoff

Run every acceptance scenario28 and scientific check29 applicable to the claimed scope. Produce a feature matrix linking product requirement→module→test→observed result. Demonstrate successful, failed, blocked, cancelled and inconclusive runs. Verify exports contain exact input hashes and source lineage. Update implementation status and README with commands and remaining external dependencies.

The final handoff must distinguish implemented software, exercised synthetic behavior, verified real datasets, live AI calls, unsupported physical claims and external setup still required. Never certify a real site or hardware from a simulated test. Keep working on fixable failures; ask a focused question only when an actual user choice/account/accepted scientific assumption is needed.

## Dependency map

Steps1→2→3→4 form the deterministic foundation. Step5 consumes2–4. Step6 can proceed after3 in parallel with interface work. Step7 requires2–4 and stable tool contracts. Step8 requires5–7, and9 hardens all layers. Step10 validates the entire result. Parallelize independent modules only after freezing shared types; one owner reconciles contracts and runs integration checks.
