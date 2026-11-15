import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { components } from '../../generated/schema';
import { EvidenceBriefDownload, evidenceBriefPath } from './EvidenceBriefDownload';

vi.mock('../../api/client', () => ({ api: { raw: vi.fn() } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace' }));
const run = { run_id: 'run-current', workspace_id: 'workspace', candidate_ids: ['site-one', 'site-two'] } as components['schemas']['RunSnapshot'];
const createURL = vi.fn(() => 'blob:verified-pdf'); const click = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createURL });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { click(this.href, this.download); });
});
it('downloads the exact selected candidate PDF through authenticated API access', async () => {
  vi.mocked(api.raw).mockResolvedValue(new Response('%PDF-1.7\nreal endpoint bytes', { headers: { 'Content-Type': 'application/pdf' } }));
  render(<EvidenceBriefDownload run={run} candidateId="site-two"/>);
  fireEvent.click(screen.getByRole('button', { name: 'Download current evidence PDF' }));
  await waitFor(() => expect(click).toHaveBeenCalledWith('blob:verified-pdf', 'analogforge-evidence-brief-run-curr-site-two.pdf'));
  expect(api.raw).toHaveBeenCalledWith('/runs/run-current/candidates/site-two/evidence-brief.pdf', expect.objectContaining({ signal: expect.any(AbortSignal), headers: { Accept: 'application/pdf' } }));
  expect(() => evidenceBriefPath(run, 'foreign-site')).toThrow('does not belong');
});
it('does not download JSON or borrow a failed report from another location', async () => {
  vi.mocked(api.raw).mockResolvedValue(new Response('{"error":"unavailable"}', { headers: { 'Content-Type': 'application/json' } }));
  render(<EvidenceBriefDownload run={run} candidateId="site-one"/>);
  fireEvent.click(screen.getByRole('button', { name: 'Download current evidence PDF' }));
  await screen.findByTestId('error-panel'); expect(createURL).not.toHaveBeenCalled(); expect(click).not.toHaveBeenCalled();
});
it('ignores an old PDF response after the operator selects a different location', async () => {
  let finish!: (response: Response) => void;
  vi.mocked(api.raw).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { rerender } = render(<EvidenceBriefDownload run={run} candidateId="site-one"/>);
  fireEvent.click(screen.getByRole('button', { name: 'Download current evidence PDF' }));
  rerender(<EvidenceBriefDownload run={run} candidateId="site-two"/>);
  await act(async () => { finish(new Response('%PDF-1.7', { headers: { 'Content-Type': 'application/pdf' } })); });
  expect(createURL).not.toHaveBeenCalled(); expect(click).not.toHaveBeenCalled();
});
