import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { startRun, tab, prove, api, isMock } from './support/workbench';
import type { components } from '../../apps/web/src/generated/schema';
type S = components['schemas'];

test('UIX-11 WebGL failure preserves list, matrix, benchmarks and exports', async ({ page }) => {
  test.setTimeout(180000);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind: string, ...args: unknown[]) {
      if (kind.startsWith('webgl')) return null;
      return original.apply(this, [kind, ...args] as Parameters<typeof original>);
    } as typeof original;
  });
  const runId = await startRun(page);
  await tab(page, 'analogs');
  await expect(page.getByTestId('candidate-list')).toBeVisible();
  await expect(page.getByTestId('candidate-row')).toHaveCount(6);
  await expect(page.getByText(/Map unavailable/).first()).toBeVisible();
  await tab(page, 'qualification'); await expect(page.getByTestId('qualification-matrix')).toBeVisible();
  await prove(page); await expect(page.getByTestId('benchmark-row').first()).toBeVisible();
  await expect(page.getByTestId('attempt-row')).toHaveCount(3);
  await tab(page, 'passport'); await expect(page.getByTestId('export-btn')).toHaveCount(3);
  const downloading = page.waitForEvent('download');
  await page.locator('[data-testid=export-btn][data-format=json]').click();
  const exported = JSON.parse((await readFile((await (await downloading).path())!)).toString());
  expect(exported.bundle.attempts).toHaveLength(3);
  if (!isMock()) {
    const snapshot = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
    expect(snapshot.body.test_result_ids).toHaveLength(3);
    expect(exported.bundle.passport.id).toBe(snapshot.body.passport_id);
  }
});
