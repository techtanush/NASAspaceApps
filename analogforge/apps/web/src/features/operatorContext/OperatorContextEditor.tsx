import { useEffect, useRef, useState } from 'react';
import { useWorkspace, useWorkspaceSession } from '../../app/WorkspaceContext';
import { commandKey } from '../../api/idempotency';
import { CONTEXT_LIMITS, documentMediaType, operatorDocumentContentUrl, saveOperatorContext, uploadOperatorDocument, type ContextKind, type ContextInput, type OperatorContext, type OperatorDocument } from '../../api/operatorContext';
import { Button, ErrorPanel, FormField } from '../../components/ui';
import { OperatorFeatures, type CustomFeature } from './OperatorFeatures';

export interface OperatorContextDraft { documents: { document: OperatorDocument; reviewed_excerpt: string }[]; features: CustomFeature[]; saved: OperatorContext | null }
export const emptyContextDraft = (): OperatorContextDraft => ({ documents: [], features: [], saved: null });
export const hasContextDraft = (draft: OperatorContextDraft | undefined) => !!draft && (draft.documents.length > 0 || draft.features.length > 0);

export function OperatorContextEditor({ kind, roverRevisionId = null, value, onChange, onBusyChange, onSaveContext, disabled = false }: {
  kind: ContextKind; roverRevisionId?: string | null; value: OperatorContextDraft; onChange: (value: OperatorContextDraft) => void; onBusyChange?: (busy: boolean) => void; onSaveContext?: (context: OperatorContext, signal: AbortSignal) => Promise<void>; disabled?: boolean;
}) {
  const workspace = useWorkspace(); const session = useWorkspaceSession();
  const [reviewed, setReviewed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null); const [status, setStatus] = useState('');
  const active = useRef(true); const request = useRef<AbortController | null>(null); const saveCommand = useRef<{ input: string; key: string } | null>(null); const pendingUpload = useRef<{ file: File; key: string } | null>(null);
  const current = useRef(value); current.current = value;
  useEffect(() => { active.current = true; return () => { active.current = false; request.current?.abort(); }; }, [workspace, kind, roverRevisionId]);
  const locked = disabled || busy || session?.role === 'VIEWER';
  const change = (next: OperatorContextDraft) => { setReviewed(false); setStatus('Context changed. Review and save this version before preparing requirements.'); setError(null); onChange({ ...next, saved: null }); };
  const begin = (message: string) => { const controller = new AbortController(); request.current = controller; setBusy(true); onBusyChange?.(true); setError(null); setStatus(message); return controller.signal; };
  const finish = (signal: AbortSignal) => { if (active.current && request.current?.signal === signal) { setBusy(false); onBusyChange?.(false); } };
  const upload = async (file: File, key: string) => {
    pendingUpload.current = null;
    try { documentMediaType(file); } catch (cause) { setError(cause); return; }
    pendingUpload.current = { file, key }; const signal = begin('Uploading and extracting the selected document');
    try {
      const document = await uploadOperatorDocument(file, workspace, { key, signal });
      if (!active.current || signal.aborted) return;
      if (current.current.documents.some(item => item.document.id === document.id)) throw new Error('This exact stored document is already attached.');
      change({ ...current.current, documents: [...current.current.documents, { document, reviewed_excerpt: '' }] });
      pendingUpload.current = null; setStatus(`Stored ${document.filename}. Review its extracted text and choose any excerpt to include.`);
    } catch (cause) { if (active.current && !signal.aborted) { setError(cause); setStatus('The document was not attached. Existing context is retained.'); } } finally { finish(signal); }
  };
  const save = async () => {
    pendingUpload.current = null;
    const input: ContextInput = { schema_version: 'operator-context.v1', kind, rover_revision_id: kind === 'ROVER' ? roverRevisionId : null, documents: value.documents.map(item => ({ document_id: item.document.id, reviewed_excerpt: item.reviewed_excerpt })), features: kind === 'ROVER' ? value.features : [], reviewed: true };
    const serialized = JSON.stringify(input);
    if (!saveCommand.current || saveCommand.current.input !== serialized) saveCommand.current = { input: serialized, key: commandKey() };
    const signal = begin('Saving the reviewed context version');
    try {
      const saved = await saveOperatorContext(input, workspace, { key: saveCommand.current.key, signal });
      if (!active.current || signal.aborted) return;
      if (saved.kind !== kind || saved.rover_revision_id !== input.rover_revision_id) throw new Error('The saved context belongs to another profile. Reload before continuing.');
      if (JSON.stringify(saved.documents.map(source => ({ document_id: source.document_id, reviewed_excerpt: source.reviewed_excerpt }))) !== JSON.stringify(input.documents) || JSON.stringify(saved.features) !== JSON.stringify(input.features) || saved.documents.some(source => { const original = current.current.documents.find(item => item.document.id === source.document_id)?.document; return !original || original.original_sha256 !== source.original_sha256 || original.filename !== source.filename || original.media_type !== source.media_type; })) throw new Error('The saved context does not match the sources and declarations you reviewed. Reload before continuing.');
      await onSaveContext?.(saved, signal);
      if (!active.current || signal.aborted) return;
      onChange({ ...current.current, saved }); setStatus('Reviewed context version saved. It will be checked and pinned during preparation.');
    } catch (cause) { if (active.current && !signal.aborted) { setError(cause); setStatus('Context was not confirmed saved. Your entered values are retained.'); } } finally { finish(signal); }
  };
  const invalidFeature = new Set(value.features.map(feature => feature.name.trim().toLowerCase())).size !== value.features.length || value.features.some(feature => !feature.name.trim() || Array.from(feature.name).length > 100 || (!feature.unknown && (!feature.value?.trim() || Array.from(feature.value).length > 500)) || (feature.unit !== null && Array.from(feature.unit).length > 40));
  const invalidExcerpt = value.documents.some(item => item.reviewed_excerpt !== '' && !item.document.extracted_text.includes(item.reviewed_excerpt));
  return <section className="operator-context form-stack" aria-label={kind === 'MISSION' ? 'Mission background documents' : 'Rover supporting documents and features'} data-testid="operator-context-editor">
    <h2>{kind === 'MISSION' ? 'Mission background documents' : 'Supporting documents and custom features'}</h2>
    <p className="helper">Optional, untrusted operator context. Uploaded documents and declarations are background for requirement proposals, not verified measurements or scientific evidence. Review every proposed requirement.</p>
    <FormField label="Upload a supporting document" hint="PDF, DOCX, TXT, MD or JSON · up to 2 MiB each. Text extraction only; scanned pages have no OCR."><input type="file" accept=".pdf,.docx,.txt,.md,.json" disabled={locked || value.documents.length >= CONTEXT_LIMITS.documents || (kind === 'ROVER' && !roverRevisionId)} onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void upload(file, commandKey()); }}/></FormField>
    {kind === 'ROVER' && !roverRevisionId && <p className="helper">Save or select an exact numeric rover revision before attaching supporting context.</p>}
    {value.documents.map((item, index) => <article className="operator-document form-stack" key={item.document.id}>
      <h3>{item.document.filename}</h3><a href={operatorDocumentContentUrl(item.document.id)} target="_blank" rel="noreferrer">Download original {item.document.filename}</a><p className="helper">{new Intl.NumberFormat('en-US').format(item.document.size_bytes)} bytes · {item.document.media_type} · {item.document.extraction_status === 'NO_TEXT' ? 'No text extracted' : item.document.extraction_status === 'TRUNCATED' ? 'Extracted text truncated' : 'Text extracted'}</p>
      <details><summary>Source identity and extracted text</summary><dl className="readout-list"><dt>Original SHA-256</dt><dd className="hash">{item.document.original_sha256}</dd><dt>Extracted text SHA-256</dt><dd className="hash">{item.document.extracted_text_sha256}</dd><dt>Parser</dt><dd>{item.document.parser.name} · {item.document.parser.version}</dd><dt>Pages</dt><dd>{item.document.page_count ?? 'Unknown'}</dd></dl><pre className="operator-source-text" tabIndex={0} role="region" aria-label={`Extracted source text from ${item.document.filename}`}>{item.document.extracted_text || 'No text is available. The original document is retained as private operator context.'}</pre></details>
      <FormField label={`Reviewed excerpt from ${item.document.filename}`} hint="Only this exact excerpt is included in model context. Copy a contiguous passage from the extracted text, or leave it empty to retain the source identity only." error={item.reviewed_excerpt && !item.document.extracted_text.includes(item.reviewed_excerpt) ? 'Use an exact passage from the extracted text.' : undefined}><textarea rows={4} disabled={locked || item.document.extraction_status === 'NO_TEXT'} maxLength={CONTEXT_LIMITS.characters} value={item.reviewed_excerpt} onChange={event => change({ ...value, documents: value.documents.map((document, position) => position === index ? { ...document, reviewed_excerpt: event.target.value } : document) })}/></FormField>
      <Button variant="ghost" disabled={locked} onClick={() => change({ ...value, documents: value.documents.filter((_, position) => position !== index) })}>Remove {item.document.filename} from this context</Button>
    </article>)}
    {kind === 'ROVER' && <OperatorFeatures features={value.features} onChange={features => change({ ...value, features })} limit={CONTEXT_LIMITS.features} disabled={locked || !roverRevisionId}/>}
    {invalidFeature && <p className="field-error">Give each feature a distinct name (up to 100 characters), a declared value (up to 500) or Unknown, and an optional unit (up to 40).</p>}
    <p className="helper">Combined mission and rover context is limited to 6 distinct documents, 32 features and 12,000 model-visible characters including source metadata. Removal changes the next version; earlier pinned records retain their sources.</p>
    <label className="checkbox-label"><input type="checkbox" disabled={locked} checked={reviewed} onChange={event => setReviewed(event.target.checked)}/>I reviewed these source excerpts and informational declarations.</label>
    <div className="actions"><Button disabled={locked || !reviewed || invalidFeature || invalidExcerpt || (kind === 'ROVER' && !roverRevisionId)} disabledReason="Review the context and correct its fields before saving." onClick={() => { void save(); }}>Save reviewed context</Button>{busy && <Button variant="ghost" onClick={() => { request.current?.abort(); setStatus('Request cancelled. No new context is confirmed.'); setBusy(false); onBusyChange?.(false); }}>Cancel context request</Button>}</div>
    {value.saved && <div className="operator-context-identity"><p>Saved context · {value.saved.model_visible_chars} model-visible characters</p><p className="hash">Context {value.saved.id}<br/>SHA-256 {value.saved.context_sha256}</p></div>}
    <div role="status" aria-live="polite" aria-atomic="true">{status}</div>
    {error !== null && <ErrorPanel error={error} onRetry={pendingUpload.current ? () => { const pending = pendingUpload.current; if (pending) void upload(pending.file, pending.key); } : undefined}/>}
  </section>;
}
