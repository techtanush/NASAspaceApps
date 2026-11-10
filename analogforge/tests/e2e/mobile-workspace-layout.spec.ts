import {test,expect} from '@playwright/test';
import {startRun,tab,prove} from './support/workbench';
import {auditPage,finishAudit,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
const spacing='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';
test('mobile workspace exposes work, keeps captions readable and groups passport assessments',async({page})=>{
 test.setTimeout(300000);await page.setViewportSize({width:390,height:844});await installAuditInstrumentation(page);await startRun(page);
 for(const name of ['analogs','qualification']){
  await tab(page,name);
  const chrome=await page.evaluate(()=>({heading:document.querySelector('main h1')!.getBoundingClientRect().top,bottom:document.querySelector('.operations-bar')!.getBoundingClientRect().bottom,height:document.querySelector('.operations-bar')!.getBoundingClientRect().height}));expect(chrome.heading).toBeLessThan(300);expect(chrome.bottom).toBeGreaterThanOrEqual(832);expect(chrome.height).toBeLessThanOrEqual(48);
  const rows=page.locator(name==='analogs'?'[data-testid=candidate-row]':'[data-testid=qualification-matrix] tbody tr');await expect(rows.nth(1)).toBeVisible();
  const positions=await page.evaluate(selector=>{const rows=[...document.querySelectorAll(selector)].slice(0,2);const footer=document.querySelector('.operations-bar')!.getBoundingClientRect();return rows.map(row=>({top:row.getBoundingClientRect().top,bottom:row.getBoundingClientRect().bottom,limit:Math.min(innerHeight,footer.top)}));},name==='analogs'?'[data-testid=candidate-row]':'[data-testid=qualification-matrix] tbody tr');
  expect(positions).toHaveLength(2);for(const row of positions){expect(row.top).toBeGreaterThanOrEqual(0);expect(row.bottom).toBeLessThanOrEqual(row.limit+1);}
  for(const theme of ['dark','light'])await auditPage(page,`mobile-${name}`,{width:390,height:844,theme,focus:false});
 }
 for(const width of [375,390,768]){
  await page.setViewportSize({width,height:844});const sheet=await page.addStyleTag({content:spacing});
  const frame=page.locator('[data-testid=qualification-matrix] .table-frame');const caption=frame.locator('.table-caption');const before=await caption.boundingBox();expect(before).not.toBeNull();
  const containment=await caption.evaluate(node=>{const range=document.createRange();range.selectNodeContents(node);const text=range.getBoundingClientRect(),frame=node.parentElement!.getBoundingClientRect();return {left:text.left,right:text.right,min:frame.left,max:frame.right};});expect(containment.left).toBeGreaterThanOrEqual(containment.min-1);expect(containment.right).toBeLessThanOrEqual(containment.max+1);
  await frame.locator('.table-scroll').evaluate(node=>{node.scrollLeft=node.scrollWidth;});const after=await caption.boundingBox();expect(after!.x).toBeCloseTo(before!.x,1);expect(after!.width).toBeCloseTo(before!.width,1);await sheet.evaluate(node=>node.remove());
 }
 await page.setViewportSize({width:390,height:844});await page.locator('.run-metadata>summary').click();await expect(page.getByTestId('btn-cancel-run')).toBeVisible();await expect(page.getByRole('navigation',{name:'Workspace navigation'}).getByRole('link',{name:'Rovers',exact:true})).toBeVisible();await page.locator('.run-metadata>summary').click();
 await tab(page,'analogs');await page.getByTestId('candidate-row').first().getByTestId('btn-select-candidate').click();await tab(page,'test-lab');await expect(page.getByTestId('btn-prove-it')).toBeInViewport();
 const exposure=page.locator('.accepted-benchmarks tbody tr').filter({hasText:'Unique slope exposure'});await expect(exposure.getByRole('cell').first()).toContainText('At least');await expect(exposure.getByText('unique_slope_exposure_m',{exact:false})).toBeHidden();await exposure.locator('summary').click();await expect(exposure.getByText('Requirement: R-EXPOSURE',{exact:true})).toBeVisible();await expect(exposure.getByText('Operator: GTE',{exact:true})).toBeVisible();await expect(exposure.getByText('Observable: unique_slope_exposure_m',{exact:true})).toBeVisible();await exposure.locator('summary').click();
 for(const theme of ['dark','light'])await auditPage(page,'mobile-experiment',{width:390,height:844,theme,focus:false});
 await prove(page);await tab(page,'passport');
 for(const width of [1440,390])for(const theme of ['dark','light']){
  await auditPage(page,'passport-grouped',{width,height:width===390?844:900,theme,focus:false});
  const groups=await page.locator('.passport-requirements tbody').evaluateAll(groups=>groups.map(group=>{const heading=group.querySelector('th')!,first=group.querySelector('td')!;return {heading:heading.getBoundingClientRect().top,first:first.getBoundingClientRect().top,rows:group.querySelectorAll('tr').length,span:(heading as HTMLTableCellElement).rowSpan};}));
  expect(groups.length).toBeGreaterThan(0);for(const group of groups){expect(Math.abs(group.heading-group.first)).toBeLessThanOrEqual(1);expect(group.span).toBe(group.rows);}
 }
 await page.setViewportSize({width:794,height:1123});const priorDisclosures=await page.locator('.passport-sheet details').evaluateAll(nodes=>nodes.map(node=>(node as HTMLDetailsElement).open));await page.emulateMedia({media:'print'});await expect(page.locator('.passport-sheet details:not([open])')).toHaveCount(0);await expect(page.locator('.passport-print-context')).toContainText('Contract revision');await expect(page.locator('.passport-assessment-metrics').first()).toBeVisible();await expect(page.locator('.passport-evidence-reference').first()).toContainText('Evidence:');const print=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,digest:document.querySelector('[data-testid=manifest-digest]')!.getBoundingClientRect().bottom}));expect(print.width).toBeLessThanOrEqual(print.viewport);expect(print.digest).toBeLessThanOrEqual(986.46);await page.pdf({path:'../../out/three-layouts-passport.pdf',format:'A4',margin:{top:'18mm',bottom:'18mm',left:'18mm',right:'18mm'}});await page.emulateMedia({media:'screen'});await expect.poll(()=>page.locator('.passport-sheet details').evaluateAll(nodes=>nodes.map(node=>(node as HTMLDetailsElement).open))).toEqual(priorDisclosures);
 const findings=finishAudit();expect(findings,JSON.stringify(findings.slice(0,12))).toEqual([]);
});
