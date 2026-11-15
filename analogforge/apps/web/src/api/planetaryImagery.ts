import type { components } from '../generated/schema';

type AOI = components['schemas']['AreaOfInterest'];
export type PlanetaryBody = 'MARS' | 'MOON';
export const PLANETARY_SOURCES = {
  MARS: {
    // Exact ResourceURL published by NASA Trek capabilities; spherical degrees, not Earth Mercator.
    root: 'https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile',
    maxZoom: 11, tileSize: 512, radius: 3396190, format: 'image/png',
    title: 'MRO Context Camera · Caltech mosaic',
    credit: 'NASA / JPL / MSSS · Caltech Murray Lab · tiles via NASA Trek / Esri',
    source: 'https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars',
    limitations: 'Historical orbital mosaic, approximately 5 m source pixels. Preliminary uncontrolled beta01 mosaic, with possible seams and positional offsets. The finest delivered tiles sample about 10 m per pixel at the equator.',
  },
  MOON: {
    root: 'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm',
    maxZoom: 8, tileSize: 256, radius: 1737400, format: 'image/jpeg',
    title: 'LRO Wide Angle Camera · global mosaic v2',
    credit: 'NASA / GSFC / Arizona State University · NASA Trek',
    source: 'https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon',
    limitations: 'Historical orbital image mosaic, approximately 100 m source pixels. Lighting and mosaic seams can vary; this is not a live camera or a terrain elevation measurement.',
  },
} as const;

export function planetaryTileUrl(body: PlanetaryBody, z: number, x: number, y: number) {
  const source = PLANETARY_SOURCES[body];
  if (!source || ![z, x, y].every(Number.isInteger) || z < 0 || z > source.maxZoom
    || x < 0 || x >= 2 ** (z + 1) || y < 0 || y >= 2 ** z) throw new Error('Invalid planetary tile');
  return `${source.root}/${z}/${y}/${x}${body === 'MOON' ? '.jpg' : ''}`;
}

/** Pure display geometry. No Earth projection or scientific evidence is inferred. */
export function planetaryViewport(aoi: AOI, zoomDelta = 0, offset: [number, number] = [0, 0]) {
  if (!['MARS', 'MOON'].includes(aoi.body) || aoi.latitude_type !== 'PLANETOCENTRIC'
    || aoi.longitude_convention !== 'NEG180_180' || aoi.bbox.length !== 4 || !aoi.bbox.every(Number.isFinite)
    || (aoi.crs_wkt != null && aoi.crs_wkt !== (aoi.body === 'MARS' ? 'EPSG:104905' : 'EPSG:104903'))) return null;
  const [west, south, east, north] = aoi.bbox as [number, number, number, number];
  if (west < -180 || east > 180 || south < -90 || north > 90 || east <= west || north <= south) return null;
  const body = aoi.body as PlanetaryBody, source = PLANETARY_SOURCES[body];
  const baseSpan = Math.min(360, Math.max((east - west) * 1.35, (north - south) * 1.35 * 1.6, 0.01));
  const fittedZoom = Math.floor(Math.log2(180 * 640 / (source.tileSize * baseSpan)));
  // Start the camera at the deliverable source level so the first zoom-out always moves.
  const baseZoom = Math.min(source.maxZoom, Math.max(0, fittedZoom));
  const z = Math.min(source.maxZoom, Math.max(0, baseZoom + zoomDelta));
  const dpp = 180 / (source.tileSize * 2 ** z);
  const width = Math.min(360, Math.max(640 * dpp, fittedZoom < 0 ? baseSpan : 0)), height = width / 1.6;
  const lon = Math.max(-180 + width / 2, Math.min(180 - width / 2, (west + east) / 2 + offset[0]));
  const lat = height >= 180 ? 0 : Math.max(-90 + height / 2, Math.min(90 - height / 2, (south + north) / 2 + offset[1]));
  const bounds: [number, number, number, number] = [lon - width / 2, lat - height / 2, lon + width / 2, lat + height / 2];
  const span = 180 / 2 ** z, tiles: { x: number; y: number; left: number; top: number; size: number }[] = [];
  const firstX = Math.max(0, Math.floor((bounds[0] + 180) / span));
  const lastX = Math.min(2 ** (z + 1) - 1, Math.ceil((bounds[2] + 180) / span) - 1);
  const firstY = Math.max(0, Math.floor((90 - bounds[3]) / span));
  const lastY = Math.min(2 ** z - 1, Math.ceil((90 - bounds[1]) / span) - 1);
  for (let y = firstY; y <= lastY; y++) for (let x = firstX; x <= lastX; x++) {
    tiles.push({ x, y, left: (-180 + x * span - bounds[0]) / width * 640,
      top: (bounds[3] - (90 - y * span)) / height * 400, size: span / width * 640 });
  }
  if (tiles.length > 16) return null;
  return { body, z, bounds, width, height, tiles,
    sampleM: dpp * Math.PI / 180 * source.radius,
    selection: { x: (west - bounds[0]) / width * 640, y: (bounds[3] - north) / height * 400,
      width: (east - west) / width * 640, height: (north - south) / height * 400 } };
}

/** One bounded image request. The component limits tile count and concurrency. */
export async function fetchPlanetaryTile(body: PlanetaryBody, z: number, x: number, y: number, parent: AbortSignal): Promise<Blob> {
  const timeout = new AbortController(), signal = AbortSignal.any([parent, timeout.signal]);
  const timer = setTimeout(() => timeout.abort(), 8000);
  try {
    const response = await fetch(planetaryTileUrl(body, z, x, y), { signal, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error' });
    const expected = PLANETARY_SOURCES[body].format;
    if (!response.ok || !response.headers.get('Content-Type')?.toLowerCase().startsWith(expected)) throw new Error('Unavailable planetary image');
    if (Number(response.headers.get('Content-Length')) > 1048576 || !response.body) throw new Error('Invalid planetary image');
    const reader = response.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
    try {
      while (true) { const part = await reader.read(); if (part.done) break; size += part.value.length;
        if (size > 1048576) { await reader.cancel(); throw new Error('Planetary image too large'); } chunks.push(part.value); }
    } finally { reader.releaseLock(); }
    if (signal.aborted) throw new Error('Cancelled planetary image');
    const data = new Uint8Array(size); let offset = 0; for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.length; }
    if (body === 'MARS' ? data[0] !== 137 || data[1] !== 80 || data[2] !== 78 || data[3] !== 71 : data[0] !== 255 || data[1] !== 216) throw new Error('Invalid planetary image');
    return new Blob([data], { type: expected });
  } finally { clearTimeout(timer); }
}
