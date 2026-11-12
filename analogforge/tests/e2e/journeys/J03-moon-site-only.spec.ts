import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { startRun, tab, prove, api } from '../support/workbench';
import { assertAuditMatches, type S } from '../support/journeyChecks';

test('J03 Moon site-only keeps unknown thermal, natural gaps and complete exports', async ({ page }) => {
  const runId = await startRun(page, { moon: true, rover: null });
  await tab(page, 'target');
  await expect(page.getByTestId('planetary-panel')).toHaveAttribute('data-body', 'MOON');
  await tab(page, 'qualification');
  for (const id of ['R-THERMAL', 'R-GRAVITY', 'R-VACUUM']) await expect(page.locator(`[data-testid=qual-cell][data-requirement-id=${id}]`).first()).toHaveAttribute('data-status', id === 'R-THERMAL' ? 'UNKNOWN' : 'GAP');
  await tab(page, 'test-lab');
  await expect(page.getByTestId('btn-prove-it')).toHaveAttribute('data-enabled', 'false');
  await expect(page.getByTestId('prove-it-disabled-reason')).toContainText(/rover/i);
  await expect(page.getByTestId('run-state-banner')).toContainText('Not run');
  // candidate_id is a required query parameter (frozen OpenAPI); without it the platform rightly answers 422.
  const firstCandidate = (await api<{ items: { id: string }[] }>(page, `/candidates?run_id=${runId}&limit=1`)).body.items[0]!.id;
  const compat = await api<{ error: { code: string } }>(page, `/compatibility?run_id=${runId}&candidate_id=${firstCandidate}`);
  expect(compat.status).toBe(409); expect(compat.body.error.code).toBe('ROVER_REQUIRED');
  await expect.poll(async () => (await api<S['RunSnapshot']>(page, `/runs/${runId}`)).body.passport_id).not.toBeNull();
  await tab(page, 'passport');
  await expect(page.getByTestId('assurance-badge')).toHaveAttribute('data-publication', 'LIMITED');
  await expect(page.getByTestId('passport-view')).toContainText('No rover supplied');
  await assertAuditMatches(page, runId);
  for (const format of ['html', 'json']) {
    const download = page.waitForEvent('download');
    await page.locator(`[data-testid=export-btn][data-format=${format}]`).click();
    const bytes = await readFile((await (await download).path())!);
    if (format === 'html') expect(bytes.toString()).toContain('No rover supplied — site qualification only');
    else expect(JSON.parse(bytes.toString()).bundle.not_run_reason).toBe('No rover supplied — site qualification only');
  }
});

