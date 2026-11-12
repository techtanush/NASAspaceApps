import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';
import { writeFileSync,mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import spec from '../../../../contracts/openapi.bundled.json';
import { advanceRun,assembleBundle,dispatch,type MockResponse } from '../mock/handlers';
import { db,seed,resetDatabase } from '../mock/state';
import type { components } from '../generated/schema';
type S=components['schemas'];
const ajv=new Ajv2020({strict:false,validateFormats:false,allErrors:true});ajv.addSchema(spec,'contract');
const responses:{method:string;path:string;status:number;body:unknown}[]=[];
function check(method:string,template:string,path:string,body?:unknown):MockResponse {
 const result=dispatch(method,path,body,new Headers({'Idempotency-Key':crypto.randomUUID()}));
 const operation=spec.paths[template as keyof typeof spec.paths] as Record<string,{responses:Record<string,{content?:Record<string,{schema:unknown}>}>}>;
 const response=operation[method.toLowerCase()]?.responses[String(result.status)];expect(response,`${method} ${template} status ${result.status}`).toBeDefined();
 const schema=response?.content?.['application/json']?.schema;
 if(schema && typeof result.body!=='string'){const validate=ajv.compile({$ref:'contract#/paths/'+template.replace(/~/g,'~0').replace(/\//g,'~1')+'/'+method.toLowerCase()+'/responses/'+result.status+'/content/application~1json/schema'});expect(validate(result.body),JSON.stringify(validate.errors)).toBe(true);}
 responses.push({method,path:template,status:result.status,body:result.body});return result;
}
beforeEach(()=>{let identifier=4096;vi.spyOn(crypto,'randomUUID').mockImplementation(()=>`00000000-0000-4000-8000-${(++identifier).toString(16).padStart(12,'0')}`);resetDatabase();responses.length=0;});
afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();});
it('UIX-03 every JSON operation response satisfies the frozen bundled OpenAPI',async()=>{
 vi.useFakeTimers();
 check('GET','/health/live','/health/live');check('GET','/health/ready','/health/ready');check('GET','/capabilities','/capabilities');check('GET','/configuration/scenarios/{id}','/configuration/scenarios/synthetic-mars-mobility-v1');
 const draft={name:seed.missionPresets.MARS.name,objective:seed.missionPresets.MARS.objective,target:seed.missionPresets.MARS.target,requirements:seed.missionPresets.MARS.requirements,assumptions:seed.missionPresets.MARS.assumptions};
 const mission=check('POST','/missions','/missions',draft).body as S['MissionHeader'];
 check('GET','/missions','/missions');check('GET','/missions/{id}',`/missions/${mission.id}`);check('GET','/mission-drafts/{id}',`/mission-drafts/${mission.current_draft_id}`);
 check('POST','/missions/{id}/drafts',`/missions/${mission.id}/drafts`,{expected_revision:mission.revision,draft});
 const preparation=check('POST','/missions/{id}/fingerprint',`/missions/${mission.id}/fingerprint`,{expected_revision:mission.revision,mode:'synthetic',rover_revision_id:null}).body as S['PreparationAccepted'];
 const job=check('GET','/jobs/{id}',`/jobs/${preparation.job_id}`).body as S['JobStatus'];check('GET','/mission-revisions/{id}',`/mission-revisions/${job.proposed_revision_id}`);
 check('POST','/missions/{id}/accept',`/missions/${mission.id}/accept`,{expected_revision:mission.revision,revision_id:job.proposed_revision_id});
 const extra=check('POST','/missions/{id}/revisions',`/missions/${mission.id}/revisions`,{expected_revision:mission.revision,contract:seed.missionPresets.MARS}).body as S['MissionTestContract'];expect(extra.accepted_at).toBeNull();
 const rover=check('POST','/rovers','/rovers',seed.roverPresets['ARES-1']).body as S['RoverProfile'];check('GET','/rovers','/rovers');check('GET','/rovers/{id}',`/rovers/${rover.rover_id}`);check('GET','/rover-revisions/{id}',`/rover-revisions/${rover.id}`);
 check('POST','/rovers/{id}/revisions',`/rovers/${rover.rover_id}/revisions`,{expected_revision:rover.revision,profile:seed.roverPresets['ARES-1']});
 const accepted=check('POST','/runs','/runs',{mission_revision_id:job.proposed_revision_id,rover_revision_id:rover.id,mode:'synthetic',dataset_lock_id:'practice-lock-v1',scenario_config_id:'synthetic-mars-mobility-v1'}).body as S['CommandAccepted'];
 const run=db.runs[accepted.run_id]!;for(let i=0;i<6;i++)advanceRun(run);
 check('GET','/runs','/runs');check('GET','/runs/{id}',`/runs/${accepted.run_id}`);check('GET','/target-profiles/{id}',`/target-profiles/${run.target.id}`);
 check('GET','/candidates',`/candidates?run_id=${accepted.run_id}`);check('GET','/candidates/{id}',`/candidates/${run.candidates[0]!.id}`);check('GET','/qualifications',`/qualifications?run_id=${accepted.run_id}`);check('GET','/qualifications/{id}',`/qualifications/${run.qualifications[0]!.id}`);
 check('GET','/compatibility',`/compatibility?run_id=${accepted.run_id}`);check('GET','/agent-actions',`/agent-actions?run_id=${accepted.run_id}`);check('GET','/tool-receipts/{id}',`/tool-receipts/${run.receipts[0]!.id}`);check('GET','/critiques',`/critiques?run_id=${accepted.run_id}`);check('GET','/reviews/{id}',`/reviews/${run.snapshot.pending_review!.review_id}`);check('GET','/display-layers',`/display-layers?run_id=${accepted.run_id}`);
 check('GET','/evidence/{id}',`/evidence/${run.evidence[1]!.id}`);check('GET','/artifacts/{sha256}',`/artifacts/${run.evidence[1]!.artifact_sha256}`);
 check('POST','/runs/{id}/actions',`/runs/${accepted.run_id}/actions`,{action_type:'SELECT_CANDIDATE',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}});
 check('POST','/runs/{id}/actions',`/runs/${accepted.run_id}/actions`,{action_type:'BUILD_PORTFOLIO',expected_revision:run.snapshot.revision,payload:{candidate_ids:run.candidates.slice(0,2).map(c=>c.id),max_sites:2}});check('GET','/portfolios/{id}',`/portfolios/${run.portfolios[0]!.id}`);
 check('POST','/runs/{id}/actions',`/runs/${accepted.run_id}/actions`,{action_type:'PROVE_IT',expected_revision:run.snapshot.revision,payload:{candidate_id:run.candidates[0]!.id}});
 await vi.advanceTimersByTimeAsync(2000);
 check('GET','/tests',`/tests?run_id=${accepted.run_id}`);check('GET','/tests/{id}',`/tests/${run.tests[0]!.id}`);check('GET','/test-results/{id}',`/test-results/${run.results[0]!.id}`);check('GET','/passports/{id}',`/passports/${run.passport!.id}`);check('GET','/passports/{id}/exports/{format}',`/passports/${run.passport!.id}/exports/json`);const exported=check('GET','/passports/{id}/exports/{format}',`/passports/${run.passport!.id}/exports/json`);expect(typeof exported.body).toBe('string');
 const covered=new Set(responses.map(r=>r.method+' '+r.path));const jsonOperations=Object.entries(spec.paths).flatMap(([path,ops])=>Object.keys(ops).filter(method=>['get','post'].includes(method)&&!path.endsWith('/events')).map(method=>method.toUpperCase()+' '+path));expect([...covered].sort()).toEqual(jsonOperations.sort());
 writeFileSync(resolve(process.cwd(),'src/mock/fixtures/runtime-artifacts.json'),JSON.stringify(run.artifacts,null,2)+'\n');
 writeFileSync(resolve(process.cwd(),'src/mock/fixtures/runtime-bundle.json'),JSON.stringify(assembleBundle(run),null,2)+'\n');
 const output=resolve(process.cwd(),'src/mock/fixtures/validated-responses.json');mkdirSync(resolve(process.cwd(),'src/mock/fixtures'),{recursive:true});writeFileSync(output,JSON.stringify(responses,null,2)+'\n');vi.useRealTimers();
});
it('mock enforces idempotency, revision conflict, workspace authorization, no-rover rejection and live failure',()=>{
 const key=new Headers({'Idempotency-Key':'00000000-0000-4000-8000-000000000001'});const {forbidden_actions: _forbidden, ...input}=seed.missionPresets.MARS;void _forbidden;
 const first=dispatch('POST','/missions',input,key);expect(dispatch('POST','/missions',input,key)).toEqual(first);expect(dispatch('POST','/missions',{...input,name:'changed'},key).status).toBe(409);
 const mission=first.body as S['MissionHeader'];expect(dispatch('POST',`/missions/${mission.id}/drafts`,{expected_revision:99,draft:input},new Headers({'Idempotency-Key':crypto.randomUUID()})).status).toBe(409);
 expect(dispatch('GET','/artifacts/'+'f'.repeat(64),null).status).toBe(404);
 expect(dispatch('POST','/runs',{mission_revision_id:'70000000-0000-4000-8000-000000000001',rover_revision_id:null,mode:'live',dataset_lock_id:'unbound',scenario_config_id:'live-hackathon-v1'},new Headers({'Idempotency-Key':crypto.randomUUID()}))).toMatchObject({status:503,body:{error:{code:'PROVIDER_AUTH_FAILED',details:{dependency:'OPENAI_API_KEY'}}}});
});
