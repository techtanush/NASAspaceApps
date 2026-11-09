import { expect, test } from '@playwright/test';
import { startRun, tab, prove, api } from '../support/workbench';
import { persistedResults, assertAuditMatches, downloadPassportJson, type S } from '../support/journeyChecks';

test('J05 rover conflict never relaxes exposure contract', async ({ page }) => {
  const runId = await startRun(page, { rover: 'practice-lite' });
  const original = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  const contract = await api<S['MissionTestContract']>(page, `/mission-revisions/${original.body.mission_revision_id}`);
  expect(contract.body.requirements.find(row => row.id === 'R-EXPOSURE')?.lower).toBe(100);
  await prove(page, 'Practice grid-r0c0');
  await expect(page.getByTestId('attempt-row').last()).toHaveAttribute('data-outcome', 'FAIL');
  await expect(page.getByTestId('failure-category').last()).toHaveAttribute('data-category', 'ROVER');
  const after = await api<S['MissionTestContract']>(page, `/mission-revisions/${original.body.mission_revision_id}`);
  expect(after.body).toEqual(contract.body);
  await persistedResults(page, runId);
  await tab(page, 'passport');
  await expect(page.getByTestId('passport-view')).toContainText('NEW_CONTRACT_REQUIRED');
  await assertAuditMatches(page, runId);
  const exported = await downloadPassportJson(page);
  expect(exported.bundle.attempts.at(-1)?.result.failure_category).toBe('ROVER');
  expect(exported.bundle.mission.requirements.find(row => row.id === 'R-EXPOSURE')?.lower).toBe(100);
});

