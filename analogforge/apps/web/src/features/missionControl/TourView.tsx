import { api } from '../../api/client';
import type { components } from '../../generated/schema';
import { useRunAssurance } from './useRunAssurance';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, ExternalLink, Globe2, LayoutDashboard, Loader } from 'lucide-react';
import { Button, ConnectionIndicator, ErrorPanel, ModeBadge, ResultBadge, Skeleton, PublicationBadge } from '../../components/ui';
import type { GlobeMarker } from '../../maps/GlobeStage';
import { groupNearbyLocations } from '../../maps/globeMarkers';
import { Guide, Panel, useScene } from './StageShell';
import { useRunData } from './useRunData';
import { buildCoverage, buildSites, siteName, siteStatusSummary, STATUS_WORD, type Site } from './tour';
import { PROGRESS_STEPS, PROVING_LABEL, sentenceCase } from './narrator';
import { RegionalInspector, TargetInspector } from './RegionalInspector';
import { boxCentre, formatPlace } from './coordinates';
import { BenchmarkEvidence } from './BenchmarkEvidence';
import { RunActivity } from './RunActivity';
import { EnvironmentContext } from './EnvironmentContext';
import { EarthNomination } from './EarthNomination';
import { RunTerminalNotice } from './RunTerminalNotice';
import { SiteTestPurpose } from './SiteTestPurpose';
import { EvidenceBriefDownload } from './EvidenceBriefDownload';
import { ResultPresentation } from './ResultPresentation';
import { LocationOverview } from './LocationOverview';
import { SiteFieldPlan } from './SiteFieldPlan';

const ORIGIN: Record<string, string> = { KNOWN_CONTROL: 'Known control', DISCOVERED: 'Discovered', USER_SUPPLIED: 'Nominated', SYNTHETIC_CONTROL: 'Synthetic practice' };
const TERMINAL = ['FAILED', 'BLOCKED', 'CANCELLED'];
function LocalMap({ group, selected, onSelect }: { group: Site[]; selected: string; onSelect: (id: string) => void }) {
  const boxes = group.map(site => site.candidate.aoi.bbox as number[]); const west = Math.min(...boxes.map(box => box[0]!)), south = Math.min(...boxes.map(box => box[1]!)), east = Math.max(...boxes.map(box => box[2]!)), north = Math.max(...boxes.map(box => box[3]!));
  const spanX = east - west || 1, spanY = north - south || 1; const width = 320, height = Math.max(72, Math.min(200, Math.round((width * spanY) / spanX)));
  return <figure className="mc-localmap" data-testid="local-map"><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Arrangement of nearby sites, north up">{group.map(site => { const box = site.candidate.aoi.bbox as number[]; const x = ((box[0]! - west) / spanX) * width, y = ((north - box[3]!) / spanY) * height, w = Math.max(10, ((box[2]! - box[0]!) / spanX) * width), h = Math.max(10, ((box[3]! - box[1]!) / spanY) * height);
    return <g key={site.candidate.id} className="mc-localmap-site" data-status={site.status} data-selected={site.candidate.id === selected} onClick={() => onSelect(site.candidate.id)}><rect x={x + 1} y={y + 1} width={w - 2} height={h - 2}/><text x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="central">{site.index}</text></g>; })}</svg><figcaption className="helper">Separate nearby candidate footprints. North is up; this arrangement shows geometry rather than terrain imagery.</figcaption></figure>;
}
export function TourView() {
  const { runId } = useParams(); const run = useRunData(runId); const { snapshot, contract } = run; const assurance = useRunAssurance(snapshot, contract, run.rover);
  const sites = useMemo(() => (contract ? buildSites(run.candidates, contract.requirements, run.qualifications) : []), [contract, run.candidates, run.qualifications]);
  const coverage = useMemo(() => (contract ? buildCoverage(contract.requirements, sites) : []), [contract, sites]);
  const groups = useMemo(() => groupNearbyLocations(sites), [sites]);
  const [search, setSearch] = useSearchParams();
  const [selectionError, setSelectionError] = useState<unknown>(null);
  const selectedId = search.get('site') ?? search.get('candidate');
  const setSelectedId = useCallback((id: string) => setSearch(current => { current.set('site', id); current.set('view', 'regional'); return current; }, { replace: true }),[setSearch]);
  const regional = search.get('view') === 'regional'; const targetDetail = search.get('view') === 'target';
  const setView = (view: string) => setSearch(current => { if (view) current.set('view', view); else current.delete('view'); return current; });
  const dashboard = search.get('view') === 'dashboard' || search.get('view') === 'overview';
  const overview = dashboard || (!selectedId && !targetDetail);
  const showOverview = useCallback(() => setSearch(current => { current.delete('site'); current.delete('candidate'); current.set('view', 'globe'); return current; }, { replace: true }), [setSearch]);
  const showDashboard = () => setSearch(current => { current.delete('site'); current.delete('candidate'); current.set('view', 'dashboard'); return current; });
  const researching = !!snapshot && !TERMINAL.includes(snapshot.state) && !['COMPLETED', 'AWAITING_REVIEW'].includes(snapshot.state);
  const wasResearching = useRef(researching);
  useEffect(() => {
    if (wasResearching.current && !researching && sites.length) showOverview();
    wasResearching.current = researching;
  }, [researching, sites.length, showOverview]);
  const selected = sites.find(site => site.candidate.id === selectedId) ?? null; const group = selected ? groups.find(items => items.includes(selected)) ?? [selected] : [];
  const siteCard = useRef<HTMLElement>(null); const previousSite = useRef<string | null>(null);
  useEffect(() => {
    if (previousSite.current && previousSite.current !== selected?.candidate.id && siteCard.current) {
      const body = siteCard.current.closest('.mc-panel-body');
      if (body) body.scrollTop += siteCard.current.getBoundingClientRect().top - body.getBoundingClientRect().top;
    }
    previousSite.current = selected?.candidate.id ?? null;
  }, [selected?.candidate.id]);
  const markers = useMemo<GlobeMarker[]>(() => sites.map(site=>({id:site.candidate.id,lat:site.lat,lng:site.lng,label:siteName(site),status:site.status,index:site.index})), [sites]);
  const selectSite = (id:string) => { setSelectedId(id); };
  const onMarkerSelect = useCallback((id: string) => { setSelectedId(id); }, [setSelectedId]);
  const touring = sites.length > 0 && !researching; const target = contract ? boxCentre(contract.target.bbox) : null;
  const overviewFocus = sites[0];
  useScene(touring
    ? { body: 'EARTH', layout: dashboard ? 'dashboard' : 'panel', autoRotate: false, markers, selectedMarker: selected?.candidate.id ?? null, box: selected ? selected.candidate.aoi.bbox : null, focus: overview || !selected ? { lat: overviewFocus?.lat ?? 20, lng: overviewFocus?.lng ?? 0, altitude: 2.3 } : { lat: selected.lat, lng: selected.lng, altitude: 0.95 } }
    : { body: contract?.target.body ?? 'MARS', layout: 'panel', autoRotate: false, scanning: true, focus: target ? { ...target, altitude: 1.7 } : null, pin: target, box: contract ? contract.target.bbox : null }, { onMarkerSelect });
  if (run.error) return <Panel title="Investigation unavailable" testid="tour-error"><ErrorPanel error={run.error}/></Panel>;
  // New qualification IDs can arrive while their scoped records are fetching.
  // Keep the existing candidate map mounted so that live updates preserve its camera.
  if ((run.loading && sites.length === 0) || !snapshot || !contract) return <Panel title="Opening the investigation" testid="tour-loading"><Skeleton label="Retrieving the investigation"/></Panel>;
  if (selectedId && !sites.some(site => site.candidate.id === selectedId)) return <Panel title="Site unavailable"><p>This candidate is not part of the current run.</p><Button onClick={() => setSearch({})}>Return to site list</Button></Panel>;
  const badges = <span className="mc-run-status"><ModeBadge mode={snapshot.mode}/><span>{sentenceCase(snapshot.state)}</span><ConnectionIndicator connection={run.connection === 'connecting' ? 'reconnecting' : run.connection}/>{snapshot.passport_id && <span aria-label="Run publication assurance"><PublicationBadge publication={assurance.publication}/></span>}</span>;
  if (!touring) {
    const stopped = TERMINAL.includes(snapshot.state); const current = PROGRESS_STEPS.findIndex(step => (step.states as readonly string[]).includes(snapshot.state));
    return <Panel testid="run-progress" step="Investigation" title={snapshot.state === 'BLOCKED' ? 'Investigation paused' : stopped ? `Investigation ${sentenceCase(snapshot.state).toLowerCase()}` : snapshot.state === 'COMPLETED' ? 'No Earth sites were found' : 'Working on your investigation'} lead={contract.name} notice={stopped ? <RunTerminalNotice run={snapshot}/> : undefined}
      footer={<><Link to={`/runs/${snapshot.run_id}/target`}>Open evidence workbench</Link>{!stopped && snapshot.state !== 'COMPLETED' && <Button variant="secondary" data-testid="btn-cancel-run" disabled={run.pending} onClick={() => { void run.action({ action_type: 'CANCEL', expected_revision: snapshot.revision, payload: {} }); }}>Cancel</Button>}</>}>
      {badges}
      <Guide>{stopped ? 'The run stopped before a location plan was ready. Its recorded evidence and reason remain available in the workbench.' : 'Follow the investigation here. When this stage finishes, Earth opens with a numbered pin for each location and its saved results.'}</Guide>
      <ol className="mc-progress" data-testid="progress-steps" data-state={snapshot.state}>{PROGRESS_STEPS.map((step, index) => { const state = stopped ? 'next' : current >= 0 && index < current ? 'done' : index === current ? 'current' : 'next'; return <li key={step.label} data-state={state}><span className="mc-progress-mark" aria-hidden="true">{state === 'done' ? <Check size={12} strokeWidth={2.5}/> : state === 'current' ? <Loader size={12} className="mc-spin"/> : null}</span>{step.label}</li>; })}</ol>
      <RunActivity run={snapshot}/>
    </Panel>;
  }
  const position = selected ? sites.indexOf(selected) : 0; const step = (delta: number) => { const next = sites[(position + delta + sites.length) % sites.length]; if (next) setSelectedId(next.candidate.id); };
  const canProve = !!snapshot.rover_revision_id && (snapshot.pending_review?.allowed_actions.includes('PROVE_IT') ?? false);
  const prove = async (site: Site) => {
    let confirmed = snapshot;
    if (confirmed.selected_candidate_id !== site.candidate.id) {
      const ok = await run.action({ action_type: 'SELECT_CANDIDATE', expected_revision: confirmed.revision, payload: { candidate_id: site.candidate.id } });
      if (!ok) return;
      confirmed = await api.get<components['schemas']['RunSnapshot']>(`/runs/${snapshot.run_id}`);
    }
    if (confirmed.run_id !== snapshot.run_id || confirmed.workspace_id !== snapshot.workspace_id || confirmed.selected_candidate_id !== site.candidate.id || confirmed.state !== 'AWAITING_REVIEW' || !confirmed.rover_revision_id || !confirmed.pending_review?.allowed_actions.includes('PROVE_IT')) throw new Error('The selected location is not ready for a rover test. Wait for its evidence review to finish.');
    await run.action({ action_type: 'PROVE_IT', expected_revision: confirmed.revision, payload: { candidate_id: site.candidate.id } });
  };
  const working = PROVING_LABEL[snapshot.state] ?? PROGRESS_STEPS.find(step => (step.states as readonly string[]).includes(snapshot.state))?.label;
  const technical = !researching && search.get('detail') === 'technical';
  const changePresentation = (next: boolean) => setSearch(current => { if (next) current.set('detail', 'technical'); else current.delete('detail'); return current; }, { replace: true });
  if (overview) return <Panel testid="tour" step={`${sites.length} Earth locations · mission rehearsal plan`} title={dashboard ? 'Your location test plan' : 'Your Earth test locations'} lead={contract.name} notice={TERMINAL.includes(snapshot.state) ? <RunTerminalNotice run={snapshot}/> : undefined} footer={dashboard ? <><Button variant="secondary" onClick={showOverview}><Globe2 size={16} aria-hidden="true"/>Back to Earth</Button><EvidenceBriefDownload run={snapshot} candidateId={sites[0]!.candidate.id} allLocations/></> : <Button variant="primary" data-testid="btn-results-dashboard" onClick={() => setView('dashboard')}><LayoutDashboard size={16} aria-hidden="true"/>Open results dashboard</Button>}>
    {badges}
    {dashboard ? <LocationOverview sites={sites} coverage={coverage} hasRover={!!snapshot.rover_revision_id} onSelect={selectSite}/> : <section className="mc-earth-directory" aria-label="Earth location directory"><p>Choose a numbered pin or a location below. Open its satellite map, test procedure, benchmarks, and PDF.</p><p className="helper">Each pin connects to an exact site coordinate. Nearby pin labels spread apart so every location remains selectable.</p><ol>{sites.map(site => <li key={site.candidate.id}><button type="button" aria-label={`Inspect location ${site.index}`} onClick={() => selectSite(site.candidate.id)}><span className="mc-directory-number">{site.index}</span><span><strong>{siteName(site)}</strong><span className="helper">{siteStatusSummary(site)}</span></span><ChevronRight size={16} aria-hidden="true"/></button></li>)}</ol><p className="helper">These are candidate rehearsal sites from the screened search area. Real imagery does not make synthetic measurements real; the data mode remains shown above.</p></section>}
    <details className="mc-activity-disclosure"><summary>Investigation work log</summary><RunActivity run={snapshot}/></details>
  </Panel>;
  return <>{regional && selected && <RegionalInspector runId={snapshot.run_id} site={selected} run={snapshot}/ >}{targetDetail && <TargetInspector runId={snapshot.run_id} profileId={snapshot.target_profile_id} target={contract.target} run={snapshot}/>}<Panel testid="tour" step={`Location ${position + 1} of ${sites.length}`} title={selected ? siteName(selected) : 'Earth locations'} lead={contract.name} notice={TERMINAL.includes(snapshot.state) ? <RunTerminalNotice run={snapshot}/> : undefined}
    footer={<><div className="mc-tour-nav" role="group" aria-label="Tour"><Button variant="secondary" aria-label="Previous site" data-testid="btn-prev-site" onClick={() => step(-1)}><ChevronLeft size={16} aria-hidden="true"/></Button><span className="mono" data-testid="tour-position">{position + 1} / {sites.length}</span><Button variant="secondary" aria-label="Next site" data-testid="btn-next-site" onClick={() => step(1)}><ChevronRight size={16} aria-hidden="true"/></Button></div>
      <Button variant="ghost" data-testid="btn-all-sites" onClick={showOverview}><Globe2 size={16} aria-hidden="true"/>All locations</Button></>}>
    {badges}
    {!researching && <ResultPresentation technical={technical} onChange={changePresentation}/>}
    {assurance.error && <ErrorPanel error={assurance.error}/>}
    <div className="mc-view-switch" role="group" aria-label="Evidence view"><Button variant="secondary" aria-pressed={!regional && !targetDetail} onClick={() => setView('globe')}>Globe</Button><Button variant="secondary" aria-label="Inspect location" aria-pressed={regional} onClick={() => setView('regional')}>Site detail</Button><Button variant="secondary" aria-label="Target evidence" aria-pressed={targetDetail} onClick={() => setView('target')}>Target</Button></div>
    <Button variant="secondary" onClick={showDashboard}><LayoutDashboard size={16} aria-hidden="true"/>Results dashboard</Button>
    {researching && <div className="mc-research-status" role="status"><p className="mc-working-line"><Loader size={14} className="mc-spin" aria-hidden="true"/>{working ?? 'Research is still running'}</p><p>Candidate locations are provisional while the remaining evidence is checked. Follow the work log for each recorded operation.</p></div>}
    <details className="mc-activity-disclosure" open={researching || technical || undefined}><summary>Investigation work log</summary><RunActivity run={snapshot}/></details>
    {selected && <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="site-selection-announcement">Site {selected.index} of {sites.length}: {selected.candidate.name}. {STATUS_WORD[selected.status]}.</p>}
    {selected && <article ref={siteCard} className="mc-site-card" data-testid="site-card" data-status={selected.status} aria-label={`Site ${selected.index}`}>
      <header><p className="mono">{formatPlace(selected.lat, selected.lng)} · {ORIGIN[selected.candidate.origin] ?? selected.candidate.origin}</p><span className="mc-site-status" data-status={selected.status}>{siteStatusSummary(selected)}</span></header>
      <div className="mc-site-actions mc-location-exports"><EvidenceBriefDownload key={selected.candidate.id} run={snapshot} candidateId={selected.candidate.id}/><a className="button" data-variant="secondary" data-testid="link-report" href={`/runs/${snapshot.run_id}/report?site=${selected.candidate.id}`} target="_blank" rel="noreferrer">Location report<ExternalLink size={14} aria-hidden="true"/></a></div>
      <SiteTestPurpose site={selected}/>
      <div className="mc-site-actions mc-primary-test-action">{snapshot.rover_revision_id ? <><Button variant="primary" data-testid="link-prove" disabled={run.pending || snapshot.state !== 'AWAITING_REVIEW' || !canProve} onClick={() => { setSelectionError(null); void prove(selected).catch(setSelectionError); }}>{researching ? 'Rover model running…' : 'Run rover test here'}</Button><p className="helper">{canProve ? 'Design and independently verify this location’s route. Stay here to follow progress; this is a model, not a physical rover trial.' : snapshot.state === 'COMPLETED' ? 'The run is complete. Its recorded route and results remain below; start a new investigation for another test.' : 'The next test becomes available after its required evidence review.'}</p></> : <p className="helper">No rover supplied: this investigation compares site evidence only.</p>}</div>
      {!researching && <details className="mc-benchmark-details" open={technical || undefined}><summary>Start, checkpoints, and field procedure</summary><SiteFieldPlan runId={snapshot.run_id} candidateId={selected.candidate.id} revision={snapshot.revision}/></details>}
      <section className="mc-site-benchmarks" aria-label="Benchmarks and measured results"><h2>Benchmarks and measured results</h2><BenchmarkEvidence run={snapshot} contract={contract} site={selected} technical={technical}/></section>
      <details className="mc-benchmark-details" open={technical || undefined}><summary>Weather and operating context</summary><EnvironmentContext run={snapshot} candidateId={selected.candidate.id}/></details>
      {selected.candidate.limitations.length > 0 && <details className="mc-benchmark-details" key={`limits-${selected.candidate.id}`} open={technical || undefined}><summary>Source and model limits ({selected.candidate.limitations.length})</summary><ul className="mc-limits">{selected.candidate.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
      {run.results.length > 0 && <details className="mc-benchmark-details" open={technical || undefined}><summary>Run-level rover test attempts ({run.results.length})</summary><p className="helper">These attempts belong to the run; they are not attributed to the currently viewed site.</p><ol className="mc-attempts" data-testid="attempts">{run.results.map((result, index) => <li key={result.id}><span className="mono">Attempt {index + 1}</span><ResultBadge outcome={result.outcome}/>{result.failure_category && <span className="helper">{sentenceCase(result.failure_category)} problem</span>}</li>)}</ol></details>}
      <div className="mc-site-actions">
        <Link className="button" data-variant="ghost" to={`/runs/${snapshot.run_id}/qualification?candidate=${selected.candidate.id}`}>Evidence workbench</Link>
      </div>
      {(run.actionError ?? selectionError) != null && <ErrorPanel error={run.actionError ?? selectionError}/>}
    </article>}
    <details className="mc-coverage-strip" data-testid="coverage-strip" aria-label="Which site tests each requirement"><summary>Requirement coverage · {coverage.filter(row => row.state === 'COVERED').length} of {coverage.length} supported</summary><ul>{coverage.map(row => <li key={row.requirement.id} data-state={row.state}><span>{row.requirement.label}</span><strong>{row.state === 'COVERED' ? row.sites.map(site => `Site ${site.index}`).join(', ') : row.state === 'GAP' ? 'Not testable on Earth' : 'No site yet'}</strong></li>)}</ul></details>
    <details className="mc-portfolio" aria-label="Benchmark-specific rehearsal portfolio"><summary>Plan a rehearsal across several locations</summary><p className="helper">Different sites can support different requirements. A computed portfolio records those assignments and remaining gaps. Requirements that must happen together cannot be combined across separate locations.</p><div className="mc-site-actions"><Button variant="secondary" disabled={run.pending||snapshot.state!=='AWAITING_REVIEW'} disabledReason="Portfolio assembly is available when the investigation awaits review." onClick={()=>{void run.action({action_type:'BUILD_PORTFOLIO',expected_revision:snapshot.revision,payload:{candidate_ids:snapshot.candidate_ids,max_sites:3}});}}>Build rehearsal portfolio</Button><Link to={`/runs/${snapshot.run_id}/portfolio`}>Inspect portfolio{snapshot.portfolio_ids.length>0?` (${snapshot.portfolio_ids.length})`:''}</Link></div></details>
    <details className="mc-benchmark-details"><summary>Suggest another Earth location</summary><EarthNomination key={snapshot.run_id} run={snapshot} action={run.action} pending={run.pending} error={run.actionError}/></details>
    {group.length > 1 && selected && <details className="mc-nearby"><summary>{group.length} nearby footprints</summary><LocalMap group={group} selected={selected.candidate.id} onSelect={selectSite}/></details>}
    <ul className="mc-site-list" data-testid="site-list" aria-label="Sites">{sites.map(site => <li key={site.candidate.id}><button type="button" data-testid="site-chip" data-status={site.status} aria-pressed={site === selected} onClick={() => selectSite(site.candidate.id)}><span className="mc-ticker-index">{site.index}</span>{siteName(site)}</button></li>)}</ul>
    <details className="mc-benchmark-details" open={technical || undefined}><summary>Run details and provenance</summary><PublicationBadge publication={assurance.publication}/><p className="helper">Search scope: areas covered by this investigation’s terrain data and screened candidate windows.</p><p className="mono">Run {snapshot.run_id} · revision {snapshot.revision}</p><p className="mono">Dataset lock: {snapshot.dataset_lock_id}</p><Link to={`/runs/${snapshot.run_id}/target`}>Open evidence workbench</Link></details>

  </Panel></>;
}
