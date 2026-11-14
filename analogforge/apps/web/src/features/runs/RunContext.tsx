import { createContext,useContext } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { components } from '../../generated/schema';
import { api } from '../../api/client';
import { findEvidenceByAlgorithm, type ALGORITHM_IDS } from '../../api/artifacts';
import { useWorkspace } from '../../app/WorkspaceContext';
export type Schema=components['schemas'];
export interface RunContextValue { snapshot:Schema['RunSnapshot'];contract:Schema['MissionTestContract'];candidates:Schema['EarthAnalogCandidate'][];qualifications:Schema['QualificationDimension'][];action:(request:Schema['RunAction'])=>Promise<boolean>;showEvidence:(id:string)=>void;pending:boolean; }
export const RunContext=createContext<RunContextValue|null>(null);
export function useRun(){const context=useContext(RunContext);if(!context)throw new Error('Run context is required');return context;}
export function useOperationArtifact<T>(ids:readonly string[],key:keyof typeof ALGORITHM_IDS){const workspace=useWorkspace();return useQuery({queryKey:['workspace',workspace,'display-artifact',key,...ids],queryFn:async({signal})=>{const evidence=await findEvidenceByAlgorithm(ids,key,signal);if(!evidence?.artifact_sha256)return null;return api.get<T>(`/artifacts/${evidence.artifact_sha256}`,{signal});},enabled:ids.length>0,retry:false});}
export interface ComparisonDisplay {evaluation_stage:string;reason_code:string;measured_value:number|null;measured_unit:string|null;threshold_lower:number|null;threshold_upper:number|null;explanation:string;}
export interface ScreeningDisplay {windows:{window_id:string;name:string;rank:number|null;excluded:boolean;exclusion_reason:string|null}[];limitations:string[];}
export interface TargetDisplay {slope_histogram:{metric_id:string;edges:number[];area_fraction:number[];unit:string;support_scale_m:number;valid_area_m2:number}|null;unavailable_dimensions:{dimension:string;reason_code:string;message:string}[];}
export interface VerificationDisplay {violations?:{segment_from_index:number|null;segment_to_index:number|null;message:string}[];benchmark_rows:{constraint_id:string;requirement_id:string;rule:string;measured:number|null;unit:string|null;margin:number|null;status:Schema['VerificationOutcome']}[];limitations:string[];}
export interface TelemetryDisplay {samples:{index:number;node_id:string;cumulative_distance_m:number;elapsed_s:number;lon:number|null;lat:number|null;cumulative_energy_conservative_wh:number|null;reserve_pct:number|null}[];}
