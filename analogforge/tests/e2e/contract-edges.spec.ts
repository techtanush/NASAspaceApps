import {test,expect} from '@playwright/test';
import {newMission,startRun,tab,api,inspectHooks,isMock,choose} from './support/workbench';
for(const decision of ['APPROVE_EVIDENCE','REJECT_EVIDENCE'] as const)test(`review scope ${decision} preserves frozen scientific results`,async({page})=>{
 await newMission(page,{preview:isMock()?'review-proxy':undefined});await page.getByTestId('btn-start-run').click();await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state','AWAITING_REVIEW');
 const runId=page.url().match(/\/runs\/([^/]+)/)![1];
 const before=await api<{pending_review:{review_id:string;kind:string;status:string}|null;mission_revision_id:string}>(page,`/runs/${runId}`);
 await tab(page,'qualification');
 if(before.body.pending_review&&before.body.pending_review.kind!=='EVIDENCE_READY'){
  const frozen=await api(page,`/qualifications?run_id=${runId}`);
  const id=decision==='APPROVE_EVIDENCE'?'btn-approve-evidence':'btn-reject-evidence';
  await expect(page.getByTestId(id)).toBeVisible();await inspectHooks(page);await page.getByTestId(id).click();
  const review=await api<{status:string}>(page,`/reviews/${before.body.pending_review.review_id}`);expect(review.status).toBe(200);expect(review.body.status).toBe(decision==='APPROVE_EVIDENCE'?'APPROVED':'REJECTED');
  const after=await api<{mission_revision_id:string}>(page,`/runs/${runId}`);expect(after.body.mission_revision_id).toBe(before.body.mission_revision_id);
  const rows=await api(page,`/qualifications?run_id=${runId}`);expect(rows.body).toEqual(frozen.body);
 }else{
  expect(isMock(),'The explicit preview must create a reviewable proxy').toBe(false);
  await expect(page.getByTestId('btn-approve-evidence')).toHaveCount(0);await expect(page.getByTestId('btn-reject-evidence')).toHaveCount(0);
 }
});
test('blocked dependency retry retains accepted inputs and reaches review',async({page})=>{
 await newMission(page,{preview:isMock()?'blocked-worker':undefined});await page.getByTestId('btn-start-run').click();
 await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state',isMock()?'BLOCKED':/AWAITING_REVIEW|BLOCKED/);
 const runId=page.url().match(/\/runs\/([^/]+)/)![1];const before=await api<{blocked_dependencies:string[];mission_revision_id:string;rover_revision_id:string;mode:string}>(page,`/runs/${runId}`);
 if(before.body.blocked_dependencies.length){
  const retry=page.getByTestId('btn-retry-dependency').first();await expect(retry).toHaveAttribute('data-dependency-id',before.body.blocked_dependencies[0]);await inspectHooks(page);await retry.click();await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state','AWAITING_REVIEW');
  const after=await api<typeof before.body>(page,`/runs/${runId}`);for(const key of ['mission_revision_id','rover_revision_id','mode'] as const)expect(after.body[key]).toBe(before.body[key]);expect(after.body.blocked_dependencies).toEqual([]);
 }else{expect(isMock()).toBe(false);await expect(page.getByTestId('btn-retry-dependency')).toHaveCount(0);}
});
test('portfolio action exposes per-requirement coverage and residual gaps',async({page})=>{
 const runId=await startRun(page);await tab(page,'portfolio');await expect(page.getByTestId('btn-build-portfolio')).toBeVisible();await page.getByTestId('btn-build-portfolio').click();await expect(page.getByTestId('portfolio-row').first()).toBeVisible();
 for(const row of await page.getByTestId('portfolio-row').all()){await expect(row).toHaveAttribute('data-requirement-id',/.+/);await expect(row).toHaveAttribute('data-coverage',/.+/);}
 const snapshot=await api<{portfolio_ids:string[]}>(page,`/runs/${runId}`);expect(snapshot.body.portfolio_ids.length).toBeGreaterThan(0);const portfolio=await api<{id:string;run_id:string}>(page,`/portfolios/${snapshot.body.portfolio_ids[0]}`);expect(portfolio.status).toBe(200);expect(portfolio.body.run_id).toBe(runId);await inspectHooks(page);
});


test('editing an existing rover creates a new immutable revision with the frozen request shape',async({page})=>{
 await page.goto('/rovers');await expect(page.getByTestId('rover-form')).toBeVisible();
 const profiles=await api<{items:{id:string;rover_id:string;name:string;revision:number}[]}>(page,'/rovers');const prior=profiles.body.items.find(r=>r.name==='ARES-1')!;expect(prior).toBeTruthy();
 const frozen=await api(page,`/rover-revisions/${prior.id}`);await choose(page,'select-rover',prior.id);
 await page.locator('[data-testid=input-rover-field][data-field=name]').fill('ARES-1 field revision');await page.getByTestId('btn-rover-save').click();await expect(page.getByRole('status').filter({hasText:`Saved revision ${prior.revision+1}`})).toBeVisible();
 const unchanged=await api(page,`/rover-revisions/${prior.id}`);expect(unchanged.body).toEqual(frozen.body);
 const latest=await api<{items:{id:string;rover_id:string;name:string;revision:number}[]}>(page,'/rovers');expect(latest.body.items.some(r=>r.rover_id===prior.rover_id&&r.revision===prior.revision+1&&r.name==='ARES-1 field revision')).toBe(true);await inspectHooks(page);
});

test('job success keeps run settings locked until the proposed contract arrives',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.addInitScript(()=>{
  localStorage.setItem('af.theme','light');
  const state={requested:false,release:()=>{}};
  const pending=new Promise<void>(resolve=>{state.release=resolve;});
  Object.assign(window,{__proposalGate:state});
  const original=window.fetch.bind(window);
  window.fetch=async(input,init)=>{
   const path=new URL(input instanceof Request?input.url:String(input),location.href).pathname;
   if(path.startsWith('/api/v1/mission-revisions/')&&(init?.method??(input instanceof Request?input.method:'GET'))==='GET'){
    state.requested=true;await pending;
   }
   return original(input,init);
  };
 });
 await page.goto(isMock()?'/?mockLatency=300':'/');
 const authoring=newMission(page);
 await page.waitForFunction(()=>(window as unknown as {__proposalGate:{requested:boolean}}).__proposalGate.requested);
 try{
  await expect(page.locator('[data-testid=preparation-status][data-job-state=SUCCEEDED]')).toBeVisible();
  await expect(page.getByTestId('select-scenario')).toBeDisabled();
  await expect(page.getByTestId('select-mode')).toBeDisabled();
  await expect(page.getByTestId('btn-accept-contract')).toBeDisabled();
  await expect(page.getByRole('listbox')).toHaveCount(0);
 }finally{
  await page.evaluate(()=>(window as unknown as {__proposalGate:{release:()=>void}}).__proposalGate.release());
 }
 await authoring;
 await expect(page.getByTestId('select-scenario')).toBeEnabled();
 await page.keyboard.press('Tab');await page.evaluate(()=>scrollTo(0,0));
 await page.getByTestId('select-scenario').click();
 const selected=page.locator('[role=option][data-value=synthetic-mars-mobility-v1]');
 await expect(selected).toBeVisible();const bounds=await selected.boundingBox();
 expect(bounds).not.toBeNull();expect(bounds!.y).toBeGreaterThanOrEqual(0);expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(844);
 await selected.click();await expect(page.getByRole('listbox')).toHaveCount(0);
});
