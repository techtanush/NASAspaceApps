import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Welcome } from './Welcome';

const state = vi.hoisted(() => ({ responses: new Map<string, unknown>(), reads: [] as [string, string][], enabled: [] as [string, boolean][], session: undefined as { workspaceId: string; role: 'OWNER'; authMode: 'local' } | undefined, reset: vi.fn() }));
vi.mock('../../api/hooks/useApi', () => ({ useApi: (workspace: string, path: string, enabled = true) => { state.reads.push([workspace, path]); state.enabled.push([path, enabled]); return { data: state.responses.get(path) }; } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace', useWorkspaceSession: () => state.session }));
vi.mock('./state', () => ({ useMissionControl: () => ({ reset: state.reset }) }));
vi.mock('./StageShell', () => ({ useScene: () => {} }));
vi.mock('../../maps/GlobeStage', () => ({ GlobeStage: () => <div aria-label="Earth globe"/> }));

beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', class {
    observe() {} unobserve() {} disconnect() {}
  });
  state.responses.clear(); state.reads.length = 0; state.enabled.length = 0; state.reset.mockClear();
  state.session = { workspaceId: 'workspace', role: 'OWNER', authMode: 'local' };
  state.responses.set('/workspace/recent-runs?limit=4', { items: [{ id: '12345678-run', mission_revision_id: 'mission-revision', workspace_id: 'workspace', state: 'AWAITING_REVIEW', mode: 'live' }] });
});

it('keeps the public introduction readable without a session and never reads or displays private history', () => {
  state.session = undefined;
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  expect(screen.getByRole('heading', { name: 'A world away. Tested closer to home.' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Enter AnalogForge' })).toHaveAttribute('href', '/start/place');
  expect(state.enabled).toContainEqual(['/workspace/recent-runs?limit=4', false]);
  expect(state.reads).not.toContainEqual(['workspace', '/mission-revisions/mission-revision']);
  expect(screen.queryByTestId('recent-investigations')).not.toBeInTheDocument();
});

it('enters the mission directly without account controls and starts a fresh investigation', () => {
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  const entry = screen.getByRole('link', { name: 'Enter AnalogForge' });
  expect(entry).toHaveAttribute('href', '/start/place');
  fireEvent.click(entry);
  expect(state.reset).toHaveBeenCalledOnce();
  expect(screen.getByText('Open exploration. No account required.')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /sign in|sign up|log in|log out|sign out/i })).not.toBeInTheDocument();
});

it('explains the complete investigation and preserves a direct entry after the scroll sections', () => {
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  expect(screen.getByRole('link', { name: 'Explore the mission' })).toHaveAttribute('href', '#how-it-works');
  expect(screen.getByRole('list', { name: 'How it works' }).children).toHaveLength(4);
  expect(screen.getByRole('heading', { name: /Know what Earth can prove/ })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Start your investigation' })).toHaveAttribute('href', '/start/place');
  expect(screen.getByRole('link', { name: 'Open mission library' })).toHaveAttribute('href', '/workbench');
});

it('resumes by the pinned mission name while retaining the exact run destination', () => {
  state.responses.set('/mission-revisions/mission-revision', { id: 'mission-revision', workspace_id: 'workspace', name: 'Gale regional terrain rehearsal' });
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Gale regional terrain rehearsal/ })).toHaveAttribute('href', '/runs/12345678-run/tour');
  expect(state.reads).toContainEqual(['workspace', '/mission-revisions/mission-revision']);
  expect(state.reads).toContainEqual(['workspace', '/workspace/recent-runs?limit=4']);
  expect(state.reads).not.toContainEqual(['workspace', '/runs?limit=4']);
});

it.each([
  undefined,
  { id: 'another-revision', workspace_id: 'workspace', name: 'Unrelated mission' },
  { id: 'mission-revision', workspace_id: 'another-workspace', name: 'Private mission' },
])('keeps a usable run link without borrowing an unavailable or foreign mission label', contract => {
  state.responses.set('/mission-revisions/mission-revision', contract);
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Investigation 12345678/ })).toHaveAttribute('href', '/runs/12345678-run/tour');
  expect(screen.queryByText(/Unrelated mission|Private mission/)).not.toBeInTheDocument();
});
