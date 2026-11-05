# Tanush architecture reading map

Read the First rows before substantive implementation, then specialist rows as the module begins. Links point to the original shared files in this checkout; do not copy and modify a private architecture fork. The entire architecture is present on every branch.

| Architecture | When | How to use it | Gate |
| --- | --- | --- | --- |
| [34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md](../../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md) | First (mandatory) | Completion tiers, errata E-01…E-18, forbidden behaviors; overrides 00–33 | All |
| [35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md) | First (mandatory) | Kit, entry points, registrar rules, stage→operation table, config keys | All |
| [36-DATASET-PLUG-IN-AND-NASA-SLOT.md](../../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md) | First (mandatory) | Dataset CLI, lock file, binding rules | PLT-17 |
| [38-RUNTIME-KEYS-AND-LOCAL-SETUP.md](../../architecture%20files/38-RUNTIME-KEYS-AND-LOCAL-SETUP.md) | First (mandatory) | Keys, DB bootstrap ladder, preflight stages | PLT-16/17 |
| [39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md](../../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) | First (mandatory) | Your PLT rows; journeys you must support | All gates |
| [40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md](../../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) | First (mandatory) | Scenarios, storylines, seeded defect, picker rule | PLT-10, PLT-20 |
| [00-ARCHITECTURE-DECISIONS.md](../../architecture%20files/00-ARCHITECTURE-DECISIONS.md) | First | Binding stack/status/mode/immutability decisions; preserve these in settings/policy. | All gates |
| [01-VISION-CONTEXT-AND-SCOPE.md](../../architecture%20files/01-VISION-CONTEXT-AND-SCOPE.md) | First | Understand why qualification, compatibility and actual verification are separate. | Product scope |
| [02-PRODUCT-REQUIREMENTS.md](../../architecture%20files/02-PRODUCT-REQUIREMENTS.md) | First | Trace platform/API/agents obligations and the complete58-requirement product ledger. | Final RC |
| [03-SYSTEM-ARCHITECTURE.md](../../architecture%20files/03-SYSTEM-ARCHITECTURE.md) | First | Implement API/worker/store boundaries, not request-inline raster CPU. | F0 |
| [04-REPOSITORY-AND-DEPENDENCIES.md](../../architecture%20files/04-REPOSITORY-AND-DEPENDENCIES.md) | First | Create only owned scaffolding/locks/commands and publish native runtime. | F0 |
| [05-DOMAIN-MODEL-AND-CONTRACTS.md](../../architecture%20files/05-DOMAIN-MODEL-AND-CONTRACTS.md) | First | Pydantic/semantic types, revisions, hashes, preparation/no-rover and shared IDs. | F0/domain |
| [06-DATABASE-AND-STORAGE.md](../../architecture%20files/06-DATABASE-AND-STORAGE.md) | First | Actual DB schema/migrations/lineage/artifact atomicity. | Persistence |
| [07-HTTP-API-AND-EVENTS.md](../../architecture%20files/07-HTTP-API-AND-EVENTS.md) | First | All request/read/action/error/SSE contracts and scenario capabilities. | API/client |
| [08-DATASET-CATALOG.md](../../architecture%20files/08-DATASET-CATALOG.md) | Before science integration | Understand credentials/coverage/support; decoder implementation remains Ayan’s. | Source gate |
| [11-QUALIFICATION-AND-UNCERTAINTY.md](../../architecture%20files/11-QUALIFICATION-AND-UNCERTAINTY.md) | Before policy | Evidence/scale/confidence meanings; policy cannot turn missing evidence into PASS. | Qualification |
| [12-ROUTE-ENERGY-AND-VERIFICATION.md](../../architecture%20files/12-ROUTE-ENERGY-AND-VERIFICATION.md) | Before tool integration | Freeze test/route/energy/search semantics; invoke Ayan, do not duplicate solver. | I1 |
| [13-COMPOSITE-ANALOG-PORTFOLIOS.md](../../architecture%20files/13-COMPOSITE-ANALOG-PORTFOLIOS.md) | Before portfolio | Persist and expose portfolio assignments/co-location/residuals. | Full scope |
| [14-AGENT-ORCHESTRATION.md](../../architecture%20files/14-AGENT-ORCHESTRATION.md) | Before agent work | Scheduler, roles, state graph, budgets, review/PROVE_IT gates. | P1 |
| [15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md](../../architecture%20files/15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md) | Before agent work | Strict task/tool/result/receipt/preparation contracts and canonical names. | P1 |
| [19-ANALOG-PASSPORT-AND-EXPORTS.md](../../architecture%20files/19-ANALOG-PASSPORT-AND-EXPORTS.md) | Before export work | Assemble exact frozen bundle/manifest, serve renderer output. | U1/RC |
| [20-CREDENTIALS-AND-EXTERNAL-SERVICES.md](../../architecture%20files/20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) | Before live probes | Actual provider/source credential setup without searching unrelated files. | Live gates |
| [21-CONFIGURATION-AND-PREFLIGHT.md](../../architecture%20files/21-CONFIGURATION-AND-PREFLIGHT.md) | First | Typed settings, source-policy/acquired asset locks and honest capability states. | F0/preflight |
| [22-BACKEND-MODULES.md](../../architecture%20files/22-BACKEND-MODULES.md) | Before services | Module responsibilities and port boundaries. | All services |
| [23-JOBS-AND-RECOVERY.md](../../architecture%20files/23-JOBS-AND-RECOVERY.md) | Before worker | Lease/fencing/retry/cancel/event atomicity. | Recovery |
| [24-SECURITY-IDENTITY-AND-DATA-POLICY.md](../../architecture%20files/24-SECURITY-IDENTITY-AND-DATA-POLICY.md) | Before hardening | Local binding, authorization, workspace isolation and source/output controls. | Security |
| [25-DEPLOYMENT-OPERATIONS-AND-OBSERVABILITY.md](../../architecture%20files/25-DEPLOYMENT-OPERATIONS-AND-OBSERVABILITY.md) | Before RC | Compose/proxy/resource/backup/restore observability without deployment. | Operations |
| [26-TEST-STRATEGY.md](../../architecture%20files/26-TEST-STRATEGY.md) | First and final | Implement platform and combined release tests; software versus live/physical gates. | All tests |
| [27-IMPLEMENTATION-PLAYBOOK.md](../../architecture%20files/27-IMPLEMENTATION-PLAYBOOK.md) | First | Global dependency order; team split narrows file ownership only. | Integration |
| [28-DEMO-SCENARIOS-AND-ACCEPTANCE.md](../../architecture%20files/28-DEMO-SCENARIOS-AND-ACCEPTANCE.md) | Before I1/RC | Combined positive/negative/no-data/no-rover/scientific/UI scenarios. | RC |
| [29-SCIENTIFIC-VALIDATION.md](../../architecture%20files/29-SCIENTIFIC-VALIDATION.md) | Before science acceptance | Required source and scientific evidence versus fake success. | Data acceptance |
| [30-REQUIREMENTS-TRACEABILITY.md](../../architecture%20files/30-REQUIREMENTS-TRACEABILITY.md) | At each checkpoint | Update requirement→module→test→observed evidence. | Final ledger |
| [32-CODING-AGENT-EXECUTION-PROMPT.md](../../architecture%20files/32-CODING-AGENT-EXECUTION-PROMPT.md) | Context only | Whole-app handoff intent; your personal task assigns own implementation and integration. | No scope creep |

## Concrete contract and fixture files

- [Domain schema](../../architecture%20files/contracts/domain.schema.json), [OpenAPI](../../architecture%20files/contracts/openapi.yaml), and [canonical error codes](../../architecture%20files/contracts/error-codes.json).
- [Mission fixture](../../architecture%20files/examples/mission-contract.json), [rover import](../../architecture%20files/examples/rover-import.json), [graph regression](../../architecture%20files/examples/synthetic-route-graph.json), [constraints](../../architecture%20files/examples/constraints-artifact.json), and [environment template](../../architecture%20files/examples/.env.example).
- [Team service boundary](../../team%20coordination/03-SERVICE-BOUNDARIES.md) and [ownership registry](../../team%20coordination/contracts/ownership.json) decide who implements each side of a shared feature.

## Related runtime role specifications

These describe the product’s Agent Council, not permission to spawn additional coding agents. Tanush implements runtime roles; others read them for their consumer/output obligations.

- [01-mission-director](../../architecture%20files/agents/01-mission-director.md)
- [02-requirements](../../architecture%20files/agents/02-requirements.md)
- [03-rover-systems](../../architecture%20files/agents/03-rover-systems.md)
- [04-planetary-target](../../architecture%20files/agents/04-planetary-target.md)
- [05-earth-analog-scout](../../architecture%20files/agents/05-earth-analog-scout.md)
- [06-qualification](../../architecture%20files/agents/06-qualification.md)
- [07-scientific-critic](../../architecture%20files/agents/07-scientific-critic.md)
- [08-test-designer](../../architecture%20files/agents/08-test-designer.md)
- [09-verification-replanning](../../architecture%20files/agents/09-verification-replanning.md)
- [10-evidence-passport](../../architecture%20files/agents/10-evidence-passport.md)

## Required scientific credibility reading

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
