import type { GlobeBody } from '../../maps/globeAssets';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '../../app/WorkspaceContext';
import { api } from '../../api/client';
import { parseVisualization, useVisualizationCapabilities, type VisualizationCoverage } from '../../api/visualization';

/**
 * Terrain-data coverage for a chosen place, shown before a run starts.
 *
 * Plug-in point: the backend does not yet expose dataset footprints. When it does, resolve the real state here
 * (COVERED, PARTIAL or NONE) and every screen that shows coverage updates. Until then the honest answer is UNKNOWN.
 */
export type CoverageState = 'COVERED' | 'PARTIAL' | 'NONE' | 'UNKNOWN';
export interface Coverage { state: CoverageState; message: string; data?:VisualizationCoverage; error?:unknown }
export function useCoverage(body: GlobeBody, bbox: readonly number[] | null, scenario?:{id:string;default_dataset_lock_id:string}): Coverage {
  const workspace=useWorkspace(); const capabilities=useVisualizationCapabilities(); const box=bbox?.join(',');
  const query=useQuery({queryKey:['workspace',workspace,'visualization-coverage',body,box,scenario?.id,scenario?.default_dataset_lock_id],enabled:!!capabilities.data?.coverage&&!!box&&!!scenario,queryFn:async({signal})=>{
    const params=new URLSearchParams({body,bbox:box!,scenario_config_id:scenario!.id,dataset_lock_id:scenario!.default_dataset_lock_id});
    const result=parseVisualization<VisualizationCoverage>('coverage',await api.get(`/visualization/coverage?${params}`,{signal}));
    if(result.body!==body||result.bbox.join(',')!==box||result.scenario_config_id!==scenario!.id||result.dataset_lock_id!==scenario!.default_dataset_lock_id)throw new Error('Coverage does not match the selected source and dataset lock');
    return result;
  },retry:false});
  const error=capabilities.error??query.error;
  if(error)return {state:'UNKNOWN',message:'Terrain coverage could not be read. No availability is assumed.',error};
  if(query.data)return {state:query.data.state,message:`${query.data.reason} ${query.data.basis==='VALIDATED_FOOTPRINT'?'Validated source footprint only; valid pixels and mission suitability are checked separately.':''}`,data:query.data};
  return {state:'UNKNOWN',message:!scenario?'Choose a source mode at review to check the exact scenario and dataset lock.':capabilities.isPending||query.isFetching?'Checking prepared terrain coverage for this source.':'Prepared coverage is unavailable for this deployment. The investigation will check its required evidence.'};
}
