import {test,expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import {startRun,tab} from './support/workbench';
import {auditPage,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
test('screening placeholders retain committed row geometry',async({page})=>{
 test.setTimeout(300000);await installAuditInstrumentation(page);await page.goto('/?mockLatency=300');await startRun(page);await tab(page,'analogs');
 const observations=[];
 for(const width of [1280,390])for(const theme of ['dark','light'])for(const density of ['compact','default','comfortable']){
  const findings=await auditPage(page,'S06-cls-focused',{width,height:width===390?844:800,theme,density,focus:false});
  const observed=await page.evaluate(()=>({cls:(window as unknown as {__auditCLS:number}).__auditCLS,shifts:(window as unknown as {__auditShifts:unknown[]}).__auditShifts,scroll:document.querySelector('.candidate-table')!.scrollWidth,client:document.querySelector('.candidate-table')!.clientWidth,list:document.querySelector('.analogs-list-pane')!.getBoundingClientRect().width,map:document.querySelector('.earth-map-panel')!.getBoundingClientRect().width,rows:[...document.querySelectorAll('[data-testid=candidate-row]')].slice(0,2).map(row=>row.getBoundingClientRect().bottom),limit:document.querySelector('.operations-bar')!.getBoundingClientRect().top}));
  observations.push({width,theme,density,...observed,findings});console.log(JSON.stringify(observations.at(-1)));
  expect(findings,JSON.stringify(findings)).toEqual([]);expect(observed.cls).toBeLessThanOrEqual(.02);expect(observed.scroll).toBeLessThanOrEqual(observed.client+1);if(width===390)for(const bottom of observed.rows)expect(bottom).toBeLessThanOrEqual(observed.limit+1);else expect(observed.list/(observed.list+observed.map)).toBeCloseTo(.4,2);
 }
 writeFileSync('../../out/s06-cls-focused.json',JSON.stringify(observations,null,2));
});
test('pending rank and committed status remain contained with expanded text spacing',async({page})=>{
 test.setTimeout(120000);await page.goto('/?mockLatency=300');await startRun(page);await tab(page,'analogs');
 await page.addInitScript(()=>{if(!new URLSearchParams(location.search).has('holdScreening'))return;const original=window.fetch.bind(window);let release=()=>{};const gate=new Promise<void>(resolve=>{release=resolve;});Object.assign(window,{releaseScreening:release});window.fetch=async(input,init)=>{const url=new URL(input instanceof Request?input.url:String(input),location.href);if(url.pathname.startsWith('/api/v1/evidence/'))await gate;return original(input,init);};});
 const url=page.url();const observations:Record<string,unknown>[]=[];
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:844});await page.goto(url+'?holdScreening=1');const rank=page.getByTestId('candidate-row').first().locator('.screening-rank');await expect(rank).toHaveText('Unknown');await page.evaluate(()=>document.fonts.ready);await page.addStyleTag({content:'*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'});
  const observation=await rank.evaluate(node=>{const r=node.getBoundingClientRect();const range=document.createRange();range.selectNodeContents(node);const g=range.getBoundingClientRect();return {width:r.width,glyphWidth:g.width,left:g.left,right:g.right,min:r.left,max:r.right};});observations.push({viewport:width,...observation});console.log(JSON.stringify(observations.at(-1)));expect(observation.left).toBeGreaterThanOrEqual(observation.min);expect(observation.right).toBeLessThanOrEqual(observation.max);await page.evaluate(()=>(window as unknown as {releaseScreening:()=>void}).releaseScreening());await expect(rank).not.toHaveText('Unknown');const status=page.getByTestId('candidate-row').first().locator('.candidate-screening');await expect(status).toHaveText('Shortlisted');const committedStatus=await status.evaluate(node=>{const r=node.getBoundingClientRect();const range=document.createRange();range.selectNodeContents(node);const g=range.getBoundingClientRect();return {width:r.width,glyphWidth:g.width,left:g.left,right:g.right,min:r.left,max:r.right};});observations[observations.length-1]={...observations[observations.length-1],committedStatus};console.log(JSON.stringify({viewport:width,committedStatus}));expect(committedStatus.left).toBeGreaterThanOrEqual(committedStatus.min);expect(committedStatus.right).toBeLessThanOrEqual(committedStatus.max);
 }
 writeFileSync('../../out/s06-pending-spacing-after.json',JSON.stringify(observations,null,2));
});
