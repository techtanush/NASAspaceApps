import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import { SiteFieldPlan, type FieldPlan } from './SiteFieldPlan';
vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace-one' }));
const plan: FieldPlan = { run_id: 'run-one', run_revision: 5, candidate_id: 'site-two', center: [-111.5, 35.5], bbox: [-112, 35, -111, 36], route: null, route_note: 'Route not yet computed for this location.', field_readiness: 'Field survey required.', steps: ['Survey the ground.'], screened_count: 4, dataset_lock_id: 'test-lock' };
function mount() { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><SiteFieldPlan runId="run-one" candidateId="site-two" revision={5}/></MemoryRouter></QueryClientProvider>); }
it('shows a region centre without inventing driving endpoints for a site without a route', async () => {
  vi.mocked(api.get).mockResolvedValue(plan); mount();
  expect(await screen.findByText('Start and finish are not established.')).toBeVisible();
  expect(screen.getByText('Reference coordinate · not an approved starting point')).toBeVisible();
  expect(api.get).toHaveBeenCalledWith('/runs/run-one/candidates/site-two/test-plan', expect.anything());
  expect(screen.queryByText('Start', { exact: true })).toBeNull();
});
it('shows stored loop endpoints, scoped checkpoints and design assumptions separately from criteria', async () => {
  vi.mocked(api.get).mockResolvedValue({ ...plan, route: { start: [-111.5, 35.5], finish: [-111.5, 35.5], coordinates: [[-111.5, 35.5], [-111.4, 35.6], [-111.5, 35.5]], outcome: 'PASS', support_scale_m: 500,
    checkpoints: [{ id: 'W1', position: [-111.4, 35.6], activity: 'STOP', capability: null, dwell_s: 60, tolerance_m: 50, requirement_ids: [], origin: 'USER_DESIGNATED' }], assumptions: ['Procedural stop only; no material evidence.'] } }); mount();
  expect(await screen.findByText(/return loop/)).toBeVisible();
  expect(screen.getByText('No accepted mission criterion assigned to this checkpoint.')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Inspect modeled route checks and telemetry' })).toHaveAttribute('href', '/runs/run-one/test-lab');
  expect(screen.getByRole('img')).toHaveAccessibleName(/not a surveyed field corridor/);
});
it('rejects another site’s route instead of showing its coordinates', async () => {
  vi.mocked(api.get).mockResolvedValue({ ...plan, candidate_id: 'foreign-site' }); mount();
  expect(await screen.findByRole('heading', { name: 'Field test plan unavailable' })).toBeVisible();
  expect(screen.queryByText('Assessed region centre')).toBeNull();
});
