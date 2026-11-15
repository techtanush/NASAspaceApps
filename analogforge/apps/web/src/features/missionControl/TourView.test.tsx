import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import type { components } from '../../generated/schema';
import seed from '../../mock/fixtures/seed.json';
import type { useRunData } from './useRunData';
import { TourView } from './TourView';

type S = components['schemas'];
const state = vi.hoisted(() => ({ run: {} as ReturnType<typeof useRunData>, publication: 'UNPUBLISHED' }));
vi.mock('./useRunData', () => ({ useRunData: () => state.run }));
vi.mock('./useRunAssurance', () => ({ useRunAssurance: () => ({ publication: state.publication }) }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <aside>{children}</aside>, Panel: ({ title, step, children, footer, notice, testid }: { title: string; step: string; children: ReactNode; footer: ReactNode; notice: ReactNode; testid: string }) => <section data-testid={testid}><p>{step}</p><h1>{title}</h1>{notice}<div className="mc-panel-body">{children}</div>{footer}</section> }));
vi.mock('./RegionalInspector', () => ({ RegionalInspector: ({ site }: { site: { candidate: { name: string } } }) => <section aria-label="Regional map">{site.candidate.name}</section>, TargetInspector: () => <section aria-label="Target map"/> }));
vi.mock('./RunActivity', () => ({ RunActivity: () => <p>Persisted operation log</p> }));
vi.mock('./RunTerminalNotice', () => ({ RunTerminalNotice: () => <p role="status">Recorded terminal reason</p> }));
vi.mock('./BenchmarkEvidence', () => ({ BenchmarkEvidence: ({ site }: { site: { candidate: { id: string } } }) => <p>Benchmarks for {site.candidate.id}</p> }));
vi.mock('./EnvironmentContext', () => ({ EnvironmentContext: () => <p>Stored environment context</p> }));
vi.mock('./EarthNomination', () => ({ EarthNomination: () => <p>Nomination boundary</p> }));
vi.mock('./EvidenceBriefDownload', () => ({ EvidenceBriefDownload: () => <button>Download current evidence PDF</button> }));
beforeEach(() => {
  state.publication = 'UNPUBLISHED';
  state.run = { snapshot: { run_id: seed.runId, mode: 'synthetic', state: 'QUALIFYING', candidate_ids: seed.candidates.slice(0, 2).map(candidate => candidate.id), blocked_dependencies: [], portfolio_ids: [] }, contract: { ...seed.missionPresets.MARS, id: 'mission', name: 'Terrain rehearsal' }, candidates: seed.candidates.slice(0, 2), qualifications: [], results: [], lastEvent: { summary: 'Comparing the next accepted slope requirement.' }, connection: 'connected', loading: false, pending: false, action: vi.fn() } as unknown as ReturnType<typeof useRunData>;
});
function tour() { return <MemoryRouter initialEntries={[`/runs/${seed.runId}/tour`]}><Routes><Route path="/runs/:runId/tour" element={<TourView/>}/></Routes></MemoryRouter>; }
function mount() { return render(tour()); }
it('keeps limited publication visible beside workflow completion without opening technical details', async () => {
  state.publication = 'LIMITED';
  state.run.snapshot = { ...state.run.snapshot!, state: 'COMPLETED', passport_id: 'registered-passport' } as S['RunSnapshot'];
  mount();
  await screen.findByRole('region', { name: 'Regional map' });
  expect(screen.getByLabelText('Run publication assurance')).toHaveTextContent('LIMITED');
  expect(screen.getByText('Run details and provenance').closest('details')).not.toHaveAttribute('open');
  expect(state.run.action).not.toHaveBeenCalled();
});
it('keeps the selected map mounted while newly pinned qualification records load', async () => {
  const view = mount();
  const map = await screen.findByRole('region', { name: 'Regional map' });
  state.run = { ...state.run, loading: true, qualifications: [] };
  view.rerender(tour());
  expect(screen.getByRole('region', { name: 'Regional map' })).toBe(map);
  expect(screen.getByText('Location 1 of 2')).toBeVisible();
  expect(screen.queryByTestId('tour-loading')).toBeNull();
  expect(screen.getByText('Benchmarks for ' + seed.candidates[0]!.id)).toBeVisible();
});
it('opens each actual location map and keeps in-progress work visible while candidate evidence is incomplete', async () => {
  mount();
  await waitFor(() => expect(screen.getByRole('region', { name: 'Regional map' })).toHaveTextContent(seed.candidates[0]!.name));
  expect(screen.getByText('Location 1 of 2')).toBeVisible();
  expect(screen.getByText('Checking each requirement')).toBeVisible();
  expect(screen.getByText(/Candidate locations are provisional/)).toBeVisible();
  expect(screen.queryByText('Comparing the next accepted slope requirement.')).toBeNull();
  expect(screen.getByText('Investigation work log').closest('details')).toHaveAttribute('open');
  expect(screen.queryByRole('group', { name: 'Result presentation' })).toBeNull();
  expect(screen.getByRole('heading', { name: 'Benchmarks and measured results' })).toBeVisible();
  expect(screen.getByText('No benchmark has yet demonstrated a supported rehearsal here. Review the measured results and remaining unknowns below.')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Next site' }));
  await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(seed.candidates[1]!.name));
  expect(screen.getByRole('region', { name: 'Regional map' })).toHaveTextContent(seed.candidates[1]!.name);
  expect(screen.getByTestId('link-report')).toHaveAttribute('href', `/runs/${seed.runId}/report?site=${seed.candidates[1]!.id}`);
  expect(screen.getByTestId('site-selection-announcement')).toHaveTextContent(`Site 2 of 2: ${seed.candidates[1]!.name}`);
});
it('keeps failed-run reason visible and retains explicit globe and target access', async () => {
  state.run.snapshot = { ...state.run.snapshot!, state: 'FAILED' } as S['RunSnapshot']; mount();
  await screen.findByRole('region', { name: 'Regional map' }); expect(screen.getByText('Recorded terminal reason')).toBeVisible();
  expect(screen.getByText('Investigation work log').closest('details')).not.toHaveAttribute('open');
  fireEvent.click(screen.getByRole('button', { name: /^Globe$/ }));
  expect(screen.queryByRole('region', { name: 'Regional map' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Target evidence' })); expect(screen.getByRole('region', { name: 'Target map' })).toBeVisible();
});
it('changes results disclosure depth without changing the selected location or failed-run truth', async () => {
  state.run.snapshot = { ...state.run.snapshot!, state: 'FAILED' } as S['RunSnapshot']; mount();
  await screen.findByRole('region', { name: 'Regional map' });
  expect(screen.getByRole('button', { name: 'Simplified' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByText('Run details and provenance').closest('details')).not.toHaveAttribute('open');
  fireEvent.click(screen.getByRole('button', { name: 'Technical details' }));
  expect(screen.getByText('Run details and provenance').closest('details')).toHaveAttribute('open');
  expect(screen.getByText('Recorded terminal reason')).toBeVisible();
  expect(screen.getByRole('region', { name: 'Regional map' })).toHaveTextContent(seed.candidates[0]!.name);
  fireEvent.click(screen.getByRole('button', { name: 'Next site' }));
  await waitFor(() => expect(screen.getByRole('region', { name: 'Regional map' })).toHaveTextContent(seed.candidates[1]!.name));
  expect(screen.getByRole('button', { name: 'Technical details' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Simplified' }));
  expect(screen.getByText('Run details and provenance').closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText('Recorded terminal reason')).toBeVisible();
  expect(state.run.action).not.toHaveBeenCalled();
});
