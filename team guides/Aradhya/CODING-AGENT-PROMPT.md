# Aradhya coding-agent prompt (paste this and nothing else)

```text
You are Aradhya's coding agent for AnalogForge (NASA Space Apps 2026: "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars").
Your branch is aradhya/frontend-experience. You will work unattended, for as many hours and with as many subagents as needed, until your
definition of done is met. Nobody is available to answer questions: make the conservative choice consistent with the architecture and record it.

FIRST, verify you are in the repository root on branch aradhya/frontend-experience (git branch --show-current). If not, check it out.
THEN read, completely and in this order:
  1. team guides/COMMON-BUILDER-PROTOCOL.md        (how you work, forbidden shortcuts, git, subagents, resume, final steps)
  2. team guides/Aradhya/README.md and 01 .. 09 and STATUS-TEMPLATE.json   (what you build; 08 is the file-by-file specification)
  3. architecture files/41 (THE DESIGN STANDARD: you must make this look like a professional mission-operations console, not generic/AI-template UI; read it completely) and team guides/Aradhya/10-DESIGN-SYSTEM-AND-VISUAL-QA.md and team guides/Aradhya/design/*
  3b. architecture files/34, 35, 39, 40              (precedence/errata, frozen kit and seams incl. section 5b UI-readable artifacts, acceptance catalog, practice storylines)
  4. the architecture documents listed in team guides/Aradhya/03-ARCHITECTURE-READING-MAP.md (16-19 and 07 are essential)
Your FIRST command is: python3 "architecture files/contracts/kit/materialize.py"   (then --verify). The kit is read-only for you.

You build (a) the React 19 + TypeScript workbench in analogforge/apps/web: all screens S01-S12, Earth map (MapLibre, offline basemap) and a separate body-aware
planetary panel, generated API client from the kit's contracts/openapi.bundled.json, TanStack Query state, SSE controller with dedup/resync, accessible UI,
every data-testid of contracts/ui-testids.json; (b) a stateful MSW mock backend (visible MOCK PREVIEW banner, impossible in production builds) that replays the
practice storylines and serves REAL renderer output as mock exports; (c) the pure Python passport renderer analogforge.rendering.passport
(html/json/csv) implementing the kit's PassportRenderer port; (d) Playwright journeys J01-J13 of architecture files/39 section 3 that run in mock mode now and
against the real backend at merge time (same specs). You compute NO scientific value; you display server data and the artifacts of architecture 35 section 5b.

The UI must look like NASA already holds the contract and an astronaut/mission planner uses it today: neutral chrome, colour only for evidence state (always colour+shape+icon+word), dense but rigorous 4 px grid, tabular numerals and units, self-hosted Inter + IBM Plex Mono, no gradients/glass/glow/emoji/hero sections/template look (architecture 41 section 2 lists every banned pattern). Copy design/tokens.json, verify_tokens.py and gen_tokens_css.py as 10 instructs, build a /__styleguide of all components, run the visual audit (UIX-13) and the multi-reviewer design review (DR-01..04).
Build in the phases of team guides/Aradhya/02-IMPLEMENTATION-PLAN.md. Write the catalog tests first (UIX-01..UIX-11) with real assertions. Use subagents for
independent screens/modules and, in the audit phase, adversarial reviewers who try to break the work.

You may NOT: ship placeholder/Lorem/TODO copy, hex colours outside tokens.css, a UI library that imposes its own look, or a design-review score you wrote yourself; edit the kit or any path you do not own; add a scientific enum by hand; compute qualification/energy/slope/exposure in the browser; hide a failed,
unknown or gap row; hardcode a green result; leave a control without real behavior; skip, xfail or weaken a test; claim a gate passed that you did not execute;
commit secrets or generated build output.

You are DONE only when every gate in team guides/Aradhya/05-TEST-AND-MERGE-GATES.md (incl. UIX-12, UIX-13) and the design review of 10 (DR-01..04) passed with executed assertions, 09-SELF-AUDIT... is complete,
`materialize.py --verify` and `team coordination/scripts/check_branch_ownership.py --person aradhya` both PASS, team handoffs/aradhya/STATUS.json is truthful,
and the work is committed and pushed to origin aradhya/frontend-experience. Finish by printing: unmet gates first, passed gates, pushed SHA, and the three
things the merging agent should verify first.
```
