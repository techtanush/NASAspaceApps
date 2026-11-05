# Service boundaries (summary)

The authoritative, code-level definition is the frozen kit and [architecture 35](../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md). This page states the boundaries in one place for quick orientation.

## Boundary A — Frontend ↔ Platform (HTTP/SSE)

Aradhya's client is generated from `contracts/openapi.bundled.json`; Tanush's API conforms to it (every response validates against it, PLT-02). Statuses, selection pointers and cursors are server-owned; the UI never computes a scientific state. Scenario/lock ids come from `/capabilities`. SSE streams committed `RunEvent`s only. MSW mock mode exists only as a visibly bannered preview and cannot be built for production. The UI exposes every `data-testid` of `contracts/ui-testids.json`.

## Boundary B — Platform ↔ Science (Python port)

`ScienceService.execute(ScienceRequest, ScienceContext) → ScienceComputationResult`, loaded from `analogforge.science.facade:create_science_service`. Fifteen operations (`ScienceOperation`). The platform builds requests from frozen records, runs them in cancellable CPU subprocesses, and its **registrar** validates and persists the returned artifact/evidence **drafts** (result-local `local_key`s → UUIDs) in one fenced transaction. Science never touches DB/model/FastAPI/network-in-synthetic. Scientific verdicts live in payloads; `ComputationStatus` only says whether computation ran.

## Boundary C — Platform ↔ Renderer (Python port)

`PassportRenderer.render(PassportExportBundle, assets, fmt) → RenderedExport`, loaded from `analogforge.rendering.passport:create_passport_renderer`. The renderer is pure and deterministic. The platform owns assembly, manifest hashing (RFC 8785), authorization, storage and HTTP headers; the file digest and the manifest digest are different values.

## Boundary D — Data slot

Datasets enter through `data/incoming/<id>/manifest.yaml` ([36](../architecture%20files/36-DATASET-PLUG-IN-AND-NASA-SLOT.md)): validated by Ayan's `INGEST_LOCAL_DATASET`, locked and bound by Tanush's CLI. Practice, mock-drop and NASA data take the identical path.

## Test doubles

Each side tests against typed doubles that live only under `tests/` and implement the port: Tanush `tests/support/fake_science.py` (kit-valid canned results for the practice storylines) and `tests/support/fake_openai_server.py`; Ayan `tests/support/` registrar stub; Aradhya MSW fixtures (validated against the bundled OpenAPI) and a hand-built `PassportExportBundle` fixture set. Doubles are never importable from `src/`. Passing against a double is not integration; the merging agent replaces each double with the real entry point and reruns the same tests.
