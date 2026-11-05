# Ayan scope and file ownership

Your implementation must operate as a reusable scientific library plus approved source adapters. It must not require a running web API, model call, browser session or SQL database to calculate terrain or verify a route.

## Owned production paths

- `analogforge/src/analogforge/science/`: typed facade, normalized scientific metadata, raster/planetary transforms, features, comparison, qualification math, compatibility math, routing, energy, verification, diagnosis, portfolio and analytic fixtures.
- `adapters/earthdata/`, `pds/`, `emit/`, `diviner/`, `user_survey/`, `source_http/`: metadata selection/download/decoding/quality and approved source HTTP behavior.
- `rendering/tiles/`: prepared scientific display images/legend/affine/CRS and mask overlays; images are derived presentation artifacts, not replacements for analytical arrays.
- `config/datasets.yaml`, `algorithms.yaml`, `candidates.yaml`: versioned source/feature/rule/search/candidate definitions. Do not introduce a hidden mission-default override here.
- Scientific suites under `tests/unit/science/`, `tests/property/science/`, `tests/integration/science/`, `tests/replay/science/`, `tests/fixtures/science/` and `scripts/science/`.

The longest-prefix registry governs exact path ownership. You own leaf initializers inside your packages; shared root package/adapters/rendering initializers, Python lock, application wrappers, settings, migrations and public domain/API schemas are Tanush's. Never change them without a recorded owner handoff. Add a small dependency request to your own handoff directory when a required decoder package is missing.

## Functional deliverables

1. Source registry and real locked source selections, with source-policy versus acquired-asset manifest distinction.
2. Correct Earth/Mars/Moon metadata/frame/scale/mask handling and comparable target/candidate features.
3. Bounded coarse-to-fine candidate discovery and controls, with documented exclusions and novelty scope.
4. Deterministic qualification/confidence/compatibility proposals using exact accepted requirements and evidence.
5. Frozen benchmark assembly, tasks, traversability graph, route search, exposure/diversity, energy and independent verification.
6. Supported failure diagnosis and legal repair suggestions; numerical module does not autonomously rewrite the mission or dispatch another role.
7. Portfolio coverage with co-location and honest gaps/unknowns, plus display-layer drafts.
8. Analytic/property/replay/actual-source tests and reproducible scientific reports.

## Persistence and orchestration boundary

Your facade returns computed proposals and content-addressed artifact/evidence drafts. Tanush allocates persisted UUIDs, resolves local keys, creates receipts and commits run/qualification/result state. You must not write DB rows, advance a run, construct fake receipt IDs or call the product's model. Supply enough typed data and lineage that the registrar can persist without guessing.

Your comparisons are scientifically deterministic; Tanush's policy validates the proposal against the run/evidence scope. A computation may be successful while its requirement result is FAIL/UNKNOWN. Keep execution status and scientific status distinct.

## Unsupported claims

Do not call a natural Earth site a complete Mars/Moon simulation. MOLA gives regional context, not wheel-scale stress. NASADEM cannot establish20cm clearance, actual autonomous navigation, traction or sample chemistry. Earth mineral evidence plus a MOLA-only target cannot prove mineral equivalence. A protected-download error is not evidence that terrain is unsuitable. A bounded/approximate search failure is not global infeasibility.

## Not your work

Do not scaffold another backend/frontend/database or implement Agent Council conversations. Do not edit global locks/migrations/contracts to fit your private representation. Do not add hardware/simulator/ROS dependencies excluded from the architecture. Leave UI/API/export authentication and model keys to the respective owners. Your dependency reports should make integration easy rather than leaving undocumented dictionaries for someone else to reverse engineer.

## Scientific responsibilities in owned files

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
