# AnalogForge workbench

The Aradhya branch implements the React workbench, offline maps, a development-only stateful mock backend, the pure Python passport renderer, and browser acceptance checks. Scientific values are read from the API and registered artifacts. The browser does not calculate qualification, energy, slope, or exposure.

## Start the preview

From `analogforge/`, use Node 22 and the pinned pnpm 10:

```sh
uv venv --python 3.12
uv pip install -e '.[dev,extra-aradhya]'
corepack pnpm install --frozen-lockfile
corepack pnpm run dev:mock
```

Open `http://127.0.0.1:5176`. No API keys are needed. The permanent **MOCK PREVIEW** banner identifies the simulated backend. It replays synthetic practice fixtures; these are not real terrain measurements or physical rover results. The preview persists its simulated server state in IndexedDB so reload and reconnect can be exercised. Add `?resetMock=1` to reset that preview database.

The preview’s exports are produced by the actual Python renderer through a local Vite development bridge. They preserve the current accepted inputs, all attempts, qualifications, audited statements, and separate manifest/file digests. The bridge is unavailable in production.

## Connect the real backend

`corepack pnpm run dev` proxies `/api/v1` to the backend on port 8003. Configure `API_PORT`, `WEB_PORT`, or `VITE_API_BASE_URL` as needed. `corepack pnpm run build` produces static assets without the mock transport, service worker, or styleguide. It rejects `VITE_API_MOCK=1`.

The Tanush/Ayan merge supplies the actual platform and scientific services. Running this branch’s preview does not validate that combined backend, live model access, real datasets, or physical rover behavior.

## Check the branch

```sh
corepack pnpm run generate:client
corepack pnpm run typecheck
corepack pnpm run lint
corepack pnpm run test
corepack pnpm run test:contracts
corepack pnpm run build
corepack pnpm run test:e2e:mock
corepack pnpm run a11y
corepack pnpm run audit:visual
.venv/bin/pytest tests/contracts/kit tests/unit/passport_renderer tests/contracts/ui -q
.venv/bin/mypy src/analogforge/rendering/passport
.venv/bin/python scripts/ui/verify_exports.py --self-test
.venv/bin/python scripts/ui/forbidden_scan.py --json out/forbidden.json
.venv/bin/python scripts/ui/mutation_check.py --json out/mutations.json
```

Browser checks use `PLAYWRIGHT_CHROMIUM_EXECUTABLE` when set, an installed macOS Chrome when available, or Playwright Chromium. Install the latter with `corepack pnpm --filter @analogforge/web exec playwright install chromium` if needed. Run browser suites serially on memory-constrained machines.

The same journeys run against the merged backend with `E2E_TARGET=real` and `E2E_BASE_URL` pointing to the merged workbench origin; they retain API identity, receipt, evidence, and digest assertions. See `team handoffs/aradhya/STATUS.json` for the checks actually executed and remaining integration boundaries.

## Design and test tools

`/__styleguide` is available only in development. It shows all components in both themes and three densities. The full visual audit checks every screen across six viewports, both themes, and the required density variants. Its reports, screenshot catalog, production resource audit, and mutation logs are generated under `out/` and are not committed. The workspace postinstall adds only `/analogforge/out/` to the clone’s local Git exclude file; the frozen kit ignore file stays unchanged.

Explicit development fixtures `?mockScenario=review-proxy` and `?mockScenario=blocked-worker` exercise scoped human review and dependency recovery. `?mockLatency=300` adds the visual audit’s network latency; ordinary preview sessions have no artificial latency. These switches do not exist in production builds.
