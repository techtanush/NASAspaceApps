import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { Button } from '../../components/ui';
import { marsPractice, moonPractice } from '../missions/practicePresets';
import { boxCentre } from './coordinates';
import { chooseLaunch, type Launch } from './scenario';
import { useMissionControl, type Plan, type TargetBody } from './state';

type S = components['schemas'];
export function practiceTarget(launch: Launch | null, body: TargetBody): S['MissionDraftInput']['target'] | null {
  const scenario = body === 'MARS' ? 'synthetic-mars-mobility-v1' : 'synthetic-moon-gap-v1';
  if (!launch || launch.mode !== 'synthetic' || launch.scenario.body !== body || launch.scenario.id !== scenario || launch.scenario.default_dataset_lock_id !== 'synthetic-policy-v1') return null;
  return structuredClone((body === 'MARS' ? marsPractice : moonPractice).target) as S['MissionDraftInput']['target'];
}
export function ExactTargetBounds({ target }: { target: S['MissionDraftInput']['target'] }) {
  return <span className="mono">Exact bounds: west {target.bbox[0]}°, south {target.bbox[1]}°, east {target.bbox[2]}°, north {target.bbox[3]}°</span>;
}
export function PracticeTargetChoice({ launch, plan, update }: { launch: Launch | null; plan: Plan; update: (patch: Partial<Plan>) => void }) {
  const target = practiceTarget(launch, plan.body);
  if (!target || !launch) return null;
  const selected = plan.practiceSource?.scenarioId === launch.scenario.id && plan.practiceSource.datasetLockId === launch.scenario.default_dataset_lock_id && JSON.stringify(plan.exactTarget) === JSON.stringify(target);
  return <section className="mc-coverage" data-testid="practice-target-area"><div><strong>Bundled synthetic practice target</strong><p>This source measures its configured practice area. A named place does not imply data coverage. No NASA observations are used.</p><p><ExactTargetBounds target={target}/></p><p className="helper mono">{launch.scenario.id} · {launch.scenario.default_dataset_lock_id}</p>
    <Button data-testid="btn-use-practice-target" variant="secondary" disabled={selected} onClick={() => { const centre = boxCentre(target.bbox); update({ lat: centre.lat, lng: centre.lng, latText: String(centre.lat), lngText: String(centre.lng), siteId: null, confirmed: false, exactTarget: target, practiceSource: { scenarioId: launch.scenario.id, datasetLockId: launch.scenario.default_dataset_lock_id } }); }}>{selected ? 'Practice target area selected' : 'Use practice target area'}</Button>
    {selected && <p className="helper" role="status">The exact configured bounds are selected. Editing coordinates or area size creates a custom target.</p>}
  </div></section>;
}
export function PracticeTargetArea() {
  const { plan, update } = useMissionControl(); const workspace = useWorkspace();
  const capabilities = useApi<S['CapabilityReport']>(workspace, '/capabilities');
  const scenarios = useQuery({ queryKey: ['workspace', workspace, 'mc-scenarios', capabilities.data?.scenario_config_ids], enabled: !!capabilities.data, queryFn: ({ signal }) => Promise.all((capabilities.data?.scenario_config_ids ?? []).map(id => api.get<S['ScenarioConfig']>(`/configuration/scenarios/${id}`, { signal }))) });
  const launch = capabilities.data && scenarios.data ? chooseLaunch(plan.body, { ...capabilities.data, live_ai_configured: false }, scenarios.data.map(scenario => ({ ...scenario, allowed_modes: scenario.allowed_modes.filter(mode => mode === 'synthetic') }))) : null;
  return <PracticeTargetChoice launch={launch} plan={plan} update={update}/>;
}
