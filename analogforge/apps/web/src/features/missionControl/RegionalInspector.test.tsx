import {beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import seed from '../../mock/fixtures/seed.json';
import {buildSites,type Candidate} from './tour';
import {RegionalInspector} from './RegionalInspector';
const state=vi.hoisted(()=>({layers:[] as Record<string,unknown>[]}));
vi.mock('../../api/hooks/useApi',()=>({useApi:()=>({data:{items:state.layers},isPending:false,error:null})}));
vi.mock('../../app/WorkspaceContext',()=>({useWorkspace:()=> 'workspace'}));
vi.mock('../../maps/EarthMap',()=>({EarthMap:({layers}:{layers:unknown[]})=><div data-testid="layer-count">{layers.length}</div>}));
vi.mock('../../maps/PlanetaryPanel',()=>({PlanetaryPanel:()=>null}));
describe('selected-site display ancestry',()=>{
 const site=buildSites(seed.candidates.slice(0,1) as unknown as Candidate[],[],[])[0]!;
 const layer={id:'layer',candidate_id:site.candidate.id,body:'EARTH',run_id:'run',workspace_id:'workspace',mode:site.candidate.mode,layer_kind:'SLOPE',support_scale_m:60,width_px:32,height_px:32,source_evidence_ids:[],display_crs_wkt:'EPSG:3857'};
 beforeEach(()=>{state.layers=[];});
 it('displays only layers for the selected candidate, run, workspace, body and mode',()=>{state.layers=[layer,{...layer,id:'foreign-candidate',candidate_id:'other'},{...layer,id:'foreign-run',run_id:'other'},{...layer,id:'foreign-workspace',workspace_id:'other'},{...layer,id:'wrong-body',body:'MARS'},{...layer,id:'wrong-mode',mode:'live'}];render(<RegionalInspector runId="run" site={site}/>);expect(screen.getByTestId('layer-count')).toHaveTextContent('1');});
 it('retains geometry and an explicit unavailable notice when no matching evidence exists',()=>{state.layers=[{...layer,run_id:'other'}];render(<RegionalInspector runId="run" site={site}/>);expect(screen.getByRole('status')).toHaveTextContent('Terrain imagery unavailable');expect(screen.getByTestId('layer-count')).toHaveTextContent('0');});
});
