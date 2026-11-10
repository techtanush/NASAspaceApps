# Defects found in other owners' areas (facade worker)

## D-01 `features/slope.py::aspect_from_gradient` can return exactly 360.0 (core, not mine)
`np.degrees(np.arctan2(-dz_dx, -dz_dy)) % 360.0` returns `360.0` when the angle is a tiny negative number (e.g. `-1e-15 % 360.0 == 360.0`),
violating the documented `[0, 360)` range; `raster.store.build_analysis_grid` then raises `RasterError("aspect_deg must lie in [0, 360)")`.
Reproduction: analyse window `grid-r2c2` of the default practice grid through `ANALYZE_CANDIDATE` (before the workaround it came back
`BLOCKED SOURCE_CONTENT_INVALID`). Workaround: `science/ops/terrain.py::clean_aspect` folds values `>= 360` back by 360 before building the grid.
Proper fix (owner of `features/slope.py`): `aspect = np.where(aspect >= 360.0, 0.0, aspect)` after the modulo.
