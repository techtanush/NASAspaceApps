import { expect, test } from '@playwright/test';
import { startRun, tab, prove } from '../support/workbench';
import { persistedResults, assertAuditMatches, downloadPassportJson } from '../support/journeyChecks';

test('J06 no energy calibration is inconclusive and never zero', async ({ page }) => {
  const runId = await startRun(page, { rover: 'practice-no-energy-model' });
  await prove(page, 'Practice grid-r0c0');
  await expect(page.getByTestId('attempt-row').last()).toHaveAttribute('data-outcome', 'INCONCLUSIVE');
  await expect(page.getByTestId('failure-category').last()).toHaveAttribute('data-category', 'DATA');
  await expect(page.getByTestId('unknown-value').first()).toHaveText('Unknown');
  const persisted = await persistedResults(page, runId);
  for (const result of persisted.results) {
    expect(result.metrics.find(row => row.metric_id === 'energy_conservative_wh')?.value).toBeNull();
    expect(result.metrics.find(row => row.metric_id === 'reserve_pct')?.value).toBeNull();
  }
  const latest = persisted.results.at(-1)!;
  expect(latest.metrics.find(row => row.metric_id === 'energy_conservative_wh')?.value).toBeNull();
  expect(latest.metrics.find(row => row.metric_id === 'reserve_pct')?.value).toBeNull();
  const playback = page.getByTestId('route-playback');
  await expect(playback.locator('dt', { hasText: 'Modeled energy' }).locator('+ dd')).toHaveText('Unknown');
  await expect(playback.locator('dt', { hasText: 'Reserve' }).locator('+ dd')).toHaveText('Unknown');
  const energyCells = playback.getByRole('table').locator('tbody tr td:last-child');
  expect(await energyCells.allTextContents()).toEqual(['Unknown', 'Unknown', 'Unknown']);
  await tab(page, 'passport'); await assertAuditMatches(page, runId);
  const exported = await downloadPassportJson(page);
  expect(exported.bundle.attempts.at(-1)?.result.outcome).toBe('INCONCLUSIVE');
  for (const attempt of exported.bundle.attempts) expect(attempt.result.metrics.find(row => row.metric_id === 'energy_conservative_wh')?.value).toBeNull();
});

