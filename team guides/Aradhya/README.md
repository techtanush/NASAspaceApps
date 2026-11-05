# Aradhya interface maps and passport branch

Your branch is `aradhya/frontend-experience`. Your local checkout is `Aradhya/`. Give Codex the [coding agent prompt](CODING-AGENT-PROMPT.md) and implement the interface, generated client and pure passport renderer under that checkout's `analogforge/`.

Your job is a working mission-test workbench, not a presentation with hardcoded scientific results. Tanush supplies the real API/Agent Council/persistence; Ayan supplies scientific evidence, route outputs and display layers. The frontend must make their distinctions and limitations understandable.

Follow [scope](01-SCOPE-AND-FILE-OWNERSHIP.md), [implementation sequence](02-IMPLEMENTATION-PLAN.md), [architecture map](03-ARCHITECTURE-READING-MAP.md), [interfaces](04-SERVICE-INTERFACES-AND-HANDOFFS.md), [tests/merge gates](05-TEST-AND-MERGE-GATES.md) and [handoff checklist](06-HANDOFF-CHECKLIST.md).

Start against the supplied C0 OpenAPI with a **visibly mocked development preview** while F0 is prepared. Deliver U0 early. Once the real backend is available, disable mocks explicitly and connect the same components/client to persisted data. Never silently return mock PASS when a real request fails.

References: [architecture](../../architecture%20files/README.md), [team rules](../../team%20coordination/README.md), [service boundary](../../team%20coordination/03-SERVICE-BOUNDARIES.md), [ownership](../../team%20coordination/contracts/ownership.json). Reports and requests go under `team handoffs/aradhya/`.
