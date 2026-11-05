# AnalogForge implementation blueprint

This folder is the complete build specification for AnalogForge: a mission-conditioned Earth analog qualification and modeled test-design application. It includes product requirements, implementation decisions, scientific algorithms, ten agent role specifications, typed contracts, API operations, data/credential setup, interface behavior, execution order and acceptance checks. It does not contain an implemented app or measured results from real NASA products.

Start with the reading order below. Keep the shared contracts authoritative while implementing specialist modules; do not read one UI file and invent the remaining backend. The goal is a coherent full application, with truthful handling of unavailable data and external setup.

## Start here

1. [Architecture decisions and precedence](00-ARCHITECTURE-DECISIONS.md): binding technical choices, invariants and source conflicts.
2. [Vision context and scope](01-VISION-CONTEXT-AND-SCOPE.md) and [product requirements](02-PRODUCT-REQUIREMENTS.md): full product obligations and intended users.
3. [System architecture](03-SYSTEM-ARCHITECTURE.md), [repository layout](04-REPOSITORY-AND-DEPENDENCIES.md), [domain contracts](05-DOMAIN-MODEL-AND-CONTRACTS.md), [storage](06-DATABASE-AND-STORAGE.md) and [API/events](07-HTTP-API-AND-EVENTS.md).
4. [Implementation playbook](27-IMPLEMENTATION-PLAYBOOK.md): execute milestones through the complete product, with working gates.
5. [Coding agent execution prompt](32-CODING-AGENT-EXECUTION-PROMPT.md): the self-contained implementation handoff task.

## Scientific implementation

- [08 Dataset catalog](08-DATASET-CATALOG.md): NASADEM/SRTM, MOLA, LOLA, EMIT, Diviner and user-survey access/limits.
- [09 Ingestion and provenance](09-DATA-INGESTION-AND-PROVENANCE.md): metadata, downloads, masks, policy locks and immutable acquired assets.
- [10 Terrain and planetary comparison](10-TERRAIN-AND-PLANETARY-COMPARISON.md): body-aware geometry, slope, relief, roughness, comparable support and discovery.
- [11 Qualification and uncertainty](11-QUALIFICATION-AND-UNCERTAINTY.md): deterministic statuses, evidence strength and unavailable conditions.
- [12 Route energy and verification](12-ROUTE-ENERGY-AND-VERIFICATION.md): bounded route solver, independent verifier, exposure, tasks, energy, diagnosis and replans.
- [13 Composite portfolios](13-COMPOSITE-ANALOG-PORTFOLIOS.md): coverage, co-location and minimal complementary campaigns.
- [29 Scientific validation](29-SCIENTIFIC-VALIDATION.md): analytic controls, real-data gates, mission sensitivity and scope of claims.

## Agents and tools

Read [14 Orchestration](14-AGENT-ORCHESTRATION.md), [15 Tool and prompt contracts](15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md) and the [common system policy](prompts/COMMON-SYSTEM-POLICY.md), then the role being implemented:

| Role | Specification |
| --- | --- |
| Mission Director | [01](agents/01-mission-director.md) |
| Requirements | [02](agents/02-requirements.md) |
| Rover Systems | [03](agents/03-rover-systems.md) |
| Planetary Target | [04](agents/04-planetary-target.md) |
| Earth Analog Scout | [05](agents/05-earth-analog-scout.md) |
| Qualification | [06](agents/06-qualification.md) |
| Scientific Critic | [07](agents/07-scientific-critic.md) |
| Test Designer | [08](agents/08-test-designer.md) |
| Verification and Replanning | [09](agents/09-verification-replanning.md) |
| Evidence and Passport | [10](agents/10-evidence-passport.md) |

Each role has entry conditions, explicit task kinds, allowed tools, outputs, evidence requirements, authority limits, retry/stop behavior, handoffs and acceptance cases. One configured model can implement all roles. Deterministic tools supply measurements; backend policy commits scientific conclusions.

## Product interface

[16 Journeys and screens](16-USER-JOURNEYS-AND-SCREENS.md), [17 Frontend components and state](17-FRONTEND-COMPONENTS-AND-STATE.md), [18 Maps and visual design](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md), and [19 Passports and exports](19-ANALOG-PASSPORT-AND-EXPORTS.md) define the workbench, accessible alternatives, data ownership, committed event behavior, negative states and report integrity.

## Setup delivery and acceptance

- [20 Credentials and services](20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) and [21 Configuration/preflight](21-CONFIGURATION-AND-PREFLIGHT.md): exact key names, account dependencies, mode behavior and source locking.
- [22 Backend modules](22-BACKEND-MODULES.md) and [23 Durable jobs/recovery](23-JOBS-AND-RECOVERY.md): implementation boundaries and failure handling.
- [24 Security](24-SECURITY-IDENTITY-AND-DATA-POLICY.md) and [25 Deployment/operations](25-DEPLOYMENT-OPERATIONS-AND-OBSERVABILITY.md): local/hosted identity, quotas, secrets, monitoring, backup and restore.
- [26 Test strategy](26-TEST-STRATEGY.md), [28 Acceptance scenarios](28-DEMO-SCENARIOS-AND-ACCEPTANCE.md), [30 Traceability](30-REQUIREMENTS-TRACEABILITY.md) and [31 Source register](31-SOURCE-REGISTER.md): what counts as verified and what remains an external prerequisite.

## Machine readable material

| File | Purpose |
| --- | --- |
| [Domain JSON Schema](contracts/domain.schema.json) | Shared entities, statuses, requirements, evidence, reviews, display layers, results and snapshots. |
| [OpenAPI](contracts/openapi.yaml) | Starting HTTP contract in JSON syntax valid as YAML1.2. Includes body schemas, action variants and response references. |
| [Error registry](contracts/error-codes.json) | Shared error codes and request-boundary mappings. |
| [Requirement ledger](contracts/requirements-traceability.csv) | Exact58 product requirements with implementation/test/evidence columns to complete during build. |
| [Environment template](examples/.env.example) | No actual secrets; synthetic/local defaults and explicit live prerequisites. |
| [Mission fixture](examples/mission-contract.json) and [rover fixture](examples/rover-profile.json) | Schema-valid persisted synthetic examples with semantic hashes. |
| [Rover import](examples/rover-import.json) | Upload/manual input shape without generated database metadata. |
| [Synthetic route graph](examples/synthetic-route-graph.json) and [constraints](examples/constraints-artifact.json) | Computable failed-route and repaired-route regression, visibly test-only. |
| [Create run](examples/request-create-run.json), [PROVE IT](examples/request-prove-it.json), [event](examples/run-event.json), [unknown qualification](examples/qualification-unknown.json) | Concrete wire examples. |
| [Dataset policy template](examples/dataset-lock.template.json) | Intentionally unresolved preflight template; never pass it off as downloaded/validated evidence. |
| [Scenario manifest](examples/scenario-manifest.json) | Small offline fixture wiring, distinct from live scenarios. |

Original documents and their hashes are in [references](references/source-manifest.json). [FILE INDEX](FILE-INDEX.md) lists every file.

## Blueprint validation

Run `rtk proxy python3 'architecture files/contracts/validate_blueprint.py'` from the connected workspace. The utility requires `jsonschema` and `referencing`; they are also specified as application development dependencies. It validates schemas/references, example shapes/hashes, original source copies, requirement ledger, internal links, JSON code examples and synthetic graph arithmetic. Results are in [BLUEPRINT VALIDATION](BLUEPRINT-VALIDATION.json).

This validates the blueprint artifacts. Application tests, live accounts, exact NASA granules, real coverage and physical rover performance remain separate gates. Credentials and actual source availability must be supplied/verified during implementation; no architecture can guarantee those external facts.

## Decisions that must survive implementation

PASS, PARTIAL, FAIL, GAP and UNKNOWN remain distinct. Verification adds INCONCLUSIVE for missing information or bounded search. Coarse planetary data provides regional context; Earth terrain-model feasibility does not certify wheel-scale clearance or physical navigation. Replanning preserves accepted requirements. The initial PROVE IT click authorizes test design and execution within accepted assumptions; new material input changes require review/new revisions. All modes and uncertainty remain visible in the final passport.

## Mandatory C1 scientific credibility controls

Read [33 scientific credibility and claim gates](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md). It defines the backend audit/compiler, source/scale/coverage/uncertainty/critic/verification/publication checks and required passport assurance pointer. Machine contracts: [assurance schema](contracts/scientific-assurance.schema.json), [SC gate registry](contracts/scientific-gates.json). Examples: [supported negative](examples/assurance-supported-negative.json), [limited unknown](examples/assurance-limited-unknown.json), [blocked claim](examples/assurance-blocked-claim.json). These are visibly synthetic shape/semantics fixtures, not executed scientific validation. All branches follow [shared credibility acceptance](../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md).
