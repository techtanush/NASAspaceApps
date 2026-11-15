import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { parseVisualization, useVisualizationCapabilities, verifyDetail, type VisualizationDetail } from '../../api/visualization';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { EarthMap } from '../../maps/EarthMap';
import { PlanetaryPanel } from '../../maps/PlanetaryPanel';
import { ErrorPanel, Skeleton } from '../../components/ui';
import type { Site } from './tour';

type S = components['schemas'];
function useDetailLayers(runId:string,subject:S['AreaOfInterest'],candidateId:string|null,profileId:string|null,run?:S['RunSnapshot']) {
  const workspace=useWorkspace(); const capabilities=useVisualizationCapabilities();
  const detail=useQuery({queryKey:['workspace',workspace,'visualization-detail',runId,candidateId,profileId,run?.dataset_lock_id,run?.revision],enabled:!!capabilities.data?.regional_detail&&!!run&&run.workspace_id===workspace,queryFn:async({signal})=>verifyDetail(parseVisualization<VisualizationDetail>('detail',await api.get(`/runs/${runId}/visualization/${candidateId?`candidates/${candidateId}`:'target'}`,{signal})),{runId,candidateId,body:subject.body,bbox:subject.bbox,lock:run!.dataset_lock_id}),retry:false});
  const path=`/display-layers?run_id=${runId}&${candidateId?`candidate_id=${candidateId}`:`target_profile_id=${profileId}`}`;
  const legacy=!capabilities.isPending&&!capabilities.error&&!capabilities.data;
  const layers=useApi<S['ListDisplayLayerManifest']>(workspace,path,(legacy||!!detail.data)&&!!(candidateId||profileId));
  const matching=useMemo(()=>(capabilities.error||detail.error||layers.error?[]:layers.data?.items??[]).filter(layer=>layer.run_id===runId&&layer.workspace_id===workspace&&layer.body===subject.body&&(!run||layer.mode===run.mode)&&(candidateId?layer.candidate_id===candidateId:layer.candidate_id===null&&layer.target_profile_id===profileId)&&(!capabilities.data||!!detail.data?.display_layer_manifest_ids.includes(layer.id))),[layers.data,layers.error,runId,workspace,subject.body,run?.mode,candidateId,profileId,capabilities.data,capabilities.error,detail.data,detail.error]);
  return {matching,detail:detail.data,error:capabilities.error??detail.error??layers.error,loading:capabilities.isPending||(!!capabilities.data&&detail.isPending)||((legacy||!!detail.data)&&layers.isPending),refetch:()=>{void capabilities.refetch();if(capabilities.data?.regional_detail)void detail.refetch();if(legacy||detail.data)void layers.refetch();}};
}
export function RegionalInspector({ runId, site, run }: { runId: string; site: Site; run?:S['RunSnapshot'] }) {
  const workspace = useWorkspace();
  const layers=useDetailLayers(runId,site.candidate.aoi,site.candidate.id,null,run);
  const matching=layers.matching.filter(layer=>layer.workspace_id===workspace&&layer.mode===site.candidate.mode);
  const candidates = useMemo(() => [site.candidate], [site.candidate]);
  return <section className="mc-regional" aria-label={`Regional evidence for ${site.candidate.name}`} data-testid="regional-inspector">
    <header><p className="mc-eyebrow">Regional evidence</p><h2>{site.candidate.name}</h2><p>Selected footprint · {site.candidate.aoi.body} · {site.candidate.mode}</p></header>
    {layers.loading && <Skeleton label="Loading selected-site layers"/>}
    {layers.error && <ErrorPanel error={layers.error} onRetry={() => { void layers.refetch(); }}/ >}
    {!layers.loading && !layers.error && matching.length === 0 && <p className="mc-detail-notice" role="status">Terrain imagery unavailable for this site. The boundary is the registered candidate footprint; it is not a terrain measurement.</p>}
    {layers.detail&&<p className="mc-detail-notice" data-testid="detail-availability">Regional data: {layers.detail.availability.toLowerCase()}. {layers.detail.reason}</p>}
    <EarthMap key={site.candidate.id} candidates={candidates} selected={site.candidate.id} candidateLabels={{[site.candidate.id]:`Site ${site.index}`}} onSelect={() => {}} layers={matching} allowSatelliteImagery/>
    {matching.map(layer => <details key={layer.id} className="mc-source"><summary>{layer.layer_kind} · source and resolution</summary><p>Comparison support: {layer.support_scale_m === null ? 'Unknown' : `${layer.support_scale_m} m`}. Native / effective source resolution: see source receipts.</p><p>Height reference: {site.candidate.aoi.vertical_datum}</p><p className="mono">Display CRS: {layer.display_crs_wkt}</p><p>No-data: transparent mask · {layer.width_px} × {layer.height_px} display pixels</p><p className="mono">Source evidence: {layer.source_evidence_ids.join(', ') || 'Unknown'}</p></details>)}
    <p className="mc-detail-notice">Zoom changes the display, not the evidence resolution. Layer units, comparison support and limitations appear below the map.</p>
  </section>;
}

export function TargetInspector({ runId, profileId, target, run }: { runId: string; profileId: string | null; target: S['AreaOfInterest']; run?:S['RunSnapshot'] }) {
  const layers=useDetailLayers(runId,target,null,profileId,run);
  return <section className="mc-regional" aria-label="Planetary target detail"><header><p className="mc-eyebrow">Planetary evidence</p><h2>Mission target</h2></header>{layers.loading&&<Skeleton label="Loading target layers"/>}{layers.error && <ErrorPanel error={layers.error}/ >}{layers.detail&&<p className="mc-detail-notice">Regional data: {layers.detail.availability.toLowerCase()}. {layers.detail.reason}</p>}<PlanetaryPanel key={profileId ?? target.body} aoi={target} layers={layers.matching}/></section>;
}
