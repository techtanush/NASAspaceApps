import { ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui';
import { requirementName } from '../../format/requirements';
import { formatPlace } from './coordinates';
import { benchmarkText, siteName, siteStatusSummary, type Site, type CoverageRow } from './tour';

export function LocationOverview({ sites, coverage, hasRover, onSelect }: { sites: Site[]; coverage: CoverageRow[]; hasRover: boolean; onSelect: (id: string) => void }) {
  return <section className="mc-location-matrix" aria-label="All-location rehearsal plan">
    <p>Each location has its own purpose, evidence, and next test. A terrain match is a starting point for rehearsal, not a physical rover pass.</p>
    <ol className="mc-location-cards">{sites.map(site => {
      const supported = site.rows.filter(row => row.status === 'PASS' || row.status === 'PARTIAL');
      return <li key={site.candidate.id}><article aria-label={`Location ${site.index}`}>
        <header><span className="mc-eyebrow">LOCATION {site.index}</span><h2>{siteName(site)}</h2><p className="mono">{formatPlace(site.lat, site.lng)}</p></header>
        <p className="mc-overview-verdict">{siteStatusSummary(site)}</p>
        <dl><dt>What this site can support</dt><dd>{supported.length ? supported.map(row => requirementName(row.requirement)).join(' · ') : 'No supported rehearsal established yet.'}</dd>
          <dt>Benchmarks to meet</dt><dd>{supported.length ? <ul>{supported.map(row => <li key={row.requirement.id}><strong>{requirementName(row.requirement)}:</strong> {benchmarkText(row.requirement, true)}{row.status === 'PARTIAL' && ' (partial evidence)'}</li>)}</ul> : 'Open the location to inspect its missing or unmet requirements.'}</dd>
          <dt>How to test</dt><dd>{!hasRover ? 'No rover is attached. Inspect this location’s measurements; start a rover investigation to establish hardware-specific route criteria.' : site.rows.some(row => ['unique_slope_exposure_m', 'completed_task_count', 'final_battery_reserve_pct'].includes(row.requirement.observable)) ? 'Open this site’s field brief for accepted criteria and any verified start and checkpoints. Survey the route before a physical trial.' : 'Validate the stated terrain measurements at their comparison scale. A separate hardware trial needs its own accepted criteria.'}</dd></dl>
        <Button variant="primary" onClick={() => onSelect(site.candidate.id)} aria-label={`Inspect location ${site.index}`}>Explore location {site.index}<ArrowRight size={15} aria-hidden="true"/></Button>
      </article></li>;
    })}</ol>
    <details className="mc-overview-coverage"><summary>Which locations support each mission requirement</summary><table><caption>Saved requirement coverage across all locations</caption><thead><tr><th scope="col">Requirement and benchmark</th><th scope="col">Locations with matching evidence</th></tr></thead><tbody>{coverage.map(row => <tr key={row.requirement.id}><th scope="row">{row.requirement.label}<p className="helper">{benchmarkText(row.requirement, true)}</p></th><td>{row.state === 'COVERED' ? row.sites.map(site => `Location ${site.index}`).join(', ') : row.state === 'GAP' ? 'Cannot be reproduced naturally on Earth' : 'No matching evidence yet'}</td></tr>)}</tbody></table></details>
  </section>;
}
