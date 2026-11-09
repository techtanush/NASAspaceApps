import { expect, test } from '@playwright/test';
import { startRun, tab, api, inspectHooks } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J07 cancellation retains committed evidence and cannot later pass', async ({ page }) => {
  const runId = await startRun(page);
  await page.keyboard.press('o');
  await expect(page.getByTestId('operation-row').first()).toBeVisible();
  await inspectHooks(page);
  await page.keyboard.press('Escape');
  await page.getByTestId('btn-cancel-run').click();
  const dialog = page.getByRole('dialog');
  if (await dialog.isVisible()) await dialog.getByRole('button', { name: /cancel run|confirm/i }).click();
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'CANCELLED', { timeout: 10000 });
  await tab(page, 'qualification');
  await page.locator('[data-testid=qual-cell] summary').first().click();
  await page.getByTestId('evidence-link').first().click();
  await expect(page.getByTestId('evidence-drawer')).toBeVisible();
  await inspectHooks(page);
  await page.keyboard.press('Escape');
  await tab(page, 'passport');
  await expect(page.getByTestId('export-btn')).toHaveCount(0);
  const current = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  expect(current.body.state).toBe('CANCELLED'); expect(current.body.passport_id).toBeNull();
  await page.reload();
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'CANCELLED');
  await expect(page.locator('[data-testid=attempt-row][data-outcome=PASS]')).toHaveCount(0);
});

