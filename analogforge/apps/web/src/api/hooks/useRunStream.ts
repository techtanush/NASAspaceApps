import { useEffect, useRef, useState } from 'react';
import type { components } from '../../generated/schema';
import { api } from '../client';
import { RunStream, type ConnectionState } from '../runStream';
type Snapshot=components['schemas']['RunSnapshot'];
export function useRunStream(runId:string|undefined,snapshot:Snapshot|undefined,onSnapshot:(snapshot:Snapshot)=>void,onEvent?:(event:components['schemas']['RunEvent'])=>void) {
 const [connection,setConnection]=useState<ConnectionState>('connecting'); const callback=useRef(onSnapshot);callback.current=onSnapshot;
 const eventCallback=useRef(onEvent);eventCallback.current=onEvent;
 const mountedRun=useRef(runId);mountedRun.current=runId;
 const hasSnapshot=Boolean(snapshot);
 useEffect(()=>{
  if(!runId || !snapshot)return;
  let active=true;let online=navigator.onLine;let generation=0;let abort=new AbortController();let controller:RunStream|undefined;
  const workspace=snapshot.workspace_id;
  const deliver=(value:Snapshot)=>{if(active&&online&&mountedRun.current===runId&&value.run_id===runId&&value.workspace_id===workspace)callback.current(value);};
  const load=()=>api.get<Snapshot>(`/runs/${runId}`,{signal:abort.signal});
  const launch=()=>{
   if(!active||!online)return;
   controller=new RunStream({runId,workspaceId:workspace,cursor:0,fetchSnapshot:load,onSnapshot:deliver,onConnection:state=>{if(active&&online&&mountedRun.current===runId)setConnection(state);},onEvent:event=>{if(active&&online&&mountedRun.current===runId)eventCallback.current?.(event);void load().then(deliver).catch(()=>{if(active&&online)setConnection('paused');});}});controller.start();
  };
  const offline=()=>{online=false;generation++;controller?.stop();abort.abort();if(active)setConnection('paused');};
  const reconnect=()=>{
   online=true;const current=++generation;abort=new AbortController();setConnection('resyncing');
   void load().then(value=>{if(!active||current!==generation||mountedRun.current!==runId)return;deliver(value);launch();}).catch(()=>{if(active&&current===generation)setConnection('paused');});
  };
  window.addEventListener('offline',offline);window.addEventListener('online',reconnect);
  if(online)launch();else setConnection('paused');
  return()=>{active=false;generation++;window.removeEventListener('offline',offline);window.removeEventListener('online',reconnect);abort.abort();controller?.stop();};
 },[runId,hasSnapshot]);
 return connection;
}
