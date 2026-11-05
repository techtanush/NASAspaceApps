# Analog Passport, provenance and export implementation

The passport is the durable result of an investigation. It must remain useful when the application is closed and must preserve limitations as carefully as positive results. Follow [00-ARCHITECTURE-DECISIONS.md](00-ARCHITECTURE-DECISIONS.md), [05-DOMAIN-MODEL-AND-CONTRACTS.md](05-DOMAIN-MODEL-AND-CONTRACTS.md), [06-DATABASE-AND-STORAGE.md](06-DATABASE-AND-STORAGE.md), and the authoritative contracts for exact fields. The server owns publication and hashing; the frontend renders an immutable snapshot.

## 1. Passport types and publication boundary

A **draft preview** can be displayed before the workflow completes, but carries a conspicuous draft/incomplete label and a list of unresolved stages. A **published passport** references a frozen mission revision, optional pinned rover revision, runtime mode, assessed candidate(s), exact qualification/evidence versions, critic review, test attempts and residual gaps/unknowns.

Published passports are immutable. New evidence, a new test, an accepted new mission or a changed rover creates a new passport revision/record linked to its predecessor; never overwrite an already downloaded report while retaining the same ID/digest. A terminal run may legitimately publish:

- A supported recommendation with a scoped modeled test `PASS`.
- A limited recommendation with unresolved dimensions or partial evidence.
- A negative recommendation after failed required benchmarks.
- An inconclusive result because data/search limits prevent a decision.
- A site-only qualification with no rover verification.
- A composite campaign proposal with separate site results and residual gaps.

Workflow `COMPLETED` is not a passport scientific `PASS`. A cancelled/failed run may expose a partial investigation record, clearly distinguished from a completed final passport.

## 2. Required report structure

### 2.1 Cover summary

Show AnalogForge title, mission name/ID and accepted revision, target body/region, runtime mode, generated/published timestamp, passport ID/revision and short scoped outcome. Include pinned rover name/revision when present; otherwise **No rover supplied — site qualification only**.

Lead with **Qualified for these tests under these assumptions**, or **No supported recommendation under the accepted contract**. Do not lead with a generic green badge or “Mars readiness”. Summarize the top supported uses, critical unknowns and irreproducible conditions within the first page/viewport.

### 2.2 Mission Test Contract

Include objective, accepted requirement IDs, priorities, hard constraints, desired exposures, measurement/comparison scale, target geometry metadata and accepted assumptions. State who/what supplied numeric thresholds: user, evidence-derived rule or proposed assumption accepted by the user. Include accepted revision digest and freeze time.

### 2.3 Target and Earth site characterization

For target and each site: region, body/coordinates, source products, source/effective resolution, no-data coverage, terrain/environment summaries, relevant acquisition/time context and uncertainty. Use comparable axes/scale where valid. Include a small static map/profile with a full table alternative. Earth location maps are geographic context, not access authorization.

### 2.4 Qualification matrix

One row per accepted requirement per candidate/portfolio assignment. Include requirement ID, observable/rule, target and Earth measurements with units, `PASS`/`PARTIAL`/`FAIL`/`GAP`/`UNKNOWN`, measurement/proxy type, evidence-strength description, evidence IDs and material limitation. Pending required analysis is not a final `PASS`; explain unresolved state if publishing a limited report.

Keep gap/unknown/fail distinctions:

- `GAP`: cannot be reproduced by natural Earth site selection.
- `UNKNOWN`: relevant evidence is absent, incompatible, too uncertain or not processed.
- `FAIL`: analyzed evidence does not satisfy the defined rule.
- `PARTIAL`: only a defined subset/proxy is supported under policy.

No single planetary-likeness percentage appears. Supported-requirement counts may be used with exact denominator and treatment of gaps/partial/unknown, without implying flight readiness.

### 2.5 Rover compatibility

List declared rover limits/capabilities, site/test demand and compatible/violated/unknown assessment. Distinguish preliminary site-level checks from route-specific computed checks. Unknown obstacle/clearance stays visible when the available terrain scale cannot resolve it. A declared sensor or sampling instrument is not observed navigation/sampling performance.

Include energy-model parameters, mass/gravity assumptions, task consumption, reserve rule and uncertainty. Do not silently apply planetary gravity to an Earth field-energy calculation. Model assumptions remain explicit in both human and machine exports.

### 2.6 PROVE IT and attempt history

The first PROVE IT authorizes design and verification within already reviewed mission/rover criteria. A pre-click benchmark preview is not an executed or frozen route. The passport includes only subsequently committed test/attempt artifacts. If design introduces a material new assumption/proxy, dependent computation pauses for exact-scope review; approval receipts remain distinct from the accepted mission contract and cannot relax its thresholds.

For every relevant attempt: ID, parent ID, selected candidate/zone, route/test version, rule set, date/tool version, outcome, failed benchmark(s), measurements/residuals, failure category and diagnostic scope. Route result is labeled **modeled terrain-feasibility verification**.

For an eventual pass, show what changed and what stayed fixed. Example safe wording: “Attempt 1 lacked required reachable slope exposure in the modeled test zone. Attempt 2 moved the test zone; the accepted exposure thresholds and rover limits were unchanged.” Do not print “passed after one replan” unless there are exactly the corresponding persisted attempts and receipts.

For bounded search exhaustion, state explored budget/domain and `INCONCLUSIVE`; do not claim no route exists unless a supported exhaustive/certified check establishes that claim for a defined model/domain. If no test was executed, explicitly state **Not verified** and why.

### 2.7 Composite portfolio

If selected: include site responsibilities, requirement-to-site mapping, site-specific outcomes, co-location rules, optimizer objective/budget, modeled site-count penalty and residual gaps/unknowns. List unmodeled logistics, access, costs and permissions. Do not imply simultaneous conditions are satisfied by independent campaigns.

### 2.8 Critic and limitations

Summarize material critic challenges, resulting evidence changes and unresolved concerns. List methodological limitations: source scale, proxy interpretation, vertical datum, terrain model, energy model, unmeasured soil/mechanics, temporal mismatch and dataset coverage as applicable. Do not use a generic disclaimer to conceal the exact unsupported requirement.

### 2.9 Next action and provenance appendix

Suggest the smallest justified next step: acquire specific evidence, analyze another region, execute a separate field measurement, revise requirements through a new accepted contract, or use a specialized facility for a physical gap. These are recommendations, not automatic external actions.

Append source/derivation/tool/evidence lineage, artifact checksums, manifest digest, mode, recorded replay origin, report generation version and authorized source links. Exclude credentials, private prompts and chain-of-thought. Safe operational decision summaries are allowed.

## 3. Machine-readable snapshot and provenance manifest

The JSON export contains the complete published passport object plus a self-describing provenance manifest and version. Generated contract types govern exact JSON names. Required semantic content:

| Manifest section | Content |
|---|---|
| Identity | Workspace-scoped passport/run IDs, schema version, runtime mode, publication/revision information. |
| Accepted inputs | Mission revision/digest; optional rover revision/digest; user-accepted assumptions; target geometry/CRS metadata. |
| Sources | Frozen source-policy/product-version lock hash; final append-only acquired-asset manifest hash; actual product/granule IDs, source URIs, source file SHA-256, versions, acquisition context, license/attribution. |
| Derived artifacts | Content-addressed IDs/checksums, tool/algorithm versions, parameter hashes, input refs, scale/grid/no-data metadata. |
| Decisions | Qualification policy version, exact state rows and evidence refs, critic challenge/resolution refs, accepted reviews. |
| Tests | Test/attempt/route/result IDs and digests, parent lineage, benchmark outcomes, failure categories and fixed-contract refs. |
| Portfolio | Selected sites/assignments/objective receipt where applicable. |
| Limitations | Material assumptions, unsupported dimensions, uncertainty, gaps, unknowns and coverage/search bounds. |
| Runtime | Environment/data lock manifest reference, software build identifier, model/config identifier where permitted, replay origin. |

IDs alone are insufficient provenance when a mutable reference could change. Pair scientific input/output references with immutable versions/content hashes. User assumptions stay distinct from measured facts. A source URL may be unavailable later; local evidence hashes and manifests remain inspectable. Do not include credential-bearing signed URLs or session tokens in the manifest.

Source discovery may append permitted new granules to a new immutable acquired-asset manifest revision during a run; it cannot change the frozen source policy or replace bytes behind an existing evidence/derivation hash. Final publication locks the exact acquired inputs actually used and their lineage. New product versions or interpretation-policy changes require the documented new-run process.

## 4. Digest algorithm and integrity semantics

Use exact field name **`manifest_sha256`**. It is a digest of the scientific provenance manifest, not a signature, certification or evidence that NASA endorses a result.

Server algorithm:

1. Construct the immutable manifest from persisted approved records and source/derived hashes.
2. Exclude `manifest_sha256` itself, self-signature fields and export-file bytes/metadata that would create a circular dependency.
3. Validate finite JSON numbers, rejecting NaN/infinity and integers outside the JSON-safe numeric range. Preserve identifiers as strings. The domain schema defines units and numeric representations.
4. Canonicalize with **RFC 8785 JSON Canonicalization Scheme**, using the pinned Python `rfc8785` implementation specified in the environment lock.
5. Compute SHA-256 over the resulting canonical UTF-8 bytes. Persist the manifest bytes and digest as immutable artifacts.
6. Generate report files referencing that digest. Compute a separate SHA-256 for each exact exported file; file digests are export metadata, not folded back into the scientific manifest.

Frontend displays the server-published digest. It must not hash arbitrarily stringified JavaScript JSON and claim parity. An optional verifier must use the same canonicalization rules and the exact manifest, not the human-readable HTML text.

A digest proves byte/content consistency with a referenced manifest, not scientific correctness. Evidence verification can establish that locally available blobs match declared hashes. An authorized verifier also checks reference resolution, mode consistency and domain rules. Missing blobs produce **Integrity not fully checked**, not **Verified**. Corrupted inputs block publication of a supposedly intact new passport.

## 5. Export formats and generation

Use `GET /api/v1/passports/{id}` for the published snapshot and `GET /api/v1/passports/{id}/exports/{format}` for available formats, as defined in OpenAPI. Access checks apply to each dependency and export. Return precise content type, safe attachment filename, byte size, content digest and immutable cache identifier where the API supports them.

### 5.1 Printable self-contained HTML (`html`)

Server-render a standalone UTF-8 HTML document using an escaped template. It contains readable semantic headings, tables, source links, inline styles and embedded report images/SVG generated from persisted artifacts. It must open offline without executing React, downloading a map library or requesting external tiles. If report imagery is unavailable, display the relevant tables and explicit image-unavailable note; never substitute a fictional map.

Use application-controlled SVG generation with sanitized labels, or raster thumbnails from the artifact service. Do not embed arbitrary model-authored SVG/HTML. No JavaScript is necessary. Limit report-image dimensions/byte budget and label display aggregation; retain original scientific artifact links/digests separately.

Print CSS: light background, high-contrast text, repeated table headers, sensible page breaks, rows/cards kept together where practical, route legends, full units and visible links/IDs. Passport title and mode appear early; mode remains visible on continuation pages via the supported print layout. Large matrices can print by site/requirement sections instead of unreadable tiny columns. Avoid fixed-height scrolling containers and clipped tables.

The browser's **Print / Save as PDF** is available to the user. There is no required server PDF renderer, headless-browser service, paid API or separate PDF generation dependency. Do not return HTML bytes under a `.pdf` filename.

### 5.2 JSON (`json`)

UTF-8 `application/json`, schema/version metadata, exact structured passport and manifest. Preserve numerical values/units/unknown nulls and all ID relationships. The export must validate against the published contract and be round-trip loadable by a verifier. Human presentation rounding is not applied. No user/model prose may override machine outcomes.

### 5.3 Qualification CSV (`csv`)

The base CSV export is one rectangular UTF-8 qualification table, one row per requirement per assessed site. Required conceptual columns: passport/run/mode, mission revision, rover revision if present, candidate/site, requirement ID/text, priority, qualification status, observable, rule/threshold, unit, target value, Earth value, comparison scale, evidence type/strength, limitation, evidence IDs, critic state, related verification outcome and `manifest_sha256`.

Wire/export column names are documented in the implementation and tested for stability. Unknown cells are empty with explicit status/reason columns; never numeric zero. Multiple evidence IDs use a documented safe delimiter within a quoted field. Proper CSV quoting handles commas, quotes and newlines. User-supplied cells beginning with spreadsheet formula triggers are neutralized for spreadsheet-safe export while JSON retains original text.

Additional benchmark/route-sample CSV exports may be added only with explicit API formats or a documented archive format. Do not concatenate heterogeneous tables into one invalid CSV or return a ZIP while claiming `text/csv`. Full attempt/route detail is already in JSON/artifact references; the base CSV does not pretend to be the whole investigation.

## 6. Export job and publication behavior

Passport assembly validates all references before publication. Export rendering may run as a worker job if required; a request for a format not yet ready returns the documented pending response and retry link/status, not a broken download. Download controls show **Preparing**, **Ready** or a safe failure reason. Retrying export generation is idempotent for the same passport/template version.

Use immutable export paths keyed by passport snapshot and renderer/template version. To regenerate with a materially changed template, create a new export rendition reference and file digest while preserving the scientific manifest and prior file. Do not mutate existing bytes behind a previously published file checksum.

If evidence access is revoked or a referenced blob is missing before export generation, return the appropriate authorized error/incomplete-integrity state. Never include cross-workspace evidence merely because it was named in a model response.

## 7. Privacy, escaping and download safety

Server template autoescaping is mandatory. Source links come from vetted metadata and use allowed URL schemes; no `javascript:` or credential-bearing links. Sanitize filenames; do not use raw user mission names as filesystem paths. Artifacts are resolved by internal IDs/content hashes through storage service, not client-provided file paths.

Receipt summaries exclude secrets, headers and private reasoning. Input JSON includes only intended profile/mission fields, not arbitrary uploaded surrounding file contents. CSV injection mitigation and HTML escaping have dedicated tests using malicious mission/requirement names. The report contains no external tracking pixels or hidden analytics.

## 8. Required consistency checks before publication

- Every accepted requirement appears in report or explicitly references a visible unresolved section.
- Qualification rows cite persisted evidence and the correct current assessment revision.
- Rover/test uses the same pinned profile revision; site-only reports do not invent a rover.
- All attempts retain the accepted contract digest; any changed contract belongs to a different run.
- Final result follows benchmark/policy rules; unresolved required benchmarks cannot silently be summarized as all passed.
- Composite assignments respect co-location rules and retain residual gaps.
- Mode and replay origin are consistent across evidence, report, timeline and exports.
- `manifest_sha256` resolves to stored canonical manifest bytes; all present blobs match their declared hashes.
- HTML, JSON and CSV agree on IDs, units, states, limitations and digest.

## 9. Acceptance criteria

| ID | Required verification |
|---|---|
| PASS-001 | Positive, negative, inconclusive, composite and no-rover passports all publish/export with correct scoped language. |
| PASS-002 | HTML opens offline with no external network requests and prints without clipped core tables or hidden gaps. |
| PASS-003 | JSON validates, preserves unknown nulls and retains all required source/attempt relationships. |
| PASS-004 | CSV parses as one rectangular table and neutralizes spreadsheet formula input without corrupting quoted text. |
| PASS-005 | Independently canonicalized manifest reproduces server `manifest_sha256`; changing a limitation or evidence hash changes it. |
| PASS-006 | Export-file SHA changes when exact bytes change while scientific manifest digest remains stable for presentation-only rendition changes. |
| PASS-007 | Synthetic/replay labels remain visible in every format; a real-data replay retains original receipt dates/source hashes. |
| PASS-008 | A 0.20 m clearance claim is unknown when evidence cannot resolve that scale; report never upgrades it to measured safe traversal. |
| PASS-009 | Earlier failed attempts and unresolved critic challenges remain accessible in the final artifact. |
| PASS-010 | Tampered, missing or unauthorized evidence cannot be represented as fully integrity-verified. |
| PASS-011 | Malicious text/links cannot execute HTML/JavaScript or spreadsheet formulas; secrets never enter export files. |
| PASS-012 | Refreshing/downloading an immutable published export yields the same published bytes/digest for that rendition. |

## Required assurance section and publication check

Include required assurance_evidence_id in the passport and manifest, plus resolved audited claims/gates in PassportExportBundle. Display exact permitted conclusions, mode/validation level, critical limitations and audit reference in HTML/JSON; flattened CSV preserves per-row status/scope/limitations and assurance reference. A blocked audit cannot issue a final passport. ALLOWED may describe a supported FAIL; LIMITED describes honest unresolved/nominal scope. Renderer never upgrades the decision. Apply [33](33-SCIENTIFIC-CREDIBILITY-AND-CLAIM-GATES.md) and shared SCI presentation/export tests.
