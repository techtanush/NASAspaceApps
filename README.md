# AnalogForge local team workspace

This repository contains the complete AnalogForge architecture and the work assignments for Tanush, Ayan and Aradhya. The application has not been implemented yet. Three local Git branches and isolated working copies let the three people build the same application without sharing an editable checkout.

| Person | Branch | Responsibility | Start here |
| --- | --- | --- | --- |
| Tanush | `tanush/platform-agents-integration` | Backend, persistence, jobs, Agent Council, API contracts, final integration | [Tanush guide](team%20guides/Tanush/README.md) |
| Ayan | `ayan/science-data-verification` | Dataset adapters, planetary/Earth terrain, qualification algorithms, routes, energy, verification, portfolios | [Ayan guide](team%20guides/Ayan/README.md) |
| Aradhya | `aradhya/frontend-experience` | Web interface, maps, generated API client, evidence/test interactions, passport renderer and browser validation | [Aradhya guide](team%20guides/Aradhya/README.md) |

The root checkout stays on `main`. Directories `Tanush/`, `Ayan/` and `Aradhya/` are local Git worktrees on the named branches. Each contains the full architecture and all team guides. Work on application code inside **your own worktree's `analogforge/` directory**. Your personal directory is an actual checkout, not a second independent copy of the project to paste into main.

On another computer, clone the local transfer bundle described in [team coordination](team%20coordination/README.md). Worktree `.git` files point to this computer; copying just a worktree folder is not a portable repository transfer.

Read [architecture](architecture%20files/README.md) for product/science authority and [team coordination](team%20coordination/README.md) for ownership, interfaces, foundation handoff, merge order and acceptance. Each coding agent starts with its person's `CODING-AGENT-PROMPT.md`, not the unrestricted whole-app prompt alone.

No GitHub repository, remote, deployment, live credentials, application code or external account is created by this planning setup. All three implementation branches start from one committed shared specification. Integration gates, rather than last-minute copying, produce the final app.
