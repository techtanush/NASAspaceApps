import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { newMission, startRun, tab, prove, isMock, inspectHooks } from './support/workbench';

async function assertAccessible(page: Page, screen: string) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations.filter(row => ['critical', 'serious'].includes(row.impact || '')), screen).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${screen}: no page overflow`).toBe(true);
}

for (const width of [1440, 900, 390]) test(`UIX-07 S01–S12 accessible at ${width}`, async ({ page }) => {
  test.setTimeout(240000);
  await page.setViewportSize({ width, height: 900 });
  await page.goto('/'); await expect(page.getByTestId('btn-new-mission')).toBeVisible(); await assertAccessible(page, 'S01');
  await page.getByTestId('btn-new-mission').click(); await assertAccessible(page, 'S02');
  await page.goto('/rovers'); await expect(page.getByTestId('rover-form')).toBeVisible(); await assertAccessible(page, 'S03');
  await newMission(page); await assertAccessible(page, 'S04');
  await page.getByTestId('btn-start-run').click();
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'AWAITING_REVIEW', { timeout: isMock() ? 10000 : 180000 });
  for (const [screen, name] of [['S05', 'target'], ['S06', 'analogs'], ['S07', 'qualification'], ['S08', 'compatibility'], ['S09', 'portfolio'], ['S10', 'test-lab']]) {
    await tab(page, name);
    if (name === 'compatibility') await expect(page.getByTestId('compat-row').first()).toBeVisible();
    await inspectHooks(page);
    await assertAccessible(page, screen);
  }
  await prove(page); await assertAccessible(page, 'S11');
  await tab(page, 'passport'); await assertAccessible(page, 'S12');
});

test('UIX-07 keyboard focus, help, reduced motion and text spacing', async ({ page }) => {
  test.setTimeout(180000);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await startRun(page); await tab(page, 'qualification');
  await page.locator('[data-testid=qual-cell] summary').first().click();
  const evidence = page.getByTestId('evidence-link').first();
  await evidence.focus(); await page.keyboard.press('Enter');
  await expect(page.getByTestId('evidence-drawer')).toBeVisible(); await inspectHooks(page);
  await page.keyboard.press('Escape'); await expect(evidence).toBeFocused();
  await page.keyboard.press('?'); await expect(page.getByTestId('shortcut-help')).toBeVisible(); await inspectHooks(page);
  for (const key of ['/', '[', ']', 'e', 'o', '?', 'Esc']) await expect(page.getByTestId('shortcut-help')).toContainText(key);
  await page.keyboard.press('Escape');
  await page.addStyleTag({ content: '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await prove(page);
  const playback = page.getByTestId('route-playback'); await expect(playback).toBeVisible();
  await expect(playback.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await expect(playback.getByRole('button', { name: 'Pause', exact: true })).toHaveCount(0);
  const durations = await page.evaluate(() => [...document.querySelectorAll('*')].flatMap(node => {
    const style = getComputedStyle(node); return [...style.transitionDuration.split(','), ...style.animationDuration.split(',')].map(value => parseFloat(value));
  }));
  expect(durations.every(duration => duration <= 0.001)).toBe(true);
});
