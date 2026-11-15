# Aradhya ownership and independent execution

Own `analogforge/apps/web/src/**` including GlobeStage, EarthMap/PlanetaryPanel view composition, imagery/coverage/detail adapters under src/api, styles, routes, shared components, narrator/report and existing workbench integration. Own frontend mocks and `analogforge/tests/e2e/**`, UI-specific tests/scripts and frontend package/lock changes when necessary. Prefer existing dependencies.

Do not edit Python API/science/jobs, numerical algorithms, source ingestion, locks, source rasters, frozen contracts or published passport rendering algorithms. Do not modify Tanush's `apps/web/public/globe/data/**` or `public/globe/deliveries/**`; consume them. Existing root globe assets remain prototype fallbacks. Never copy a private registered raster into public/.

Only you edit `src/maps/globeAssets.ts`, `GlobeStage.tsx`, `coverage.ts`, `tour.ts` and frontend generated-client consumers. Tanush sends schemas/data, not competing TS implementations. The optional API projections remain disabled until delivered. Use mock fixtures conforming to the shared planning schemas and explicit Unknown/Unavailable fallbacks so every screen can be finished now.

Required design resolution: the new globe-first home/camera navigation differs from doc 41's workbench-first/no-hero/no-decorative-loop rules. Record the narrow Mission Control exception and rationale, update doc 41 and ONLY its architecture-baseline entry through the repository process. Preserve the existing workbench standard, scientific integrity, accessibility, glass contract, tokens and anti-gaming thresholds. Do not silently relax scans or call conflicting rules satisfied. Shared general schema changes stay with Tanush/integration.

Ask Tanush for a seam change by writing the expected request/response, unavailable case and reason in your STATUS/decision notes. Continue all unaffected work. Do not implement Part F backends, scraped imagery acquisition or an Aleph server inside the frontend branch.
