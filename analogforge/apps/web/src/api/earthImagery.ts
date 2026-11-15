import type { AddProtocolAction } from 'maplibre-gl';

export const EARTH_IMAGERY_MAX_ZOOM = 13;
// MapLibre's 512 px camera world requests 256 px raster tiles one level above camera zoom.
// Verified public 2016 tiles stop adding detail at WMTS 13 near Flagstaff; 14 is interpolated.
// Stop at camera 12 so the last usable tile is not enlarged as if it contained additional detail.
export const EARTH_IMAGERY_MAP_MAX_ZOOM = EARTH_IMAGERY_MAX_ZOOM - 1;
export type EarthImageryProvider = 'eox' | 'usgs';
// The National Map advertises 1:9,028 maximum scale. Level 16 was verified to return
// a real JPEG near the research footprint; level 17 returns 404. Do not overscale it.
export const USGS_IMAGERY_MAX_ZOOM = 16;
export const earthImageryMaxZoom = (provider: EarthImageryProvider) => provider === 'usgs' ? USGS_IMAGERY_MAX_ZOOM : EARTH_IMAGERY_MAX_ZOOM;
export const EARTH_IMAGERY_TILE_BUDGET = 256;
const MAX_TILE_BYTES = 524288;
const TILE_TIMEOUT_MS = 8000;
const TILE_ROOT = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/GoogleMapsCompatible';

export function earthImageryTileUrl(z: number, x: number, y: number, provider: EarthImageryProvider = 'eox'): string {
  if (![z, x, y].every(Number.isInteger) || z < 0 || z > earthImageryMaxZoom(provider)
    || x < 0 || y < 0 || x >= 2 ** z || y >= 2 ** z) throw new Error('Invalid satellite tile');
  // WMTS is matrix/row/column, whereas the map supplies z/x/y.
  return provider === 'usgs'
    ? `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/${z}/${y}/${x}`
    : `${TILE_ROOT}/${z}/${y}/${x}.jpg`;
}

/** No application API, credentials, automatic retry or unbounded response reaches this loader. */
export function createEarthTileLoader(protocol: string, loaded: () => void, failed: (limited: boolean) => void,
  fetchTile: typeof fetch = globalThis.fetch, provider: EarthImageryProvider = 'eox'): { load: AddProtocolAction; close: () => void } {
  const session = new AbortController();
  let requests = 0, active = 0;
  const waiting = new Set<() => void>();
  const acquire = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
    const take = () => {
      if (signal.aborted || active < 4) {
        waiting.delete(take); signal.removeEventListener('abort', take);
        if (signal.aborted) reject(new DOMException('Aborted', 'AbortError'));
        else { active++; resolve(); }
      }
    };
    waiting.add(take); signal.addEventListener('abort', take, { once: true }); take();
  });
  const load: AddProtocolAction = async (request, caller) => {
    const timeout = new AbortController();
    const signal = AbortSignal.any([session.signal, caller.signal, timeout.signal]);
    let acquired = false, limited = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const url = new URL(request.url);
      const match = /^\/(\d+)\/(\d+)\/(\d+)$/.exec(url.pathname);
      if (url.protocol !== `${protocol}:` || url.hostname !== 'tiles' || url.username || url.password || url.port || url.search || url.hash || !match) throw new Error('Invalid satellite tile');
      const tile = earthImageryTileUrl(Number(match[1]), Number(match[2]), Number(match[3]), provider);
      if (requests >= EARTH_IMAGERY_TILE_BUDGET) { limited = true; throw new Error('Satellite tile budget reached'); }
      requests++;
      await acquire(signal); acquired = true;
      timer = setTimeout(() => timeout.abort(), TILE_TIMEOUT_MS);
      const response = await fetchTile(tile, { signal, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error' });
      if (!response.ok || !response.headers.get('Content-Type')?.toLowerCase().startsWith('image/jpeg')) throw new Error('Invalid satellite response');
      const length = Number(response.headers.get('Content-Length'));
      if (Number.isFinite(length) && length > MAX_TILE_BYTES) throw new Error('Satellite tile too large');
      const reader = response.body?.getReader();
      if (!reader) throw new Error('Missing satellite image');
      const chunks: Uint8Array[] = []; let size = 0;
      try {
        while (true) {
          const part = await reader.read();
          if (part.done) break;
          size += part.value.byteLength;
          if (size > MAX_TILE_BYTES) { await reader.cancel(); throw new Error('Satellite tile too large'); }
          chunks.push(part.value);
        }
      } finally { reader.releaseLock(); }
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      const data = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.byteLength; }
      if (data[0] !== 255 || data[1] !== 216) throw new Error('Invalid satellite image');
      loaded();
      return { data: data.buffer, cacheControl: response.headers.get('Cache-Control') ?? undefined };
    } catch {
      const cancelled = session.signal.aborted || caller.signal.aborted;
      if (!cancelled) { failed(limited); session.abort(); }
      if (cancelled || timeout.signal.aborted) throw new DOMException('Aborted', 'AbortError');
      // No provider body, request URL or browser exception text is presented to the user.
      throw new Error('SATELLITE_IMAGERY_UNAVAILABLE');
    } finally {
      if (timer !== undefined) clearTimeout(timer);
      if (acquired) { active--; for (const take of waiting) take(); }
    }
  };
  return { load, close: () => session.abort() };
}
