# Review evidence

This packet records the single-chat Ayan review on 9 November 2026. No subagents were used. `summary.json` identifies the exact tested source commit; the later handoff commit changes documentation/evidence only.

## What executed

The original pushed source at `68560469a34163dfb73a35b887aaa06d88a0f264` ran first in a fresh Python 3.12 environment. Its 973 science/replay and 20 kit tests passed. `baseline-red-regressions.xml` records the five independently added failures before the first fixes. The original mutation report is retained as `baseline-mutations-UNRELIABLE.json`: it must not be reused as certification.

The final source has 1,000 science/replay tests and 20 kit tests, with no skips or xfails. `science-seed1.xml` and `science-seed2.xml` are complete full-suite runs under separate hash seeds. `oracles.json` gives every named test outcome. The SCN-01…SCN-21 mapping and observed per-row counts are in `../STATUS.json`; shared tests mean those row counts must not be added together. Performance budgets remain active tests in `test_budgets.py`; cancellation, deadline and import/socket guards remain active too.

`mutations.json` records 16 meaningful mutations, each with its own successful baseline and executed failing invariant. Setup errors, skipped tests, empty collections and timeouts cannot kill a mutant. See `../REVIEW-FINDINGS.md` for the ineffective original M1/M4 definitions and the harness correction. The harness itself is checked using real child pytest processes that assert refusal of setup errors, already-failing baselines and skips.

`repro-seed1.json` and `repro-seed2.json` contain actual payloads, parameter identities and immutable artifact hashes from separate six-operation practice workflows: characterize, screen, analyze, design, search and independently verify. They ran from different working directories and match exactly after the declared elapsed-field exclusion. `repro-probe.py` reproduces that receipt using the existing integration fixture helper; its first argument is the absolute application directory and its second is the output JSON path.

`ruff.log`, `mypy.log`, `forbidden.json`, `ownership.json`, `source-config.json` and `environment.json` record the other contributor gates. Strict type checking covers 105 science/adapter/tile source files. Kit materialization was verified byte-for-byte. `whitespace-check.log` identifies the one blank EOF line already required by the frozen `ports/science_payloads.py`; that file is preserved exactly.

The raw red JUnit receipts also preserve pytest's whitespace inside failure text. Those machine records are hashed as captured, rather than edited to satisfy a prose whitespace check.

## Reproduction

From `Ayan/analogforge`, create a fresh Python 3.12 environment and install `.[dev,extra-ayan]` with rasterio 1.4.4, the tested GDAL environment. No dependency list or lockfile was weakened. Run:

```bash
rtk proxy .venv/bin/python "../architecture files/contracts/kit/materialize.py" --verify
rtk proxy .venv/bin/pytest tests/contracts/kit -q
rtk proxy env PYTHONHASHSEED=1 .venv/bin/python scripts/science/run_oracles.py --junit data/out/review-seed1.xml --json data/out/review-seed1.json
rtk proxy env PYTHONHASHSEED=2 .venv/bin/python scripts/science/run_oracles.py --junit data/out/review-seed2.xml --json data/out/review-seed2.json
rtk proxy .venv/bin/python scripts/science/mutation_check.py --json data/out/review-mutations.json
rtk proxy .venv/bin/python scripts/science/forbidden_scan.py --json data/out/review-forbidden.json
rtk proxy .venv/bin/python scripts/science/validate_sources.py
rtk proxy .venv/bin/python "../team coordination/scripts/check_branch_ownership.py" --person ayan --repo .. --base origin/main
```

The full lint/type commands and scope are in `../STATUS.json` and Ayan guide 05. `manifest.json` hashes this packet's machine evidence; documentation may be added afterward and is not represented as a scientific input.

## Formal guide-09 signoff

| Requirement | Observed result |
| --- | --- |
| Forbidden-pattern and dependency scan | Zero findings; import/socket tests execute |
| M1…M16 | All killed with passing baselines and assertion/test-phase failures |
| PERT-01…PERT-09 | All execute; before/after assertions mapped in STATUS |
| Four independent subagent reviewers | Superseded by user's explicit instruction to perform the review here without subagents; no independence claim |
| Practice outcome hardcoding | No practice window literals in production decision code outside fixtures/config |
| Temporary threshold change | Existing unit policy check and separate facade receipt demonstrate computed changes, with new config hashes |
| Cross-seed/directory reproducibility | Full oracle reports and actual six-operation receipts match |
| Facade import under 2 s, no sockets | Standalone import about 0.10 s; required socket guards pass |
| Fresh environment/no cached verdicts | Fresh environment before baseline; practice sources regenerated in test scratch directories |
| Frozen contracts and ownership | Exact kit, accepted-main ownership check passed |

This establishes offline S0/S1 contributor readiness. It does not establish actual NASA product controls, real comparative validation, a real modeled experiment, physical validation, live model behavior or final integrated UI/publication behavior. `../scientific-validation-report.json` retains those unrun scopes and the SCI mapping explicitly.
