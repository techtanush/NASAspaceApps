import { useCallback, useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { useApi } from '../../api/hooks/useApi';
import { useRunStream } from '../../api/hooks/useRunStream';
import { queryKeys } from '../../api/queryKeys';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { fetchPinnedCandidates } from '../runs/pinnedCandidates';
import { fetchPinnedQualifications } from '../runs/pinnedQualifications';

type S = components['schemas'];
const EMPTY_CANDIDATES:S['EarthAnalogCandidate'][]=[]; const EMPTY_QUALIFICATIONS:S['QualificationDimension'][]=[]; const EMPTY_RESULTS:S['TestResult'][]=[];
/** Everything the tour and report need about one run, kept current by the run event stream. */
export function useRunData(runId: string | undefined) {
  const workspace = useWorkspace(); const identity = `${workspace}:${runId}`; const activeIdentity = useRef(identity); activeIdentity.current = identity; const cache = useQueryClient();
  const snapshot = useApi<S['RunSnapshot']>(workspace, `/runs/${runId}`);
  const value = snapshot.data;
  const contract = useApi<S['MissionTestContract']>(workspace, `/mission-revisions/${value?.mission_revision_id}`, !!value);
  const candidateIds = value?.candidate_ids ?? []; const qualificationIds = value?.qualification_ids ?? []; const resultIds = value?.test_result_ids ?? [];
  const candidates = useQuery({ queryKey: queryKeys.workspace(workspace, 'candidate-projection', runId, ...candidateIds), queryFn: ({ signal }) => fetchPinnedCandidates(workspace, runId!, candidateIds, signal), enabled: candidateIds.length > 0, retry: false });
  const qualifications = useQuery({ queryKey: queryKeys.workspace(workspace, 'qualification-projection', runId, ...qualificationIds), queryFn: ({ signal }) => fetchPinnedQualifications(workspace, runId!, qualificationIds, signal), enabled: qualificationIds.length > 0, retry: false });
  const rover = useApi<S['RoverProfile']>(workspace, `/rover-revisions/${value?.rover_revision_id}`, !!value?.rover_revision_id);
  const results = useQuery({ queryKey: ['workspace', workspace, 'run-results', runId, ...resultIds], queryFn: ({ signal }) => Promise.all(resultIds.map(id => api.get<S['TestResult']>(`/test-results/${id}`, { signal }))), enabled: resultIds.length > 0, retry: false });
  const [lastEvent, setLastEvent] = useState<S['RunEvent'] | null>(null); const [pending, setPending] = useState(false); const [actionError, setActionError] = useState<unknown>(null);
  useEffect(() => { setLastEvent(null); setActionError(null); setPending(false); }, [workspace, runId]);
  const onSnapshot = useCallback((next: S['RunSnapshot']) => {
    if (next.run_id !== runId || next.workspace_id !== workspace) return; const key = queryKeys.workspace(workspace, `/runs/${runId}`);
    const old = cache.getQueryData<S['RunSnapshot']>(key); if (old && old.revision >= next.revision) return; cache.setQueryData(key, next);
  }, [cache, workspace, runId]);
  const onEvent = useCallback((event: S['RunEvent']) => { if (event.run_id === runId && event.workspace_id === workspace) setLastEvent(current => (current && current.seq >= event.seq ? current : event)); }, [runId, workspace]);
  const connection = useRunStream(runId, value, onSnapshot, onEvent);
  const action = async (request: S['RunAction']) => {
    setPending(true); setActionError(null);
    try { await api.post<S['CommandAccepted']>(`/runs/${runId}/actions`, request, { recover: async () => { const refreshed = await api.get<S['RunSnapshot']>(`/runs/${runId}`); onSnapshot(refreshed); return refreshed; } }); onSnapshot(await api.get<S['RunSnapshot']>(`/runs/${runId}`)); return true; }
    catch (cause) { if (activeIdentity.current === identity) { setActionError(cause); await snapshot.refetch(); } return false; } finally { if (activeIdentity.current === identity) setPending(false); }
  };
  return { snapshot: value, contract: contract.data, candidates: candidates.data?.items ?? EMPTY_CANDIDATES, qualifications: qualifications.data?.items ?? EMPTY_QUALIFICATIONS, rover: rover.data, results: results.data ?? EMPTY_RESULTS, lastEvent, connection, pending, action, actionError,
    error: snapshot.error || contract.error || candidates.error || qualifications.error || results.error || rover.error, loading: !value || !contract.data || (candidateIds.length > 0 && candidates.isPending) || (qualificationIds.length > 0 && qualifications.isPending) };
}
