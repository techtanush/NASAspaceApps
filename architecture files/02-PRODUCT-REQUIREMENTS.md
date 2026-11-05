# Product requirements and completion contract

Read `00-ARCHITECTURE-DECISIONS.md` first. This document specifies the complete functional product. Milestones may deliver progressively, but a prerecorded presentation, a collection of site cards, or one fixed Mars scenario does not satisfy this specification. Requirement identifiers below are stable and must appear in implementation tickets and acceptance reports.

## 1. Product purpose

AnalogForge answers: **Which Earth environment can support this particular Moon or Mars experiment, which conditions remain unrepresented, and can this rover execute a modeled version of that experiment?** Its output is a set of traceable scientific and engineering decisions, not a planetary resemblance percentage.

The primary user is a rover engineer selecting and designing an analog campaign. A planetary scientist examines the evidence and comparison scales. A field planner assembles complementary campaigns. A student or reviewer must be able to understand the final claim without reading agent logs.

Three questions always remain separate:

| Question | Product record | Permitted claim |
|---|---|---|
| Does a site provide the required condition? | Requirement qualification | The measured condition is supported, partly supported, absent, physically unavailable, or unknown. |
| Can this rover undertake the proposed test? | Rover compatibility assessment | Known limits and declared capabilities do or do not satisfy this test under stated assumptions. |
| Does a proposed continuous experiment meet the contract? | Deterministic verification attempt | The tested route meets or violates modeled constraints, or the computation is inconclusive. |

A terrain-qualified site can have an incompatible rover. A compatible rover can have a failed proposed route. An unsuccessful bounded search does not prove that every possible route fails. A completed workflow may honestly conclude no supported recommendation.

## 2. Complete product boundary

**Included:** revisioned mission authoring, manual/JSON rover profiles, Moon and Mars target regions, coarse-to-fine Earth discovery, measured terrain comparisons, approved optional mineral/thermal evidence, qualification, coverage gaps, critic review, test creation, deterministic route verification, diagnosis, bounded replanning, composite portfolios, activity receipts, resumable jobs, and exportable passports. Both worlds must work as data-processing paths, not cosmetic dropdown choices.

**Not part of this release:** hardware control, flight certification, autonomous field deployment, arbitrary CAD interpretation, photorealistic physics, unrestricted global high-resolution processing, automatic legal permission to access land, or proof of centimeter-scale traversability from a coarse DEM. Human field execution is outside the modeled verification boundary.

Further mission types can enter through extensible requirements and capability definitions. Do not ship habitat, EVA, communications, or resource-prospecting presets that imply unsupported tools exist. Show an unsupported requirement explicitly and preserve it as an unresolved condition.

## 3. Functional requirements

### 3.1 Workspace and recoverability

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-001 | Show recent missions and runs with body, mode, pinned revisions, status, updated time, and unresolved blockers. | Opening an existing run reconstructs its workbench from persisted state. |
| PR-002 | Scope every query and artifact to the configured workspace. | A record from another workspace is inaccessible and never appears in cached lists. |
| PR-003 | Autosave editable drafts with a visible saved/saving/conflict/error indicator. | Reloading restores the last server-acknowledged draft; unsaved text is identified, not described as saved. |
| PR-004 | Distinguish a workflow waiting for human review from one blocked by data, configuration, or system failure. | Each state has a reason, allowed next action, and affected requirements. |
| PR-005 | Cancel queued or active investigation without destroying evidence already committed. | The run reaches `CANCELLED`; historical receipts and attempts remain readable. |

### 3.2 Mission authoring and acceptance

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-010 | Accept target body, named or drawn target region, objective, experiment categories, constraints, and priorities. | The saved draft carries explicit planetary geometry metadata and units. |
| PR-011 | Use the Requirements role to propose structured requirements from the user's objective. | Every numeric threshold is sourced to user input, a supported source, or an explicitly labeled proposal. |
| PR-012 | Present a reviewable Mission Fingerprint before freezing a contract. | Every requirement shows stable ID, observable, rule, unit, scale, importance, proposed evidence, and rationale summary. |
| PR-013 | Separate hard constraints from desired exposure and optional objectives. | Rover safe slope is a hard limit; desired slope-band distances remain experiment requirements. |
| PR-014 | Identify physically unavailable natural Earth conditions as `GAP`. | Gravity, vacuum, or planetary atmosphere requirements retain their intended condition and a facility/simulation follow-up; they do not disappear. |
| PR-015 | Reject structurally invalid contracts and flag internally contradictory proposed tests. | A request requiring an unsafe rover exposure cannot be silently accepted as achievable. |
| PR-016 | Require explicit user acceptance of the measurable contract and attached assumptions. | The run references the accepted immutable mission revision and its digest. |
| PR-017 | Editing an accepted mission creates a new draft/revision and a new run when accepted. | Historical run thresholds and outcomes never change in place. |

Missing requirements do not default to zero. Thresholds derived from a target distribution must show the derivation and user review. The UI may suggest a terrain-only investigation when geology is unsupported, but cannot remove geology from an accepted mission to produce success.

### 3.3 Rover connection

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-020 | Provide a structured manual editor and JSON import for the same rover schema. | Valid imports round-trip through the editor without losing supported fields. |
| PR-021 | Validate positive mass, energy, dimensions, sensible angle bounds, reserve range, required units, and enumerated capabilities. | Errors point to the exact field; source text survives validation failure. |
| PR-022 | Show unknown capabilities as unknown rather than false or zero. | Missing obstacle-height capability cannot pass an obstacle requirement. |
| PR-023 | Freeze a rover revision with each run. | Updating a rover profile never changes the assessment of an existing run. |
| PR-024 | Support investigation without a rover and distinguish it from rover verification. | Site qualification works; rover-dependent tests remain unavailable until a new run pins a rover profile. |
| PR-025 | Include a clearly named example ARES-1 profile. | It loads 42 kg, 18° maximum safe slope, 0.20 m clearance, 0.30 m wheels, 1800 Wh, 20% reserve, 0.5 m/s nominal speed, stereo/IMU/LiDAR and stated capabilities. |

ARES-1 is an example specification, not a manufacturer-certified hardware profile. Nominal speed is not automatically a maximum speed. Do not infer maximum obstacle height from clearance or wheel diameter.

### 3.4 Target characterization and Earth discovery

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-030 | Characterize a chosen lunar or Martian region through its approved terrain adapter. | Target evidence includes body, source product, coordinate convention, datum, resolution, extent, no-data fraction and derived measurements. |
| PR-031 | Search a bounded Earth candidate catalog/grid according to mission needs, then investigate promising candidates at the supported comparison scale. | Receipts identify search bounds, coarse exclusions, detailed subset, and reason for stopping. |
| PR-032 | Support Earth regions nominated manually as well as automatically discovered candidates. | Both sources use identical qualification rules; candidate origin remains visible. |
| PR-033 | Include known analog controls and a candidate beyond the known-example list in validation. | A famous site has no privileged `PASS`; new candidate means newly investigated by this run, not a claim of scientific discovery. |
| PR-034 | Show data coverage before making unsupported layer claims. | Missing EMIT/thermal coverage is `UNKNOWN` for affected requirements; other dimensions can continue. |
| PR-035 | Compare terrain features at documented compatible scales. | The same comparison-scale annotation appears on target plots, candidate plots, qualification rows and passport claims. |
| PR-036 | Preserve unsuccessful or filtered candidates with reasons. | Users can inspect why a site was excluded or not investigated further. |

The default search is coarse-to-fine, bounded by a configured compute/data budget. “No candidates found in this search” must include the searched domain and its limits; it cannot mean no candidate exists on Earth.

### 3.5 Qualification and evidence

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-040 | Return one qualification row per accepted requirement per assessed candidate. | Each row contains `PASS`, `PARTIAL`, `FAIL`, `GAP`, or `UNKNOWN`, evidence references, rule, measurements, limitations and evidence strength. |
| PR-041 | Treat uncomputed rows as pending, then unknown where investigation cannot resolve them. | A loading row is never colored as a provisional pass. |
| PR-042 | Expose direct measurement, derived measurement, model estimate, proxy and user assumption separately. | A mineral-context proxy cannot be presented as verified sample composition. |
| PR-043 | Display confidence as dimension-specific evidence strength and uncertainty. | No single “% Mars,” no unlabeled confidence percentage, and no model-generated confidence number is shown. |
| PR-044 | Show every quantitative claim with its unit, scale and evidence receipt. | Clicking the evidence reference opens the persisted tool result and source lineage. |
| PR-045 | Compute states through server policy from deterministic evidence. | Client rendering and language-model prose cannot set qualification outcomes. |
| PR-046 | Distinguish pending analysis, missing evidence, measured absence, incompatible evidence, and physical gaps. | They have different labels/reasons and produce appropriate next actions. |

If a documented numeric uncertainty interval exists, display it with method and units. This is different from inventing an overall confidence score. Coverage counts such as “4 of 6 measurable requirements supported” are acceptable when the denominator, weighting and treatment of partial/unknown/gap rows are explicit. Never turn that count into a planetary similarity label.

### 3.6 Critic and user review

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-050 | Run Scientific Critic review before a final recommendation or test authorization. | Challenges reference exact requirement/evidence IDs and machine-readable reasons. |
| PR-051 | Allow challenges to reopen investigation or invalidate a previous assessment. | The UI shows old and new assessment revisions and the evidence difference. |
| PR-052 | Surface unresolved critical challenges as blockers. | A polished recommendation cannot hide a missing required source or scale mismatch. |
| PR-053 | Offer a concrete review decision where user acceptance is needed. | The user sees accepted experiment criteria and the exact proposed new assumption/proxy, affected test/evidence, unresolved limitations and consequences before accepting. |
| PR-054 | Record accepted assumptions without converting them to observations. | A user-accepted proxy stays labeled proxy in every downstream artifact. |

User acceptance cannot transform missing scientific evidence into a measured `PASS`, override an impossible natural condition, or mutate a frozen threshold. It may authorize a limited modeled experiment with explicit unresolved dimensions.

### 3.7 Rover compatibility and PROVE IT

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-060 | Compare rover limits/capabilities against the selected site and proposed test. | The result separates slope, energy, declared task capability, terrain-scale limits and unknown clearance. |
| PR-061 | Before the first `PROVE IT`, show a benchmark preview from the accepted contract and rover. That action starts test design and deterministic verification within those frozen criteria; generated artifacts expose route region, base, waypoints, exposures, tasks, forbidden regions and energy assumptions. | Required inputs and existing approvals are committed before starting; design pauses for review only if a new material assumption/proxy requires acceptance, rather than requiring a nonexistent predesigned route. |
| PR-062 | Execute terrain/route verification deterministically in the worker. | Every result resolves to route geometry, sampled measurements, constraint residuals, tool version and evidence digest. |
| PR-063 | Check continuity, exposure, rover hard limits, required waypoint/task access, return condition and energy reserve as separate benchmarks. | A green aggregate badge cannot hide a failed hard constraint or inconclusive required benchmark. |
| PR-064 | Present `PASS`, `FAIL`, or `INCONCLUSIVE` using server policy. | Search exhaustion and missing data are shown as inconclusive where appropriate. |
| PR-065 | Label the activity as modeled terrain-feasibility verification. | Map animation does not imply physical rover execution, wheel contact or validated autonomous navigation. |
| PR-066 | Preserve every attempt and all failures. | An eventual pass links to prior failures and contains an exact change list. |

The phrase “sampling access” means modeled route access to supported waypoints. It does not prove drilling, grasping, sample integrity or the presence of a particular mineral unless separate evidence and task tools support those claims. Sensor declarations do not constitute observed navigation performance.

### 3.8 Diagnosis, replanning and composites

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-070 | Classify failure as `ROUTE`, `ROVER`, `ANALOG`, `DATA`, `REQUIREMENT`, `SEARCH_LIMIT`, or `SYSTEM`. | The diagnosis cites failed constraints and supports the claimed scope of failure. |
| PR-071 | Attempt bounded repairs of route, test zone or candidate within accepted requirements. | Each attempt has a parent, budget, changed fields, unchanged contract digest and independent result. |
| PR-072 | Stop at configured retry/compute limits and explain remaining options. | It is possible to finish honestly without a pass. |
| PR-073 | Require a new user-accepted mission/rover revision for changes to requirements or rover specifications. | No automatic relaxation of slope exposure, reserve or safe limits. |
| PR-074 | Propose complementary sites when no single candidate provides sufficient coverage. | A portfolio maps each requirement to responsible site(s) and lists residual gaps/unknowns. |
| PR-075 | Keep co-located requirements together. | A continuous route cannot be assembled from slope segments in different countries. |
| PR-076 | Verify each site-specific experiment separately within a composite. | Portfolio coverage never substitutes for an unrun route or proves combined thermal/mobility performance at one site. |

Composite optimization may report supported-requirement coverage and site-count penalties using documented objectives. If travel cost, permissions or site accessibility were not modeled, say so. A portfolio is an experiment plan, not a scheduled or permitted field campaign.

### 3.9 Operations and passports

| ID | Required behavior | Observable completion |
|---|---|---|
| PR-080 | Expose useful Agent Council operations and deterministic tool receipts. | Users can follow request → evidence → critique → decision → changed result. |
| PR-081 | Stream committed run events and recover from disconnects without duplicating actions. | Reload and cursor resynchronization restore accurate progress and persisted artifacts. |
| PR-082 | Display runtime mode throughout live, synthetic and replay runs. | Replay never claims live calls; synthetic numbers never receive NASA source labels. |
| PR-083 | Build passports for positive, limited, failed and inconclusive investigations. | Unsupported dimensions remain visible in the exported final artifact. |
| PR-084 | Export printable HTML, JSON and selected table CSVs with digests and provenance. | Exports can be opened without the running frontend and agree with the pinned snapshot. |
| PR-085 | Retain evidence lineage without exposing credentials or private model reasoning. | Exported receipts are sanitized and reference resolvable, authorized artifacts. |

## 4. Prioritization without scope loss

Implement a terrain vertical slice first, then generalize it. The complete release gate includes both target bodies, multiple mission/rover revisions, data-coverage failures, critic revision, deterministic verification, bounded replanning, complementary portfolios and exports. EMIT and Diviner must have functioning adapter/coverage paths; a no-coverage result is valid, but a placeholder button is not an adapter.

Progression: data contracts and valid empty states → mission/rover revisioning → terrain evidence → candidate discovery → qualification → critic → benchmark/verification → diagnosis/replanning → portfolios → exports → full acceptance pack. A temporary synthetic shell must be explicitly synthetic and replaced by API-backed screens before the corresponding release gate passes.

## 5. Quality and performance acceptance

Design targets, to measure rather than assume: local form feedback within 200 ms; navigation with cached data within 500 ms; committed run-event visibility within 2 seconds in a normal local deployment; route/map interaction remains usable while worker jobs execute. Scientific jobs have no fabricated countdown or fixed completion promise. Show current stage, elapsed time, actual processed counts, queue state and cancel availability.

Keyboard-only operation must reach every action and evidence panel. Status uses text/icons as well as color. At 360 CSS px, all workflows remain usable in a single-column layout; large tables can have labeled horizontal scrolling or card alternatives. At 200% zoom, actions and dialogs remain reachable. Reduced-motion preference removes animated route playback and decorative movement. See screen/component/design documents for concrete behavior.

## 6. Product-level release gate

The release report must map every `PR-*` requirement to evidence or a clearly deferred future feature. Full product completion cannot be asserted while an included requirement is deferred. All scenarios in `28-DEMO-SCENARIOS-AND-ACCEPTANCE.md` must have recorded results. At least one live, real-data path for each planetary body must generate an evidence-linked passport; synthetic and replay acceptance remain separate.

## 7. Input/output ownership

Inputs: mission drafts/revisions from `/api/v1/missions`, rover revisions from `/api/v1/rovers`, run creation/status/events from `/api/v1/runs`, candidate/qualification/test/passport records from the corresponding API families. Exact request/response names come from the authoritative OpenAPI contract and generated TypeScript client. Frontend view models may rename fields for rendering but must not introduce new scientific states or implicit calculations.

Outputs: reviewable mission contract, target profile, candidate investigation set, qualification matrix, critic review, rover compatibility, experiment attempts, composite plan, sanitized activity timeline and immutable Analog Passport. All output IDs and revisions must be reachable from a run snapshot so a browser refresh reconstructs the same investigation.
