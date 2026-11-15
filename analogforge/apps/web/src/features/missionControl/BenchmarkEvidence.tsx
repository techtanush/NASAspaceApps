import type { components } from '../../generated/schema';
import { useSiteBenchmarks, type BenchmarkRow } from '../../api/visualization';
import { ErrorPanel, Skeleton, StatusBadge } from '../../components/ui';
import { quantity } from '../../format/quantity';
import { benchmarkText, ORIGIN_LABEL, type Site } from './tour';

type S=components['schemas'];
export function measurementText(measurement:BenchmarkRow['measurement']):string {
  return measurement.value===null?`Measurement unavailable. ${measurement.reason}`:`Measured ${quantity(measurement.value,measurement.unit??'',3)} at ${quantity(measurement.support_scale_m,'m')} comparison support.`;
}
/** Only the authenticated, candidate-scoped projection supplies numeric measurements. */
export function BenchmarkEvidence({run,contract,site,report=false}:{run:S['RunSnapshot'];contract:S['MissionTestContract'];site:Site;report?:boolean}) {
  const query=useSiteBenchmarks(run,contract,site.candidate.id);
  const projection=query.error?undefined:query.data;
  const content=(index:number)=>{const original=site.rows[index]!;const row=projection?.requirements[index];return <><strong>{original.requirement.label}</strong><p>Rule: {benchmarkText(original.requirement)} · {ORIGIN_LABEL[original.requirement.origin]}</p><StatusBadge status={row?.status??original.status}/><p>{row?.explanation??original.qualification?.explanation??'Unknown — committed evidence unavailable'}</p>{row&&<><p data-testid="site-measurement">{measurementText(row.measurement)}</p>{row.measurement.value!==null&&<p className="mono">Comparison evidence: {row.measurement.comparison_evidence_id}<br/>Receipt: {row.measurement.receipt_id}</p>}{row.qualification_id&&<p className="mono">Qualification: {row.qualification_id}</p>}</>}{original.qualification?.evidence_ids.map(id=><p className="mono" key={id}>Evidence: {id}</p>)}</>;};
  return <section className="mc-benchmark-evidence" aria-label="Selected-site benchmark evidence" data-testid="site-benchmark-evidence">
    {(query.discovering||(query.available&&query.isPending))&&<Skeleton label="Loading selected-site measurements"/>}
    {query.error&&<ErrorPanel error={query.error} onRetry={()=>{void query.refetch();}}/>}
    {!query.discovering&&!query.available&&!query.error&&<p className="helper">Numeric measurement projection is unavailable on this deployment. Committed requirement evidence is shown below.</p>}
    {report?<div className="mc-report-table"><table><thead><tr><th scope="col">Requirement and evidence</th></tr></thead><tbody>{site.rows.map((row,index)=><tr key={row.requirement.id}><td>{content(index)}</td></tr>)}</tbody></table></div>:<ul className="mc-benchmarks">{site.rows.map((row,index)=><li key={row.requirement.id} data-testid="benchmark-row" data-status={projection?.requirements[index]?.status??row.status}><div>{content(index)}</div></li>)}</ul>}
    {projection&&<p className="helper">Site-specific rover result IDs: {projection.test_result_ids.join(', ')||'None. No rover result is borrowed from another site.'}</p>}
  </section>;
}
