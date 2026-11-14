# Independent Ayan branch review

User requested a single-agent review here: read architecture first, execute the original branch before debugging, then fix reproduced defects. No subagents or other chats are used for this review.

## Starting point and baseline

- Checked out/pulled `ayan/science-data-verification` at `6856046`; accepted main base is `36cd52c` (C3 already included). Other branches remain untouched.
- Read all Ayan guides, common builder protocol, mandatory architecture34–40, and relevant scientific architecture08–13/18/26/29/33 plus shared SCI gate. Existing architecture is authoritative; frozen kit is unchanged.
- Materialized the missing exact kit copies, verified them, and created a fresh Python3.12.13 venv with `.[dev,extra-ayan]` and the handoff's rasterio1.4.4 constraint. All six required GDAL drivers are available. No uv.lock generated/committed.
- Original unmodified source passed: kit20, science+property+integration+contracts+replay973 with zero skips, Ruff, strict mypy72 files, forbidden scan0, mutations17/17. Ownership against origin/main passed. Actual baseline evidence is in ignored `analogforge/data/out/ayan-review-baseline/`.
- Semantic code search uses a local CocoIndex index; `.cocoindex_code/` is excluded locally via Git info/exclude, without changing project ignore rules.

## Reproduced defects and current repairs

Independent public-facade regressions in `test_review_source_pipeline.py` failed against the starting source, after correcting the test's required AOI metadata:

1. Valid geographic mock Mars data ingests, but CHARACTERIZE_TARGET blocks because the analysis path accepts only projected square cells.
2. INGEST_LOCAL_DATASET returns a normalized evidence pointer without raster bytes; ADAPTER_EVIDENCE cannot consume it.
3. Unexpected and Pydantic validation errors expose untrusted exception values including a token-bearing URL.
4. Bound lunar thermal metrics omit their source evidence from the target lineage; the helper also used the terrain grid's CRS for a different thermal grid.

The five reproductions now pass. Fifty-three existing+new focused ingestion, optional-layer, parity and port tests pass; strict mypy74 files passes. Production changes are still uncommitted:

- Safe type-only unexpected-error diagnostics; no raw Pydantic input values.
- Body-aware projected normalization with coarsest sampled native pixel support, nearest categorical sampling, conservative missing/water masks, bounded allocations and cancellation checkpoints.
- Deterministic bounded normalized-source NPZ artifacts with validated manifest, source hashes, masks, typed metadata and safe array headers; public ingestion also emits its required JSON report artifact.
- Authorized normalized evidence reuse with checksum/body/role/mode checks and persisted parent evidence.
- Thermal source inclusion, own-grid transform and whole-AOI denominator.

## Review continuation and final record

The above is the chronological initial review record, not the final gate state. The identified source, display, mask, support, attribution, error and lineage defects were corrected. A later adversarial check also reproduced a metre-unit CRS bypass of the distortion policy; native ground spacing and destination-frame validation now address it.

The original mutation gate proved unreliable: copied source lacked configuration and setup errors counted as kills. The corrected gate requires a passing baseline and actual test failures, and now targets all 16 guide behaviors meaningfully. Thresholds and tolerances were preserved; affected algorithm versions advanced to invalidate stale results. Only two versioned-handle test builders and the incorrect no-ingestion-artifacts assertion needed updates to existing tests.

Use [REVIEW-FINDINGS.md](REVIEW-FINDINGS.md), [STATUS.json](STATUS.json), [scientific-validation-report.json](scientific-validation-report.json) and the [review evidence packet](review-2026-11-09/README.md) for final results and remaining scope. The source fixes are committed separately from the evidence-only handoff commit, so the tested source SHA resolves exactly.

No real NASA source, live model, browser or physical-science validation is claimed. File-drop rehearsal uses explicitly synthetic mock NASA data. Raw downloads are distinct from normalized assets; the source selector accepts normalized evidence, not arbitrary downloaded blobs.
