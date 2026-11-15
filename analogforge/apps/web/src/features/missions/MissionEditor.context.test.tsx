import { useEffect } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import contractFixture from '../../../../../tests/fixtures/kit/blueprint-mission-contract.json';
import { binding, context, draftId, snapshot, workspaceId, roverRevisionId } from '../../test/operatorContextFixtures';
import type { ContextBinding } from '../../api/operatorContext';
import { MissionEditor } from './MissionEditor';
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../api/client', () => ({ API_BASE: '/api/v1', api: { get, post } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => workspaceId }));
vi.mock('../../maps/PlanetaryPanel', () => ({ PlanetaryPanel: () => <p>Planetary map boundary</p> }));
vi.mock('../rovers/RoverEditor', () => ({ RoverEditor: ({value,onSelect}:{value:string|null;onSelect:(id:string)=>void}) => <><p>Selected rover: {value??'none'}</p><button onClick={()=>onSelect('different-rover')}>Select a different rover</button></> }));
vi.mock('../operatorContext/BoundOperatorContext', () => ({ BoundOperatorContext: ({ onBound }: { onBound?: (binding: ContextBinding) => void }) => { useEffect(() => { onBound?.({ ...binding, context, context_id: context.id, context_sha256: context.context_sha256, mission_revision: 7 }); }, []); return <p>Persisted mission context boundary</p>; } }));
it('prepares the library draft with its acknowledged context revision and displays actual pinned source lineage', async () => {
  const proposed = { ...contractFixture, accepted_at: null };
  const header = { id: 'mission', workspace_id: workspaceId, revision: 1, name: 'Mission', current_draft_id: draftId, current_contract_id: null };
  const pinned = { ...snapshot, rover_context: null, rover_context_id: null, lineage_pinned: true };
  get.mockImplementation(async (path: string) => {
    if (path === '/capabilities') return { modes: ['synthetic'], scenario_config_ids: ['practice'], default_scenario_config_id: 'practice' };
    if (path === '/configuration/scenarios/practice') return { id: 'practice', name: 'Practice', allowed_modes: ['synthetic'], default_dataset_lock_id: 'lock' };
    if (path === '/missions/mission') return header;
    if (path === `/mission-drafts/${draftId}`) return { created_at: context.created_at, draft: { name: 'Mission', objective: 'Review target terrain', target: proposed.target } };
    if (path === '/missions/mission/operator-context') return { ...binding, context, context_id: context.id, context_sha256: context.context_sha256, mission_revision: 7 };
    if (path.startsWith('/operator-context/preview?')) return pinned;
    if (path === '/jobs/preparation-job') return { state: 'SUCCEEDED', proposed_revision_id: proposed.id };
    if (path === `/mission-revisions/${proposed.id}`) return proposed;
    if (path === `/mission-revisions/${proposed.id}/operator-context`) return pinned;
    throw new Error(`Unexpected GET ${path}`);
  });
  post.mockResolvedValue({ job_id: 'preparation-job' });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/missions/mission/edit']}><Routes><Route path="/missions/:missionId/edit" element={<MissionEditor/>}/></Routes></MemoryRouter></QueryClientProvider>);
  await screen.findByText('Persisted mission context boundary');
  await waitFor(() => expect(screen.getByTestId('btn-build-fingerprint')).toBeEnabled()); fireEvent.click(screen.getByTestId('btn-build-fingerprint'));
  await screen.findByTestId('pinned-operator-context');
  expect(post).toHaveBeenCalledWith('/missions/mission/fingerprint', { expected_revision: 7, mode: 'synthetic', rover_revision_id: null }, expect.anything());
  expect(screen.getByTestId('pinned-operator-context')).toHaveTextContent(context.context_sha256);
  expect(screen.getByTestId('pinned-operator-context')).toHaveTextContent('no scientific authority');
});

it.each([false,true])('restores the accepted context rover without discarding the contract or overriding a later edit (changed=%s)', async changed => {
  const accepted = {...contractFixture,accepted_at:'2026-11-15T04:00:00Z'};
  const header = {id:'mission',workspace_id:workspaceId,revision:7,name:'Mission',current_draft_id:draftId,current_contract_id:accepted.id};
  let resolve!: (value:typeof snapshot)=>void;
  const pending = new Promise<typeof snapshot>(done=>{resolve=done;});
  get.mockImplementation(async(path:string)=>{
    if(path==='/capabilities')return {modes:['synthetic'],scenario_config_ids:['practice'],default_scenario_config_id:'practice'};
    if(path==='/configuration/scenarios/practice')return {id:'practice',name:'Practice',allowed_modes:['synthetic'],default_dataset_lock_id:'lock'};
    if(path==='/missions/mission')return header;
    if(path===`/mission-drafts/${draftId}`)return {created_at:context.created_at,draft:{name:'Mission',objective:'Review target terrain',target:accepted.target}};
    if(path===`/mission-revisions/${accepted.id}`)return accepted;
    if(path===`/mission-revisions/${accepted.id}/operator-context`)return pending;
    throw new Error(`Unexpected GET ${path}`);
  });
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/missions/mission/edit']}><Routes><Route path="/missions/:missionId/edit" element={<MissionEditor/>}/></Routes></MemoryRouter></QueryClientProvider>);
  await screen.findByText('Persisted mission context boundary');
  await waitFor(()=>expect(get).toHaveBeenCalledWith(`/mission-revisions/${accepted.id}/operator-context`,expect.anything()));
  if(changed)fireEvent.click(screen.getByRole('button',{name:'Select a different rover'}));
  resolve(snapshot);
  if(changed){
    await waitFor(()=>expect(screen.getByText('Selected rover: different-rover')).toBeVisible());
    expect(screen.queryByTestId('pinned-operator-context')).not.toBeInTheDocument();
    expect(screen.getByTestId('btn-start-run')).toBeDisabled();
  }else{
    await screen.findByTestId('pinned-operator-context');
    expect(screen.getByText(`Selected rover: ${roverRevisionId}`)).toBeVisible();
    expect(screen.getByTestId('btn-start-run')).toBeEnabled();
    expect(screen.getByText(/Accepted revision/)).toBeVisible();
  }
});
