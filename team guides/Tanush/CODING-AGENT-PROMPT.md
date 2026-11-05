# Tanush coding agent task

You are implementing Tanush's part of AnalogForge on `tanush/platform-agents-integration`. Confirm your working directory is the Tanush checkout before changing files. Build under `analogforge/`. Work as one coding agent; do not spawn subagents or message other chats/people through tools unless the human later explicitly authorizes it.

Read your README and01–06 guides, shared coordination01–04, and the architecture reading map. Original architecture defines the full product; your guide narrows your coding ownership to backend/platform/agents/integration. The architecture's whole-app prompt is context, not permission to overwrite Ayan's science or Aradhya's frontend/renderer.

Deliver F0 first: locked Python/native environment, Postgres/API/worker boot, shared domain/OpenAPI, ScienceService/passport ports, scenario IDs, mode/identity/artifact/cancellation context and reproducible commands. Produce a tested commit for main so teammates can merge it. They may work independently on pure modules/fixtures while you do this.

Continue implementing durable mission drafts/preparation/acceptance, rover revisions, immutable runs, idempotency/revision guards, artifacts/evidence/lineage, leases/fencing/cancellation, committed events and SSE, all required read/action endpoints, ten strict Agent Council roles, one server model adapter, registered tools, policy commits and passport/export services. Call Ayan's scientific facade and Aradhya's pure renderer through shared typed interfaces. Do not duplicate their implementations. Missing modules are explicit dependencies, with test doubles restricted to tests.

Preserve scientific honesty: no model-created measurements, no fake NASA fixtures, no silent live→synthetic fallback, no threshold relaxation to force a pass, no coarse terrain claim of physical clearance/navigation. Missing information is UNKNOWN; natural-site physical impossibility is GAP; bounded route search can be INCONCLUSIVE. A completed investigation can have a failed or limited recommendation.

Use only owned files per the registry. You own common contracts/locks/migrations; coordinate changes through actual versioned requests and consumer checks. Preserve other work and secrets. Existing coding-assistant configuration stays as the user configured it. Product API key/model/source access follows architecture20/21; never search unrelated projects for keys or invent account access.

Follow your implementation plan to completion and run your test gate. Then integrate exact tested teammate checkpoints on isolated integration candidate branches/worktrees, execute the actual combined app/science/UI tests, and advance main only to a passing tested candidate. Do not deploy, create GitHub resources, send messages or operate hardware as part of this local task.

Maintain `team handoffs/tanush/implementation-status.md` and per-checkpoint report JSON using the common template. Include exact SHAs, baseline, schema/port hashes, commands/results, actual live/source tests and blockers. Continue useful independent work if credentials are absent. End only when your owned responsibilities and applicable integration gates are complete, or a precise external dependency truly prevents remaining work; never report unrun live gates as passed.

Mandatory scientific credibility work: implement [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md), architecture33 and shared credibility gate06. Run the assigned SCI tests; preserve all SC gate evidence. Do not report scientific readiness from a build, fixture shape or agent agreement. Contract baseline is C1; include the required passport assurance pointer and consumer support.
