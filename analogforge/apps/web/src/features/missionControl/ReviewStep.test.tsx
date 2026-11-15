import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { components } from '../../generated/schema';
import contractFixture from '../../../../../tests/fixtures/kit/blueprint-mission-contract.json';
import { ReviewStep } from './ReviewStep';

type S = components['schemas'];
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../api/client', () => ({ api: { get, post } }));
vi.mock('../../api/hooks/useApi', () => ({ useApi: () => ({ data: { scenario_config_ids: ['practice'], default_scenario_config_id: 'practice', live_ai_configured: false } }) }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace' }));
vi.mock('./coverage', () => ({ useCoverage: () => ({ state: 'UNKNOWN', message: 'Coverage not yet known.' }) }));
vi.mock('./state', () => ({ useMissionControl: () => ({ plan: { confirmed: true, lat: 0, lng: 0, body: 'MARS', name: 'Mission', objective: 'Traverse', sizeKm: 40, noRover: true, roverRevisionId: null }, box: { ok: true, bbox: [0, 0, 1, 1] } }) }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <p>{children}</p>, Panel: ({ children, footer }: { children: ReactNode; footer: ReactNode }) => <main>{children}{footer}</main> }));

const header: S['MissionHeader'] = { id: 'mission', workspace_id: 'workspace', revision: 1, name: 'Mission', current_draft_id: 'draft', current_contract_id: null, accepted_contract_id: null };
const proposed = { ...contractFixture, id: 'proposed', accepted_at: null } as S['MissionTestContract'];
const succeeded = (id: string): S['JobStatus'] => ({ id, state: 'SUCCEEDED', progress_step: '', run_id: null, preparation_id: 'preparation', proposed_revision_id: proposed.id, error: null });

function configure(poll: (path: string) => Promise<S['JobStatus']>) {
  const operations: string[] = [];
  let preparationCount = 0;
  get.mockImplementation(async (path: string) => {
    operations.push(`GET ${path}`);
    if (path === '/configuration/scenarios/practice') return { id: 'practice', name: 'Practice', body: 'MARS', allowed_modes: ['synthetic'], default_dataset_lock_id: 'lock' };
    if (path.startsWith('/jobs/')) return poll(path);
    if (path === '/missions/mission') return { ...header, revision: 7 };
    if (path === '/mission-revisions/proposed') return proposed;
    throw new Error(`Unexpected GET ${path}`);
  });
  post.mockImplementation(async (path: string) => {
    operations.push(`POST ${path}`);
    if (path === '/missions') return header;
    if (path === '/missions/mission/fingerprint') return { preparation_id: `preparation-${++preparationCount}`, job_id: `job-${preparationCount}`, mission_id: header.id, revision: header.revision + preparationCount };
    throw new Error(`Unexpected POST ${path}`);
  });
  return operations;
}

async function prepare() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter><ReviewStep/></MemoryRouter></QueryClientProvider>);
  const button = screen.getByRole('button', { name: 'Prepare requirements' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
}

beforeEach(() => { get.mockReset(); post.mockReset(); });

it.each(['FAILED', 'BLOCKED', 'CANCELLED'] as const)('starts a fresh preparation after confirmed %s using the authoritative mission revision', async state => {
  const operations = configure(async path => path === '/jobs/job-1' ? { ...succeeded('job-1'), state, proposed_revision_id: null } : succeeded('job-2'));
  await prepare();
  fireEvent.click(await screen.findByRole('button', { name: 'Retry request' }));
  expect(await screen.findByRole('button', { name: 'Accept and start' })).toBeEnabled();
  const preparations = post.mock.calls.filter(([path]) => path === '/missions/mission/fingerprint');
  expect(preparations).toHaveLength(2);
  expect(preparations[0]![1]).toMatchObject({ expected_revision: 1, mode: 'synthetic', rover_revision_id: null });
  expect(preparations[1]![1]).toMatchObject({ expected_revision: 7, mode: 'synthetic', rover_revision_id: null });
  expect(preparations[1]![2].key).not.toBe(preparations[0]![2].key);
  expect(operations.slice(1, 7)).toEqual(['POST /missions', 'POST /missions/mission/fingerprint', 'GET /jobs/job-1', 'GET /missions/mission', 'POST /missions/mission/fingerprint', 'GET /jobs/job-2']);
  expect(post.mock.calls.filter(([path]) => path === '/missions')).toHaveLength(1);
  const requirements = within(screen.getByTestId('proposed-requirements'));
  expect(requirements.getAllByTestId('proposed-requirement')).toHaveLength(proposed.requirements.length);
  for (const requirement of proposed.requirements) expect(requirements.getByText(requirement.label)).toBeVisible();
});

it('retries an uncertain polling failure with the accepted job and never creates a duplicate preparation', async () => {
  let polls = 0;
  const operations = configure(async path => {
    expect(path).toBe('/jobs/job-1');
    if (++polls === 1) throw new TypeError('Polling connection interrupted');
    return succeeded('job-1');
  });
  await prepare();
  expect(await screen.findByRole('alert')).toHaveTextContent('Polling connection interrupted');
  fireEvent.click(screen.getByRole('button', { name: 'Retry request' }));
  expect(await screen.findByRole('button', { name: 'Accept and start' })).toBeEnabled();
  expect(post.mock.calls.filter(([path]) => path === '/missions/mission/fingerprint')).toHaveLength(1);
  expect(post.mock.calls.filter(([path]) => path === '/missions')).toHaveLength(1);
  expect(operations.filter(operation => operation.startsWith('GET /jobs/'))).toEqual(['GET /jobs/job-1', 'GET /jobs/job-1']);
  expect(operations.indexOf('GET /missions/mission')).toBeGreaterThan(operations.lastIndexOf('GET /jobs/job-1'));
});
