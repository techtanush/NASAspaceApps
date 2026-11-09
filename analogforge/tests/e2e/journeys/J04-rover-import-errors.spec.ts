import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { api, fixture, inspectHooks } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J04 invalid imports preserve typed fields and never persist', async ({ page }) => {
  await page.goto('/missions/new');
  await page.getByTestId('input-mission-name').fill('Retained name');
  const before = await api<S['ListRoverProfile']>(page, '/rovers');
  await page.getByTestId('file-rover-import').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{broken') });
  await expect(page.getByTestId('error-panel')).toBeVisible();
  const good = JSON.parse(await readFile(fixture('rovers/ares-1.json'), 'utf8')); good.mass_kg = -3;
  await page.getByTestId('file-rover-import').setInputFiles({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(good)) });
  await expect(page.locator('[data-testid=rover-field-error][data-field=mass_kg]')).toBeVisible();
  await inspectHooks(page);
  const after = await api<S['ListRoverProfile']>(page, '/rovers');
  expect(after.body.items).toHaveLength(before.body.items.length);
  await expect(page.getByTestId('input-mission-name')).toHaveValue('Retained name');
});

