import { http, HttpResponse, delay } from 'msw';
import { canonicalMockJson,mockArtifactHash } from './contentAddressed';
import { publishAttemptArtifacts } from './attemptArtifacts';
import displayFixtures from './fixtures/display-assets.json';
import { renderMockExport } from '../api/mockBridge';
import type { components } from '../generated/schema';
import { clone,createMission,db,emit,id,makeRun,recordBase,saveDatabase,scenarios,seed,timestamp,workspaceId,type MockRun,type ReplayAttempt } from './state';
import { marsMobility } from './scripts/marsMobility';
import { validateMutation } from './validation';
import { liveNoKey } from './scripts/liveNoKey';
type M<K extends keyof components['schemas']>=components['schemas'][K];
export interface MockResponse {status:number;body:unknown;headers?:Record<string,string>}
type ExportEntry={bundle:Record<string,unknown>;manifestSha:string;exports:Record<string,{file:string;sha256:string;mediaType:string;filename:string}>};
const exportIndexes=import.meta.glob('./exports/index.json',{eager:true,import:'default'}) as Record<string,Record<string,ExportEntry>>;
const exportIndex=Object.values(exportIndexes)[0] || {};
const exportFiles=import.meta.glob('./exports/*',{query:'?raw',import:'default',eager:true}) as Record<string,string>;
const json=(body:unknown,status=200,headers?:Record<string,string>):MockResponse=>({status,body,headers});
const list=(items:unknown[],url:URL):MockResponse=>{const limit=Math.max(1,Math.min(100,Number(url.searchParams.get('limit')||25)));const cursor=Number(url.searchParams.get('cursor')||0);return json({items:items.slice(cursor,cursor+limit),next_cursor:cursor+limit<items.length?String(cursor+limit):null});};
export const error=(code:string,message:string,status=409,details:Record<string,unknown>={}):MockResponse=>json({error:{code,message,request_id:id(),retryable:false,details}},status);
const asObject=(body:unknown):Record<string,unknown>=>body && typeof body==='object'?body as Record<string,unknown>:{};
function revision(current:number,body:unknown):MockResponse|undefined {return asObject(body).expected_revision===current?undefined:error('REVISION_CONFLICT','State changed. Reload and review the current revision.',409,{current_revision:current});}
function entryFor(run:MockRun):ExportEntry|undefined{return exportIndex[run.exportFixture];}
function evidenceArtifact(run:MockRun,algorithm:string,payload:unknown,kind:M<'EvidenceRecord'>['kind']='DERIVED'):M<'EvidenceRecord'> {
 // Fixture identifiers are not claimed to be computed source or file digests.
 const artifactHash=mockArtifactHash(payload);
 const detail=asObject(payload);const target=algorithm==='characterize-target';const metrics=Array.isArray(detail.metrics)?detail.metrics as M<'MeasuredMetric'>[]:[];
 if(algorithm==='compare-requirement'&&typeof detail.measured_unit==='string')metrics.push({metric_id:typeof detail.metric_id==='string'?detail.metric_id:String(detail.requirement_id),value:typeof detail.measured_value==='number'?detail.measured_value:null,unit:detail.measured_unit,support_scale_m:typeof detail.comparison_scale_m==='number'?detail.comparison_scale_m:null,quantity_kind:'DERIVED',method_id:algorithm,valid_fraction:1,uncertainty_note:'Authored synthetic replay; uncertainty unquantified'});
 const evidence:M<'EvidenceRecord'>={...clone(run.evidence[0]!),...recordBase(run.snapshot.run_id,run.snapshot.mode),algorithm_id:algorithm,artifact_sha256:artifactHash,kind,body:target?run.target.target.body:'EARTH',aoi:target?clone(run.target.target):clone(run.candidates[0]!.aoi),native_resolution_m:target?(run.target.target.body==='MOON'?960:480):60,comparison_scale_m:typeof detail.comparison_scale_m==='number'?detail.comparison_scale_m:target?(run.target.target.body==='MOON'?960:480):60,parameters_sha256:mockArtifactHash({algorithm,mode:run.snapshot.mode,fixture:'authored-mock-replay-v1'}),metrics};run.artifacts[artifactHash]=payload;run.evidence.push(evidence);return evidence;
}
function attachDisplayArtifacts(run:MockRun):void {
 const ref={evidence_id:run.evidence[0]!.id};
 const histogram={metric_id:'surface_slope_deg',edges:[0,2,5,8,12,15,18,25,35,90],area_fraction:[0,.4,.3,0,.2,0,.1,0,0],unit:'deg',support_scale_m:run.target.target.body==='MOON'?960:480,valid_area_m2:1000000};
 const targetEvidence=evidenceArtifact(run,'characterize-target',{operation:'CHARACTERIZE_TARGET',profile_evidence:ref,metrics:run.target.metrics,slope_histogram:histogram,comparison_support_m:480,unavailable_dimensions:[{dimension:'MINERAL',reason_code:'NOT_REQUESTED',message:'Mineral context unavailable'}]});run.target.evidence_ids=[targetEvidence.id];
 const screening=evidenceArtifact(run,'screen-candidates',{operation:'SCREEN_CANDIDATES',screened_count:9,windows:[...run.candidates.map((candidate,index)=>({window_id:candidate.name.replace('Practice ',''),name:candidate.name,aoi:candidate.aoi,origin:candidate.origin,novelty_status:candidate.novelty_status,rank:index+1,excluded:false,exclusion_reason:null,feature_scores:{terrain_screening_order:index+1},is_negative_control:candidate.name.endsWith('r0c2'),evidence:ref})),...seed.excludedWindows.map(window=>({window_id:window.window_id,name:'Practice '+window.window_id,aoi:run.candidates[0]!.aoi,origin:'SYNTHETIC_CONTROL',novelty_status:'NOT_ASSESSED',rank:null,excluded:true,exclusion_reason:window.reason,feature_scores:{},is_negative_control:false,evidence:null}))],shortlist_window_ids:run.candidates.map(c=>c.name.replace('Practice ','')),stop_reason:'GRID_EXHAUSTED',search_extent:run.candidates[0]!.aoi,limitations:['SYNTHETIC PRACTICE DATA — not terrain of this location']});
 for(const candidate of run.candidates){const summary=evidenceArtifact(run,'analysis-summary',{operation:'ANALYZE_CANDIDATE',analysis_evidence:ref,analysis_grid_artifact_key:null,metrics:candidate.metrics,slope_histogram:histogram,connected_zones:[],coverage_fraction:1,limitations:candidate.limitations});candidate.evidence_ids=[screening.id,summary.id];}
 const addLayer=(key:string,candidateId:string|null)=>{
 const fixture=displayFixtures.layers[key as keyof typeof displayFixtures.layers];const asset=displayFixtures.assets[fixture.asset as keyof typeof displayFixtures.assets];
 const layer:M<'DisplayLayerManifest'>={id:id(),workspace_id:workspaceId,run_id:run.snapshot.run_id,mode:run.snapshot.mode,candidate_id:candidateId,target_profile_id:candidateId?null:run.target.id,body:fixture.body as M<'Body'>,layer_kind:'SLOPE',rendering:fixture.rendering as M<'DisplayLayerManifest'>['rendering'],image_artifact_sha256:asset.sha256,display_crs_wkt:fixture.display_crs_wkt,pixel_to_world:fixture.pixel_to_world,width_px:asset.width,height_px:asset.height,earth_corners:fixture.earth_corners,legend:clone(displayFixtures.legend),unit:'deg',support_scale_m:fixture.support_scale_m,source_evidence_ids:candidateId?run.candidates.find(c=>c.id===candidateId)!.evidence_ids:run.target.evidence_ids,nodata_transparent:true,attribution:['SYNTHETIC PRACTICE DATA — not terrain of this location'],limitations:[`Native analysis support: ${fixture.support_scale_m} m. Image pixels are display samples, never analysis cells.`, 'Alpha masks represent water, nodata or outside target coverage; masked pixels supply no value.','Authored display fixture; no visual interpolation is scientific evidence.']};
 (run.layers ||= []).push(layer);run.artifacts[asset.sha256]={mockImage:asset};
 const imageEvidence={...clone(run.evidence[0]!),...recordBase(run.snapshot.run_id,run.snapshot.mode),algorithm_id:'display-image',artifact_sha256:asset.sha256,artifact_media_type:'image/png',body:fixture.body as M<'Body'>,native_resolution_m:fixture.support_scale_m,comparison_scale_m:fixture.support_scale_m,limitations:layer.limitations};run.evidence.push(imageEvidence);
 };
 addLayer(run.target.target.body,null);for(const candidate of run.candidates)addLayer(candidate.name,candidate.id);
 for(const row of run.qualifications){const requirement=db.contracts[run.snapshot.mission_revision_id]!.requirements.find(r=>r.id===row.requirement_id)!;const candidate=run.candidates.find(c=>c.id===row.candidate_id)!;const metricId=row.requirement_id==='R-SLOPE-AVAILABILITY'?'slope_area_fraction:12-18':row.requirement_id==='R-TARGET-SLOPE-CONTEXT'?'slope_w1_deg':requirement.observable;const suppliedMetric=candidate.metrics.find(m=>m.metric_id===metricId);if(run.snapshot.scenario_config_id==='local-dataset-practice-v1'&&row.requirement_id==='R-MINERAL')row.explanation='TARGET_EVIDENCE_MISSING — Earth mineral data are available; target mineral evidence is absent';const route=['R-EXPOSURE','R-TASKS','R-RESERVE'].includes(row.requirement_id);const evidence=evidenceArtifact(run,'compare-requirement',{operation:'COMPARE_REQUIREMENT',requirement_id:row.requirement_id,proposed_status:row.status,reason_code:row.status==='GAP'?'PHYSICAL_GAP':row.status==='PASS'?'MEETS_CRITERION':row.status==='FAIL'?'INSUFFICIENT_EXPOSURE':row.requirement_id==='R-CLEARANCE'?'SCALE_UNSUPPORTED':row.requirement_id==='R-MINERAL'?(run.snapshot.scenario_config_id==='local-dataset-practice-v1'?'TARGET_EVIDENCE_MISSING':'EARTH_EVIDENCE_MISSING'):'ROUTE_NOT_VERIFIED',evaluation_stage:route?'PRELIMINARY':'FINAL',confidence:row.confidence,comparison_scale_m:row.comparison_scale_m,measured_value:suppliedMetric?.value??null,measured_unit:requirement.unit,threshold_lower:requirement.lower,threshold_upper:requirement.upper,explanation:row.explanation,limitations:row.limitations,comparison_evidence:ref,adequacy:{observable_policy_id:row.rule_id,policy_sha256:seed.hash,gates:[],validation_level:'S0'}});if(suppliedMetric)evidence.metrics=[clone(suppliedMetric)];row.evidence_ids=[evidence.id];}
}
export function assembleBundle(run:MockRun):Record<string,unknown> {
 const entry=entryFor(run);if(!entry)throw new Error('Real renderer fixture unavailable');
 const bundle=clone(entry.bundle);const mission=db.contracts[run.snapshot.mission_revision_id]!;
 const passport=clone(bundle.passport) as M<'AnalogPassport'>;
 passport.id=id();passport.run_id=run.snapshot.run_id;passport.workspace_id=workspaceId;passport.mode=run.snapshot.mode;passport.mission_revision_id=mission.id;passport.rover_revision_id=run.snapshot.rover_revision_id;passport.candidate_ids=run.candidates.map(c=>c.id);passport.qualification_ids=run.qualifications.map(q=>q.id);passport.test_result_ids=run.results.map(r=>r.id);passport.evidence_ids=run.evidence.map(e=>e.id);passport.assurance_evidence_id=id();passport.evidence_ids.push(passport.assurance_evidence_id);
 bundle.passport=passport;bundle.mode=run.snapshot.mode;bundle.replay_source_run_id=run.snapshot.mode==='replay'?seed.runId:null;bundle.mission=clone(mission);bundle.rover=run.snapshot.rover_revision_id?clone(db.rovers[run.snapshot.rover_revision_id]):null;bundle.target_profile=clone(run.target);bundle.candidates=clone(run.candidates);bundle.qualifications=clone(run.qualifications);bundle.compatibility=run.snapshot.rover_revision_id?[{candidate_id:run.snapshot.selected_candidate_id||run.candidates[0]!.id,rover_revision_id:run.snapshot.rover_revision_id,preliminary:run.results.length===0,dimensions:compatibility(run,run.snapshot.selected_candidate_id||run.candidates[0]!.id).dimensions.map(d=>({metric_id:d.metric_id,status:d.status,rover_value:null,required_value:null,unit:null,explanation:d.explanation,evidence:d.evidence_ids.map(evidence_id=>({evidence_id}))}))}]:[];bundle.critiques=run.critiques.map(e=>run.artifacts[e.artifact_sha256!]);bundle.evidence_appendix=clone(run.evidence);bundle.portfolio=run.portfolios[0]||null;
 bundle.attempts=run.tests.map((test,index)=>{const result=run.results[index]!;const event=run.events.find(e=>e.event_type==='verification.completed'&&(e.payload as Record<string,unknown>).attempt_number===index+1);const payload=(event?.payload||{}) as Record<string,unknown>;return {attempt_number:index+1,parent_attempt_number:index>0?index:null,candidate_id:test.candidate_id,candidate_name:run.candidates.find(c=>c.id===test.candidate_id)!.name,strategy:payload.strategy||'WAYPOINT_RETURN',changed_elements:index===0?[]:[String(payload.changed_elements||'See attempt receipt')],test:clone(test),result:clone(result),benchmark_rows:payload.benchmark_rows||[],violations:[],diagnosis_category:result.failure_category,diagnosis_explanation:result.limitations.join(' · '),route_image_asset_key:null};});
 const assurance=clone(bundle.assurance) as Record<string,unknown>;
 assurance.run_id=run.snapshot.run_id;assurance.workspace_id=workspaceId;assurance.mode=run.snapshot.mode;assurance.mission_content_sha256=mission.content_sha256;assurance.rover_content_sha256=run.snapshot.rover_revision_id?db.rovers[run.snapshot.rover_revision_id]!.content_sha256:null;assurance.critique_evidence_ids=[];
 const referenceIds=new Set(run.evidence.map(e=>e.id));
 assurance.claims=(assurance.claims as Record<string,unknown>[]).map(claim=>({...claim,candidate_ids:run.candidates.map(c=>c.id),evidence_ids:[...referenceIds].slice(0,1),assumption_evidence_ids:[],gates:(claim.gates as Record<string,unknown>[]).map(gate=>({...gate,evidence_ids:[...referenceIds].slice(0,1)}))}));bundle.assurance=assurance;
 return bundle;
}
const passportBuilding=new WeakSet<MockRun>();
async function finishPassport(run:MockRun):Promise<void> {
 if(run.passport||passportBuilding.has(run)||run.snapshot.state==='CANCELLED')return;passportBuilding.add(run);
 try {
 const entry=entryFor(run);if(!entry)return;
 const bundle=run.exportBundle||assembleBundle(run);run.exportBundle=bundle;saveDatabase();
 const passport=bundle.passport as M<'AnalogPassport'>;
 if(typeof window!=='undefined'&&(window as Window & {__MSW__?:boolean}).__MSW__){
  try {const rendered=await renderMockExport(bundle,'json');const content=await rendered.json() as {manifest_sha256:string};passport.manifest_sha256=content.manifest_sha256;bundle.manifest_sha256=content.manifest_sha256;}
  catch(err){run.snapshot.state='BLOCKED';run.snapshot.blocked_dependencies=['mock-renderer'];emit(run,'run.blocked',err instanceof Error?err.message:'Mock renderer unavailable');return;}
 }
 if(db.runs[run.snapshot.run_id]!==run||['CANCELLED'].includes(run.snapshot.state))return;
 run.passport=passport;const assuranceHash=mockArtifactHash(bundle.assurance);const assuranceEvidence={...clone(run.evidence[0]!),id:passport.assurance_evidence_id,algorithm_id:'scientific-assurance',artifact_sha256:assuranceHash};run.evidence.push(assuranceEvidence);run.artifacts[assuranceHash]=clone(bundle.assurance);
 run.snapshot.passport_id=passport.id;run.snapshot.state='COMPLETED';emit(run,'passport.created','Passport assembled from the synthetic practice replay.');
 } finally {passportBuilding.delete(run);}
}
function critique(run:MockRun,status:'OPEN'|'RESOLVED'):void {
 const existing=run.critiques[0];const payload={issue_id:existing?.id||id(),run_id:run.snapshot.run_id,candidate_id:run.candidates[0]!.id,requirement_id:'R-TARGET-SLOPE-CONTEXT',target_evidence_ids:run.qualifications[1]?.evidence_ids||[],reason_code:'SCALE_MISMATCH',severity:'BLOCKING',status,summary:'60 m evidence cannot support the accepted 480 m comparison. Correct common-support evidence required.',repair_request:'Cite the 480 m common-support comparison evidence',resolution_evidence_ids:status==='RESOLVED'?run.qualifications[1]?.evidence_ids||[]:[]};
 const evidence=evidenceArtifact(run,'audit-evidence',payload,'CRITIQUE');run.critiques.push(evidence);
 emit(run,status==='OPEN'?'critic.issue_created':'qualification.updated',status==='OPEN'?'Scale mismatch identified; affected claim restricted.':'Previous → Current: corrected comparison at 480 m support.',{matrix_revision:status==='OPEN'?1:2});
}
export function advanceRun(run:MockRun):void {
 if(run.snapshot.state==='COMPLETED'||run.snapshot.state==='CANCELLED'||run.snapshot.state==='FAILED'||run.snapshot.state==='BLOCKED')return;
 if(run.pendingVerification&&run.pendingVerification.nextIndex<run.pendingVerification.scripts.length){scheduleVerification(run);return;}
 if(run.snapshot.state==='BUILDING_PASSPORT'&&!run.passport){void finishPassport(run);return;}
 if(run.stage<6){const states=marsMobility.states as M<'RunState'>[];run.snapshot.state=states[run.stage]!;
  if(run.stage===1){attachDisplayArtifacts(run);run.snapshot.target_profile_id=run.target.id;}
  if(run.stage===2)run.snapshot.candidate_ids=run.candidates.map(c=>c.id);
  if(run.stage===3){run.snapshot.qualification_ids=run.qualifications.map(q=>q.id);critique(run,'OPEN');}
  if(run.stage===4){critique(run,'RESOLVED');for(const row of run.qualifications.filter(q=>q.requirement_id==='R-TARGET-SLOPE-CONTEXT'))row.critic_status='RESOLVED';}
  if(run.stage===5){run.snapshot.pending_review={review_id:id(),kind:'EVIDENCE_READY',summary:'Evidence ready. Select a candidate and inspect the benchmark before PROVE IT.',evidence_ids:[],proposal_artifact_sha256:null,blocked_requirement_ids:[],allowed_actions:run.snapshot.rover_revision_id?['SELECT_CANDIDATE','PROVE_IT','BUILD_PORTFOLIO']:['SELECT_CANDIDATE','BUILD_PORTFOLIO'],created_at:timestamp,status:'PENDING'};
 if(run.snapshot.mode==='synthetic'&&db.settings.previewScenario==='review-proxy'&&!run.previewReviewInjected){
 const proposal=evidenceArtifact(run,'audit-evidence',{kind:'PROXY',summary:'Review the use of regional terrain context as a proxy only; clearance and missing mineral requirements remain UNKNOWN.',permitted_effect:'Acknowledge this display assumption; does not override any scientific requirement'} ,'ASSUMPTION');
 run.snapshot.pending_review={review_id:id(),kind:'PROXY',summary:'Acknowledge regional terrain context as a limited proxy. No scientific threshold or rover limit changes.',evidence_ids:[proposal.id],proposal_artifact_sha256:proposal.artifact_sha256,blocked_requirement_ids:['R-CLEARANCE'],allowed_actions:['APPROVE_EVIDENCE','REJECT_EVIDENCE'],created_at:timestamp,status:'PENDING'};run.previewReviewInjected=true;
 }
 (run.reviews ||= []).push(run.snapshot.pending_review);
 if(run.snapshot.mode==='synthetic'&&db.settings.previewScenario==='blocked-worker'&&!run.previewBlockedInjected){run.previewBlockedInjected=true;run.snapshot.pending_review=null;run.snapshot.state='BLOCKED';run.snapshot.blocked_dependencies=['worker'];emit(run,'run.blocked','Worker unavailable. Retry the recorded dependency with unchanged accepted inputs.');}
 }
  emit(run,'run.state_changed',`${run.snapshot.state}: synthetic practice replay`);run.stage++;
  if(run.stage===6&&!run.snapshot.rover_revision_id&&run.snapshot.state!=='BLOCKED')void finishPassport(run);
 }
}
function metric(metricId:string,value:number|null,unit='m'):M<'MeasuredMetric'>{return {metric_id:metricId,value,unit,support_scale_m:60,quantity_kind:'DERIVED',method_id:'synthetic-practice-replay',valid_fraction:1,uncertainty_note:'Unquantified; authored synthetic replay fixture'};}
function performVerification(run:MockRun,candidateId:string):void {
 const rover=run.snapshot.rover_revision_id?db.rovers[run.snapshot.rover_revision_id]:undefined;
 const isGraph=run.snapshot.scenario_config_id==='synthetic-graph-regression-v1';const isSearchLimit=db.settings.previewScenario==='searchLimit'||new URLSearchParams(globalThis.location?.search||'').get('mockScenario')==='searchLimit';
 let scripts:ReplayAttempt[]=clone(marsMobility.attempts);
 if(!isGraph&&candidateId===run.candidates[1]?.id)scripts=scripts.filter((_,index)=>index!==1).map((s)=>({...s,candidate:run.candidates[1]!.name}));
 if(isGraph)scripts=scripts.filter((_,index)=>index!==1).map(script=>({...script,candidate:run.candidates.find(candidate=>candidate.id===candidateId)!.name}));
 if(rover?.name==='PRACTICE-LITE'){scripts=scripts.slice(0,2);scripts[1]={...scripts[1]!,outcome:'FAIL',failureCategory:'ROVER',searchStatus:'EXHAUSTIVE_INFEASIBLE',reason:'NO_PERMITTED_REPAIR — NEW_CONTRACT_REQUIRED',next:null};run.exportFixture='supported-negative';}
 if(rover?.energy_model===null){scripts=scripts.slice(0,2);scripts[1]={...scripts[1]!,outcome:'INCONCLUSIVE',failureCategory:'DATA',searchStatus:'FOUND',energy:null,exposure:150,distance:230,reason:'ENERGY_UNCALIBRATED — DATA_BLOCKED',next:null};run.exportFixture='inconclusive';}
 if(rover?.name==='PRACTICE-SMALL-BATTERY'){scripts=[{...scripts[0]!,outcome:'FAIL',failureCategory:'ROVER',searchStatus:'EXHAUSTIVE_INFEASIBLE',reason:'C-ENERGY-RESERVE — NEW_CONTRACT_REQUIRED',next:null}];run.exportFixture='supported-negative';}
 if(isSearchLimit){scripts=[{...scripts[0]!,outcome:'INCONCLUSIVE',failureCategory:'SEARCH_LIMIT',searchStatus:'BUDGET_EXHAUSTED',reason:'Bounded search; not proof that no route exists',next:null}];run.exportFixture='inconclusive';}
 run.snapshot.pending_review=null;run.snapshot.state='DESIGNING_TEST';emit(run,'test.designed','Frozen benchmark accepted; modeled verification queued.');
 run.pendingVerification={scripts:clone(scripts),nextIndex:0};saveDatabase();scheduleVerification(run);
}
const activeVerification=new WeakSet<MockRun>();
function scheduleVerification(run:MockRun):void {
 if(activeVerification.has(run)||!run.pendingVerification)return;activeVerification.add(run);const {scripts,nextIndex}=run.pendingVerification;const rover=run.snapshot.rover_revision_id?db.rovers[run.snapshot.rover_revision_id]:undefined;
 scripts.forEach((script,index)=>{if(index<nextIndex)return;setTimeout(()=>{
 if(run.snapshot.state==='CANCELLED'||db.runs[run.snapshot.run_id]!==run)return;if(run.pendingVerification&&run.pendingVerification.nextIndex>index)return;const candidate=run.candidates.find(c=>c.name===script.candidate)!;
 const test:M<'VerificationTest'>={...recordBase(run.snapshot.run_id,run.snapshot.mode),candidate_id:candidate.id,mission_revision_id:run.snapshot.mission_revision_id,rover_revision_id:run.snapshot.rover_revision_id!,test_revision:index+1,requirement_ids:['R-EXPOSURE','R-TASKS','R-RESERVE'],route_artifact_sha256:seed.hash,waypoints_artifact_sha256:seed.hash,constraints_sha256:seed.hash,required_exposures:[{requirement_id:'R-EXPOSURE',metric_id:'unique_slope_exposure_m',lower:12,upper:18,minimum_distance_m:100}],solver_config:{max_expansions:100000,max_seconds:60,max_labels_per_node:100,seed:20261105},assumptions:[`Attempt ${index+1}; parent ${index>0?run.tests[index-1]?.id:'none'}; strategy ${script.strategy}`,'Accepted mission and rover hashes unchanged',`Changed elements: ${index===0?'none':index===1?'strategy: WAYPOINT_RETURN → EXPOSURE_COVERAGE':'candidate: Practice grid-r0c1 → Practice grid-r0c0'}`]};
 const result:M<'TestResult'>={...recordBase(run.snapshot.run_id,run.snapshot.mode),test_id:test.id,outcome:script.outcome as M<'VerificationOutcome'>,failure_category:script.failureCategory as M<'FailureCategory'>|null,search_status:script.searchStatus as M<'TestResult'>['search_status'],verified_route_sha256:script.searchStatus==='FOUND'?seed.hash:null,metrics:[metric('route_distance_m',script.distance),metric('energy_conservative_wh',script.searchStatus==='FOUND'&&rover?.energy_model!==null?script.energy:null,'Wh'),metric('unique_exposure_m:R-EXPOSURE',script.exposure),metric('tasks_completed',script.searchStatus==='FOUND'?2:null,'count'),metric('reserve_pct',script.energy===null||script.searchStatus!=='FOUND'||rover?.energy_model===null?null:98.33333333333333,'percent')],violations:script.outcome==='PASS'?[]:[{requirement_id:'R-EXPOSURE',code:script.reason,message:script.reason,evidence_ids:[]}],evidence_ids:[],verifier_version:'synthetic-practice-replay-v1',limitations:['Modeled terrain-feasibility verification — not physical rover execution',`Strategy: ${script.strategy}`,`Proof scope: ${script.searchStatus==='EXHAUSTIVE_INFEASIBLE'?'discrete candidate domain under frozen constraints':'evaluated route only'}`,`Changed elements: ${index===0?'none':index===1?'strategy: WAYPOINT_RETURN → EXPOSURE_COVERAGE':'candidate: Practice grid-r0c1 → Practice grid-r0c0'}`]};
 const bounded=script.failureCategory==='SEARCH_LIMIT';const energyBlocked=script.failureCategory==='DATA';const energyInfeasible=script.reason.startsWith('C-ENERGY-RESERVE');const found=script.searchStatus==='FOUND';const exposureSupported=script.outcome==='PASS'||energyBlocked;
 const benchmarkRows=[
 {constraint_id:'C-EXPOSURE-R-EXPOSURE',requirement_id:'R-EXPOSURE',rule:'≥ 100 m unique exposure in [12,18] deg',measured:bounded||energyInfeasible?null:script.exposure,threshold:100,unit:'m',margin:bounded||energyInfeasible?null:exposureSupported?50:-100,status:bounded||energyInfeasible?'INCONCLUSIVE':exposureSupported?'PASS':'FAIL'},
 {constraint_id:'C-TASKS',requirement_id:'R-TASKS',rule:'Visit W1 and W2 on the same route',measured:found?2:null,threshold:2,unit:'count',margin:found?0:null,status:found?'PASS':'INCONCLUSIVE'},
 {constraint_id:'C-ENERGY-RESERVE',requirement_id:'R-RESERVE',rule:'Return with at least 20 percent modeled battery reserve',measured:found&&!energyBlocked&&rover?.energy_model!==null?98.33333333333333:null,threshold:20,unit:'percent',margin:found&&!energyBlocked&&rover?.energy_model!==null?78.33333333333333:null,status:energyInfeasible?'FAIL':found&&!energyBlocked&&rover?.energy_model!==null?'PASS':'INCONCLUSIVE'},
 ];
 const design=publishAttemptArtifacts(run,test,script,(algorithm,payload,kind)=>evidenceArtifact(run,algorithm,payload,kind));result.verified_route_sha256=design.routeHash;
 const verify=evidenceArtifact(run,'verify-route',{operation:'VERIFY_ROUTE',outcome:result.outcome,failure_category:result.failure_category,search_status:result.search_status,verified_route_sha256:result.verified_route_sha256,metrics:result.metrics,violations:result.violations.filter(v=>v.code==='EXPOSURE_SHORTFALL').map(v=>({code:v.code,requirement_id:v.requirement_id,constraint_id:'C-EXPOSURE-R-EXPOSURE',observed:0,threshold:100,unit:'m',segment_from_index:null,segment_to_index:null,message:v.message})),benchmark_rows:benchmarkRows,telemetry_artifact_key:'telemetry',verification_evidence:{evidence_id:run.evidence[0]!.id},limitations:result.limitations},'VERIFICATION');
 const samples=[{index:0,node_id:'S',cumulative_distance_m:0,elapsed_s:0,lon:-111,lat:35,elevation_m:0,segment_surface_slope_deg:0,cumulative_energy_conservative_wh:rover?.energy_model===null?null:0,reserve_pct:rover?.energy_model===null?null:100,in_band_requirement_ids:[]},{index:1,node_id:'W1',cumulative_distance_m:60,elapsed_s:120,lon:-110.995,lat:35.005,elevation_m:3,segment_surface_slope_deg:15,cumulative_energy_conservative_wh:rover?.energy_model===null?null:12,reserve_pct:rover?.energy_model===null?null:99,in_band_requirement_ids:['R-EXPOSURE']},{index:2,node_id:'S',cumulative_distance_m:script.distance||0,elapsed_s:460,lon:-111,lat:35,elevation_m:0,segment_surface_slope_deg:0,cumulative_energy_conservative_wh:rover?.energy_model===null?null:script.energy,reserve_pct:script.energy===null||rover?.energy_model===null?null:98.33333333333333,in_band_requirement_ids:[]}];
 const telemetry=script.searchStatus==='FOUND'?evidenceArtifact(run,'route-telemetry',{schema_version:'1.0',route_sha256:design.routeHash!,constraints_sha256:design.constraintsHash,samples}):null;result.evidence_ids=[verify.id,...(telemetry?[telemetry.id]:[]),...design.evidenceIds];run.tests.push(test);run.results.push(result);run.snapshot.test_ids=run.tests.map(t=>t.id);run.snapshot.test_result_ids=run.results.map(r=>r.id);
 for(const row of run.qualifications.filter(q=>q.candidate_id===candidate.id&&['R-EXPOSURE','R-TASKS','R-RESERVE'].includes(q.requirement_id))){
 const benchmark=benchmarkRows.find(b=>b.requirement_id===row.requirement_id)!;
 if(!(script.searchStatus!=='FOUND'&&row.requirement_id!=='R-EXPOSURE'&&benchmark.status==='INCONCLUSIVE'&&row.status==='PASS'))row.status=benchmark.status==='INCONCLUSIVE'?'UNKNOWN':benchmark.status as M<'QualificationStatus'>;
 row.explanation='FINAL — '+script.reason;
 const prior=run.artifacts[run.evidence.find(e=>e.id===row.evidence_ids[0])?.artifact_sha256||''] as Record<string,unknown>|undefined;
 const updated=evidenceArtifact(run,'compare-requirement',{...(prior||{}),operation:'COMPARE_REQUIREMENT',requirement_id:row.requirement_id,proposed_status:row.status,evaluation_stage:'FINAL',reason_code:script.outcome==='PASS'?'ROUTE_VERIFIED':script.outcome==='FAIL'?'ROUTE_FAILED':'ENERGY_MODEL_MISSING',comparison_evidence:{evidence_id:verify.id},explanation:row.explanation,measured_value:benchmark.measured,measured_unit:benchmark.unit});row.evidence_ids=[updated.id,verify.id];}
 if(run.pendingVerification)run.pendingVerification.nextIndex=index+1;
 run.snapshot.state=index===scripts.length-1?'BUILDING_PASSPORT':'REPLANNING';emit(run,'verification.completed',`Attempt ${index+1}: ${result.outcome}; ${script.reason}`,{attempt_number:index+1,strategy:script.strategy,parent_attempt:index||null,changed_elements:result.limitations[3],benchmark_rows:benchmarkRows,proof_scope:result.limitations[2]});
 if(index===scripts.length-1){activeVerification.delete(run);run.snapshot.selected_candidate_id=candidate.id;void finishPassport(run);}
 },600*(index-nextIndex+1));});
}
function compatibility(run:MockRun,candidateId:string):M<'CompatibilityAssessment'> {
 const rover=db.rovers[run.snapshot.rover_revision_id!];const reserve=run.qualifications.find(q=>q.candidate_id===candidateId&&q.requirement_id==='R-RESERVE');
 return {id:id(),run_id:run.snapshot.run_id,candidate_id:candidateId,rover_revision_id:run.snapshot.rover_revision_id!,mode:run.snapshot.mode,preliminary:run.results.length===0,dimensions:[{metric_id:'max_surface_slope_deg',status:rover?.name==='PRACTICE-LITE'?'FAIL':rover?.name==='ARES-1'||rover?.name==='PRACTICE-NO-ENERGY-MODEL'||rover?.name==='PRACTICE-SMALL-BATTERY'?'PASS':'UNKNOWN',evidence_ids:[],explanation:`Declared ${rover?.max_slope_deg??'Unknown'} deg; required band upper 18 deg. Declared capability, not observed.`},{metric_id:'ground_clearance_m',status:'UNKNOWN',evidence_ids:[],explanation:'SCALE_UNSUPPORTED; 60 m support cannot resolve 0.20 m clearance'},{metric_id:'energy_reserve_pct',status:reserve?.status||'UNKNOWN',evidence_ids:[],explanation:run.results.length?'See verifier receipt':'ROUTE_NOT_VERIFIED'},{metric_id:'obstacle_height',status:'UNKNOWN',evidence_ids:[],explanation:'Rover obstacle height is Unknown'},{metric_id:'required_capability',status:'PASS',evidence_ids:[],explanation:'geological_sampling declared, not observed'}]};
}
export function dispatch(method:string,path:string,body:unknown,headers=new Headers()):MockResponse {
 if(method!=='GET'&&method!=='POST')return error('METHOD_NOT_ALLOWED','This frozen resource does not accept this method',405);
 const url=new URL(path,'http://mock.invalid');const parts=url.pathname.split('/').filter(Boolean);const entity=parts[0],objectId=parts[1],action=parts[2];
 if(method==='POST'){
 const valid=validateMutation(url.pathname,body);if(!valid.valid)return error('VALIDATION_FAILED','Request does not satisfy the frozen API schema',422,{fields:valid.errors});
 const key=headers.get('Idempotency-Key');if(!key)return error('IDEMPOTENCY_KEY_REQUIRED','Every mutation requires an Idempotency-Key UUID',422);
 const cacheKey=`${method}:${url.pathname}:${key}`;const previous=db.idempotency[cacheKey];const serialized=JSON.stringify(body);
 if(previous)return previous.body===serialized?json(clone(previous.value),previous.status):error('IDEMPOTENCY_CONFLICT','Idempotency key reused with a different payload');
 const result=mutate(entity,objectId,action,body);if(result.status<400){db.idempotency[cacheKey]={body:serialized,status:result.status,value:clone(result.body)};saveDatabase();}return result;
 }
 if(entity==='health')return json({status:'ok'});
 if(entity==='capabilities')return json({modes:['synthetic','replay','live'],live_ai_configured:false,earthdata_configured:false,worker_healthy:true,adapters:['synthetic_practice','local_dataset'],dataset_locks:['practice-lock-v1'],export_formats:['html','json','csv'],scenario_config_ids:scenarios.map(s=>s.id),default_scenario_config_id:scenarios[0]!.id});
 if(entity==='configuration')return scenarios.find(s=>s.id===action)?json(scenarios.find(s=>s.id===action)):error('NOT_FOUND','Scenario not found',404);
 if(entity==='missions')return objectId?(db.missions[objectId]?json(db.missions[objectId]):error('NOT_FOUND','Mission not found',404)):list(Object.values(db.missions),url);
 if(entity==='mission-drafts')return db.drafts[objectId!]?json(db.drafts[objectId!]):error('NOT_FOUND','Draft not found',404);
 if(entity==='mission-revisions')return db.contracts[objectId!]?json(db.contracts[objectId!]):error('NOT_FOUND','Contract not found',404);
 if(entity==='rovers'||entity==='rover-revisions'){if(!objectId)return list(Object.values(db.rovers),url);const rover=db.rovers[objectId]||Object.values(db.rovers).find(r=>r.rover_id===objectId);return rover?json(rover):error('NOT_FOUND','Rover not found',404);}
 if(entity==='jobs')return db.jobs[objectId!]?json(db.jobs[objectId!]):error('NOT_FOUND','Job not found',404);
 if(entity==='runs')return objectId?(db.runs[objectId]?json(db.runs[objectId]!.snapshot):error('NOT_FOUND','Run not found',404)):list(Object.values(db.runs).map(r=>r.snapshot),url);
 const scopedRunId=url.searchParams.get('run_id');
 const run=scopedRunId?db.runs[scopedRunId]:objectId?Object.values(db.runs).find(r=>r.snapshot.run_id===objectId||r.target.id===objectId||r.candidates.some(c=>c.id===objectId)||r.qualifications.some(q=>q.id===objectId)||r.tests.some(t=>t.id===objectId)||r.results.some(t=>t.id===objectId)||r.evidence.some(e=>e.id===objectId)||r.snapshot.passport_id===objectId||r.portfolios.some(p=>p.id===objectId)||r.snapshot.pending_review?.review_id===objectId||r.reviews?.some(review=>review.review_id===objectId)||r.receipts.some(t=>t.id===objectId)||Object.hasOwn(r.artifacts,objectId)):undefined;
 if(!run)return error('NOT_FOUND','Object not found in this workspace',404);
 const candidateId=url.searchParams.get('candidate_id')||run.snapshot.selected_candidate_id||run.candidates[0]!.id;
 if(entity==='target-profiles')return json(run.target);
 if(entity==='candidates')return objectId?json(run.candidates.find(c=>c.id===objectId)):list(run.candidates,url);
 if(entity==='qualifications')return objectId?json(run.qualifications.find(q=>q.id===objectId)):list(run.qualifications.filter(q=>!url.searchParams.has('candidate_id')||q.candidate_id===candidateId),url);
 if(entity==='tests')return objectId?json(run.tests.find(t=>t.id===objectId)):list(run.tests,url);
 if(entity==='test-results')return json(run.results.find(r=>r.id===objectId));
 if(entity==='compatibility')return run.snapshot.rover_revision_id?json(compatibility(run,candidateId)):error('ROVER_REQUIRED','Rover verification unavailable: no rover supplied');
 if(entity==='evidence')return json(run.evidence.find(e=>e.id===objectId));
 if(entity==='artifacts'){const artifact=run.artifacts[objectId!];if(artifact&&typeof artifact==='object'&&'mockImage' in artifact){const asset=(artifact as {mockImage:{contentBase64:string;mediaType:string}}).mockImage;return {status:200,body:asset.contentBase64,headers:{'Content-Type':asset.mediaType,'X-Mock-Base64':'1','X-Artifact-SHA256':objectId!,'X-Content-Type-Options':'nosniff'}};}return Object.hasOwn(run.artifacts,objectId!)?{status:200,body:canonicalMockJson(artifact),headers:{'Content-Type':'application/json','X-Artifact-SHA256':objectId!,'X-Content-Type-Options':'nosniff'}}:error('NOT_FOUND','Artifact not referenced by this workspace',404);}
 if(entity==='critiques')return list(run.critiques,url);
 if(entity==='reviews'){const review=run.reviews?.find(item=>item.review_id===objectId)||run.snapshot.pending_review;return review?json(review):error('NOT_FOUND','Review not found',404);}
 if(entity==='agent-actions')return list(run.actions,url);
 if(entity==='tool-receipts')return json(run.receipts.find(r=>r.id===objectId));
 if(entity==='display-layers')return list((run.layers||[]).filter(layer=>url.searchParams.has('candidate_id')?layer.candidate_id===candidateId:url.searchParams.has('target_profile_id')?layer.target_profile_id===url.searchParams.get('target_profile_id'):true),url);
 if(entity==='portfolios')return json(run.portfolios.find(p=>p.id===objectId));
 if(entity==='passports'){
 if(action==='exports'){
 const format=parts[3]!;const entry=entryFor(run);const output=entry?.exports[format];if(!output)return error('EXPORT_UNAVAILABLE','Export fixture has not been generated',503);
 const key=`${objectId}:${format}`;
 if(!db.exportsRequested[key]){db.exportsRequested[key]=true;saveDatabase();return json({id:id(),state:'RUNNING',progress_step:'Rendering frozen passport',run_id:run.snapshot.run_id,preparation_id:null,proposed_revision_id:null,error:null},202,{'Retry-After':'1'});}
 const content=exportFiles[`./exports/${output.file}`];if(content===undefined)return error('EXPORT_UNAVAILABLE','Export bytes unavailable',503);
 return {status:200,body:content,headers:{'Content-Type':output.mediaType,'Content-Disposition':`attachment; filename="${output.filename}"`,'X-Artifact-SHA256':output.sha256,ETag:`"${output.sha256}"`,'X-Content-Type-Options':'nosniff'}};
 }
 return json(run.passport);
 }
 return error('NOT_FOUND','Operation unavailable',404);
}
function mutate(entity:string|undefined,objectId:string|undefined,action:string|undefined,body:unknown):MockResponse {
 const input=asObject(body);
 if(entity==='missions'&&!objectId)return json(createMission(body as M<'MissionDraftInput'>),201);
 if(entity==='missions'&&objectId){const mission=db.missions[objectId];if(!mission)return error('NOT_FOUND','Mission not found',404);const conflict=revision(mission.revision,body);if(conflict)return conflict;
 if(action==='drafts'){const draftId=id();const draft: M<'MissionDraft'>={id:draftId,workspace_id:workspaceId,mission_id:objectId,revision:mission.revision+1,created_at:timestamp,draft:clone(input.draft) as M<'MissionDraftInput'>};db.drafts[draftId]=draft;mission.current_draft_id=draftId;mission.name=draft.draft.name;mission.revision++;return json(draft,201);}
 if(action==='revisions'||action==='fingerprint'){
 const draft=db.drafts[mission.current_draft_id!]!.draft;
 const preset=seed.missionPresets[draft.target.body==='MOON'?'MOON':'MARS'];
 const content=(action==='revisions'?input.contract:{...clone(preset),name:draft.name,objective:draft.objective,target:draft.target}) as M<'MissionContent'>;
 const contractId=id();const contract:M<'MissionTestContract'>={...content,schema_version:'1.0',id:contractId,workspace_id:workspaceId,mission_id:objectId,revision:mission.revision+1,created_at:timestamp,accepted_at:null,content_sha256:mockArtifactHash(content)};db.contracts[contractId]=contract;mission.current_contract_id=contractId;mission.revision++;
 if(action==='revisions')return json(contract,201);
 const jobId=id(),preparationId=id();db.jobs[jobId]={id:jobId,state:'SUCCEEDED',progress_step:'Proposed contract requires explicit acceptance',run_id:null,preparation_id:preparationId,proposed_revision_id:contractId,error:null};return json({preparation_id:preparationId,job_id:jobId,mission_id:objectId,revision:mission.revision},202);
 }
 if(action==='accept'){const contract=db.contracts[String(input.revision_id)];if(!contract||contract.mission_id!==objectId)return error('NOT_FOUND','Revision not found in this mission',404);contract.accepted_at=timestamp;mission.accepted_contract_id=contract.id;mission.revision++;return json(contract);}
 }
 if(entity==='rovers'){
 if(!objectId){const roverId=id(),revisionId=id();const rover:M<'RoverProfile'>={...clone(body as M<'RoverInput'>),schema_version:'1.0',id:revisionId,rover_id:roverId,workspace_id:workspaceId,revision:1,created_at:timestamp,content_sha256:mockArtifactHash(body)};db.rovers[revisionId]=rover;return json(rover,201);}
 const previous=db.rovers[objectId]||Object.values(db.rovers).find(r=>r.rover_id===objectId);if(!previous)return error('NOT_FOUND','Rover not found',404);const conflict=revision(previous.revision,body);if(conflict)return conflict;const revisionId=id();const rover={...clone(previous),...clone(input.profile as M<'RoverInput'>),id:revisionId,revision:previous.revision+1,content_sha256:mockArtifactHash(input.profile)};db.rovers[revisionId]=rover;return json(rover,201);
 }
 if(entity==='runs'&&!objectId){
 const create=body as M<'RunCreateInput'>;
 if(create.mode==='live')return error(liveNoKey.code,liveNoKey.message,503,{dependency:liveNoKey.dependency});
 const contract=db.contracts[create.mission_revision_id];if(!contract?.accepted_at)return error('CONTRACT_NOT_ACCEPTED','Accept the exact displayed mission revision before starting');
 const scenario=scenarios.find(s=>s.id===create.scenario_config_id);if(!scenario||!scenario.allowed_modes.includes(create.mode))return error('AWAITING_DATASETS','Scenario unavailable; bind datasets before starting',422);
 if(scenario.body!==contract.target.body)return error('BODY_MISMATCH','Mission body differs from scenario body',422);
 const run=makeRun(create);return json({run_id:run.snapshot.run_id,job_id:null,command_id:id(),revision:run.snapshot.revision},202);
 }
 if(entity==='runs'&&objectId&&action==='actions'){
 const run=db.runs[objectId];if(!run)return error('NOT_FOUND','Run not found',404);const conflict=revision(run.snapshot.revision,body);if(conflict)return conflict;
 const request=body as M<'RunAction'>;const payload=request.payload;
 if(request.action_type==='PROVE_IT'&&!run.snapshot.rover_revision_id)return error('ROVER_REQUIRED','Rover verification unavailable: no rover supplied');
 const terminal=['COMPLETED','CANCELLED','FAILED'].includes(run.snapshot.state);if(terminal&&['PROVE_IT','RETRY','APPROVE_EVIDENCE','REJECT_EVIDENCE','NOMINATE_CANDIDATE'].includes(request.action_type))return error('ACTION_NOT_ALLOWED','A terminal investigation cannot be resumed or changed');
 if(request.action_type==='RETRY'&&(run.snapshot.state!=='BLOCKED'||!run.snapshot.blocked_dependencies.includes(request.payload.dependency_id)))return error('ACTION_NOT_ALLOWED','Only a recorded blocked dependency can be retried');
 if(request.action_type==='CANCEL'&&terminal)return json({run_id:objectId,job_id:null,command_id:id(),revision:run.snapshot.revision},202);
 if(request.action_type==='CANCEL'){run.snapshot.state='CANCELLED';emit(run,'run.cancelled','Cancelled by the operator; completed evidence retained.');}
 else if(request.action_type==='SELECT_CANDIDATE') {if(!run.candidates.some(c=>c.id===request.payload.candidate_id))return error('NOT_FOUND','Candidate belongs to a different run',404);run.snapshot.selected_candidate_id=request.payload.candidate_id;emit(run,'run.state_changed','Candidate selection confirmed by the backend.');}
 else if(request.action_type==='PROVE_IT'){if(run.snapshot.pending_review&&run.snapshot.pending_review.kind!=='EVIDENCE_READY'&&run.snapshot.pending_review.status==='PENDING')return error('REVIEW_REQUIRED','Review the exact pending assumption before authorizing verification');if(!run.snapshot.rover_revision_id)return error('ROVER_REQUIRED','Rover verification unavailable: no rover supplied');if(!run.candidates.some(c=>c.id===request.payload.candidate_id))return error('NOT_FOUND','Candidate not found',404);if(run.snapshot.state!=='AWAITING_REVIEW')return error('ACTION_NOT_ALLOWED','PROVE IT requires reviewed evidence and an available candidate');performVerification(run,request.payload.candidate_id);}
 else if(request.action_type==='BUILD_PORTFOLIO'){const valid=request.payload.candidate_ids.filter(cid=>run.candidates.some(c=>c.id===cid));if(valid.length!==request.payload.candidate_ids.length)return error('NOT_FOUND','Portfolio candidate belongs to another run',404);const mission=db.contracts[run.snapshot.mission_revision_id]!;const portfolio:M<'CompositePortfolio'>={...recordBase(objectId,run.snapshot.mode),candidate_ids:valid.slice(0,request.payload.max_sites),requirement_assignments:mission.requirements.map(r=>({requirement_id:r.id,candidate_ids:r.operator==='NOT_NATURALLY_REPRODUCIBLE'?[]:valid.slice(0,1),coverage:r.operator==='NOT_NATURALLY_REPRODUCIBLE'?'GAP':'UNKNOWN'})),objective_value:0,algorithm_id:'exhaustive-subset-v1',residual_requirement_ids:mission.requirements.map(r=>r.id),limitations:['Separate campaigns do not establish co-located verification','Site tests unverified; coverage remains UNKNOWN']};run.portfolios.push(portfolio);run.snapshot.portfolio_ids.push(portfolio.id);emit(run,'qualification.updated','Portfolio assembled with explicit residual gaps and unknowns.');}
 else if(request.action_type==='SELECT_PORTFOLIO'){if(!run.portfolios.some(p=>p.id===request.payload.portfolio_id))return error('NOT_FOUND','Portfolio belongs to another run',404);run.snapshot.selected_portfolio_id=request.payload.portfolio_id;emit(run,'qualification.updated','Portfolio selection confirmed.');}
 else if(request.action_type==='APPROVE_EVIDENCE'||request.action_type==='REJECT_EVIDENCE'){
 const review=run.snapshot.pending_review;if(!review||review.review_id!==request.payload.review_id)return error('NOT_FOUND','Review is not pending in this run',404);
 if(review.kind==='EVIDENCE_READY'||!review.allowed_actions.includes(request.action_type))return error('ACTION_NOT_ALLOWED','Scientific evidence cannot be approved or overridden');
 if(request.payload.evidence_ids.some(evidenceId=>!review.evidence_ids.includes(evidenceId)))return error('NOT_FOUND','Review evidence is not part of this proposal',404);
 review.status=request.action_type==='APPROVE_EVIDENCE'?'APPROVED':'REJECTED';run.snapshot.pending_review=null;run.snapshot.state='AWAITING_REVIEW';emit(run,'review.required',`${review.status}: proxy display assumption recorded. Accepted criteria, rover and scientific rows unchanged.`);
 }
 else if(request.action_type==='RETRY'){run.snapshot.blocked_dependencies=[];if(request.payload.dependency_id==='mock-renderer'){run.snapshot.state='BUILDING_PASSPORT';emit(run,'run.state_changed','Retrying the frozen export bundle without changing scientific inputs.');void finishPassport(run);}else{run.stage=5;run.snapshot.state='VALIDATING';emit(run,'run.state_changed','Dependency retry queued with unchanged inputs.');}}
 else if(request.action_type==='NOMINATE_CANDIDATE'){const candidate={...clone(run.candidates[0]!),...recordBase(objectId,run.snapshot.mode),name:request.payload.name,aoi:request.payload.aoi,origin:'USER_SUPPLIED' as const,novelty_status:'NOT_ASSESSED' as const};run.candidates.push(candidate);run.snapshot.candidate_ids.push(candidate.id);emit(run,'evidence.created','User-supplied candidate queued for analysis.');}
 void payload;return json({run_id:objectId,job_id:null,command_id:id(),revision:run.snapshot.revision},202);
 }
 return error('NOT_FOUND','Operation unavailable',404);
}
function response(result:MockResponse):Response {
 if(result.headers?.['X-Mock-Base64']==='1'){const headers={...result.headers};delete headers['X-Mock-Base64'];const bytes=Uint8Array.from(atob(String(result.body)),character=>character.charCodeAt(0));return new HttpResponse(bytes,{status:result.status,headers});}
 if(typeof result.body==='string')return new HttpResponse(result.body,{status:result.status,headers:result.headers});
 return HttpResponse.json(result.body as Record<string,unknown>,{status:result.status,headers:result.headers});
}
export const handlers=[http.get('*/auth/session',()=>HttpResponse.json({workspace_id:workspaceId,role:'OWNER',csrf_token:'development-only-preview-csrf',user:{id:'mock-preview-owner'}})),http.all('*/api/v1/*',async({request})=>{
 if(db.settings.latencyMs)await delay(db.settings.latencyMs);
 const url=new URL(request.url);const path=url.pathname.replace(/^.*\/api\/v1/,'')+url.search;
 if(request.method==='GET'&&/\/runs\/[^/]+\/events/.test(path)){
  const runId=path.split('/')[2]!;const run=db.runs[runId];if(!run)return response(error('NOT_FOUND','Run not found',404));
  const after=Math.max(Number(url.searchParams.get('after')||0),Number(request.headers.get('Last-Event-ID')||0));if(Number(url.searchParams.get('after'))<0)return response(error('EVENT_CURSOR_EXPIRED','Event cursor expired; reload the snapshot',410));
  const encoder=new TextEncoder();let cursor=after;let timer:ReturnType<typeof setInterval>|undefined;
  const stream=new ReadableStream<Uint8Array>({start(controller){const send=()=>{if(request.signal.aborted){clearInterval(timer);controller.close();return;}for(const event of run.events.filter(e=>e.seq>cursor)){controller.enqueue(encoder.encode(`id: ${event.seq}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`));cursor=event.seq;}controller.enqueue(encoder.encode(': heartbeat\n\n'));if(['COMPLETED','CANCELLED','FAILED'].includes(run.snapshot.state)){clearInterval(timer);controller.close();}};timer=setInterval(send,200);send();},cancel(){clearInterval(timer);}});
  return new HttpResponse(stream,{headers:{'Content-Type':'text/event-stream','Cache-Control':'no-cache'}});
 }
 if(request.method==='GET'&&/\/passports\/[^/]+\/exports\//.test(path)){
  const passportId=path.split('/')[2]!;const format=path.split('/')[4]!.split('?')[0]!;const run=Object.values(db.runs).find(item=>item.snapshot.passport_id===passportId);
  const key=`${passportId}:${format}`;
  if(run?.exportBundle&&db.exportsRequested[key]){try{return await renderMockExport(run.exportBundle,format);}catch(err){return response(error('EXPORT_UNAVAILABLE',err instanceof Error?err.message:'Renderer bridge unavailable',503));}}
 }
 const body=request.method==='POST'?await request.json().catch(()=>null):null;
 return response(dispatch(request.method,path,body,request.headers));
})];
