import { expect, test, type Locator } from '@playwright/test';
import { startRun, tab, prove } from '../support/workbench';
import { persistedResults, assertAuditMatches, type S } from '../support/journeyChecks';

test('J02 graph regression preserves exact independent graph oracle', async ({ page }) => {
  const runId = await startRun(page, { scenario: 'synthetic-graph-regression-v1' });
  await prove(page, 'Practice grid-r0c0');
  await expect(page.getByTestId('attempt-row')).toHaveCount(2);
  const first = page.locator('[data-testid=attempt-row][data-attempt-number="1"]');
  const second = page.locator('[data-testid=attempt-row][data-attempt-number="2"]');
  await expect(first).toHaveAttribute('data-outcome', 'FAIL');
  await expect(second).toHaveAttribute('data-outcome', 'PASS');
  const metricCell = (attempt: Locator, id: string) => attempt.locator('tr').filter({ has: page.getByRole('rowheader', { name: id, exact: true }) }).locator('td').first();
  await expect(metricCell(first, 'route_distance_m')).toHaveText(/120\s*m/);
  await expect(metricCell(first, 'energy_conservative_wh')).toHaveText(/26\.0\s*Wh/);
  await expect(metricCell(first, 'unique_exposure_m:R-EXPOSURE')).toHaveText(/0\s*m/);
  await expect(metricCell(second, 'route_distance_m')).toHaveText(/230\s*m/);
  await expect(metricCell(second, 'energy_conservative_wh')).toHaveText(/30\.0\s*Wh/);
  await expect(metricCell(second, 'unique_exposure_m:R-EXPOSURE')).toHaveText(/150\s*m/);
  const persisted = await persistedResults(page, runId);
  expect(persisted.results.map(result => result.outcome)).toEqual(['FAIL', 'PASS']);
  const metric = (result: S['TestResult'], id: string) => result.metrics.find(row => row.metric_id === id)?.value;
  expect(metric(persisted.results[0]!, 'route_distance_m')).toBe(120);
  expect(metric(persisted.results[0]!, 'energy_conservative_wh')).toBe(26);
  expect(metric(persisted.results[0]!, 'unique_exposure_m:R-EXPOSURE')).toBe(0);
  expect(metric(persisted.results[1]!, 'route_distance_m')).toBe(230);
  expect(metric(persisted.results[1]!, 'energy_conservative_wh')).toBe(30);
  expect(metric(persisted.results[1]!, 'unique_exposure_m:R-EXPOSURE')).toBe(150);
  await tab(page, 'passport');
  await expect(page.getByTestId('mode-badge').first()).toHaveAttribute('data-mode', 'synthetic');
  await assertAuditMatches(page, runId);
});

