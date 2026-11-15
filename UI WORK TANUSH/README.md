# UI WORK TANUSH — visualization backend and data handoff

Branch: `tanush/platform-agents-integration`. Both branches share the same seed, including Claude's incomplete UI and main1721844. You own Earth/Mars/Moon visualization DATA, prepared regional layers, source provenance, coverage and API read projections. Aradhya owns every frontend component/camera/control. This split deliberately avoids both agents editing maps TS files.

Read [DELIVERY.md](DELIVERY.md) and [STATUS.json](STATUS.json) first for the implementation and current checks. The numbered files and execution prompt preserve the original plan. The shared [seam contract](../team%20handoffs/ui-split/INTEGRATION-CONTRACT.md) records the round's ownership and scientific rules; its statements that visualization routes are only proposed describe the original handoff. The six optional backend routes are now implemented, with capability discovery and packaged versioned response schemas. They remain disabled until explicitly enabled.

Your delivery lets the frontend zoom into the actual selected target/site and display aligned, attributed source imagery/terrain without pretending global textures are high-resolution evidence. Do not build another dashboard, redesign frontend cards or silently increase scientific resolution.
