import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { binding, roverContext, roverRevisionId, workspaceId } from '../../test/operatorContextFixtures';
import { BoundOperatorContext } from './BoundOperatorContext';
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../api/client', () => ({ API_BASE: '/api/v1', api: { get, post } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => workspaceId, useWorkspaceSession: () => ({ role: 'OWNER' }) }));
const original = { ...binding, target_kind: 'ROVER_REVISION', target_id: roverRevisionId, mission_revision: null, context_revision: 1, context: roverContext, context_id: roverContext.id, context_sha256: roverContext.context_sha256 };
beforeEach(() => { get.mockReset(); post.mockReset(); });
it('reloads exact saved revision context and keeps edits across a rejected bind and authoritative retry', async () => {
  const edited = { ...roverContext, id: '88888888-8888-4888-8888-888888888888', context_sha256: 'f'.repeat(64), features: [{ ...roverContext.features[0]!, name: 'Auger reach' }] };
  get.mockResolvedValueOnce(original).mockResolvedValueOnce({ ...original, context_revision: 2 });
  let binds = 0;
  post.mockImplementation(async (path: string) => {
    if (path === '/operator-contexts') return edited;
    if (path === `/rover-revisions/${roverRevisionId}/operator-context`) { if (++binds === 1) throw new Error('Revision changed; refresh the stored association'); return { ...original, context_revision: 3, context: edited, context_id: edited.id, context_sha256: edited.context_sha256 }; }
    throw new Error(`Unexpected POST ${path}`);
  });
  const onContextChange = vi.fn(); const onEdited = vi.fn(); const onPendingChange = vi.fn();
  render(<BoundOperatorContext kind="ROVER" id={roverRevisionId} targetId={roverRevisionId} onContextChange={onContextChange} onEdited={onEdited} onPendingChange={onPendingChange}/>);
  expect(await screen.findByLabelText('Feature name')).toHaveValue('Drill reach'); expect(screen.getByLabelText('Declared value')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Feature name'), { target: { value: 'Auger reach' } }); expect(onEdited).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('checkbox', { name: 'I reviewed these source excerpts and informational declarations.' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Revision changed'); expect(screen.getByLabelText('Feature name')).toHaveValue('Auger reach');
  expect(onContextChange).toHaveBeenLastCalledWith(roverContext);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh binding and keep edits' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Refresh binding and keep edits' })).not.toBeInTheDocument());
  expect(screen.getByLabelText('Feature name')).toHaveValue('Auger reach');
  fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' }));
  await waitFor(() => expect(onContextChange).toHaveBeenLastCalledWith(edited));
  expect(onPendingChange).toHaveBeenLastCalledWith(false);
  const creates = post.mock.calls.filter(([path]) => path === '/operator-contexts'); expect(creates[1]?.[2].key).toBe(creates[0]?.[2].key);
  const associations = post.mock.calls.filter(([path]) => path.endsWith('/operator-context')); expect(associations.map(([, input]) => input.expected_context_revision)).toEqual([1, 2]); expect(associations[0]?.[2].key).not.toBe(associations[1]?.[2].key);
});
it('aborts a pending read when the bound target unmounts and never applies its late context to another revision', async () => {
  let resolve!: (value: typeof original) => void; let signal: AbortSignal | undefined;
  get.mockImplementation((_path: string, options: { signal?: AbortSignal }) => { signal = options.signal; return new Promise(done => { resolve = done; }); });
  const changed = vi.fn(); const mounted = render(<BoundOperatorContext kind="ROVER" id={roverRevisionId} targetId={roverRevisionId} onContextChange={changed}/>);
  mounted.unmount(); expect(signal?.aborted).toBe(true); resolve(original); await Promise.resolve(); expect(changed).not.toHaveBeenCalled();
});
