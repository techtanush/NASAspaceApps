import { api } from '../../api/client';
import type { Schema } from './RunContext';

/** IDs in the snapshot are the current projection; collection pages also retain historical revisions. */
export async function fetchPinnedQualifications(workspace: string, runId: string, ids: string[], signal?: AbortSignal) {
  const wanted = new Set(ids);
  const found = new Map<string, Schema['QualificationDimension']>();
  const cursors = new Set<string>();
  let cursor: string | null = null;
  if (!ids.length) return { items: [] };
  for (let page = 0; page < 1000; page++) {
    const params = new URLSearchParams({ run_id: runId, limit: '100' });
    if (cursor) params.set('cursor', cursor);
    const result = await api.get<Schema['ListQualificationDimension']>(`/qualifications?${params}`, { signal });
    for (const row of result.items) {
      if (!wanted.has(row.id)) continue;
      if (row.run_id !== runId || row.workspace_id !== workspace) {
        throw new Error('Qualification evidence does not match the pinned run and workspace.');
      }
      found.set(row.id, row);
    }
    if (found.size === wanted.size) return { items: ids.map(id => found.get(id)!) };
    cursor = result.next_cursor;
    if (!cursor || cursors.has(cursor)) break;
    cursors.add(cursor);
  }
  throw new Error('Pinned qualification evidence is incomplete. Refresh the run snapshot.');
}
