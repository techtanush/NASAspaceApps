import { afterEach, expect, it, vi } from 'vitest';
import type { components } from '../generated/schema';
import { fetchPlanetaryTile, planetaryTileUrl, planetaryViewport } from './planetaryImagery';

const aoi: components['schemas']['AreaOfInterest'] = { body: 'MARS', bbox: [137.31534,-4.884353,137.48466,-4.715647], latitude_type: 'PLANETOCENTRIC', longitude_convention: 'NEG180_180', crs_wkt: null, vertical_datum: 'Unknown' };
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it('uses each planetary WMTS matrix directly and never applies Earth Mercator', () => {
  expect(planetaryTileUrl('MARS',8,451,134)).toBe('https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/8/134/451');
  expect(planetaryTileUrl('MOON',8,289,160)).toContain('/8/160/289.jpg');
  for (const args of [[12,0,0],[0,2,0],[0,0,1],[-1,0,0],[1.5,0,0]]) expect(() => planetaryTileUrl('MARS',...args as [number,number,number])).toThrow();
});

it('derives camera tiles and footprint from arbitrary selected regions and caps source detail', () => {
  const gale = planetaryViewport(aoi)!;
  expect(gale.tiles.length).toBeGreaterThan(0); expect(gale.tiles.length).toBeLessThanOrEqual(16);
  expect(gale.selection.width).toBeGreaterThan(100); expect(gale.selection.height).toBeGreaterThan(100);
  const elsewhere = planetaryViewport({ ...aoi, bbox: [-20,10,-19.8,10.2] })!;
  expect(elsewhere.tiles).not.toEqual(gale.tiles);
  expect(planetaryViewport(aoi,100)!.z).toBe(11);
  expect(planetaryViewport({ ...aoi, body: 'MOON' },100)!.z).toBe(8);
  expect(planetaryViewport(aoi,2)!.sampleM).toBeCloseTo(10.17,1);
  expect(planetaryViewport(aoi,0,[1,1])!.bounds).not.toEqual(gale.bounds);
});

it('rejects unsupported bodies, coordinate axes, projections and invalid geometry', () => {
  for (const patch of [ { body:'EARTH' }, { latitude_type:'GEODETIC' }, { longitude_convention:'ZERO_360' },
    { crs_wkt:'EPSG:3857' }, { bbox:[140,0,130,1] }, { bbox:[-181,0,1,1] }, { bbox:[0,0,1,91] }, { bbox:[0,NaN,1,1] } ]) {
    expect(planetaryViewport({ ...aoi, ...patch } as components['schemas']['AreaOfInterest'])).toBeNull();
  }
});

it('fetches a single bounded public image without credentials, redirects or referrer', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(new Uint8Array([137,80,78,71,13,10,26,10]), { headers:{'Content-Type':'image/png'} }));
  vi.stubGlobal('fetch',fetcher);
  expect((await fetchPlanetaryTile('MARS',8,451,134,new AbortController().signal)).type).toBe('image/png');
  expect(fetcher.mock.calls[0]![1]).toMatchObject({ credentials:'omit',redirect:'error',referrerPolicy:'no-referrer' });
});

it.each([
  () => new Response('not an image',{headers:{'Content-Type':'text/html'}}),
  () => new Response('bad bytes',{headers:{'Content-Type':'image/png'}}),
  () => new Response('image',{headers:{'Content-Type':'image/png','Content-Length':'1048577'}}),
  () => new Response(new Uint8Array(1048577),{headers:{'Content-Type':'image/png'}}),
  () => new Response('',{status:404}),
])('fails closed for missing, invalid and oversized image responses', async response => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response()));
  await expect(fetchPlanetaryTile('MARS',8,451,134,new AbortController().signal)).rejects.toThrow();
});

it('cancels in-flight image requests at the existing eight second deadline', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch',vi.fn((_url,{signal}:{signal:AbortSignal}) => new Promise((_resolve,reject) => signal.addEventListener('abort',() => reject(new DOMException('Aborted','AbortError'))))));
  const call = fetchPlanetaryTile('MARS',8,451,134,new AbortController().signal);
  const assertion = expect(call).rejects.toThrow('Aborted');
  await vi.advanceTimersByTimeAsync(8000); await assertion;
});


it.each([
  { body: 'MARS', bbox: [137.399, -4.801, 137.401, -4.799], ceiling: 11 },
  // A ten-kilometre lunar region near the equator is smaller than the finest delivered view.
  { body: 'MOON', bbox: [23.308, 0.509, 23.638, 0.839], ceiling: 8 },
] as const)('zooms out immediately from the deliverable ceiling for small $body regions', ({ body, bbox, ceiling }) => {
  const selected = { ...aoi, body, bbox: [...bbox] }, original = JSON.stringify(selected);
  const initial = planetaryViewport(selected)!, wider = planetaryViewport(selected, -1)!;
  expect(initial.z).toBe(ceiling); expect(wider.z).toBe(ceiling - 1);
  expect(wider.width).toBeCloseTo(initial.width * 2);
  expect(wider.selection.width).toBeCloseTo(initial.selection.width / 2);
  expect(wider.selection.height).toBeCloseTo(initial.selection.height / 2);
  // Zoom changes the view, never the geographic region, and reversing it restores the same camera.
  expect(planetaryViewport(selected, 0)!.bounds).toEqual(initial.bounds);
  const offset: [number, number] = [0.1, 0.1];
  expect(planetaryViewport(selected, -1, offset)!.bounds).not.toEqual(wider.bounds);
  for (const view of [initial, wider, planetaryViewport(selected, 0, offset)!]) {
    expect(view.bounds[0] + view.selection.x / 640 * view.width).toBeCloseTo(bbox[0], 10);
    expect(view.bounds[3] - view.selection.y / 400 * view.height).toBeCloseTo(bbox[3], 10);
    expect(view.selection.width / 640 * view.width).toBeCloseTo(bbox[2] - bbox[0], 10);
    expect(view.selection.height / 400 * view.height).toBeCloseTo(bbox[3] - bbox[1], 10);
  }
  expect(JSON.stringify(selected)).toBe(original);
});
