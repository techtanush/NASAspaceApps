import { useMissionControl } from './state';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowDown, MapPin, Target, Bot, Globe2, Route, FileText, Layers, ShieldCheck } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace, useWorkspaceSession } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { ModeBadge } from '../../components/ui';
import { BrandSymbol } from '../../components/ui/BrandSymbol';
import { useScene } from './StageShell';
import { GlobeStage, type GlobeScene } from '../../maps/GlobeStage';

const LANDING_SCENE: GlobeScene = { body: 'EARTH', autoRotate: false, layout: 'landing', focus: { lat: 18, lng: -40, altitude: 2.3 } };

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
  const reduced = useReducedMotion();
  useScene(LANDING_SCENE);
  const session = useWorkspaceSession();
  const workspace = useWorkspace(); const runs = useApi<Runs>(workspace, '/workspace/recent-runs?limit=4', Boolean(session));
  const recent = session ? runs.data?.items ?? [] : [];
  const reveal = { initial: reduced ? false as const : { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, amount: .15 }, transition: { duration: reduced ? 0 : .5 } };
  return <div className="mc-landing" data-testid="welcome" tabIndex={0} role="region" aria-label="Explore AnalogForge">
    <section className="mc-landing-hero" aria-labelledby="welcome-title"><GlobeStage scene={LANDING_SCENE}/><div className="mc-landing-copy">
    <div className="mc-hero-kicker"><BrandSymbol size={42}/><p className="mc-eyebrow">Planetary mission. Earth rehearsal.</p></div>
    <h1 id="welcome-title" tabIndex={-1}>A world away.<br/><span>Tested closer to home.</span></h1>
    <p className="mc-hero-lead">Find where on Earth to rehearse a mission to Mars or the Moon. Set the target, describe the objective and bring a rover. Follow the evidence to the right site for each benchmark.</p>
    <div className="mc-hero-actions"><Link className="button mc-cta" data-variant="primary" to="/start/place" reloadDocument={!session} data-testid="btn-begin" onClick={reset}>Enter AnalogForge<ArrowRight size={16} aria-hidden="true"/></Link><a className="button mc-case-link" href="/case-studies/gale-crater-flagstaff/">See the NASA terrain case study</a></div>
    <p className="mc-landing-access">Open exploration. No account required.</p>
    <p className="mc-hero-principle"><span aria-hidden="true"/>What Earth cannot reproduce stays visible.</p>
    <a className="mc-landing-scroll" href="#how-it-works">Explore the mission<ArrowDown size={16} aria-hidden="true"/></a>
    </div><p className="mc-landing-orbit-label"><span aria-hidden="true"/>Earth · your next rehearsal ground</p></section>

    <div className="mc-landing-details">
    <motion.section {...reveal} className="mc-landing-section" id="how-it-works" aria-labelledby="landing-method">
      <div className="mc-landing-heading"><p className="mc-eyebrow">01 / The investigation</p><h2 id="landing-method">One mission.<br/>A different job for every site.</h2><p>A slope rehearsal, a sampling traverse and an endurance test need different evidence. Start with your mission; compare sites against the capabilities you actually need.</p></div>
      <ol className="mc-landing-stages" aria-label="How it works">{STAGES.map(({ icon: Icon, title, text }, index) => <li key={title}><span className="mc-stage-index">0{index + 1}</span><Icon size={24} strokeWidth={1.4} aria-hidden="true"/><h3>{title}</h3><p>{text}</p></li>)}</ol>
    </motion.section>

    <motion.section {...reveal} className="mc-landing-section mc-landing-evidence" aria-labelledby="landing-evidence">
      <div className="mc-landing-heading"><p className="mc-eyebrow">02 / Follow the evidence</p><h2 id="landing-evidence">From planetary terrain<br/>to an Earth test plan.</h2><p>Watch the investigation progress, then explore the locations it returns. Every verdict connects to a requirement, a measurement and the limits of that comparison.</p></div>
      <div className="mc-landing-flow" aria-label="The evidence pipeline"><div><Target size={30} aria-hidden="true"/><strong>Mars or Moon</strong><span>Your target region + mission goals</span></div><ArrowRight aria-hidden="true"/><div><Layers size={30} aria-hidden="true"/><strong>Compare evidence</strong><span>Terrain, support scale + coverage</span></div><ArrowRight aria-hidden="true"/><div><MapPin size={30} aria-hidden="true"/><strong>Earth test sites</strong><span>Coordinates + capability benchmarks</span></div></div>
      <p className="mc-landing-caption">Searches cover the supplied datasets and candidate windows. A map image provides visual context; it does not establish terrain measurements or worldwide search coverage.</p>
    </motion.section>

    <motion.section {...reveal} className="mc-landing-section" aria-labelledby="landing-results">
      <div className="mc-landing-heading"><p className="mc-eyebrow">03 / Take it into the field</p><h2 id="landing-results">A location is only<br/>the beginning.</h2><p>Understand why a site was selected, what to rehearse there and which benchmark the rover must meet. Keep the simple overview, or open the technical evidence.</p></div>
      <div className="mc-landing-deliverables">{[
        {icon:Globe2,title:'Explore each location',text:'Rotate Earth, select a geographic pin and inspect satellite context for the actual candidate footprint.'},
        {icon:Route,title:'Rehearse a specific capability',text:'Inspect modeled routes, checkpoints and results when route evidence is available. Missing route evidence stays explicit.'},
        {icon:FileText,title:'Carry a professional field brief',text:'Download an executive summary, location-by-location procedures, benchmarks, graphs and a technical appendix.'},
      ].map(({icon:Icon,title,text})=><article key={title}><Icon size={24} strokeWidth={1.4} aria-hidden="true"/><h3>{title}</h3><p>{text}</p></article>)}</div>
    </motion.section>

    <motion.section {...reveal} className="mc-landing-section mc-landing-limits" aria-labelledby="landing-limits"><ShieldCheck size={30} strokeWidth={1.4} aria-hidden="true"/><div><p className="mc-eyebrow">Scientific honesty, built in</p><h2 id="landing-limits">Know what Earth can prove.<br/>And what it cannot.</h2><p>Gravity, atmosphere, radiation and other planetary conditions cannot be reproduced by choosing a similar landscape. AnalogForge keeps these gaps visible. A successful modeled rehearsal supports a bounded claim; it does not guarantee mission success.</p><p>Practice investigations are labeled synthetic. Live evidence retains its source, resolution and coverage limits. NASA orbital imagery and public Earth imagery are visual context, separate from the measured terrain used for qualification.</p><Link to="/about" reloadDocument={!session}>Explore the data and methodology<ArrowRight size={16} aria-hidden="true"/></Link></div></motion.section>

    {recent.length > 0 && <section className="mc-landing-section mc-recent" data-testid="recent-investigations"><h2>Continue an investigation</h2><ul>{recent.map(run => <RecentInvestigation key={run.id} run={run} workspace={workspace}/>)}</ul></section>}
    <section className="mc-landing-section mc-landing-final" aria-labelledby="landing-start"><p className="mc-eyebrow">Ready for the next world</p><h2 id="landing-start">Start with a place.<br/>Leave with a test plan.</h2><Link className="button mc-cta" data-variant="primary" to="/start/place" reloadDocument={!session} onClick={reset}>Start your investigation<ArrowRight size={16} aria-hidden="true"/></Link><Link className="mc-secondary-entry" to="/workbench" reloadDocument={!session}>Open mission library</Link></section>
    <footer className="mc-landing-footer"><strong><BrandSymbol size={24}/>AnalogForge</strong><p>Mission-conditioned qualification of Earth analogs for Mars and the Moon.</p><p>Not a NASA product; no endorsement implied. Modeled terrain evidence is not field validation.</p></footer>
    </div>
  </div>;
}
