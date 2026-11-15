import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { components } from '../generated/schema';
import { fetchPlanetaryTile } from '../api/planetaryImagery';
import { PlanetaryBasemap } from './PlanetaryBasemap';

vi.mock('../api/planetaryImagery', async original => ({ ...await original<typeof import('../api/planetaryImagery')>(), fetchPlanetaryTile: vi.fn() }));
const aoi: components['schemas']['AreaOfInterest'] = { body:'MARS',bbox:[137.31534,-4.884353,137.48466,-4.715647],latitude_type:'PLANETOCENTRIC',longitude_convention:'NEG180_180',crs_wkt:null,vertical_datum:'Unknown' };
beforeEach(() => {
  vi.mocked(fetchPlanetaryTile).mockReset().mockResolvedValue(new Blob(['test tile']));
  vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:orbital-test'); static revokeObjectURL = vi.fn(); });
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('loads bounded real-source tiles, describes the region and keeps source limits discoverable', async () => {
  render(<PlanetaryBasemap aoi={aoi}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(screen.getByRole('img',{name:'Mars orbital imagery of the selected mission region'}).querySelectorAll('image').length).toBeGreaterThan(0);
  expect(vi.mocked(fetchPlanetaryTile).mock.calls.length).toBeLessThanOrEqual(16);
  expect(screen.getByText(/MRO Context Camera/)).toBeInTheDocument();
  fireEvent.click(screen.getByText('Imagery source and accuracy'));
  expect(screen.getByText(/Preliminary uncontrolled beta01/)).toBeVisible();
  expect(screen.getByText(/visual context; slope, traversability/)).toBeVisible();
});

it('zooms to genuinely different source tiles, stops at the source ceiling and never changes the AOI', async () => {
  const original = structuredClone(aoi);
  render(<PlanetaryBasemap aoi={aoi}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  const first = vi.mocked(fetchPlanetaryTile).mock.calls[0]![1];
  fireEvent.click(screen.getByRole('button',{name:'Zoom in on planetary surface'}));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(vi.mocked(fetchPlanetaryTile).mock.calls.at(-1)![1]).toBe(first + 1);
  fireEvent.click(screen.getByRole('button',{name:'Zoom in on planetary surface'}));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(screen.getByRole('button',{name:'Zoom in on planetary surface'})).toBeDisabled();
  expect(aoi).toEqual(original);
});

it('exposes failed tiles honestly, does not auto-retry, and permits an explicit retry', async () => {
  vi.mocked(fetchPlanetaryTile).mockRejectedValue(new Error('provider unavailable'));
  render(<PlanetaryBasemap aoi={aoi}/>);
  await screen.findByText('Orbital imagery could not load.');
  const calls = vi.mocked(fetchPlanetaryTile).mock.calls.length;
  await act(async () => {});
  expect(fetchPlanetaryTile).toHaveBeenCalledTimes(calls);
  expect(calls).toBeLessThanOrEqual(4);
  fireEvent.click(screen.getByRole('button',{name:'Reload imagery'}));
  await waitFor(() => expect(vi.mocked(fetchPlanetaryTile).mock.calls.length).toBeGreaterThan(calls));
});

it('aborts tile work and revokes images when leaving a site', async () => {
  const {unmount} = render(<PlanetaryBasemap aoi={aoi}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  const signal = vi.mocked(fetchPlanetaryTile).mock.calls[0]![4];
  unmount();
  expect(signal.aborted).toBe(true);
  expect(URL.revokeObjectURL).toHaveBeenCalled();
});


it.each(['MARS', 'MOON'] as const)('labels %s coordinates in the body frame without implying Earth WGS84', async body => {
  render(<PlanetaryBasemap aoi={{ ...aoi, body }}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  const caption = screen.getByText('Selected region').closest('div')!;
  expect(caption).toHaveTextContent('137.40000° E, 4.80000° S');
  expect(caption).toHaveTextContent(`${body === 'MARS' ? 'Mars' : 'Moon'} · planetocentric latitude, east-positive longitude`);
  expect(caption).not.toHaveTextContent('WGS84');
});


it.each([
  { body: 'MARS', bbox: [137.399, -4.801, 137.401, -4.799] },
  { body: 'MOON', bbox: [23.308, 0.509, 23.638, 0.839] },
] as const)('responds to the first $body zoom-out and restores the original outline after pan/recenter', async ({ body, bbox }) => {
  const selected = { ...aoi, body, bbox: [...bbox] }, original = JSON.stringify(selected);
  render(<PlanetaryBasemap aoi={selected}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  const rect = screen.getByRole('img').querySelector('rect')!;
  const initialOutline = ['x', 'y', 'width', 'height'].map(name => rect.getAttribute(name));
  const initialLevel = vi.mocked(fetchPlanetaryTile).mock.calls[0]![1];
  fireEvent.click(screen.getByRole('button', { name: 'Zoom out on planetary surface' }));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(vi.mocked(fetchPlanetaryTile).mock.calls.at(-1)![1]).toBe(initialLevel - 1);
  expect(Number(rect.getAttribute('width'))).toBeCloseTo(Number(initialOutline[2]) / 2);
  fireEvent.click(screen.getByRole('button', { name: 'Pan planetary imagery east' }));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('button', { name: 'Recenter selected planetary region' }));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(vi.mocked(fetchPlanetaryTile).mock.calls.at(-1)![1]).toBe(initialLevel);
  expect(['x', 'y', 'width', 'height'].map(name => rect.getAttribute(name))).toEqual(initialOutline);
  expect(JSON.stringify(selected)).toBe(original);
});


it('pans immediately from the actual polar camera and reverses outward pans without accumulated clamp debt', async () => {
  const selected = { ...aoi, body: 'MOON' as const, bbox: [-45, -89.16, 45, -87.84] }, original = JSON.stringify(selected);
  render(<PlanetaryBasemap aoi={selected}/>);
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  const rect = screen.getByRole('img').querySelector('rect')!;
  const initialY = rect.getAttribute('y');
  fireEvent.click(screen.getByRole('button', { name: 'Pan planetary imagery north' }));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(rect.getAttribute('y')).not.toBe(initialY);
  // The camera is clamped at the south edge; repeated outward requests must not build hidden debt.
  for (let i = 0; i < 3; i++) {
    fireEvent.click(screen.getByRole('button', { name: 'Pan planetary imagery south' }));
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  }
  expect(rect.getAttribute('y')).toBe(initialY);
  fireEvent.click(screen.getByRole('button', { name: 'Pan planetary imagery north' }));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(rect.getAttribute('y')).not.toBe(initialY);
  expect(JSON.stringify(selected)).toBe(original);
});
