# UI WORK TANUSH — visualization backend and data handoff

Branch: `tanush/platform-agents-integration`. Both branches share the same seed, including Claude's incomplete UI and main1721844. You own Earth/Mars/Moon visualization DATA, prepared regional layers, source provenance, coverage and API read projections. Aradhya owns every frontend component/camera/control. This split deliberately avoids both agents editing maps TS files.

Read `00-START-HERE.md`, `01-OWNERSHIP-AND-DELIVERABLES.md`, `02-DATA-AND-IMAGERY-PLAN.md`, `03-REGIONAL-ZOOM-AND-API-PLAN.md`, `04-ALEPH-REFERENCE.md`, `05-TEST-AND-MERGE-GATES.md` and the execution prompt. The shared [seam contract](../team%20handoffs/ui-split/INTEGRATION-CONTRACT.md) is authoritative for this round; schemas are proposed planning contracts, not implemented endpoints.

Your delivery lets the frontend zoom into the actual selected target/site and display aligned, attributed source imagery/terrain without pretending global textures are high-resolution evidence. Do not build another dashboard, redesign frontend cards or silently increase scientific resolution.
