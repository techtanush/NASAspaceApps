import { beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import seed from '../../mock/fixtures/seed.json';
import { api } from '../../api/client';
import { MissionEditor } from './MissionEditor';

vi.mock('../../api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../rovers/RoverEditor', () => ({ RoverEditor: () => <div>Rover editor boundary</div> }));
vi.mock('../../maps/PlanetaryPanel', () => ({ PlanetaryPanel: () => <div>Region preview boundary</div> }));

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
