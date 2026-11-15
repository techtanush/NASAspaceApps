# Reviewed operator context v1

This optional API is outside the frozen 43-operation contract. It stores mission background documents, rover supporting documents and custom rover features as **untrusted context**. It does not add scientific evidence, approve operating limits, modify a saved numeric RoverProfile or change qualification algorithms.

All paths below start with `/api/v1`. Reads require workspace membership and return `Cache-Control: no-store`. Mutations require Owner/Editor membership, a UUID `Idempotency-Key`, the existing exact-origin policy and session CSRF token when configured OIDC authentication is used. Local mode retains the automatic local Owner identity and loopback restriction.

| Method and path | Request / result |
| --- | --- |
| `POST /operator-documents` | Raw file bytes; `Content-Type` matching its extension and `X-Upload-Filename: encodeURIComponent(filename)`. Returns a Document, 201. |
| `GET /operator-documents/{id}` | Document metadata and extracted text, scoped by document ID rather than hash. |
| `GET /operator-documents/{id}/content` | Original bytes as an attachment; a hash alone grants no download access. |
| `POST /operator-contexts` | Reviewed ContextInput below; returns immutable Context, 201. |
| `GET /operator-contexts/{id}` | Exact immutable reviewed Context. |
| `GET /operator-context/preview` | Optional `mission_context_id` and `rover_context_id` query parameters; validates the combined budget and returns Snapshot. No parameters returns absent context. |
| `GET`, `POST /missions/{id}/operator-context` | Current exact draft binding. POST requires `expected_revision`, `expected_context_revision`, `context_id`, `context_sha256`; returns Binding, 201. |
| `GET`, `POST /rover-revisions/{id}/operator-context` | Exact saved rover revision sidecar. POST requires `expected_context_revision`, `context_id`, `context_sha256`; returns Binding, 201. |
| `GET /preparations/{id}/operator-context` | Context frozen when preparation was enqueued. |
| `GET /mission-revisions/{id}/operator-context` | Context frozen with the proposed scientific revision. |
| `GET /runs/{id}/operator-context` | Context frozen at run admission; never the current editable binding. |
| `POST /operator-context/runs` | `{run_request: <unchanged frozen createRun body>, expected_rover_context_id: <uuid or null>}`; returns the existing run command, 202. Rejects a reviewed rover sidecar race. |

Document fields are `schema_version: "operator-document.v1"`, `id`, `workspace_id`, `created_at`, `filename`, `media_type`, `size_bytes`, `original_sha256`, `extracted_text`, `extracted_text_sha256`, `extraction_status`, `text_truncated`, `page_count`, `parser: {name, version}`, `source_kind: "OPERATOR_UPLOAD"`, `trust: "UNTRUSTED_CONTEXT"`, and uploader provenance. Filenames are sanitized display basenames, never storage paths. Original bytes and extracted UTF-8 text have separate private CAS hashes.

Extraction supports UTF-8 TXT/MD/JSON, DOCX and PDF. Limits: 2 MiB/file; 64,000 extracted Unicode characters; 40 PDF pages; 8 MiB decoded content; DOCX at most 128 ZIP members and 200:1 per-member expansion. Encrypted, malformed, unsupported or oversized content fails explicitly. Extraction status is `EXTRACTED`, `TRUNCATED` or `NO_TEXT`; scanned/image-only PDFs do not acquire fictional OCR text. PDF extraction may differ from visual layout and must be reviewed. Parsing uses a disposable credential-free subprocess with a 10-second wall deadline, 5-second CPU limit and 384 MiB Linux address-space/macOS RSS bound. Each API process permits one extraction; durable actor/workspace accounting permits six attempts/minute, including failed attempts.

ContextInput is:

```json
{
  "schema_version": "operator-context.v1",
  "kind": "MISSION",
  "rover_revision_id": null,
  "documents": [{"document_id": "<uuid>", "reviewed_excerpt": "Exact extracted substring"}],
  "features": [],
  "reviewed": true
}
```

`ROVER` requires its exact `rover_revision_id`; only rover contexts accept features. A feature is `{name, value, unit, unknown}`: name 1–100 characters, declared value 1–500 characters or null, unit 1–40 characters or null. `unknown` must equal whether value is null. Names must be distinct ignoring case/outer whitespace. Strings/excerpts otherwise retain their exact whitespace. A nonempty excerpt must be an exact substring of the stored extraction. Empty excerpts retain document provenance without exposing text to the model. Context responses add `id`, workspace/time, `reviewed_by`, `context_sha256`, `model_visible_chars`, and trust; document selections expand with `filename`, `original_sha256`, `media_type`, `extraction_status` and `text_truncated`.

Binding fields are `schema_version: "operator-context-binding.v1"`, `target_kind`, exact `target_id`, `context_revision`, `context_id`, `context_sha256`, `context`, and `mission_revision`. An initial binding has context revision 0 and null context. Mission binding increments MissionHeader.revision and returns the new `mission_revision`; use it for the frozen fingerprint request. A stale revision returns 409. Passing null context/hash appends a removal binding. Originals, previous contexts and old pins remain private immutable audit records.

The exact model-visible Snapshot payload is `{schema_version: "operator-context-snapshot.v1", mission_context, rover_context, trust: "UNTRUSTED_CONTEXT", scientific_authority: "NONE", qualification_supported: false}`. Each model context contains `context_id`, `context_sha256`, `kind`, `rover_revision_id`, expanded `documents`, `features` and trust. Combined canonical RFC8785 JSON must be at most 12,000 Unicode characters, with at most six distinct documents and 32 features. Snapshot responses additionally return `snapshot_sha256`, `model_visible_chars`, `mission_context_id`, `rover_context_id` and `lineage_pinned`; these response-only fields are excluded from the payload/hash/count. Absent context returns null snapshot hash, null contexts and count 0. Newly prepared revisions also retain an explicit immutable empty pin (`lineage_pinned: true`), so adding a rover context later requires new preparation/review. Historical records without a pin return false. The preview endpoint supplies exact server accounting.

Preparation source hashes include the pinned context hash when present. Proposals remain unaccepted and undergo existing deterministic validation. Acceptance does not validate document claims. Run admission uses the accepted mission revision's context and rejects drift from a prepared rover context. Existing context-free requests retain their behavior. Role `get_run_snapshot` reads expose the pinned payload separately from authoritative inputs, under privileged instructions that documents cannot override policy and custom features remain declared context/UNKNOWN for qualification.

Parser versions are pinned to [pypdf 7.1.0](https://pypi.org/project/pypdf/7.1.0/) and [defusedxml 0.7.1](https://pypi.org/project/defusedxml/0.7.1/). PDF bounds follow the parser's [security configuration](https://pypdf.readthedocs.io/en/stable/user/security.html) and [extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html). No external document service or model call is used for extraction.
