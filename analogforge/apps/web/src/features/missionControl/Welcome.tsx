import { useMissionControl } from './state';
import { Link } from 'react-router-dom';
import { ArrowRight, MapPin, Target, Bot, Globe2 } from 'lucide-react';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { ModeBadge } from '../../components/ui';
import { useScene } from './StageShell';

type Runs = components['schemas']['ListRunSnapshot'];
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
  const workspace = useWorkspace(); const runs = useApi<Runs>(workspace, '/runs?limit=4');
  const recent = runs.data?.items ?? [];
  return <section className="mc-hero" data-testid="welcome" aria-labelledby="welcome-title">
    <p className="mc-eyebrow">Mission-conditioned analog qualification</p>
    <h1 id="welcome-title" tabIndex={-1}>Find where on Earth to rehearse a mission to Mars or the Moon.</h1>
    <p className="mc-hero-lead">Give AnalogForge a place, a mission and a rover. It finds Earth sites whose terrain matches, says which capability each site can test, and states the benchmark your rover must meet there. What Earth cannot reproduce stays visible.</p>
    <div className="mc-hero-actions"><Link className="button mc-cta" data-variant="primary" to="/start/place" data-testid="btn-begin" onClick={reset}>Begin a new investigation<ArrowRight size={16} aria-hidden="true"/></Link></div>
    <ol className="mc-stages" aria-label="How it works">{STAGES.map(({ icon: Icon, title, text }, index) => <li key={title}><span className="mc-stage-index" aria-hidden="true">{index + 1}</span><Icon size={16} strokeWidth={1.5} aria-hidden="true"/><div><strong>{title}</strong><span>{text}</span></div></li>)}</ol>
    {recent.length > 0 && <div className="mc-recent" data-testid="recent-investigations"><h2>Continue an investigation</h2><ul>{recent.map(run => <li key={run.id}><Link to={`/runs/${run.id}/tour`}><span className="mono">{run.id.slice(0, 8)}</span><span>{sentence(run.state)}</span><ModeBadge mode={run.mode}/></Link></li>)}</ul></div>}
    <p className="mc-hero-foot helper">Not a NASA product; no endorsement implied. Results are modeled terrain evidence, not field validation.</p>
  </section>;
}
