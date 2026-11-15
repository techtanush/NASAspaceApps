import type { ReactNode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import contractFixture from '../../../../../tests/fixtures/kit/blueprint-mission-contract.json';
import { binding, context, document, draftId, roverContext, roverRevisionId, snapshot, workspaceId } from '../../test/operatorContextFixtures';
import { ReviewStep } from './ReviewStep';
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../api/client', () => ({ API_BASE: '/api/v1', api: { get, post } }));
vi.mock('../../api/hooks/useApi', () => ({ useApi: () => ({ data: { scenario_config_ids: ['practice'], default_scenario_config_id: 'practice' } }) }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => workspaceId }));
vi.mock('./coverage', () => ({ useCoverage: () => ({ state: 'UNKNOWN', message: 'Coverage is not confirmed.' }) }));
vi.mock('./state', () => ({ useMissionControl: () => ({ plan: { confirmed: true, lat: 0, lng: 0, body: 'MARS', name: 'Mission', objective: 'Traverse', sizeKm: 40, noRover: false, roverRevisionId, roverName: 'Rover', roverContext, roverContextChecked: true, missionContextDraft: { documents: [{ document, reviewed_excerpt: context.documents[0]!.reviewed_excerpt }], features: [], saved: context } }, box: { ok: true, bbox: [0, 0, 1, 1] } }) }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <p>{children}</p>, Panel: ({ children, footer }: { children: ReactNode; footer: ReactNode }) => <main>{children}{footer}</main> }));
const proposed = { ...contractFixture, id: '66666666-6666-4666-8666-666666666666', accepted_at: null };
const runId = '77777777-7777-4777-8777-777777777777';
const header = { id: 'mission', workspace_id: workspaceId, revision: 1, name: 'Mission', current_draft_id: draftId, current_contract_id: null, accepted_contract_id: null };
function configure({ budgetFailure = false, pinnedDrift = false, admissionDrift = false } = {}) {
  const operations: string[] = []; let roverReads = 0;
  get.mockImplementation(async (path: string) => {
    operations.push(`GET ${path}`);
    if (path === '/configuration/scenarios/practice') return { id: 'practice', name: 'Practice', body: 'MARS', allowed_modes: ['synthetic'], default_dataset_lock_id: 'lock' };
    if (path === '/missions/mission') return { ...header, revision: 3 };
    if (path === '/missions/mission/operator-context') return binding;
    if (path === `/rover-revisions/${roverRevisionId}/operator-context`) { roverReads++; const changed = admissionDrift && roverReads > 1; return { ...binding, target_kind: 'ROVER_REVISION', target_id: roverRevisionId, mission_revision: null, context: changed ? null : roverContext, context_id: changed ? null : roverContext.id, context_sha256: changed ? null : roverContext.context_sha256 }; }
    if (path.startsWith('/operator-context/preview?')) { if (budgetFailure) throw new Error('Combined context exceeds the 12,000 character budget'); return snapshot; }
    if (path === '/jobs/job-1') return { id: 'job-1', state: 'SUCCEEDED', progress_step: '', proposed_revision_id: proposed.id };
    if (path === `/mission-revisions/${proposed.id}`) return proposed;
    if (path === `/mission-revisions/${proposed.id}/operator-context`) return pinnedDrift ? { ...snapshot, rover_context: null, rover_context_id: null } : snapshot;
    if (path === `/runs/${runId}/operator-context`) return snapshot;
    throw new Error(`Unexpected GET ${path}`);
  });
  post.mockImplementation(async (path: string) => {
    operations.push(`POST ${path}`);
    if (path === '/missions') return header;
    if (path === '/missions/mission/operator-context') return { ...binding, context_revision: 1, mission_revision: 2, context, context_id: context.id, context_sha256: context.context_sha256 };
    if (path === '/missions/mission/fingerprint') return { job_id: 'job-1', preparation_id: 'preparation' };
    if (path === '/missions/mission/accept') return { ...proposed, accepted_at: document.created_at };
    if (path === '/operator-context/runs') return { run_id: runId, revision: 1 };
    throw new Error(`Unexpected POST ${path}`);
  });
  return operations;
}
async function prepare() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/review']}><Routes><Route path="/review" element={<ReviewStep/>}/><Route path="/runs/:runId/tour" element={<p>Admitted tour</p>}/></Routes></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Prepare requirements' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Prepare requirements' }));
}
beforeEach(() => { get.mockReset(); post.mockReset(); });
it('binds the reviewed version before fingerprint, uses the acknowledged mission revision and verifies admitted snapshot identity', async () => {
  const operations = configure(); await prepare();
  const accept = await screen.findByRole('button', { name: 'Accept and start' });
  expect(post).toHaveBeenCalledWith('/missions/mission/fingerprint', { expected_revision: 2, mode: 'synthetic', rover_revision_id: roverRevisionId }, expect.anything());
  expect(screen.getByTestId('pinned-operator-context')).toHaveTextContent(snapshot.snapshot_sha256!);
  fireEvent.click(accept); await screen.findByText('Admitted tour');
  expect(post).toHaveBeenCalledWith('/operator-context/runs', { run_request: expect.objectContaining({ mission_revision_id: proposed.id, rover_revision_id: roverRevisionId }), expected_rover_context_id: roverContext.id }, expect.anything());
  expect(operations.indexOf('POST /missions/mission/operator-context')).toBeLessThan(operations.indexOf('POST /missions/mission/fingerprint'));
  expect(operations.at(-1)).toBe(`GET /runs/${runId}/operator-context`);
});
it('blocks preparation at the actual combined budget error, preserving the reviewed source identity', async () => {
  configure({ budgetFailure: true }); await prepare();
  expect(await screen.findByRole('alert')).toHaveTextContent('12,000'); expect(screen.getByText(`SHA-256 ${context.context_sha256}`, { exact: false })).toBeVisible();
  expect(post.mock.calls.some(([path]) => path === '/missions/mission/fingerprint')).toBe(false);
});
it('refuses an unexpected prepared context instead of offering acceptance', async () => {
  configure({ pinnedDrift: true }); await prepare(); await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: 'Accept and start' })).not.toBeInTheDocument(); expect(post.mock.calls.some(([path]) => String(path).endsWith('/accept'))).toBe(false);
});
it('rejects a changed rover sidecar after proposal before accepting or admitting any run', async () => {
  configure({ admissionDrift: true }); await prepare(); fireEvent.click(await screen.findByRole('button', { name: 'Accept and start' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('changed after preparation'); expect(post.mock.calls.some(([path]) => String(path).endsWith('/accept') || path === '/operator-context/runs')).toBe(false);
});
