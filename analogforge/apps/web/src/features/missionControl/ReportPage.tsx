import { useRunAssurance } from './useRunAssurance';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button, ErrorPanel, ModeBadge, Skeleton, PublicationBadge } from '../../components/ui';
import { useRunData } from './useRunData';
import { buildSites } from './tour';
import { BenchmarkEvidence } from './BenchmarkEvidence';
import { EnvironmentContext } from './EnvironmentContext';
import { formatPlace } from './coordinates';
import { RunTerminalNotice } from './RunTerminalNotice';

export function ReportPage() {
  const { runId } = useParams(); const [search] = useSearchParams(); const run = useRunData(runId); const assurance = useRunAssurance(run.snapshot, run.contract, run.rover);
  if (run.error) return <div className="mc-report"><h1>Report unavailable</h1><ErrorPanel error={run.error}/></div>;
  if (run.loading || !run.snapshot || !run.contract) return <div className="mc-report"><h1>Opening report</h1><Skeleton label="Loading current run evidence"/></div>;
  const { snapshot, contract } = run;
  const site = buildSites(run.candidates, contract.requirements, run.qualifications).find(item => item.candidate.id === search.get('site'));
  if (!site) return <div className="mc-report"><h1>Site unavailable</h1><p>This site does not belong to the current run, or its evidence has not loaded.</p><Link to={`/runs/${runId}/tour`}>Return to Earth sites</Link></div>;
  return <article className="mc-report" data-theme="light" data-testid="site-report">
    <nav className="mc-report-actions" aria-label="Report actions"><Link to={`/runs/${runId}/tour?site=${site.candidate.id}`}>Back to site</Link><Button onClick={() => window.print()}>Print / save PDF</Button><Link to={`/runs/${runId}/passport`}>Published passport and exports</Link></nav>
    <header><p className="mc-eyebrow">AnalogForge · current evidence summary</p><h1 tabIndex={-1}>{contract.name}</h1><p>{site.candidate.name} · {formatPlace(site.lat, site.lng)}</p><ModeBadge mode={snapshot.mode}/><PublicationBadge publication={assurance.publication}/></header>
    <RunTerminalNotice run={snapshot}/>
    <p>Search scope: areas covered by this investigation’s terrain data and screened candidate windows.</p>
    <p className="mc-detail-notice">Presentation of current run data. This browser summary is not an immutable published passport. Assurance is shown only from a matching publication audit.</p>
    <dl className="mc-report-meta"><dt>Target</dt><dd>{contract.target.body} · {contract.target.bbox.join(', ')}</dd><dt>Rover revision</dt><dd>{snapshot.rover_revision_id ?? 'No rover — site qualification only'}</dd><dt>Run</dt><dd>{snapshot.run_id} · revision {snapshot.revision} · {snapshot.state}</dd><dt>Mission revision</dt><dd>{snapshot.mission_revision_id}</dd></dl>
    <h2>Why this site matches or falls short</h2><BenchmarkEvidence run={snapshot} contract={contract} site={site} report/>
    <EnvironmentContext run={snapshot} candidateId={site.candidate.id} report/>
    <h2>Provenance</h2><p className="mono">Dataset lock: {snapshot.dataset_lock_id}</p><p className="mono">Configuration: {snapshot.config_sha256}</p><p className="mono">Contract digest: {contract.content_sha256}</p><p className="mono">Manifest: {assurance.passport?.manifest_sha256 ?? 'Not published'}</p><h2>Limitations</h2><ul>{site.candidate.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>Earth locations cannot reproduce every planetary condition. Modeled qualification does not establish physical rover performance.</p>
    <p><Link to={`/runs/${runId}/qualification?candidate=${site.candidate.id}`}>Inspect requirement evidence and provenance</Link></p><p>{assurance.passport ? `Published UTC: ${assurance.passport.created_at}` : 'Passport not published; immutable exports unavailable.'}</p><footer>AnalogForge · Not a NASA product; no endorsement implied. Source attributions and immutable evidence digests are retained with the published passport.</footer>
  </article>;
}
