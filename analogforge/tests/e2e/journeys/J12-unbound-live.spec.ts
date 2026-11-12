import { expect, test } from '@playwright/test';
import { newMission, api } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J12 live dataset slot is explicitly unavailable and cannot start an accepted contract', async ({ page }) => {
  const creation = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/v1/missions' && response.status() === 201);
  await newMission(page);
  const created = await (await creation).json() as S['MissionHeader'];
  const accepted = await api<S['MissionHeader']>(page, `/missions/${created.id}`);
  expect(accepted.body.accepted_contract_id).not.toBeNull();
  // Reopen this test's accepted Mars mission; older pages may begin with a Moon mission.
  await page.goto(`/missions/${created.id}/edit?scenario=live-hackathon-v1`);
  await expect(page.getByTestId('requirement-row')).toHaveCount(9);
  await expect(page.getByTestId('btn-accept-contract')).toBeDisabled();
  await expect(page.locator('[data-testid=scenario-note][data-scenario-id=live-hackathon-v1]')).toHaveAttribute('data-available', 'false');
  await expect(page.locator('[data-testid=empty-state][data-reason=AWAITING_DATASETS]')).toBeVisible();
  await expect(page.getByTestId('btn-start-run')).toBeDisabled();
  const scenario = await api<S['ScenarioConfig']>(page, '/configuration/scenarios/live-hackathon-v1');
  expect(scenario.body.allowed_modes).toEqual([]);
});

