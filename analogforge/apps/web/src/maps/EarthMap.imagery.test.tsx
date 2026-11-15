import { afterEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { components } from '../generated/schema';
import seed from '../mock/fixtures/seed.json';
import { EarthMap } from './EarthMap';

type Row = { layout?: Record<string, unknown>; paint?: Record<string, unknown>; id: string };
const state = vi.hoisted(() => ({ map: null as null | {
  emit: (event: string) => void;
  layers: Map<string, Row>;
  sources: Map<string, unknown>;
}, protocols: new Map<string, unknown>() }));
vi.mock('../api/client', () => ({ api: { raw: vi.fn(async () => ({ blob: async () => new Blob(['prepared raster']) })) } }));
vi.mock('./layerRegistry', () => ({ validateEarthLayer: vi.fn() }));
vi.mock('maplibre-gl', () => ({
  setWorkerUrl: vi.fn(), addProtocol: vi.fn((name, handler) => state.protocols.set(name, handler)), removeProtocol: vi.fn(name => state.protocols.delete(name)),
  Map: vi.fn(function () {
    const layers = new Map<string, Row>([['background', { id: 'background' }]]), sources = new Map<string, unknown>();
    const listeners = new Map<string, Set<() => void>>();
    let ready = false;
    const instance = {
      layers, sources,
      emit: (event: string) => { if (event === 'load') ready = true; for (const handler of listeners.get(event) ?? []) handler(); },
      on: (event: string, handler: unknown, layerHandler?: unknown) => {
        const fn = (layerHandler ?? handler) as () => void;
        if (!listeners.has(event)) listeners.set(event, new Set()); listeners.get(event)!.add(fn);
      },
      once: (event: string, fn: () => void) => { if (!listeners.has(event)) listeners.set(event, new Set()); listeners.get(event)!.add(fn); },
      off: (event: string, fn: () => void) => listeners.get(event)?.delete(fn),
      isStyleLoaded: () => ready,
      addSource: (id: string, source: object) => sources.set(id, { ...source, setData: vi.fn() }), getSource: (id: string) => sources.get(id), removeSource: (id: string) => sources.delete(id),
      addLayer: (layer: Row) => layers.set(layer.id, layer), getLayer: (id: string) => layers.get(id), removeLayer: (id: string) => layers.delete(id),
      setLayoutProperty: (id: string, name: string, value: unknown) => { const row = layers.get(id)!; row.layout = { ...row.layout, [name]: value }; },
      setPaintProperty: (id: string, name: string, value: unknown) => { const row = layers.get(id)!; row.paint = { ...row.paint, [name]: value }; },
      getMaxZoom: () => 22, getMaxBounds: () => null, setMaxZoom: vi.fn(), setMaxBounds: vi.fn(),
      addControl: vi.fn(), resize: vi.fn(), remove: vi.fn(), fitBounds: vi.fn(), getCanvas: () => document.createElement('canvas'),
    };
    state.map = instance; return instance;
  }),
  Marker: class { setLngLat() { return this; } addTo() { return this; } remove() {} }, ScaleControl: class {},
}));
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); state.map = null; state.protocols.clear(); });

it('hides measurement colors only while opted in, then restores the exact chosen raster and opacity', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as CanvasRenderingContext2D);
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:prepared'), revokeObjectURL: vi.fn() }));
  const external = vi.fn(); vi.stubGlobal('fetch', external);
  const candidate = seed.candidates[0] as components['schemas']['EarthAnalogCandidate'];
  const layer = (id: string, kind: 'ELEVATION' | 'SLOPE'): components['schemas']['DisplayLayerManifest'] => ({ id, workspace_id: candidate.workspace_id, run_id: candidate.run_id, candidate_id: candidate.id, target_profile_id: null, body: 'EARTH', layer_kind: kind, rendering: 'EARTH_WEBMERCATOR_IMAGE', mode: 'synthetic', unit: kind === 'SLOPE' ? 'deg' : 'm', support_scale_m: 60, legend: [{ label: `${kind} legend`, lower: null, upper: null, color: '#123456' }], image_artifact_sha256: 'a'.repeat(64), display_crs_wkt: 'EPSG:3857', pixel_to_world: [1, 0, 0, 0, -1, 0], width_px: 2, height_px: 2, earth_corners: [[0, 1], [1, 1], [1, 0], [0, 0]], source_evidence_ids: [], nodata_transparent: true, limitations: [], attribution: [] });
  render(<EarthMap candidates={[candidate]} selected={candidate.id} onSelect={vi.fn()} allowSatelliteImagery layers={[layer('elevation', 'ELEVATION'), layer('slope', 'SLOPE')]}/>);
  act(() => state.map!.emit('load'));
  await waitFor(() => expect(state.map!.layers.has('display-slope')).toBe(true));
  expect(external).not.toHaveBeenCalled(); expect(state.protocols.size).toBe(0);
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show ELEVATION prepared layer' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' }));
  fireEvent.change(screen.getAllByRole('slider')[1]!, { target: { value: '0.4' } });
  expect(state.map!.layers.get('display-slope')!.layout?.visibility).toBe('visible');
  expect(screen.getByTestId('raster-selection')).toHaveTextContent('SLOPE (deg)');
  fireEvent.click(screen.getByRole('button', { name: 'Load satellite imagery' }));
  expect(state.map!.layers.get('display-elevation')!.layout?.visibility).toBe('none');
  expect(state.map!.layers.get('display-slope')!.layout?.visibility).toBe('none');
  expect(state.map!.layers.get('candidates')!.paint?.['fill-opacity']).toBe(0);
  expect(screen.queryByTestId('raster-selection')).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain view' }));
  expect(state.map!.layers.get('display-elevation')!.layout?.visibility).toBe('none');
  expect(state.map!.layers.get('display-slope')!.layout?.visibility).toBe('visible');
  expect(state.map!.layers.get('display-slope')!.paint?.['raster-opacity']).toBe(0.4);
  expect(state.map!.layers.get('candidates')!.paint?.['fill-opacity']).toBe(1);
  expect(screen.getByTestId('raster-selection')).toHaveTextContent('SLOPE (deg)');
  expect(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' })).not.toBeDisabled();
  expect(state.protocols.size).toBe(0); expect(external).not.toHaveBeenCalled();
});
