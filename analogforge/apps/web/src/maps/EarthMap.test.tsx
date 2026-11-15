import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { components } from '../generated/schema';
import { EarthMap } from './EarthMap';
import seed from '../mock/fixtures/seed.json';
vi.mock('maplibre-gl', () => ({ setWorkerUrl: vi.fn() }));
afterEach(() => vi.restoreAllMocks());
it('retains the tour label and starts with one identified opaque raster while keeping every layer accessible', () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  const candidate = seed.candidates[0] as components['schemas']['EarthAnalogCandidate'];
  const layer = (id: string, kind: components['schemas']['DisplayLayerManifest']['layer_kind'], unit: string): components['schemas']['DisplayLayerManifest'] => ({ id, workspace_id: candidate.workspace_id, run_id: candidate.run_id, candidate_id: candidate.id, target_profile_id: null, body: 'EARTH', layer_kind: kind, rendering: 'EARTH_WEBMERCATOR_IMAGE', mode: 'synthetic', unit, support_scale_m: 60, legend: [{ label: `${kind} legend`, lower: null, upper: null, color: '#123456' }], image_artifact_sha256: 'a'.repeat(64), display_crs_wkt: 'EPSG:3857', pixel_to_world: [1, 0, 0, 0, -1, 0], width_px: 2, height_px: 2, earth_corners: [[0, 1], [1, 1], [1, 0], [0, 0]], source_evidence_ids: [], nodata_transparent: true, limitations: [], attribution: [] });
  render(<EarthMap candidates={[candidate]} selected={candidate.id} candidateLabels={{ [candidate.id]: 'Site 4' }} onSelect={() => {}} layers={[layer('elevation', 'ELEVATION', 'm'), layer('slope', 'SLOPE', 'deg')]}/>);
  expect(screen.getByText(/Selected: Site 4/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Load satellite imagery' })).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: 'Show ELEVATION prepared layer' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' })).not.toBeChecked();
  expect(screen.getByTestId('raster-selection')).toHaveTextContent('ELEVATION (m)');
  expect(screen.getByTestId('raster-selection')).not.toHaveTextContent('SLOPE');
  for (const slider of screen.getAllByRole('slider')) expect(slider).toHaveValue('1');
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show SLOPE prepared layer' }));
  expect(screen.getByTestId('raster-selection')).toHaveTextContent('Selected raster overlay');
  expect(screen.getByTestId('raster-selection')).toHaveTextContent('SLOPE (deg)');
});

it('keeps analysis colors hidden when satellite imagery is the default, including before WebGL initializes', () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  const candidate = seed.candidates[0] as components['schemas']['EarthAnalogCandidate'];
  render(<EarthMap candidates={[candidate]} selected={candidate.id} onSelect={() => {}} allowSatelliteImagery autoLoad/>);
  expect(screen.queryByTestId('raster-selection')).toBeNull();
  expect(screen.getByRole('status')).toHaveTextContent('Map unavailable');
  expect(screen.queryByText('Loading satellite tiles…')).toBeNull();
  expect(screen.getByRole('button', {name:'Measured terrain view'})).toBeDisabled();
});
