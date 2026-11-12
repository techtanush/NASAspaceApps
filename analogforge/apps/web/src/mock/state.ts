import { mockArtifactHash } from './contentAddressed';
import seedJson from './fixtures/seed.json';
import type { components } from '../generated/schema';
type MappedPayload=Model<'RunEvent'>['payload'];
type Model<K extends keyof components['schemas']> = components['schemas'][K];
export const seed = seedJson;
export const workspaceId=seed.workspaceId;
export const timestamp=seed.createdAt;
export function id():string { return crypto.randomUUID(); }
export const clone = <T>(value:T):T => structuredClone(value);
export function recordBase(runId:string,mode:Model<'RuntimeMode'>='synthetic') {return {schema_version:'1.0' as const,id:id(),workspace_id:workspaceId,run_id:runId,mode,created_at:timestamp};}
export interface ReplayAttempt {candidate:string;strategy:string;outcome:string;failureCategory:string|null;searchStatus:string;distance:number|null;energy:number|null;exposure:number;reason:string;next:string|null}
export interface MockRun {
 snapshot:Model<'RunSnapshot'>; candidates:Model<'EarthAnalogCandidate'>[]; qualifications:Model<'QualificationDimension'>[];
 target:Model<'PlanetaryTargetProfile'>; tests:Model<'VerificationTest'>[]; results:Model<'TestResult'>[];
 events:Model<'RunEvent'>[]; evidence:Model<'EvidenceRecord'>[]; artifacts:Record<string,unknown>;
 critiques:Model<'EvidenceRecord'>[]; actions:Model<'AgentAction'>[]; receipts:Model<'ToolReceipt'>[];
 portfolios:Model<'CompositePortfolio'>[]; passport:Model<'AnalogPassport'>|null; exportFixture:string; stage:number; exportBundle?:Record<string,unknown>; layers?:Model<'DisplayLayerManifest'>[]; pendingVerification?:{scripts:ReplayAttempt[];nextIndex:number}; reviews?:Model<'ReviewRequest'>[]; previewBlockedInjected?:boolean; previewReviewInjected?:boolean;
}
export interface Database {
 missions:Record<string,Model<'MissionHeader'>>; drafts:Record<string,Model<'MissionDraft'>>; contracts:Record<string,Model<'MissionTestContract'>>;
 rovers:Record<string,Model<'RoverProfile'>>; jobs:Record<string,Model<'JobStatus'>>; runs:Record<string,MockRun>;
 idempotency:Record<string,{body:string;status:number;value:unknown}>; exportsRequested:Record<string,boolean>; settings:{previewScenario?:string;latencyMs?:number};
}
export const db:Database={missions:{},drafts:{},contracts:{},rovers:{},jobs:{},runs:{},idempotency:{},exportsRequested:{},settings:{}};
export const scenarios=seed.scenarios as Model<'ScenarioConfig'>[];
export function resetDatabase():void {
 for(const key of Object.keys(db) as (keyof Database)[]) Object.assign(db,{[key]:{}});
 for(const preset of Object.values(seed.roverPresets)) {
  const roverId=id();const revision=id();db.rovers[revision]={...clone(preset),schema_version:'1.0',id:revision,rover_id:roverId,workspace_id:workspaceId,revision:1,created_at:timestamp,content_sha256:mockArtifactHash(preset)} as Model<'RoverProfile'>;
 }
}
resetDatabase();
let persistent:IDBDatabase|undefined;
export async function loadDatabase():Promise<void> {
 if(typeof indexedDB==='undefined')return;
 await new Promise<void>((resolve,reject)=>{const req=indexedDB.open('analogforge-mock-preview-v1',1);req.onupgradeneeded=()=>req.result.createObjectStore('backend');req.onerror=()=>reject(req.error);req.onsuccess=()=>{persistent=req.result;const read=persistent.transaction('backend').objectStore('backend').get('state');read.onerror=()=>reject(read.error);read.onsuccess=()=>{if(read.result)Object.assign(db,read.result);resolve();};};});
}
let requestedSave=0, committedSave=0, writing=false;
let pendingSave:Promise<void>=Promise.resolve();
let persistenceError:unknown;
export function saveDatabase():void {
 if(!persistent)return;
 requestedSave++;
 if(writing)return;
 writing=true;
 pendingSave=(async()=>{
  try{
   while(committedSave<requestedSave){
    const revision=requestedSave;
    await new Promise<void>((resolve,reject)=>{
     const transaction=persistent!.transaction('backend','readwrite');
     transaction.oncomplete=()=>resolve();
     transaction.onerror=transaction.onabort=()=>reject(transaction.error||new Error('Preview storage transaction failed'));
     transaction.objectStore('backend').put(clone(db),'state');
    });
    committedSave=revision;
   }
   persistenceError=undefined;
  }catch(error){persistenceError=error;}
  finally{writing=false;}
 })();
}
export async function flushDatabase():Promise<void> {
 let checkpoint:Promise<void>;
 do{checkpoint=pendingSave;await checkpoint;if(persistenceError!==undefined)throw persistenceError;}while(checkpoint!==pendingSave);
}
export function getRun(runId:string):MockRun|undefined { return db.runs[runId]; }
export function emit(run:MockRun,eventType:string,summary:string,payload:Record<string,unknown>={}):void {
 const snapshot=run.snapshot;snapshot.last_event_seq++;snapshot.revision++;
 const event:Model<'RunEvent'>={...recordBase(snapshot.run_id,snapshot.mode),seq:snapshot.last_event_seq,event_type:eventType,state:snapshot.state,summary,payload:payload as MappedPayload,evidence_ids:[]};run.events.push(event);
 const receipt:Model<'ToolReceipt'>={...recordBase(snapshot.run_id,snapshot.mode),invocation_id:id(),tool_name:eventType,tool_version:'synthetic-replay-v1',input_sha256:seed.hash,output_sha256:seed.hash,evidence_ids:[],status:'SUCCEEDED',error_code:null,elapsed_ms:1,cache_hit:false};run.receipts.push(receipt);
 const action:Model<'AgentAction'>={...recordBase(snapshot.run_id,snapshot.mode),agent_role:'Terrain engine',invocation_id:id(),action_type:'TOOL_RESULT',tool_name:eventType,tool_receipt_id:receipt.id,summary,evidence_ids:[],status:'SUCCEEDED'};run.actions.push(action);saveDatabase();
}
export function createMission(input:Model<'MissionDraftInput'>):Model<'MissionHeader'> {
 const missionId=id(),draftId=id();const header:Model<'MissionHeader'>={id:missionId,workspace_id:workspaceId,revision:1,name:input.name,current_draft_id:draftId,current_contract_id:null,accepted_contract_id:null};
 db.missions[missionId]=header;db.drafts[draftId]={id:draftId,workspace_id:workspaceId,mission_id:missionId,revision:1,created_at:timestamp,draft:clone(input)};saveDatabase();return header;
}
export function makeRun(input:Model<'RunCreateInput'>):MockRun {
 const runId=id();const mission=db.contracts[input.mission_revision_id]!;
 const snapshot:Model<'RunSnapshot'>={...recordBase(runId,input.mode),id:runId,state:'VALIDATING',revision:1,last_event_seq:0,mission_revision_id:input.mission_revision_id,rover_revision_id:input.rover_revision_id,target_profile_id:null,candidate_ids:[],qualification_ids:[],test_ids:[],test_result_ids:[],portfolio_ids:[],passport_id:null,pending_review:null,blocked_dependencies:[],config_sha256:seed.hash,selected_candidate_id:null,selected_portfolio_id:null,scenario_config_id:input.scenario_config_id,dataset_lock_id:input.dataset_lock_id};
 const target={...clone(seed.target),...recordBase(runId,input.mode),target:clone(mission.target)} as Model<'PlanetaryTargetProfile'>;
 const candidateIds=new Map(seed.candidates.map(c=>[c.id,id()]));
 const initialEvidence=clone(seed.evidence).map(e=>({...e,...recordBase(runId,input.mode)})) as Model<'EvidenceRecord'>[];
 const candidates=clone(seed.candidates).map(c=>({...c,id:candidateIds.get(c.id)!,run_id:runId,mode:input.mode,evidence_ids:initialEvidence.map(e=>e.id)})) as Model<'EarthAnalogCandidate'>[];
 const template=clone(seed.qualifications) as Model<'QualificationDimension'>[];
 const qualifications=candidates.flatMap(candidate=>mission.requirements.map(requirement=>{
  const found=template.find(q=>candidateIds.get(q.candidate_id)===candidate.id&&q.requirement_id===requirement.id);
  return found?{...found,...recordBase(runId,input.mode),candidate_id:candidate.id,evidence_ids:initialEvidence.map(e=>e.id)}:{...recordBase(runId,input.mode),candidate_id:candidate.id,requirement_id:requirement.id,status:requirement.operator==='NOT_NATURALLY_REPRODUCIBLE'?'GAP':'UNKNOWN',evidence_ids:initialEvidence.map(e=>e.id),rule_id:'synthetic-preview-fixture',rule_version:'1.0.0',confidence:'UNASSESSED',comparison_scale_m:mission.target.body==='MOON'?960:480,explanation:requirement.id==='R-THERMAL'?'EARTH_EVIDENCE_MISSING':'PHYSICAL_GAP',limitations:['Synthetic practice fixture; not an empirical result'],critic_status:'ACCEPTED',critique_evidence_ids:[]};
 })) as Model<'QualificationDimension'>[];
 target.evidence_ids=initialEvidence.map(e=>e.id);
 const run:MockRun={snapshot,candidates,qualifications,target,tests:[],results:[],events:[],evidence:initialEvidence,artifacts:{},critiques:[],actions:[],receipts:[],portfolios:[],passport:null,exportFixture:mission.target.body==='MOON'?'limited':'failed-with-replan',stage:0};
 db.runs[runId]=run;saveDatabase();return run;
}
