import { useRunAssurance } from './useRunAssurance';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button, ErrorPanel, ModeBadge, Skeleton, PublicationBadge } from '../../components/ui';
import { useRunData } from './useRunData';
import { buildSites, siteName } from './tour';
import { BenchmarkEvidence } from './BenchmarkEvidence';
import { EnvironmentContext } from './EnvironmentContext';
import { formatPlace } from './coordinates';
import { RunTerminalNotice } from './RunTerminalNotice';
import { SiteTestPurpose } from './SiteTestPurpose';
import { EvidenceBriefDownload } from './EvidenceBriefDownload';
import { ResultPresentation } from './ResultPresentation';
import { SiteFieldPlan } from './SiteFieldPlan';

export function ReportPage() {
  const { runId } = useParams(); const [search, setSearch] = useSearchParams(); const run = useRunData(runId); const assurance = useRunAssurance(run.snapshot, run.contract, run.rover);
  if (run.error) return <div className="mc-report"><h1>Report unavailable</h1><ErrorPanel error={run.error}/></div>;
  if (run.loading || !run.snapshot || !run.contract) return <div className="mc-report"><h1>Opening report</h1><Skeleton label="Loading current run evidence"/></div>;
  const { snapshot, contract } = run;
  const site = buildSites(run.candidates, contract.requirements, run.qualifications).find(item => item.candidate.id === search.get('site'));
  if (!site) return <div className="mc-report"><h1>Site unavailable</h1><p>This site does not belong to the current run, or its evidence has not loaded.</p><Link to={`/runs/${runId}/tour`}>Return to Earth sites</Link></div>;
  const presentationAvailable = ['COMPLETED', 'AWAITING_REVIEW', 'FAILED', 'BLOCKED', 'CANCELLED'].includes(snapshot.state);
  const technical = presentationAvailable && search.get('detail') === 'technical';
  const changePresentation = (next: boolean) => setSearch(current => { if (next) current.set('detail', 'technical'); else current.delete('detail'); return current; }, { replace: true });
  return <article className="mc-report" data-theme="light" data-testid="site-report">
    <nav className="mc-report-actions" aria-label="Report actions"><Link to={`/runs/${runId}/tour?site=${site.candidate.id}`}>Back to location</Link><EvidenceBriefDownload key={site.candidate.id} run={snapshot} candidateId={site.candidate.id}/><EvidenceBriefDownload key={`all-${site.candidate.id}`} run={snapshot} candidateId={site.candidate.id} allLocations/><Button variant="ghost" onClick={() => window.print()}>Print this page</Button></nav>
    <header className="mc-report-heading"><p className="mc-eyebrow">AnalogForge · current evidence brief</p><h1 tabIndex={-1}>{siteName(site)}</h1><p className="mc-report-mission">{contract.name}</p><p>{formatPlace(site.lat, site.lng)} · Location {site.index} · <ModeBadge mode={snapshot.mode}/></p></header>
    <RunTerminalNotice run={snapshot}/>
    {presentationAvailable && <ResultPresentation technical={technical} onChange={changePresentation}/>}
    <p className="mc-report-scope">Current evidence at run revision {snapshot.revision}. This brief is not an immutable published passport. It covers the terrain data and candidate windows screened by this investigation.</p>
    <SiteTestPurpose site={site}/>
    <SiteFieldPlan key={site.candidate.id} runId={snapshot.run_id} candidateId={site.candidate.id} revision={snapshot.revision}/>
    <section className="mc-report-results" aria-label="Location benchmarks"><h2>Benchmarks and measured results</h2><BenchmarkEvidence run={snapshot} contract={contract} site={site} technical={technical}/></section>
    <details className="mc-report-context" open={technical || undefined}><summary>Weather and operating context</summary><EnvironmentContext run={snapshot} candidateId={site.candidate.id} report/></details>
    <section className="mc-report-limitations"><h2>Limits of this location</h2><ul>{site.candidate.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Earth locations cannot reproduce every planetary condition. Modeled qualification does not establish physical rover performance.</p></section>
    <details className="mc-report-provenance" open={technical || undefined}><summary>Source and record references</summary><dl className="mc-report-meta"><dt>Target</dt><dd>{contract.target.body} · {contract.target.bbox.join(', ')}</dd><dt>Rover revision</dt><dd>{snapshot.rover_revision_id ?? 'No rover — site qualification only'}</dd><dt>Run</dt><dd>{snapshot.run_id} · revision {snapshot.revision} · {snapshot.state}</dd><dt>Mission revision</dt><dd>{snapshot.mission_revision_id}</dd><dt>Dataset lock</dt><dd>{snapshot.dataset_lock_id}</dd><dt>Configuration</dt><dd className="mono">{snapshot.config_sha256}</dd><dt>Contract digest</dt><dd className="mono">{contract.content_sha256}</dd><dt>Published manifest</dt><dd className="mono">{assurance.passport?.manifest_sha256 ?? 'Not published'}</dd></dl></details>
    <details className="mc-report-publication"><summary>Publication and assurance</summary><PublicationBadge publication={assurance.publication}/><p>{assurance.passport ? `Published UTC: ${assurance.passport.created_at}` : 'Passport not published; immutable exports unavailable.'}</p><Link to={`/runs/${runId}/passport`}>Published passport and exports</Link></details>
    <footer><p><Link to={`/runs/${runId}/qualification?candidate=${site.candidate.id}`}>Inspect requirement evidence and provenance</Link></p>AnalogForge · Not a NASA product; no endorsement implied. This current brief retains source references; an immutable published passport has its own publication audit.</footer>
  </article>;
}
