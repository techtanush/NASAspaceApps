import { afterEach,expect,it,vi } from 'vitest';
import { setupServer } from 'msw/node';
import { loadSession } from './session';
import { api,setSessionCsrf } from './client';
import { ApiError } from './errors';
import { handlers } from '../mock/handlers';
import { workspaceId } from '../mock/state';
const otherWorkspace='12345678-abcd-4123-8123-123456789abc';
afterEach(()=>{vi.unstubAllGlobals();setSessionCsrf(undefined);});
it('uses the authenticated server workspace instead of a fabricated development UUID and installs its CSRF before mutations',async()=>{
 const requests:{url:string;headers:Headers;credentials:unknown}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url,init)=>{requests.push({url:String(url),headers:new Headers(init.headers),credentials:init.credentials});return String(url)==='/auth/session'?Response.json({workspace_id:otherWorkspace,role:'EDITOR',csrf_token:'server-session-csrf'}):Response.json({revision:1});}));
 expect(await loadSession()).toEqual({workspaceId:otherWorkspace,role:'EDITOR',csrfToken:'server-session-csrf'});await api.post('/missions',{});
 expect(requests[0]).toMatchObject({url:'/auth/session',credentials:'same-origin'});expect(requests[1]!.headers.get('X-CSRF-Token')).toBe('server-session-csrf');
});
it('supports nested authoritative workspace and the documented csrfToken compatibility alias',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>Response.json({workspace:{id:otherWorkspace,role:'VIEWER'},csrfToken:'nested-session-token',user:{id:'optional-user'}})));
 expect(await loadSession()).toEqual({workspaceId:otherWorkspace,role:'VIEWER',csrfToken:'nested-session-token'});
});
it('an omitted token stays absent, clearing a prior workspace token',async()=>{
 setSessionCsrf('old-workspace-token');let calls=0;const headers:Headers[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_url,init)=>{void _url;headers.push(new Headers(init.headers));return ++calls===1?Response.json({workspace_id:otherWorkspace,role:'OWNER'}):Response.json({revision:1});}));
 expect(await loadSession()).toEqual({workspaceId:otherWorkspace,role:'OWNER'});await api.post('/missions',{});expect(headers[1]!.has('X-CSRF-Token')).toBe(false);
});
it.each([
 [{workspace_id:'not-a-uuid',role:'OWNER'},'workspace'],
 [{workspace_id:otherWorkspace,role:'ADMIN'},'role'],
 [{workspace_id:otherWorkspace,role:'OWNER',csrf_token:''},'empty token'],
 [{workspace_id:otherWorkspace,role:'OWNER',csrf_token:'bad\r\nheader'},'unsafe token'],
 [{workspace_id:otherWorkspace,role:'OWNER',csrf_token:'one',csrfToken:'two'},'conflicting token'],
 [{authenticated:false},'unauthenticated response'],
])('rejects invalid session %s (%s) with an ApiError and no workspace fallback',async(body,label)=>{
 void label;vi.stubGlobal('fetch',vi.fn(async()=>Response.json(body)));await expect(loadSession()).rejects.toMatchObject({name:'ApiError',code:'SESSION_INVALID'});
});
it('401, HTTP failures, malformed JSON and network failures are named errors rather than a local workspace fallback',async()=>{
 for(const [response,code] of [[new Response('{}',{status:401}),'AUTH_REQUIRED'],[new Response('{}',{status:503}),'SESSION_UNAVAILABLE'],[new Response('not json'),'SESSION_INVALID']] as const){vi.stubGlobal('fetch',vi.fn(async()=>response));try{await loadSession();throw new Error('Expected session rejection');}catch(error){expect(error).toBeInstanceOf(ApiError);expect(error).toMatchObject({code});}}
 vi.stubGlobal('fetch',vi.fn(async()=>{throw new TypeError('Disconnected');}));await expect(loadSession()).rejects.toMatchObject({code:'SESSION_UNAVAILABLE',retryable:true});
});
it('mock /auth/session exposes the actual seeded workspace and an explicit development CSRF token',async()=>{
 const server=setupServer(...handlers);server.listen({onUnhandledRequest:'error'});
 try{const response=await fetch('http://localhost/auth/session');expect(response.status).toBe(200);expect(await response.json()).toMatchObject({workspace_id:workspaceId,role:'OWNER',csrf_token:'development-only-preview-csrf'});}finally{server.close();}
});
