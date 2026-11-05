# Tanush — interfaces and handoffs

All seams are frozen kit types ([35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)). There are no mid-build hand-offs; the merging agent connects the three branches.

## You consume (load via `importlib`; never import at module top level)

| Entry point | Provider | How you use it |
| --- | --- | --- |
| `analogforge.science.facade:create_science_service` | Ayan | Build `ScienceRequest`s from frozen records; run `execute` in a CPU subprocess with a `ScienceContext` you implement (`scratch_dir`, `read_artifact`, `local_dataset_root`, `check_cancelled`, `report_progress`, `http_client`); register the result with the registrar |
| `analogforge.rendering.passport:create_passport_renderer` | Aradhya | Assemble a `PassportExportBundle` + `ProvidedAsset`s; call `render` per format; store bytes; serve |
| `analogforge.science.fixtures.practice:generate_all`, `…mock_nasa_drop:generate`, `analogforge.science.datasets.inspect:draft_manifest` | Ayan | Called by the dataset CLI |

If an entry point is absent, preflight reports `SCIENCE_FACADE_MISSING` / `RENDERER_MISSING` and run creation for scenarios that need it fails with a named `503`; **no fallback object is constructed in `src/`**.

## You provide

| Artifact | Consumer | Contract |
| --- | --- | --- |
| A server whose responses validate against `contracts/openapi.bundled.json` | Aradhya's client, MSW fixtures, e2e | PLT-02 |
| `GET /capabilities` scenario list per architecture 40 §10, `GET /configuration/scenarios/{id}` | Aradhya's UI | scenario/lock ids are never guessed by the UI |
| SSE `RunEvent`s and durable operation/receipt/critique/review/display-layer reads | Aradhya | architecture 07 |
| `PassportExportBundle` + assets | Aradhya's renderer | architecture 35 §4 (assembly guarantees) |
| `ScienceContext` implementation | Ayan's facade | per `ports.science.ScienceContext` |
| `config/scenarios.yaml` | Ayan (reads scenario source selectors via requests only) | architecture 35 §7 |
| Dataset CLI and lock files | operators | architecture 36 |

## Doubles you write (tests only)

`tests/support/fake_science.py` returns **kit-valid** `ScienceComputationResult`s for the storylines of architecture 40 §6, built through the kit models with real artifact bytes on scratch (so the registrar's hashing is truly exercised). `fake_renderer.py` returns deterministic bytes per format. `fake_openai_server.py` serves a local Responses-API-shaped endpoint (strict tool calls, refusal, malformed, timeout modes). The merging agent replaces the first two with the real entry points and reruns the same tests.

## Defects you find elsewhere

`STATUS.json.defects_in_other_areas` with a reproduction; never edit another owner's files. Kit blockers: `CHANGE-REQUEST-<n>.json` + local workaround.

## Dependencies

Platform-only packages go in `extra-tanush`. You own `uv.lock`; regenerate it only from the committed `pyproject.toml`. Because the merged `pyproject.toml` will also contain Ayan's and Aradhya's extras, your `uv.lock` is **re-locked by the merging agent** — do not hand-edit it to anticipate them.
