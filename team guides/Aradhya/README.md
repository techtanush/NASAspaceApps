# Aradhya — interface, maps and passport renderer

**Branch:** `aradhya/frontend-experience` · **Agent:** Claude Code or Codex · **Result:** the React workbench (all screens, maps, SSE, accessible, mock-previewable) and the pure passport renderer (`analogforge.rendering.passport:create_passport_renderer`).

You make the product legible, truthful **and professional**: a mission-test workbench, not a chat window and not a template. It must look like NASA already holds the contract and a mission planner will use it for a six-hour shift tomorrow — [architecture 41](../../architecture%20files/41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md) defines exactly what that means and the visual audit gates enforce it. Every scientific state comes from the server; you display it with its scale, limits and unknowns, and you never compute science. Tanush's API and Ayan's science are not available to you during the build — you develop against the **bundled OpenAPI**, a faithful **stateful mock backend** (visibly bannered), and typed renderer fixtures. The merging agent runs your journeys against the real backend.

## How to run this branch in one session

1. Clone the repo, check out `aradhya/frontend-experience`.
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
| [07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) | Truthful presentation requirements |
| [08-MODULE-SPECIFICATION.md](08-MODULE-SPECIFICATION.md) | **File-by-file specification** |
| [09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md](09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md) | Adversarial self-review and mutation checks |
| [10-DESIGN-SYSTEM-AND-VISUAL-QA.md](10-DESIGN-SYSTEM-AND-VISUAL-QA.md) | **How the product must look: professional mission-console standard, design tokens, visual audit and design review gates** |
| [design/](design/) | `tokens.json` (verified palette), `verify_tokens.py`, `gen_tokens_css.py` |
| [STATUS-TEMPLATE.json](STATUS-TEMPLATE.json) | Report you fill |

Authoritative context: [architecture 34](../../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md), [35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md), [39](../../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md), [40](../../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md), [41 (design standard)](../../architecture%20files/41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md), [16](../../architecture%20files/16-USER-JOURNEYS-AND-SCREENS.md)–[19](../../architecture%20files/19-ANALOG-PASSPORT-AND-EXPORTS.md).
