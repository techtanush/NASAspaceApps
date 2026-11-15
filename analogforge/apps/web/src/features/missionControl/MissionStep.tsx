import { useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Button, FormField, Input } from '../../components/ui';
import { GLOBE_ASSETS } from '../../maps/globeAssets';
import { Guide, Panel, useScene } from './StageShell';
import { useMissionControl } from './state';
import { NAMED_SITES } from './namedSites';
import { formatPlace } from './coordinates';

const EXAMPLES = [
  { label: 'Slope traverse', text: 'Test rover mobility on 12–18 degree slopes with at least 100 m of unique exposure, then return with at least 20% battery reserve.' },
  { label: 'Sampling run', text: 'Reach two geological sampling waypoints on steep rocky terrain and return with at least 20% modeled battery reserve.' },
  { label: 'Terrain only', text: 'Find Earth terrain whose slope distribution matches this area. No rover test is required.' },
];
export function MissionStep() {
  const { plan, update, box } = useMissionControl(); const navigate = useNavigate(); const ready = plan.confirmed && plan.lat !== null && plan.lng !== null && box?.ok === true;
  useScene({ body: plan.body, layout: 'panel', autoRotate: false, focus: ready ? { lat: plan.lat!, lng: plan.lng!, altitude: 1.7 } : null, pin: ready ? { lat: plan.lat!, lng: plan.lng! } : null, box: ready ? box.bbox : null });
  const site = NAMED_SITES.find(item => item.id === plan.siteId); const suggested = `${site?.name ?? GLOBE_ASSETS[plan.body].label} rehearsal`;
  useEffect(() => { if (ready && plan.name === '') update({ name: suggested }); }, [ready, plan.name, suggested, update]);
  if (!ready) return <Navigate to="/start/place" replace/>;
  const valid = plan.name.trim() !== '' && plan.objective.trim() !== '';
  return <Panel testid="mission-step" step="Step 2 of 4" title="What is the mission?" lead={`Target: ${GLOBE_ASSETS[plan.body].label}, ${formatPlace(plan.lat!, plan.lng!)}.`}
    footer={<><Button variant="ghost" onClick={() => navigate('/start/place')}><ArrowLeft size={16} aria-hidden="true"/>Back</Button><Button variant="primary" data-testid="btn-mission-continue" disabled={!valid} disabledReason="Add a name and what the rover must achieve." onClick={() => navigate('/start/rover')}>Continue<ArrowRight size={16} aria-hidden="true"/></Button></>}>
    <Guide>Say what the rover must achieve in plain words. AnalogForge turns it into measurable requirements, and you review every one before anything is locked.</Guide>
    <FormField label="Mission name"><Input data-testid="input-mc-name" value={plan.name} onChange={event => update({ name: event.target.value })}/></FormField>
    <div className="mc-field"><label className="mc-field-label" htmlFor="mc-objective">What must the rover achieve?</label>
      <textarea id="mc-objective" className="mc-textarea" data-testid="input-mc-objective" rows={6} value={plan.objective} placeholder="Describe the capability to rehearse, with numbers where you have them." onChange={event => update({ objective: event.target.value })}/>
      <div className="mc-chips" role="group" aria-label="Example missions">{EXAMPLES.map(example => <button key={example.label} type="button" className="mc-chip" data-testid="objective-example" onClick={() => update({ objective: example.text })}>{example.label}</button>)}</div></div>
  </Panel>;
}
