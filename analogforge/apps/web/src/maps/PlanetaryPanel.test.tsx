import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { components } from '../generated/schema';
import { api } from '../api/client';
import fixtures from '../mock/fixtures/display-assets.json';
import seed from '../mock/fixtures/seed.json';
import { PlanetaryPanel } from './PlanetaryPanel';
vi.mock('./PlanetaryBasemap', () => ({ PlanetaryBasemap: () => <div>Orbital imagery</div> }));

type S = components['schemas'];
const aoi = seed.missionPresets.MARS.target as S['AreaOfInterest'];
const layer: S['DisplayLayerManifest'] = { ...fixtures.layers.MARS, id: 'display', workspace_id: 'workspace', run_id: 'run', mode: 'synthetic', body: 'MARS', rendering: 'PLANETARY_PLANAR_IMAGE', candidate_id: null, target_profile_id: 'profile', layer_kind: 'ELEVATION', image_artifact_sha256: 'a'.repeat(64), width_px: 64, height_px: 64, earth_corners: null, legend: [], unit: 'm', source_evidence_ids: [], nodata_transparent: true, attribution: [], limitations: [] };
beforeEach(() => {
  class DisplayURL extends URL { static createObjectURL = vi.fn(() => 'blob:prepared-display'); static revokeObjectURL = vi.fn(); }
  vi.stubGlobal('URL', DisplayURL);
  vi.spyOn(api, 'raw').mockResolvedValue(new Response(new Blob(['prepared image'])));
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('moves a visible crosshair to arbitrary display points and gives keyboard and pointer inspection identical coordinates', () => {
  render(<PlanetaryPanel aoi={aoi} layers={[layer]}/>);
  fireEvent.click(screen.getByRole('button', { name: 'Measured terrain' }));
  const inspector = screen.getByRole('group', { name: /MARS bounding box/ });
  fireEvent.focus(inspector);
  fireEvent.keyDown(inspector, { key: 'ArrowRight' });
  fireEvent.keyDown(inspector, { key: 'ArrowDown', shiftKey: true });
  expect(screen.getByTestId('planetary-crosshair')).toHaveAttribute('transform', 'translate(241 170)');
  const coordinates = screen.getByTestId('planetary-inspection').textContent;
  expect(coordinates).toContain('display CRS coordinates');
  expect(coordinates).toContain('Analysis cell values require committed evidence');
  fireEvent.keyDown(inspector, { key: 'Enter' });
  fireEvent.keyDown(inspector, { key: ' ' });
  expect(screen.getByTestId('planetary-inspection')).toHaveTextContent(coordinates!);
  vi.spyOn(inspector, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 480, height: 320 } as DOMRect);
  fireEvent.click(inspector, { clientX: 241, clientY: 170 });
  expect(screen.getByTestId('planetary-inspection')).toHaveTextContent(coordinates!);
  expect(screen.getByTestId('planetary-inspection')).toHaveAttribute('aria-live', 'polite');
  expect(screen.getByTestId('planetary-inspection')).toHaveAttribute('aria-atomic', 'true');
  fireEvent.keyDown(inspector, { key: 'Home' });
  expect(screen.getByTestId('planetary-crosshair')).toHaveAttribute('transform', 'translate(240 160)');
  expect(api.raw).toHaveBeenCalledTimes(1);
});

it('keeps geometry-only inspection honest, clamps the crosshair, and resets it when the target changes', () => {
  const { rerender } = render(<PlanetaryPanel aoi={aoi}/>);
  fireEvent.click(screen.getByText('Coordinates and region tools'));
  const inspector = screen.getByRole('group', { name: /MARS bounding box/ });
  for (let index = 0; index < 50; index++) fireEvent.keyDown(inspector, { key: 'ArrowLeft', shiftKey: true });
  for (let index = 0; index < 40; index++) fireEvent.keyDown(inspector, { key: 'ArrowUp', shiftKey: true });
  expect(screen.getByTestId('planetary-crosshair')).toHaveAttribute('transform', 'translate(0 0)');
  expect(screen.getByTestId('planetary-inspection')).toHaveTextContent('Geometry only; analysis cell measurements are unavailable');
  expect(screen.getByTestId('planetary-inspection')).not.toHaveTextContent('display CRS coordinates');
  expect(api.raw).not.toHaveBeenCalled();
  rerender(<PlanetaryPanel aoi={{ ...aoi, body: 'MOON' }}/>);
  expect(screen.getByTestId('planetary-crosshair')).toHaveAttribute('transform', 'translate(240 160)');
  expect(screen.getByTestId('planetary-inspection')).toHaveTextContent('Select display pixel');
});
