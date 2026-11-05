# Three-person parallel build coordination

One application, three branches, three coding agents working **in parallel, each from one prompt**, then one **merging agent** fuses them. This folder defines ownership, the shared frozen contract kit, runtime isolation and how the pieces meet. The product and science live in `architecture files/`; read [34](../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md) and [35](../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md) first.

## What the project is

AnalogForge — NASA Space Apps Challenge 2026, *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*. A mission-conditioned qualification workbench: Mission Fingerprint → target characterization → Earth candidate discovery → requirement-by-requirement qualification (PASS/PARTIAL/FAIL/GAP/UNKNOWN) → **PROVE IT** (deterministic, independently verified route/energy/exposure experiment with diagnosis and bounded replanning) → Analog Passport (HTML/JSON/CSV). Everything is built and rehearsed on synthetic practice data now; the single missing piece is the NASA dataset, which plugs into a prepared slot at the hackathon ([36](../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md), [37](../architecture%20files/37-HACKATHON-DAY-RUNBOOK.md)).

## Who does what

| Person | Branch | Start here | Builds |
| --- | --- | --- | --- |
| Tanush | `tanush/platform-agents-integration` | [team guides/Tanush/README.md](../team%20guides/Tanush/README.md) | FastAPI backend, PostgreSQL/PostGIS persistence, durable jobs/leases/events, Agent Council (10 roles), tool registrar, policy + scientific assurance, passport assembly/export service, config/compose/Make/CLI, dataset CLI |
| Ayan | `ayan/science-data-verification` | [team guides/Ayan/README.md](../team%20guides/Ayan/README.md) | The `ScienceService` facade: ingestion, terrain/qualification/compatibility math, route search + independent verifier, portfolio, display layers, practice-data generators, live source adapters |
| Aradhya | `aradhya/frontend-experience` | [team guides/Aradhya/README.md](../team%20guides/Aradhya/README.md) | React workbench, generated client, MapLibre + planetary panel, accessible UI, SSE controller, pure passport renderer, Playwright suites |
| Merging agent | `merging-branch` | `merging guide/README.md` on that branch | Purity checks of each branch, wiring, combined tests, browser clicks, release candidate |

## The one-shot workflow

1. **Each person clones their branch** (or uses a worktree), opens a coding agent (Claude Code or Codex) and pastes **only** `team guides/<Name>/CODING-AGENT-PROMPT.md`. The agent runs unattended until its guide's *definition of done* is met, using subagents inside its owned paths as it sees fit.
2. The agent's **first command** materializes the frozen contract kit; its **last commands** are the self-audit, the gate suite and `kit --verify`. It commits and pushes its branch with a filled `STATUS.json`.
3. When all three report `ready_to_merge`, the merging agent (one prompt: `merging guide/MERGING-AGENT-PROMPT.md`) verifies each branch, merges in the fixed order, wires seams, runs combined suites and browser journeys, and produces the release candidate.
4. At the hackathon, only the dataset is added ([37](../architecture%20files/37-HACKATHON-DAY-RUNBOOK.md)).

## Documents

| File | Content |
| --- | --- |
| [01 Ownership and contract freeze](01-OWNERSHIP-AND-CONTRACT-FREEZE.md) | Who may edit which path; the kit; shared files |
| [02 Integration and merge playbook](02-INTEGRATION-AND-MERGE-PLAYBOOK.md) | Checkpoints and the summary of the merge procedure |
| [03 Service boundaries](03-SERVICE-BOUNDARIES.md) | Platform/science/renderer/frontend seams in brief |
| [04 Local run and data isolation](04-LOCAL-RUN-AND-DATA-ISOLATION.md) | Profiles, ports, databases, credentials |
| [05 Parallel one-shot execution plan](05-PARALLEL-ONE-SHOT-EXECUTION-PLAN.md) | Internal phase gates each agent follows; no human hand-offs mid-build |
| [06 Scientific credibility and release gate](06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md) | SC gates, SCI-01…SCI-18 |
| `contracts/ownership.json` | Machine-readable ownership + kit rules |
| `scripts/check_branch_ownership.py` | Changed-path checker (kit-aware) |
| `scripts/validate_team_setup.py` | Guide/baseline integrity validator |
| `scripts/refresh_baseline.py` | Rewrites `architecture-baseline.json` after a recorded architecture change |
| `templates/` | Handoff, contract-change and scientific-validation templates |

## Rules that never bend

* Own paths only; kit files byte-identical; no force-push; no history rewriting; no secrets committed.
* A gate that was not executed is not passed. A test is never weakened, skipped or special-cased to turn a gate green.
* Truthful negative results are valid outcomes. Synthetic data is never labeled NASA; live never silently falls back.
* If something blocks you: implement everything that is independent, record the exact blocker in `STATUS.json`, and finish. Do not stop at the first obstacle and do not invent a workaround that changes a contract.
