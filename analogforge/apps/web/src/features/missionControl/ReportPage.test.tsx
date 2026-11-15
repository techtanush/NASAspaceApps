import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import seed from '../../mock/fixtures/seed.json';
import { api } from '../../api/client';
import { ReportPage } from './ReportPage';
vi.mock('../../api/client', () => ({ api: { raw: vi.fn() } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => seed.workspaceId }));
vi.mock('./useRunAssurance', () => ({ useRunAssurance: () => ({ publication: 'UNPUBLISHED' }) }));
vi.mock('./useRunData', () => ({ useRunData: () => ({ snapshot: { run_id: seed.runId, workspace_id: seed.workspaceId, mode: 'synthetic', state: 'FAILED', revision: 12, candidate_ids: seed.candidates.map(candidate => candidate.id) }, contract: { ...seed.missionPresets.MARS, name: 'Accepted mission' }, candidates: seed.candidates, qualifications: [], loading: false }) }));
vi.mock('./BenchmarkEvidence', () => ({ BenchmarkEvidence: () => <p>Candidate-scoped benchmark boundary</p> }));
vi.mock('./EnvironmentContext', () => ({ EnvironmentContext: () => <p>Stored environment boundary</p> }));
vi.mock('./RunTerminalNotice', () => ({ RunTerminalNotice: () => <p role="status">Recorded terminal reason</p> }));
function mount(site: string) { render(<MemoryRouter initialEntries={[`/runs/${seed.runId}/report?site=${site}`]}><Routes><Route path="/runs/:runId/report" element={<ReportPage/>}/></Routes></MemoryRouter>); }
it('offers a current-evidence PDF for the exact location while retaining terminal truth and publication limits', async () => {
  vi.mocked(api.raw).mockRejectedValue(new Error('PDF unavailable')); mount(seed.candidates[1]!.id);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(seed.candidates[1]!.name);
  expect(screen.getByText('Recorded terminal reason')).toBeVisible();
  expect(screen.getByText(/This brief is not an immutable published passport/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Download current evidence PDF' }));
  await waitFor(() => expect(api.raw).toHaveBeenCalledWith(`/runs/${seed.runId}/candidates/${seed.candidates[1]!.id}/evidence-brief.pdf`, expect.anything()));
  await screen.findByTestId('error-panel');
});
it('does not offer a report or PDF for a candidate outside the current run', () => {
  vi.mocked(api.raw).mockClear(); mount('foreign-candidate');
  expect(screen.getByRole('heading', { name: 'Site unavailable' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Download current evidence PDF' })).toBeNull(); expect(api.raw).not.toHaveBeenCalled();
});
