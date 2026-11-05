# AnalogForge — NASA Space Apps 2026 team repository

**Challenge:** *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars.*
**Product:** AnalogForge, a mission-conditioned Earth-analog qualification and test-design workbench: Mission Fingerprint → planetary target characterization → Earth candidate discovery → requirement-by-requirement qualification (PASS / PARTIAL / FAIL / GAP / UNKNOWN) → **PROVE IT** (deterministic, independently verified route/energy/exposure experiment with diagnosis and bounded replanning) → Analog Passport (HTML/JSON/CSV). *A place can look like Mars and still be useless for the test; AnalogForge checks the test, not the resemblance.*

The application is **not implemented yet**: this repository contains the complete specification, a frozen contract kit, and one-shot build guides for three parallel coding agents plus a merging guide. Everything except the NASA-provided dataset is built and rehearsed on synthetic practice data; the dataset plugs into a prepared slot at the hackathon.

## Branches and who runs them

| Branch | Person | Start here | Result |
| --- | --- | --- | --- |
| `tanush/platform-agents-integration` | Tanush | [team guides/Tanush/README.md](team%20guides/Tanush/README.md) | Backend, persistence, jobs, Agent Council, policy/assurance, API, config/compose, passport assembly |
| `ayan/science-data-verification` | Ayan | [team guides/Ayan/README.md](team%20guides/Ayan/README.md) | Scientific library behind the `ScienceService` port, dataset slot, route verifier, generators |
| `aradhya/frontend-experience` | Aradhya | [team guides/Aradhya/README.md](team%20guides/Aradhya/README.md) | React workbench, maps, mock backend, pure passport renderer, browser journeys |
| `merging-branch` | merging agent | `merging guide/README.md` on that branch | Purity checks, wiring, combined tests, release candidate |
| `main` | — | this README | Shared specification and guides |

Each person clones their branch and pastes **one prompt** (`team guides/<Name>/CODING-AGENT-PROMPT.md`) into Claude Code or Codex. The agent runs unattended (with subagents as needed) until its definition of done, then pushes with a filled `STATUS.json`. When all three are ready, the merging agent (one prompt) fuses them.

## Read order

1. [architecture files/README.md](architecture%20files/README.md) — product and science specification (documents 00–33).
2. [34 One-shot build profile and errata](architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md) (overrides 00–33 where they conflict) and [35 Frozen contract kit and seams](architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md).
3. [36 Dataset plug-in](architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md), [37 Hackathon-day runbook](architecture%20files/37-HACKATHON-DAY-RUNBOOK.md), [38 Keys and local setup](architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md), [39 Acceptance catalog](architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md), [40 Practice scenarios](architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md).
4. [team coordination/README.md](team%20coordination/README.md) and [team guides/COMMON-BUILDER-PROTOCOL.md](team%20guides/COMMON-BUILDER-PROTOCOL.md).

## Keys needed (summary; details in [38](architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md))

None to build or run synthetic mode. For `live` mode: an OpenAI API key and an explicit model id (`OPENAI_API_KEY`, `OPENAI_MODEL`). Earthdata token only for optional network downloads. No NASA API key, map key or sponsor credentials.

## Validation

```bash
python3 "architecture files/contracts/validate_blueprint.py"          # specification integrity (needs jsonschema, referencing)
python3 "team coordination/scripts/validate_team_setup.py"            # guide/baseline integrity
python3 "architecture files/contracts/kit/materialize.py" --verify    # after materializing into analogforge/
```

These validate planning artifacts only; they certify no application behavior, real data, live model access or physical rover performance.
