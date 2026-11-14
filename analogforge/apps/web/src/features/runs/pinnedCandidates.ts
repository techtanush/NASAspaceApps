import { api } from '../../api/client';
import type { Schema } from './RunContext';

/** Preserve the science shortlist and appended nominations; unknown rows keep their collection order. */
export function orderCandidates(rows: Schema['EarthAnalogCandidate'][], ids: string[]) {
  const positions = new Map(ids.map((id, index) => [id, index]));
  return [...rows].sort((left, right) =>
    (positions.get(left.id) ?? ids.length) - (positions.get(right.id) ?? ids.length));
}

/** Candidate collection pagination is chronological; the run pins the presentation order. */
export async function fetchPinnedCandidates(workspace: string, runId: string, ids: string[], signal?: AbortSignal) {
  const found = new Map<string, Schema['EarthAnalogCandidate']>();
  const cursors = new Set<string>();
  let cursor: string | null = null;
  if (!ids.length) return { items: [] };
  for (let page = 0; page < 1000; page++) {
    const params = new URLSearchParams({ run_id: runId, limit: '100' });
    if (cursor) params.set('cursor', cursor);
    const result = await api.get<Schema['ListEarthAnalogCandidate']>(`/candidates?${params}`, { signal });
    for (const row of result.items) {
      if (row.run_id !== runId || row.workspace_id !== workspace) {
        throw new Error('Candidate evidence does not match the pinned run and workspace.');
      }
      found.set(row.id, row);
    }
    cursor = result.next_cursor;
    if (!cursor) {
      if (ids.every(id => found.has(id))) return { items: orderCandidates([...found.values()], ids) };
      break;
    }
    if (cursors.has(cursor)) break;
    cursors.add(cursor);
  }
  throw new Error('Pinned candidate evidence is incomplete. Refresh the run snapshot.');
}
