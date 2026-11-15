import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { api } from '../../api/client';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { Button, ErrorPanel, FileDrop, Skeleton } from '../../components/ui';
import { RoverEditor } from '../rovers/RoverEditor';
import { fetchRoverProfiles } from '../rovers/roverProfiles';
import { parseRoverImport, type RoverValidationIssue } from '../rovers/validation';
import { Guide, Panel, useScene } from './StageShell';
import { useMissionControl } from './state';
import { BoundOperatorContext } from '../operatorContext/BoundOperatorContext';

type Rover = components['schemas']['RoverProfile'];
const SPECS: { key: keyof Rover; label: string; unit: string }[] = [
  { key: 'mass_kg', label: 'Mass', unit: 'kg' }, { key: 'max_slope_deg', label: 'Max slope', unit: '°' }, { key: 'ground_clearance_m', label: 'Clearance', unit: 'm' },
  { key: 'wheel_diameter_m', label: 'Wheel', unit: 'm' }, { key: 'battery_wh', label: 'Battery', unit: 'Wh' }, { key: 'min_reserve_pct', label: 'Reserve', unit: '%' },
];
function latestRevisions(items: Rover[]): Rover[] {
  const latest = new Map<string, Rover>(); for (const rover of items) { const seen = latest.get(rover.rover_id); if (!seen || rover.revision > seen.revision) latest.set(rover.rover_id, rover); }
  return [...latest.values()].sort((a, b) => a.name.localeCompare(b.name));
}
export function RoverStep() {
  const { plan, update, box } = useMissionControl(); const navigate = useNavigate(); const workspace = useWorkspace(); const cache = useQueryClient();
  const ready = plan.confirmed && plan.lat !== null && plan.lng !== null && box?.ok === true && plan.objective.trim() !== '';
  useScene({ body: plan.body, layout: 'panel', autoRotate: false, focus: ready ? { lat: plan.lat!, lng: plan.lng!, altitude: 1.7 } : null, pin: ready ? { lat: plan.lat!, lng: plan.lng! } : null, box: ready ? box.bbox : null });
  const rovers = useQuery({ queryKey: ['workspace', workspace, 'mc-rovers'], queryFn: ({ signal }) => fetchRoverProfiles(signal) });
  const [editor, setEditor] = useState(false);
  const [contextPending, setContextPending] = useState(false);
  const [issues, setIssues] = useState<RoverValidationIssue[]>([]); const [error, setError] = useState<unknown>(null); const [saving, setSaving] = useState(false);
  if (!ready) return <Navigate to="/start/mission" replace/>;
  const importFile = async (file?: File) => {
    if (!file) return; setIssues([]); setError(null); const parsed = parseRoverImport(await file.text());
    if (!parsed.ok) { setIssues(parsed.errors); return; }
    setSaving(true);
    try { const saved = await api.post<Rover>('/rovers', parsed.value, { recover: () => api.get('/rovers') }); await cache.invalidateQueries({ queryKey: ['workspace', workspace, 'mc-rovers'] }); update({ roverRevisionId: saved.id, roverName: saved.name, noRover: false }); }
    catch (cause) { setError(cause); } finally { setSaving(false); }
  };
  const list = latestRevisions(rovers.data?.items ?? []); const chosen = plan.noRover || plan.roverRevisionId !== null;
  const nameCounts = new Map<string, number>(); for (const rover of list) nameCounts.set(rover.name, (nameCounts.get(rover.name) ?? 0) + 1);
  return <Panel testid="rover-step" step="Step 3 of 4" title="Which rover?" lead="Choose the rover to test, add one, or qualify the site without a rover."
    footer={<><Button variant="ghost" onClick={() => navigate('/start/mission')}><ArrowLeft size={16} aria-hidden="true"/>Back</Button><Button variant="primary" data-testid="btn-rover-continue" disabled={!chosen || saving || contextPending} disabledReason="Choose a rover or the site-only option, and finish saving any supporting context." onClick={() => navigate('/start/review')}>Continue<ArrowRight size={16} aria-hidden="true"/></Button></>}>
    <Guide>The rover’s limits set the benchmark. Every result is tied to this exact rover revision.</Guide>
    {rovers.isPending ? <Skeleton label="Retrieving saved rovers"/> : rovers.error ? <ErrorPanel error={rovers.error} onRetry={() => { void rovers.refetch(); }}/> :
      <ul className="mc-rovers" data-testid="rover-options">{list.map(rover => { const selected = plan.roverRevisionId === rover.id; return <li key={rover.id}><button type="button" className="mc-rover" data-testid="rover-option" data-rover={rover.name} data-rover-id={rover.rover_id} data-rover-revision-id={rover.id} aria-pressed={selected} onClick={() => update({ roverRevisionId: rover.id, roverName: rover.name, noRover: false })}>
        <span className="mc-rover-head"><strong>{rover.name}</strong><span className="revision-badge">rev {rover.revision}</span>{selected && <Check size={16} aria-hidden="true"/>}</span>
        {(nameCounts.get(rover.name) ?? 0) > 1 && <span className="mc-energy mono" title={rover.rover_id}>Rover ID {rover.rover_id.slice(0, 8)}</span>}
        <span className="mc-specs">{SPECS.map(spec => <span key={spec.key}><em>{spec.label}</em>{rover[spec.key] === null || rover[spec.key] === undefined ? 'Unknown' : `${String(rover[spec.key])} ${spec.unit}`}</span>)}</span>
        <span className="mc-energy" data-energy={rover.energy_model?.calibration_status ?? 'NONE'}>{rover.energy_model ? `Energy model: ${rover.energy_model.calibration_status === 'CALIBRATED' ? 'calibrated' : 'assumed, not calibrated'}` : 'No energy model: route results will be inconclusive'}</span>
      </button></li>; })}
        <li><button type="button" className="mc-rover" data-testid="rover-none" aria-pressed={plan.noRover} onClick={() => update({ noRover: true, roverRevisionId: null, roverName: null })}><span className="mc-rover-head"><strong>No rover: qualify the site only</strong>{plan.noRover && <Check size={16} aria-hidden="true"/>}</span><span className="mc-energy">Earth sites are matched to the target terrain. Route benchmarks are not run.</span></button></li></ul>}
    <div className="mc-field"><span className="mc-field-label">Add a rover from a JSON profile</span><FileDrop data-testid="mc-rover-import" aria-label="Rover JSON profile" disabled={saving} onChange={event => { void importFile(event.target.files?.[0]); }}/>
      {issues.length > 0 && <ul className="mc-issues" role="alert" data-testid="rover-import-issues">{issues.slice(0, 5).map(issue => <li key={`${issue.field}:${issue.message}`}><strong>{issue.field}</strong> {issue.message}</li>)}</ul>}
      {error !== null && <ErrorPanel error={error}/>}
      <Button variant="secondary" aria-expanded={editor} onClick={() => setEditor(value => !value)}>{editor ? 'Close rover editor' : 'Create or edit a rover'}</Button>
      {editor && <div className="mc-inline-editor"><RoverEditor showContext={false} value={plan.roverRevisionId} onSavingChange={setSaving} onSelect={id => { if (!id) { update({noRover:true, roverRevisionId:null, roverName:null}); return; } void api.get<Rover>(`/rover-revisions/${id}`).then(rover => { update({roverRevisionId:rover.id,roverName:rover.name,noRover:false}); }).catch(setError); }}/></div>}
      <p className="helper">The <a href="/rovers" target="_blank" rel="noreferrer">rover library opens in a separate tab</a>; your investigation stays here.</p></div>
    {!plan.noRover && plan.roverRevisionId && <BoundOperatorContext key={plan.roverRevisionId} kind="ROVER" id={plan.roverRevisionId} targetId={plan.roverRevisionId} disabled={saving} onPendingChange={setContextPending} onContextChange={roverContext => { if (!plan.roverContextChecked || (plan.roverContext?.id ?? null) !== (roverContext?.id ?? null)) update({ roverContext, roverContextChecked: true }); }}/>}
  </Panel>;
}
