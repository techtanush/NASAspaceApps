import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useWorkspace } from '../../app/WorkspaceContext';
import { ErrorPanel } from '../../components/ui';
import { formatPlace } from './coordinates';

type Position = [number, number];
type RoutePlan = {
  start: Position; finish: Position; coordinates: Position[]; outcome: string; support_scale_m: number | null;
  checkpoints: { id: string; position: Position; activity: string; capability: string | null; dwell_s: number; tolerance_m: number; requirement_ids: string[]; origin: string }[];
  assumptions: string[];
};
export type FieldPlan = { run_id: string; run_revision: number; candidate_id: string; center: Position; bbox: number[];
  route: RoutePlan | null; route_note: string; field_readiness: string; steps: string[]; screened_count: number | null; dataset_lock_id: string | null };
const place = ([lon, lat]: Position) => formatPlace(lat, lon);
export function SiteFieldPlan({ runId, candidateId, revision }: { runId: string; candidateId: string; revision: number }) {
  const workspace = useWorkspace();
  const result = useQuery({ queryKey: ['workspace', workspace, 'site-field-plan', runId, candidateId, revision], retry: false,
    queryFn: async ({ signal }) => {
      const plan = await api.get<FieldPlan>(`/runs/${runId}/candidates/${candidateId}/test-plan`, { signal });
      if (plan.run_id !== runId || plan.candidate_id !== candidateId) throw new Error('This test plan belongs to another location.');
      return plan;
    } });
  const plan = result.data;
  if (result.error) return <section className="mc-field-plan"><h2>Field test plan unavailable</h2><ErrorPanel error={result.error} onRetry={() => { void result.refetch(); }}/></section>;
  if (!plan) return <section className="mc-field-plan" aria-busy="true"><h2>Opening this location’s test plan</h2></section>;
  const route = plan.route;
  const [west, south, east, north] = plan.bbox as [number, number, number, number];
  const cosine = Math.cos((south + north) / 2 * Math.PI / 180);
  const scale = Math.min(440 / ((east - west) * cosine), 240 / (north - south));
  const width = (east - west) * cosine * scale, height = (north - south) * scale;
  const plot = ([lon, lat]: Position) => [(500 - width) / 2 + (lon - west) * cosine * scale, 24 + (north - lat) * scale];
  return <section className="mc-field-plan" aria-label="Location field test plan">
    <p className="mc-eyebrow">01 · How this location was found</p><h2>From mission to test site</h2>
    <p>The accepted mission criteria were compared with registered terrain observations in {plan.screened_count == null ? 'the acquired candidate windows' : `${plan.screened_count} screened windows`}. The benchmarks below show exactly which conditions this site matches. This is a regional search.</p>
    <p className="mc-eyebrow">02 · Where to test</p><h2>Start, checkpoints and finish</h2>
    <p>{plan.route_note}</p><div className="mc-field-coordinates"><span>Assessed region centre</span><strong>{place(plan.center)}</strong><small>Reference coordinate · not an approved starting point</small></div>
    <figure className="mc-field-route"><svg viewBox="0 0 500 300" role="img" aria-label={route ? 'Computed raster route within the assessed Earth region; not a surveyed field corridor' : 'Assessed Earth region and reference centre; no route computed'}>
      <rect x={(500 - width) / 2} y="24" width={width} height={height} fill="var(--surface-2)" stroke="var(--accent)"/>
      {route ? <><path d={route.coordinates.map((point, i) => `${i ? 'L' : 'M'} ${plot(point).join(' ')}`).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2"/>{route.checkpoints.map((item, i) => { const [x, y] = plot(item.position); return <g key={item.id}><circle cx={x} cy={y} r="4" fill="var(--text-primary)"/><text x={x + 7} y={y - 7}>{i + 1}</text></g>; })}</> : <circle cx={plot(plan.center)[0]} cy={plot(plan.center)[1]} r="4" fill="var(--accent)"/>}
    </svg><figcaption>North up · WGS84 coordinate schematic. Outline: assessed region. {route ? `Line: stored ${route.support_scale_m ?? 'unknown'} m raster route.` : 'Dot: region centre.'} No field clearance is implied.</figcaption></figure>
    {route ? <><dl className="mc-field-endpoints"><dt>Start</dt><dd>{place(route.start)}</dd><dt>Finish</dt><dd>{place(route.finish)}{route.start.every((v, i) => v === route.finish[i]) && ' · return loop'}</dd></dl>
      <ol className="mc-field-stops">{route.checkpoints.map(item => <li key={item.id}><strong>{item.id} · {place(item.position)}</strong><p>{item.activity.toLowerCase()} · {item.capability?.replaceAll('_', ' ') ?? 'capability unspecified'} · dwell {item.dwell_s} s · tolerance {item.tolerance_m} m</p><small>{item.requirement_ids.length ? `Criteria: ${item.requirement_ids.join(', ')}` : 'No accepted mission criterion assigned to this checkpoint.'}</small></li>)}</ol>
      <details><summary>Route design assumptions</summary>{route.assumptions.map((line, i) => <p key={i}>{line}</p>)}</details>
      <p><Link to={`/runs/${runId}/test-lab`}>Inspect modeled route checks and telemetry</Link></p></> : <p><strong>Start and finish are not established.</strong> Survey this site, select endpoints and compute an independently verified route before planning a drive.</p>}
    <details className="mc-field-sequence"><summary>Field procedure and observations to collect</summary><ol>{plan.steps.map(step => <li key={step}>{step}</li>)}</ol></details>
    <p className="mc-field-readiness">{plan.field_readiness}</p>
    <p>Terrain matching checks site suitability. Hardware acceptance needs a separately specified rover test; Earth testing does not assure Mars or Moon mission success.</p>
    <p className="mc-eyebrow">03 · What to test and the benchmark to meet</p>
  </section>;
}
