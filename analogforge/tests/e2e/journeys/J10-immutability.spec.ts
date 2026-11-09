import { expect, test } from '@playwright/test';
import { startRun, api } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J10 editing creates a new draft while accepted run inputs remain immutable', async ({ page }) => {
  const runId = await startRun(page);
  const before = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  const contract = await api<S['MissionTestContract']>(page, `/mission-revisions/${before.body.mission_revision_id}`);
  const header = await api<S['MissionHeader']>(page, `/missions/${contract.body.mission_id}`);
  const changed = await api(page, `/mission-revisions/${before.body.mission_revision_id}`, { method: 'PATCH', body: { objective: 'Changed' } });
  expect([403, 405, 409]).toContain(changed.status);
  await page.goto(`/missions/${contract.body.mission_id}/edit`);
  await expect(page.getByTestId('input-objective')).toHaveValue(contract.body.objective);
  await page.getByTestId('input-objective').fill('New draft objective, requiring a separately accepted contract.');
  await expect(page.locator('[data-testid=save-indicator][data-save-state=saved]')).toBeVisible();
  const revised = await api<S['MissionHeader']>(page, `/missions/${contract.body.mission_id}`);
  expect(revised.body.current_draft_id).not.toBe(header.body.current_draft_id);
  const pinned = await api<S['MissionTestContract']>(page, `/mission-revisions/${before.body.mission_revision_id}`);
  expect(pinned.body).toEqual(contract.body);
  await page.goto(`/runs/${runId}/mission`);
  await expect(page.getByTestId('requirement-row')).toHaveCount(9);
  const after = await api<S['RunSnapshot']>(page, `/runs/${runId}`);
  expect(after.body.mission_revision_id).toBe(before.body.mission_revision_id);
  expect(after.body.rover_revision_id).toBe(before.body.rover_revision_id);
});

