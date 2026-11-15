import { useEnvironment, environmentReason } from '../../api/environment';
import type { components } from '../../generated/schema';
import { ErrorPanel } from '../../components/ui';
import { quantity } from '../../format/quantity';
import { formatCoordinate } from '../../format/coordinates';
export function EnvironmentContext({run,candidateId,report=false}:{run:components['schemas']['RunSnapshot'];candidateId:string;report?:boolean}) {
  const query=useEnvironment(run);const data=query.error?undefined:query.data;const site=data?.earth_candidates.find(item=>item.candidate_id===candidateId);const weather=site?.weather;const nasa=data?.nasa_reference;
  return <details className="mc-environment mc-source" open={report} data-testid="environment-context"><summary>Weather and operating context · {weather?.samples.some(sample=>sample.value!==null)?'stored samples':'unknown'}</summary>
    <p>Earth air and weather are operational context. They do not establish planetary equivalence or change terrain qualification, benchmark results or ranking.</p>
    {query.error&&<ErrorPanel error={query.error} onRetry={()=>{void query.refetch();}}/>}
    {query.isPending&&<p role="status">Reading stored environment context.</p>}
    {!query.isPending&&!query.error&&<p>{environmentReason(site?.reason_code??data?.reason_code,weather?.samples.some(sample=>sample.value!==null))}</p>}
    {weather&&<><h3>Earth site weather</h3><p>Declared sample window: {weather.query.start} to {weather.query.end}. Captured: {weather.fetched_at}.</p>{site?.representative_point&&<p>Representative AOI midpoint: {formatCoordinate(site.representative_point.latitude,'lat')}, {formatCoordinate(site.representative_point.longitude,'lon')}. Spatial support is unknown.</p>}<ul className="mc-weather-samples">{weather.samples.slice(0,32).map((sample,index)=><li key={`${sample.parameter}:${sample.valid_at}:${index}`}><strong>{sample.quantity.replaceAll('_',' ')}</strong><span>{quantity(sample.value,sample.unit)}</span><time dateTime={sample.valid_at}>{sample.valid_at}</time></li>)}</ul>{weather.samples.length>32&&<p>Showing the first 32 stored samples.</p>}<p>Source: {weather.query.source}. Resolved model: unknown. These values apply to the declared point and UTC sample window.</p><p className="mono">Response digest: {weather.provenance.response_sha256}</p>{weather.limitations.map(item=><p key={item}>{item}</p>)}</>}
    {nasa&&<><h3>Historical Mars rover point</h3><p>{environmentReason(nasa.reason_code)} Selected target AOI applicability: unknown.</p>{nasa.station_name&&<p>{nasa.station_name}{nasa.sol!==undefined?` · sol ${nasa.sol}`:''}. {nasa.observed_start} to {nasa.observed_end}.</p>}{nasa.quantities?.map(item=><p key={`${item.quantity}:${item.unit}`}>{item.quantity.replaceAll('_',' ')}: {quantity(item.minimum,item.unit)} to {quantity(item.maximum,item.unit)} · {item.accepted_sample_count} accepted samples.</p>)}{nasa.provenance&&<><p className="mono">NASA archive label: {nasa.provenance.label_url}</p><p className="mono">NASA archive table: {nasa.provenance.table_url}</p></>}{nasa.limitations?.map(item=><p key={item}>{item}</p>)}</>}
    {data?.snapshot_sha256&&<p className="mono">Stored context digest: {data.snapshot_sha256}</p>}
    <p>No operating limits or weather-based mission pass are inferred.</p>
  </details>;
}
