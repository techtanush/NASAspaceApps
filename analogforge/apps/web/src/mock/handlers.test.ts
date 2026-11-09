import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import { writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { setupServer } from 'msw/node';
import { handlers,dispatch,advanceRun } from './handlers';
import { db,seed,resetDatabase,type MockRun } from './state';
import * as rendererBridge from '../api/mockBridge';
import { SSEParser } from '../api/runStream';
import type { components } from '../generated/schema';
type S=components['schemas'];
const scenarioArtifacts:Record<string,Record<string,unknown>>={};
const post=(path:string,body:unknown)=>dispatch('POST',path,body,new Headers({'Idempotency-Key':crypto.randomUUID()}));
function boot(body:'MARS'|'MOON'='MARS',roverName:string|null='ARES-1',scenario='synthetic-mars-mobility-v1'):MockRun {
 const preset=seed.missionPresets[body];const {forbidden_actions:_actions,...draft}=preset;void _actions;
 const header=post('/missions',draft).body as S['MissionHeader'];
 const prep=post(`/missions/${header.id}/fingerprint`,{expected_revision:header.revision,mode:'synthetic',rover_revision_id:null}).body as S['PreparationAccepted'];
 const revisionId=db.jobs[prep.job_id]!.proposed_revision_id!;
 post(`/missions/${header.id}/accept`,{expected_revision:header.revision,revision_id:revisionId});
 const rover=Object.values(db.rovers).find(r=>r.name===roverName);
 const created=post('/runs',{mission_revision_id:revisionId,rover_revision_id:rover?.id||null,mode:'synthetic',dataset_lock_id:'practice-lock-v1',scenario_config_id:scenario}).body as S['CommandAccepted'];
 const run=db.runs[created.run_id]!;for(let i=0;i<6;i++)advanceRun(run);return run;
}
beforeEach(()=>resetDatabase());
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
it('all43: real MSW GET events streams ordered replay and larger Last-Event-ID cursor with terminal close',async()=>{
 const run=boot();run.snapshot.state='COMPLETED';const server=setupServer(...handlers);server.listen({onUnhandledRequest:'error'});
 try{
  const response=await fetch(`http://localhost/api/v1/runs/${run.snapshot.run_id}/events?after=0`,{headers:{'Last-Event-ID':'2'}});expect(response.status).toBe(200);expect(response.headers.get('Content-Type')).toBe('text/event-stream');
  const received:S['RunEvent'][]=[];const parser=new SSEParser(message=>received.push(JSON.parse(message.data) as S['RunEvent']));parser.feed(await response.text());expect(received.length).toBeGreaterThan(0);expect(received[0]!.seq).toBe(3);expect(received.map(e=>e.seq)).toEqual(run.events.filter(e=>e.seq>2).map(e=>e.seq));expect(received.every(e=>e.run_id===run.snapshot.run_id)).toBe(true);
  const expired=await fetch(`http://localhost/api/v1/runs/${run.snapshot.run_id}/events?after=-1`);expect(expired.status).toBe(410);expect(await expired.json()).toMatchObject({error:{code:'EVENT_CURSOR_EXPIRED'}});
 }finally{server.close();}
});
it.each([
 ['ARES-1','PASS',null,3],['PRACTICE-LITE','FAIL','ROVER',2],['PRACTICE-NO-ENERGY-MODEL','INCONCLUSIVE','DATA',2],['PRACTICE-SMALL-BATTERY','FAIL','ROVER',1],
])('storyline %s retains every attempt, contract hashes and scientific category',async(name,outcome,category,count)=>{
 vi.useFakeTimers();const run=boot('MARS',name as string);const mission=cloneContract(run);
 const response=post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}});expect(response.status).toBe(202);await vi.advanceTimersByTimeAsync(2500);
 expect(run.results).toHaveLength(count as number);expect(run.results.at(-1)).toMatchObject({outcome,failure_category:category});expect(db.contracts[run.snapshot.mission_revision_id]).toEqual(mission);expect(run.snapshot.state).toBe('COMPLETED');expect(run.exportBundle).toBeDefined();
 scenarioArtifacts[String(name)]=structuredClone(run.artifacts);writeFileSync('src/mock/fixtures/scenario-artifacts.json',JSON.stringify(scenarioArtifacts,null,2)+'\n');
 if(name==='PRACTICE-NO-ENERGY-MODEL')expect(run.results.at(-1)!.metrics.find(m=>m.metric_id==='reserve_pct')!.value).toBeNull();
});
function cloneContract(run:MockRun){return structuredClone(db.contracts[run.snapshot.mission_revision_id]);}
it('Moon no-rover keeps thermal unknown, physical gaps and rejects verification without inventing a rover',async()=>{
 const run=boot('MOON',null,'synthetic-moon-gap-v1');await Promise.resolve();expect(run.snapshot.rover_revision_id).toBeNull();expect(run.qualifications.some(q=>q.requirement_id==='R-THERMAL'&&q.status==='UNKNOWN')).toBe(true);expect(run.qualifications.some(q=>q.status==='GAP')).toBe(true);expect(dispatch('GET',`/compatibility?run_id=${run.snapshot.run_id}`,null).status).toBe(409);expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}}).body).toMatchObject({error:{code:'ROVER_REQUIRED'}});expect(run.passport).not.toBeNull();
});
it('invalid rover import never persists and stale semantic command cannot overwrite selection',()=>{
 expect(post('/rovers',{name:'broken',max_slope_deg:-1}).status).toBe(422);expect(Object.keys(db.rovers)).toHaveLength(4);
 const run=boot();const revision=run.snapshot.revision;expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'SELECT_CANDIDATE',expected_revision:revision,payload:{candidate_id:run.candidates[0]!.id}}).status).toBe(202);expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'SELECT_CANDIDATE',expected_revision:revision,payload:{candidate_id:run.candidates[1]!.id}}).status).toBe(409);expect(run.snapshot.selected_candidate_id).toBe(run.candidates[0]!.id);
});
it('run-local resource identity and terminal state policy prevent cross-run stale reads and revival',()=>{
 const first=boot();const second=boot();expect(first.candidates[0]!.id).not.toBe(second.candidates[0]!.id);expect(first.qualifications[0]!.id).not.toBe(second.qualifications[0]!.id);
 expect((dispatch('GET',`/candidates/${second.candidates[0]!.id}`,null).body as S['EarthAnalogCandidate']).run_id).toBe(second.snapshot.run_id);
 expect(post(`/runs/${first.snapshot.run_id}/actions`,{action_type:'CANCEL',expected_revision:first.snapshot.revision,payload:{}}).status).toBe(202);
 expect(post(`/runs/${first.snapshot.run_id}/actions`,{action_type:'RETRY',expected_revision:first.snapshot.revision,payload:{dependency_id:'absent'}}).status).toBe(409);expect(first.snapshot.state).toBe('CANCELLED');
 const pinned=structuredClone(db.contracts[first.snapshot.mission_revision_id]);expect(dispatch('PATCH',`/mission-revisions/${first.snapshot.mission_revision_id}`,{name:'changed'}).status).toBe(405);expect(db.contracts[first.snapshot.mission_revision_id]).toEqual(pinned);
});
it('reload during modeled verification resumes persisted pending attempts without duplicate work',async()=>{
 vi.useFakeTimers();const run=boot();post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}});await vi.advanceTimersByTimeAsync(650);expect(run.results).toHaveLength(1);
 const reloaded=structuredClone(run);db.runs[run.snapshot.run_id]=reloaded;vi.clearAllTimers();advanceRun(reloaded);await vi.advanceTimersByTimeAsync(1300);expect(reloaded.results).toHaveLength(3);expect(reloaded.snapshot.state).toBe('COMPLETED');expect(reloaded.results.map(result=>result.outcome)).toEqual(['FAIL','FAIL','PASS']);
});
it('no-energy records exposure/tasks PASS independently of overall INCONCLUSIVE, reserve and every energy sample stay Unknown',async()=>{
 vi.useFakeTimers();const run=boot('MARS','PRACTICE-NO-ENERGY-MODEL');post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[1]!.id}});await vi.advanceTimersByTimeAsync(1500);
 const rows=run.qualifications.filter(q=>q.candidate_id===run.candidates[1]!.id);expect(rows.find(q=>q.requirement_id==='R-EXPOSURE')!.status).toBe('PASS');expect(rows.find(q=>q.requirement_id==='R-TASKS')!.status).toBe('PASS');expect(rows.find(q=>q.requirement_id==='R-RESERVE')!.status).toBe('UNKNOWN');
 const latest=run.results.at(-1)!;const verifyEvidence=run.evidence.find(e=>e.id===latest.evidence_ids[0])!;const payload=run.artifacts[verifyEvidence.artifact_sha256!] as {benchmark_rows:{requirement_id:string;status:string;margin:number|null}[]};expect(payload.benchmark_rows.find(b=>b.requirement_id==='R-EXPOSURE')).toMatchObject({status:'PASS',margin:50});expect(payload.benchmark_rows.find(b=>b.requirement_id==='R-RESERVE')).toMatchObject({status:'INCONCLUSIVE',margin:null});
 for(const evidence of run.evidence.filter(e=>e.algorithm_id==='route-telemetry')){const telemetry=run.artifacts[evidence.artifact_sha256!] as {samples:{cumulative_energy_conservative_wh:number|null;reserve_pct:number|null}[]};expect(telemetry.samples.every(sample=>sample.cumulative_energy_conservative_wh===null&&sample.reserve_pct===null)).toBe(true);}
 const assessment=dispatch('GET',`/compatibility?run_id=${run.snapshot.run_id}&candidate_id=${run.candidates[1]!.id}`,null).body as S['CompatibilityAssessment'];expect(assessment.dimensions.find(d=>d.metric_id==='energy_reserve_pct')!.status).toBe('UNKNOWN');
});
it('declared lightweight slope incompatibility is FAIL and absent reserve metric never becomes PASS',()=>{
 const run=boot('MARS','PRACTICE-LITE');const assessment=dispatch('GET',`/compatibility?run_id=${run.snapshot.run_id}`,null).body as S['CompatibilityAssessment'];expect(assessment.dimensions.find(d=>d.metric_id==='max_surface_slope_deg')).toMatchObject({status:'FAIL'});expect(assessment.dimensions.find(d=>d.metric_id==='max_surface_slope_deg')!.explanation).toContain('12 deg');expect(assessment.dimensions.find(d=>d.metric_id==='energy_reserve_pct')!.status).toBe('UNKNOWN');
});
it('display manifests preserve body-specific affine geometry, Earth corner order, masks and image bytes',async()=>{
 const run=boot();const layers=dispatch('GET',`/display-layers?run_id=${run.snapshot.run_id}`,null).body as S['ListDisplayLayerManifest'];expect(layers.items).toHaveLength(7);const target=layers.items.find(l=>l.body==='MARS')!;expect(target.earth_corners).toBeNull();expect(target.display_crs_wkt).toContain('Mars');expect(target.nodata_transparent).toBe(true);expect(target.support_scale_m).toBe(480);
 const earth=layers.items.find(l=>l.candidate_id===run.candidates[0]!.id)!;const [west,south,east,north]=run.candidates[0]!.aoi.bbox;expect(earth.earth_corners).toEqual([[west,north],[east,north],[east,south],[west,south]]);expect(earth.pixel_to_world[5]).toBeLessThan(0);
 const server=setupServer(...handlers);server.listen();try{const image=await fetch(`http://localhost/api/v1/artifacts/${target.image_artifact_sha256}`);expect(image.headers.get('Content-Type')).toBe('image/png');const bytes=new Uint8Array(await image.arrayBuffer());expect([...bytes.slice(0,8)]).toEqual([137,80,78,71,13,10,26,10]);}finally{server.close();}
});

it('design/search/diagnosis artifacts and exact content-addressed constraints survive canonical graph and raster variants',async()=>{
 vi.useFakeTimers();const graph=boot('MARS','ARES-1','synthetic-graph-regression-v1');post(`/runs/${graph.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:graph.snapshot.revision,payload:{candidate_id:graph.candidates[0]!.id}});await vi.advanceTimersByTimeAsync(1500);
 expect(graph.tests).toHaveLength(2);for(const test of graph.tests){const raw=dispatch('GET',`/artifacts/${test.constraints_sha256}`,null);expect(typeof raw.body).toBe('string');expect(createHash('sha256').update(String(raw.body)).digest('hex')).toBe(test.constraints_sha256);expect(JSON.parse(String(raw.body))).toMatchObject({artifact_kind:'SYNTHETIC_GRAPH_REGRESSION',mission_revision_id:graph.snapshot.mission_revision_id,rover_revision_id:graph.snapshot.rover_revision_id});}
 for(const algorithm of ['design-benchmark','search-route','diagnose-result'])expect(graph.evidence.some(e=>e.algorithm_id===algorithm)).toBe(true);
 scenarioArtifacts.GRAPH=structuredClone(graph.artifacts);writeFileSync('src/mock/fixtures/scenario-artifacts.json',JSON.stringify(scenarioArtifacts,null,2)+'\n');
});
it('local dataset mineral unknown cites missing target evidence while the Earth mineral dataset is present',()=>{
 const run=boot('MARS','ARES-1','local-dataset-practice-v1');for(const row of run.qualifications.filter(q=>q.requirement_id==='R-MINERAL')){expect(row.status).toBe('UNKNOWN');const artifact=run.artifacts[run.evidence.find(e=>e.id===row.evidence_ids[0])!.artifact_sha256!] as {reason_code:string};expect(artifact.reason_code).toBe('TARGET_EVIDENCE_MISSING');expect(row.explanation).toContain('TARGET_EVIDENCE_MISSING');}
});
it.each(['APPROVE_EVIDENCE','REJECT_EVIDENCE'])('review-proxy %s acknowledges only the exact proposal and preserves scientific unknowns',action_type=>{
 db.settings.previewScenario='review-proxy';const run=boot();const review=run.snapshot.pending_review!;expect(review.kind).toBe('PROXY');const qualifiers=structuredClone(run.qualifications);const mission=cloneContract(run);
 expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type,expected_revision:run.snapshot.revision,payload:{review_id:review.review_id,evidence_ids:review.evidence_ids,comment:'Reviewed assumption scope'}}).status).toBe(202);expect(run.snapshot.pending_review).toBeNull();expect(run.qualifications).toEqual(qualifiers);expect(db.contracts[run.snapshot.mission_revision_id]).toEqual(mission);expect((dispatch('GET',`/reviews/${review.review_id}`,null).body as S['ReviewRequest']).status).toBe(action_type==='APPROVE_EVIDENCE'?'APPROVED':'REJECTED');
});
it('blocked-worker retry is restricted to the recorded dependency and resumes once with unchanged inputs',()=>{
 db.settings.previewScenario='blocked-worker';const run=boot();expect(run.snapshot.state).toBe('BLOCKED');expect(run.snapshot.blocked_dependencies).toEqual(['worker']);const contract=cloneContract(run);
 expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'RETRY',expected_revision:run.snapshot.revision,payload:{dependency_id:'invented'}}).status).toBe(409);
 expect(post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'RETRY',expected_revision:run.snapshot.revision,payload:{dependency_id:'worker'}}).status).toBe(202);advanceRun(run);expect(run.snapshot.state).toBe('AWAITING_REVIEW');expect(run.snapshot.blocked_dependencies).toEqual([]);expect(db.contracts[run.snapshot.mission_revision_id]).toEqual(contract);
});
it('canonical graph selecting corridor B retains both attempts instead of applying raster filtering twice',async()=>{
 vi.useFakeTimers();const run=boot('MARS','ARES-1','synthetic-graph-regression-v1');post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[1]!.id}});await vi.advanceTimersByTimeAsync(1500);expect(run.results.map(result=>result.outcome)).toEqual(['FAIL','PASS']);expect(run.results.map(result=>result.metrics.find(metric=>metric.metric_id==='route_distance_m')!.value)).toEqual([120,230]);
});

it('passport publication is singleflight and the frozen passport identity cannot change during slow rendering',async()=>{
 vi.useFakeTimers();let complete:(response:Response)=>void=()=>undefined;
 const render=vi.spyOn(rendererBridge,'renderMockExport').mockImplementation(()=>new Promise(resolve=>{complete=resolve;}));Object.assign(window,{__MSW__:true});
 try{const run=boot();post(`/runs/${run.snapshot.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}});await vi.advanceTimersByTimeAsync(1900);expect(run.snapshot.state).toBe('BUILDING_PASSPORT');const frozenId=(run.exportBundle!.passport as S['AnalogPassport']).id;
 for(let n=0;n<5;n++)advanceRun(run);expect(render).toHaveBeenCalledTimes(1);expect((run.exportBundle!.passport as S['AnalogPassport']).id).toBe(frozenId);
 complete(Response.json({manifest_sha256:'b'.repeat(64)}));await vi.advanceTimersByTimeAsync(1);expect(run.snapshot.state).toBe('COMPLETED');expect(run.snapshot.passport_id).toBe(frozenId);for(let n=0;n<5;n++)advanceRun(run);expect(render).toHaveBeenCalledTimes(1);expect(run.snapshot.passport_id).toBe(frozenId);
 }finally{delete (window as Window&{__MSW__?:boolean}).__MSW__;render.mockRestore();}
});
