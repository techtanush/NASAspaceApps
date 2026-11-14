import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { newMission, api, inspectHooks, isMock } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J13 live without credentials fails without creating a run or scripted fallback', async ({ page }) => {
  const root = resolve(import.meta.dirname, '../../..');
  const rehearsal = (action: string) => execFileSync(process.env.ANALOGFORGE_CLI || resolve(root, '.venv/bin/analogforge'),
    ['rehearsal', action, '--json'], { cwd: root, env: { ...process.env, ANALOGFORGE_TEST_HOOKS: '1', ANALOGFORGE_ALLOW_TEST_HARNESS_PROVIDER: '1' }, stdio: 'pipe' });
  if (!isMock()) rehearsal('bind-live-slot');
  try {
  await newMission(page, { mode: 'live', ...(!isMock() ? { scenario: 'live-hackathon-v1' } : {}) });
  const before = await api<S['ListRunSnapshot']>(page, '/runs');
  await page.getByTestId('btn-start-run').click();
  await expect(page.locator('[data-testid=error-panel][data-error-code=PROVIDER_AUTH_FAILED]')).toBeVisible();
  await expect(page.locator('[data-testid=remediation-hint][data-dependency=OPENAI_API_KEY]')).toBeVisible();
  await inspectHooks(page);
  const after = await api<S['ListRunSnapshot']>(page, '/runs');
  expect(after.body.items).toHaveLength(before.body.items.length);
  } finally {
    if (!isMock()) rehearsal('restore-live-slot');
  }
});
