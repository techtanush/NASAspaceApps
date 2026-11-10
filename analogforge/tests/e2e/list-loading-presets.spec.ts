import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
import {auditPage,finishAudit,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
test('candidate metadata fits the 40/60 split and four loading rows remain complete',async({page})=>{
 test.setTimeout(300000);await installAuditInstrumentation(page);
 await page.addInitScript(()=>{const original=window.fetch.bind(window);let release=()=>{};const gate=new Promise<void>(resolve=>{release=resolve;});Object.assign(window,{releaseWorkspace:release});window.fetch=async(input,init)=>{const url=new URL(input instanceof Request?input.url:String(input),location.href);if(new URLSearchParams(location.search).has('holdWorkspace')&&['/api/v1/missions','/api/v1/runs'].includes(url.pathname))await gate;return original(input,init);};});
 await page.goto('/?holdWorkspace=1');await expect(page.getByRole('status',{name:'Retrieving saved missions'})).toBeVisible();
 for(const width of [1440,390])for(const theme of ['dark','light'])for(const density of ['compact','default','comfortable']){
  await page.setViewportSize({width,height:900});await page.evaluate(({theme,density})=>{document.documentElement.dataset.theme=theme;document.documentElement.dataset.density=density;},{theme,density});
  for(const id of ['mission-list','run-list']){
   const table=page.getByTestId(id);await expect(table.locator('.table-overflow-hint')).toHaveCount(0);await expect(table.locator('tbody tr[aria-hidden=true]')).toHaveCount(4);
   const geometry=await table.evaluate(node=>{const slot=node.getBoundingClientRect(),region=node.querySelector('.table-scroll')!.getBoundingClientRect();return [...node.querySelectorAll('tbody tr')].map(row=>({top:row.getBoundingClientRect().top,bottom:row.getBoundingClientRect().bottom,min:Math.max(slot.top,region.top),max:Math.min(slot.bottom,region.bottom)}));});
   for(const row of geometry){expect(row.top).toBeGreaterThanOrEqual(row.min-1);expect(row.bottom).toBeLessThanOrEqual(row.max+1);}
  }
 }
 await page.evaluate(()=>(window as unknown as {releaseWorkspace:()=>void}).releaseWorkspace());await expect(page.getByRole('status',{name:'Retrieving saved missions'})).toBeHidden();
 await expect(page.locator('.workspace-table-slot .table-overflow-hint')).toHaveCount(0);
 const preset=page.locator('.practice-presets');await expect(preset).not.toHaveAttribute('open');await preset.locator('summary').click();await expect(preset.getByRole('link').first()).toBeVisible();const href=await preset.getByRole('link').first().getAttribute('href');expect(href).toContain('/missions/new?scenario=');await preset.locator('summary').click();
 await page.setViewportSize({width:1440,height:900});await expect(preset).toHaveAttribute('open');expect((await preset.boundingBox())!.height).toBeLessThanOrEqual(184);
 for(const width of [1440,390])for(const theme of ['dark','light'])await auditPage(page,'workspace-compact',{width,height:900,theme,focus:false});
 await startRun(page);await tab(page,'analogs');
 for(const width of [1920,1440,1280,390])for(const theme of ['dark','light']){
  await auditPage(page,'candidate-metadata',{width,height:900,theme,focus:false});
  const dimensions=await page.locator('.analogs-workspace').evaluate(node=>{const list=node.querySelector('.analogs-list-pane')!.getBoundingClientRect(),map=node.querySelector('.earth-map-panel')!.getBoundingClientRect(),scroll=node.querySelector('.candidate-table')!;const values=[...node.querySelectorAll('.candidate-metadata')].flatMap(item=>[...item.querySelectorAll(':scope>span')].map(value=>{const range=document.createRange();range.selectNodeContents(value);const r=range.getBoundingClientRect();return {left:r.left,right:r.right};}));return {ratio:list.width/(list.width+map.width),list:[list.left,list.right],width:scroll.clientWidth,scroll:scroll.scrollWidth,values};});
  if(width>=1280)expect(dimensions.ratio).toBeCloseTo(.4,2);expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width+1);for(const value of dimensions.values){expect(value.left).toBeGreaterThanOrEqual(dimensions.list[0]-1);expect(value.right).toBeLessThanOrEqual(dimensions.list[1]+1);}
 }
 const first=page.getByTestId('candidate-row').first();await first.getByTestId('btn-select-candidate').click();await expect(first).toHaveAttribute('data-selected','true');await first.locator('summary').click();await expect(first.getByText('WGS84 · bounds',{exact:true})).toBeVisible();
 await page.goto('/');await page.setViewportSize({width:390,height:900});await expect(page.getByTestId('run-row').first()).toBeVisible();await expect(page.getByTestId('run-list').locator('.table-overflow-hint')).toBeVisible();
 const findings=finishAudit();expect(findings,JSON.stringify(findings.slice(0,12))).toEqual([]);
});
