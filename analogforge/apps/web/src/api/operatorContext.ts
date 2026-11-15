import { API_BASE, api, type RequestOptions } from './client';
import type { components } from '../generated/schema';
import type { CustomFeature } from '../features/operatorContext/OperatorFeatures';

export const CONTEXT_LIMITS = { fileBytes: 2 * 1024 * 1024, documents: 6, features: 32, characters: 12000 } as const;
export type ContextKind = 'MISSION' | 'ROVER';
type Extraction = 'EXTRACTED' | 'TRUNCATED' | 'NO_TEXT';
export interface ContextDocument { document_id: string; filename: string; original_sha256: string; media_type: string; extraction_status: Extraction; text_truncated: boolean; reviewed_excerpt: string }
export interface OperatorDocument { schema_version: 'operator-document.v1'; id: string; workspace_id: string; created_at: string; filename: string; media_type: string; size_bytes: number; original_sha256: string; extracted_text: string; extracted_text_sha256: string; extraction_status: Extraction; text_truncated: boolean; page_count: number | null; parser: { name: string; version: string }; source_kind: 'OPERATOR_UPLOAD'; trust: 'UNTRUSTED_CONTEXT' }
export interface ModelContext { context_id: string; context_sha256: string; kind: ContextKind; rover_revision_id: string | null; documents: ContextDocument[]; features: CustomFeature[]; trust: 'UNTRUSTED_CONTEXT' }
export interface OperatorContext extends Omit<ModelContext, 'context_id'> { schema_version: 'operator-context.v1'; id: string; workspace_id: string; created_at: string; reviewed: true; reviewed_by: string; model_visible_chars: number }
export interface ContextBinding { schema_version: 'operator-context-binding.v1'; target_kind: 'MISSION_DRAFT' | 'ROVER_REVISION'; target_id: string; context_revision: number; context_id: string | null; context_sha256: string | null; context: OperatorContext | null; mission_revision: number | null }
export interface ContextSnapshot { schema_version: 'operator-context-snapshot.v1'; mission_context: ModelContext | null; rover_context: ModelContext | null; trust: 'UNTRUSTED_CONTEXT'; scientific_authority: 'NONE'; qualification_supported: false; snapshot_sha256: string | null; model_visible_chars: number; mission_context_id: string | null; rover_context_id: string | null; lineage_pinned?: boolean }
export interface ContextInput { schema_version: 'operator-context.v1'; kind: ContextKind; rover_revision_id: string | null; documents: { document_id: string; reviewed_excerpt: string }[]; features: CustomFeature[]; reviewed: true }
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA = /^[a-f0-9]{64}$/;
const MIME: Record<string, string> = { pdf: 'application/pdf', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', txt: 'text/plain', md: 'text/markdown', json: 'application/json' };
const string = (value: unknown): value is string => typeof value === 'string';
const count = (value: string) => Array.from(value).length;
const integer = (value: unknown, max = Number.MAX_SAFE_INTEGER): value is number => Number.isSafeInteger(value) && Number(value) >= 0 && Number(value) <= max;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
function invalid(): never { throw new Error('The stored operator context could not be verified. Reload its authoritative record before continuing.'); }
function features(value: unknown): value is CustomFeature[] { return Array.isArray(value) && value.length <= CONTEXT_LIMITS.features && value.every(feature => object(feature) && string(feature.name) && count(feature.name) >= 1 && count(feature.name) <= 100 && (feature.unit === null || (string(feature.unit) && count(feature.unit) >= 1 && count(feature.unit) <= 40)) && typeof feature.unknown === 'boolean' && (feature.unknown ? feature.value === null : string(feature.value) && count(feature.value) >= 1 && count(feature.value) <= 500)); }
function documents(value: unknown): value is ContextDocument[] { return Array.isArray(value) && value.length <= CONTEXT_LIMITS.documents && new Set(value.map(document => document?.document_id)).size === value.length && value.every(document => object(document) && string(document.document_id) && UUID.test(document.document_id) && string(document.filename) && string(document.original_sha256) && SHA.test(document.original_sha256) && string(document.media_type) && Object.values(MIME).includes(document.media_type) && ['EXTRACTED', 'TRUNCATED', 'NO_TEXT'].includes(String(document.extraction_status)) && typeof document.text_truncated === 'boolean' && string(document.reviewed_excerpt) && count(document.reviewed_excerpt) <= CONTEXT_LIMITS.characters); }
function contextFields(value: unknown): value is ModelContext { return object(value) && SHA.test(String(value.context_sha256)) && ['MISSION', 'ROVER'].includes(String(value.kind)) && value.trust === 'UNTRUSTED_CONTEXT' && documents(value.documents) && features(value.features) && (value.kind === 'MISSION' ? value.rover_revision_id === null && value.features.length === 0 : string(value.rover_revision_id) && UUID.test(value.rover_revision_id)); }
export function parseOperatorDocument(value: unknown, workspace: string): OperatorDocument {
  if (!object(value) || value.schema_version !== 'operator-document.v1' || value.workspace_id !== workspace || !UUID.test(String(value.id)) || !string(value.created_at) || !string(value.filename) || !Object.values(MIME).includes(String(value.media_type)) || !integer(value.size_bytes, CONTEXT_LIMITS.fileBytes) || value.size_bytes === 0 || !SHA.test(String(value.original_sha256)) || !SHA.test(String(value.extracted_text_sha256)) || !string(value.extracted_text) || count(value.extracted_text) > 64000 || !['EXTRACTED', 'TRUNCATED', 'NO_TEXT'].includes(String(value.extraction_status)) || typeof value.text_truncated !== 'boolean' || (value.page_count !== null && !integer(value.page_count)) || !object(value.parser) || !string(value.parser.name) || !string(value.parser.version) || value.source_kind !== 'OPERATOR_UPLOAD' || value.trust !== 'UNTRUSTED_CONTEXT' || (value.extraction_status === 'NO_TEXT' && value.extracted_text.trim() !== '')) invalid();
  return value as unknown as OperatorDocument;
}
export function parseOperatorContext(value: unknown, workspace: string): OperatorContext {
  if (!contextFields(value) || !object(value) || value.schema_version !== 'operator-context.v1' || value.workspace_id !== workspace || !UUID.test(String(value.id)) || !string(value.created_at) || !string(value.reviewed_by) || value.reviewed !== true || !integer(value.model_visible_chars, CONTEXT_LIMITS.characters)) invalid();
  return value as unknown as OperatorContext;
}
export function parseContextBinding(value: unknown, workspace: string, kind: ContextBinding['target_kind'], targetId: string): ContextBinding {
  if (!object(value) || value.schema_version !== 'operator-context-binding.v1' || value.target_kind !== kind || value.target_id !== targetId || !integer(value.context_revision) || (kind === 'MISSION_DRAFT' ? !integer(value.mission_revision) : value.mission_revision !== null)) invalid();
  const context = value.context === null ? null : parseOperatorContext(value.context, workspace);
  if (context ? value.context_id !== context.id || value.context_sha256 !== context.context_sha256 || (kind === 'ROVER_REVISION' ? context.kind !== 'ROVER' || context.rover_revision_id !== targetId : context.kind !== 'MISSION') : value.context_id !== null || value.context_sha256 !== null) invalid();
  return value as unknown as ContextBinding;
}
export function parseContextSnapshot(value: unknown, expected?: { missionId?: string | null; roverId?: string | null; roverRevisionId?: string | null }): ContextSnapshot {
  if (!object(value) || value.schema_version !== 'operator-context-snapshot.v1' || value.trust !== 'UNTRUSTED_CONTEXT' || value.scientific_authority !== 'NONE' || value.qualification_supported !== false || !integer(value.model_visible_chars, CONTEXT_LIMITS.characters) || (value.lineage_pinned !== undefined && typeof value.lineage_pinned !== 'boolean')) invalid();
  for (const [field, kind] of [['mission_context', 'MISSION'], ['rover_context', 'ROVER']] as const) {
    const context = value[field];
    if (context !== null && (!contextFields(context) || !UUID.test(String(context.context_id)) || context.kind !== kind)) invalid();
    if (value[kind === 'MISSION' ? 'mission_context_id' : 'rover_context_id'] !== (object(context) ? context.context_id : null)) invalid();
  }
  if (value.mission_context === null && value.rover_context === null ? value.snapshot_sha256 !== null || value.model_visible_chars !== 0 : !SHA.test(String(value.snapshot_sha256))) invalid();
  const result = value as unknown as ContextSnapshot;
  if (expected && ((Object.hasOwn(expected, 'missionId') && result.mission_context_id !== expected.missionId) || (Object.hasOwn(expected, 'roverId') && result.rover_context_id !== expected.roverId) || (result.rover_context && result.rover_context.rover_revision_id !== expected.roverRevisionId && Object.hasOwn(expected, 'roverRevisionId')))) invalid();
  if (new Set([...(result.mission_context?.documents ?? []), ...(result.rover_context?.documents ?? [])].map(document => document.document_id)).size > CONTEXT_LIMITS.documents || (result.rover_context?.features.length ?? 0) > CONTEXT_LIMITS.features) invalid();
  return result;
}
export function documentMediaType(file: File): string { const type = MIME[file.name.split('.').at(-1)?.toLowerCase() ?? '']; if (!type) throw new Error('Choose a PDF, DOCX, TXT, MD or JSON document.'); if (file.size < 1 || file.size > CONTEXT_LIMITS.fileBytes) throw new Error('Choose a nonempty document no larger than 2 MiB.'); return type; }
export function operatorDocumentContentUrl(id: string): string { if (!UUID.test(id)) invalid(); return `${API_BASE}/operator-documents/${id}/content`; }
export async function uploadOperatorDocument(file: File, workspace: string, options: RequestOptions): Promise<OperatorDocument> {
  const response = await api.raw('/operator-documents', { method: 'POST', body: file, signal: options.signal, headers: { 'Content-Type': documentMediaType(file), 'X-Upload-Filename': encodeURIComponent(file.name), 'Idempotency-Key': options.key! } });
  return parseOperatorDocument(await response.json(), workspace);
}
export async function saveOperatorContext(input: ContextInput, workspace: string, options: RequestOptions): Promise<OperatorContext> { return parseOperatorContext(await api.post('/operator-contexts', input, options), workspace); }
export async function getOperatorDocument(id: string, workspace: string, options: RequestOptions = {}): Promise<OperatorDocument> { return parseOperatorDocument(await api.get(`/operator-documents/${id}`, options), workspace); }
export async function getContextBinding(kind: 'MISSION' | 'ROVER', id: string, targetId: string, workspace: string, options: RequestOptions = {}): Promise<ContextBinding> { return parseContextBinding(await api.get(`/${kind === 'MISSION' ? 'missions' : 'rover-revisions'}/${id}/operator-context`, options), workspace, kind === 'MISSION' ? 'MISSION_DRAFT' : 'ROVER_REVISION', targetId); }
export async function bindOperatorContext(kind: 'MISSION' | 'ROVER', id: string, targetId: string, workspace: string, binding: ContextBinding, context: OperatorContext | null, options: RequestOptions, missionRevision?: number): Promise<ContextBinding> {
  return parseContextBinding(await api.post(`/${kind === 'MISSION' ? 'missions' : 'rover-revisions'}/${id}/operator-context`, { expected_context_revision: binding.context_revision, context_id: context?.id ?? null, context_sha256: context?.context_sha256 ?? null, ...(kind === 'MISSION' ? { expected_revision: missionRevision } : {}) }, options), workspace, kind === 'MISSION' ? 'MISSION_DRAFT' : 'ROVER_REVISION', targetId);
}
export async function previewOperatorContext(missionId: string | null, roverId: string | null, roverRevisionId: string | null, options: RequestOptions = {}): Promise<ContextSnapshot> {
  const query = new URLSearchParams(); if (missionId) query.set('mission_context_id', missionId); if (roverId) query.set('rover_context_id', roverId);
  return parseContextSnapshot(await api.get(`/operator-context/preview?${query}`, options), { missionId, roverId, roverRevisionId });
}
export async function getPinnedOperatorContext(scope: 'preparations' | 'mission-revisions' | 'runs', id: string, expected?: Parameters<typeof parseContextSnapshot>[1], options: RequestOptions = {}): Promise<ContextSnapshot> { return parseContextSnapshot(await api.get(`/${scope}/${id}/operator-context`, options), expected); }
export function startContextRun(runRequest: components['schemas']['RunCreateInput'], roverContextId: string | null, options: RequestOptions) { return api.post<components['schemas']['CommandAccepted']>('/operator-context/runs', { run_request: runRequest, expected_rover_context_id: roverContextId }, options); }
