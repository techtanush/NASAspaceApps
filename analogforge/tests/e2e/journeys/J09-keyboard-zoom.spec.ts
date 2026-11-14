import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { keyboardMission } from '../support/journeyChecks';

test('J09 keyboard-only authoring and qualification work at 390px', async ({ page }) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 390, height: 844 });
  await keyboardMission(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const audit = await new AxeBuilder({ page }).analyze();
  expect(audit.violations.filter(row => ['critical', 'serious'].includes(row.impact || ''))).toEqual([]);
});


test('J09b 200 percent zoom reflow retains primary actions and keyboard focus', async ({ browser }) => {
  test.setTimeout(180000);
  // A 1440px desktop at 200% zoom exposes a 720 CSS-pixel layout with doubled backing scale.
  const context = await browser.newContext({ viewport: { width: 720, height: 450 }, deviceScaleFactor: 2, baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5176' });
  const page = await context.newPage();
  try {
    // This extra context must own focus for native keyboard-triggered file selection.
    await page.bringToFront();
    await expect.poll(()=>page.evaluate(()=>document.hasFocus())).toBe(true);
    await keyboardMission(page);
    expect(await page.evaluate(() => devicePixelRatio)).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.locator('main h1')).toBeVisible();
  } finally { await context.close(); }
});

