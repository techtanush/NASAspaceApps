import {beforeEach,expect,it,vi} from 'vitest';
import {api} from '../../api/client';
import type {components} from '../../generated/schema';
import {fetchRoverProfiles} from './roverProfiles';
import rover from '../../../../../tests/fixtures/kit/rovers/ares-1.json';
vi.mock('../../api/client',()=>({api:{get:vi.fn()}}));
const profile=(id:string)=>({...rover,id,rover_id:id,workspace_id:'workspace',revision:1,created_at:'2026-11-12T00:00:00Z'}) as components['schemas']['RoverProfile'];
beforeEach(()=>vi.resetAllMocks());
it('loads later revisions with opaque encoded cursors, de-duplicates boundary rows and propagates cancellation',async()=>{
 const signal=new AbortController().signal;
 vi.mocked(api.get).mockResolvedValueOnce({items:[profile('old')],next_cursor:'a+b /='}).mockResolvedValueOnce({items:[profile('old'),profile('new')],next_cursor:null});
 expect((await fetchRoverProfiles(signal)).items.map(row=>row.id)).toEqual(['old','new']);
 expect(api.get).toHaveBeenNthCalledWith(2,'/rovers?cursor=a%2Bb+%2F%3D&limit=100',{signal});
});
it('rejects cyclic cursors without silently claiming a complete library',async()=>{
 vi.mocked(api.get).mockResolvedValue({items:[],next_cursor:'same'});
 await expect(fetchRoverProfiles()).rejects.toThrow('repeated a cursor');expect(api.get).toHaveBeenCalledTimes(2);
});
it('preserves collection errors instead of returning a truncated success',async()=>{
 vi.mocked(api.get).mockResolvedValueOnce({items:[profile('old')],next_cursor:'next'}).mockRejectedValueOnce(new Error('offline'));
 await expect(fetchRoverProfiles()).rejects.toThrow('offline');
});
