import { afterEach, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import { createEarthTileLoader, earthImageryTileUrl, EARTH_IMAGERY_TILE_BUDGET } from './earthImagery';

const request = (z = 13, x = 1555, y = 3239) => ({ url: `af-test://tiles/${z}/${x}/${y}` });
const jpeg = () => new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg', 'Cache-Control': 'max-age=86400' } });
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

it('maps z/x/y to the verified 2016 WMTS matrix/row/column and rejects unsupported levels', () => {
  expect(earthImageryTileUrl(13, 1555, 3239)).toBe('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/GoogleMapsCompatible/13/3239/1555.jpg');
  for (const args of [[14, 0, 0], [-1, 0, 0], [13, 8192, 1], [13, 1, -1], [13.5, 1, 1], [NaN, 1, 1]]) {
    expect(() => earthImageryTileUrl(...args as [number, number, number])).toThrow();
  }
});

it('uses the exact USGS host and row/column order through its verified level 16, rejecting overscale', async () => {
  expect(earthImageryTileUrl(16, 12470, 25865, 'usgs')).toBe('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/16/25865/12470');
  expect(() => earthImageryTileUrl(17, 24940, 51730, 'usgs')).toThrow();
  expect(() => earthImageryTileUrl(16, 65536, 0, 'usgs')).toThrow();
  const fetchTile = vi.fn<typeof fetch>().mockImplementation(async () => jpeg());
  const failed = vi.fn(), loader = createEarthTileLoader('af-test', vi.fn(), failed, fetchTile, 'usgs');
  await loader.load(request(16, 12470, 25865), new AbortController());
  expect(fetchTile.mock.calls[0]).toEqual([earthImageryTileUrl(16, 12470, 25865, 'usgs'), expect.objectContaining({ credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error' })]);
  await expect(loader.load({ url: 'af-test://tiles/16/12470/25865?host=other' }, new AbortController())).rejects.toThrow('SATELLITE_IMAGERY_UNAVAILABLE');
  expect(fetchTile).toHaveBeenCalledOnce(); loader.close();
});

it('does no work until explicitly invoked, then fetches only the fixed host without credentials or referrer', async () => {
  const fetchTile = vi.fn<typeof fetch>().mockImplementation(async () => jpeg());
  const loaded = vi.fn(), failed = vi.fn();
  const loader = createEarthTileLoader('af-test', loaded, failed, fetchTile);
  expect(fetchTile).not.toHaveBeenCalled();
  const result = await loader.load(request(), new AbortController());
  expect(fetchTile).toHaveBeenCalledOnce();
  expect(fetchTile.mock.calls[0]).toEqual([earthImageryTileUrl(13, 1555, 3239), expect.objectContaining({ credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error' })]);
  expect(new Uint8Array(result.data as ArrayBuffer)).toEqual(new Uint8Array([255, 216, 255, 217]));
  expect(result.cacheControl).toBe('max-age=86400');
  expect(loaded).toHaveBeenCalledOnce(); expect(failed).not.toHaveBeenCalled(); loader.close();
});

it.each(['other://tiles/13/1/1', 'af-test://foreign/13/1/1', 'af-test://user:password@tiles/13/1/1',
  'af-test://tiles/13/1/1?token=private', 'af-test://tiles/13/1/1#other', 'af-test://tiles/14/1/1'])('rejects foreign or malformed tile identity: %s', async url => {
  const fetchTile = vi.fn<typeof fetch>(); const failed = vi.fn();
  const loader = createEarthTileLoader('af-test', vi.fn(), failed, fetchTile);
  await expect(loader.load({ url }, new AbortController())).rejects.toThrow('SATELLITE_IMAGERY_UNAVAILABLE');
  expect(fetchTile).not.toHaveBeenCalled(); expect(failed).toHaveBeenCalledWith(false); loader.close();
});

it('stops at exactly 256 requests and reports the budget limit without retries', async () => {
  const fetchTile = vi.fn<typeof fetch>().mockImplementation(async () => jpeg()); const failed = vi.fn();
  const loader = createEarthTileLoader('af-test', vi.fn(), failed, fetchTile);
  for (let i = 0; i < EARTH_IMAGERY_TILE_BUDGET; i++) await loader.load(request(13, 1555 + i), new AbortController());
  await expect(loader.load(request(), new AbortController())).rejects.toThrow();
  expect(fetchTile).toHaveBeenCalledTimes(256); expect(failed.mock.calls).toEqual([[true]]); loader.close();
});

it.each(['http', 'content-type', 'length', 'body-limit', 'invalid-jpeg'])('fails closed and sanitizes %s failures', async fault => {
  const fetchTile = vi.fn<typeof fetch>().mockImplementation(async () => {
    if (fault === 'http') return new Response('provider private error', { status: 503 });
    if (fault === 'content-type') return new Response('private html', { headers: { 'Content-Type': 'text/html' } });
    if (fault === 'length') return new Response(new Uint8Array([255, 216]), { headers: { 'Content-Type': 'image/jpeg', 'Content-Length': '524289' } });
    if (fault === 'body-limit') return new Response(new Uint8Array(524289), { headers: { 'Content-Type': 'image/jpeg' } });
    return new Response('not jpeg', { headers: { 'Content-Type': 'image/jpeg' } });
  });
  const failed = vi.fn(), loaded = vi.fn(); const loader = createEarthTileLoader('af-test', loaded, failed, fetchTile);
  await expect(loader.load(request(), new AbortController())).rejects.toThrow('SATELLITE_IMAGERY_UNAVAILABLE');
  expect(failed).toHaveBeenCalledWith(false); expect(loaded).not.toHaveBeenCalled(); expect(fetchTile).toHaveBeenCalledOnce(); loader.close();
});

it('limits concurrent requests to four and cancels queued and active work on close', async () => {
  const fetchTile = vi.fn<typeof fetch>().mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  }));
  const failed = vi.fn(); const loader = createEarthTileLoader('af-test', vi.fn(), failed, fetchTile);
  const calls = Array.from({ length: 8 }, (_, i) => loader.load(request(13, 1555 + i), new AbortController()).catch(error => error));
  await waitFor(() => expect(fetchTile).toHaveBeenCalledTimes(4));
  loader.close(); const outcomes = await Promise.all(calls);
  expect(outcomes.every(error => error.name === 'AbortError')).toBe(true);
  expect(fetchTile).toHaveBeenCalledTimes(4); expect(failed).not.toHaveBeenCalled();
});

it('times out an active request after eight seconds and does not retry', async () => {
  vi.useFakeTimers();
  const fetchTile = vi.fn<typeof fetch>().mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  }));
  const failed = vi.fn(); const loader = createEarthTileLoader('af-test', vi.fn(), failed, fetchTile);
  const outcome = loader.load(request(), new AbortController()).catch(error => error);
  await vi.advanceTimersByTimeAsync(8001);
  expect((await outcome).name).toBe('AbortError'); expect(failed).toHaveBeenCalledWith(false);
  expect(fetchTile).toHaveBeenCalledOnce(); loader.close();
});
