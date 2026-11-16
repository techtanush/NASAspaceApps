import { BrandSymbol } from '../../components/ui/BrandSymbol';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import { MotionConfig, motion, useReducedMotion } from 'motion/react';
import { GlobeStage, type GlobeScene } from '../../maps/GlobeStage';
import { STEPS, useMissionControl, type StepId } from './state';
import { useWorkspaceSession } from '../../app/WorkspaceContext';

function stepFor(pathname: string): StepId | null {
  if (pathname.startsWith('/start/')) return (pathname.split('/')[2] as StepId) ?? null;
  return /\/runs\/[^/]+\/tour/.test(pathname) ? 'tour' : null;
}
function StepRail({ current }: { current: StepId }) {
  const { plan } = useMissionControl(); const index = STEPS.findIndex(step => step.id === current);
  const reachable = (id: StepId) => id === 'place' || (plan.confirmed && (id === 'mission' || (plan.objective.trim() !== '' && (id === 'rover' || ((plan.noRover || plan.roverRevisionId !== null) && id === 'review')))));
  return <nav className="mc-rail" aria-label="Progress" data-testid="step-rail"><ol>{STEPS.map((step, position) => {
    const state = position < index ? 'done' : position === index ? 'current' : 'next';
    const body = <><span className="mc-rail-mark" aria-hidden="true">{state === 'done' ? <Check size={12} strokeWidth={2.5}/> : position + 1}</span><span className="mc-rail-label">{step.label}</span></>;
    return <li key={step.id} data-state={state} data-step={step.id} aria-current={state === 'current' ? 'step' : undefined}>{step.path && current !== 'tour' && state !== 'current' && reachable(step.id) ? <NavLink to={step.path}>{body}</NavLink> : <span>{body}</span>}</li>;
  })}</ol></nav>;
}
function Stage() {
  const { scene, handlers } = useMissionControl(); const location = useLocation(); const step = stepFor(location.pathname);
  const navigate = useNavigate();
  const openSurfaceDetail = !/view=(regional|target)/.test(location.search) && ((scene.body === 'EARTH' && scene.selectedMarker && step === 'tour') || (scene.body !== 'EARTH' && scene.box && step === 'place'))
    ? () => { const query = new URLSearchParams(location.search); if (scene.body === 'EARTH') query.set('site',scene.selectedMarker!); query.set('view',scene.body === 'EARTH'?'regional':'target'); navigate(`${location.pathname}?${query}`,{replace:true}); }
    : undefined;
  const session=useWorkspaceSession();
  useEffect(() => { document.documentElement.dataset.stage = 'true'; return () => { delete document.documentElement.dataset.stage; }; }, []);
  return <div className="mc" data-theme="dark" data-testid="mission-control" data-layout={scene.layout ?? 'center'}>
    {scene.layout !== 'dashboard' && scene.layout !== 'landing' && <GlobeStage scene={scene} onPick={handlers.onPick} onMarkerSelect={handlers.onMarkerSelect} onSurfaceDetail={openSurfaceDetail}/>}
    <header className="mc-header"><Link to="/" reloadDocument={!session} className="wordmark"><BrandSymbol/>AnalogForge</Link>
      {session?.authMode === 'oidc' && <div className="mc-workspace-context" aria-label="Workspace context"><span>Workspace</span><strong>{session.role.charAt(0)+session.role.slice(1).toLowerCase()}</strong></div>}<nav className="mc-header-links" aria-label="Other views"><Link to="/workbench" reloadDocument={!session}>Evidence workbench</Link><Link to="/rovers" reloadDocument={!session}>Rovers</Link><Link to="/about" reloadDocument={!session}>About</Link></nav></header>
    <div className="mc-content" data-regional={/view=(regional|target)/.test(location.search) ? 'true' : 'false'}><Outlet/></div>
    {step && scene.layout !== 'dashboard' && <StepRail current={step}/>}
  </div>;
}
export function StageShell() { return <MotionConfig reducedMotion="user"><Stage/></MotionConfig>; }
/** Each screen declares what the globe should show while it is mounted. */
export function useScene(scene: GlobeScene, handlers: { onPick?: (lat: number, lng: number) => void; onMarkerSelect?: (id: string) => void } = {}) {
  const { setScene, setHandlers } = useMissionControl(); const key = JSON.stringify(scene);
  useEffect(() => { setScene(scene); }, [key]);
  useEffect(() => { setHandlers(handlers); return () => setHandlers({}); }, [handlers.onPick, handlers.onMarkerSelect]);
}
export function Panel({ title, step, lead, children, footer, notice, testid }: { title: string; step?: string; lead?: ReactNode; children: ReactNode; footer?: ReactNode; notice?: ReactNode; testid?: string }) {
  const reducedMotion = useReducedMotion();
  const body = useRef<HTMLDivElement>(null); const hasNotice = Boolean(notice);
  const [more, setMore] = useState(false);
  useEffect(() => {
    const element = body.current; if (!element) return;
    const update = () => setMore(element.scrollHeight - element.scrollTop - element.clientHeight > 20);
    update(); element.addEventListener('scroll', update, { passive: true });
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update);
    resize?.observe(element); for (const child of element.children) resize?.observe(child);
    return () => { element.removeEventListener('scroll', update); resize?.disconnect(); };
  }, [children]);
  useEffect(() => { if (hasNotice) body.current?.scrollTo({ top: 0, behavior: 'instant' }); }, [hasNotice]);
  return <motion.section className="mc-panel panel" data-theme="light" data-testid={testid} aria-labelledby="mc-panel-title" initial={reducedMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reducedMotion ? 0 : .22, ease: [.22, 1, .36, 1] }}>
    <header className="mc-panel-head">{step && <p className="mc-eyebrow">{step}</p>}<h1 id="mc-panel-title" tabIndex={-1}>{title}</h1>{lead && <p className="mc-lead">{lead}</p>}</header>
    <div className="mc-panel-body" ref={body} tabIndex={0} aria-label="Scroll for more mission details">{notice && <div className="mc-panel-notice">{notice}</div>}{children}</div>
    {more && <p className="mc-scroll-cue">More details below · scroll this panel ↓</p>}
    {footer && <footer className="mc-panel-foot">{footer}</footer>}
  </motion.section>;
}
export function Guide({ children }: { children: ReactNode }) {
  return <aside className="mc-guide" aria-label="Guide" data-testid="guide"><span className="mc-guide-mark" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor"/><path d="M1.5 9h15M9 1.5c2.6 2.4 2.6 12.6 0 15M9 1.5c-2.6 2.4-2.6 12.6 0 15" fill="none" stroke="currentColor"/></svg></span><p>{children}</p></aside>;
}
export function Choice<T extends string>({ label, value, options, onChange, testid }: { label: string; value: T; options: readonly { value: T; label: string }[]; onChange: (value: T) => void; testid?: string }) {
  return <div className="mc-choice" role="group" aria-label={label} data-testid={testid}>{options.map(option => <button key={option.value} type="button" aria-pressed={value === option.value} data-value={option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>;
}
