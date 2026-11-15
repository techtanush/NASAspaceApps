import { type Site } from './tour';

export function SiteTestPurpose({ site }: { site: Site }) {
  const supported = site.rows.filter(row => row.status === 'PASS');
  const partial = site.rows.filter(row => row.status === 'PARTIAL');
  return <section className="mc-test-purpose" aria-label="What to test at this location">
    <h2>What to test here</h2>
    {supported.length > 0 ? <><p>Current evidence supports these rehearsals:</p><ul>{supported.map(row => <li key={row.requirement.id}>{row.requirement.label}</li>)}</ul></> : <p>No benchmark has yet demonstrated a supported rehearsal here. Review the measured results and remaining unknowns below.</p>}
    {partial.length > 0 && <p>Partial support only: {partial.map(row => row.requirement.label).join('; ')}. Check the limitations before planning a test.</p>}
  </section>;
}
