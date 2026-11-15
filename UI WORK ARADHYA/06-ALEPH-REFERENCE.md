# Aleph reference — Aradhya

Reviewed 14 November 2026 at commit `1b307cdb7c470a7715da497ba406355dfe7d3163`. Repository: https://github.com/Belluxx/Aleph . Code license MIT; this does not grant rights to third-party datasets. Review packed 40 selected source/doc files (~39,948 tokens); read its README, package/license and capture/layer/dashboard/browser structure. No Aleph code or datasets were installed into AnalogForge.

Useful references (pinned):
- [Browser interaction](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/web/app.js): selected-area capture/detail views, layer toggles, lazy 3D loading, stale async protection, loading new raster before replacing old display, resource limits.
- [Interface structure](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/web/index.html): source/layer controls and capture inspection. Use interaction ideas within AnalogForge's tokens/components, not a copied second UI framework.
- [Layer preparation](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/alephgeo/layers.py): map-ready imagery, hillshade and elevation-derived relief. Tanush owns this side.

Apply now: inspect selected-site bbox, separate global context from local terrain, coherent layer controls, same-ID list/map selection, explicit partial coverage, async cancellation/resource cleanup, attributed imagery. Use existing React/MapLibre/GlobeStage; no Aleph iframe, second Python web server, direct provider fetches or generic localStorage domain state.

Do not port its Earth Web Mercator math into Mars/Moon; do not port satellite/streetview/Google mesh download paths. [Upstream README](https://github.com/Belluxx/Aleph/blob/1b307cdb7c470a7715da497ba406355dfe7d3163/README.md) explicitly warns that those downloads conflict with Google terms and use undocumented APIs. Use documented, permitted NASA/Microsoft/open datasets through Tanush's validated pipeline. Buildings/streetview are optional Earth context at most, never evidence of planetary analogy.

Do not inherit display conventions blindly: Aleph's terrarium path substitutes a base height where data is missing and its relief can exaggerate slope by level. AnalogForge must preserve an explicit no-data mask, source height reference, resolution and visible exaggeration factor. A dramatic 3D picture is not a qualified route or a measurement. Copying substantial MIT code later requires the copyright/license notice plus the app's third-party register; referencing interaction ideas here does not add a package dependency.
