import { describe,expect,it,vi } from 'vitest';
import { render,screen } from '@testing-library/react';
import { QueryClient,QueryClientProvider } from '@tanstack/react-query';
import type { components } from '../../generated/schema';
import seed from '../../mock/fixtures/seed.json';
import { TargetView } from './TargetView';
import { RunContext,type RunContextValue } from '../runs/RunContext';
const frozenHistogram={metric_id:'surface_slope_deg',unit:'deg',edges:[0,5,18],area_fraction:[0.4,0.6],valid_area_m2:1200,support_scale_m:480};
vi.mock('../runs/RunContext',async original=>({...await original<Record<string,unknown>>(),useOperationArtifact:()=>({data:{slope_histogram:frozenHistogram,unavailable_dimensions:[]}})}));
vi.mock('../../api/client',()=>({api:{get:vi.fn(async(path:string)=>path.startsWith('/display-layers')?{items:[],next_cursor:null}:seed.target)}}));
vi.mock('../../maps/PlanetaryPanel',()=>({PlanetaryPanel:()=> <div data-testid="planetary-panel">MARS target extent</div>}));
describe('FE-012 target display consumes frozen scientific payloads',()=>{
 it('renders edges/area_fraction without interpreting histogram values as measurements',async()=>{type S=components['schemas'];const context={snapshot:{run_id:'run',target_profile_id:'target'},contract:{target:seed.missionPresets.MARS.target}} as unknown as RunContextValue;render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><RunContext.Provider value={context}><TargetView/></RunContext.Provider></QueryClientProvider>);expect(await screen.findByRole('rowheader',{name:'0–5 deg'})).toBeVisible();expect(screen.getByRole('rowheader',{name:'5–18 deg'})).toBeVisible();expect(screen.getByRole('table',{name:/Slope histogram data/})).toBeVisible();expect(screen.getAllByText('0.4').length).toBeGreaterThan(0);const target=seed.target as S['PlanetaryTargetProfile'];expect(target.metrics.length).toBeGreaterThan(0);});
});
