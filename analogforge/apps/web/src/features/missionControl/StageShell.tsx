import { useEffect, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Check } from 'lucide-react';
import { GlobeStage, type GlobeScene } from '../../maps/GlobeStage';
import { STEPS, useMissionControl, type StepId } from './state';

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
  useEffect(() => { document.documentElement.dataset.stage = 'true'; return () => { delete document.documentElement.dataset.stage; }; }, []);
  return <div className="mc" data-theme="dark" data-testid="mission-control" data-layout={scene.layout ?? 'center'}>
    <GlobeStage scene={scene} onPick={handlers.onPick} onMarkerSelect={handlers.onMarkerSelect}/>
    <header className="mc-header"><Link to="/" className="wordmark"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" stroke="currentColor" fill="none"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>AnalogForge</Link>
      <nav className="mc-header-links" aria-label="Other views"><Link to="/workbench">Evidence workbench</Link><Link to="/rovers">Rovers</Link><Link to="/about">About</Link></nav></header>
    <div className="mc-content" data-regional={/view=(regional|target)/.test(location.search) ? 'true' : 'false'}><Outlet/></div>
    {step && <StepRail current={step}/>}
  </div>;
}
export function StageShell() { return <Stage/>; }
/** Each screen declares what the globe should show while it is mounted. */
export function useScene(scene: GlobeScene, handlers: { onPick?: (lat: number, lng: number) => void; onMarkerSelect?: (id: string) => void } = {}) {
  const { setScene, setHandlers } = useMissionControl(); const key = JSON.stringify(scene);
  useEffect(() => { setScene(scene); }, [key]);
  useEffect(() => { setHandlers(handlers); return () => setHandlers({}); }, [handlers.onPick, handlers.onMarkerSelect]);
}
export function Panel({ title, step, lead, children, footer, testid }: { title: string; step?: string; lead?: ReactNode; children: ReactNode; footer?: ReactNode; testid?: string }) {
  return <section className="mc-panel panel" data-testid={testid} aria-labelledby="mc-panel-title">
    <header className="mc-panel-head">{step && <p className="mc-eyebrow">{step}</p>}<h1 id="mc-panel-title" tabIndex={-1}>{title}</h1>{lead && <p className="mc-lead">{lead}</p>}</header>
    <div className="mc-panel-body">{children}</div>
    {footer && <footer className="mc-panel-foot">{footer}</footer>}
  </section>;
}
export function Guide({ children }: { children: ReactNode }) {
  return <aside className="mc-guide" aria-label="Guide" data-testid="guide"><span className="mc-guide-mark" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor"/><path d="M1.5 9h15M9 1.5c2.6 2.4 2.6 12.6 0 15M9 1.5c-2.6 2.4-2.6 12.6 0 15" fill="none" stroke="currentColor"/></svg></span><p>{children}</p></aside>;
}
export function Choice<T extends string>({ label, value, options, onChange, testid }: { label: string; value: T; options: readonly { value: T; label: string }[]; onChange: (value: T) => void; testid?: string }) {
  return <div className="mc-choice" role="group" aria-label={label} data-testid={testid}>{options.map(option => <button key={option.value} type="button" aria-pressed={value === option.value} data-value={option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>;
}
