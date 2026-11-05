# Three person build coordination

This is the division of one application across three branches. Tanush owns the platform and its final assembly, Ayan owns scientific computation, and Aradhya owns the user experience. Existing architecture files remain the product/scientific specification. These team files define ownership, dependency order and delivery boundaries without changing scientific requirements.

## Local working copies

The repository root is the integration checkout on `main`. The sibling directories below it are isolated worktrees:

```text
NASA space apps/                     main, integration checkout
  architecture files/               original full blueprint
  team coordination/                shared collaboration contracts
  team guides/{Tanush,Ayan,Aradhya}/  personal instructions
  Tanush/                           tanush/platform-agents-integration
    architecture files/             complete Git snapshot
    team guides/Tanush/              Tanush instructions
    analogforge/                    future application code
  Ayan/                             ayan/science-data-verification
    architecture files/
    team guides/Ayan/
    analogforge/
  Aradhya/                          aradhya/frontend-experience
    architecture files/
    team guides/Aradhya/
    analogforge/
```

Do not edit the root application while an agent is implementing in a person worktree. Do not launch three coding agents in one editable checkout. A branch name alone does not isolate filesystem writes; the worktrees do. Shared Git objects/refs are expected; files and runtime state must stay separate.

## Start sequence

1. Each person opens their named worktree, reads its own guide and gives the coding agent its `CODING-AGENT-PROMPT.md`.
2. Everyone reads the [ownership/freeze rules](01-OWNERSHIP-AND-CONTRACT-FREEZE.md), [service boundaries](03-SERVICE-BOUNDARIES.md) and [runtime isolation](04-LOCAL-RUN-AND-DATA-ISOLATION.md).
3. Tanush ships the small F0 foundation first. Ayan starts pure science fixtures; Aradhya starts frontend against the supplied OpenAPI/MSW fixtures. Neither needs to wait idle for the API.
4. Tanush integrates F0 into main. Ayan and Aradhya merge that accepted main checkpoint into their own branches. They do not overwrite their current code with a downloaded directory.
5. Integrate the scientific tool layer and interface early, then iterate with the [merge playbook](02-INTEGRATION-AND-MERGE-PLAYBOOK.md). Final merge readiness requires all applicable per-person and combined tests.

The [48 hour schedule](05-48-HOUR-EXECUTION-SCHEDULE.md) is a suggested order of checkpoints. It is not permission to fabricate a PASS or describe incomplete live dependencies as completed.

## Local transfer between computers

`analogforge-team.bundle` at the repository root is an offline Git transfer artifact created after the shared baseline/branches. It contains committed history and all branches; it excludes ignored data and secrets. Copy the bundle using the team's chosen transfer method. No network account is required to create or clone it.

On a teammate's computer, use the bundle's actual path and a new empty destination:

```bash
rtk proxy git clone "/path/to/analogforge-team.bundle" "analogforge-team"
```

Inside that clone, Ayan selects `ayan/science-data-verification` and Aradhya selects `aradhya/frontend-experience`. A clone normally creates remote-tracking branches from the bundle; `rtk git branch -a` confirms the actual state. If the local branch is absent, create it tracking its matching `origin/...` branch. The resulting origin points to a **bundle file**, not a writable GitHub repository. Do not tell an agent to push changes there.

To transfer a completed feature back, create a new bundle from the contributor clone containing that feature branch. Tanush fetches it into an import reference and follows the exact merge process in02. The original planning bundle is a baseline snapshot; it does not automatically update when later work is committed. Do not transfer `.env` or raw downloaded datasets through Git bundles.

## Documents and tools

- [Ownership and contract freeze](01-OWNERSHIP-AND-CONTRACT-FREEZE.md)
- [Integration and merge playbook](02-INTEGRATION-AND-MERGE-PLAYBOOK.md)
- [Service boundaries](03-SERVICE-BOUNDARIES.md)
- [Runtime isolation](04-LOCAL-RUN-AND-DATA-ISOLATION.md)
- [Schedule](05-48-HOUR-EXECUTION-SCHEDULE.md)
- [Ownership registry](contracts/ownership.json)
- [Handoff template](templates/handoff-report.json)
- [Contract change template](templates/contract-change-request.json)
- [Setup validator](scripts/validate_team_setup.py)
- [Changed-path ownership checker](scripts/check_branch_ownership.py)

No subagents were used to prepare these team assignments. Runtime Agent Council roles are part of the future product, a separate concept from coding-agent delegation during this setup task.
