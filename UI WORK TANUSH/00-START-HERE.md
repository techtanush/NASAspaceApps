# Tanush start sequence

1. Verify the worktree is clean before updating `tanush/platform-agents-integration`. Fetch and pull --ff-only; never reset unsaved work. Record common handoff SHA in STATUS.
2. Read this entire folder and shared contract/ownership/schemas. Read `team handoffs/betterui/UI-PLAN.md`, especially Part F, and PROGRESS. Part F is proposed work, not existing backend capability.
3. Read architecture 08–10 (datasets/provenance/terrain), 18 (maps), 19 (exports), 24 (security), 29 and33 (scientific credibility), 35–36 (contracts and dataset plugin),38 (private setup),41 (display integrity) and the existing LOCAL-LIVE-RUNBOOK.
4. Inspect current science/display/layers.py, display/legend.py, dataset application/facade, API artifact authorization and actual frozen DisplayLayerManifest. Reuse these instead of parallel undocumented layer formats.
5. Set up a new ignored local profile using .env.example; no credentials or datasets are in this branch. The existing live rehearsal is on the original machine only. Do not copy another branch's database or mutate its locked sources.
6. Deliver T0/T1/T2 first. Aradhya can continue against mocks while you work. More terrain regions, automatic proving, attachments/chat and cloud deployment are later scope.

The verified main at1721844 has a completed real NASADEM/MOLA run with500m comparison support, two PASS/two FAIL and LIMITED assurance. Its logs/rasters are not repo fixtures and its results must not be hardcoded into new UI/backend code.

Stable round base: fetch tag `ui-split-base-20261114` and resolve it with `rtk git rev-parse ui-split-base-20261114`. Record that SHA in STATUS; compare only subsequent implementation changes against this tag. Do not move or force-update the tag.
