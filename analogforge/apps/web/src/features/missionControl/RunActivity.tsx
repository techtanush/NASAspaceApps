import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { ApiError } from '../../api/errors';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { ErrorPanel } from '../../components/ui';
import { sentenceCase } from './narrator';

export interface ActivityItem {id:string;run_id:string;seq:number;event_type:string;created_at:string;state:string;status:'RUNNING'|'COMPLETED'|'BLOCKED'|'FAILED'|'CANCELLED'|'INFO';summary:string;failure_code?:string|null;task_kind:string|null;role:string|null;candidate_id:string|null;candidate_name:string|null;requirement_id:string|null;invocation_id:string|null;tool_receipt_id:string|null;evidence_ids:string[];evidence_count?:number;evidence_ids_truncated?:boolean;role_result_id?:string|null}
interface ActivityPage {items:ActivityItem[];next_cursor:string|null;last_event_seq:number}
export async function fetchRunActivity(runId:string,signal:AbortSignal):Promise<{items:ActivityItem[];truncated:boolean}|null> {
  if(import.meta.env.VITE_API_MOCK==='1')return null;
  const items:ActivityItem[]=[]; const seen=new Set<string>(); let cursor:string|null=null; let lastSeq=0;
  for(let pageIndex=0;pageIndex<20;pageIndex++) {
    const params=new URLSearchParams({limit:'100'});if(cursor)params.set('cursor',cursor);
    let page:ActivityPage;
    try{page=await api.get<ActivityPage>(`/runs/${runId}/activity?${params}`,{signal});}catch(error){if(pageIndex===0&&error instanceof ApiError&&error.status===404)return null;throw error;}
    if(!Array.isArray(page.items)||!(page.next_cursor===null||typeof page.next_cursor==='string')||!Number.isSafeInteger(page.last_event_seq))throw new Error('Unsupported activity response');
    if(page.items.some(item=>item.failure_code!=null&&(typeof item.failure_code!=='string'||!/^\b[A-Z][A-Z0-9_]{0,63}$/.test(item.failure_code))))throw new Error('Unsupported recorded failure code');
    if(page.items.some(item=>(item.evidence_count!==undefined&&(!Number.isSafeInteger(item.evidence_count)||item.evidence_count<item.evidence_ids.length))||(item.evidence_ids_truncated!==undefined&&(typeof item.evidence_ids_truncated!=='boolean'||item.evidence_count===undefined||item.evidence_ids_truncated!==(item.evidence_count>item.evidence_ids.length)))||(item.role_result_id!=null&&typeof item.role_result_id!=='string')))throw new Error('Unsupported activity evidence reference counts');
    for(const item of page.items){if(item.run_id!==runId||item.id!==`${runId}:${item.seq}`||!Number.isSafeInteger(item.seq)||item.seq<=lastSeq||item.seq>page.last_event_seq||typeof item.summary!=='string'||!['RUNNING','COMPLETED','BLOCKED','FAILED','CANCELLED','INFO'].includes(item.status)||!Array.isArray(item.evidence_ids))throw new Error('Activity does not match the selected investigation');lastSeq=item.seq;items.push(item);}
    if(page.next_cursor===null)return {items,truncated:false};
    if(seen.has(page.next_cursor)||page.items.length===0)throw new Error('Activity cursor did not advance');seen.add(page.next_cursor);cursor=page.next_cursor;
  }
  return {items,truncated:true};
}
export function useRunActivity(run:components['schemas']['RunSnapshot'],enabled=true) {
  const workspace=useWorkspace();
  const query=useQuery({queryKey:['workspace',workspace,'run-activity',run.run_id],enabled:enabled&&run.workspace_id===workspace,queryFn:({signal})=>fetchRunActivity(run.run_id,signal),retry:false});
  useEffect(()=>{if(enabled&&run.workspace_id===workspace)void query.refetch();},[run.run_id,run.last_event_seq,workspace,enabled]);
  return query;
}
export function ActivityReferences({item}:{item:ActivityItem}) {
  if(!item.tool_receipt_id&&!item.evidence_ids.length&&!item.role_result_id)return null;
  const total=item.evidence_count??item.evidence_ids.length;const truncated=total>item.evidence_ids.length;
  return <details><summary>Evidence references{truncated?` (${item.evidence_ids.length} of ${total})`:''}</summary>{truncated&&<p className="helper">Showing {item.evidence_ids.length} of {total} evidence references. The full list is retained in the recorded role result.</p>}{item.role_result_id&&<p className="mono">Role result: {item.role_result_id}</p>}{item.tool_receipt_id&&<p className="mono">Receipt: {item.tool_receipt_id}</p>}{item.evidence_ids.map(id=><p className="mono" key={id}>{id}</p>)}</details>;
}
export function RunActivity({run}:{run:components['schemas']['RunSnapshot']}) {
  const query=useRunActivity(run);
  const items=query.error?[]:query.data?.items??[];
  return <section className="mc-activity" aria-label="Investigation activity" data-testid="run-activity">
    <header><div><p className="mc-eyebrow">Work log</p><h2>Investigation activity</h2></div><span className="mono">{items.length?`${items.length} records`:sentenceCase(run.state)}</span></header>
    <p className="helper">Committed operations and evidence, updated as this investigation progresses.</p>
    {query.error&&<ErrorPanel error={query.error} onRetry={()=>{void query.refetch();}}/>}
    {!items.length&&!query.error&&<p className="helper" role="status">{query.isPending?'Retrieving recorded activity.':query.data===null?'Detailed activity is unavailable on this deployment. The committed run state is shown above.':'No committed activity records yet.'}</p>}
    <ol className="mc-activity-list" aria-label="Recorded operations" aria-live="polite" aria-relevant="additions">{items.map(item=><li key={item.id} data-status={item.status} data-testid="activity-item"><span className="mc-activity-dot" aria-hidden="true"/><div><div className="mc-activity-meta"><strong>{sentenceCase(item.task_kind??item.event_type)}</strong><span>{item.event_type.endsWith('.started')?'Started':sentenceCase(item.status)}</span></div><p>{item.summary}</p>{item.candidate_name&&<p className="helper">Site: {item.candidate_name}</p>}<ActivityReferences item={item}/><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time></div></li>)}</ol>
    {query.data?.truncated&&<p className="mc-detail-notice">Showing the first 2,000 activity records. Later records are available in the evidence workbench.</p>}
  </section>;
}
