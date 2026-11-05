# File ownership and the contract freeze

There is **one** application under `analogforge/`. The final merge combines three complementary sets of modules plus a byte-identical shared kit. It never combines three separately scaffolded apps, three databases, three status enums or three implementations of the same calculation.

## 1. The frozen contract kit (read-only for all)

`architecture files/contracts/kit/` holds the exact files that every branch materializes into `analogforge/` as its first action ([35](../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md)):

```bash
python3 "architecture files/contracts/kit/materialize.py"            # first command of every session
python3 "architecture files/contracts/kit/materialize.py" --verify   # last command; must print "PASS"
```

Kit files are owned by nobody. Editing one is a failed gate. The only editable region is the owner's own `extra-<name>` list in `pyproject.toml`. If the kit blocks you, record a contract-change request and continue with a compatible local workaround.

## 2. Master layout and owners

```text
analogforge/
  README.md Makefile compose.yaml  services/api/  ops/  scripts/{bootstrap,preflight,seed_synthetic,validate_docs,lock_sources}  uv.lock   Tanush
  .env.example .gitignore pyproject.toml  contracts/ (generated kit files)  src/analogforge/{__init__,ports/**}             kit (nobody)
  config/scenarios.yaml  config/presets/**                                                                                   Tanush
  config/{datasets,algorithms,candidates}.yaml  scripts/science/**                                                           Ayan
  package.json pnpm-lock.yaml pnpm-workspace.yaml  apps/web/**                                                               Aradhya
  src/analogforge/{main.py,settings.py,cli.py,api,domain,db,jobs,application,agents,tools}/                                  Tanush
  src/analogforge/adapters/{openai,storage,identity}/                                                                        Tanush
  src/analogforge/science/**  (facade, geometry, raster, features, comparison, qualification, compatibility, routing,
                               energy, portfolio, display, datasets, fixtures, provenance)                                   Ayan
  src/analogforge/adapters/{earthdata,pds,emit,diviner,user_survey,source_http}/  src/analogforge/rendering/tiles/           Ayan
  src/analogforge/rendering/passport/**                                                                                      Aradhya
  tests/contracts/kit/**  tests/fixtures/kit/**                                                                              kit (nobody)
  tests/{unit,integration}/platform/**  tests/contracts/platform/**  tests/support/**                                         Tanush
  tests/{unit,property,integration,replay}/science/**  tests/contracts/science/**  tests/fixtures/science/**                  Ayan
  tests/unit/passport_renderer/**  tests/contracts/ui/**  tests/e2e/**                                                       Aradhya
  data/                                                                                                                      git-ignored runtime
team guides/<Person>/**  team handoffs/<person>/**                                                                           that person
architecture files/**  team coordination/**  README.md  .gitignore                                                           Tanush (changes follow the recorded change process)
merging guide/**  team handoffs/merging/**                                                                                   merging agent
```

Machine-readable form: `contracts/ownership.json` (longest matching prefix; unknown paths are unowned and may not be edited; kit files may be committed unchanged by anyone). The checker `scripts/check_branch_ownership.py --person <name>` implements it, including kit awareness.

Application-service wrappers belong to Tanush; algorithms to Ayan; presentation to Aradhya. Tanush's `application/verification` loads records, authorizes and persists; Ayan's `science/routing` computes and independently checks. Tanush's `application/passports` assembles/freezes the bundle; Aradhya's `rendering/passport` turns it into bytes. No policy or calculation is duplicated in a wrapper or in the browser.

## 3. Shared files and single writers

| File | Single writer | Notes |
| --- | --- | --- |
| `pyproject.toml` | kit; extras per person | Add only to your own `extra-<name>` list; no other edit |
| `uv.lock` | Tanush | Ayan/Aradhya install with `uv pip install -e ".[dev,extra-<name>]"` and never commit a lock |
| `compose.yaml`, `Makefile`, `services/api/migrations/**` | Tanush | Migrations only on his branch (no competing heads) |
| `package.json`, `pnpm-lock.yaml`, `apps/web/src/generated/**` | Aradhya | Generated client regenerates from the kit's bundled OpenAPI |
| `config/*.yaml` | per the master layout | Cross-branch keys fixed in [35](../architecture%20files/35-FROZEN-CONTRACT-KIT-AND-CROSS-BRANCH-SEAMS.md) §7 |
| `architecture files/**` originals | read-only for Ayan/Aradhya | Tanush edits only through the recorded change process |

## 4. Contract change process (should be rare)

`templates/contract-change-request.json` → your `team handoffs/<person>/CHANGE-REQUEST-<n>.json`. Keep working with a compatible workaround. The **merging agent** applies an accepted change to the kit via `kit/tools/build_kit.py`, updates all consumers and re-runs every gate. Additive private helpers inside owned modules need no process; any public field, enum, nullability, unit, status meaning, port signature or dependency lock does.

## 5. Branch discipline

Own branch, own clone, own runtime profile. Commit only owned files plus exact kit files. Never rebase/force-push/reset another person's branch; never resolve a conflict by taking one whole side; never edit another owner's files to make your tests pass (report the missing interface). The ownership checker is an aid, not a security boundary.

## 6. Completion versus build order

Within each branch the build order is: kit → pure/deterministic core → typed port implementation → integration points → full scope → hardening → self-audit. Optional scientific sources keep tested no-coverage states. A feature is not complete because its tab exists or a mock response has the right colors.

## 7. Accepted revisions

C1 (scientific assurance, passport `assurance_evidence_id`) — [record](contracts/C1-SCIENTIFIC-ASSURANCE-CHANGE.json). C2 (one-shot layer: kit, entry points, dataset slot, errata) — [record](contracts/C2-ONE-SHOT-KIT-CHANGE.json). Baseline hashes: `contracts/architecture-baseline.json`.
