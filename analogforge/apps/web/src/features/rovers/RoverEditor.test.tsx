import {expect,it,vi} from 'vitest';
import {render,screen,within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import {api} from '../../api/client';
import {RoverEditor} from './RoverEditor';
import rover from '../../../../../tests/fixtures/kit/rovers/ares-1.json';
vi.mock('../../api/client',()=>({api:{get:vi.fn(async()=>({items:[],next_cursor:null})),post:vi.fn()}}));
it('attributes rejected mass to the imported file while retaining a valid editable mass',async()=>{
 const user=userEvent.setup();render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><RoverEditor/></MemoryRouter></QueryClientProvider>);
 const mass=screen.getByLabelText('Mass (kg)');expect(mass).toHaveValue(42);expect(mass).not.toHaveAttribute('aria-invalid','true');
 const text=JSON.stringify({...rover,mass_kg:-3});const file=new File([text],'invalid-mass.json',{type:'application/json'});Object.defineProperty(file,'text',{value:async()=>text});
 await user.upload(screen.getByTestId('file-rover-import'),file);
 const rejection=await screen.findByRole('region',{name:'Rejected import validation'});const issue=within(rejection).getByTestId('rover-field-error');expect(issue).toHaveAttribute('data-field','mass_kg');expect(issue).toHaveAttribute('data-source','rejected-import');expect(within(issue).getByRole('img',{name:'Rejected import warning'})).toBeVisible();expect(within(issue).getByText('Mass',{exact:true})).toBeVisible();expect(issue).toHaveTextContent('invalid-mass.json');expect(issue).toHaveTextContent('Imported value: −3.0 kg');expect(within(issue).getByText('Must be greater than 0.')).toBeVisible();
 expect(mass).toHaveValue(42);expect(mass).not.toHaveAttribute('aria-invalid','true');expect(mass.closest('.form-field')).not.toHaveTextContent('must be > 0');
 await user.click(within(issue).getByText('Validation diagnostics'));expect(within(issue).getByText('Field: mass_kg')).toBeVisible();expect(within(issue).getByText('Message: must be > 0')).toBeVisible();expect(within(issue).getByText('Rejected JSON value: -3')).toBeVisible();
});

it('keeps a newly saved rover visible when it is beyond the first collection page',async()=>{
 const user=userEvent.setup();let saved=false;
 const profile={...rover,id:'new-profile',rover_id:'new-rover',workspace_id:'workspace',revision:1,created_at:'2026-11-12T00:00:00Z'};
 vi.mocked(api.get).mockImplementation(async(path:string)=>path.startsWith('/rovers?')?{items:saved?[profile]:[],next_cursor:null}:{items:[],next_cursor:'second-page'});
 vi.mocked(api.post).mockImplementation(async()=>{saved=true;return profile;});
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><RoverEditor/></MemoryRouter></QueryClientProvider>);
 const text=JSON.stringify(rover);const file=new File([text],'ares-1.json',{type:'application/json'});Object.defineProperty(file,'text',{value:async()=>text});
 await user.upload(screen.getByTestId('file-rover-import'),file);
 await screen.findByTestId('rover-import-preview');await user.click(screen.getByTestId('btn-rover-save'));
 await screen.findByText('Saved revision 1');expect(await screen.findByTestId('select-rover')).toHaveTextContent('ARES-1');
});
