import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { MissionControlProvider } from './state';
import { StageShell, useScene } from './StageShell';
import type { GlobeScene } from '../../maps/GlobeStage';

vi.mock('../../maps/GlobeStage', () => ({ GlobeStage: ({onSurfaceDetail}:{onSurfaceDetail?:()=>void}) => <button type="button" disabled={!onSurfaceDetail} onClick={onSurfaceDetail}>Close globe zoom</button> }));
vi.mock('../../app/WorkspaceContext', () => ({useWorkspaceSession:()=>({authMode:'local',role:'OWNER'})}));
afterEach(cleanup);

function Scene({scene}:{scene:GlobeScene}) { useScene(scene); const location=useLocation(); return <output aria-label="Current route">{location.pathname}{location.search}</output>; }
function mount(path:string,scene:GlobeScene) {
  render(<MemoryRouter initialEntries={[path]}><MissionControlProvider><Routes><Route element={<StageShell/>}><Route path="*" element={<Scene scene={scene}/>}/></Route></Routes></MissionControlProvider></MemoryRouter>);
}

it('hands close Earth zoom to the exact selected site while preserving unrelated query state', async () => {
  mount('/runs/run-a/tour?site=old&keep=value',{body:'EARTH',selectedMarker:'candidate-current'});
  await waitFor(()=>expect(screen.getByRole('button',{name:'Close globe zoom'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Close globe zoom'}));
  expect(screen.getByLabelText('Current route')).toHaveTextContent('/runs/run-a/tour?site=candidate-current&keep=value&view=regional');
  expect(screen.getByRole('button',{name:'Close globe zoom'})).toBeDisabled();
});

it('opens a real planetary surface view only when a target region has been selected', async () => {
  mount('/start/place',{body:'MOON',box:[23,0,24,1]});
  await waitFor(()=>expect(screen.getByRole('button',{name:'Close globe zoom'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Close globe zoom'}));
  expect(screen.getByLabelText('Current route')).toHaveTextContent('/start/place?view=target');
});

it.each([
  ['/runs/run-a/tour',{body:'EARTH'}],
  ['/start/place',{body:'MARS'}],
  ['/',{body:'EARTH',selectedMarker:'candidate'}],
  ['/runs/run-a/tour?view=target',{body:'EARTH',selectedMarker:'candidate'}],
] as [string,GlobeScene][])('does not fabricate a detail target for %s',async(path,scene)=>{
  mount(path,scene);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Close globe zoom'})).toBeDisabled());
  expect(screen.getByLabelText('Current route')).toHaveTextContent(path);
});
