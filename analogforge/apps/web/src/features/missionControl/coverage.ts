import type { GlobeBody } from '../../maps/globeAssets';

/**
 * Terrain-data coverage for a chosen place, shown before a run starts.
 *
 * Plug-in point: the backend does not yet expose dataset footprints. When it does, resolve the real state here
 * (COVERED, PARTIAL or NONE) and every screen that shows coverage updates. Until then the honest answer is UNKNOWN.
 */
export type CoverageState = 'COVERED' | 'PARTIAL' | 'NONE' | 'UNKNOWN';
export interface Coverage { state: CoverageState; message: string }
export function useCoverage(body: GlobeBody, bbox: readonly number[] | null): Coverage {
  void body; void bbox; // inputs the real resolver will use
  return { state: 'UNKNOWN', message: 'Terrain data coverage for this area is checked when the investigation starts.' };
}
