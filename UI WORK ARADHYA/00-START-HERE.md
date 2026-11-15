# Start here

1. Work in your clone/worktree on `aradhya/frontend-experience`; check for unsaved work before updating. If clean: `rtk git fetch origin`, then `rtk git pull --ff-only origin aradhya/frontend-experience`. Never reset somebody else's work.
2. Record HEAD in STATUS as the shared handoff base before your first implementation commit. Both branches have the same seed; do not begin from stale round-one code.
3. Read `01-CURRENT-STATE.md`, the shared integration contract, the preserved Claude UI plan and progress, and your new implementation/test documents.
4. Read architecture 17 (state), 18 (body/CRS/layers), 19 (passport), 33 (claims), 35 (contracts), 41 (design). Read `team guides/Aradhya/07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md` and `10-DESIGN-SYSTEM-AND-VISUAL-QA.md`. Actual code is under `analogforge/apps/web`, not historical `frontend/` examples.
5. Use a working Node 22+ installation and the pinned Corepack/pnpm version from the workspace package. Do not repair or upgrade the user's system Node as part of UI work. The validation machine's Homebrew Node currently fails loading simdjson; its private Node 22 toolchain worked. A different machine should install/use its own supported Node, not depend on the original operator's absolute paths.
6. From `analogforge`: `rtk proxy corepack pnpm install --frozen-lockfile`. From `analogforge/apps/web`: `rtk proxy env VITE_API_MOCK=1 WEB_PORT=5300 corepack pnpm exec vite --host 127.0.0.1`. Open localhost:5300. Choose an unused port; do not kill somebody else's server. Mock mode is a labelled development preview and cannot be built for production.
7. Inspect the complete tour card BELOW the fold, all actions and progress/error states before restyling. Repair correctness first, then add report/drill-down, then polish and run gates.

Do not copy `.env`, `.runtime`, data, secrets or running DB files from another worktree. Frontend mock work needs no OpenAI or weather credentials. Full renderer-backed mock download checks need the documented local Python environment; use the normal project setup rather than substituting fake renderer bytes.

Stable round base: fetch tag `ui-split-base-20261114` and resolve it with `rtk git rev-parse ui-split-base-20261114`. Record that SHA in STATUS; compare only subsequent implementation changes against this tag. Do not move or force-update the tag.
