import { expect, type Locator, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { api, fixture, isMock } from './workbench';
import type { components } from '../../../apps/web/src/generated/schema';
export type S = components['schemas'];
export const runTimeout = () => isMock() ? 10000 : 180000;
export const verificationTimeout = () => isMock() ? 15000 : 240000;

export async function persistedResults(page: Page, runId: string) {
  const snapshot = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  expect(snapshot.status).toBe(200);
  const tests = await api<S['ListVerificationTest']>(page, `/tests?run_id=${runId}&limit=100`);
  expect(tests.status).toBe(200);
  const results = await Promise.all(snapshot.body.test_result_ids.map(async id => {
    const response = await api<S['TestResult']>(page, `/test-results/${id}`);
    expect(response.status).toBe(200);
    expect(response.body.run_id).toBe(runId);
    expect(tests.body.items.some(item => item.id === response.body.test_id)).toBe(true);
    if (!isMock()) {
      expect(response.body.evidence_ids.length).toBeGreaterThan(0);
      for (const evidenceId of response.body.evidence_ids) {
        const evidence = await api<S['EvidenceRecord']>(page, `/evidence/${evidenceId}`);
        expect(evidence.status).toBe(200);
        expect(evidence.body.run_id).toBe(runId);
        expect(evidence.body.artifact_sha256).toMatch(/^[a-f0-9]{64}$/);
      }
    }
    return response.body;
  }));
  if (!isMock()) {
    const actions = await api<S['ListAgentAction']>(page, `/agent-actions?run_id=${runId}&limit=100`);
    expect(actions.status).toBe(200);
    expect(actions.body.items.length).toBeGreaterThan(0);
    for (const action of actions.body.items.filter(item => item.tool_receipt_id)) {
      const receipt = await api<S['ToolReceipt']>(page, `/tool-receipts/${action.tool_receipt_id}`);
      expect(receipt.status).toBe(200);
      expect(receipt.body.run_id).toBe(runId);
    }
  }
  return { snapshot: snapshot.body, tests: tests.body.items, results };
}

export async function assertAuditMatches(page: Page, runId: string) {
  const snapshot = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  expect(snapshot.body.passport_id).not.toBeNull();
  const passport = await api<S['AnalogPassport']>(page, `/passports/${snapshot.body.passport_id}`);
  const evidence = await api<S['EvidenceRecord']>(page, `/evidence/${passport.body.assurance_evidence_id}`);
  expect(evidence.status).toBe(200);
  const artifact = await api<{ publication: string; claims: { permitted_statement: string }[] }>(page, `/artifacts/${evidence.body.artifact_sha256}`);
  expect(artifact.status).toBe(200);
  await expect(page.getByTestId('assurance-badge')).toHaveAttribute('data-publication', artifact.body.publication);
  for (const claim of artifact.body.claims) await expect(page.getByTestId('passport-view')).toContainText(claim.permitted_statement);
  return { passport: passport.body, assurance: artifact.body };
}

export async function downloadPassportJson(page: Page): Promise<{ bundle: { attempts: { result: S['TestResult'] }[]; mission: S['MissionTestContract'] } }> {
  await expect(page.getByTestId('export-btn')).toHaveCount(3);
  const ready = page.waitForEvent('download');
  await page.locator('[data-testid=export-btn][data-format=json]').click();
  const downloaded = await ready;
  return JSON.parse((await readFile((await downloaded.path())!)).toString());
}

export async function tabTo(page: Page, target: Locator, limit = 180) {
  for (let count = 0; count < limit; count++) {
    if (await target.evaluate(node => node === document.activeElement).catch(() => false)) {
      const focus = await target.evaluate(node => {
        const style = getComputedStyle(node);
        return { outline: parseFloat(style.outlineWidth), style: style.outlineStyle, shadow: style.boxShadow };
      });
      expect(focus.outline >= 2 && focus.style !== 'none' || focus.shadow !== 'none', 'Keyboard focus must be visible').toBe(true);
      return;
    }
    await page.keyboard.press('Tab');
  }
  throw new Error(`Keyboard could not reach ${await target.getAttribute('data-testid')}`);
}

export async function pressControl(page: Page, target: Locator) {
  await tabTo(page, target);
  await page.keyboard.press('Enter');
}

export async function keyboardMission(page: Page) {
  // Enable native file-chooser interception before any keyboard activation; it is switched on lazily by the first
  // listener, and a late switch lets the real dialog open and block the page (observed ~50% at 200 % zoom).
  page.on('filechooser', () => undefined);
  await page.goto('/');
  await pressControl(page, page.getByTestId('btn-new-mission'));
  await tabTo(page, page.getByTestId('input-mission-name'));
  await page.keyboard.type('Keyboard mobility investigation');
  await tabTo(page, page.getByTestId('input-objective'));
  await page.keyboard.type('Test geological sampling mobility with 100 m unique exposure on 12–18 degree slopes and return with reserve.');
  await tabTo(page, page.getByTestId('select-target-preset'));
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-testid=input-bbox][data-edge=min_lon]')).toHaveValue('137');
  await expect(page.locator('[data-testid=save-indicator][data-save-state=saved]')).toBeVisible();
  await tabTo(page, page.getByTestId('file-rover-import'));
  // A keyboard-opened native file picker needs a focused document; earlier contexts in the same worker can leave it unfocused.
  await page.bringToFront();
  await expect.poll(() => page.evaluate(() => document.hasFocus())).toBe(true);
  await expect(page.getByTestId('file-rover-import')).toBeFocused();
  const choosing = page.waitForEvent('filechooser');
  await page.keyboard.press('Space');
  await (await choosing).setFiles(fixture('rovers/ares-1.json'));
  await expect(page.getByTestId('rover-import-preview')).toBeVisible();
  await pressControl(page, page.getByTestId('btn-rover-save'));
  await expect(page.getByTestId('select-rover')).toContainText('ARES-1');
  await pressControl(page, page.getByTestId('btn-build-fingerprint'));
  await expect(page.locator('[data-testid=preparation-status][data-job-state=SUCCEEDED]')).toBeVisible({ timeout: 60000 });
  await expect(page.getByTestId('requirement-row')).toHaveCount(9);
  await pressControl(page, page.getByTestId('btn-accept-contract'));
  await pressControl(page, page.getByTestId('btn-start-run'));
  await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'AWAITING_REVIEW', { timeout: runTimeout() });
  await pressControl(page, page.locator('[data-testid=run-nav-tab][data-tab=analogs]'));
  await expect(page.getByTestId('candidate-row')).toHaveCount(6);
  await pressControl(page, page.locator('[data-testid=run-nav-tab][data-tab=qualification]'));
  await expect(page.getByTestId('qualification-matrix')).toBeVisible();
  await expect(page.locator('[data-testid=qual-cell][data-requirement-id=R-GRAVITY]').first()).toHaveAttribute('data-status', 'GAP');
  await expect(page.locator('[data-testid=qual-cell][data-requirement-id=R-CLEARANCE]').first()).toHaveAttribute('data-status', 'UNKNOWN');
}

