import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
// @ts-expect-error Shared runtime audit instrumentation.
import {auditPage,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
test('fresh audit cohorts retain the controlled document and loaded heading',async({page})=>{
 test.setTimeout(240000);await installAuditInstrumentation(page);await startRun(page);await tab(page,'qualification');
 for(let index=0;index<48;index++){
  const findings=await auditPage(page,'S07-navigation-stress',{width:index%2?390:1440,height:index%2?844:900,theme:index%2?'light':'dark',density:['compact','default','comfortable'][index%3],focus:false,expectedHeading:'Qualification'});expect(findings).toEqual([]);
  expect(await page.evaluate(()=>!!navigator.serviceWorker.controller)).toBe(true);
 }
});
