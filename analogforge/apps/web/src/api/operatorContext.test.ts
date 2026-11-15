import { afterEach, describe, expect, it, vi } from 'vitest';
import { binding, context, document, draftId, roverContext, roverRevisionId, snapshot, workspaceId } from '../test/operatorContextFixtures';
import { CONTEXT_LIMITS, documentMediaType, parseContextBinding, parseContextSnapshot, parseOperatorContext, parseOperatorDocument, uploadOperatorDocument } from './operatorContext';
afterEach(() => vi.unstubAllGlobals());
describe('private operator context boundary', () => {
  it('accepts bounded private source provenance and refuses foreign workspace or false extraction claims', () => {
    expect(parseOperatorDocument(document, workspaceId)).toEqual(document);
    expect(parseOperatorDocument({ ...document, extraction_status: 'NO_TEXT', extracted_text: ' \n\t' }, workspaceId).extracted_text).toBe(' \n\t');
    for (const patch of [{ workspace_id: 'foreign' }, { original_sha256: 'bad' }, { trust: 'VERIFIED' }, { source_kind: 'SCIENCE_EVIDENCE' }, { extraction_status: 'NO_TEXT' }, { size_bytes: CONTEXT_LIMITS.fileBytes + 1 }]) expect(() => parseOperatorDocument({ ...document, ...patch }, workspaceId)).toThrow();
  });
  it('retains arbitrary declarations and an actual declared zero without making them numeric profile values', () => {
    const declared = { ...roverContext, features: [{ name: 'Drill reach', value: '0', unit: 'cm', unknown: false }] };
    expect(parseOperatorContext(declared, workspaceId).features[0]?.value).toBe('0');
    expect(() => parseOperatorContext({ ...declared, features: [{ ...declared.features[0], unknown: true }] }, workspaceId)).toThrow();
    expect(() => parseOperatorContext({ ...declared, kind: 'MISSION', rover_revision_id: null }, workspaceId)).toThrow();
  });
  it('validates exact draft/revision binding, hash pointer and authoritative mission revision', () => {
    expect(parseContextBinding(binding, workspaceId, 'MISSION_DRAFT', draftId)).toEqual(binding);
    for (const patch of [{ target_id: roverRevisionId }, { mission_revision: null }, { context: context, context_id: context.id, context_sha256: 'f'.repeat(64) }]) expect(() => parseContextBinding({ ...binding, ...patch }, workspaceId, 'MISSION_DRAFT', draftId)).toThrow();
  });
  it('refuses snapshot authority claims, missing digests, context drift and wrong rover identity', () => {
    expect(parseContextSnapshot(snapshot, { missionId: context.id, roverId: roverContext.id, roverRevisionId })).toEqual(snapshot);
    for (const patch of [{ qualification_supported: true }, { scientific_authority: 'EVIDENCE' }, { snapshot_sha256: null }, { model_visible_chars: 12001 }]) expect(() => parseContextSnapshot({ ...snapshot, ...patch })).toThrow();
    expect(() => parseContextSnapshot(snapshot, { roverId: context.id })).toThrow();
    expect(() => parseContextSnapshot(snapshot, { roverRevisionId: draftId })).toThrow();
  });
  it('uploads original bytes with encoded filename, declared type and a reusable command key', async () => {
    const fetcher = vi.fn(async () => Response.json(document)); vi.stubGlobal('fetch', fetcher);
    const file = new File(['source'], 'Mission background.txt', { type: 'text/plain' });
    expect(await uploadOperatorDocument(file, workspaceId, { key: roverRevisionId })).toEqual(document);
    const [, init] = fetcher.mock.calls[0]! as unknown as [string, RequestInit]; const headers = new Headers(init.headers);
    expect(init.body).toBe(file); expect(headers.get('X-Upload-Filename')).toBe('Mission%20background.txt'); expect(headers.get('Content-Type')).toBe('text/plain'); expect(headers.get('Idempotency-Key')).toBe(roverRevisionId);
    expect(() => documentMediaType(new File(['x'], 'bad.exe'))).toThrow('PDF'); expect(() => documentMediaType(new File([], 'empty.pdf'))).toThrow('nonempty');
  });
});
