import {beforeEach,describe,expect,it,vi} from 'vitest';
import {render,screen,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import type {components} from '../../generated/schema';
import {api} from '../../api/client';
import {Workspace} from './Workspace';
type S=components['schemas'];
vi.mock('../../api/client',()=>({api:{get:vi.fn()}}));
const run:S['RunSnapshot']={schema_version:'1.0',id:'00000000-0000-4000-8000-000000000002',workspace_id:'00000000-0000-4000-8000-000000000001',run_id:'00000000-0000-4000-8000-000000000002',mode:'synthetic',created_at:'2026-11-08T12:00:00Z',state:'COMPLETED',revision:12,last_event_seq:9,mission_revision_id:'00000000-0000-4000-8000-000000000003',rover_revision_id:'00000000-0000-4000-8000-000000000004',target_profile_id:null,candidate_ids:[],qualification_ids:[],test_ids:['00000000-0000-4000-8000-000000000005'],test_result_ids:['00000000-0000-4000-8000-000000000006'],portfolio_ids:[],passport_id:null,pending_review:null,blocked_dependencies:[],config_sha256:'a'.repeat(64),selected_candidate_id:null,selected_portfolio_id:null,scenario_config_id:'synthetic-mars-mobility-v1',dataset_lock_id:'practice-lock-v1'};
beforeEach(()=>vi.clearAllMocks());
describe('UX-001 terminal state and scientific outcome are independent',()=>{
 const outcomes:S['VerificationOutcome'][]=['PASS','FAIL','INCONCLUSIVE'];
 it.each(outcomes)('a COMPLETED investigation displays its actual %s verifier result',async(outcome)=>{
  const result:S['TestResult']={schema_version:'1.0',id:run.test_result_ids[0]!,workspace_id:run.workspace_id,run_id:run.run_id,mode:run.mode,created_at:run.created_at,test_id:run.test_ids[0]!,outcome,failure_category:outcome==='PASS'?null:outcome==='FAIL'?'ROUTE':'DATA',search_status:'FOUND',verified_route_sha256:outcome==='PASS'?'b'.repeat(64):null,metrics:[],violations:[],evidence_ids:[],verifier_version:'test-fixture',limitations:[]};
  vi.mocked(api.get).mockImplementation(async(path:string)=>path.startsWith('/test-results/')?result:path==='/runs'?{items:[run],next_cursor:null}:path==='/capabilities'?{scenario_config_ids:[]}:{items:[],next_cursor:null});
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Workspace/></MemoryRouter></QueryClientProvider>);
  const row=await screen.findByTestId('run-row');expect(row).toHaveAttribute('data-state','COMPLETED');expect(await within(row).findByText(outcome)).toBeVisible();expect(within(row).getByText('COMPLETED')).toBeVisible();
 });
});
