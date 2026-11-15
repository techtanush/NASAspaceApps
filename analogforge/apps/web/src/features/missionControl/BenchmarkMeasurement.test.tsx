import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import type { BenchmarkRow } from '../../api/visualization';
import seed from '../../mock/fixtures/seed.json';
import { BenchmarkMeasurement } from './BenchmarkMeasurement';

const row = { requirement: { ...seed.missionPresets.MARS.requirements[0], label: 'Slope comparison', operator: 'LTE', lower: null, upper: 5, unit: 'deg' }, measurement: { value: 0, unit: 'deg', support_scale_m: 500, comparison_evidence_id: 'selected-site-evidence', receipt_id: 'selected-site-receipt', reason: '' } } as BenchmarkRow;
it('plots a real zero against the accepted limit and retains its exact receipt provenance', () => {
  const { container } = render(<BenchmarkMeasurement row={row}/>);
  expect(screen.getByRole('img', { name: /Slope comparison: measured 0 deg/ })).toBeVisible();
  expect(screen.getByTestId('benchmark-measurement-chart')).toHaveAttribute('data-evidence-id', 'selected-site-evidence');
  expect(container.querySelectorAll('circle')).toHaveLength(1);
  expect(container.querySelector('circle')).toHaveAttribute('cx', '34');
  expect(container.querySelectorAll('.mc-measurement-limit')).toHaveLength(1);
  expect(screen.getByText('500 m comparison support')).toBeVisible();
});
it('renders no invented graph when a measurement is unknown', () => {
  const { container } = render(<BenchmarkMeasurement row={{ ...row, measurement: { ...row.measurement, value: null, reason: 'No covered samples' } }}/>);
  expect(container.querySelector('svg')).toBeNull();
});

it('keeps simple chart labels concise while technical labels and plotted evidence stay exact', () => {
  const measured = { ...row, measurement: { ...row.measurement, value: 4.506562500000001 } };
  const original = JSON.stringify(measured);
  const { container, rerender } = render(<BenchmarkMeasurement row={measured} simplified/>);
  expect(screen.getByRole('img', { name: /measured 4.507 deg/ })).toBeVisible();
  const position = container.querySelector('circle')!.getAttribute('cx');
  rerender(<BenchmarkMeasurement row={measured}/>);
  expect(screen.getByRole('img', { name: /measured 4.506562500000001 deg/ })).toBeVisible();
  expect(container.querySelector('circle')).toHaveAttribute('cx', position);
  expect(JSON.stringify(measured)).toBe(original);
});


it('changes fraction labels to percentages while preserving the measured position and provenance', () => {
  const fractional = { ...row, requirement: { ...row.requirement, operator:'GTE', lower:0.05, upper:null, unit:'fraction' }, measurement: { ...row.measurement, value:0.002, unit:'fraction' } } as BenchmarkRow;
  const original = JSON.stringify(fractional);
  const { container, rerender } = render(<BenchmarkMeasurement row={fractional} simplified/>);
  expect(screen.getByRole('img', { name:/measured 0.2%.*at least 5%/ })).toBeVisible();
  const position = container.querySelector('circle')!.getAttribute('cx');
  rerender(<BenchmarkMeasurement row={fractional}/>);
  expect(screen.getByRole('img', { name:/measured 0.002 fraction.*at least 0.05 fraction/ })).toBeVisible();
  expect(container.querySelector('circle')).toHaveAttribute('cx',position);
  expect(screen.getByTestId('benchmark-measurement-chart')).toHaveAttribute('data-evidence-id','selected-site-evidence');
  expect(JSON.stringify(fractional)).toBe(original);
});
