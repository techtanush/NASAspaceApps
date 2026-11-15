import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import { ApiError } from './errors';
import { useWorkspace } from '../app/WorkspaceContext';
import type { components } from '../generated/schema';
import capabilitiesSchema from './visualization-schemas/capabilities.v1.schema.json';
import coverageSchema from './visualization-schemas/coverage.v1.schema.json';
import detailSchema from './visualization-schemas/site-detail.v1.schema.json';
import benchmarksSchema from './visualization-schemas/site-benchmarks.v1.schema.json';

type S = components['schemas'];
export interface VisualizationCapabilities { schema_version:'1.0'; enabled:true; coverage:true; regional_detail:true; benchmarks:true; imagery_catalog_path:string; imagery_purpose:'VISUAL_CONTEXT_ONLY'; openapi_path:string }
export interface VisualizationDetail { schema_version:'1.0'; run_id:string; candidate_id:string|null; body:S['Body']; bbox:number[]; dataset_lock_id:string|null; availability:'AVAILABLE'|'PARTIAL'|'UNAVAILABLE'; reason:string; display_layer_manifest_ids:string[] }
export interface VisualizationCoverage { schema_version:'1.0'; body:S['Body']; bbox:number[]; scenario_config_id:string; dataset_lock_id:string|null; state:'COVERED'|'PARTIAL'|'NONE'|'UNKNOWN'; basis:'VALIDATED_FOOTPRINT'|'VALID_MASK'|'UNAVAILABLE'; reason:string; datasets:{id:string;version:string;body:S['Body'];bbox:number[];validated:true;eligible_for_scenario:boolean;native_resolution_m:number|null;comparison_support_m:number|null}[] }
export interface BenchmarkRow { requirement:S['Requirement']; qualification_id:string|null; status:S['QualificationStatus']; explanation:string; measurement:{value:number|null;unit:string|null;support_scale_m:number|null;comparison_evidence_id:string|null;receipt_id:string|null;reason:string}; test_result_ids:string[] }
export interface VisualizationBenchmarks { schema_version:'1.0'; run_id:string; candidate_id:string; mission_revision_id:string; dataset_lock_id:string|null; requirements:BenchmarkRow[]; test_result_ids:string[] }
const ajv = new Ajv2020({strict:false,allErrors:true}); addFormats(ajv);
const validators = {capabilities:ajv.compile(capabilitiesSchema),coverage:ajv.compile(coverageSchema),detail:ajv.compile(detailSchema),benchmarks:ajv.compile(benchmarksSchema)};
export function parseVisualization<T>(kind:keyof typeof validators,value:unknown):T { if (!validators[kind](value)) throw new Error(`Unsupported visualization ${kind} response`); return value as T; }
/** A missing extension is supported. Authorization and network failures stay visible. */
export function useVisualizationCapabilities() {
  const workspace=useWorkspace();
  return useQuery({queryKey:['workspace',workspace,'visualization-capabilities'],queryFn:async({signal})=>{if(import.meta.env.VITE_API_MOCK==='1')return null;try{return parseVisualization<VisualizationCapabilities>('capabilities',await api.get('/visualization/capabilities',{signal}));}catch(error){if(error instanceof ApiError&&error.status===404)return null;throw error;}},retry:false,staleTime:60_000});
}
export function verifyDetail(detail:VisualizationDetail,subject:{runId:string;candidateId:string|null;body:S['Body'];bbox:number[];lock:string}) {
  if(detail.run_id!==subject.runId||detail.candidate_id!==subject.candidateId||detail.body!==subject.body||detail.dataset_lock_id!==subject.lock||detail.bbox.length!==subject.bbox.length||detail.bbox.some((value,index)=>value!==subject.bbox[index]))throw new Error('Regional evidence does not match the selected run, site or dataset lock');
  if(detail.availability==='UNAVAILABLE'&&detail.display_layer_manifest_ids.length)throw new Error('Unavailable regional evidence advertised layers');
  return detail;
}
function stable(value:unknown):string {if(Array.isArray(value))return `[${value.map(stable).join(',')}]`;if(value&&typeof value==='object')return `{${Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>`${JSON.stringify(key)}:${stable(item)}`).join(',')}}`;return JSON.stringify(value);}
export function verifyBenchmarks(value:VisualizationBenchmarks,run:S['RunSnapshot'],candidateId:string,requirements:S['Requirement'][]) {
  if(value.run_id!==run.run_id||value.candidate_id!==candidateId||value.mission_revision_id!==run.mission_revision_id||value.dataset_lock_id!==run.dataset_lock_id||!run.candidate_ids.includes(candidateId)||value.requirements.length!==requirements.length||value.requirements.some((row,index)=>stable(row.requirement)!==stable(requirements[index]))||value.test_result_ids.some(id=>!run.test_result_ids.includes(id))||(!run.rover_revision_id&&value.test_result_ids.length))throw new Error('Benchmark evidence does not match the accepted run and selected site');
  for(const row of value.requirements){const m=row.measurement;if(row.test_result_ids.some(id=>!value.test_result_ids.includes(id))||(row.qualification_id!==null&&!run.qualification_ids.includes(row.qualification_id)))throw new Error('Benchmark ancestry is unavailable');if(m.value!==null&&(!Number.isFinite(m.value)||m.unit!==row.requirement.unit||m.support_scale_m===null||m.support_scale_m<=0||!m.comparison_evidence_id||!m.receipt_id))throw new Error('Benchmark measurement is missing compatible evidence');}
  return value;
}
export function useSiteBenchmarks(run:S['RunSnapshot']|undefined,contract:S['MissionTestContract']|undefined,candidateId:string|null) {
  const workspace=useWorkspace();const capabilities=useVisualizationCapabilities();
  const query=useQuery({queryKey:['workspace',workspace,'visualization-benchmarks',run?.run_id,candidateId,run?.dataset_lock_id,contract?.id,run?.revision],enabled:!!capabilities.data?.benchmarks&&!!run&&run.workspace_id===workspace&&!!contract&&!!candidateId&&run.candidate_ids.includes(candidateId),queryFn:async({signal})=>verifyBenchmarks(parseVisualization<VisualizationBenchmarks>('benchmarks',await api.get(`/runs/${run!.run_id}/visualization/candidates/${candidateId}/benchmarks`,{signal})),run!,candidateId!,contract!.requirements),retry:false});
  return {...query,error:capabilities.error??query.error,available:!!capabilities.data?.benchmarks,discovering:capabilities.isPending,refetch:async()=>{const capability=await capabilities.refetch();if(capability.data?.benchmarks)return query.refetch();}};
}
