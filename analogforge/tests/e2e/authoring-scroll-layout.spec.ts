import {test,expect} from '@playwright/test';
import {newMission} from './support/workbench';
import {auditPage,finishAudit,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
test('authoring digest and acceptance controls stay clear of header controls when scrolled',async({page})=>{
 test.setTimeout(180000);await installAuditInstrumentation(page);await newMission(page);
 for(const [name,anchor] of [['authoring-contract-digest','[data-region=fingerprint] .hash-group'],['authoring-acceptance-controls','[data-region=run-configuration] .actions']]){
  for(const width of [1440,390])for(const theme of ['dark','light']){
   await auditPage(page,name,{width,height:width===390?844:900,theme,focus:true,anchor});await expect(page.locator(anchor).first()).toBeVisible();
  }
 }
 const findings=finishAudit();expect(findings,JSON.stringify(findings.slice(0,12))).toEqual([]);
});
