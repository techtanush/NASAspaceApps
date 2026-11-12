import type { QueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { queryKeys } from '../../api/queryKeys';
import type { Schema } from './RunContext';

/** IDs in the snapshot are the current projection; collection pages also retain historical revisions. */
export async function fetchPinnedQualifications(cache: QueryClient, workspace: string, runId: string, ids: string[]) {
  const items = await Promise.all(ids.map(id => cache.fetchQuery({
    // The run path also exempts immutable records from generic SSE collection invalidation.
    queryKey: queryKeys.workspace(workspace, `/runs/${runId}`, 'qualification', id),
    staleTime: Infinity,
    retry: false,
    queryFn: async ({ signal }) => {
      const row = await api.get<Schema['QualificationDimension']>(`/qualifications/${id}`, { signal });
      if (row.id !== id || row.run_id !== runId || row.workspace_id !== workspace) {
        throw new Error('Qualification evidence does not match the pinned run and workspace.');
      }
      return row;
    },
  })));
  return { items };
}
