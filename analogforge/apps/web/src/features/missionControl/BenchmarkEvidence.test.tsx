import { render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import type { components } from '../../generated/schema';
import seed from '../../mock/fixtures/seed.json';
import { useSiteBenchmarks, type BenchmarkRow } from '../../api/visualization';
import { BenchmarkEvidence } from './BenchmarkEvidence';
import { buildSites } from './tour';

type S = components['schemas'];
vi.mock('../../api/visualization', () => ({ useSiteBenchmarks: vi.fn() }));
const candidate = seed.candidates[0] as S['EarthAnalogCandidate'];
const requirement = { ...seed.missionPresets.MARS.requirements[0], label: 'Accepted slope limit', operator: 'LTE', lower: null, upper: 5, unit: 'deg' } as S['Requirement'];
const contract = { requirements: [requirement] } as S['MissionTestContract'];
const run = { run_id: seed.runId, candidate_ids: [candidate.id] } as S['RunSnapshot'];
const site = buildSites([candidate], [requirement], [])[0]!;
const row: BenchmarkRow = { requirement, qualification_id: null, status: 'UNKNOWN', explanation: 'No covered samples.', measurement: { value: null, unit: null, support_scale_m: null, comparison_evidence_id: null, receipt_id: null, reason: 'No covered samples.' }, test_result_ids: [] };
const result = (measurement = row.measurement) => ({ data: { requirements: [{ ...row, measurement }], test_result_ids: [] }, available: true, discovering: false, isPending: false, error: null, refetch: vi.fn() }) as unknown as ReturnType<typeof useSiteBenchmarks>;
beforeEach(() => vi.mocked(useSiteBenchmarks).mockReturnValue(result()));
it('keeps unknown benchmarks visible without plotting missing samples', () => {
  render(<BenchmarkEvidence run={run} contract={contract} site={site}/>);
  expect(useSiteBenchmarks).toHaveBeenCalledWith(run, contract, candidate.id);
  expect(screen.getByTestId('benchmark-row')).toHaveAttribute('data-status', 'UNKNOWN');
  expect(screen.getByText('Measurement unavailable. No covered samples.')).toBeVisible();
  expect(screen.queryByTestId('benchmark-measurement-chart')).toBeNull();
});
it('shows a verified numeric measurement and preserves evidence behind its disclosure', () => {
  vi.mocked(useSiteBenchmarks).mockReturnValue(result({ value: 0, unit: 'deg', support_scale_m: 500, comparison_evidence_id: 'same-site-evidence', receipt_id: 'same-site-receipt', reason: '' }));
  render(<BenchmarkEvidence run={run} contract={contract} site={site}/>);
  expect(screen.getByRole('img', { name: /Accepted slope limit: measured 0 deg/ })).toBeVisible();
  expect(screen.getByTestId('benchmark-measurement-chart')).toHaveAttribute('data-evidence-id', 'same-site-evidence');
  expect(screen.getByText('Evidence and method').closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText(/Comparison evidence: same-site-evidence/)).toHaveTextContent('Receipt: same-site-receipt');
});
it('discards stale numeric data when the candidate projection is rejected', () => {
  vi.mocked(useSiteBenchmarks).mockReturnValue({ ...result({ ...row.measurement, value: 4 }), error: new Error('Selected-site identity mismatch') } as ReturnType<typeof useSiteBenchmarks>);
  render(<BenchmarkEvidence run={run} contract={contract} site={site}/>);
  expect(screen.getByTestId('error-panel')).toBeVisible(); expect(screen.queryByTestId('benchmark-measurement-chart')).toBeNull();
});
