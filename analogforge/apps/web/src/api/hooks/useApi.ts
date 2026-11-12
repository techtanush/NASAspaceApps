import { useQuery,replaceEqualDeep } from '@tanstack/react-query';
import type { components } from '../../generated/schema';
import { api } from '../client';
import { queryKeys } from '../queryKeys';
import { newerSnapshot } from '../runStream';
type Snapshot=components['schemas']['RunSnapshot'];
function isSnapshot(value:unknown):value is Snapshot {return Boolean(value&&typeof value==='object'&&'run_id' in value&&'last_event_seq' in value&&'candidate_ids' in value&&'state' in value);}
export function reconcileResponse(previous:unknown,incoming:unknown):unknown {
 if(isSnapshot(previous)&&isSnapshot(incoming)) {
  if(previous.run_id!==incoming.run_id||previous.workspace_id!==incoming.workspace_id)return previous;
  return newerSnapshot(previous,incoming);
 }
 return replaceEqualDeep(previous,incoming);
}
export function useApi<T>(workspaceId:string,path:string,enabled=true) {
 return useQuery({queryKey:queryKeys.workspace(workspaceId,path),queryFn:({signal})=>api.get<T>(path,{signal}),enabled,retry:false,structuralSharing:reconcileResponse});
}
