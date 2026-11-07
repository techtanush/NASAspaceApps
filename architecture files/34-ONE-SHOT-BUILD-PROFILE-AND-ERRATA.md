# One-shot build profile, completion tiers and errata

This document is binding. It sits **above** documents 00–33 wherever they conflict (it resolves the conflicts it lists) and defines what "finished" means for the pre-hackathon build. Read it immediately after [00](00-ARCHITECTURE-DECISIONS.md) and before any module work.

## 1. What is being built, for whom, and why

**Challenge track.** NASA Space Apps Challenge 2026: *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars.* Teams use open Earth, Moon and Mars data to identify and characterize terrestrial analogs and present them as a map, visualization or other tool.

**Product.** AnalogForge: a mission-conditioned analog **qualification and test-design** workbench. Given a Moon/Mars mission test and a rover profile it (1) turns intent into a Mission Fingerprint of measurable requirements, (2) characterizes the planetary target, (3) discovers and qualifies Earth candidate regions requirement-by-requirement with PASS / PARTIAL / FAIL / GAP / UNKNOWN and explicit evidence scale, (4) runs **PROVE IT**: a deterministic route/energy/exposure experiment independently verified, diagnosed and bounded-replanned, and (5) exports an evidence-backed **Analog Passport** (HTML/JSON/CSV). One-line message: *a place can look like Mars and still be useless for the test; AnalogForge checks the test, not the resemblance.*

**Team split.** Three people, three branches, three coding agents working in parallel, each given **one prompt**:

| Person | Branch | Agent | Owns |
| --- | --- | --- | --- |
| Tanush | `tanush/platform-agents-integration` | Claude Code or Codex | Backend, persistence, jobs, Agent Council, policy/assurance, API, config/compose, passport assembly |
| Ayan | `ayan/science-data-verification` | Claude Code or Codex | All scientific computation, dataset ingestion, routing/energy/verifier, display layers |
| Aradhya | `aradhya/frontend-experience` | Claude Code or Codex | React workbench, generated client, maps, pure passport renderer, browser tests |

A fourth session (the **merging agent**, branch `merging-branch`, guide in `merging guide/`) fuses the three finished branches, proves each is pure, wires the seams, and runs the combined browser tests.

## 2. The three completion tiers

| Tier | When | Content | Data |
| --- | --- | --- | --- |
| **P — pre-hackathon build (this work)** | Now | The **entire** application, offline-complete and merged: all screens, 10 agent roles, all 15 science operations, durable jobs, assurance, exports, security, recovery. Runs end-to-end in `synthetic` mode and in `local-dataset-practice` mode against practice rasters dropped in through the exact slot NASA data will use. Live adapters (Earthdata/PDS/EMIT/Diviner) and live OpenAI orchestration are fully coded and tested against recorded fixtures/stubs. | Synthetic only. **No NASA granule is required.** |
| **H — hackathon day** | At the event | Operator drops the NASA-provided product(s) into `analogforge/data/incoming/<dataset_id>/`, writes one `manifest.yaml` per product ([36](36-DATASET-PLUG-IN-AND-NASA-SLOT.md)), runs the documented bind/validate/lock commands, runs the live scenario. Target effort: minutes of operator work plus one short agent session to resolve format surprises ([37](37-HACKATHON-DAY-RUNBOOK.md)). | The missing "last Lego piece". |
| **R — rehearsal evidence** | Before H | Rehearse tier H with a *mock NASA drop* (synthetic rasters in a different format and layout) so the slot is proven, not assumed ([39](39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) §5). | Synthetic |

**Nothing may be left for tier H except supplying data and its manifest.** If a feature needs data to exist before it can be built, it is specified with a synthetic equivalent in [40](40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) and must be completed against that equivalent in tier P.

### What "complete" means in tier P (applies to every branch)

A branch is complete only when **all** hold, with observed evidence in its status report:

1. Every file in the branch guide's *deliverable manifest* (`08-MODULE-SPECIFICATION.md`) exists and is non-trivially implemented (no `pass` bodies, `NotImplementedError`, `TODO`, `FIXME`, `HACK` strings in owned production code).
2. The frozen contract kit is materialized and `materialize.py --verify` passes ([35](35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)).
3. Every test listed in the branch's `05-TEST-AND-MERGE-GATES.md` exists, runs, and passes; none is skipped, xfailed or deleted. Tests needing an unavailable external service are *marked* with the documented marker and have an offline equivalent that runs.
4. The branch's self-audit (`09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md`) passes, including mutation checks that prove the tests can fail.
5. `STATUS.json` (from `STATUS-TEMPLATE.json`) is filled with real commands, exit codes, counts and commit SHA; `ready_to_merge` is true only when every gate above is true.
6. The work is committed and pushed to the branch.

"Done" is never "it compiles", "the unit tests I wrote pass", or "the UI looks right".

## 3. Errata and precedence rulings

Each ruling applies everywhere; where a numbered document says otherwise, this table wins.

| ID | Conflict found | Ruling |
| --- | --- | --- |
| E-01 | [17](17-FRONTEND-COMPONENTS-AND-STATE.md) shows `frontend/src/` and `api/generated`; [04](04-REPOSITORY-AND-DEPENDENCIES.md) shows `apps/web/src/...`. | Frontend root is `analogforge/apps/web/`. Generated client lives in `apps/web/src/generated/`. Substitute paths from 17 accordingly. |
| E-02 | Budgets are repeated in 14, 21, 23, 24, 26 with small differences. | The single source of truth is `analogforge.ports.catalog.BUDGETS` (from the kit). Documents describing the same budget are explanatory. |
| E-03 | "3 replans" vs "two route repairs and one candidate switch". | Both are true: `replans_total = 3` is the **sum** of ≤2 same-candidate route repairs and ≤1 candidate switch. A fourth attempt is never permitted; terminal state is `BUILDING_PASSPORT` with the last supported result. |
| E-04 | [12](12-ROUTE-ENERGY-AND-VERIFICATION.md) describes search generically; the Test Designer role names four strategies without semantics. | Strategy semantics are fixed by the kit type `RouteStrategy` (comments there are normative). `WAYPOINT_RETURN` is the **default first proposal**: it enforces only hard constraints. Unique-exposure requirements are enforced by the independent verifier, so a promising-looking site can genuinely FAIL its first attempt and the diagnosis → replan loop is computed, not scripted. |
| E-05 | [12](12-ROUTE-ENERGY-AND-VERIFICATION.md) §9 and SCI-10 quote 340 m / 34 Wh as "the repaired route". | `S,B,C,W1,W2,W1,C,B,S` (340 m, 34 Wh, 150 m, PASS) remains the **supplied-route verifier oracle**. The minimum-distance **search** with `EXPOSURE_COVERAGE` returns `S,A,W1,W2,W1,C,B,S` (230 m, 30 Wh, 150 m, PASS; lexicographic tie-break). Both PASS. SCI-10 is satisfied by: attempt 1 = 120 m / 26 Wh / 0 m FAIL, attempt 2 = PASS with ≥100 m unique exposure; the verifier oracle test uses 340 m. Exact values: `catalog.GRAPH_EXPECTED`. |
| E-06 | [06](06-DATABASE-AND-STORAGE.md)/[05](05-DOMAIN-MODEL-AND-CONTRACTS.md) make `EvidenceRecord.run_id` required, but dataset acceptance happens before any run. | Operator-time dataset validation produces a **dataset lock file** (no DB row). The platform re-executes `INGEST_LOCAL_DATASET` (hash-cached) inside the run when the dataset is first used and registers SOURCE evidence under that run. |
| E-07 | Candidates are UUID rows in the platform and anonymous windows in science. | Science identifies candidates by stable string `window_id` (`CandidateRef.window_id`); the platform maps `window_id ↔ candidate UUID` and never lets a UUID reach pure science code. Practice candidate **name** = `"Practice " + window_id`. |
| E-08 | `TestResult` requires an outcome, but a search with no route has no route to verify. | When `SEARCH_ROUTE` returns `EXHAUSTIVE_INFEASIBLE`, `BUDGET_EXHAUSTED`, `NOT_RUN` or `ERROR`, the platform constructs the `TestResult` from the search payload per the 12 §7 table; for `EXHAUSTIVE_INFEASIBLE` the **category is assigned by `DIAGNOSE_RESULT`** (`ANALOG` vs `ROVER`, rule in 40 §6). `VERIFY_ROUTE` is only invoked on an actual route. |
| E-09 | [11](11-QUALIFICATION-AND-UNCERTAINTY.md) requires continuity rows to be "preliminary" before PROVE IT but gives no status. | Before verification, rows for route-dependent requirements (`R-EXPOSURE`, `R-TASKS`, `R-RESERVE` and any requirement with a `co_location_group` and `evidence_scope=terrain_model` whose observable derives from a route) are `UNKNOWN`, `reason_code=ROUTE_NOT_VERIFIED`, `evaluation_stage=PRELIMINARY`. After verification they become `PASS/FAIL` with `evaluation_stage=FINAL`. A pending (not-yet-computed) row is a distinct UI state `PENDING`, never a status. |
| E-10 | 43 API operations are specified; dataset registration is needed but unspecified. | The 43 operations are **frozen** (no additions). Dataset registration is an operator **CLI** (`analogforge datasets …`), not HTTP. `GET /capabilities` and `GET /configuration/scenarios/{id}` report dataset-lock and scenario availability. |
| E-11 | `examples/.env.example` and the kit's `.env.example` differ. | The kit's `.env.example` (adds profile ports) is canonical. |
| E-12 | The brief's rover example has `ground_clearance_m: 0.22`. | Baseline ARES-1 uses **0.20** (decision register); uploaded profiles always govern. `max_obstacle_height_m` stays `null` for ARES-1. |
| E-13 | 04 pins Python 3.12; the sandbox may have 3.13. | `requires-python = ">=3.12,<3.14"`. Develop and CI on 3.12; 3.13 must also pass imports. |
| E-14 | Earlier personal guides forbade subagents. | **Superseded.** Coding agents *may and should* use subagents/parallel workers inside their own owned paths for independent modules and for adversarial review, under the single-writer-per-file rule in each branch guide. Spawning agents never relaxes ownership, the kit freeze, or the test gates. |
| E-15 | 04 requires an `rtk` prefix "in this user's environment". | Use `rtk` only if the binary exists; otherwise run the identical command. Every command in the guides is valid without `rtk`. |
| E-16 | 20 implies Earthdata tokens are needed for live work. | A **file-drop dataset needs no network and no token.** `EARTHDATA_TOKEN` is needed only for the optional network adapters (`earthdata`, `pds`). |
| E-17 | Root README describes per-person local worktrees. | Each person simply **clones their own branch**. Worktrees are an optional convenience. |
| E-18 | Doc 26 says `make test-live` exists; live gates cannot run without credentials. | `make test-live` must exist, must `SKIP` with a printed reason when credentials are absent, and its result is reported as `BLOCKED_EXTERNAL`, never `PASSED`. |
| E-19 | [18](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) §7–§8 give *proposed* tokens, fonts ("system fonts") and layout; they are not specific enough to guarantee a professional result. | [41](41-FRONTEND-DESIGN-SYSTEM-AND-PROFESSIONAL-UI-STANDARD.md) is binding for all visual design: tokens (`team guides/Aradhya/design/tokens.json`, verified contrast), self-hosted Inter + IBM Plex Mono (not system fonts, no CDN), shell layout, components, copy voice and the banned-"slop" list. 18 keeps authority over map/layer **behavior**. |

If you discover another contradiction while building: do not silently pick a side. Record it in your `STATUS.json.contradictions_found` with the files, the choice you made, and the reasoning, and continue. The merging agent reconciles the list.

## 4. Behaviors that every agent must treat as release-blocking defects

These repeat the scientific rules in [29](29-SCIENTIFIC-VALIDATION.md)/[33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) in the form coding agents most often violate them:

1. Writing a function that returns a fixed PASS/FAIL (or fixed numbers) for the practice scenario instead of computing it. Practice outcomes must emerge from the raster/graph computation; tests must also pass on a *perturbed* fixture where the answer changes.
2. Relaxing a requirement, rover limit, reserve, or tolerance to obtain a pass.
3. Letting an unknown (`null`) become `0`, `NaN`, `false`, or an empty list that is displayed as a result.
4. Treating a missing optional dataset as absence/FAIL, or as success.
5. Mixing modes (synthetic data labeled NASA; replay presented as live; live silently falling back to scripted roles).
6. Computing qualification, energy, slope or exposure in the browser, or in the platform's policy layer.
7. A UI control with no real endpoint, a mock response in production mode, or a hidden mock fallback.
8. Editing frozen kit files or another person's owned paths.
9. Weakening, skipping, deleting or special-casing a test to make a gate green.
10. Reporting a gate as passed that was not executed.

## 5. Pre-hackathon "no missing piece" checklist

When tiers P and R are complete, the following must be demonstrably true (the merging agent verifies each; [37](37-HACKATHON-DAY-RUNBOOK.md) assumes them):

- `analogforge datasets validate` accepts a manifest + a raster in each of: GeoTIFF/COG, HGT, GDAL-readable PDS3/PDS4 `.img/.lbl|.xml`, NetCDF, ASCII grid — and rejects, with a named reason, a dataset missing CRS, body, units, nodata, or vertical reference.
- A live scenario (`live-hackathon-v1`) exists, reports `AWAITING_DATASETS` until bound, and runs the identical code path as `local-dataset-practice-v1` once bound.
- Everything that is not data (map, passport, agents, assurance, keys, preflight, Compose, tests) is exercised with practice data and passes the same gates it will pass with NASA data.
- The operator can tell, from `analogforge preflight --scenario live-hackathon-v1`, exactly which of {dataset files, manifest fields, `OPENAI_API_KEY`, `OPENAI_MODEL`} is still missing.
