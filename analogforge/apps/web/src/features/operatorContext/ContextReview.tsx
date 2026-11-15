import { operatorDocumentContentUrl } from '../../api/operatorContext';
import type { ContextSnapshot, ModelContext, OperatorContext } from '../../api/operatorContext';

function ContextSources({ context }: { context: ModelContext | OperatorContext }) {
  return <div className="operator-context-review">
    <p className="hash">Context {'context_id' in context ? context.context_id : context.id}<br/>SHA-256 {context.context_sha256}</p>
    {context.documents.map(document => <details key={document.document_id}><summary>{document.filename} · {document.extraction_status === 'NO_TEXT' ? 'No extracted text' : document.text_truncated ? 'Truncated source text' : 'Reviewed excerpt'}</summary><a href={operatorDocumentContentUrl(document.document_id)} target="_blank" rel="noreferrer">Download original {document.filename}</a><p className="hash">Original SHA-256 {document.original_sha256}</p><p className="helper">{document.media_type} · untrusted operator upload</p><pre className="operator-source-text" tabIndex={0} role="region" aria-label={`Reviewed excerpt from ${document.filename}`}>{document.reviewed_excerpt || 'No source text included; source identity only.'}</pre></details>)}
    {context.features.length > 0 && <dl className="operator-feature-summary">{context.features.map((feature, index) => <div key={index}><dt>{feature.name}</dt><dd>{feature.unknown ? 'Unknown' : feature.value}{feature.unit ? ` ${feature.unit}` : ''}<span className="helper">Informational declaration</span></dd></div>)}</dl>}
  </div>;
}
export function SavedContextReview({ context, label }: { context: OperatorContext; label: string }) {
  return <section className="operator-context" aria-label={label}><h3>{label}</h3><ContextSources context={context}/><p className="helper">Saved for review; preparation must pin this exact version.</p></section>;
}
export function PinnedContextReview({ snapshot }: { snapshot: ContextSnapshot }) {
  return <section className="operator-context" aria-label="Pinned operator context" data-testid="pinned-operator-context">
    <h2>Pinned operator context</h2><p className="helper">Untrusted operator background, with no scientific authority. These declarations do not set numeric rover constraints or establish evidence.</p>
    {!snapshot.snapshot_sha256 ? <p>{snapshot.lineage_pinned ? 'The pinned context contains no supporting documents or custom declarations.' : 'No operator context lineage is recorded for this historical record.'}</p> : <><p className="hash">Snapshot SHA-256 {snapshot.snapshot_sha256}</p><p>{snapshot.model_visible_chars} of 12,000 model-visible characters, including metadata</p></>}
    {snapshot.mission_context && <div><h3>Mission background</h3><ContextSources context={snapshot.mission_context}/></div>}
    {snapshot.rover_context && <div><h3>Rover supporting context</h3><p className="hash">Exact rover revision {snapshot.rover_context.rover_revision_id}</p><ContextSources context={snapshot.rover_context}/></div>}
  </section>;
}
