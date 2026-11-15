import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Welcome } from './Welcome';

const state = vi.hoisted(() => ({ responses: new Map<string, unknown>(), reads: [] as [string, string][] }));
vi.mock('../../api/hooks/useApi', () => ({ useApi: (workspace: string, path: string) => { state.reads.push([workspace, path]); return { data: state.responses.get(path) }; } }));
vi.mock('../../app/WorkspaceContext', () => ({ useWorkspace: () => 'workspace' }));
vi.mock('./state', () => ({ useMissionControl: () => ({ reset: () => {} }) }));
vi.mock('./StageShell', () => ({ useScene: () => {} }));

beforeEach(() => {
  state.responses.clear(); state.reads.length = 0;
  state.responses.set('/runs?limit=4', { items: [{ id: '12345678-run', mission_revision_id: 'mission-revision', workspace_id: 'workspace', state: 'AWAITING_REVIEW', mode: 'live' }] });
});

it('resumes by the pinned mission name while retaining the exact run destination', () => {
  state.responses.set('/mission-revisions/mission-revision', { id: 'mission-revision', workspace_id: 'workspace', name: 'Gale regional terrain rehearsal' });
  render(<MemoryRouter><Welcome/></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Gale regional terrain rehearsal/ })).toHaveAttribute('href', '/runs/12345678-run/tour');
  expect(state.reads).toContainEqual(['workspace', '/mission-revisions/mission-revision']);
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
