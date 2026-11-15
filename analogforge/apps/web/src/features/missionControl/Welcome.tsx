import { useMissionControl } from './state';
import { Link } from 'react-router-dom';
import { ArrowRight, MapPin, Target, Bot, Globe2 } from 'lucide-react';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { ModeBadge } from '../../components/ui';
import { useScene } from './StageShell';

type Runs = components['schemas']['ListRunSnapshot'];
function RecentInvestigation({ run, workspace }: { run: components['schemas']['RunSnapshot']; workspace: string }) {
  const contract = useApi<components['schemas']['MissionTestContract']>(workspace, `/mission-revisions/${run.mission_revision_id}`);
  const scoped = contract.data?.id === run.mission_revision_id && contract.data.workspace_id === workspace;
  const name = scoped && contract.data?.name.trim() ? contract.data.name : `Investigation ${run.id.slice(0, 8)}`;
  return <li><Link to={`/runs/${run.id}/tour`} title={`Run ${run.id}`}><span>{name}</span><span>{sentence(run.state)}</span><ModeBadge mode={run.mode}/></Link></li>;
}
const STAGES = [
  { icon: MapPin, title: 'Pick the place', text: 'Drop a pin on Mars or the Moon.' },
  { icon: Target, title: 'Describe the mission', text: 'Say what the rover must achieve there.' },
  { icon: Bot, title: 'Add the rover', text: 'Enter its limits, or qualify the site alone.' },
  { icon: Globe2, title: 'Tour Earth sites', text: 'See where on Earth to test, and the benchmark to meet.' },
];
const sentence = (state: string) => state.toLowerCase().replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());
export function Welcome() {
  const { reset } = useMissionControl();
  useScene({ body: 'EARTH', autoRotate: true, layout: 'hero', focus: { lat: 18, lng: -40, altitude: 2.3 } });
  const workspace = useWorkspace(); const runs = useApi<Runs>(workspace, '/workspace/recent-runs?limit=4');
  const recent = runs.data?.items ?? [];
  return <section className="mc-hero" data-testid="welcome" aria-labelledby="welcome-title">
    <div className="mc-hero-kicker"><span className="mc-orbit-mark" aria-hidden="true"><svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="10"/><ellipse cx="24" cy="24" rx="23" ry="8" transform="rotate(-35 24 24)"/><path d="M24 4v7M24 37v7M4 24h7M37 24h7"/></svg></span><p className="mc-eyebrow">Planetary mission. Earth rehearsal.</p></div>
    <h1 id="welcome-title" tabIndex={-1}>A world away.<br/><span>Tested closer to home.</span></h1>
    <p className="mc-hero-lead">Find where on Earth to rehearse a mission to Mars or the Moon. Set the target, describe the objective and bring a rover. Follow the evidence to the right site for each benchmark.</p>
    <p className="mc-hero-principle"><span aria-hidden="true"/>What Earth cannot reproduce stays visible.</p>
    <div className="mc-hero-actions"><Link className="button mc-cta" data-variant="primary" to="/start/place" data-testid="btn-begin" onClick={reset}>Begin a new investigation<ArrowRight size={16} aria-hidden="true"/></Link><Link className="mc-secondary-entry" to="/workbench">Open mission library</Link></div>
    <ol className="mc-stages" aria-label="How it works">{STAGES.map(({ icon: Icon, title, text }, index) => <li key={title}><span className="mc-stage-index" aria-hidden="true">{index + 1}</span><Icon size={16} strokeWidth={1.5} aria-hidden="true"/><div><strong>{title}</strong><span>{text}</span></div></li>)}</ol>
    {recent.length > 0 && <div className="mc-recent" data-testid="recent-investigations"><h2>Continue an investigation</h2><ul>{recent.map(run => <RecentInvestigation key={run.id} run={run} workspace={workspace}/>)}</ul></div>}
    <p className="mc-hero-foot helper">Not a NASA product; no endorsement implied. Results are modeled terrain evidence, not field validation.</p>
  </section>;
}
