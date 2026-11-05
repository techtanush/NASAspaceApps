# AnalogForge local team workspace

This repository contains the complete AnalogForge architecture and the work assignments for Tanush, Ayan and Aradhya. The application has not been implemented yet. Three local Git branches and isolated working copies let the three people build the same application without sharing an editable checkout.

| Person | Branch | Responsibility | Start here |
| --- | --- | --- | --- |
| Tanush | `tanush/platform-agents-integration` | Backend, persistence, jobs, Agent Council, API contracts, final integration | [Tanush guide](team%20guides/Tanush/README.md) |
| Ayan | `ayan/science-data-verification` | Dataset adapters, planetary/Earth terrain, qualification algorithms, routes, energy, verification, portfolios | [Ayan guide](team%20guides/Ayan/README.md) |
| Aradhya | `aradhya/frontend-experience` | Web interface, maps, generated API client, evidence/test interactions, passport renderer and browser validation | [Aradhya guide](team%20guides/Aradhya/README.md) |

The root checkout stays on `main`. Directories `Tanush/`, `Ayan/` and `Aradhya/` are local Git worktrees on the named branches. Each contains the full architecture and all team guides. Work on application code inside **your own worktree's `analogforge/` directory**. Your personal directory is an actual checkout, not a second independent copy of the project to paste into main.

On another computer, clone [techtanush/NASAspaceApps](https://github.com/techtanush/NASAspaceApps), then select your branch from the table. For example, Ayan can start directly with:

```bash
rtk proxy git clone --branch ayan/science-data-verification https://github.com/techtanush/NASAspaceApps.git
```

Tanush and Aradhya use their respective branch names. Open the cloned repository root and follow `team guides/<YourName>/README.md`; the nested person worktrees described above are specific to this original computer. A clone of your branch is already an isolated checkout. The local transfer bundle remains an offline alternative described in [team coordination](team%20coordination/README.md). Copying just a worktree folder is not a portable repository transfer.

Read [architecture](architecture%20files/README.md) for product/science authority and [team coordination](team%20coordination/README.md) for ownership, interfaces, foundation handoff, merge order and acceptance. Each coding agent starts with its person's `CODING-AGENT-PROMPT.md`, not the unrestricted whole-app prompt alone.

GitHub stores the shared architecture and three implementation branches; the app will still run locally. All branches start from the same committed C1 specification with their individual scope, implementation plan and merge gates under `team guides/`. This repository currently contains planning artifacts and validators. App implementation, live credentials and deployment remain future work.

Scientific credibility is now a binding C1 implementation/merge requirement: [architecture33](architecture%20files/33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md), [shared release gate](team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md) and each person's07 guide specify backend enforcement, scientific evidence and truthful UI/exports. Planning validation does not establish implemented scientific capability.
