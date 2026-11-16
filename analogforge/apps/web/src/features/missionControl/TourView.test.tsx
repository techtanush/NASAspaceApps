import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import type { components } from '../../generated/schema';
import seed from '../../mock/fixtures/seed.json';
import type { useRunData } from './useRunData';
import { TourView } from './TourView';
import { api } from '../../api/client';

type S = components['schemas'];
const state = vi.hoisted(() => ({ run: {} as ReturnType<typeof useRunData>, publication: 'UNPUBLISHED' }));
vi.mock('./useRunData', () => ({ useRunData: () => state.run }));
vi.mock('./useRunAssurance', () => ({ useRunAssurance: () => ({ publication: state.publication }) }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <aside>{children}</aside>, Panel: ({ title, step, children, footer, notice, testid }: { title: string; step: string; children: ReactNode; footer: ReactNode; notice: ReactNode; testid: string }) => <section data-testid={testid}><p>{step}</p><h1>{title}</h1>{notice}<div className="mc-panel-body">{children}</div>{footer}</section> }));
vi.mock('./RegionalInspector', () => ({ RegionalInspector: ({ site }: { site: { candidate: { name: string } } }) => <section aria-label="Regional map">{site.candidate.name}</section>, TargetInspector: () => <section aria-label="Target map"/> }));
vi.mock('./RunActivity', () => ({ RunActivity: () => <p>Persisted operation log</p> }));
vi.mock('./RunTerminalNotice', () => ({ RunTerminalNotice: () => <p role="status">Recorded terminal reason</p> }));
vi.mock('./BenchmarkEvidence', () => ({ BenchmarkEvidence: ({ site }: { site: { candidate: { id: string } } }) => <p>Benchmarks for {site.candidate.id}</p> }));
vi.mock('./SiteFieldPlan', () => ({ SiteFieldPlan: () => <p>Scoped field plan</p> }));
vi.mock('./EnvironmentContext', () => ({ EnvironmentContext: () => <p>Stored environment context</p> }));
vi.mock('./EarthNomination', () => ({ EarthNomination: () => <p>Nomination boundary</p> }));
vi.mock('./EvidenceBriefDownload', () => ({ EvidenceBriefDownload: () => <button>Download current evidence PDF</button> }));
beforeEach(() => {
  vi.restoreAllMocks();
  state.publication = 'UNPUBLISHED';
  state.run = { snapshot: { run_id: seed.runId, mode: 'synthetic', state: 'AWAITING_REVIEW', candidate_ids: seed.candidates.slice(0, 2).map(candidate => candidate.id), blocked_dependencies: [], portfolio_ids: [] }, contract: { ...seed.missionPresets.MARS, id: 'mission', name: 'Terrain rehearsal' }, candidates: seed.candidates.slice(0, 2), qualifications: [], results: [], lastEvent: { summary: 'Comparing the next accepted slope requirement.' }, connection: 'connected', loading: false, pending: false, action: vi.fn() } as unknown as ReturnType<typeof useRunData>;
});
function tour() { return <MemoryRouter initialEntries={[`/runs/${seed.runId}/tour`]}><Routes><Route path="/runs/:runId/tour" element={<TourView/>}/></Routes></MemoryRouter>; }
function mount() { const view = render(tour()); fireEvent.click(screen.getByRole('button', {name:'Inspect location 1'})); return view; }
it('starts on Earth with an individual location directory and a separate results dashboard', () => {
  render(tour());
  expect(screen.getByRole('heading', {name:'Your Earth test locations'})).toBeVisible();
  expect(screen.getByRole('region', {name:'Earth location directory'})).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name:'Open results dashboard'}));
  expect(screen.getByRole('heading', {name:'Your location test plan'})).toBeVisible();
  expect(screen.getByRole('region', {name:'All-location rehearsal plan'})).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name:'Back to Earth'}));
  expect(screen.getByRole('button', {name:'Inspect location 1'})).toBeVisible();
  expect(screen.getByRole('button', {name:'Inspect location 2'})).toBeVisible();
  expect(screen.queryByRole('region', {name:'Regional map'})).not.toBeInTheDocument();
  expect(state.run.action).not.toHaveBeenCalled();
});
it('explains unsupported returned coordinates instead of inventing a map position or reporting no results', () => {
  state.run.snapshot = {...state.run.snapshot!,state:'COMPLETED'} as S['RunSnapshot'];
  state.run.candidates = state.run.candidates.map(candidate => ({...candidate,aoi:{...candidate.aoi,crs_wkt:'EPSG:32612',bbox:[400000,3900000,401000,3901000]}}));
  render(tour());
  expect(screen.getByRole('heading',{name:'Earth coordinates need review'})).toBeVisible();
  expect(screen.getByRole('status')).toHaveTextContent('unsupported Earth coordinates');
  expect(screen.queryByRole('button',{name:'Inspect location 1'})).toBeNull();
});
it('runs the selected rover test in the tour after confirming the exact current selection and revision', async () => {
  state.run.snapshot = {...state.run.snapshot!, state:'AWAITING_REVIEW', workspace_id:'workspace', revision:7,
    rover_revision_id:'rover', selected_candidate_id:null, pending_review:{allowed_actions:['SELECT_CANDIDATE','PROVE_IT']}} as S['RunSnapshot'];
  vi.mocked(state.run.action).mockResolvedValue(true);
  vi.spyOn(api, 'get').mockResolvedValue({...state.run.snapshot, revision:8, selected_candidate_id:seed.candidates[0]!.id});
  mount(); fireEvent.click(screen.getByRole('button', {name:'Run rover test here'}));
  await waitFor(() => expect(state.run.action).toHaveBeenLastCalledWith({action_type:'PROVE_IT',expected_revision:8,payload:{candidate_id:seed.candidates[0]!.id}}));
  expect(screen.getByRole('region', {name:'Regional map'})).toBeVisible();
});
it('does not bypass the evidence review or prove a different site after a selection race', async () => {
  state.run.snapshot = {...state.run.snapshot!, state:'AWAITING_REVIEW', workspace_id:'workspace', revision:7,
    rover_revision_id:'rover', selected_candidate_id:null, pending_review:{allowed_actions:['SELECT_CANDIDATE','PROVE_IT']}} as S['RunSnapshot'];
  vi.mocked(state.run.action).mockResolvedValue(true);
  vi.spyOn(api, 'get').mockResolvedValue({...state.run.snapshot, revision:8, selected_candidate_id:'another-site'});
  mount(); fireEvent.click(screen.getByRole('button', {name:'Run rover test here'}));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not ready for a rover test'));
  expect(state.run.action).toHaveBeenCalledTimes(1);
  expect(vi.mocked(state.run.action).mock.calls[0]![0].action_type).toBe('SELECT_CANDIDATE');
});
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
it('keeps research on one progress screen until the saved results are ready, then opens Earth', async () => {
  state.run.snapshot = {...state.run.snapshot!, state:'QUALIFYING'} as S['RunSnapshot'];
  const view = render(tour());
  expect(screen.getByTestId('run-progress')).toBeVisible();
  expect(screen.queryByRole('button', {name:'Inspect location 1'})).toBeNull();
  expect(screen.getByText('Persisted operation log')).toBeVisible();
  state.run = {...state.run, snapshot:{...state.run.snapshot!, state:'AWAITING_REVIEW'} as S['RunSnapshot']};
  view.rerender(tour());
  expect(await screen.findByRole('heading', {name:'Your Earth test locations'})).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name:'Inspect location 1'}));
  expect(screen.getByRole('region', {name:'Regional map'})).toHaveTextContent(seed.candidates[0]!.name);
  fireEvent.click(screen.getByRole('button', {name:'Next site'}));
  expect(screen.getByRole('region', {name:'Regional map'})).toHaveTextContent(seed.candidates[1]!.name);
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
