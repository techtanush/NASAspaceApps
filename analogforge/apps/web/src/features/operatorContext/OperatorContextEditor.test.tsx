import { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { context, document, workspaceId } from '../../test/operatorContextFixtures';
import { saveOperatorContext, uploadOperatorDocument } from '../../api/operatorContext';
import { emptyContextDraft, OperatorContextEditor, type OperatorContextDraft } from './OperatorContextEditor';
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => workspaceId, useWorkspaceSession: () => ({ role: 'OWNER' }) }));
vi.mock('../../api/operatorContext', async original => ({ ...await original<typeof import('../../api/operatorContext')>(), saveOperatorContext: vi.fn(), uploadOperatorDocument: vi.fn() }));
function Editor({ onSaveContext }: { onSaveContext?: Parameters<typeof OperatorContextEditor>[0]['onSaveContext'] }) {
  const [draft, setDraft] = useState<OperatorContextDraft>(emptyContextDraft);
  return <><OperatorContextEditor kind="MISSION" value={draft} onChange={setDraft} onSaveContext={onSaveContext}/><output data-testid="saved-context">{draft.saved?.id ?? 'Unsaved'}</output></>;
}
beforeEach(() => { vi.mocked(uploadOperatorDocument).mockReset(); vi.mocked(saveOperatorContext).mockReset(); });
it('stores the real upload response, displays escaped source text and saves only an explicitly reviewed exact excerpt', async () => {
  vi.mocked(uploadOperatorDocument).mockResolvedValue(document); vi.mocked(saveOperatorContext).mockResolvedValue(context);
  const { container } = render(<Editor/>);
  fireEvent.change(screen.getByLabelText('Upload a supporting document'), { target: { files: [new File(['source'], document.filename)] } });
  await screen.findByRole('heading', { name: document.filename });
  fireEvent.click(screen.getByText('Source identity and extracted text'));
  expect(container.querySelector('script')).toBeNull(); expect(screen.getByText(document.extracted_text)).toBeVisible();
  const save = screen.getByRole('button', { name: 'Save reviewed context' }); expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText(`Reviewed excerpt from ${document.filename}`), { target: { value: 'invented numeric limit' } });
  fireEvent.click(screen.getByRole('checkbox')); expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText(`Reviewed excerpt from ${document.filename}`), { target: { value: context.documents[0]!.reviewed_excerpt } });
  fireEvent.click(screen.getByRole('checkbox')); await waitFor(() => expect(screen.getByRole('button', { name: 'Save reviewed context' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' }));
  await waitFor(() => expect(screen.getByTestId('saved-context')).toHaveTextContent(context.id));
  expect(saveOperatorContext).toHaveBeenCalledWith(expect.objectContaining({ documents: [{ document_id: document.id, reviewed_excerpt: context.documents[0]!.reviewed_excerpt }], reviewed: true, features: [] }), workspaceId, expect.objectContaining({ key: expect.any(String) }));
});
it('retains entered context and the same logical save key after uncertain failure, without claiming a save', async () => {
  vi.mocked(saveOperatorContext).mockRejectedValueOnce(new TypeError('Connection interrupted')).mockResolvedValueOnce({ ...context, documents: [] });
  render(<Editor/>); fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' }));
  await screen.findByRole('alert'); expect(screen.getByTestId('saved-context')).toHaveTextContent('Unsaved');
  fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' })); await waitFor(() => expect(screen.getByTestId('saved-context')).toHaveTextContent(context.id));
  expect(vi.mocked(saveOperatorContext).mock.calls[1]?.[2].key).toBe(vi.mocked(saveOperatorContext).mock.calls[0]?.[2].key);
});
it('does not confirm a saved association when the authoritative revision bind is rejected', async () => {
  vi.mocked(saveOperatorContext).mockResolvedValue({ ...context, documents: [] }); const bind = vi.fn().mockRejectedValue(new Error('Revision changed; reload stored binding'));
  render(<Editor onSaveContext={bind}/>); fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save reviewed context' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Revision changed'); expect(screen.getByTestId('saved-context')).toHaveTextContent('Unsaved');
});
it('ignores a late upload after cancellation instead of fabricating a newly attached document', async () => {
  let resolve!: (value: typeof document) => void; vi.mocked(uploadOperatorDocument).mockImplementation(() => new Promise(done => { resolve = done; }));
  render(<Editor/>); fireEvent.change(screen.getByLabelText('Upload a supporting document'), { target: { files: [new File(['source'], document.filename)] } });
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel context request' })); resolve(document);
  await waitFor(() => expect(screen.queryByRole('heading', { name: document.filename })).not.toBeInTheDocument()); expect(screen.getByTestId('saved-context')).toHaveTextContent('Unsaved');
});
