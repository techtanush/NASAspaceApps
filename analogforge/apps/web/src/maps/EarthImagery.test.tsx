import { afterEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AddProtocolAction, Map as MapInstance } from 'maplibre-gl';
import type { components } from '../generated/schema';
import { EarthImagery, earthImageryBounds, earthImageryGroundSampling, EARTH_IMAGERY_SOURCE } from './EarthImagery';
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

it('retains an offline default, then installs georeferenced regional tiles only after opt-in and restores camera constraints', () => {
  const map = fakeMap(), active = vi.fn();
  render(<EarthImagery map={map as unknown as MapInstance} aoi={aoi} onActiveChange={active}/>);
  expect(state.protocols.size).toBe(0); expect(map.addSource).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  expect(map.addSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE, expect.objectContaining({ type: 'raster', tileSize: 256, minzoom: 0, maxzoom: 13, bounds: [-111.1, 34.9, -110.87, 35.13] }));
  expect(map.setMaxZoom).toHaveBeenCalledWith(12); expect(active).toHaveBeenLastCalledWith(true);
  expect(screen.getByText(/Historical 2016\/2017 mosaic/)).toHaveTextContent('nominal 10 m Sentinel-2 input');
  expect(screen.getByText(/Historical 2016\/2017 mosaic/)).toHaveTextContent('15.7 m/pixel');
  expect(screen.getByRole('link', { name: 'CC BY 4.0' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  expect(state.protocols.size).toBe(0); expect(map.removeSource).toHaveBeenCalledWith(EARTH_IMAGERY_SOURCE);
  expect(map.setMaxZoom).toHaveBeenLastCalledWith(22); expect(map.setMaxBounds).toHaveBeenLastCalledWith(null); expect(active).toHaveBeenLastCalledWith(false);
});

it('does not offer loading without WebGL or supported geographic coordinates', () => {
  render(<EarthImagery map={null} aoi={aoi} onActiveChange={vi.fn()}/>);
  expect(screen.getByRole('button', { name: 'Load satellite imagery' })).toBeDisabled();
  for (const bad of [{ ...aoi, body: 'MARS' }, { ...aoi, crs_wkt: 'EPSG:3857' }, { ...aoi, bbox: [170, 1, -170, 2] },
    { ...aoi, bbox: [-120, 30, -110, 40] }, { ...aoi, bbox: [-111, 85, -110, 86] }, { ...aoi, bbox: [NaN, 35, -110, 36] }]) {
    expect(earthImageryBounds(bad as typeof aoi)).toBeNull();
  }
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
    for (let i = 0; i < 65; i++) await load({ url: `${protocol}://tiles/13/${1555 + i}/3239` }, new AbortController()).catch(() => {});
    error({ sourceId: EARTH_IMAGERY_SOURCE });
  });
  expect(screen.getByRole('status')).toHaveTextContent('64-tile limit');
  expect(active).toHaveBeenLastCalledWith(false); expect(state.protocols.size).toBe(0);
});
