import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { components } from '../../generated/schema';
import rover from '../../../../../tests/fixtures/kit/rovers/ares-1.json';
import { fetchRoverProfiles } from '../rovers/roverProfiles';
import { RoverStep } from './RoverStep';
import { api } from '../../api/client';
import example from '../../../../../config/presets/rovers/ares-1.json';

const update = vi.hoisted(() => vi.fn());
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace' }));
vi.mock('../rovers/roverProfiles', () => ({ fetchRoverProfiles: vi.fn() }));
vi.mock('../rovers/RoverEditor', () => ({ RoverEditor: () => null }));
vi.mock('./state', () => ({ useMissionControl: () => ({ plan: { confirmed: true, lat: 0, lng: 0, body: 'MARS', objective: 'Traverse', noRover: false, roverRevisionId: null }, update, box: { ok: true, bbox: [0, 0, 1, 1] } }) }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <p>{children}</p>, Panel: ({ children, footer }: { children: ReactNode; footer: ReactNode }) => <main>{children}{footer}</main> }));

it('offers the documented example on a fresh workspace without silently creating a rover', async () => {
  vi.mocked(fetchRoverProfiles).mockResolvedValue({items:[],next_cursor:null});
  const save=vi.spyOn(api,'post').mockResolvedValue({...rover,id:'saved-example',name:example.name});
  const cache = new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={cache}><MemoryRouter><RoverStep/></MemoryRouter></QueryClientProvider>);
  const button=await screen.findByRole('button',{name:'Use ARES-1 example rover'});
  expect(save).not.toHaveBeenCalled();expect(screen.getByText(/documented illustrative specifications/)).toBeVisible();
  fireEvent.click(button);
  await screen.findByRole('button',{name:'Use ARES-1 example rover'});
  expect(save).toHaveBeenCalledWith('/rovers',example,expect.any(Object));
  expect(update).toHaveBeenCalledWith({roverRevisionId:'saved-example',roverName:'ARES-1',noRover:false});
  save.mockRestore();
});

it('distinguishes independent same-name rovers and selects their exact latest revisions', async () => {
  const profile = (id: string, roverId: string, revision: number, name = 'ARES-1') => ({ ...rover, id, rover_id: roverId, workspace_id: 'workspace', revision, name, created_at: '2026-11-14T00:00:00Z' }) as components['schemas']['RoverProfile'];
  vi.mocked(fetchRoverProfiles).mockResolvedValue({ items: [profile('old-revision', 'aaaaaaaa-1111', 1), profile('latest-revision', 'aaaaaaaa-1111', 2), profile('other-revision', 'bbbbbbbb-2222', 1), profile('unique-revision', 'cccccccc-3333', 1, 'Field rover')], next_cursor: null });
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter><RoverStep/></MemoryRouter></QueryClientProvider>);
  const options = await screen.findAllByTestId('rover-option');
  expect(options).toHaveLength(3);
  const first = options.find(option => option.dataset.roverId === 'aaaaaaaa-1111')!;
  const second = options.find(option => option.dataset.roverId === 'bbbbbbbb-2222')!;
  expect(first).toHaveAttribute('data-rover-revision-id', 'latest-revision');
  expect(within(first).getByText('Rover ID aaaaaaaa')).toHaveAttribute('title', 'aaaaaaaa-1111');
  expect(within(second).getByText('Rover ID bbbbbbbb')).toBeVisible();
  expect(within(options.find(option => option.dataset.roverId === 'cccccccc-3333')!).queryByText(/Rover ID/)).not.toBeInTheDocument();
  fireEvent.click(second);
  expect(update).toHaveBeenLastCalledWith({ roverRevisionId: 'other-revision', roverName: 'ARES-1', noRover: false });
  fireEvent.click(first);
  expect(update).toHaveBeenLastCalledWith({ roverRevisionId: 'latest-revision', roverName: 'ARES-1', noRover: false });
});
