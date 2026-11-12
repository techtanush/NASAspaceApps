import { act,renderHook,waitFor } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import { api } from '../client';
import { RunStream } from '../runStream';
import { reconcileResponse } from './useApi';
import { useRunStream } from './useRunStream';
import type { components } from '../../generated/schema';
type Snapshot=components['schemas']['RunSnapshot'];
const snapshot=(run_id:string,revision=1)=>({run_id,workspace_id:'workspace',last_event_seq:0,revision,state:'AWAITING_REVIEW',candidate_ids:[]}) as unknown as Snapshot;
afterEach(()=>vi.restoreAllMocks());
it('FE-005 delayed old-run snapshot is aborted and cannot call the new-run callback',async()=>{
 vi.spyOn(RunStream.prototype,'start').mockImplementation(function(this:RunStream){void this;});
 let resolveOld:(value:Snapshot)=>void=()=>undefined;const get=vi.spyOn(api,'get').mockImplementation(()=>new Promise(resolve=>{resolveOld=resolve as (value:Snapshot)=>void;}));
 const first=vi.fn(),second=vi.fn();const hook=renderHook(({run,callback})=>useRunStream(run.run_id,run,callback),{initialProps:{run:snapshot('a'),callback:first}});
 // Trigger the event handler through a controller built by the hook.
 const constructorOptions=(RunStream.prototype.start as unknown as {mock:{contexts:RunStream[]}}).mock.contexts[0] as unknown as {options:{onEvent:()=>void}};
 act(()=>constructorOptions.options.onEvent());expect(get).toHaveBeenCalledOnce();hook.rerender({run:snapshot('b'),callback:second});
 await act(async()=>{resolveOld(snapshot('a',10));});await waitFor(()=>expect(second).not.toHaveBeenCalled());expect(first).not.toHaveBeenCalled();hook.unmount();
});
it('FE-004 cache reconciliation rejects stale or wrong-identity snapshots including delayed query completions',()=>{const current=snapshot('a',8);expect(reconcileResponse(current,snapshot('a',2))).toBe(current);expect(reconcileResponse(current,snapshot('b',20))).toBe(current);expect((reconcileResponse(current,snapshot('a',9)) as Snapshot).revision).toBe(9);});
it('offline pauses and closes the stream; online refetches the snapshot before opening one replacement subscription',async()=>{
 const start=vi.spyOn(RunStream.prototype,'start').mockImplementation(()=>undefined);const stop=vi.spyOn(RunStream.prototype,'stop').mockImplementation(()=>undefined);const get=vi.spyOn(api,'get').mockResolvedValue(snapshot('a',3));
 const hook=renderHook(()=>useRunStream('a',snapshot('a'),vi.fn()));expect(start).toHaveBeenCalledTimes(1);
 act(()=>window.dispatchEvent(new Event('offline')));expect(hook.result.current).toBe('paused');expect(stop).toHaveBeenCalledTimes(1);
 await act(async()=>{window.dispatchEvent(new Event('online'));});expect(get).toHaveBeenCalledTimes(1);expect(start).toHaveBeenCalledTimes(2);hook.unmount();
});

it('coalesces replay bursts while preserving a final refresh after an in-flight snapshot',async()=>{
 const start=vi.spyOn(RunStream.prototype,'start').mockImplementation(()=>undefined);
 const pending:Array<(value:Snapshot)=>void>=[];
 const get=vi.spyOn(api,'get').mockImplementation(()=>new Promise(resolve=>{pending.push(resolve as (value:Snapshot)=>void);}));
 const receive=vi.fn();const hook=renderHook(()=>useRunStream('a',snapshot('a'),receive));
 const controller=start.mock.contexts[0] as unknown as {options:{onEvent:()=>void}};
 act(()=>{for(let i=0;i<25;i++)controller.options.onEvent();});
 expect(get).toHaveBeenCalledOnce();
 await act(async()=>{pending[0]!(snapshot('a',2));});
 await waitFor(()=>expect(get).toHaveBeenCalledTimes(2));
 await act(async()=>{pending[1]!(snapshot('a',3));});
 expect(receive).toHaveBeenLastCalledWith(snapshot('a',3));
 expect(get).toHaveBeenCalledTimes(2);hook.unmount();
});
