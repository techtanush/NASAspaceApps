import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from '../../api/client';
import {ApiError} from '../../api/errors';
import {fetchRunActivity,type ActivityItem} from './RunActivity';
const runId='run';
const item=(seq:number):ActivityItem=>({id:`${runId}:${seq}`,run_id:runId,seq,event_type:'tool.started',created_at:'2026-11-14T12:00:00Z',state:'QUALIFYING',status:'RUNNING',summary:'Comparing accepted terrain benchmark.',task_kind:'COMPARE_REQUIREMENT',role:'scientific_worker',candidate_id:'site',candidate_name:'Selected site',requirement_id:'R-SLOPE',invocation_id:'invocation',tool_receipt_id:null,evidence_ids:[]});
afterEach(()=>vi.restoreAllMocks());
describe('recorded activity pagination and authorization',()=>{
 it('appends persisted pages in sequence and follows only the opaque cursor',async()=>{const get=vi.spyOn(api,'get').mockResolvedValueOnce({items:[item(1)],next_cursor:'opaque:cursor',last_event_seq:3}).mockResolvedValueOnce({items:[item(3)],next_cursor:null,last_event_seq:3});expect(await fetchRunActivity(runId,new AbortController().signal)).toEqual({items:[item(1),item(3)],truncated:false});expect(get.mock.calls[1]![0]).toContain('cursor=opaque%3Acursor');});
 it('accepts an absent extension but keeps authorization failures visible',async()=>{const error=(status:number)=>new ApiError(status,{error:{code:'NOT_FOUND',message:'Unavailable',request_id:'',retryable:false,details:{}}});vi.spyOn(api,'get').mockRejectedValueOnce(error(404)).mockRejectedValueOnce(error(403));await expect(fetchRunActivity(runId,new AbortController().signal)).resolves.toBeNull();await expect(fetchRunActivity(runId,new AbortController().signal)).rejects.toMatchObject({status:403});});
 it('rejects cross-run rows, repeated sequences, and a cursor that does not advance',async()=>{const get=vi.spyOn(api,'get');for(const items of [[{...item(1),run_id:'foreign'}],[item(2),item(1)],[{...item(1),id:'foreign:1'}]]){get.mockResolvedValueOnce({items,next_cursor:null,last_event_seq:2});await expect(fetchRunActivity(runId,new AbortController().signal)).rejects.toThrow('selected investigation');}get.mockResolvedValueOnce({items:[item(1)],next_cursor:'same',last_event_seq:3}).mockResolvedValueOnce({items:[item(2)],next_cursor:'same',last_event_seq:3});await expect(fetchRunActivity(runId,new AbortController().signal)).rejects.toThrow('cursor did not advance');});
});
