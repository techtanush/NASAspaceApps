# Architecture file index

Every file below belongs to the implementation blueprint. Validation reports describe planning integrity, not application or scientific completion.

| File | Purpose |
| --- | --- |
| [00-ARCHITECTURE-DECISIONS.md](00-ARCHITECTURE-DECISIONS.md) | Architecture decisions and precedence |
| [01-VISION-CONTEXT-AND-SCOPE.md](01-VISION-CONTEXT-AND-SCOPE.md) | AnalogForge vision context and scope |
| [02-PRODUCT-REQUIREMENTS.md](02-PRODUCT-REQUIREMENTS.md) | Product requirements and completion contract |
| [03-SYSTEM-ARCHITECTURE.md](03-SYSTEM-ARCHITECTURE.md) | System architecture |
| [04-REPOSITORY-AND-DEPENDENCIES.md](04-REPOSITORY-AND-DEPENDENCIES.md) | Repository layout and dependencies |
| [05-DOMAIN-MODEL-AND-CONTRACTS.md](05-DOMAIN-MODEL-AND-CONTRACTS.md) | Domain model and contracts |
| [06-DATABASE-AND-STORAGE.md](06-DATABASE-AND-STORAGE.md) | Database and artifact storage |
| [07-HTTP-API-AND-EVENTS.md](07-HTTP-API-AND-EVENTS.md) | HTTP API and committed events |
| [08-DATASET-CATALOG.md](08-DATASET-CATALOG.md) | Dataset catalog and scientific access contracts |
| [09-DATA-INGESTION-AND-PROVENANCE.md](09-DATA-INGESTION-AND-PROVENANCE.md) | Data ingestion, normalization, and evidence provenance |
| [10-TERRAIN-AND-PLANETARY-COMPARISON.md](10-TERRAIN-AND-PLANETARY-COMPARISON.md) | Terrain analysis, candidate discovery, and planetary comparison |
| [11-QUALIFICATION-AND-UNCERTAINTY.md](11-QUALIFICATION-AND-UNCERTAINTY.md) | Requirement qualification, uncertainty, and scientific claims |
| [12-ROUTE-ENERGY-AND-VERIFICATION.md](12-ROUTE-ENERGY-AND-VERIFICATION.md) | PROVE IT: route design, resource search, energy, and verification |
| [13-COMPOSITE-ANALOG-PORTFOLIOS.md](13-COMPOSITE-ANALOG-PORTFOLIOS.md) | Composite analog portfolios and residual gaps |
| [14-AGENT-ORCHESTRATION.md](14-AGENT-ORCHESTRATION.md) | Agent orchestration: ten roles, one controlled workflow |
| [15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md](15-TOOL-REGISTRY-AND-PROMPT-CONTRACT.md) | Tool registry and model-facing contracts |
| [16-USER-JOURNEYS-AND-SCREENS.md](16-USER-JOURNEYS-AND-SCREENS.md) | User journeys, screens and interaction states |
| [17-FRONTEND-COMPONENTS-AND-STATE.md](17-FRONTEND-COMPONENTS-AND-STATE.md) | Frontend implementation, components and state ownership |
| [18-MAPS-LAYERS-AND-VISUAL-DESIGN.md](18-MAPS-LAYERS-AND-VISUAL-DESIGN.md) | Maps, scientific layers and visual design |
| [19-ANALOG-PASSPORT-AND-EXPORTS.md](19-ANALOG-PASSPORT-AND-EXPORTS.md) | Analog Passport, provenance and export implementation |
| [20-CREDENTIALS-AND-EXTERNAL-SERVICES.md](20-CREDENTIALS-AND-EXTERNAL-SERVICES.md) | Credentials and external services |
| [21-CONFIGURATION-AND-PREFLIGHT.md](21-CONFIGURATION-AND-PREFLIGHT.md) | Configuration and preflight |
| [22-BACKEND-MODULES.md](22-BACKEND-MODULES.md) | Backend module implementation contracts |
| [23-JOBS-AND-RECOVERY.md](23-JOBS-AND-RECOVERY.md) | Durable jobs events and recovery |
| [24-SECURITY-IDENTITY-AND-DATA-POLICY.md](24-SECURITY-IDENTITY-AND-DATA-POLICY.md) | Security identity and data policy |
| [25-DEPLOYMENT-OPERATIONS-AND-OBSERVABILITY.md](25-DEPLOYMENT-OPERATIONS-AND-OBSERVABILITY.md) | Deployment operations and observability |
| [26-TEST-STRATEGY.md](26-TEST-STRATEGY.md) | Test strategy and release gates |
| [27-IMPLEMENTATION-PLAYBOOK.md](27-IMPLEMENTATION-PLAYBOOK.md) | Implementation playbook with completion gates |
| [28-DEMO-SCENARIOS-AND-ACCEPTANCE.md](28-DEMO-SCENARIOS-AND-ACCEPTANCE.md) | Demo scenarios, negative controls and acceptance evidence |
| [29-SCIENTIFIC-VALIDATION.md](29-SCIENTIFIC-VALIDATION.md) | Scientific validation and evidence release gates |
| [30-REQUIREMENTS-TRACEABILITY.md](30-REQUIREMENTS-TRACEABILITY.md) | Requirements traceability and completion evidence |
| [31-SOURCE-REGISTER.md](31-SOURCE-REGISTER.md) | Source register and verification boundaries |
| [32-CODING-AGENT-EXECUTION-PROMPT.md](32-CODING-AGENT-EXECUTION-PROMPT.md) | Coding agent execution prompt |
| [33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) | Scientific credibility and enforceable claim gates |
| [BLUEPRINT-VALIDATION.json](BLUEPRINT-VALIDATION.json) | Supporting blueprint artifact |
| [FILE-INDEX.md](FILE-INDEX.md) | Architecture file index |
| [README.md](README.md) | AnalogForge implementation blueprint |
| [agents/01-mission-director.md](agents/01-mission-director.md) | Role 01 — Mission Director |
| [agents/02-requirements.md](agents/02-requirements.md) | Role 02 — Requirements Agent |
| [agents/03-rover-systems.md](agents/03-rover-systems.md) | Role 03 — Rover Systems Agent |
| [agents/04-planetary-target.md](agents/04-planetary-target.md) | Role 04 — Planetary Target Agent |
| [agents/05-earth-analog-scout.md](agents/05-earth-analog-scout.md) | Role 05 — Earth Analog Scout |
| [agents/06-qualification.md](agents/06-qualification.md) | Role 06 — Qualification Agent |
| [agents/07-scientific-critic.md](agents/07-scientific-critic.md) | Role 07 — Scientific Critic |
| [agents/08-test-designer.md](agents/08-test-designer.md) | Role 08 — Test Designer |
| [agents/09-verification-replanning.md](agents/09-verification-replanning.md) | Role 09 — Verification and Replanning |
| [agents/10-evidence-passport.md](agents/10-evidence-passport.md) | Role 10 — Evidence and Analog Passport |
| [contracts/domain.schema.json](contracts/domain.schema.json) | Typed JSON Schema contract |
| [contracts/error-codes.json](contracts/error-codes.json) | Supporting blueprint artifact |
| [contracts/openapi.yaml](contracts/openapi.yaml) | Supporting blueprint artifact |
| [contracts/requirements-traceability.csv](contracts/requirements-traceability.csv) | Supporting blueprint artifact |
| [contracts/scientific-assurance.schema.json](contracts/scientific-assurance.schema.json) | Typed JSON Schema contract |
| [contracts/scientific-gates.json](contracts/scientific-gates.json) | Supporting blueprint artifact |
| [contracts/validate_blueprint.py](contracts/validate_blueprint.py) | Supporting blueprint artifact |
| [examples/.env.example](examples/.env.example) | Supporting blueprint artifact |
| [examples/assurance-blocked-claim.json](examples/assurance-blocked-claim.json) | Supporting blueprint artifact |
| [examples/assurance-limited-unknown.json](examples/assurance-limited-unknown.json) | Supporting blueprint artifact |
| [examples/assurance-supported-negative.json](examples/assurance-supported-negative.json) | Supporting blueprint artifact |
| [examples/constraints-artifact.json](examples/constraints-artifact.json) | Supporting blueprint artifact |
| [examples/dataset-lock.template.json](examples/dataset-lock.template.json) | Supporting blueprint artifact |
| [examples/mission-contract.json](examples/mission-contract.json) | Supporting blueprint artifact |
| [examples/qualification-unknown.json](examples/qualification-unknown.json) | Supporting blueprint artifact |
| [examples/request-create-run.json](examples/request-create-run.json) | Supporting blueprint artifact |
| [examples/request-prove-it.json](examples/request-prove-it.json) | Supporting blueprint artifact |
| [examples/rover-import.json](examples/rover-import.json) | Supporting blueprint artifact |
| [examples/rover-profile.json](examples/rover-profile.json) | Supporting blueprint artifact |
| [examples/run-event.json](examples/run-event.json) | Supporting blueprint artifact |
| [examples/scenario-manifest.json](examples/scenario-manifest.json) | Supporting blueprint artifact |
| [examples/synthetic-route-graph.json](examples/synthetic-route-graph.json) | Supporting blueprint artifact |
| [prompts/COMMON-SYSTEM-POLICY.md](prompts/COMMON-SYSTEM-POLICY.md) | Common system policy for all AnalogForge roles |
| [references/AnalogForge_Final_Research_Build_Brief.docx](references/AnalogForge_Final_Research_Build_Brief.docx) | Supporting blueprint artifact |
| [references/docx-text-extract.txt](references/docx-text-extract.txt) | Supporting blueprint artifact |
| [references/original-concept.txt](references/original-concept.txt) | Supporting blueprint artifact |
| [references/source-manifest.json](references/source-manifest.json) | Supporting blueprint artifact |
| [examples/assurance-supported-positive.json](examples/assurance-supported-positive.json) | Synthetic supported-positive assurance fixture |
