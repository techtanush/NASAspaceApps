# Ayan — progress log

Created during the independent debug review of 2026-11-11 (the builder protocol requires this file; the original run kept its notes in `REVIEW-PROGRESS.md`). Entries are taken from the branch history, not reconstructed from memory.

| Phase | Commit | Date | What |
| --- | --- | --- | --- |
| S1 core, routing, adapters | `802b765` | 2026-11-08 | science core, routing engine, live adapters (wave 1) |
| S2 fixtures, dataset slot, portfolio, display, audit | `0ab1f4b` | 2026-11-09 | wave 2 |
| S3 facade (15 operations), conformance, gate scripts | `4072a85` | 2026-11-09 | wave 3 |
| S4 adversarial-review repairs | `876944e`, `290a688`, `76bd01e` | 2026-11-09 | test support relocation, aspect 360, property tests, routing/datasets/terrain fixes, S-NO-ENERGY row credit |
| S5 status | `12e5e10`, `1639f2e`, `6856046` | 2026-11-09 | STATUS.json with executed gates |
| Codex review repairs | `1e9538a`, `3e5d1b9`, `8b37d8f` | 2026-11-09 | normalized source workflows, review gates, projection distortion; see `REVIEW-PROGRESS.md` |
| Independent debug review | `4766f6d` | 2026-11-11 | SC-02 seam defect in SCREEN_CANDIDATES fixed (see `DEBUG-REVIEW.md`) |
| Seam fixes, second pass | this commit | 2026-11-11 | audit of route-level VERIFICATION claims, accepted energy-assumption evidence, decisive metrics on COMPARISON evidence; real-science trial journeys 10/10 |

## Next three actions (for the merging agent)
1. Merge after Tanush; the only expected conflict is the `pyproject.toml` extras block (keep both extras; regenerate `uv.lock` with `h5py`).
2. Run Tanush's journeys with `AF_SCIENCE_IMPL=real` (10/10 passed in the 2026-11-11 trial merge; `DEBUG-REVIEW.md` §3).
3. Re-run `tests/integration/science/test_evidence_artifact_integrity.py` after any change to evidence emission.
