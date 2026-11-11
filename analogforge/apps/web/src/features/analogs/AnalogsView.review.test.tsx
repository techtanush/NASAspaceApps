import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import seed from '../../mock/fixtures/seed.json';
import { RunContext, type RunContextValue, type Schema } from '../runs/RunContext';
import { AnalogsView } from './AnalogsView';
vi.mock('../../maps/EarthMap', () => ({ EarthMap: () => <div>Map boundary</div> }));
vi.mock('../../api/artifacts', () => ({ findEvidenceByAlgorithm: vi.fn(async () => undefined) }));
vi.mock('../../api/client', () => ({ api: { get: vi.fn(async () => null) } }));

function mount(action: RunContextValue['action']) {
  const context: RunContextValue = {
    snapshot: { run_id: 'run', workspace_id: seed.workspaceId, selected_candidate_id: null, revision: 1 } as Schema['RunSnapshot'],
    contract: seed.missionPresets.MARS as Schema['MissionTestContract'],
    candidates: seed.candidates as Schema['EarthAnalogCandidate'][], qualifications: [],
    pending: false, action, showEvidence: vi.fn(),
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><BrowserRouter><RunContext.Provider value={context}>
    <Link to="/runs/run/qualification">Open qualification</Link>
    <Routes><Route path="/runs/run/analogs" element={<AnalogsView />} />
      <Route path="/runs/run/qualification" element={<h1>Qualification</h1>} /></Routes>
  </RunContext.Provider></BrowserRouter></QueryClientProvider>);
}
beforeEach(() => { window.history.replaceState(null, '', '/runs/run/analogs'); });
afterEach(() => { window.history.replaceState(null, '', '/'); });

it('does not redirect a newer tab navigation when a candidate acknowledgement finishes in the same turn', async () => {
  let acknowledge!: (value: boolean) => void;
  const action = vi.fn(() => new Promise<boolean>(resolve => { acknowledge = resolve; }));
  mount(action);
  fireEvent.click(screen.getAllByTestId('btn-select-candidate')[0]!);
  expect(action).toHaveBeenCalledOnce();
  await act(async () => {
    fireEvent.click(screen.getByRole('link', { name: 'Open qualification' }));
    acknowledge(true);
    await Promise.resolve();
  });
  await waitFor(() => expect(window.location.pathname).toBe('/runs/run/qualification'));
  expect(screen.getByRole('heading', { name: 'Qualification' })).toBeVisible();
});

it('still records acknowledged candidate selection in the URL while the user stays on Analogs', async () => {
  mount(vi.fn(async () => true));
  fireEvent.click(screen.getAllByTestId('btn-select-candidate')[0]!);
  await waitFor(() => expect(new URLSearchParams(window.location.search).get('candidate')).toBe(seed.candidates[0]!.id));
  expect(window.location.pathname).toBe('/runs/run/analogs');
});
