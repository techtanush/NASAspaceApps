import type { components } from '../../generated/schema';

type S = components['schemas'];
export interface Launch { scenario: S['ScenarioConfig']; mode: S['RuntimeMode'] }
/** Chooses the runnable scenario for a body: live data when it is configured, otherwise practice data. */
export function chooseLaunch(body: S['Body'], capabilities: S['CapabilityReport'], scenarios: S['ScenarioConfig'][]): Launch | null {
  const runnable = scenarios.filter(scenario => scenario.body === body && scenario.allowed_modes.length > 0);
  const live = capabilities.live_ai_configured ? runnable.find(scenario => scenario.allowed_modes.includes('live')) : undefined;
  if (live) return { scenario: live, mode: 'live' };
  const practice = runnable.filter(scenario => scenario.allowed_modes.includes('synthetic'));
  const chosen = practice.find(scenario => scenario.id === capabilities.default_scenario_config_id) ?? practice.find(scenario => !scenario.id.includes('graph') && !scenario.id.includes('local')) ?? practice[0] ?? runnable[0];
  return chosen ? { scenario: chosen, mode: chosen.allowed_modes.includes('synthetic') ? 'synthetic' : chosen.allowed_modes[0]! } : null;
}
