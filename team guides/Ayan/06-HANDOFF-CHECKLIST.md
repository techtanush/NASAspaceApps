# Ayan — definition of done (checklist)

Tick only with observed evidence recorded in `STATUS.json`.

- [ ] Correct branch/clone; kit materialized and `--verify` PASS at start and end; `tests/contracts/kit` green.
- [ ] Only owned paths changed (ownership checker PASS); `extra-ayan` is the only `pyproject.toml` edit; no `uv.lock`.
- [ ] `create_science_service()` returns a `ScienceService` supporting all 15 operations; each has happy-path, `BLOCKED`/`LIMITED` and cancellation tests; every result validates as `ScienceComputationResult`.
- [ ] `tests/support/registrar_stub.py` enforces the platform registration rules and your results pass it; crafted bad results are rejected.
- [ ] Canonical graph: every `GRAPH_EXPECTED` entry reproduced by the real search + independent verifier; falsified totals rejected.
- [ ] Energy oracle within 1e-8 Wh; analytic geometry oracles GEO-01…10 pass.
- [ ] Practice generators produce all five practice datasets and the nine mock-drop datasets, byte-deterministic, **and** the independent checker confirms every window property of architecture 40 §4.
- [ ] Screening, truth table, five storylines and nine perturbations pass through `facade.execute` only.
- [ ] Dataset validation implements every check of architecture 36 §4 with a failing fixture each; `draft_manifest` works; parity (fixture ≡ local dataset) holds.
- [ ] Optional layers (mineral/thermal) honest: UNKNOWN with the specified reasons; categorical ids never interpolated.
- [ ] Display layers: correct corners/affine/legend/transparency/attribution.
- [ ] Live adapters implemented and tested with mocked HTTP + format-faithful files; none contacts a real server; none reads the environment.
- [ ] Import hygiene: no `fastapi/sqlalchemy/psycopg/openai`/platform imports; no `os.environ`; no network in synthetic.
- [ ] Determinism: two executions give identical bytes; budgets in `05` §4 met.
- [ ] No `NotImplementedError`/`TODO`/`FIXME`/`HACK`; no hard-coded practice outcomes; no weakened/skipped tests; mutation checks demonstrate tests can fail.
- [ ] `STATUS.json` complete and truthful; contradictions and cross-area defects listed; committed; pushed to `origin ayan/science-data-verification`.

Deliver as early as each phase gate allows by pushing at every gate — but the **branch is only mergeable at the end**.
