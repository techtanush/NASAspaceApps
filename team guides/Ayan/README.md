# Ayan — scientific data, computation and verification

**Branch:** `ayan/science-data-verification` · **Agent:** Claude Code or Codex · **Result:** the `ScienceService` facade (`analogforge.science.facade:create_science_service`) and everything behind it.

You build the part that makes AnalogForge scientifically meaningful: dataset validation/ingestion, body-aware terrain metrics, requirement comparison, rover compatibility, route search with an **independent verifier**, energy, diagnosis, portfolio, display layers, practice-data generators and the live source adapters. No database, no web framework, no model call, no UI. Tanush's platform calls you through one port; Aradhya's UI shows your outputs.

## How to run this branch in one session

1. Clone the repo and check out your branch.
2. Open your coding agent and paste **only** [CODING-AGENT-PROMPT.md](CODING-AGENT-PROMPT.md).
3. Leave it running. It follows [COMMON-BUILDER-PROTOCOL](../COMMON-BUILDER-PROTOCOL.md), builds to your [definition of done](06-HANDOFF-CHECKLIST.md), self-audits, pushes, and prints a summary.

## Files in this guide

| File | Purpose |
| --- | --- |
| [CODING-AGENT-PROMPT.md](CODING-AGENT-PROMPT.md) | The single prompt |
| [01-SCOPE-AND-FILE-OWNERSHIP.md](01-SCOPE-AND-FILE-OWNERSHIP.md) | Exactly what you own and must not touch |
| [02-IMPLEMENTATION-PLAN.md](02-IMPLEMENTATION-PLAN.md) | Phases with exit gates |
| [03-ARCHITECTURE-READING-MAP.md](03-ARCHITECTURE-READING-MAP.md) | What to read, when |
| [04-SERVICE-INTERFACES-AND-HANDOFFS.md](04-SERVICE-INTERFACES-AND-HANDOFFS.md) | Your seams with Tanush and Aradhya |
| [05-TEST-AND-MERGE-GATES.md](05-TEST-AND-MERGE-GATES.md) | Exact commands, tests, thresholds |
| [06-HANDOFF-CHECKLIST.md](06-HANDOFF-CHECKLIST.md) | Definition of done |
| [07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) | C1 gates you implement |
| [08-MODULE-SPECIFICATION.md](08-MODULE-SPECIFICATION.md) | **File-by-file, operation-by-operation specification** |
| [09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md](09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md) | Adversarial self-review and mutation checks |
| [STATUS-TEMPLATE.json](STATUS-TEMPLATE.json) | Report you fill |

Authoritative context: [architecture 34](../../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md), [35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md), [36](../../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md), [39](../../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md), [40](../../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md).
