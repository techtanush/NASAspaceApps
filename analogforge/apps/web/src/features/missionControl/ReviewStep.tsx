import { useRef, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Lock } from 'lucide-react';
import { api } from '../../api/client';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { Button, ErrorPanel, ModeBadge, Skeleton } from '../../components/ui';
import { GLOBE_ASSETS } from '../../maps/globeAssets';
import { Guide, Panel, useScene } from './StageShell';
import { useMissionControl } from './state';
import { formatPlace } from './coordinates';
import { chooseLaunch } from './scenario';
import { benchmarkText, ORIGIN_LABEL } from './tour';

type S = components['schemas']; type Phase = 'idle' | 'creating' | 'preparing' | 'proposed' | 'starting';
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
export function ReviewStep() {
  const { plan, box } = useMissionControl(); const navigate = useNavigate(); const workspace = useWorkspace();
  const ready = plan.confirmed && plan.lat !== null && plan.lng !== null && box?.ok === true && plan.objective.trim() !== '' && (plan.noRover || plan.roverRevisionId !== null);
  useScene({ body: plan.body, layout: 'panel', autoRotate: false, focus: ready ? { lat: plan.lat!, lng: plan.lng!, altitude: 1.7 } : null, pin: ready ? { lat: plan.lat!, lng: plan.lng! } : null, box: ready ? box.bbox : null });
  const capabilities = useApi<S['CapabilityReport']>(workspace, '/capabilities');
  const scenarios = useQuery({ queryKey: ['workspace', workspace, 'mc-scenarios', capabilities.data?.scenario_config_ids], enabled: !!capabilities.data, queryFn: ({ signal }) => Promise.all((capabilities.data?.scenario_config_ids ?? []).map(id => api.get<S['ScenarioConfig']>(`/configuration/scenarios/${id}`, { signal }))) });
  const [phase, setPhase] = useState<Phase>('idle'); const [progress, setProgress] = useState(''); const [error, setError] = useState<unknown>(null);
  const [header, setHeader] = useState<S['MissionHeader'] | null>(null); const [contract, setContract] = useState<S['MissionTestContract'] | null>(null); const alive = useRef(true);
  if (!ready) return <Navigate to="/start/rover" replace/>;
  const launch = capabilities.data && scenarios.data ? chooseLaunch(plan.body, capabilities.data, scenarios.data) : null;
  const rover = plan.noRover ? null : plan.roverRevisionId;
  const prepare = async () => {
    if (!launch || !box.ok) return; setError(null); setPhase('creating'); setProgress('Saving the mission draft');
    try {
      const draft: S['MissionDraftInput'] = { name: plan.name.trim(), objective: plan.objective.trim(), target: { body: plan.body, bbox: [...box.bbox], longitude_convention: 'NEG180_180', latitude_type: 'PLANETOCENTRIC', crs_wkt: null, vertical_datum: 'Unknown' } };
      const created = await api.post<S['MissionHeader']>('/missions', draft, { recover: () => api.get('/missions') });
      setPhase('preparing'); setProgress('Proposing measurable requirements');
      const accepted = await api.post<S['PreparationAccepted']>(`/missions/${created.id}/fingerprint`, { expected_revision: created.revision, mode: launch.mode, rover_revision_id: rover } satisfies S['FingerprintInput'], { recover: () => api.get(`/missions/${created.id}`) });
      let status = await api.get<S['JobStatus']>(`/jobs/${accepted.job_id}`);
      for (let attempt = 0; attempt < 600 && alive.current && (status.state === 'QUEUED' || status.state === 'RUNNING'); attempt++) { setProgress(status.progress_step || 'Proposing measurable requirements'); await pause(700); status = await api.get<S['JobStatus']>(`/jobs/${accepted.job_id}`); }
      if (status.state !== 'SUCCEEDED' || !status.proposed_revision_id) throw status.error ?? new Error(`Requirement preparation ended as ${status.state.toLowerCase()}.`);
      const proposed = await api.get<S['MissionTestContract']>(`/mission-revisions/${status.proposed_revision_id}`);
      setHeader(await api.get<S['MissionHeader']>(`/missions/${created.id}`)); setContract(proposed); setPhase('proposed');
    } catch (cause) { setError(cause); setPhase('idle'); }
  };
  const start = async () => {
    if (!launch || !header || !contract) return; setError(null); setPhase('starting');
    try {
      const locked = await api.post<S['MissionTestContract']>(`/missions/${header.id}/accept`, { expected_revision: header.revision, revision_id: contract.id } satisfies S['MissionAcceptInput'], { recover: () => api.get(`/missions/${header.id}`) });
      const run = await api.post<S['CommandAccepted']>('/runs', { mission_revision_id: locked.id, rover_revision_id: rover, mode: launch.mode, dataset_lock_id: launch.scenario.default_dataset_lock_id, scenario_config_id: launch.scenario.id } satisfies S['RunCreateInput'], { recover: () => api.get('/runs') });
      navigate(`/runs/${run.run_id}/tour`);
    } catch (cause) { setError(cause); setPhase('proposed'); }
  };
  const busy = phase === 'creating' || phase === 'preparing' || phase === 'starting';
  return <Panel testid="review-step" step="Step 4 of 4" title="Review and lock" lead="Check the test, review the proposed requirements, then lock it and start."
    footer={<><Button variant="ghost" disabled={busy} onClick={() => navigate('/start/rover')}><ArrowLeft size={16} aria-hidden="true"/>Back</Button>
      {phase === 'proposed' || phase === 'starting' ? <Button variant="primary" data-testid="btn-accept-start" disabled={busy} onClick={() => { void start(); }}><Lock size={16} aria-hidden="true"/>{phase === 'starting' ? 'Starting' : 'Accept and start'}</Button>
        : <Button variant="primary" data-testid="btn-prepare" disabled={busy || !launch} disabledReason={!launch && !capabilities.isPending && !scenarios.isPending ? `No runnable data source is configured for ${GLOBE_ASSETS[plan.body].label}.` : undefined} onClick={() => { void prepare(); }}>{busy ? 'Preparing' : 'Prepare requirements'}</Button>}</>}>
    <Guide>{phase === 'proposed' ? 'These are the measurable requirements. Accepting locks the test: a later change creates a new revision.' : 'Nothing is locked yet. Preparing proposes the requirements for you to review.'}</Guide>
    <dl className="mc-summary" data-testid="review-summary">
      <div><dt>Place</dt><dd>{GLOBE_ASSETS[plan.body].label} · {formatPlace(plan.lat!, plan.lng!)} · {plan.sizeKm} km area</dd><Link to="/start/place">Edit</Link></div>
      <div><dt>Mission</dt><dd><strong>{plan.name}</strong><span>{plan.objective}</span></dd><Link to="/start/mission">Edit</Link></div>
      <div><dt>Rover</dt><dd>{plan.noRover ? 'None: site qualification only' : plan.roverName}</dd><Link to="/start/rover">Edit</Link></div>
      <div><dt>Data</dt><dd>{launch ? <>{launch.scenario.name} <ModeBadge mode={launch.mode}/></> : capabilities.isPending || scenarios.isPending ? 'Checking configured data sources' : 'No runnable data source'}</dd></div>
    </dl>
    {busy && <div className="mc-working" role="status" data-testid="prepare-status" data-phase={phase}><Skeleton label={progress || 'Working'}/><p>{progress}</p></div>}
    {error !== null && <ErrorPanel error={error} onRetry={phase === 'idle' ? () => { void prepare(); } : undefined}/>}
    {contract && <section className="mc-requirements" data-testid="proposed-requirements" aria-label="Proposed requirements"><h2>Requirements to be locked</h2><ul>{contract.requirements.map(requirement => <li key={requirement.id} data-testid="proposed-requirement"><strong>{requirement.label}</strong><span className="mc-rule">Must be {benchmarkText(requirement)}</span><span className="mc-tags"><span className="revision-badge">{ORIGIN_LABEL[requirement.origin]}</span>{requirement.mandatory ? <span className="revision-badge">Mandatory</span> : <span className="revision-badge">Optional</span>}</span></li>)}</ul></section>}
  </Panel>;
}
