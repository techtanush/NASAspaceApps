import { expect, test } from '@playwright/test';
import { newMission, api, inspectHooks } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J13 live without credentials fails without creating a run or scripted fallback', async ({ page }) => {
  await newMission(page, { mode: 'live' });
  const before = await api<S['ListRunSnapshot']>(page, '/runs');
  await page.getByTestId('btn-start-run').click();
  await expect(page.locator('[data-testid=error-panel][data-error-code=PROVIDER_AUTH_FAILED]')).toBeVisible();
  await expect(page.locator('[data-testid=remediation-hint][data-dependency=OPENAI_API_KEY]')).toBeVisible();
  await inspectHooks(page);
  const after = await api<S['ListRunSnapshot']>(page, '/runs');
  expect(after.body.items).toHaveLength(before.body.items.length);
});
