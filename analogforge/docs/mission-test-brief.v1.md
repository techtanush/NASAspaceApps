# Mission and location test briefs

These optional authenticated read projections do not modify the frozen passport, scientific contract, accepted
requirements, run state, results, request budgets or source policy.

- `GET /api/v1/runs/{run_id}/candidates/{candidate_id}/evidence-brief.pdf`: complete current site evidence,
  executive summary, methods, final coordinates, field-planning reference, simple graphs and technical appendix.
- `GET /api/v1/runs/{run_id}/test-brief.pdf`: one dossier containing a location directory and a bookmarked concise
  section for each investigated site. Failed sites remain visible. Full raster images and audit appendices remain
  in the individual PDFs. Bound: 1–8 sites, 120 total pages; an individual PDF retains its 40-page bound.
- `GET /api/v1/runs/{run_id}/candidates/{candidate_id}/test-plan`: the same site-owned field-planning data for
  the online report. This is not a new route solver or a physical readiness assessment.

All reject query parameters, validate UUIDs, require the current principal/workspace, verify pinned run membership
and return private/no-store content. PDF responses identify the run revision and exact snapshot/PDF hashes.
The dossier is assembled from one transactional run snapshot; each reduced site snapshot has its own updated digest.
Existing bounded isolated PDF execution, concurrency, input/output bytes, memory, CPU and wall-clock limits apply.
No network calls, source acquisitions or model calls occur during a download.

## Route admission

Only the selected site's latest pinned experiment can supply route endpoints. Require its exact accepted mission,
rover, candidate window, constraints digest and route digest, a matching successful VERIFY_ROUTE request/receipt
and scientific invocation, and the scoped immutable verifier artifact. Its registered payload, result outcome,
metrics and route digest must agree. Geographic geometry and tasks are bounded; every displayed point must lie
inside the selected site. Abstract graph fixtures cannot become geographic driving instructions.

Geographic task coordinates come from their saved location or the same executable route's task/node geometry;
they are never borrowed from another site. Start, ordered checkpoints, finish and the north-up coordinate schematic
are planning references. Regional cells cannot establish wheel-scale clearance or a safe driving corridor.
Uncomputed, newer incomplete, corrupt or foreign routes show no endpoints. Reference region centres are explicitly
not route starts. Coordinate display digits do not establish survey accuracy.

## Reading the plan

1. How the site was found: accepted target, registered regional screening, dataset lock and analysis support.
2. Where it is: final Earth region bounds and reference centre, with each site kept distinct.
3. Where to where: recorded route endpoints and checkpoints when admitted; otherwise an explicit missing-route state.
4. What to exercise: accepted criterion dimension/observable and any task's recorded required capability.
5. Benchmark: exact mission limits and stored measured verdict; separate table of modeled route checks.
6. Before field execution: access/permit review, rover-scale survey, operator-approved plan, calibrated telemetry and
   task observations. These procedural recommendations are not invented scientific measurements or accepted thresholds.

When only terrain criteria were accepted, the document says so. It cannot invent a component-level acceptance test,
route requirement, guaranteed transfer to planetary conditions, confidence percentage or material sampling evidence.
Generated tasks, default solver bounds and assumed energy calibration retain the original recorded assumptions.
Earth testing reduces uncertainty; it does not assure mission success on Mars or the Moon.

The PDF navigation sidebar provides section/site bookmarks (the requested per-location document tabs). Source text
is escaped; it cannot introduce scripts, external fetches, file references or PDF actions. The existing immutable
passport remains a separate artifact with its independent publication audit.
