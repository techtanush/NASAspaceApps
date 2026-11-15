import { afterEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AddProtocolAction, Map as MapInstance } from 'maplibre-gl';
import type { components } from '../generated/schema';
import { EarthImagery, earthImageryBounds, earthImageryGroundSampling, supportsUsgsDetail, EARTH_IMAGERY_SOURCE, EARTH_IMAGERY_WORLD_BOUNDS } from './EarthImagery';
import seed from '../mock/fixtures/seed.json';
const state = vi.hoisted(() => ({ protocols: new Map<string, AddProtocolAction>() }));
vi.mock('maplibre-gl', () => ({ addProtocol: vi.fn((name, action) => state.protocols.set(name, action)), removeProtocol: vi.fn(name => state.protocols.delete(name)) }));
const aoi = seed.candidates[0]!.aoi as components['schemas']['AreaOfInterest'];
function fakeMap() {
  const sources = new Map(), layers = new Map();
  return { getMaxZoom: () => 22, getMaxBounds: () => null, setMaxZoom: vi.fn(), setMaxBounds: vi.fn(), on: vi.fn(), off: vi.fn(),
    addSource: vi.fn((id, value) => sources.set(id, value)), getSource: (id: string) => sources.get(id), removeSource: vi.fn(id => sources.delete(id)),
    addLayer: vi.fn(value => layers.set(value.id, value)), getLayer: (id: string) => layers.get(id), removeLayer: vi.fn(id => layers.delete(id)) };
}
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); state.protocols.clear(); });

it('loads finer US aerial tiles without moving the scientific footprint, and switches to global imagery explicitly', () => {
  const map = fakeMap(), active = vi.fn(), original = JSON.stringify(aoi);
  render(<EarthImagery autoLoad preferHighDetail map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  expect(map.addSource).toHaveBeenLastCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ maxzoom: 16 }));
  expect(map.setMaxZoom).toHaveBeenLastCalledWith(15);
  expect(screen.getByText(/Historical aerial/)).toHaveTextContent('2.0 m/pixel');
  fireEvent.click(screen.getByText('Imagery source and resolution'));
  expect(screen.getByRole('link', { name: /USDA \/ USGS/ })).toBeVisible();
  fireEvent.change(screen.getByLabelText('Imagery layer'), { target: { value: 'eox' } });
  expect(map.addSource).toHaveBeenLastCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ maxzoom: 13 }));
  expect(map.setMaxZoom).toHaveBeenLastCalledWith(12); expect(state.protocols.size).toBe(1);
  expect(JSON.stringify(aoi)).toBe(original);
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  expect(map.setMaxZoom).toHaveBeenLastCalledWith(22); expect(state.protocols.size).toBe(0);
});

it('uses global imagery outside conservative continental-US coverage without inventing aerial coverage', () => {
  const elsewhere = { ...aoi, bbox: [12.0, 43.0, 12.1, 43.1] }, map = fakeMap();
  expect(supportsUsgsDetail(elsewhere)).toBe(false);
  expect(supportsUsgsDetail({ ...aoi, body: 'MARS' })).toBe(false);
  render(<EarthImagery autoLoad preferHighDetail map={map as unknown as MapInstance} aoi={elsewhere} onActiveChange={vi.fn()}/>);
  expect(map.addSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ maxzoom: 13 }));
  expect(screen.queryByLabelText('Imagery layer')).not.toBeInTheDocument();
  expect(earthImageryGroundSampling(aoi, 'usgs')).toBeCloseTo(earthImageryGroundSampling(aoi)! / 8, 10);
});

it('retains an offline default, then installs georeferenced regional tiles only after opt-in and restores camera constraints', () => {
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0); expect(map.addSource).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  expect(map.addSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ type: 'raster', tileSize: 256, minzoom: 0, maxzoom: 13, bounds: [-180, -85, 180, 85] }));
  expect(map.setMaxZoom).toHaveBeenCalledWith(12); expect(active).toHaveBeenLastCalledWith(true);
  expect(screen.getByText(/Historical satellite/)).toHaveTextContent('15.7 m/pixel');
  expect(screen.getByRole('link', { name: 'CC BY 4.0', hidden: true })).not.toBeVisible();
  fireEvent.click(screen.getByText('Imagery source and resolution'));
  expect(screen.getByText(/Historical 2016\/2017 mosaic/)).toHaveTextContent('nominal 10 m Sentinel-2 input');
  expect(screen.getByRole('link', { name: 'CC BY 4.0' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  expect(state.protocols.size).toBe(0); expect(map.removeSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE);
  expect(map.setMaxZoom).toHaveBeenLastCalledWith(22); expect(map.setMaxBounds).not.toHaveBeenCalled(); expect(active).toHaveBeenLastCalledWith(false);
});

it('does not offer loading without WebGL or supported geographic coordinates', () => {
  render(<EarthImagery map={null} aoi={aoi} onActiveChange={vi.fn()}/>);
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeDisabled();
  for (const bad of [{ ...aoi, body: 'MARS' }, { ...aoi, crs_wkt: 'EPSG:3857' }, { ...aoi, bbox: [170, 1, -170, 2] },
    { ...aoi, bbox: [-120, 30, -110, 40] }, { ...aoi, bbox: [-111, 85, -110, 86] }, { ...aoi, bbox: [NaN, 35, -110, 36] }]) {
    expect(earthImageryBounds(bad as typeof aoi)).toBeNull();
  }
});

it('accepts the canonical null-CRS Earth AOI emitted by the science screen without rewriting candidate metadata', () => {
  const canonical = { ...aoi, crs_wkt: null }, original = JSON.stringify(canonical);
  const map = fakeMap(), active = vi.fn();
  expect(earthImageryBounds(canonical)).toEqual(earthImageryBounds(aoi));
  expect(earthImageryGroundSampling(canonical)).toEqual(earthImageryGroundSampling(aoi));
  render(<EarthImagery map={map as unknown as MapInstance} aoi={canonical} onActiveChange={active}/>);
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  expect(map.addSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ bounds: EARTH_IMAGERY_WORLD_BOUNDS }));
  expect(active).toHaveBeenLastCalledWith(true); expect(JSON.stringify(canonical)).toBe(original);
});

it.each([
  { crs_wkt: undefined }, { crs_wkt: '' }, { crs_wkt: 'UNKNOWN' }, { crs_wkt: 'EPSG:3857' },
  { crs_wkt: 'EPSG:32612' }, { body: 'MARS' }, { latitude_type: 'PLANETOCENTRIC' },
  { latitude_type: 'PLANETOGRAPHIC' }, { latitude_type: undefined }, { longitude_convention: 'ZERO_360' },
  { longitude_convention: undefined }, { bbox: [440000, 3900000, 441000, 3901000] },
])('does not infer a geographic frame for missing, projected or mixed axis metadata: %s', patch => {
  const unsupported = { ...aoi, crs_wkt: null, ...patch } as unknown as typeof aoi;
  expect(earthImageryBounds(unsupported)).toBeNull(); expect(earthImageryGroundSampling(unsupported)).toBeNull();
});

it('labels delivered Mercator sampling by latitude instead of claiming nominal sensor resolution for every tile', () => {
  const flagstaff = { ...aoi, bbox: [-111.66, 35.19, -111.64, 35.2066] };
  expect(earthImageryGroundSampling(flagstaff)).toBeCloseTo(15.615358747, 6);
  expect(earthImageryGroundSampling({ ...aoi, bbox: [-0.1, -0.1, 0.1, 0.1] })).toBeCloseTo(19.109257071, 6);
  expect(earthImageryGroundSampling({ ...aoi, crs_wkt: 'EPSG:3857' })).toBeNull();
});

it('restores offline mode on provider failure and displays no provider response body', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('PRIVATE PROVIDER BODY', { status: 503 })));
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  const [protocol, load] = [...state.protocols.entries()][0]!;
  await act(async () => { await load({ url: `${protocol}://tiles/13/1555/3239` }, new AbortController()).catch(() => {}); });
  await waitFor(() => expect(active).toHaveBeenLastCalledWith(false));
  expect(screen.getByRole('status')).toHaveTextContent('Satellite imagery unavailable');
  expect(screen.queryByText(/PRIVATE PROVIDER BODY/)).not.toBeInTheDocument(); expect(state.protocols.size).toBe(0);
});

it('removes old imagery and its protocol when a new site is selected, requiring a fresh opt-in', () => {
  const map = fakeMap(), active = vi.fn();
  const view = render(<EarthImagery key="site-one" map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  expect(state.protocols.size).toBe(1);
  view.rerender(<EarthImagery key="site-two" map={map as unknown as MapInstance} aoi={{ ...aoi, bbox: [-112, 35, -111.99, 35.01] }} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0); expect(map.removeSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE);
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeVisible(); expect(map.addSource).toHaveBeenCalledTimes(1);
});

it('also restores measured terrain when the map cannot decode or display a tile', () => {
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  const callback = map.on.mock.calls[0]![1] as (event: { sourceId: string }) => void;
  act(() => callback({ sourceId: EARTH_IMAGERY_SOURCE }));
  expect(screen.getByRole('status')).toHaveTextContent('Satellite imagery unavailable');
  expect(active).toHaveBeenLastCalledWith(false); expect(state.protocols.size).toBe(0);
});

it('aborts its protocol when the owning map is removed without updating a destroyed camera', () => {
  const map = fakeMap(), active = vi.fn();
  const view = render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  const remove = map.on.mock.calls.find(call => call[0] === 'remove')![1] as () => void;
  act(() => remove()); expect(state.protocols.size).toBe(0);
  view.unmount(); expect(map.setMaxZoom.mock.calls).toEqual([[12]]);
  expect(active).toHaveBeenLastCalledWith(false);
});

it('keeps the actual tile-budget reason when the map subsequently emits its generic load error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg' } })));
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  const [protocol, load] = [...state.protocols.entries()][0]!;
  const error = map.on.mock.calls[0]![1] as (event: { sourceId: string }) => void;
  await act(async () => {
    for (let i = 0; i < 257; i++) await load({ url: `${protocol}://tiles/13/${1555 + i}/3239` }, new AbortController()).catch(() => {});
    error({ sourceId: EARTH_IMAGERY_SOURCE });
  });
  expect(screen.getByRole('status')).toHaveTextContent('256-tile limit');
  expect(active).toHaveBeenLastCalledWith(false); expect(state.protocols.size).toBe(0);
});


it('starts an authorized selected-site view once its map is ready, and honors the later measured-view choice', () => {
  const map = fakeMap(), active = vi.fn();
  const view = render(<EarthImagery autoLoad map={null} aoi={aoi} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0);
  view.rerender(<EarthImagery autoLoad map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(1); expect(active).toHaveBeenLastCalledWith(true);
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  view.rerender(<EarthImagery autoLoad map={map as unknown as MapInstance} aoi={{ ...aoi }} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0); expect(map.addSource).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeVisible();
});

it('does not automatically retry a failed site but starts a fresh bounded view for a newly selected site', () => {
  const map = fakeMap(), active = vi.fn();
  const view = render(<EarthImagery key="one" autoLoad map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  const fail = map.on.mock.calls.find(call => call[0] === 'error')![1] as (event: { sourceId: string }) => void;
  act(() => fail({ sourceId: EARTH_IMAGERY_SOURCE }));
  view.rerender(<EarthImagery key="one" autoLoad map={map as unknown as MapInstance} aoi={{ ...aoi }} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0); expect(map.addSource).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('status')).toHaveTextContent('Satellite imagery unavailable');
  view.rerender(<EarthImagery key="two" autoLoad map={map as unknown as MapInstance} aoi={{ ...aoi, bbox: [-112, 35, -111.99, 35.01] }} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(1); expect(map.addSource).toHaveBeenCalledTimes(2);
  expect(map.removeSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE);
});

it('does not auto-load unsupported planetary or projected footprints', () => {
  const map = fakeMap();
  render(<EarthImagery autoLoad map={map as unknown as MapInstance} aoi={{ ...aoi, crs_wkt: 'EPSG:3857' }} onActiveChange={vi.fn()}/>);
  expect(state.protocols.size).toBe(0); expect(map.addSource).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeDisabled();
  expect(screen.queryByText('Loading satellite tiles…')).not.toBeInTheDocument();
});


it('allows country and distant world views without expanding the immutable selected scientific footprint', async () => {
  const fetchTile = vi.fn().mockImplementation(async () => new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg' } }));
  vi.stubGlobal('fetch', fetchTile);
  const map = fakeMap(), active = vi.fn(), original = JSON.stringify(aoi);
  render(<EarthImagery autoLoad map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  expect(map.setMaxBounds).not.toHaveBeenCalled();
  expect(map.addSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ bounds: [-180, -85, 180, 85], maxzoom: 13 }));
  const [protocol, load] = [...state.protocols.entries()][0]!;
  await act(async () => {
    // Country-scale tile near western Europe and a distant high-detail tile in Japan are both
    // valid visual requests even though the selected scientific footprint remains in Arizona.
    await load({ url: `${protocol}://tiles/4/8/5` }, new AbortController());
    await load({ url: `${protocol}://tiles/13/7276/3228` }, new AbortController());
  });
  expect(fetchTile).toHaveBeenCalledTimes(2);
  expect(fetchTile.mock.calls[0]![0]).toContain('/4/5/8.jpg');
  expect(fetchTile.mock.calls[1]![0]).toContain('/13/3228/7276.jpg');
  expect(JSON.stringify(aoi)).toBe(original);
  expect(screen.getByText(/Loading uses the public EOX tile service/)).toHaveTextContent('measured coverage remains limited to the selected footprint');
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  expect(map.setMaxBounds).not.toHaveBeenCalled(); expect(map.setMaxZoom).toHaveBeenLastCalledWith(22);
});


it('keeps satellite view through a canceled camera tile and then loads the next visible tile', async () => {
  const fetchTile = vi.fn().mockImplementationOnce((_url: RequestInfo | URL, options?: RequestInit) => new Promise<Response>((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(new DOMException('Superseded tile', 'AbortError')), { once: true });
  })).mockResolvedValue(new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg' } }));
  vi.stubGlobal('fetch', fetchTile);
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery autoLoad map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  const [protocol, load] = [...state.protocols.entries()][0]!;
  const onError = map.on.mock.calls.find(call => call[0] === 'error')![1] as (event: { sourceId: string; error: Error }) => void;
  const caller = new AbortController();
  await act(async () => {
    const canceled = load({ url: `${protocol}://tiles/13/1555/3239` }, caller);
    await Promise.resolve(); expect(fetchTile).toHaveBeenCalledTimes(1);
    caller.abort(); await expect(canceled).rejects.toMatchObject({ name: 'AbortError' });
    onError({ sourceId: EARTH_IMAGERY_SOURCE, error: new DOMException('Superseded tile', 'AbortError') });
  });
  expect(active).toHaveBeenLastCalledWith(true); expect(state.protocols.size).toBe(1);
  expect(screen.getByRole('button', { name: 'Measured terrain view' })).toBeVisible();
  expect(screen.queryByText(/Satellite imagery unavailable/)).not.toBeInTheDocument();
  await act(async () => { await load({ url: `${protocol}://tiles/12/777/1619` }, new AbortController()); });
  expect(fetchTile).toHaveBeenCalledTimes(2); expect(state.protocols.size).toBe(1);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(active).toHaveBeenLastCalledWith(true);
});
