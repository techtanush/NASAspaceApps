import { afterAll, beforeAll, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import seed from '../../mock/fixtures/seed.json';
import { api } from '../../api/client';
import { MissionEditor } from './MissionEditor';

vi.mock('../../api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../rovers/RoverEditor', () => ({ RoverEditor: () => <div>Rover editor boundary</div> }));
vi.mock('../operatorContext/BoundOperatorContext', () => ({ BoundOperatorContext: () => null }));
vi.mock('../../maps/PlanetaryPanel', () => ({ PlanetaryPanel: () => <div>Region preview boundary</div> }));

// The real preset select scrolls its focused option; jsdom has no layout API.
const originalScrollIntoView = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
beforeAll(() => Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() }));
afterAll(() => {
  if (originalScrollIntoView) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScrollIntoView);
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView');
});

const target = seed.missionPresets.MARS.target;
const draft = (name: string, objective = 'Original experiment objective') => ({ name, objective, target });
const header = (id: string, revision = 1) => ({ id, revision, current_draft_id: `${id}-draft`, current_contract_id: null });
const stored = (id: string, value = draft(id === 'mission-a' ? 'Mission A' : 'Mission B')) => ({
  id: `${id}-draft`, mission_id: id, created_at: seed.createdAt, draft: value,
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
function mount(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Link to="/missions/mission-b/edit">Switch mission</Link>
    <Routes>
      <Route path="/missions/new" element={<MissionEditor />} />
      <Route path="/missions/:missionId/edit" element={<MissionEditor />} />
    </Routes>
  </MemoryRouter></QueryClientProvider>);
}
async function defaultGet(path: string): Promise<unknown> {
  if (path === '/capabilities') return { modes: ['synthetic'], scenario_config_ids: ['practice'], default_scenario_config_id: 'practice' };
  if (path === '/configuration/scenarios/practice') return { id: 'practice', name: 'Practice', allowed_modes: ['synthetic'] };
  if (path.startsWith('/mission-drafts/')) return stored(path.includes('mission-b') ? 'mission-b' : 'mission-a');
  if (path.startsWith('/missions/')) return header(path.split('/').at(-1)!);
  throw new Error(`Unexpected test request: ${path}`);
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.get).mockImplementation(defaultGet as typeof api.get);
  vi.mocked(api.post).mockImplementation((async (path: string, body: unknown) => {
    if (path === '/missions') return header('mission-a');
    if (path.endsWith('/drafts')) return stored(path.split('/')[2]!, (body as { draft: ReturnType<typeof draft> }).draft);
    throw new Error(`Unexpected test command: ${path}`);
  }) as typeof api.post);
});

it('keeps body and goals visible while exact coordinates and engineering source settings start collapsed', async () => {
  mount('/missions/new');
  const coordinates=screen.getByText('Exact coordinates and data reference').closest('details')!;
  const data=screen.getByText('Advanced data settings').closest('details')!;
  expect(coordinates.open).toBe(false);expect(data.open).toBe(false);
  expect(screen.getByRole('link',{name:'Open the guided mission setup'})).toHaveAttribute('href','/start/place');
  expect(screen.getByRole('textbox',{name:'Mission name'})).toBeVisible();expect(screen.getByText('Target body')).toBeVisible();
  fireEvent.click(screen.getByText('Exact coordinates and data reference'));
  await waitFor(()=>expect(coordinates.open).toBe(true));
  fireEvent.change(screen.getAllByTestId('input-bbox')[0]!,{target:{value:'-'}});
  expect(coordinates.open).toBe(true);expect(screen.getByRole('alert')).toHaveTextContent('complete numeric');
});

it('starts custom targets with an unknown reference and saves an edited vertical datum in each draft', async () => {
  mount('/missions/new');
  const datum = screen.getByRole('textbox', { name: 'Vertical datum / reference' });
  expect(datum).toHaveValue('Unknown');
  fireEvent.change(datum, { target: { value: 'MOLA areoid' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Mission name' }), { target: { value: 'Real Mars region' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'Compare measured Mars terrain' } });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions', expect.objectContaining({
    target: expect.objectContaining({ body: 'MARS', vertical_datum: 'MOLA areoid' }),
  }), expect.anything()));
  await waitFor(() => expect(screen.getByTestId('save-indicator')).toHaveAttribute('data-save-state', 'saved'));
  fireEvent.change(datum, { target: { value: 'MOLA MEGDR areoid reference' } });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/drafts', expect.objectContaining({
    draft: expect.objectContaining({ target: expect.objectContaining({ vertical_datum: 'MOLA MEGDR areoid reference' }) }),
  }), expect.anything()));
});

it('keeps unfinished coordinates unsaved and preserves negative decimals typed one character at a time', async () => {
  const user = userEvent.setup();
  mount('/missions/mission-a/edit');
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled());
  const south = screen.getByRole('textbox', { name: 'South latitude (deg)' });
  const north = screen.getByRole('textbox', { name: 'North latitude (deg)' });
  await user.clear(south);
  expect(south).toHaveValue('');
  expect(screen.getByTestId('btn-build-fingerprint')).toBeDisabled();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 600)); });
  expect(api.post).not.toHaveBeenCalled();
  await user.type(south, '-');
  expect(south).toHaveValue('-');
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a complete numeric value');
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 600)); });
  expect(api.post).not.toHaveBeenCalled();
  await user.clear(south);
  await user.type(south, '-4.95');
  await user.clear(north);
  await user.type(north, '-4.65');
  expect(south).toHaveValue('-4.95');
  expect(north).toHaveValue('-4.65');
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/drafts', expect.objectContaining({
    draft: expect.objectContaining({ target: expect.objectContaining({ bbox: [137, -4.95, 138, -4.65] }) }),
  }), expect.anything()));
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled());
});

it('loads finite exponential bounds and waits for a complete typed exponent before saving', async () => {
  const user = userEvent.setup();
  vi.mocked(api.get).mockImplementation((async (path: string) => path === '/mission-drafts/mission-a-draft'
    ? stored('mission-a', { ...draft('Mission A'), target: { ...target, bbox: [1e-7, -5, 1, -4] } })
    : defaultGet(path)) as typeof api.get);
  mount('/missions/mission-a/edit');
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled());
  const west = screen.getByRole('textbox', { name: 'West longitude (deg)' });
  expect(west).toHaveValue('1e-7');
  await user.clear(west);
  await user.type(west, '1e');
  expect(west).toHaveValue('1e');
  expect(screen.getByTestId('btn-build-fingerprint')).toBeDisabled();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 600)); });
  expect(api.post).not.toHaveBeenCalled();
  await user.type(west, '-');
  expect(west).toHaveValue('1e-');
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a complete numeric value');
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 600)); });
  expect(api.post).not.toHaveBeenCalled();
  await user.type(west, '6');
  expect(west).toHaveValue('1e-6');
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/drafts', expect.objectContaining({
    draft: expect.objectContaining({ target: expect.objectContaining({ bbox: [1e-6, -5, 1, -4] }) }),
  }), expect.anything()));
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled());
});

it('resets custom body references to Unknown and restores the exact metadata of explicit synthetic presets', async () => {
  mount('/missions/new');
  fireEvent.change(screen.getByRole('textbox', { name: 'Vertical datum / reference' }), { target: { value: 'Custom Mars reference' } });
  fireEvent.click(screen.getByRole('radio', { name: 'Moon' }));
  fireEvent.click(screen.getByRole('button', { name: 'Change body and clear region' }));
  expect(screen.getByRole('textbox', { name: 'Vertical datum / reference' })).toHaveValue('Unknown');
  expect(screen.getByRole('textbox', { name: 'South latitude (deg)' })).toHaveValue(String(seed.missionPresets.MOON.target.bbox[1]));
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Target preset' }), { key: 'ArrowDown' });
  fireEvent.click(await screen.findByRole('option', { name: 'Practice Moon target (synthetic)' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Mission name' }), { target: { value: 'Practice metadata' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'Check explicit preset references' } });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions', expect.objectContaining({
    target: seed.missionPresets.MOON.target,
  }), expect.anything()));
  await waitFor(() => expect(screen.getByTestId('save-indicator')).toHaveAttribute('data-save-state', 'saved'));
  fireEvent.click(screen.getByRole('radio', { name: 'Mars' }));
  fireEvent.click(screen.getByRole('button', { name: 'Change body and clear region' }));
  expect(screen.getByRole('textbox', { name: 'Vertical datum / reference' })).toHaveValue('Unknown');
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Target preset' }), { key: 'ArrowDown' });
  fireEvent.click(await screen.findByRole('option', { name: 'Practice Mars target (synthetic)' }));
  expect(screen.getByRole('textbox', { name: 'South latitude (deg)' })).toHaveValue(String(seed.missionPresets.MARS.target.bbox[1]));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/drafts', expect.objectContaining({
    draft: expect.objectContaining({ target: seed.missionPresets.MARS.target }),
  }), expect.anything()));
});

it('loads the new mission identity when route parameters change without unmounting the editor', async () => {
  mount('/missions/mission-a/edit');
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mission name' })).toHaveValue('Mission A'));
  fireEvent.click(screen.getByRole('link', { name: 'Switch mission' }));
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mission name' })).toHaveValue('Mission B'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'Mission B revised objective' } });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-b/drafts', expect.anything(), expect.anything()));
  expect(vi.mocked(api.post).mock.calls.some(([path]) => path === '/missions/mission-a/drafts')).toBe(false);
});

it('saves the latest edit after a slow initial draft receipt finishes', async () => {
  const receipt = deferred<ReturnType<typeof stored>>();
  vi.mocked(api.get).mockImplementation((async (path: string) =>
    path === '/mission-drafts/mission-a-draft' ? receipt.promise : defaultGet(path)) as typeof api.get);
  mount('/missions/new');
  fireEvent.change(screen.getByRole('textbox', { name: 'Mission name' }), { target: { value: 'Initial mission name' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'Initial mission objective' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/mission-drafts/mission-a-draft'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Mission name' }), { target: { value: 'Latest mission name' } });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 650)); });
  await act(async () => { receipt.resolve(stored('mission-a', draft('Initial mission name', 'Initial mission objective'))); });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/drafts', expect.objectContaining({
    draft: expect.objectContaining({ name: 'Latest mission name' }),
  }), expect.anything()), { timeout: 2000 });
  await waitFor(() => expect(screen.getByTestId('save-indicator')).toHaveAttribute('data-save-state', 'saved'));
});

it('does not offer an obsolete fingerprint after the draft changes during preparation', async () => {
  const job = deferred<{ state: string; proposed_revision_id: string }>();
  const originalPost = vi.mocked(api.post).getMockImplementation()!;
  vi.mocked(api.post).mockImplementation((async (path: string, body: unknown, options: Parameters<typeof api.post>[2]) =>
    path.endsWith('/fingerprint') ? { job_id: 'job-1' } : originalPost(path, body, options)) as typeof api.post);
  vi.mocked(api.get).mockImplementation((async (path: string) => {
    if (path === '/jobs/job-1') return job.promise;
    if (path === '/mission-revisions/old-proposal') return {
      ...seed.missionPresets.MARS, id: 'old-proposal', mission_id: 'mission-a', revision: 1,
      accepted_at: null, objective: 'Original experiment objective',
    };
    return defaultGet(path);
  }) as typeof api.get);
  mount('/missions/mission-a/edit');
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled());
  fireEvent.click(screen.getByTestId('btn-build-fingerprint'));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/jobs/job-1'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'Materially different experiment' } });
  await act(async () => { job.resolve({ state: 'SUCCEEDED', proposed_revision_id: 'old-proposal' }); });
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).not.toHaveTextContent('Preparing'));
  expect(screen.queryAllByTestId('requirement-row')).toHaveLength(0);
  expect(screen.getByTestId('btn-accept-contract')).toBeDisabled();
});

it('does not restore an accepted revision into a draft edited while acceptance was pending', async () => {
  const receipt = deferred<unknown>();
  const proposal = { ...seed.missionPresets.MARS, id: 'proposal', mission_id: 'mission-a', revision: 1, accepted_at: null };
  vi.mocked(api.get).mockImplementation((async (path: string) => {
    if (path === '/missions/mission-a') return { ...header('mission-a'), current_contract_id: 'proposal' };
    if (path === '/mission-revisions/proposal') return proposal;
    return defaultGet(path);
  }) as typeof api.get);
  const originalPost = vi.mocked(api.post).getMockImplementation()!;
  vi.mocked(api.post).mockImplementation((async (path: string, body: unknown, options: Parameters<typeof api.post>[2]) =>
    path.endsWith('/accept') ? receipt.promise : originalPost(path, body, options)) as typeof api.post);
  mount('/missions/mission-a/edit');
  await waitFor(() => expect(screen.getByTestId('btn-accept-contract')).toBeEnabled());
  fireEvent.click(screen.getByTestId('btn-accept-contract'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/missions/mission-a/accept', expect.anything(), expect.anything()));
  fireEvent.change(screen.getByRole('textbox', { name: 'Experiment objective' }), { target: { value: 'A new draft after acceptance began' } });
  await act(async () => { receipt.resolve({ ...proposal, accepted_at: seed.createdAt }); });
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).not.toHaveTextContent('Preparing'));
  expect(screen.queryAllByTestId('requirement-row')).toHaveLength(0);
  expect(screen.getByTestId('btn-start-run')).toBeDisabled();
});

it('keeps an existing mission read-only until its saved identity and draft have loaded', async () => {
  const pendingHeader = deferred<ReturnType<typeof header>>();
  vi.mocked(api.get).mockImplementation((async (path: string) =>
    path === '/missions/mission-b' ? pendingHeader.promise : defaultGet(path)) as typeof api.get);
  mount('/missions/mission-b/edit');
  expect(screen.queryByRole('textbox', { name: 'Mission name' })).not.toBeInTheDocument();
  expect(screen.getByRole('status', { name: 'Retrieving the saved mission draft' })).toBeVisible();
  expect(api.post).not.toHaveBeenCalled();
  await act(async () => { pendingHeader.resolve(header('mission-b')); });
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mission name' })).toHaveValue('Mission B'));
  expect(api.post).not.toHaveBeenCalled();
});

it('offers a safe retry after a saved mission fails to load without exposing a blank form', async () => {
  let failed = false;
  vi.mocked(api.get).mockImplementation((async (path: string) => {
    if (path === '/missions/mission-b' && !failed) { failed = true; throw { code: 'ARTIFACT_UNAVAILABLE', message: 'Saved draft connection interrupted' }; }
    return defaultGet(path);
  }) as typeof api.get);
  mount('/missions/mission-b/edit');
  await waitFor(() => expect(screen.getByTestId('error-panel')).toBeVisible());
  expect(screen.queryByRole('textbox', { name: 'Mission name' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry request' }));
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mission name' })).toHaveValue('Mission B'));
  expect(api.post).not.toHaveBeenCalled();
});
