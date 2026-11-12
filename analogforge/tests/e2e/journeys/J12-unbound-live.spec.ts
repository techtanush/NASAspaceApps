import { expect, test } from '@playwright/test';
import { newMission, api } from '../support/workbench';
import { type S } from '../support/journeyChecks';

test('J12 live dataset slot is explicitly unavailable and cannot start an accepted contract', async ({ page }) => {
  await newMission(page);
  const missions = await api<S['ListMissionHeader']>(page, '/missions');
  const accepted = missions.body.items.find(mission => mission.accepted_contract_id !== null);
  expect(accepted).toBeDefined();
  await page.goto(`/missions/${accepted!.id}/edit?scenario=live-hackathon-v1`);
  await expect(page.getByTestId('requirement-row')).toHaveCount(9);
  await expect(page.getByTestId('btn-accept-contract')).toBeDisabled();
  await expect(page.locator('[data-testid=scenario-note][data-scenario-id=live-hackathon-v1]')).toHaveAttribute('data-available', 'false');
  await expect(page.locator('[data-testid=empty-state][data-reason=AWAITING_DATASETS]')).toBeVisible();
  await expect(page.getByTestId('btn-start-run')).toBeDisabled();
  const scenario = await api<S['ScenarioConfig']>(page, '/configuration/scenarios/live-hackathon-v1');
  expect(scenario.body.allowed_modes).toEqual([]);
});

