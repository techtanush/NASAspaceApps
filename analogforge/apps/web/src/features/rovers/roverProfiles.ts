import {api} from '../../api/client';
import type {components} from '../../generated/schema';
type Rover=components['schemas']['RoverProfile'];

/** Collection cursors include every immutable revision, not just the first page. */
export async function fetchRoverProfiles(signal?:AbortSignal){
 const profiles=new Map<string,Rover>();const cursors=new Set<string>();let cursor:string|null=null;
 for(let page=0;page<1000;page++){
  const path:string=cursor?`/rovers?${new URLSearchParams({cursor,limit:'100'})}`:'/rovers';
  const result:components['schemas']['ListRoverProfile']=await api.get<components['schemas']['ListRoverProfile']>(path,{signal});
  for(const profile of result.items)profiles.set(profile.id,profile);
  if(!result.next_cursor)return {items:[...profiles.values()],next_cursor:null};
  if(cursors.has(result.next_cursor))throw new Error('Rover revision pagination repeated a cursor. Refresh the library.');
  cursors.add(result.next_cursor);cursor=result.next_cursor;
 }
 throw new Error('Rover revision library exceeds the loading limit. Contact the workspace operator.');
}
