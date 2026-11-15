import { api } from '../../api/client';
import type { components } from '../../generated/schema';
import { useRunAssurance } from './useRunAssurance';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, ExternalLink, Globe2, Loader } from 'lucide-react';
import { Button, ConnectionIndicator, ErrorPanel, ModeBadge, ResultBadge, Skeleton, PublicationBadge } from '../../components/ui';
import type { GlobeMarker } from '../../maps/GlobeStage';
import { groupNearbyLocations } from '../../maps/globeMarkers';
import { Guide, Panel, useScene } from './StageShell';
import { useRunData } from './useRunData';
import { buildCoverage, buildSites, STATUS_WORD, type Site } from './tour';
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

const ORIGIN: Record<string, string> = { KNOWN_CONTROL: 'Known control', DISCOVERED: 'Discovered', USER_SUPPLIED: 'Nominated', SYNTHETIC_CONTROL: 'Synthetic practice' };
const TERMINAL = ['FAILED', 'BLOCKED', 'CANCELLED'];
function LocalMap({ group, selected, onSelect }: { group: Site[]; selected: string; onSelect: (id: string) => void }) {
  const boxes = group.map(site => site.candidate.aoi.bbox as number[]); const west = Math.min(...boxes.map(box => box[0]!)), south = Math.min(...boxes.map(box => box[1]!)), east = Math.max(...boxes.map(box => box[2]!)), north = Math.max(...boxes.map(box => box[3]!));
  const spanX = east - west || 1, spanY = north - south || 1; const width = 320, height = Math.max(72, Math.min(200, Math.round((width * spanY) / spanX)));
  return <figure className="mc-localmap" data-testid="local-map"><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Arrangement of nearby sites, north up">{group.map(site => { const box = site.candidate.aoi.bbox as number[]; const x = ((box[0]! - west) / spanX) * width, y = ((north - box[3]!) / spanY) * height, w = Math.max(10, ((box[2]! - box[0]!) / spanX) * width), h = Math.max(10, ((box[3]! - box[1]!) / spanY) * height);
    return <g key={site.candidate.id} className="mc-localmap-site" data-status={site.status} data-selected={site.candidate.id === selected} onClick={() => onSelect(site.candidate.id)}><rect x={x + 1} y={y + 1} width={w - 2} height={h - 2}/><text x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="central">{site.index}</text></g>; })}</svg><figcaption className="helper">Separate nearby candidate footprints. North is up; this arrangement shows geometry rather than terrain imagery.</figcaption></figure>;
}
export function TourView() {
  const navigate = useNavigate();
  const { runId } = useParams(); const run = useRunData(runId); const { snapshot, contract } = run; const assurance = useRunAssurance(snapshot, contract, run.rover);
  const sites = useMemo(() => (contract ? buildSites(run.candidates, contract.requirements, run.qualifications) : []), [contract, run.candidates, run.qualifications]);
  const coverage = useMemo(() => (contract ? buildCoverage(contract.requirements, sites) : []), [contract, sites]);
  const groups = useMemo(() => groupNearbyLocations(sites), [sites]);
  const [search, setSearch] = useSearchParams();
  const [selectionError, setSelectionError] = useState<unknown>(null);
  const selectedId = search.get('site') ?? search.get('candidate');
  const setSelectedId = useCallback((id: string) => setSearch(current => { current.set('site', id); current.set('view', 'regional'); return current; }, { replace: true }),[setSearch]);
  const regional = search.get('view') === 'regional'; const targetDetail = search.get('view') === 'target';
  const setView = (view: string) => setSearch(current => { if (view) current.set('view', view); else current.delete('view'); return current; }); const [overview, setOverview] = useState(false);
  useEffect(() => { if (sites.length > 0 && (!selectedId || !search.has('view'))) setSelectedId(selectedId ?? sites[0]!.candidate.id); }, [sites, selectedId, search, setSelectedId]);
  const selected = sites.find(site => site.candidate.id === selectedId) ?? null; const group = selected ? groups.find(items => items.includes(selected)) ?? [selected] : [];
  const siteCard = useRef<HTMLElement>(null); const previousSite = useRef<string | null>(null);
  useEffect(() => {
    if (previousSite.current && previousSite.current !== selected?.candidate.id && siteCard.current) {
      const body = siteCard.current.closest('.mc-panel-body');
      if (body) body.scrollTop += siteCard.current.getBoundingClientRect().top - body.getBoundingClientRect().top;
    }
    previousSite.current = selected?.candidate.id ?? null;
  }, [selected?.candidate.id]);
  const markers = useMemo<GlobeMarker[]>(() => sites.map(site=>({id:site.candidate.id,lat:site.lat,lng:site.lng,label:site.candidate.name,status:site.status,index:site.index})), [sites]);
  const selectSite = (id:string) => { setSelectedId(id); setOverview(false); };
  const onMarkerSelect = useCallback((id: string) => { setSelectedId(id); setOverview(false); }, [setSelectedId]);
  const touring = sites.length > 0; const target = contract ? boxCentre(contract.target.bbox) : null;
  const groupMarker = selected ? markers.find(marker => marker.id === selected.candidate.id) : undefined;
  useScene(touring
    ? { body: 'EARTH', layout: 'panel', autoRotate: false, markers, selectedMarker: selected?.candidate.id ?? null, box: selected ? selected.candidate.aoi.bbox : null, focus: overview || !selected ? { lat: 20, lng: groupMarker?.lng ?? 0, altitude: 2.3 } : { lat: selected.lat, lng: selected.lng, altitude: 0.95 } }
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
      <Guide>{stopped ? 'The run stopped before any Earth site was assessed. The reason is recorded in the evidence workbench.' : 'AnalogForge is measuring the target and screening Earth terrain. This view updates by itself.'}</Guide>
      <ol className="mc-progress" data-testid="progress-steps" data-state={snapshot.state}>{PROGRESS_STEPS.map((step, index) => { const state = stopped ? 'next' : current >= 0 && index < current ? 'done' : index === current ? 'current' : 'next'; return <li key={step.label} data-state={state}><span className="mc-progress-mark" aria-hidden="true">{state === 'done' ? <Check size={12} strokeWidth={2.5}/> : state === 'current' ? <Loader size={12} className="mc-spin"/> : null}</span>{step.label}</li>; })}</ol>
      <RunActivity run={snapshot}/>
    </Panel>;
  }
  const position = selected ? sites.indexOf(selected) : 0; const step = (delta: number) => { const next = sites[(position + delta + sites.length) % sites.length]; if (next) { setSelectedId(next.candidate.id); setOverview(false); } };
  const canProve = !!snapshot.rover_revision_id && (snapshot.pending_review?.allowed_actions.includes('PROVE_IT') ?? false);
  const prove = async (site: Site) => { if (snapshot.selected_candidate_id !== site.candidate.id) { const ok = await run.action({ action_type: 'SELECT_CANDIDATE', expected_revision: snapshot.revision, payload: { candidate_id: site.candidate.id } }); if (!ok) throw new Error('Selection was not confirmed'); const confirmed = await api.get<components['schemas']['RunSnapshot']>(`/runs/${snapshot.run_id}`); if (confirmed.selected_candidate_id !== site.candidate.id) throw new Error('Site selection is still pending. Wait for the investigation to update, then retry.'); } };
  const working = PROVING_LABEL[snapshot.state] ?? PROGRESS_STEPS.find(step => (step.states as readonly string[]).includes(snapshot.state))?.label;
  const researching = !TERMINAL.includes(snapshot.state) && !['COMPLETED', 'AWAITING_REVIEW'].includes(snapshot.state);
  const technical = !researching && search.get('detail') === 'technical';
  const changePresentation = (next: boolean) => setSearch(current => { if (next) current.set('detail', 'technical'); else current.delete('detail'); return current; }, { replace: true });
  return <>{regional && selected && <RegionalInspector runId={snapshot.run_id} site={selected} run={snapshot}/ >}{targetDetail && <TargetInspector runId={snapshot.run_id} profileId={snapshot.target_profile_id} target={contract.target} run={snapshot}/>}<Panel testid="tour" step={`Location ${position + 1} of ${sites.length}`} title={selected?.candidate.name ?? 'Earth locations'} lead={contract.name} notice={TERMINAL.includes(snapshot.state) ? <RunTerminalNotice run={snapshot}/> : undefined}
    footer={<><div className="mc-tour-nav" role="group" aria-label="Tour"><Button variant="secondary" aria-label="Previous site" data-testid="btn-prev-site" onClick={() => step(-1)}><ChevronLeft size={16} aria-hidden="true"/></Button><span className="mono" data-testid="tour-position">{position + 1} / {sites.length}</span><Button variant="secondary" aria-label="Next site" data-testid="btn-next-site" onClick={() => step(1)}><ChevronRight size={16} aria-hidden="true"/></Button></div>
      <Button variant="ghost" aria-pressed={overview} data-testid="btn-all-sites" onClick={() => { if (overview) { setView('regional'); setOverview(false); } else { setView('globe'); setOverview(true); } }}><Globe2 size={16} aria-hidden="true"/>{overview ? 'Back to site' : 'Whole Earth'}</Button></>}>
    {badges}
    {!researching && <ResultPresentation technical={technical} onChange={changePresentation}/>}
    {assurance.error && <ErrorPanel error={assurance.error}/>}
    <div className="mc-view-switch" role="group" aria-label="Evidence view"><Button variant="secondary" aria-pressed={!regional && !targetDetail} onClick={() => { setView('globe'); setOverview(false); }}>Globe</Button><Button variant="secondary" aria-label="Inspect location" aria-pressed={regional} onClick={() => { setView('regional'); setOverview(false); }}>Site detail</Button><Button variant="secondary" aria-label="Target evidence" aria-pressed={targetDetail} onClick={() => setView('target')}>Target</Button></div>
    {!regional && !targetDetail && groups.some(items => items.length > 1) && <p className="helper">Nearby globe markers are grouped for readability. Choose an individual location from the site list or use Previous / Next; each has its own map, benchmarks and report.</p>}
    {researching && <div className="mc-research-status" role="status"><p className="mc-working-line"><Loader size={14} className="mc-spin" aria-hidden="true"/>{working ?? 'Research is still running'}</p><p>Candidate locations are provisional while the remaining evidence is checked. Follow the work log for each recorded operation.</p></div>}
    <details className="mc-activity-disclosure" open={researching || technical || undefined}><summary>Investigation work log</summary><RunActivity run={snapshot}/></details>
    {selected && <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="site-selection-announcement">Site {selected.index} of {sites.length}: {selected.candidate.name}. {STATUS_WORD[selected.status]}.</p>}
    {selected && <article ref={siteCard} className="mc-site-card" data-testid="site-card" data-status={selected.status} aria-label={`Site ${selected.index}`}>
      <header><p className="mono">{formatPlace(selected.lat, selected.lng)} · {ORIGIN[selected.candidate.origin] ?? selected.candidate.origin}</p><span className="mc-site-status" data-status={selected.status}>{STATUS_WORD[selected.status]}</span></header>
      <SiteTestPurpose site={selected}/>
      <section className="mc-site-benchmarks" aria-label="Benchmarks and measured results"><h2>Benchmarks and measured results</h2><BenchmarkEvidence run={snapshot} contract={contract} site={selected} technical={technical}/></section>
      <details className="mc-benchmark-details" open={technical || undefined}><summary>Weather and operating context</summary><EnvironmentContext run={snapshot} candidateId={selected.candidate.id}/></details>
      {selected.candidate.limitations.length > 0 && <details className="mc-benchmark-details" key={`limits-${selected.candidate.id}`} open={technical || undefined}><summary>Source and model limits ({selected.candidate.limitations.length})</summary><ul className="mc-limits">{selected.candidate.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
      {run.results.length > 0 && <details className="mc-benchmark-details" open={technical || undefined}><summary>Run-level rover test attempts ({run.results.length})</summary><p className="helper">These attempts belong to the run; they are not attributed to the currently viewed site.</p><ol className="mc-attempts" data-testid="attempts">{run.results.map((result, index) => <li key={result.id}><span className="mono">Attempt {index + 1}</span><ResultBadge outcome={result.outcome}/>{result.failure_category && <span className="helper">{sentenceCase(result.failure_category)} problem</span>}</li>)}</ol></details>}
      <div className="mc-site-actions">
        <a className="button" data-variant="primary" data-testid="link-report" href={`/runs/${snapshot.run_id}/report?site=${selected.candidate.id}`} target="_blank" rel="noreferrer">Location report<ExternalLink size={14} aria-hidden="true"/></a>
        {snapshot.rover_revision_id ? <button type="button" className="button" data-variant="primary" data-testid="link-prove" disabled={run.pending} onClick={() => { setSelectionError(null); void prove(selected).then(() => { navigate(`/runs/${snapshot.run_id}/test-lab`); }).catch(setSelectionError); }}>Open rover test</button> : <p className="helper">No rover supplied: route benchmarks are not run.</p>}
        <Link className="button" data-variant="ghost" to={`/runs/${snapshot.run_id}/qualification?candidate=${selected.candidate.id}`}>Evidence workbench</Link>
      </div>
      <EvidenceBriefDownload key={selected.candidate.id} run={snapshot} candidateId={selected.candidate.id}/>
      {!canProve && snapshot.rover_revision_id && <p className="helper">The rover test opens in the evidence workbench.</p>}
      {(run.actionError ?? selectionError) != null && <ErrorPanel error={run.actionError ?? selectionError}/>}
    </article>}
    <details className="mc-coverage-strip" data-testid="coverage-strip" aria-label="Which site tests each requirement"><summary>Requirement coverage · {coverage.filter(row => row.state === 'COVERED').length} of {coverage.length} supported</summary><ul>{coverage.map(row => <li key={row.requirement.id} data-state={row.state}><span>{row.requirement.label}</span><strong>{row.state === 'COVERED' ? row.sites.map(site => `Site ${site.index}`).join(', ') : row.state === 'GAP' ? 'Not testable on Earth' : 'No site yet'}</strong></li>)}</ul></details>
    <details className="mc-portfolio" aria-label="Benchmark-specific rehearsal portfolio"><summary>Plan a rehearsal across several locations</summary><p className="helper">Different sites can support different requirements. A computed portfolio records those assignments and remaining gaps. Requirements that must happen together cannot be combined across separate locations.</p><div className="mc-site-actions"><Button variant="secondary" disabled={run.pending||snapshot.state!=='AWAITING_REVIEW'} disabledReason="Portfolio assembly is available when the investigation awaits review." onClick={()=>{void run.action({action_type:'BUILD_PORTFOLIO',expected_revision:snapshot.revision,payload:{candidate_ids:snapshot.candidate_ids,max_sites:3}});}}>Build rehearsal portfolio</Button><Link to={`/runs/${snapshot.run_id}/portfolio`}>Inspect portfolio{snapshot.portfolio_ids.length>0?` (${snapshot.portfolio_ids.length})`:''}</Link></div></details>
    <details className="mc-benchmark-details"><summary>Suggest another Earth location</summary><EarthNomination key={snapshot.run_id} run={snapshot} action={run.action} pending={run.pending} error={run.actionError}/></details>
    {group.length > 1 && selected && <details className="mc-nearby"><summary>{group.length} nearby footprints</summary><LocalMap group={group} selected={selected.candidate.id} onSelect={selectSite}/></details>}
    <ul className="mc-site-list" data-testid="site-list" aria-label="Sites">{sites.map(site => <li key={site.candidate.id}><button type="button" data-testid="site-chip" data-status={site.status} aria-pressed={site === selected} onClick={() => selectSite(site.candidate.id)}><span className="mc-ticker-index">{site.index}</span>{site.candidate.name}</button></li>)}</ul>
    <details className="mc-benchmark-details" open={technical || undefined}><summary>Run details and provenance</summary><PublicationBadge publication={assurance.publication}/><p className="helper">Search scope: areas covered by this investigation’s terrain data and screened candidate windows.</p><p className="mono">Run {snapshot.run_id} · revision {snapshot.revision}</p><p className="mono">Dataset lock: {snapshot.dataset_lock_id}</p><Link to={`/runs/${snapshot.run_id}/target`}>Open evidence workbench</Link></details>

  </Panel></>;
}
