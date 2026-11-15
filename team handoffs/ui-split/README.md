# Mission Control parallel build — start here

Round: 14 November 2026. Product: AnalogForge. Contributors: Aradhya (frontend), Tanush (visualization backend/data). This is a new round after the first full integration, not a request to rebuild the original app.

Both contributor branches start from the SAME handoff commit, containing main at `1721844d827795bfd0a003df769934d8657e9b57` plus every BETTERUI commit through `fc5e084c8b4e9e895604ba4be85e78fe2864fe7c` and this documentation. The handoff preserves Claude's partial UI. It does not claim that UI is release ready. BETTERUI itself and main are not changed by this handoff.

- Aradhya: read [UI WORK ARADHYA](../../UI%20WORK%20ARADHYA/README.md), then continue on `aradhya/frontend-experience`.
- Tanush: read [UI WORK TANUSH](../../UI%20WORK%20TANUSH/README.md), then continue on `tanush/platform-agents-integration`.
- Shared authority: [integration contract](INTEGRATION-CONTRACT.md) and [ownership](OWNERSHIP.json).

Aradhya builds all browser presentation, camera interaction, forms, the Earth-site tour, detailed-view UI and report. Tanush supplies trustworthy Earth/Mars/Moon imagery and prepared regional display data, coverage and benchmark projections. Tanush owns the visual DATA; Aradhya owns how users SEE and INTERACT with it.

Work independently against the frozen seams and explicit unavailable fixtures. A missing backend feature is a labelled state, not a reason to fake data or stall all frontend work. A missing polished frontend is not a reason to build an alternate dashboard on Tanush's branch. Keep commits small and independently testable.

No Aleph dependency, downloaded external imagery, new API endpoint, new scientific computation, or complete UI implementation is added by this planning handoff. Source packages remain the existing application.
