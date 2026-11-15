import { expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { components } from '../../generated/schema';
import { moonPractice } from '../missions/practicePresets';
import { PracticeTargetChoice, practiceTarget } from './PracticeTargetArea';
import { MissionControlProvider, useMissionControl } from './state';
import type { Launch } from './scenario';

const launch: Launch = { mode: 'synthetic', scenario: { id: 'synthetic-moon-gap-v1', body: 'MOON', default_dataset_lock_id: 'synthetic-policy-v1', allowed_modes: ['synthetic'] } as components['schemas']['ScenarioConfig'] };
it('offers the shared practice target only for its exact synthetic scenario, lock and body', () => {
  expect(practiceTarget(launch, 'MOON')).toEqual(moonPractice.target);
  for (const other of [null, { ...launch, mode: 'live' as const }, { ...launch, scenario: { ...launch.scenario, id: 'another-scenario' } }, { ...launch, scenario: { ...launch.scenario, default_dataset_lock_id: 'another-lock' } }, { ...launch, scenario: { ...launch.scenario, body: 'MARS' as const } }]) expect(practiceTarget(other, 'MOON')).toBeNull();
  expect(practiceTarget(launch, 'MARS')).toBeNull();
});
function Setup() {
  const { plan, update, box } = useMissionControl();
  return <><button onClick={() => update({ body: 'MOON' })}>Moon</button><PracticeTargetChoice launch={launch} plan={plan} update={update}/><output data-testid="selected-target">{JSON.stringify({ target: plan.exactTarget, binding: plan.practiceSource, bbox: box?.ok ? box.bbox : null })}</output>{(['body', 'lat', 'lng', 'latText', 'lngText', 'sizeKm', 'siteId'] as const).map(key => <button key={key} onClick={() => update({ [key]: key === 'body' ? 'MARS' : key === 'siteId' ? 'named-site' : key.endsWith('Text') ? '1' : 1 })}>Edit {key}</button>)}<button onClick={() => update({ name: 'Changed title' })}>Edit title</button></>;
}
it('preserves the preset AOI rather than recomputing a square, and clears its binding on any manual geometry edit', () => {
  render(<MissionControlProvider><Setup/></MissionControlProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'Moon' }));
  const select = () => fireEvent.click(screen.getByRole('button', { name: 'Use practice target area' }));
  const value = () => JSON.parse(screen.getByTestId('selected-target').textContent!);
  select();
  expect(value()).toEqual({ target: moonPractice.target, binding: { scenarioId: launch.scenario.id, datasetLockId: launch.scenario.default_dataset_lock_id }, bbox: moonPractice.target.bbox });
  fireEvent.click(screen.getByRole('button', { name: 'Edit title' }));
  expect(value().target).toEqual(moonPractice.target);
  for (const key of ['lat', 'lng', 'latText', 'lngText', 'sizeKm', 'siteId', 'body']) {
    fireEvent.click(screen.getByRole('button', { name: `Edit ${key}` }));
    expect(value().target).toBeNull(); expect(value().binding).toBeNull();
    if (key !== 'body') select();
  }
});
