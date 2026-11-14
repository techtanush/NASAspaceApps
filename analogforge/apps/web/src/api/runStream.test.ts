import { afterEach, expect, it, vi } from 'vitest';
import { BACKOFF_MS, RunStream, SSEParser, newerSnapshot } from './runStream';
import type { components } from '../generated/schema';
type Snapshot=components['schemas']['RunSnapshot'];type Event=components['schemas']['RunEvent'];
const snapshot=(seq=0,revision=1)=>({run_id:'run-a',last_event_seq:seq,revision,state:'AWAITING_REVIEW'}) as Snapshot;
const event=(seq:number,run_id='run-a',state='QUALIFYING')=>({seq,run_id,state}) as Event;
afterEach(()=>{vi.useRealTimers();});
it('parses split SSE fields, multiple data lines, id and heartbeat without inventing an event',()=>{const receive=vi.fn();const p=new SSEParser(receive);p.feed(': heartbeat\n\nid: 4\nevent: qualific');p.feed('ation.updated\ndata: {\ndata: "x":1}\n\n');expect(receive).toHaveBeenCalledExactlyOnceWith({id:'4',event:'qualification.updated',data:'{\n"x":1}'});});
function setup(){const onEvent=vi.fn(),onSnapshot=vi.fn(),onConnection=vi.fn(),fetchSnapshot=vi.fn(async()=>snapshot(8,3));const fetcher=vi.fn(async()=>new Response(new ReadableStream({start(){/* Controlled stream remains open until abort. */}}),{headers:{'Content-Type':'text/event-stream'}}));const stream=new RunStream({runId:'run-a',cursor:0,onEvent,onSnapshot,onConnection,fetchSnapshot,fetcher});stream.start();return {stream,onEvent,onSnapshot,onConnection,fetchSnapshot,fetcher};}
it('FE-003 ignores duplicates and wrong-run/out-of-order events, resyncs a gap',async()=>{const s=setup();expect(await s.stream.accept(event(1))).toBe('event');expect(await s.stream.accept(event(1))).toBe('ignored');expect(await s.stream.accept(event(0))).toBe('ignored');expect(await s.stream.accept(event(2,'run-b'))).toBe('ignored');expect(await s.stream.accept(event(3))).toBe('resync');expect(s.onEvent).toHaveBeenCalledTimes(1);expect(s.fetchSnapshot).toHaveBeenCalledTimes(1);expect(s.stream.lastSequence).toBe(8);s.stream.stop();});
it('terminal event obtains final snapshot then closes without reconnect',async()=>{const s=setup();expect(await s.stream.accept(event(1,'run-a','COMPLETED'))).toBe('terminal');expect(s.onSnapshot).toHaveBeenCalledOnce();expect(s.onConnection).toHaveBeenLastCalledWith('closed');expect(await s.stream.accept(event(2))).toBe('ignored');});
it('reads a terminal stream through EOF without aborting its successful response',async()=>{
 let signal:AbortSignal|undefined;
 const closed=vi.fn();
 const stream=new RunStream({runId:'run-a',cursor:0,onEvent:vi.fn(),onSnapshot:vi.fn(),
  onConnection:closed,fetchSnapshot:async()=>({...snapshot(1,2),state:'COMPLETED'}),
  fetcher:async(_url,init)=>{signal=init?.signal as AbortSignal;return new Response(new ReadableStream({start(controller){
   controller.enqueue(new TextEncoder().encode(`id:1\nevent:run.state_changed\ndata:${JSON.stringify(event(1,'run-a','COMPLETED'))}\n\n`));controller.close();
  }}));}});
 stream.start();
 await vi.waitFor(()=>expect(closed).toHaveBeenLastCalledWith('closed'));
 expect(signal?.aborted).toBe(false);
 stream.stop();
 expect(signal?.aborted).toBe(false);
});
it('drains EOF when one server batch contains completion followed by export notifications',async()=>{
 const bytes=new TextEncoder().encode([event(1,'run-a','COMPLETED'),event(2,'run-a','COMPLETED'),event(3,'run-a','COMPLETED')].map(value=>`id:${value.seq}\nevent:run.state_changed\ndata:${JSON.stringify(value)}\n\n`).join(''));
 const response=new Response(new ReadableStream({start(controller){controller.enqueue(bytes);controller.close();}}));
 const reader=response.body!.getReader();const read=vi.spyOn(reader,'read');vi.spyOn(response.body!,'getReader').mockReturnValue(reader);
 let signal:AbortSignal|undefined;
 const receive=vi.fn();const stream=new RunStream({runId:'run-a',cursor:0,onEvent:receive,onSnapshot:vi.fn(),onConnection:vi.fn(),
  fetchSnapshot:async()=>({...snapshot(3,4),state:'COMPLETED'}),fetcher:async(_url,init)=>{signal=init?.signal as AbortSignal;return response;}});
 stream.start();await vi.waitFor(()=>expect(read).toHaveBeenCalledTimes(2));
 expect(receive).toHaveBeenCalledOnce();stream.stop();expect(signal?.aborted).toBe(false);
});
it('FE-005 stop/run-switch rejects late events and cancels reconnect timers',async()=>{vi.useFakeTimers();const s=setup();s.stream.stop();await vi.runAllTimersAsync();expect(await s.stream.accept(event(1))).toBe('ignored');expect(s.fetcher).toHaveBeenCalledTimes(1);});
it('410 expired cursor resyncs before reopening; backoff remains locked',async()=>{vi.useFakeTimers();let calls=0;const fetchSnapshot=vi.fn(async()=>snapshot(8,4));const fetcher=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>{void _input;void _init;calls++;return calls===1?new Response('{}',{status:410}):new Response(new ReadableStream({start(){/* Keep subscription active. */}}));});const stream=new RunStream({runId:'run-a',cursor:0,fetchSnapshot,fetcher,onSnapshot:vi.fn(),onConnection:vi.fn(),onEvent:vi.fn()});stream.start();await vi.advanceTimersByTimeAsync(1);expect(fetchSnapshot).toHaveBeenCalled();expect(String(fetcher.mock.calls[1]?.[0])).toContain('after=8');expect([...BACKOFF_MS]).toEqual([1000,2000,4000,8000,15000]);stream.stop();});
it('FE-004 stale snapshots never overwrite a newer revision',()=>{const current=snapshot(8,9);expect(newerSnapshot(current,snapshot(3,5))).toBe(current);expect(newerSnapshot(current,snapshot(10,10)).revision).toBe(10);});
it('FE-005 each new run resets its cursor and cannot inherit the previous run sequence',async()=>{
 const first=setup();await first.stream.accept(event(1));await first.stream.accept(event(2));first.stream.stop();
 const onEvent=vi.fn();const next=new RunStream({runId:'run-b',cursor:0,fetchSnapshot:async()=>({...snapshot(),run_id:'run-b'}),onEvent,onSnapshot:vi.fn(),onConnection:vi.fn(),fetcher:async()=>new Response(new ReadableStream({start(){/* controlled */}}))});next.start();
 expect(next.lastSequence).toBe(0);expect(await next.accept(event(1,'run-b'))).toBe('event');expect(onEvent).toHaveBeenCalledOnce();next.stop();
});
it('wrong-run or regressive resync snapshot is rejected without advancing cursor or calling consumer',async()=>{
 const receive=vi.fn();const stream=new RunStream({runId:'run-a',cursor:0,onEvent:vi.fn(),onSnapshot:receive,onConnection:vi.fn(),fetchSnapshot:async()=>({...snapshot(90,9),run_id:'run-b'}),fetcher:async()=>new Response(new ReadableStream({start(){/* controlled */}}))});stream.start();await expect(stream.accept(event(5))).rejects.toThrow('Snapshot identity');expect(stream.lastSequence).toBe(0);expect(receive).not.toHaveBeenCalled();stream.stop();
});
