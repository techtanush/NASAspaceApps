import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../../api/errors';
import { commandKey } from '../../api/idempotency';
import { bindOperatorContext, getContextBinding, getOperatorDocument, type ContextBinding, type ContextKind, type OperatorContext } from '../../api/operatorContext';
import { useWorkspace } from '../../app/WorkspaceContext';
import { Button, ErrorPanel, Skeleton } from '../../components/ui';
import { emptyContextDraft, OperatorContextEditor, type OperatorContextDraft } from './OperatorContextEditor';

export function BoundOperatorContext({ kind, id, targetId, missionRevision, disabled, onContextChange, onPendingChange, onEdited, onBound }: {
  kind: ContextKind; id: string; targetId: string; missionRevision?: number; disabled?: boolean;
  onContextChange?: (context: OperatorContext | null) => void; onPendingChange?: (pending: boolean) => void; onEdited?: () => void; onBound?: (binding: ContextBinding) => void;
}) {
  const workspace = useWorkspace(); const [draft, setDraft] = useState<OperatorContextDraft>(emptyContextDraft); const [binding, setBinding] = useState<ContextBinding | null>(null);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [dirty, setDirty] = useState(false); const [error, setError] = useState<unknown>(null); const [attempt, setAttempt] = useState(0);
  const [saveConflict, setSaveConflict] = useState(false);
  const [refreshError, setRefreshError] = useState<unknown>(null); const refresh = useRef<AbortController | null>(null);
  const callbacks = useRef({ onContextChange, onPendingChange, onEdited, onBound }); callbacks.current = { onContextChange, onPendingChange, onEdited, onBound };
  const command = useRef<{ input: string; key: string } | null>(null);
  useEffect(() => {
    if (import.meta.env.VITE_API_MOCK === '1') { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true); setError(null);
    void (async () => {
      try {
        const current = await getContextBinding(kind, id, targetId, workspace, { signal: controller.signal });
        const documents = await Promise.all((current.context?.documents ?? []).map(async source => {
          const document = await getOperatorDocument(source.document_id, workspace, { signal: controller.signal });
          if (document.original_sha256 !== source.original_sha256 || document.filename !== source.filename || document.media_type !== source.media_type || !document.extracted_text.includes(source.reviewed_excerpt)) throw new Error('A stored source no longer matches the reviewed context. Reload before editing.');
          return { document, reviewed_excerpt: source.reviewed_excerpt };
        }));
        if (controller.signal.aborted) return;
        setBinding(current); setDraft({ documents, features: current.context?.features ?? [], saved: current.context }); setDirty(false); callbacks.current.onContextChange?.(current.context); callbacks.current.onBound?.(current);
      } catch (cause) { if (!controller.signal.aborted) setError(cause); } finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => { controller.abort(); refresh.current?.abort(); };
  }, [kind, id, targetId, workspace, attempt]);
  useEffect(() => { callbacks.current.onPendingChange?.(loading || busy || dirty); }, [loading, busy, dirty]);
  useEffect(() => () => callbacks.current.onPendingChange?.(false), []);
  if (import.meta.env.VITE_API_MOCK === '1') return <p className="helper">Document uploads and custom context require the real server. No documents are stored in mock preview.</p>;
  if (loading) return <Skeleton label="Retrieving the exact revision’s operator context"/>;
  if (error !== null) return <section className="operator-context"><h2>Operator context</h2>{error instanceof ApiError && error.status === 404 ? <p className="helper">Optional document context is unavailable on this server.</p> : <ErrorPanel error={error}/>}<Button onClick={() => setAttempt(value => value + 1)}>Reload stored context</Button></section>;
  if (!binding) return null;
  return <>{saveConflict && <div className="operator-context"><p>The association was not confirmed. Refresh its authoritative revision while keeping your entered sources and declarations, then retry the save.</p><Button disabled={busy} onClick={() => {
    refresh.current?.abort(); const controller = new AbortController(); refresh.current = controller; setBusy(true); setRefreshError(null);
    void getContextBinding(kind, id, targetId, workspace, { signal: controller.signal }).then(current => { if (controller.signal.aborted) return; setBinding(current); callbacks.current.onBound?.(current); setSaveConflict(false); }).catch(cause => { if (!controller.signal.aborted) setRefreshError(cause); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
  }}>Refresh binding and keep edits</Button>{refreshError !== null && <ErrorPanel error={refreshError}/>}</div>}<OperatorContextEditor kind={kind} roverRevisionId={kind === 'ROVER' ? targetId : null} value={draft} disabled={disabled || busy} onBusyChange={setBusy}
    onChange={next => { setDraft(next); setDirty(next.saved === null); if (next.saved === null) callbacks.current.onEdited?.(); }}
    onSaveContext={async (context, signal) => {
      const input = `${binding.context_revision}:${context.id}:${missionRevision ?? ''}`;
      if (!command.current || command.current.input !== input) command.current = { input, key: commandKey() };
      try {
        const updated = await bindOperatorContext(kind, id, targetId, workspace, binding, context, { key: command.current.key, signal }, kind === 'MISSION' ? binding.mission_revision ?? missionRevision : undefined);
        if (signal.aborted) return;
        setBinding(updated); setDirty(false); setSaveConflict(false); callbacks.current.onContextChange?.(updated.context); callbacks.current.onBound?.(updated);
      } catch (cause) { if (!signal.aborted) setSaveConflict(true); throw cause; }
    }}/></>;
}
