# Tanush — platform, agents, policy and integration

**Branch:** `tanush/platform-agents-integration` · **Agent:** Claude Code or Codex · **Result:** the application skeleton everything plugs into: FastAPI + PostgreSQL/PostGIS + durable worker + Agent Council + policy/assurance + passport assembly/export + CLI/Compose/Make.

You own every durable boundary: settings, identity, accepted mission/rover records, runs, jobs, evidence registration, tools/roles, policy, public HTTP and operations. Ayan's science and Aradhya's UI/renderer plug into the seams you consume through **entry points** (`analogforge.science.facade:create_science_service`, `analogforge.rendering.passport:create_passport_renderer`). You never implement science or UI; you test against typed doubles that live only under `tests/`.

## How to run this branch in one session

1. Clone the repo, check out `tanush/platform-agents-integration`.
2. Open Claude Code or Codex and paste **only** [CODING-AGENT-PROMPT.md](CODING-AGENT-PROMPT.md).
3. Leave it running; it follows [COMMON-BUILDER-PROTOCOL](../COMMON-BUILDER-PROTOCOL.md), builds to your [definition of done](06-HANDOFF-CHECKLIST.md), self-audits, pushes and prints a summary.

## Files in this guide

| File | Purpose |
| --- | --- |
| [CODING-AGENT-PROMPT.md](CODING-AGENT-PROMPT.md) | The single prompt |
| [01-SCOPE-AND-FILE-OWNERSHIP.md](01-SCOPE-AND-FILE-OWNERSHIP.md) | What you own and must not touch |
| [02-IMPLEMENTATION-PLAN.md](02-IMPLEMENTATION-PLAN.md) | Phases with exit gates |
| [03-ARCHITECTURE-READING-MAP.md](03-ARCHITECTURE-READING-MAP.md) | What to read, when |
| [04-SERVICE-INTERFACES-AND-HANDOFFS.md](04-SERVICE-INTERFACES-AND-HANDOFFS.md) | Your seams |
| [05-TEST-AND-MERGE-GATES.md](05-TEST-AND-MERGE-GATES.md) | Exact commands, tests, thresholds |
| [06-HANDOFF-CHECKLIST.md](06-HANDOFF-CHECKLIST.md) | Definition of done |
| [07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) | C1 backend enforcement |
| [08-MODULE-SPECIFICATION.md](08-MODULE-SPECIFICATION.md) | **File-by-file specification** |
| [09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md](09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md) | Adversarial self-review and mutation checks |
| [STATUS-TEMPLATE.json](STATUS-TEMPLATE.json) | Report you fill |

Authoritative context: [architecture 34](../../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md), [35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md), [36](../../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md), [38](../../architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md), [39](../../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md), [40](../../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md).
