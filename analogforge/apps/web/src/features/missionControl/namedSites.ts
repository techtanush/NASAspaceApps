import type { GlobeBody } from '../../maps/globeAssets';

/** Well-known places offered as shortcuts. Coordinates are approximate centres for navigation, not survey values. */
export interface NamedSite { id: string; body: GlobeBody; name: string; note: string; lat: number; lng: number }
export const NAMED_SITES: NamedSite[] = [
  { id: 'gale', body: 'MARS', name: 'Gale Crater', note: 'Curiosity landing region', lat: -4.8, lng: 137.4 },
  { id: 'jezero', body: 'MARS', name: 'Jezero Crater', note: 'Perseverance landing region', lat: 18.38, lng: 77.58 },
  { id: 'valles', body: 'MARS', name: 'Valles Marineris', note: 'Canyon system', lat: -13.9, lng: -59.2 },
  { id: 'olympus', body: 'MARS', name: 'Olympus Mons flank', note: 'Shield volcano slopes', lat: 18.65, lng: -133.8 },
  { id: 'south-pole', body: 'MOON', name: 'South polar region', note: 'Near Shackleton crater', lat: -88.5, lng: 0 },
  { id: 'tranquillitatis', body: 'MOON', name: 'Mare Tranquillitatis', note: 'Apollo 11 landing region', lat: 0.674, lng: 23.473 },
  { id: 'tycho', body: 'MOON', name: 'Tycho', note: 'Young ray crater', lat: -43.3, lng: -11.2 },
];
export const AREA_SIZES_KM = [10, 20, 40, 80] as const;
