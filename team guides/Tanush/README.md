# Tanush platform agents and integration branch

Your branch is `tanush/platform-agents-integration`. Your local checkout is the top-level `Tanush/` folder. Implement the application under that checkout's `analogforge/`. You own the backend and final assembly; Ayan supplies scientific modules and Aradhya supplies the interface and passport renderer.

Give your coding agent [CODING AGENT PROMPT](CODING-AGENT-PROMPT.md). Then follow [scope](01-SCOPE-AND-FILE-OWNERSHIP.md), [build plan](02-IMPLEMENTATION-PLAN.md), [architecture reading map](03-ARCHITECTURE-READING-MAP.md), [handoffs](04-SERVICE-INTERFACES-AND-HANDOFFS.md), [tests/merge gates](05-TEST-AND-MERGE-GATES.md) and [completion checklist](06-HANDOFF-CHECKLIST.md).

Your first deliverable is F0: a runnable backend foundation, stable typed ports/contracts, dependency locks and local launch profiles. Ship that early so the other two can connect to real services. Your final deliverable is a coherent locally runnable app with persisted evidence, all ten roles, scientific tools, UI and truthful reports.

Do not implement a second terrain/route engine while waiting for Ayan. Do not build a competing frontend while waiting for Aradhya. Use explicit typed test doubles in platform tests, label incomplete capability, and replace them at integration. Only you advance main, using isolated tested merge candidates.

The full architecture remains at [architecture README](../../architecture%20files/README.md). Team collaboration rules are at [coordination README](../../team%20coordination/README.md). Exact ownership rules are in [ownership registry](../../team%20coordination/contracts/ownership.json). Report status in `team handoffs/tanush/`, not by editing the other people's files.

Before implementing scientific results, read the mandatory [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md). It assigns your concrete backend/science/presentation responsibilities and shared adversarial merge tests under contract C1.
