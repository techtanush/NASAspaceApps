import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import bundle from '../../../../../tests/unit/passport_renderer/fixtures/bundles/positive.json';
import { PassportView } from './PassportView';

const state = vi.hoisted(() => ({ audit: {} as Record<string, unknown> }));
vi.mock('../../api/hooks/useApi', () => ({ useApi: (_workspace: string, path: string) => ({
  data: path.startsWith('/passports/') ? bundle.passport : bundle.rover,
  error: null, refetch: vi.fn(),
}) }));
vi.mock('../runs/RunContext', () => ({
  useRun: () => ({
    snapshot: { passport_id: bundle.passport.id, run_id: bundle.passport.run_id,
      workspace_id: bundle.passport.workspace_id, mode: bundle.mode, state: 'COMPLETED',
      revision: 1, mission_revision_id: bundle.mission.id, rover_revision_id: bundle.rover?.id,
      test_result_ids: bundle.attempts.map(attempt => attempt.result?.id) },
    contract: bundle.mission, qualifications: [], candidates: [],
  }),
  useOperationArtifact: () => ({ data: state.audit, error: null, refetch: vi.fn() }),
}));
vi.mock('../testLab/Attempts', () => ({
  Attempts: () => <p>Committed attempts</p>,
  useRunResults: () => ({ data: bundle.attempts.map(attempt => attempt.result), error: null, refetch: vi.fn() }),
}));

beforeEach(() => { state.audit = structuredClone(bundle.assurance); });

it('shows the permitted positive cover only for a matching valid audit', () => {
  render(<PassportView />);
  expect(screen.getByText('Qualified for these tests under these assumptions:')).toBeVisible();
  expect(screen.getByTestId('assurance-badge')).toHaveAttribute('data-publication', bundle.assurance.publication);
});

it.each([
  ['unrecognized publication', { publication: 'NOT_A_PUBLICATION' }],
  ['missing claims', { claims: [] }],
  ['wrong run', { run_id: '00000000-0000-4000-8000-000000000999' }],
  ['wrong workspace', { workspace_id: '00000000-0000-4000-8000-000000000999' }],
  ['promoted mode', { mode: 'live' }],
  ['missing report timestamp', { created_at: undefined }],
  ['invalid report timestamp', { created_at: '2026-99-99T25:00:00Z' }],
  ['malformed claims', { claims: [{}] }],
  ['non-array claims', { claims: 'qualified' }],
  ['missing limitations', { limitations: undefined }],
  ['wrong accepted rover', { rover_content_sha256: 'f'.repeat(64) }],
  ['wrong accepted mission', { mission_content_sha256: 'f'.repeat(64) }],
])('keeps a %s audit incomplete instead of presenting a qualified headline', (_name, change) => {
  state.audit = { ...state.audit, ...change };
  render(<PassportView />);
  expect(screen.getByTestId('assurance-badge')).toHaveAttribute('data-publication', 'INCOMPLETE');
  expect(screen.queryByText('Qualified for these tests under these assumptions:')).not.toBeInTheDocument();
  expect(screen.queryByTestId('export-btn')).not.toBeInTheDocument();
});
