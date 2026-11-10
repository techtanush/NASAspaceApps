import { useQuery } from '@tanstack/react-query';
import type { components } from '../generated/schema';
import algorithms from '../../../../contracts/algorithm-ids.json';
import { api } from './client';
import { queryKeys } from './queryKeys';
export const ALGORITHM_IDS=algorithms.algorithm_ids;
export async function getEvidence(id:string,signal?:AbortSignal):Promise<components['schemas']['EvidenceRecord']>{return api.get(`/evidence/${id}`,{signal});}
export async function findEvidenceByAlgorithm(ids:readonly string[],key:keyof typeof ALGORITHM_IDS,signal?:AbortSignal){const records=await Promise.all(ids.map(id=>getEvidence(id,signal)));return records.find(record=>record.algorithm_id===ALGORITHM_IDS[key]);}
export function useEvidence(workspaceId:string,id:string|undefined){return useQuery({queryKey:queryKeys.workspace(workspaceId,'evidence',id),queryFn:({signal})=>getEvidence(id!,signal),enabled:Boolean(id),retry:false});}
export function useArtifactJson<T>(workspaceId:string,sha:string|undefined){return useQuery({queryKey:queryKeys.workspace(workspaceId,'artifact',sha),queryFn:({signal})=>api.get<T>(`/artifacts/${sha}`,{signal}),enabled:Boolean(sha),retry:false});}
