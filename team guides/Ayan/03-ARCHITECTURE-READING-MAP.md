# Ayan architecture reading map

Read the First rows before substantive implementation, then specialist rows as the module begins. Links point to the original shared files in this checkout; do not copy and modify a private architecture fork. The entire architecture is present on every branch.

| Architecture | When | How to use it | Gate |
| --- | --- | --- | --- |
| [00-ARCHITECTURE-DECISIONS.md](../../architecture%20files/00-ARCHITECTURE-DECISIONS.md) | First | Chosen stack, mode/status/scale/immutability; no private alternative meanings. | All science |
| [01-VISION-CONTEXT-AND-SCOPE.md](../../architecture%20files/01-VISION-CONTEXT-AND-SCOPE.md) | First | Mission-conditioned usefulness, not planetary-likeness percentage. | Product goal |
| [02-PRODUCT-REQUIREMENTS.md](../../architecture%20files/02-PRODUCT-REQUIREMENTS.md) | First | Scientific discovery/qualification/verification/composite requirements and acceptance. | S0/S1 |
| [04-REPOSITORY-AND-DEPENDENCIES.md](../../architecture%20files/04-REPOSITORY-AND-DEPENDENCIES.md) | First | Use owned science/adapters/tests; request Python lock changes from Tanush. | Environment |
| [05-DOMAIN-MODEL-AND-CONTRACTS.md](../../architecture%20files/05-DOMAIN-MODEL-AND-CONTRACTS.md) | First | Requirement operators/parameters/units/IDs/evidence scope and public types. | Port consistency |
| [07-HTTP-API-AND-EVENTS.md](../../architecture%20files/07-HTTP-API-AND-EVENTS.md) | Before display integration | Understand public output/read/display contracts; do not create endpoints. | I1 |
| [08-DATASET-CATALOG.md](../../architecture%20files/08-DATASET-CATALOG.md) | First | Dataset selectors/access/labels/quality/support and unsupported claims. | Source adapters |
| [09-DATA-INGESTION-AND-PROVENANCE.md](../../architecture%20files/09-DATA-INGESTION-AND-PROVENANCE.md) | First | Safe acquisition/metadata/provenance, policy lock and acquired granules. | Source adapters |
| [10-TERRAIN-AND-PLANETARY-COMPARISON.md](../../architecture%20files/10-TERRAIN-AND-PLANETARY-COMPARISON.md) | First | Body/frame/projection/mask/derivatives/roughness/scale/discovery calculations. | S0/S1 |
| [11-QUALIFICATION-AND-UNCERTAINTY.md](../../architecture%20files/11-QUALIFICATION-AND-UNCERTAINTY.md) | First | Deterministic requirement status/confidence/proxy/unknown rules. | Qualification |
| [12-ROUTE-ENERGY-AND-VERIFICATION.md](../../architecture%20files/12-ROUTE-ENERGY-AND-VERIFICATION.md) | First | Exact route/energy/exposure/search/independent verifier/failure/replan semantics. | S0 |
| [13-COMPOSITE-ANALOG-PORTFOLIOS.md](../../architecture%20files/13-COMPOSITE-ANALOG-PORTFOLIOS.md) | Before portfolios | Coverage/minimum-site/co-location/residual gap mathematics. | S1 |
| [15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md](../../architecture%20files/15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md) | Before facade | Map scientific functions to tool input/output without owning registry/roles. | F0 port |
| [18-MAPS-LAYERS-AND-VISUAL-DESIGN.md](../../architecture%20files/18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) | Before display | Generate scientifically correct images/manifests/legends for Aradhya. | Map handoff |
| [19-ANALOG-PASSPORT-AND-EXPORTS.md](../../architecture%20files/19-ANALOG-PASSPORT-AND-EXPORTS.md) | Before reporting handoff | Supply exact limitations/provenance/attempt captions rather than re-rendering reports. | Passport inputs |
| [20-CREDENTIALS-AND-EXTERNAL-SERVICES.md](../../architecture%20files/20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) | Before live source work | Protected Earthdata setup; no generic NASA API key or token leakage. | Access gates |
| [21-CONFIGURATION-AND-PREFLIGHT.md](../../architecture%20files/21-CONFIGURATION-AND-PREFLIGHT.md) | First | Limits/preflight/policy versus asset lock and configured server-owned paths. | Resources |
| [22-BACKEND-MODULES.md](../../architecture%20files/22-BACKEND-MODULES.md) | Before facade | Pure math/source adapters versus durable application wrappers. | Architecture |
| [26-TEST-STRATEGY.md](../../architecture%20files/26-TEST-STRATEGY.md) | First and final | Analytic/property/source replay and independent expected-value tests. | Test gates |
| [27-IMPLEMENTATION-PLAYBOOK.md](../../architecture%20files/27-IMPLEMENTATION-PLAYBOOK.md) | Context | Global order; deliver S0 early so UI/platform can connect. | Coordination |
| [28-DEMO-SCENARIOS-AND-ACCEPTANCE.md](../../architecture%20files/28-DEMO-SCENARIOS-AND-ACCEPTANCE.md) | Before S1 | Known/negative/mission-sensitivity/missing-scale/no-data acceptance. | Integration |
| [29-SCIENTIFIC-VALIDATION.md](../../architecture%20files/29-SCIENTIFIC-VALIDATION.md) | First and final | Scientific validation details and real-versus-synthetic claims. | Final science |
| [31-SOURCE-REGISTER.md](../../architecture%20files/31-SOURCE-REGISTER.md) | Before source probes | Official reference register and unvalidated granule boundaries. | Research provenance |

## Concrete contract and fixture files

- [Domain schema](../../architecture%20files/contracts/domain.schema.json), [OpenAPI](../../architecture%20files/contracts/openapi.yaml), and [canonical error codes](../../architecture%20files/contracts/error-codes.json).
- [Mission fixture](../../architecture%20files/examples/mission-contract.json), [rover import](../../architecture%20files/examples/rover-import.json), [graph regression](../../architecture%20files/examples/synthetic-route-graph.json), [constraints](../../architecture%20files/examples/constraints-artifact.json), and [environment template](../../architecture%20files/examples/.env.example).
- [Team service boundary](../../team%20coordination/03-SERVICE-BOUNDARIES.md) and [ownership registry](../../team%20coordination/contracts/ownership.json) decide who implements each side of a shared feature.

## Related runtime role specifications

These describe the product’s Agent Council, not permission to spawn additional coding agents. Tanush implements runtime roles; others read them for their consumer/output obligations.

- [03-rover-systems](../../architecture%20files/agents/03-rover-systems.md)
- [04-planetary-target](../../architecture%20files/agents/04-planetary-target.md)
- [05-earth-analog-scout](../../architecture%20files/agents/05-earth-analog-scout.md)
- [06-qualification](../../architecture%20files/agents/06-qualification.md)
- [07-scientific-critic](../../architecture%20files/agents/07-scientific-critic.md)
- [08-test-designer](../../architecture%20files/agents/08-test-designer.md)
- [09-verification-replanning](../../architecture%20files/agents/09-verification-replanning.md)

## Required scientific credibility reading

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
