import { setSessionCsrf } from './client';
import { ApiError } from './errors';
export interface Session {workspaceId:string;role:'OWNER'|'EDITOR'|'VIEWER';csrfToken?:string;authMode?:'local'|'oidc'}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function sessionError(code:string,message:string,status:number,retryable=false):ApiError {
 return new ApiError(status,{error:{code,message,request_id:crypto.randomUUID(),retryable,details:{}}});
}
function record(value:unknown):Record<string,unknown>|undefined {return value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:undefined;}
export async function loadSession():Promise<Session> {
 const controller=new AbortController();
 const deadline=setTimeout(()=>controller.abort(),15000);
 try{return await authenticatedSession(controller.signal);}finally{clearTimeout(deadline);}
}
async function authenticatedSession(signal:AbortSignal):Promise<Session> {
 // Clear the previous session's token before any failed refresh or workspace switch.
 setSessionCsrf(undefined);
 let response:Response;
 try{response=await fetch('/auth/session',{method:'GET',credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store',signal});}
 catch{throw sessionError('SESSION_UNAVAILABLE','Unable to load the authenticated session. Retry the connection.',0,true);}
 if(response.status===401)throw sessionError('AUTH_REQUIRED','Sign in to access this workspace.',401);
 if(!response.ok)throw sessionError('SESSION_UNAVAILABLE','The authenticated session service is unavailable.',response.status,response.status>=500);
 let data:unknown;
 try{data=await response.json();}catch{if(signal.aborted)throw sessionError('SESSION_UNAVAILABLE','The session check timed out. Retry the connection.',0,true);throw sessionError('SESSION_INVALID','The server returned an invalid session response.',502);}
 const body=record(data),workspace=record(body?.workspace);
 if(body?.authenticated===false)throw sessionError('AUTH_REQUIRED','Sign in to access this workspace.',401);
 const workspaceId=body?.workspace_id??workspace?.id;
 const role=body?.role??workspace?.role;
 if(!body||typeof workspaceId!=='string'||!UUID.test(workspaceId)||!['OWNER','EDITOR','VIEWER'].includes(String(role)))throw sessionError('SESSION_INVALID','The session does not identify a valid authorized workspace and role.',502);
 // JSON null means the session supplies no token (local mode without cookie sessions); absent and null are equivalent.
 const hasSnake=Object.hasOwn(body,'csrf_token')&&body.csrf_token!==null,hasCamel=Object.hasOwn(body,'csrfToken')&&body.csrfToken!==null;
 const csrf=hasSnake?body.csrf_token:body.csrfToken;
 if((hasSnake||hasCamel)&&(typeof csrf!=='string'||csrf.length===0||csrf.length>4096||[...csrf].some(character=>character.charCodeAt(0)<=32||character.charCodeAt(0)===127)))throw sessionError('SESSION_INVALID','The session supplied an invalid CSRF token.',502);
 if(hasSnake&&hasCamel&&body.csrf_token!==body.csrfToken)throw sessionError('SESSION_INVALID','The session supplied conflicting CSRF token fields.',502);
 if(body.auth_mode!==undefined&&!['local','oidc'].includes(String(body.auth_mode)))throw sessionError('SESSION_INVALID','The session supplied an unsupported authentication mode.',502);
 const session:Session={workspaceId,role:role as Session['role'],...(typeof csrf==='string'?{csrfToken:csrf}:{}),...(body.auth_mode?{authMode:body.auth_mode as Session['authMode']}:{})};
 setSessionCsrf(session.csrfToken);
 return session;
}
