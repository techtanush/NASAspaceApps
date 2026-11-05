# Ayan — interfaces and handoffs

Everything you exchange with the other branches is a **frozen kit type** ([35](../../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)). There are no mid-build handoffs: you deliver a branch that works against the kit, and the merging agent connects it.

## You provide

| Entry point (fixed dotted path) | Consumer | Contract |
| --- | --- | --- |
| `analogforge.science.facade:create_science_service` → `ScienceService` | Tanush's worker | `supported_operations()` = all 15; `execute(request, context)` per `08` §4 |
| `analogforge.science.fixtures.practice:generate_all(out_dir) -> list[str]` | `analogforge datasets generate-practice` | Writes the practice datasets (data + `manifest.yaml`) under `out_dir/<dataset_id>/` |
| `analogforge.science.fixtures.mock_nasa_drop:generate(out_dir) -> list[str]` | `analogforge datasets generate-mock-nasa-drop` | Writes the mock NASA drop (architecture 39 §5) |
| `analogforge.science.datasets.inspect:draft_manifest(dataset_dir, body, role) -> dict` | `analogforge datasets scaffold` | Draft manifest with `TODO_FILL_IN` provenance fields |
| `config/{datasets,algorithms,candidates}.yaml` | Tanush's preflight (parses strictly) and your facade | Keys per architecture 35 §7 |

## You receive (from the kit; you cannot change it)

`ScienceRequest`/`ScienceContext` (`ports.science`), operation inputs/payloads and artifact formats (`ports.science_payloads`), `DatasetManifest` (`ports.datasets`), hashing (`ports.hashing`), shared ids/budgets/oracles (`ports.catalog`), domain value types (`ports.domain_models`). The platform supplies the context: `scratch_dir()`, `read_artifact(sha)`, `local_dataset_root(id)`, `check_cancelled()`, `report_progress()`, `http_client()` (live only).

## What the platform will do with your output (so you can make it registrable)

The registrar (architecture 35 §3.3) re-hashes every artifact from `scratch_dir()/scratch_relpath`, topologically orders your evidence by `parent_local_keys`, resolves every `EvidenceRef(local_key=…)` in your payload, rejects dangling keys, enforces `SYNTHETIC_` naming by mode and rejects `source_uri` with query strings. **Your `tests/support/registrar_stub.py` must enforce exactly these rules** so your suite catches a rejection before the merge.

## What Aradhya's UI shows from you

Metric names/units/support scale/valid fractions, benchmark rows (`constraint_id`, rule text, measured, threshold, margin, status), violations, telemetry samples, display-layer manifests (corners/affine/legend/attribution) and limitation strings. Write limitation strings as short, specific, user-facing sentences (they appear verbatim in the passport): e.g. *"Terrain model at 60 m support; cannot resolve 0.20 m obstacles."*

## Defects you find elsewhere

Record in `STATUS.json.defects_in_other_areas` with a reproduction; never edit another owner's files. If the kit blocks you, `team handoffs/ayan/CHANGE-REQUEST-<n>.json` plus a local workaround.

## Dependencies you need

Put science-only packages in `extra-ayan` of `pyproject.toml` (e.g. `numba` only if truly needed; prefer numpy/scipy). No dependency may need network at import time or a compiler at install time on a clean machine without a documented reason. Never commit `uv.lock`.
