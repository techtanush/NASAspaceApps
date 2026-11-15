import { afterEach, expect, it, vi } from 'vitest';
import { api, setSessionCsrf } from './client';
import { queryKeys, normalizedFilters } from './queryKeys';
afterEach(()=>{vi.unstubAllGlobals();setSessionCsrf();});
it('FE-006 reuses identical key and payload after uncertain response and snapshot recovery',async()=>{let calls=0; const headers:string[]=[];const bodies:unknown[]=[];const recover=vi.fn(async()=>undefined);vi.stubGlobal('fetch',vi.fn(async (_url,init)=>{calls++;headers.push(new Headers(init.headers).get('Idempotency-Key')!); bodies.push(init.body); if(calls===1) throw new TypeError('network');return Response.json({revision:2});}));expect(await api.post('/runs/a/actions',{expected_revision:1},{recover})).toEqual({revision:2});expect(recover).toHaveBeenCalledOnce();expect(new Set(headers).size).toBe(1);expect(bodies[0]).toBe(bodies[1]);});
it('FE-006 does not automatically repeat a semantic revision conflict',async()=>{const fetcher=vi.fn(async()=>Response.json({error:{code:'REVISION_CONFLICT',message:'Reload current state',request_id:'x',retryable:false,details:{current_revision:3}}},{status:409}));vi.stubGlobal('fetch',fetcher);await expect(api.post('/runs/a/actions',{})).rejects.toMatchObject({code:'REVISION_CONFLICT',status:409});expect(fetcher).toHaveBeenCalledOnce();});
it('FE-014 isolates normalized cache keys by workspace',()=>{expect(queryKeys.workspace('a','runs')).not.toEqual(queryKeys.workspace('b','runs'));expect(normalizedFilters({z:1,a:2})).toEqual({a:2,z:1});});
it('preserves an explicit raw document media type and normal CSRF authorization',async()=>{
 const bytes=new Uint8Array([37,80,68,70]);const fetcher=vi.fn(async()=>Response.json({id:'stored-document'}));vi.stubGlobal('fetch',fetcher);setSessionCsrf('session-token');
 await api.raw('/operator-documents',{method:'POST',body:bytes,headers:{'Content-Type':'application/pdf','X-Upload-Filename':'mission.pdf','Idempotency-Key':'upload-command'}});
 const [,init]=fetcher.mock.calls[0]! as unknown as [string,RequestInit];const headers=new Headers(init.headers);
 expect(headers.get('Content-Type')).toBe('application/pdf');expect(headers.get('X-CSRF-Token')).toBe('session-token');expect(headers.get('Idempotency-Key')).toBe('upload-command');expect(init.body).toBe(bytes);expect(init.credentials).toBe('same-origin');
});
