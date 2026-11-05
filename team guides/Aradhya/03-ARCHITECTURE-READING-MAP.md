# Aradhya architecture reading map

Read the First rows before substantive implementation, then specialist rows as the module begins. Links point to the original shared files in this checkout; do not copy and modify a private architecture fork. The entire architecture is present on every branch.

| Architecture | When | How to use it | Gate |
| --- | --- | --- | --- |
| [34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md](../../architecture%20files/34-ONE-SHOT-BUILD-PROFILE-AND-ERRATA.md) | First (mandatory) | Completion tiers, errata E-01…E-18 (note E-01 frontend path, E-09 preliminary rows), forbidden behaviors | All |
| [35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md) | First (mandatory) | Kit, bundled OpenAPI, renderer seam, §5b UI-readable artifacts, test-id contract | All |
| [39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md](../../architecture%20files/39-ACCEPTANCE-CATALOG-AND-PURITY-TESTS.md) | First (mandatory) | Your UIX rows and journeys J1–J13 (the exact click scripts) | All gates |
| [40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md](../../architecture%20files/40-PRACTICE-SCENARIOS-AND-FIXTURE-SPECS.md) | First (mandatory) | Storylines, truth tables, scenario catalog the mock must replay | UIX-03/05 |
| [00-ARCHITECTURE-DECISIONS.md](../../architecture%20files/00-ARCHITECTURE-DECISIONS.md) | First | Never duplicate statuses, mislabel modes or let UI alter scientific truth. | All UX |
| [01-VISION-CONTEXT-AND-SCOPE.md](../../architecture%20files/01-VISION-CONTEXT-AND-SCOPE.md) | First | Core user question and truthful scope of modeled test outcomes. | Product story |
| [02-PRODUCT-REQUIREMENTS.md](../../architecture%20files/02-PRODUCT-REQUIREMENTS.md) | First | All user-facing functional requirements and negative states. | Full UI |
| [04-REPOSITORY-AND-DEPENDENCIES.md](../../architecture%20files/04-REPOSITORY-AND-DEPENDENCIES.md) | First | Frontend/client/renderer paths, locks and generated contract approach. | Tooling |
| [05-DOMAIN-MODEL-AND-CONTRACTS.md](../../architecture%20files/05-DOMAIN-MODEL-AND-CONTRACTS.md) | First | Exact entity/status/quantity/selection/revision/requirement types. | Client |
| [07-HTTP-API-AND-EVENTS.md](../../architecture%20files/07-HTTP-API-AND-EVENTS.md) | First | Requests/actions/read/review/SSE/export/display contracts. | API integration |
| [08-DATASET-CATALOG.md](../../architecture%20files/08-DATASET-CATALOG.md) | Before map labels | Know actual source scale/coverage; raw source decoding belongs to Ayan. | Truthful maps |
| [11-QUALIFICATION-AND-UNCERTAINTY.md](../../architecture%20files/11-QUALIFICATION-AND-UNCERTAINTY.md) | Before matrix | PASS/PARTIAL/FAIL/GAP/UNKNOWN/confidence scope and evidence semantics. | Matrix/evidence |
| [12-ROUTE-ENERGY-AND-VERIFICATION.md](../../architecture%20files/12-ROUTE-ENERGY-AND-VERIFICATION.md) | Before test lab | Explain modeled route/energy/exposure/search/failed attempts correctly. | Test UX |
| [13-COMPOSITE-ANALOG-PORTFOLIOS.md](../../architecture%20files/13-COMPOSITE-ANALOG-PORTFOLIOS.md) | Before portfolio | Show co-location versus separate-campaign coverage and residual unknowns. | Portfolio |
| [14-AGENT-ORCHESTRATION.md](../../architecture%20files/14-AGENT-ORCHESTRATION.md) | Before operations | Display committed roles/actions/reviews rather than private reasoning. | Timeline |
| [16-USER-JOURNEYS-AND-SCREENS.md](../../architecture%20files/16-USER-JOURNEYS-AND-SCREENS.md) | First | End-to-end screen/actions/loading/error/review behavior. | Workflows |
| [17-FRONTEND-COMPONENTS-AND-STATE.md](../../architecture%20files/17-FRONTEND-COMPONENTS-AND-STATE.md) | First | Components/query/router/local state/SSE reconciliation and accessibility. | State |
| [18-MAPS-LAYERS-AND-VISUAL-DESIGN.md](../../architecture%20files/18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) | First | Earth/planetary map distinction, manifests/legend/scale/visual rules. | Maps/design |
| [19-ANALOG-PASSPORT-AND-EXPORTS.md](../../architecture%20files/19-ANALOG-PASSPORT-AND-EXPORTS.md) | First | Pure renderer, complete frozen report, escaping/digests/download format. | Exports |
| [20-CREDENTIALS-AND-EXTERNAL-SERVICES.md](../../architecture%20files/20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) | Before capability UX | Keep secrets out of browser; missing keys show safe remediation only. | Security |
| [21-CONFIGURATION-AND-PREFLIGHT.md](../../architecture%20files/21-CONFIGURATION-AND-PREFLIGHT.md) | Before real backend | Correct profile/scenario/mode/source-policy settings. | Runtime |
| [24-SECURITY-IDENTITY-AND-DATA-POLICY.md](../../architecture%20files/24-SECURITY-IDENTITY-AND-DATA-POLICY.md) | Before renderer/API completion | Escaping/CSRF/workspace/source link/output safety. | Security |
| [26-TEST-STRATEGY.md](../../architecture%20files/26-TEST-STRATEGY.md) | First and final | Meaningful component/renderer/browser/real-API tests and release gates. | Tests |
| [27-IMPLEMENTATION-PLAYBOOK.md](../../architecture%20files/27-IMPLEMENTATION-PLAYBOOK.md) | Context | Build UI early against C1, then integrate actual F0/S0. | Coordination |
| [28-DEMO-SCENARIOS-AND-ACCEPTANCE.md](../../architecture%20files/28-DEMO-SCENARIOS-AND-ACCEPTANCE.md) | First and final | Full positive/negative/no-rover/unknown/replan/portfolio scenarios. | Acceptance |
| [30-REQUIREMENTS-TRACEABILITY.md](../../architecture%20files/30-REQUIREMENTS-TRACEABILITY.md) | At handoff | Map UI behavior to actual requirement IDs and observed test results. | Report |

## Concrete contract and fixture files

- [Domain schema](../../architecture%20files/contracts/domain.schema.json), [OpenAPI](../../architecture%20files/contracts/openapi.yaml), and [canonical error codes](../../architecture%20files/contracts/error-codes.json).
- [Mission fixture](../../architecture%20files/examples/mission-contract.json), [rover import](../../architecture%20files/examples/rover-import.json), [graph regression](../../architecture%20files/examples/synthetic-route-graph.json), [constraints](../../architecture%20files/examples/constraints-artifact.json), and [environment template](../../architecture%20files/examples/.env.example).
- [Team service boundary](../../team%20coordination/03-SERVICE-BOUNDARIES.md) and [ownership registry](../../team%20coordination/contracts/ownership.json) decide who implements each side of a shared feature.

## Related runtime role specifications

These describe the product’s Agent Council, not permission to spawn additional coding agents. Tanush implements runtime roles; others read them for their consumer/output obligations.

- [07-scientific-critic](../../architecture%20files/agents/07-scientific-critic.md)
- [08-test-designer](../../architecture%20files/agents/08-test-designer.md)
- [09-verification-replanning](../../architecture%20files/agents/09-verification-replanning.md)
- [10-evidence-passport](../../architecture%20files/agents/10-evidence-passport.md)

## Required scientific credibility reading

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
