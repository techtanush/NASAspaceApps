import type { components } from '../generated/schema';
import { API_BASE } from './client';
type RunEvent = components['schemas']['RunEvent'];
type Snapshot = components['schemas']['RunSnapshot'];
export interface SSEMessage { id: string; event: string; data: string }
export class SSEParser {
  private buffer = ''; private event = ''; private id = ''; private data: string[] = [];
  constructor(private readonly receive: (message: SSEMessage) => void) {}
  feed(chunk: string): void {
    this.buffer += chunk.replace(/\r\n/g,'\n');
    let split: number;
    while ((split = this.buffer.indexOf('\n')) !== -1) {
      const line = this.buffer.slice(0, split).replace(/\r$/,''); this.buffer = this.buffer.slice(split + 1);
      if (!line) {
        if (this.data.length) this.receive({id:this.id,event:this.event || 'message',data:this.data.join('\n')});
        this.event=''; this.data=[]; continue;
      }
      if (line.startsWith(':')) continue;
      const colon=line.indexOf(':'); const field=colon < 0 ? line : line.slice(0,colon); const value=(colon < 0 ? '' : line.slice(colon+1)).replace(/^ /,'');
      if(field==='id' && !value.includes('\0')) this.id=value;
      if(field==='event') this.event=value;
      if(field==='data') this.data.push(value);
    }
  }
}
export const BACKOFF_MS = [1000,2000,4000,8000,15000] as const;
const terminal = new Set(['COMPLETED','FAILED','CANCELLED']);
export type ConnectionState = 'connected' | 'connecting' | 'paused' | 'resyncing' | 'closed';
export interface RunStreamOptions {
  runId: string; cursor: number; workspaceId?:string; onEvent: (event: RunEvent) => void;
  onSnapshot: (snapshot: Snapshot) => void; onConnection: (state: ConnectionState) => void;
  fetchSnapshot: () => Promise<Snapshot>; fetcher?: typeof fetch;
}
export class RunStream {
  private cursor: number; private stopped = true; private abort?: AbortController;
  private timer?: ReturnType<typeof setTimeout>; private reconnects = 0; private generation = 0;
  constructor(private readonly options: RunStreamOptions) { this.cursor=options.cursor; }
  start(): void { if (!this.stopped) return; this.stopped=false; this.generation++; void this.connect(false,this.generation); }
  stop(): void { this.stopped=true; this.generation++; this.abort?.abort(); clearTimeout(this.timer); this.options.onConnection('closed'); }
  get lastSequence(): number { return this.cursor; }
  private async resync(generation: number): Promise<Snapshot | undefined> {
    this.options.onConnection('resyncing');
    const snapshot=await this.options.fetchSnapshot();
    if(this.stopped || generation !== this.generation) return;
    if(snapshot.run_id!==this.options.runId || (this.options.workspaceId&&snapshot.workspace_id!==this.options.workspaceId) || snapshot.last_event_seq<this.cursor)throw new TypeError('Snapshot identity or cursor mismatch');
    this.cursor=snapshot.last_event_seq; this.options.onSnapshot(snapshot); return snapshot;
  }
  async accept(event: RunEvent): Promise<'ignored'|'event'|'resync'|'terminal'> {
    if(this.stopped || event.run_id!==this.options.runId || (this.options.workspaceId&&event.workspace_id!==this.options.workspaceId) || event.seq<=this.cursor) return 'ignored';
    if(event.seq!==this.cursor+1) { await this.resync(this.generation); return 'resync'; }
    this.cursor=event.seq; this.options.onEvent(event);
    if(terminal.has(event.state)) { await this.resync(this.generation); this.stop(); return 'terminal'; }
    return 'event';
  }
  private async connect(reconnect: boolean,generation: number): Promise<void> {
    if(this.stopped || generation !== this.generation) return;
    try {
      if(reconnect) { const snapshot=await this.resync(generation); if(snapshot && terminal.has(snapshot.state)) { this.stop(); return; } }
      if(this.stopped || generation !== this.generation) return;
      this.options.onConnection('connecting'); this.abort=new AbortController();
      const response=await (this.options.fetcher || fetch)(`${API_BASE}/runs/${this.options.runId}/events?after=${this.cursor}`,{signal:this.abort.signal,credentials:'same-origin',headers:{Accept:'text/event-stream','Last-Event-ID':String(this.cursor)}});
      if(response.status===410) { await this.resync(generation); this.schedule(generation,0); return; }
      if(!response.ok || !response.body) throw new TypeError('Event stream unavailable');
      this.options.onConnection('connected');
      const reader=response.body.getReader(); const decoder=new TextDecoder(); let pending=Promise.resolve<'ignored'|'event'|'resync'|'terminal'>('ignored');
      const parser=new SSEParser(message=>{pending=pending.then(()=>this.accept(JSON.parse(message.data) as RunEvent));});
      while(!this.stopped && generation===this.generation) {
        const read=await reader.read(); if(read.done) break;
        parser.feed(decoder.decode(read.value,{stream:true}));
        const state=await pending;
        if(state==='resync') {await reader.cancel(); this.schedule(generation,0); return;}
        if(state==='terminal') {await reader.cancel(); return;}
      }
      if(!this.stopped) this.schedule(generation);
    } catch(error) {
      if(this.stopped || generation!==this.generation || (error instanceof DOMException && error.name==='AbortError')) return;
      this.options.onConnection('paused'); this.schedule(generation);
    }
  }
  private schedule(generation: number, delay?: number): void {
    if(this.stopped || generation!==this.generation) return;
    const base=BACKOFF_MS[Math.min(this.reconnects++,BACKOFF_MS.length-1)]!;
    // Cryptographic jitter affects reconnect timing only, never displayed scientific values.
    const jitter = typeof crypto !== 'undefined' ? crypto.getRandomValues(new Uint8Array(1))[0]! : 0;
    this.timer=setTimeout(()=>void this.connect(true,generation),delay ?? base + jitter);
  }
}
export function newerSnapshot(current: Snapshot | undefined, incoming: Snapshot): Snapshot { return current && current.run_id===incoming.run_id && (current.revision>incoming.revision||current.last_event_seq>incoming.last_event_seq) ? current : incoming; }
