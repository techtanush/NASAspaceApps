#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p out data/out
uv run --locked python '../architecture files/contracts/kit/materialize.py' --verify
# Kit import-isolation assertions require their own Python process.
uv run --locked pytest tests/contracts/kit -q --junitxml out/kit-junit.xml
AF_SCIENCE_IMPL=real AF_RENDERER_IMPL=real uv run --locked pytest \
  tests/unit/platform tests/integration/platform tests/contracts/platform \
  -q --strict-markers -p no:randomly --junitxml data/out/platform-junit.xml
uv run --locked pytest tests/unit/science tests/property/science tests/integration/science \
  tests/replay/science tests/contracts/science tests/unit/passport_renderer tests/contracts/ui \
  -q --strict-markers --junitxml out/science-renderer-junit.xml
./scripts/validate_docs.sh
# The unchanged frozen kit test contains one overlong line; owned code has no exclusions.
uv run --locked ruff check src tests --extend-exclude tests/contracts/kit
uv run --locked mypy src/analogforge --exclude src/analogforge/ports
corepack pnpm run generate:client
git diff --exit-code -- apps/web/src/generated
for check in typecheck lint test test:contracts build; do corepack pnpm run "$check"; done
uv run --locked python scripts/forbidden_scan.py --json out/platform-forbidden.json
uv run --locked python scripts/science/forbidden_scan.py --json out/science-forbidden.json
uv run --locked python scripts/ui/forbidden_scan.py --json out/ui-forbidden.json
uv run --locked python '../merging guide/scripts/wire_check.py' --repo .. --stage final --json out/wire-final.json
uv run --locked python '../merging guide/scripts/purity_check.py' --person merging --repo .. --base origin/main --json out/purity-merged.json
uv run --locked analogforge preflight --mode synthetic --scenario synthetic-mars-mobility-v1 --output out/preflight-synthetic.json
