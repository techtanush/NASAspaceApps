import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, ExternalLink, Globe2, Loader } from 'lucide-react';
import { Button, ConnectionIndicator, ErrorPanel, ModeBadge, ResultBadge, Skeleton, StatusBadge } from '../../components/ui';
import type { GlobeMarker } from '../../maps/GlobeStage';
import { Guide, Panel, useScene } from './StageShell';
import { useRunData } from './useRunData';
import { benchmarkText, buildCoverage, buildSites, ORIGIN_LABEL, STATUS_WORD, type Site } from './tour';
import { narrateSite, PROGRESS_STEPS, PROVING_LABEL, sentenceCase } from './narrator';
import { boxCentre, formatPlace } from './coordinates';

const ORIGIN: Record<string, string> = { KNOWN_CONTROL: 'Known control', DISCOVERED: 'Discovered', USER_SUPPLIED: 'Nominated', SYNTHETIC_CONTROL: 'Synthetic practice' };
const TERMINAL = ['FAILED', 'BLOCKED', 'CANCELLED'];
/** Sites closer together than this share one globe ticker; the panel shows their local arrangement. */
const CLUSTER_DEG = 1.5;
function clusters(sites: Site[]): Site[][] {
  const groups: Site[][] = [];
  for (const site of sites) { const home = groups.find(group => Math.abs(group[0]!.lat - site.lat) < CLUSTER_DEG && Math.abs(group[0]!.lng - site.lng) < CLUSTER_DEG); if (home) home.push(site); else groups.push([site]); }
  return groups;
}
const BEST = ['PASS', 'PARTIAL', 'UNKNOWN', 'GAP', 'FAIL'];
function LocalMap({ group, selected, onSelect }: { group: Site[]; selected: string; onSelect: (id: string) => void }) {
  const boxes = group.map(site => site.candidate.aoi.bbox as number[]); const west = Math.min(...boxes.map(box => box[0]!)), south = Math.min(...boxes.map(box => box[1]!)), east = Math.max(...boxes.map(box => box[2]!)), north = Math.max(...boxes.map(box => box[3]!));
  const spanX = east - west || 1, spanY = north - south || 1; const width = 320, height = Math.max(72, Math.min(200, Math.round((width * spanY) / spanX)));
  return <figure className="mc-localmap" data-testid="local-map"><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Arrangement of nearby sites, north up">{group.map(site => { const box = site.candidate.aoi.bbox as number[]; const x = ((box[0]! - west) / spanX) * width, y = ((north - box[3]!) / spanY) * height, w = Math.max(10, ((box[2]! - box[0]!) / spanX) * width), h = Math.max(10, ((box[3]! - box[1]!) / spanY) * height);
    return <g key={site.candidate.id} className="mc-localmap-site" data-status={site.status} data-selected={site.candidate.id === selected} onClick={() => onSelect(site.candidate.id)}><rect x={x + 1} y={y + 1} width={w - 2} height={h - 2}/><text x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="central">{site.index}</text></g>; })}</svg><figcaption className="helper">These sites are close together, so they share one marker on the globe. North is up.</figcaption></figure>;
}
export function TourView() {
  const { runId } = useParams(); const run = useRunData(runId); const { snapshot, contract } = run;
  const sites = useMemo(() => (contract ? buildSites(run.candidates, contract.requirements, run.qualifications) : []), [contract, run.candidates, run.qualifications]);
  const coverage = useMemo(() => (contract ? buildCoverage(contract.requirements, sites) : []), [contract, sites]);
  const groups = useMemo(() => clusters(sites), [sites]);
  const [selectedId, setSelectedId] = useState<string | null>(null); const [overview, setOverview] = useState(false);
  useEffect(() => { if (sites.length > 0 && !sites.some(site => site.candidate.id === selectedId)) setSelectedId(sites[0]!.candidate.id); }, [sites, selectedId]);
  const selected = sites.find(site => site.candidate.id === selectedId) ?? null; const group = selected ? groups.find(items => items.includes(selected)) ?? [selected] : [];
  const markers = useMemo<GlobeMarker[]>(() => groups.map(items => { const lead = items[0]!; const status = BEST.find(level => items.some(site => site.status === level)) ?? 'UNKNOWN';
    return { id: lead.candidate.id, lat: items.reduce((sum, site) => sum + site.lat, 0) / items.length, lng: items.reduce((sum, site) => sum + site.lng, 0) / items.length, label: items.length === 1 ? lead.candidate.name : `${items.length} sites`, status, index: items.length === 1 ? lead.index : items.length }; }), [groups]);
  const onMarkerSelect = useCallback((id: string) => { setSelectedId(id); setOverview(false); }, []);
  const touring = sites.length > 0; const target = contract ? boxCentre(contract.target.bbox) : null;
  const groupMarker = group[0] ? markers.find(marker => marker.id === group[0]!.candidate.id) : undefined;
  useScene(touring
    ? { body: 'EARTH', layout: 'panel', autoRotate: false, markers, selectedMarker: groupMarker?.id ?? null, focus: overview || !groupMarker ? { lat: 20, lng: groupMarker?.lng ?? 0, altitude: 2.3 } : { lat: groupMarker.lat, lng: groupMarker.lng, altitude: 1.5 } }
    : { body: contract?.target.body ?? 'MARS', layout: 'panel', autoRotate: false, scanning: true, focus: target ? { ...target, altitude: 1.7 } : null, pin: target, box: contract ? contract.target.bbox : null }, { onMarkerSelect });
  if (run.error) return <Panel title="Investigation unavailable" testid="tour-error"><ErrorPanel error={run.error}/></Panel>;
  if (run.loading || !snapshot || !contract) return <Panel title="Opening the investigation" testid="tour-loading"><Skeleton label="Retrieving the investigation"/></Panel>;
  const badges = <span className="mc-badges"><ModeBadge mode={snapshot.mode}/><ConnectionIndicator connection={run.connection === 'connecting' ? 'reconnecting' : run.connection}/></span>;
  if (!touring) {
    const stopped = TERMINAL.includes(snapshot.state); const current = PROGRESS_STEPS.findIndex(step => (step.states as readonly string[]).includes(snapshot.state));
    return <Panel testid="run-progress" step="Investigation" title={stopped ? `Investigation ${sentenceCase(snapshot.state).toLowerCase()}` : snapshot.state === 'COMPLETED' ? 'No Earth sites were found' : 'Working on your investigation'} lead={contract.name}
      footer={<><Link to={`/runs/${snapshot.run_id}/target`}>Open evidence workbench</Link>{!stopped && snapshot.state !== 'COMPLETED' && <Button variant="secondary" data-testid="btn-cancel-run" disabled={run.pending} onClick={() => { void run.action({ action_type: 'CANCEL', expected_revision: snapshot.revision, payload: {} }); }}>Cancel</Button>}</>}>
      {badges}
      <Guide>{stopped ? 'The run stopped before any Earth site was assessed. The reason is recorded in the evidence workbench.' : 'AnalogForge is measuring the target and screening Earth terrain. This view updates by itself.'}</Guide>
      <ol className="mc-progress" data-testid="progress-steps" data-state={snapshot.state}>{PROGRESS_STEPS.map((step, index) => { const state = stopped ? 'next' : index < current || current === -1 ? 'done' : index === current ? 'current' : 'next'; return <li key={step.label} data-state={state}><span className="mc-progress-mark" aria-hidden="true">{state === 'done' ? <Check size={12} strokeWidth={2.5}/> : state === 'current' ? <Loader size={12} className="mc-spin"/> : null}</span>{step.label}</li>; })}</ol>
      {run.lastEvent && <p className="mc-event helper" role="status">{run.lastEvent.summary}</p>}
      {snapshot.blocked_dependencies.length > 0 && <p className="mc-error" role="alert">Blocked on: {snapshot.blocked_dependencies.join(', ')}</p>}
    </Panel>;
  }
  const position = selected ? sites.indexOf(selected) : 0; const step = (delta: number) => { const next = sites[(position + delta + sites.length) % sites.length]; if (next) { setSelectedId(next.candidate.id); setOverview(false); } };
  const canProve = !!snapshot.rover_revision_id && (snapshot.pending_review?.allowed_actions.includes('PROVE_IT') ?? false);
  const prove = async (site: Site) => { if (snapshot.selected_candidate_id !== site.candidate.id) { const ok = await run.action({ action_type: 'SELECT_CANDIDATE', expected_revision: snapshot.revision, payload: { candidate_id: site.candidate.id } }); if (!ok) return; } };
  const working = PROVING_LABEL[snapshot.state];
  return <Panel testid="tour" step="Earth sites" title="Where to rehearse on Earth" lead={`${sites.length} candidate ${sites.length === 1 ? 'site' : 'sites'} for ${contract.name}.`}
    footer={<><div className="mc-tour-nav" role="group" aria-label="Tour"><Button variant="secondary" aria-label="Previous site" data-testid="btn-prev-site" onClick={() => step(-1)}><ChevronLeft size={16} aria-hidden="true"/></Button><span className="mono" data-testid="tour-position">{position + 1} / {sites.length}</span><Button variant="secondary" aria-label="Next site" data-testid="btn-next-site" onClick={() => step(1)}><ChevronRight size={16} aria-hidden="true"/></Button></div>
      <Button variant="ghost" aria-pressed={overview} data-testid="btn-all-sites" onClick={() => setOverview(value => !value)}><Globe2 size={16} aria-hidden="true"/>{overview ? 'Back to site' : 'Whole Earth'}</Button></>}>
    {badges}
    {selected && <Guide>{narrateSite(selected, sites.length)}</Guide>}
    {working && <p className="mc-working-line" role="status"><Loader size={14} className="mc-spin" aria-hidden="true"/>{working}</p>}
    <section className="mc-coverage-strip" data-testid="coverage-strip" aria-label="Which site tests each requirement"><h2>Requirement coverage</h2><ul>{coverage.map(row => <li key={row.requirement.id} data-state={row.state}><span>{row.requirement.label}</span><strong>{row.state === 'COVERED' ? row.sites.map(site => `Site ${site.index}`).join(', ') : row.state === 'GAP' ? 'Not testable on Earth' : 'No site yet'}</strong></li>)}</ul></section>
    {group.length > 1 && selected && <LocalMap group={group} selected={selected.candidate.id} onSelect={onMarkerSelect}/>}
    <ul className="mc-site-list" data-testid="site-list" aria-label="Sites">{sites.map(site => <li key={site.candidate.id}><button type="button" data-testid="site-chip" data-status={site.status} aria-pressed={site === selected} onClick={() => onMarkerSelect(site.candidate.id)}><span className="mc-ticker-index">{site.index}</span>{site.candidate.name}</button></li>)}</ul>
    {selected && <article className="mc-site-card" data-testid="site-card" data-status={selected.status} aria-label={`Site ${selected.index}`}>
      <header><div><h2>{selected.candidate.name}</h2><p className="mono">{formatPlace(selected.lat, selected.lng)} · {ORIGIN[selected.candidate.origin] ?? selected.candidate.origin}</p></div><span className="mc-site-status" data-status={selected.status}>{STATUS_WORD[selected.status]}</span></header>
      <h3>Benchmarks at this site</h3>
      <ul className="mc-benchmarks">{selected.rows.map(row => <li key={row.requirement.id} data-testid="benchmark-row" data-status={row.status}><div><strong>{row.requirement.label}</strong><span>Must be {benchmarkText(row.requirement)} · {ORIGIN_LABEL[row.requirement.origin]}</span>{row.qualification?.explanation && <span className="mc-explain">{row.qualification.explanation}</span>}</div><StatusBadge status={row.status}/></li>)}</ul>
      {selected.candidate.limitations.length > 0 && <><h3>What this site cannot show</h3><ul className="mc-limits">{selected.candidate.limitations.map(item => <li key={item}>{item}</li>)}</ul></>}
      {run.results.length > 0 && <><h3>Rover test attempts</h3><ol className="mc-attempts" data-testid="attempts">{run.results.map((result, index) => <li key={result.id}><span className="mono">Attempt {index + 1}</span><ResultBadge outcome={result.outcome}/>{result.failure_category && <span className="helper">{sentenceCase(result.failure_category)} problem</span>}</li>)}</ol></>}
      <div className="mc-site-actions">
        {snapshot.rover_revision_id ? <Link className="button" data-variant="primary" data-testid="link-prove" to={`/runs/${snapshot.run_id}/test-lab`} onClick={() => { void prove(selected); }}>Prove it here</Link> : <p className="helper">No rover supplied: route benchmarks are not run.</p>}
        <a className="button" data-variant="secondary" data-testid="link-report" href={`/runs/${snapshot.run_id}/report?site=${selected.candidate.id}`} target="_blank" rel="noreferrer">Open report<ExternalLink size={14} aria-hidden="true"/></a>
        <Link className="button" data-variant="ghost" to={`/runs/${snapshot.run_id}/qualification`}>View evidence</Link>
      </div>
      {!canProve && snapshot.rover_revision_id && <p className="helper">The rover test opens in the evidence workbench.</p>}
      {run.actionError !== null && <ErrorPanel error={run.actionError}/>}
    </article>}
  </Panel>;
}
