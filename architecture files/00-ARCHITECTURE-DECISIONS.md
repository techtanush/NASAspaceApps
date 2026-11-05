# Architecture decisions and precedence

This is the binding decision register for the AnalogForge implementation blueprint. The deliverable in this folder is a specification, not an implemented application. Prepared November 3, 2026, America/Los_Angeles.

## Authority

The human request and supplied AnalogForge brief define product intent. These architecture files resolve implementation details. Explicit contracts in `contracts/` govern wire formats; this decision register governs technical choices; numbered documents explain implementation; examples are fixtures, not scientific observations. Conflicts must be corrected before implementation rather than silently choosing whichever file is convenient.

## Product completeness

Build the complete mission-conditioned qualification workflow: mission and rover inputs, Moon and Mars target support, Earth candidate discovery, requirement qualification, explicit gaps and unknowns, rover compatibility, critic review, deterministic verification, failure diagnosis, bounded replanning, composite portfolios, provenance, and exportable passports. Execute in milestones, but do not redefine the full product as a static demo. NASADEM/SRTM Earth and MOLA/LOLA planetary terrain are the first required scientific adapters. EMIT and Diviner have specified adapters and honest no-coverage states; evidence-backed geology/thermal claims require their actual supported data or another approved source. A successful terrain-only run cannot claim successful mineral or thermal qualification.

## Chosen system

- Frontend: React 19, TypeScript, Vite, React Router, TanStack Query, MapLibre GL JS, accessible HTML/CSS. Use a single page workbench rather than a chat-led product.
- Backend: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3. Generate TypeScript clients from OpenAPI.
- Persistence: PostgreSQL 16 with PostGIS 3.4. Immutable revisioned domain records, append-only evidence and events. One local Docker Compose database; no SQLite alternative.
- Jobs: one separate Python worker using PostgreSQL job leases and `FOR UPDATE SKIP LOCKED`; SSE from committed run events. No Redis/Celery dependency.
- Science: rasterio/GDAL, NumPy, SciPy, pyproj, Shapely. CPU work runs in worker processes, not API request handlers.
- Artifact storage: local filesystem under configured `DATA_ROOT`, content-addressed blobs; an S3-compatible adapter is a later deployment option. Never put raster bytes in database rows.
- AI: server-side OpenAI Responses API, strict function calls, one configurable model shared by ten roles. `OPENAI_MODEL` must be explicitly configured and capability-tested; do not invent a current model name or require a specific expensive model. No other model provider is required for version 1.
- Mapping: no paid basemap key required. Default neutral basemap with bundled Earth outline and application-owned raster overlays. Optional external tiles require an explicitly configured licensed provider and attribution. Earth slippy-map tiles are not a planetary CRS.
- Deployment: Docker Compose locally; same API/worker/database architecture on a Linux server behind HTTPS. A static-only host cannot execute the raster worker.

## Runtime modes

`live`: real downloaded scientific products plus live model calls; missing required input blocks affected work. `replay`: previously computed, checksummed evidence and recorded operations, visibly labeled replay; no fabricated live calls. `synthetic`: analytic test rasters and scripted agent decisions, visibly labeled synthetic throughout; never relabel synthetic evidence as NASA data. Mode is immutable per run and attached to every evidence/output object.

## Shared invariants

- IDs are UUID strings. Timestamps UTC ISO 8601. Quantities use SI except explicitly named degrees, Wh, and percentages. Unknown numeric values are null, never zero or NaN.
- `QualificationStatus`: `PASS`, `PARTIAL`, `FAIL`, `GAP`, `UNKNOWN`. `GAP` means physically unavailable by natural Earth site selection; missing data means `UNKNOWN`.
- `VerificationOutcome`: `PASS`, `FAIL`, `INCONCLUSIVE`. A bounded search failure is not proof that no feasible route exists.
- `FailureCategory`: `ROUTE`, `ROVER`, `ANALOG`, `DATA`, `REQUIREMENT`, `SEARCH_LIMIT`, `SYSTEM`.
- Run states: `DRAFT`, `VALIDATING`, `CHARACTERIZING`, `DISCOVERING`, `QUALIFYING`, `CRITIQUING`, `AWAITING_REVIEW`, `DESIGNING_TEST`, `VERIFYING`, `DIAGNOSING`, `REPLANNING`, `BUILDING_PASSPORT`, `COMPLETED`, `BLOCKED`, `FAILED`, `CANCELLED`. Job states are separate.
- The accepted mission contract and rover revision are immutable for a run. Replanning may change route, test zone, or candidate within fixed requirements. Changing a mission threshold requires a user-accepted new contract revision and a new run. Never lower requirements to manufacture PASS.
- Qualification-only runs may pin no rover. Their rover revision is null, compatibility is unavailable, and PROVE IT is blocked. Adding a rover creates a new run with reusable scientific evidence, never mutates the old run. Natural-language Mission Fingerprint preparation is a separate pre-run job; accepted requirements are validated, not rewritten, inside a run.
- Deterministic tools produce quantitative truth; model roles request tools and propose decisions. Evidence references must resolve to persisted tool outputs. A server policy engine commits qualification and verification states.
- Scale must be attached to terrain measurements. Coarse DEMs do not establish centimeter-scale obstacles, clearance, wheel contact, traction, or actual autonomous navigation performance. Route results are modeled terrain-feasibility assessments under stated assumptions.
- Planetary source geometry carries body, longitude convention, horizontal CRS and vertical datum. Do not insert planetary geometry into Earth PostGIS SRID 4326. Earth GeoJSON alone uses WGS84 longitude,latitude.
- Logs contain tool names, sanitized input summaries, evidence, decisions, and results; no private chain-of-thought or secrets.
- API prefix `/api/v1`; errors use a consistent structured envelope; mutations use idempotency keys and revision guards. IDs and records are scoped to a workspace.

## Fixed baseline scenario

ARES-1: 42 kg, maximum safe slope 18 degrees, clearance 0.20 m, wheel diameter 0.30 m, battery 1800 Wh, minimum reserve 20 percent, nominal speed 0.5 m/s, stereo/IMU/LiDAR, navigation and geological sampling capability. Candidate sites and mission exposure thresholds are scenario assumptions until accepted. The pasted text's 0.22 m clearance is superseded by the DOCX's 0.20 m baseline; comparisons must still use uploaded profile values. No uncomputed candidate receives a PASS.

## Documentation responsibilities

Each document must include concrete behavior, implementation boundaries, input/output references, failure handling, and acceptance criteria. Each external dataset/service claim must cite an official source or explicitly be a proposed design choice. External credentials are setup dependencies, not values to invent or collect into these files. Exact software patches, data granules, checksums, and available model identifiers are resolved during preflight and recorded in a lock manifest.

## Binding scientific claim policy

Apply [33 scientific credibility and claim gates](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) to every scientific result and final passport. Deterministic backend audits enforce SC-01–SC-15, immutable evidence and exact claim scope. The C1 passport contract requires assurance_evidence_id. Scientific limitations cannot be waived by model prose or user review; truthful negative/unknown reports are legitimate outcomes.
