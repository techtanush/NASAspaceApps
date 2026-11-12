// Independent protocol evidence for a fully consumed terminal SSE response.
// A Chromium cancellation notification alone is never enough to waive C12.
const terminal=new Set(['COMPLETED','FAILED','CANCELLED']);
export function terminalStreamProof(text,url,requestId){
 if(!requestId)return null;
 const parsed=new URL(url,'http://audit.invalid');
 const run=parsed.pathname.match(/^\/api\/v1\/runs\/([a-f0-9-]{36})\/events$/)?.[1];
 const start=Number(parsed.searchParams.get('after')??0);
 if(!run||!Number.isSafeInteger(start)||start<0)return null;
 let sequence=start,workspace=null,last=null,count=0;
 try{
  for(const frame of text.replace(/\r\n/g,'\n').split('\n\n')){
   const data=frame.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).replace(/^ /,'')).join('\n');
   if(!data)continue;
   const event=JSON.parse(data);
   const id=frame.split('\n').find(line=>line.startsWith('id:'))?.slice(3).trim();
   if(event.run_id!==run||!event.workspace_id||event.seq!==sequence+1||String(event.seq)!==id)return null;
   if(workspace!==null&&workspace!==event.workspace_id)return null;
   workspace=event.workspace_id;sequence=event.seq;last=event;count++;
  }
 }catch{return null;}
 if(!count||!terminal.has(last.state)||!text.endsWith('\n\n'))return null;
 return {requestId,runId:run,workspaceId:workspace,lastSequence:sequence,state:last.state,eventCount:count};
}
export function matchesTerminalSnapshot(proof,snapshots,startedAt,endedAt){
 return !!proof&&snapshots.some(({snapshot,seenAt})=>seenAt>=startedAt&&seenAt<=endedAt&&
  snapshot.run_id===proof.runId&&snapshot.workspace_id===proof.workspaceId&&
  snapshot.state===proof.state&&snapshot.last_event_seq===proof.lastSequence);
}
