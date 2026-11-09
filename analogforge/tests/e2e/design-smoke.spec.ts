import {test,expect} from '@playwright/test';
// Shared executable visual rules; this is a fast regression complement to the full crawl.
import {auditPage,auditGlyphs,finishAudit,installAuditInstrumentation,auditFailures} from '../../scripts/ui/visual_audit.mjs';
test('design rules reject visual regressions on the shell and full component kit',async({page})=>{
 test.setTimeout(180000);await installAuditInstrumentation(page);
 const external:string[]=[];const browserErrors:string[]=[];
 // Record attempted foreign resources without depending on their availability.
 await page.route(url=>/^https?:$/.test(url.protocol)&&url.origin!==(process.env.E2E_BASE_URL||'http://127.0.0.1:5176'),route=>route.fulfill({status:200,contentType:'text/css',body:''}));
 page.on('request',request=>{if(/^https?:/.test(request.url())&&new URL(request.url()).origin!==(process.env.E2E_BASE_URL||'http://127.0.0.1:5176'))external.push(request.url());});
 page.on('pageerror',error=>browserErrors.push(error.message));
 for(const path of ['/','/__styleguide']){
  await page.goto(path);await expect(page.locator('main h1')).toBeVisible();
  for(const theme of ['dark','light'])for(const width of [1440,390]){const findings=await auditPage(page,path==='/'?'S01-smoke':'styleguide-smoke',{theme,width,height:900,focus:true});expect(findings,JSON.stringify(findings.slice(0,12))).toEqual([]);}
  if(path==='/__styleguide')await auditGlyphs(page);
 }
 expect(auditFailures(page),'C12 unexpected transport failures').toEqual([]);
 expect(external,'C01 external requests').toEqual([]);expect(browserErrors,'C12 browser errors').toEqual([]);
 const found=finishAudit();expect(found.length,JSON.stringify(found.slice(0,12))).toBe(0);
});
