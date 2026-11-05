# AnalogForge vision context and scope

AnalogForge helps a mission team decide which Earth environment can support a particular Moon or Mars test. The recommendation is conditional on the experiment, equipment, available evidence, and analysis scale. The finished application must explain the recommendation, execute a modeled verification experiment, and preserve the evidence needed to challenge the result.

## Problem and value

Earth analog missions already exist. AnalogForge does not claim to invent them or replace planetary scientists. Its contribution is a repeatable workflow connecting mission intent, planetary context, terrestrial evidence, engineering constraints, and test execution. A terrain similarity statistic is an input to that workflow, not its final answer.

The central user is a rover engineer planning mobility and field sampling tests. Planetary scientists use the evidence comparisons; field planners use complementary site portfolios; educators use the explanation and passport. The core interface must support the engineer without making expert users read a chat transcript.

## Three product promises

1. Mission Fingerprint: state the conditions the experiment needs, which are mission objectives, which are rover hard limits, and which cannot be reproduced by choosing an Earth site.
2. Analog Qualification and Gaps: show PASS, PARTIAL, FAIL, GAP, or UNKNOWN for every requirement, supported by specific evidence and a stated scale.
3. PROVE IT: search for and independently evaluate a route that exercises the requested conditions while satisfying the modeled rover constraints. The experiment may invalidate an initially promising site.

## Complete experience

The user creates a mission and selects a Moon/Mars region. They enter or upload a rover profile. A requirements role proposes a structured contract, separating user-supplied facts from proposed defaults. The user accepts that contract. A run freezes both the contract and rover revisions, characterizes the planetary target, discovers Earth candidates, compares evidence, and undergoes scientific critique.

After selecting a candidate, the user requests verification. A test designer translates accepted requirements into a route benchmark. A deterministic solver proposes a route; an independent verifier recalculates its metrics. When a test fails, the application explains whether the evidence indicates a route, rover, site, data, requirement, search-budget, or system problem. It may change the route or site within a bounded policy. It cannot silently change the contract. The final passport records the outcome, including unsuccessful or inconclusive outcomes.

## Full version one versus first milestone

The full version one includes both planetary bodies, all ten agent roles, coarse-to-fine Earth discovery, compatibility assessment, portfolios, deterministic verification, review gates, immutable evidence, exports, cancellation/recovery, and authenticated deployment. Build a terrain-first vertical slice before adding the remaining capabilities. A milestone is an implementation order, not permission to ship mock functionality as completed work.

EMIT mineral and Diviner thermal adapters must exist as documented integrations with explicit coverage/access/error behavior. Their absence must not prevent a terrain-only mission, but must prevent PASS for a requirement that depends on their evidence. A field-sampling-access proxy is different from demonstrated mineral equivalence. All optional science features must have an honest unavailable state.

## Product boundaries

Version one performs modeled terrain and route feasibility, not flight qualification, soil-contact simulation, navigation-algorithm execution, hardware-in-the-loop testing, or autonomous physical deployment. Sensor presence can support task eligibility but does not prove navigation accuracy. A coarse DEM cannot certify centimeter-scale clearance or obstacle negotiation. A rover battery profile alone does not establish energy consumption: a declared energy model and coefficients are necessary inputs.

No ROS, F-prime, Isaac stack, arbitrary CAD/URDF ingestion, reinforcement learning, custom foundation model, or physical rover dependency belongs in the implementation baseline. Such integrations can consume exported benchmarks later without changing the evidence model.

## Success

An engineer can reproduce a recommendation from locked inputs and calculations; distinguish unavailable evidence from an unsuitable site; see a real critic challenge; inspect a computed failed benchmark; observe an eligible replan under unchanged requirements; and export a passport with resolvable source and result references. A successful software build must also produce truthful BLOCKED and INCONCLUSIVE results. A specific real site is not guaranteed to pass simply because the demo story prefers that ending.

## Source interpretation

The retained source documents in `references/` express product intent. Numeric examples, agent dialogue, candidate rankings, illustrative passes, and battery results are examples rather than observations. The architecture register resolves inconsistent example values. The brief is not a low-level architecture; this folder supplies that missing implementation detail.
