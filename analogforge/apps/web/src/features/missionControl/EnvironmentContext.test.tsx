import {beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import type {components} from '../../generated/schema';
import {EnvironmentContext} from './EnvironmentContext';
const state=vi.hoisted(()=>({data:null as unknown}));
vi.mock('../../api/environment',async importOriginal=>({...await importOriginal<typeof import('../../api/environment')>(),useEnvironment:()=>({data:state.data,error:null,isPending:false})}));
const run={run_id:'run'} as components['schemas']['RunSnapshot'];
const captured=()=>({status:'CAPTURED',reason_code:'OPERATING_CONTEXT_ONLY',earth_candidates:[{candidate_id:'site',status:'AVAILABLE',reason_code:'COMPLETE_SAMPLE_WINDOW',representative_point:{latitude:35.38836677978821,longitude:-111.58526362148456,method:'GEODETIC_AOI_MIDPOINT'},weather:{query:{start:'2026-11-14T12:00:00Z',end:'2026-11-14T15:00:00Z',source:'mix'},fetched_at:'2026-11-14T11:59:00Z',samples:[{parameter:'temperature',quantity:'air_temperature',unit:'degC',valid_at:'2026-11-14T12:00:00Z',value:0}],provenance:{response_sha256:'a'.repeat(64)},limitations:[]}}],nasa_reference:null,snapshot_sha256:'b'.repeat(64)});
describe('stored weather presentation',()=>{
 beforeEach(()=>{state.data=captured();});
 it('labels a complete captured window accurately and preserves a real zero and raw coordinates',()=>{render(<EnvironmentContext run={run} candidateId="site" report/>);expect(screen.getByText('Stored Earth weather samples cover the requested point and UTC window.')).toBeVisible();expect(screen.getByText(/0.*degC/)).toBeVisible();expect(screen.getByText(/35.38837° N, 111.58526° W/)).toBeVisible();expect((state.data as ReturnType<typeof captured>).earth_candidates[0]!.representative_point.latitude).toBe(35.38836677978821);expect(screen.queryByText('No verified stored context is available.')).not.toBeInTheDocument();});
 it('does not call captured samples unavailable when a future reason code is unrecognized',()=>{const value=captured();value.earth_candidates[0]!.reason_code='FUTURE_CONTEXT_NOTE';state.data=value;render(<EnvironmentContext run={run} candidateId="site" report/>);expect(screen.getByText('Stored operating context; source limitations are shown below.')).toBeVisible();expect(screen.queryByText('No verified stored context is available.')).not.toBeInTheDocument();});
});
