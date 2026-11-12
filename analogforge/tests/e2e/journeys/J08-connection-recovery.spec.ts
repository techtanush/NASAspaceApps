import { expect, test } from '@playwright/test';
import { startRun, tab, prove, api, isMock, inspectHooks } from '../support/workbench';
import { persistedResults, verificationTimeout, type S } from '../support/journeyChecks';

test('J08 offline reconnect resynchronizes with strictly unique persisted events', async ({ page, context }) => {
  const id = await startRun(page);
  await context.setOffline(true);
  await expect(page.getByTestId('connection-indicator')).toHaveAttribute('data-connection', 'paused');
  await page.waitForTimeout(6000); // Deliberate offline interval required by J08.
  await context.setOffline(false);
  await expect(page.getByTestId('connection-indicator')).toHaveAttribute('data-connection', 'connected');
  await page.keyboard.press('o');
  await expect(page.getByTestId('operation-row').first()).toBeVisible();
  await inspectHooks(page);
  const seq = await page.getByTestId('operation-row').evaluateAll(elements => elements.map(node => Number(node.getAttribute('data-seq'))));
  expect(seq.length).toBeGreaterThan(0); expect(new Set(seq).size).toBe(seq.length);
  expect(seq.every((value, index) => index === 0 || value > seq[index - 1]!)).toBe(true);
  await page.keyboard.press('Escape');
  const snapshot = await api<S['RunSnapshot']>(page, `/runs/${id}`);
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', snapshot.body.state);
});


test('J08b reload during verification resumes immutable attempts without duplication', async ({ page }) => {
  if (isMock()) await page.clock.install();
  const runId = await startRun(page);
  await tab(page, 'analogs');
  await page.locator('[data-testid=btn-select-candidate][data-candidate-name="Practice grid-r0c1"]').click();
  await expect(page.locator('[data-testid=candidate-row][data-candidate-name="Practice grid-r0c1"]')).toHaveAttribute('data-selected', 'true');
  await tab(page, 'test-lab');
  if (isMock()) await page.clock.pauseAt(new Date());
  const accepted = page.waitForResponse(response => response.url().endsWith(`/runs/${runId}/actions`) && response.request().method() === 'POST' && response.request().postDataJSON()?.action_type === 'PROVE_IT');
  await page.getByTestId('btn-prove-it').click();
  expect((await accepted).status()).toBe(202);
  if (isMock()) {
    await page.clock.runFor(850);
    // Flush UI notification frames while staying before the second immutable attempt at 1200 ms.
    for (let frame = 0; frame < 6 && await page.locator('[data-testid=attempt-row][data-attempt-number="1"]').count() === 0; frame++) await page.clock.runFor(50);
  }
  await expect(page.locator('[data-testid=attempt-row][data-attempt-number="1"]')).toBeVisible();
  const first = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  expect(first.body.test_result_ids.length).toBe(1);
  // Mock time is paused exactly between attempts; a real worker may still be closing attempt 1 (VERIFYING/DIAGNOSING)
  // or already designing attempt 2. Either way the reload happens mid-run with exactly one committed result.
  if (isMock()) expect(first.body.state).toBe('REPLANNING');
  else expect(['VERIFYING', 'DIAGNOSING', 'REPLANNING', 'DESIGNING_TEST']).toContain(first.body.state);
  await page.reload();
  if (isMock()) await page.clock.resume();
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'COMPLETED', { timeout: verificationTimeout() });
  await expect(page.getByTestId('attempt-row')).toHaveCount(3);
  const persisted = await persistedResults(page, runId);
  expect(new Set(persisted.snapshot.test_ids).size).toBe(3);
  expect(new Set(persisted.snapshot.test_result_ids).size).toBe(3);
  expect(persisted.snapshot.test_result_ids[0]).toBe(first.body.test_result_ids[0]);
  expect(persisted.results.map(result => result.outcome)).toEqual(['FAIL', 'FAIL', 'PASS']);
});

