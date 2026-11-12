.PHONY: bootstrap dev migrate seed-synthetic preflight test test-live generate-client build check backup restore-check down

PY := uv run

bootstrap:
	./scripts/bootstrap.sh

dev:
	./scripts/dev.sh

migrate:
	$(PY) analogforge migrate

seed-synthetic:
	$(PY) analogforge seed-synthetic

preflight:
	$(PY) analogforge preflight --mode synthetic --scenario synthetic-mars-mobility-v1

test:
	@mkdir -p data/out
	$(PY) pytest tests/contracts/kit -q --strict-markers -p no:randomly
	$(PY) pytest tests/unit/platform tests/integration/platform tests/contracts/platform -q --strict-markers -p no:randomly --junitxml data/out/platform-junit.xml

test-live:
	./scripts/test_live.sh

generate-client:
	@if [ -f apps/web/package.json ]; then cd apps/web && corepack pnpm exec openapi-typescript ../../contracts/openapi.bundled.json -o src/generated/schema.d.ts; else echo "Frontend package is unavailable"; exit 1; fi

build:
	$(PY) python -m compileall -q src/analogforge
	@if [ -f apps/web/package.json ]; then cd apps/web && corepack pnpm build; else echo "Frontend package is unavailable"; exit 1; fi

check:
	$(PY) python '../architecture files/contracts/kit/materialize.py' --verify
	$(MAKE) test
	./scripts/validate_docs.sh
	$(PY) ruff check src tests/unit/platform tests/integration/platform tests/contracts/platform tests/support
	$(PY) mypy src/analogforge --exclude 'src/analogforge/(ports|science|rendering/passport|adapters/(earthdata|pds|emit|diviner|user_survey|source_http))'
	$(PY) python -m analogforge.cli preflight --mode synthetic --scenario synthetic-mars-mobility-v1 --output data/out/preflight-synthetic.json --json
	$(PY) python -m analogforge.cli export-openapi --out data/out/openapi.exported.json
	$(PY) python '../team coordination/scripts/check_branch_ownership.py' --person tanush --repo ..
	./scripts/forbidden_scan.py --json data/out/forbidden.json
	./scripts/mutation_check.py --json data/out/mutations.json

backup:
	./ops/backup/backup.sh

restore-check:
	./ops/restore/restore_check.sh

down:
	$(PY) analogforge db down
