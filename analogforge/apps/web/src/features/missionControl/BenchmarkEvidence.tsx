import type { components } from '../../generated/schema';
import { useSiteBenchmarks, type BenchmarkRow } from '../../api/visualization';
import { ErrorPanel, Skeleton, StatusBadge } from '../../components/ui';
import { quantity } from '../../format/quantity';
import { benchmarkText, readableQuantity, ORIGIN_LABEL, type Site } from './tour';
import { BenchmarkMeasurement } from './BenchmarkMeasurement';

type S=components['schemas'];
export function measurementText(measurement:BenchmarkRow['measurement'], simplified=false):string {
  return measurement.value===null?`Measurement unavailable. ${measurement.reason}`:`Measured ${(simplified && measurement.unit==='fraction' ? readableQuantity(measurement.value,measurement.unit,true) : quantity(measurement.value,measurement.unit??'',3))} at ${quantity(measurement.support_scale_m,'m')} comparison support.`;
}
/** Only the authenticated, candidate-scoped projection supplies numeric measurements. */
export function BenchmarkEvidence({run,contract,site,report=false,technical=false}:{run:S['RunSnapshot'];contract:S['MissionTestContract'];site:Site;report?:boolean;technical?:boolean}) {
  const query=useSiteBenchmarks(run,contract,site.candidate.id);
  const projection=query.error?undefined:query.data;
  return <section className="mc-benchmark-evidence" aria-label="Selected-site benchmark evidence" data-testid="site-benchmark-evidence">
    <p className="helper">Results for this Earth location: <strong>PASS</strong> meets the accepted mission criterion; <strong>FAIL</strong> does not. Each row shows the rule and its supporting measurement. {run.rover_revision_id?'Modeled rover results are listed separately when available.':'No rover simulation was run for this investigation.'}</p>
    {(query.discovering||(query.available&&query.isPending))&&<Skeleton label="Loading selected-site measurements"/>}
    {query.error&&<ErrorPanel error={query.error} onRetry={()=>{void query.refetch();}}/>}
    {!query.discovering&&!query.available&&!query.error&&<p className="helper">Numeric measurement projection is unavailable on this deployment. Committed requirement evidence is shown below.</p>}
    <ol className="mc-benchmarks">{site.rows.map((original,index)=>{
      const row=projection?.requirements[index];const status=row?.status??original.status;
      return <li key={original.requirement.id} data-testid="benchmark-row" data-status={status}>
        <header className="mc-benchmark-heading"><h3>{original.requirement.label}</h3><StatusBadge status={status}/></header>
        <p className="mc-benchmark-rule">{benchmarkText(original.requirement,!technical)}</p>
        {row&&<><p data-testid="site-measurement">{measurementText(row.measurement,!technical)}</p><BenchmarkMeasurement row={row} simplified={!technical}/></>}
        {(row?.measurement.value===null || row?.measurement.value===undefined) && <p>{row?.explanation??original.qualification?.explanation??'Unknown — committed evidence unavailable'}</p>}
        <details className="mc-evidence-references" open={report||technical||undefined}><summary>Evidence and method</summary>
          {row?.measurement.value!==null && row?.measurement.value!==undefined && <p>{row.explanation}</p>}
          <p>{ORIGIN_LABEL[original.requirement.origin]} · Requirement {original.requirement.id}</p>
          {row?.measurement.value!==null&&row?.measurement.comparison_evidence_id&&<p className="mono">Comparison evidence: {row.measurement.comparison_evidence_id}<br/>Receipt: {row.measurement.receipt_id}</p>}
          {row?.qualification_id&&<p className="mono">Qualification: {row.qualification_id}</p>}
          {original.qualification?.evidence_ids.map(id=><p className="mono" key={id}>Evidence: {id}</p>)}
          {!row?.measurement.comparison_evidence_id&&!original.qualification?.evidence_ids.length&&<p>No committed measurement reference is available.</p>}
        </details>
      </li>;
    })}</ol>
    {projection&&<details className="mc-evidence-references" open={report||technical||undefined}><summary>Site-specific rover results</summary><p>{projection.test_result_ids.join(', ')||'None. No rover result is borrowed from another site.'}</p></details>}
  </section>;
}
