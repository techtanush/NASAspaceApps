# Tanush coding-agent prompt (paste this and nothing else)

```text
You are Tanush's coding agent for AnalogForge (NASA Space Apps 2026: "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars").
Your branch is tanush/platform-agents-integration. You will work unattended, for as many hours and with as many subagents as needed, until your
definition of done is met. Nobody is available to answer questions: make the conservative choice consistent with the architecture and record it.

FIRST, verify you are in the repository root on branch tanush/platform-agents-integration (git branch --show-current). If not, check it out.
THEN read, completely and in this order:
  1. team guides/COMMON-BUILDER-PROTOCOL.md        (how you work, forbidden shortcuts, git, subagents, resume, final steps)
  2. team guides/Tanush/README.md and 01 .. 09 and STATUS-TEMPLATE.json   (what you build; 08 is the file-by-file specification)
  3. architecture files/34, 35, 36, 38, 39, 40      (precedence/errata, frozen kit and seams, dataset slot, keys/setup, acceptance catalog, practice scenarios)
  4. the architecture documents listed in team guides/Tanush/03-ARCHITECTURE-READING-MAP.md (03, 05-07, 14, 15, 19-26, 33 are essential)
Your FIRST command is: python3 "architecture files/contracts/kit/materialize.py"   (then --verify). The kit is read-only for you; you own uv.lock.

You build the platform: FastAPI API (all 43 operations of the kit's bundled OpenAPI), PostgreSQL/PostGIS persistence and migrations, durable worker with
leases/fencing/cancellation, the registrar that validates and persists science results, the ten-role Agent Council (scripted provider for synthetic/replay,
OpenAI Responses provider for live), the 21-tool registry, policy, scientific assurance (SC-01..15) and passport assembly/export, CLI, preflight, Compose/Make.
You call science ONLY through the entry point analogforge.science.facade:create_science_service and the renderer ONLY through
analogforge.rendering.passport:create_passport_renderer; you test against typed doubles under tests/support/ (never importable from src/). You compute no
scientific number yourself. Synthetic runs need no keys and no network. Live mode never falls back silently.

Build in the phases of team guides/Tanush/02-IMPLEMENTATION-PLAN.md. Write the catalog tests first (PLT-01..PLT-21 in architecture files/39) with real
assertions. Use subagents for independent modules and, in the audit phase, adversarial reviewers who try to break the work.

You may NOT: edit the kit, architecture files (except by the recorded change process, which you do not use in this build), or any path you do not own;
hardcode practice results; relax any requirement, limit or tolerance; label synthetic data as NASA; skip, xfail or weaken a test; claim a gate passed that
you did not execute; commit secrets or data. If PostgreSQL/PostGIS is unavailable, try every option in architecture files/38 section 4.1 before marking DB rows blocked.

You are DONE only when every gate in team guides/Tanush/05-TEST-AND-MERGE-GATES.md passed with executed assertions, 09-SELF-AUDIT... is complete,
`materialize.py --verify` and `team coordination/scripts/check_branch_ownership.py --person tanush` both PASS, team handoffs/tanush/STATUS.json is truthful,
and the work is committed and pushed to origin tanush/platform-agents-integration. Finish by printing: unmet gates first, passed gates, pushed SHA, and the
three things the merging agent should verify first.
```
