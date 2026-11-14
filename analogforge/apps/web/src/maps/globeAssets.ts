import type { components } from '../generated/schema';

export type GlobeBody = components['schemas']['Body'];

/**
 * Surface imagery for each globe. This file is the single plug-in point for visual planet data.
 *
 * To replace a placeholder with a real global map, put an equirectangular image (2:1, longitude -180..180 left to
 * right, north up) in apps/web/public/globe/, point `surface` at it, set `placeholder` to false and fill in
 * `attribution`. `relief` is optional greyscale elevation used only for shading.
 */
export interface GlobeAsset {
  surface: string;
  relief: string | null;
  placeholder: boolean;
  attribution: string;
  atmosphere: { color: string; altitude: number } | null;
  radiusKm: number;
  label: string;
}

const base = `${import.meta.env.BASE_URL}globe/`;

export const GLOBE_ASSETS: Record<GlobeBody, GlobeAsset> = {
  EARTH: {
    surface: `${base}earth-blue-marble.jpg`,
    relief: null,
    placeholder: false,
    attribution: 'Earth imagery: NASA Blue Marble, via three-globe (MIT)',
    atmosphere: { color: '#6FB7FF', altitude: 0.17 },
    radiusKm: 6371.0,
    label: 'Earth',
  },
  MARS: {
    surface: `${base}mars-placeholder.jpg`,
    relief: `${base}mars-relief.jpg`,
    placeholder: true,
    attribution: 'Placeholder surface imagery (generated). Not a map of Mars.',
    atmosphere: { color: '#E8A06A', altitude: 0.09 },
    radiusKm: 3396.19,
    label: 'Mars',
  },
  MOON: {
    surface: `${base}moon-placeholder.jpg`,
    relief: `${base}moon-relief.jpg`,
    placeholder: true,
    attribution: 'Placeholder surface imagery (generated). Not a map of the Moon.',
    atmosphere: null,
    radiusKm: 1737.4,
    label: 'Moon',
  },
};

export const STARFIELD = `${base}starfield.png`;
/** Canvas colours for WebGL overlays; DOM overlays use the design tokens. */
export const GLOBE_INK = { accent: '#5AAEFF', ring: (t: number) => `rgba(90,174,255,${Math.max(0, 1 - t)})`, space: '#05080C' };
